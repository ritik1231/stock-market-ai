import asyncio
import logging
import threading
import time
from typing import Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.tools.broker_errors import BrokerAPIError, BrokerServerError  # noqa: F401 — re-exported

logger = logging.getLogger(__name__)
settings = get_settings()

# Session cache — Angel One sessions are valid for ~24 h; we refresh every 6 h
_session_lock = threading.Lock()
_session_obj = None
_session_expires = 0.0
_SESSION_TTL = 6 * 3600

# Symbol token cache: normalised ticker → (tradingsymbol, symboltoken, exchange)
_symbol_cache: dict[str, tuple[str, str, str]] = {}

_ANGEL_STATUS_MAP = {
    "complete": "filled",
    "cancelled": "canceled",
    "rejected": "rejected",
    "open": "accepted",
    "pending": "pending",
    "open pending": "pending",
    "trigger pending": "pending",
    "after market order req received": "pending",
    "modify pending": "pending",
    "not modified": "accepted",
}


def _map_status(raw: str) -> str:
    return _ANGEL_STATUS_MAP.get(raw.lower(), raw.lower())


def _make_fresh_session():
    import pyotp
    from SmartApi import SmartConnect

    if not all([
        settings.ANGEL_API_KEY,
        settings.ANGEL_CLIENT_ID,
        settings.ANGEL_PASSWORD,
        settings.ANGEL_TOTP_SECRET,
    ]):
        raise BrokerAPIError(
            "Angel One credentials not configured — set ANGEL_API_KEY, "
            "ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET"
        )

    obj = SmartConnect(api_key=settings.ANGEL_API_KEY)
    totp = pyotp.TOTP(settings.ANGEL_TOTP_SECRET).now()
    data = obj.generateSession(
        settings.ANGEL_CLIENT_ID,
        settings.ANGEL_PASSWORD,
        totp,
    )
    if not data.get("status"):
        raise BrokerAPIError(
            f"Angel One login failed: {data.get('message', 'unknown error')}"
        )
    return obj


def _get_session():
    global _session_obj, _session_expires
    now = time.monotonic()
    with _session_lock:
        if _session_obj is None or now >= _session_expires:
            _session_obj = _make_fresh_session()
            _session_expires = now + _SESSION_TTL
    return _session_obj


def _resolve_symbol(ticker: str) -> tuple[str, str, str]:
    """Return (tradingsymbol, symboltoken, exchange) for a ticker.

    Caches results — symbol tokens are stable.
    """
    key = ticker.upper()
    if key in _symbol_cache:
        return _symbol_cache[key]

    if ticker.upper().endswith(".BO"):
        exchange = "BSE"
        clean = ticker[:-3].upper()
    else:
        exchange = "NSE"
        clean = ticker.replace(".NS", "").replace(".ns", "").upper()

    obj = _get_session()
    result = obj.searchScrip(exchange=exchange, searchscrip=clean)
    if result.get("status") and result.get("data"):
        eq_sym = f"{clean}-EQ"
        for item in result["data"]:
            if item.get("tradingsymbol") == eq_sym:
                entry = (eq_sym, str(item["symboltoken"]), exchange)
                _symbol_cache[key] = entry
                return entry
        # Fall back to the first hit
        item = result["data"][0]
        entry = (item["tradingsymbol"], str(item["symboltoken"]), exchange)
        _symbol_cache[key] = entry
        return entry

    raise BrokerAPIError(f"Symbol not found on {exchange}: {clean}")


async def get_account() -> dict:
    def _call() -> dict:
        obj = _get_session()
        rms = obj.getRMS()
        if not rms.get("status"):
            raise BrokerAPIError(f"getRMS failed: {rms.get('message')}")
        data = rms.get("data", {})
        net = float(data.get("net", 0))
        used = float(data.get("utilisedAmount", 0))
        available = float(data.get("availablecash", net - used))
        return {
            "equity": net,
            "buying_power": available,
            "portfolio_value": net,
            "cash": available,
            # India-specific aliases
            "used_margin": used,
            "available_cash": available,
        }

    try:
        return await asyncio.to_thread(_call)
    except BrokerAPIError:
        raise
    except Exception as exc:
        raise BrokerAPIError(f"get_account failed: {exc}") from exc


async def get_positions() -> list[dict]:
    def _call() -> list[dict]:
        obj = _get_session()
        result = obj.position()
        if not result.get("status"):
            raise BrokerAPIError(f"position() failed: {result.get('message')}")
        positions = result.get("data") or []
        out = []
        for p in positions:
            qty = float(p.get("netqty", 0))
            if qty == 0:
                continue
            price = float(p.get("ltp", 0))
            out.append({
                "ticker": p.get("tradingsymbol", ""),
                "qty": qty,
                "avg_entry": float(p.get("averageprice", 0)),
                "current_price": price,
                "unrealized_pnl": float(p.get("unrealised", 0)),
                "market_value": round(qty * price, 4),
            })
        return out

    try:
        return await asyncio.to_thread(_call)
    except BrokerAPIError:
        raise
    except Exception as exc:
        raise BrokerAPIError(f"get_positions failed: {exc}") from exc


@retry(
    retry=retry_if_exception_type(BrokerServerError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def place_order(
    ticker: str,
    action: str,
    qty: int,
    limit_price: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    def _call() -> dict:
        tradingsymbol, symboltoken, exchange = _resolve_symbol(ticker)
        obj = _get_session()

        orderparams = {
            "variety": "ROBO",
            "tradingsymbol": tradingsymbol,
            "symboltoken": symboltoken,
            "transactiontype": "BUY" if action.upper() == "BUY" else "SELL",
            "exchange": exchange,
            "ordertype": "LIMIT",
            "producttype": "BO",
            "duration": "DAY",
            "price": str(round(limit_price, 2)),
            "squareoff": str(round(take_profit, 2)),
            "stoploss": str(round(stop_loss, 2)),
            "quantity": str(qty),
        }

        result = obj.placeOrder(orderparams)
        if not result.get("status"):
            msg = result.get("message", "unknown")
            if any(code in str(result.get("errorcode", "")) for code in ("AG8000", "AG8001", "500")):
                raise BrokerServerError(f"place_order server error (retryable): {msg}")
            raise BrokerAPIError(f"place_order failed: {msg}")

        data = result.get("data", {})
        return {
            "order_id": data.get("uniqueorderid") or data.get("orderid", ""),
            "status": "accepted",
            "symbol": tradingsymbol,
            "qty": qty,
            "limit_price": limit_price,
            "created_at": None,
        }

    try:
        return await asyncio.to_thread(_call)
    except BrokerAPIError:
        raise
    except Exception as exc:
        raise BrokerAPIError(f"place_order failed: {exc}") from exc


async def get_order(order_id: str) -> dict:
    def _call() -> dict:
        obj = _get_session()
        result = obj.individual_order_details(order_id)
        if not result.get("status"):
            raise BrokerAPIError(f"get_order failed: {result.get('message')}")

        data = result.get("data", {})
        raw_status = data.get("status", "unknown")
        avg_price_raw = data.get("averageprice") or data.get("avgprice")
        filled_price: Optional[float] = None
        if avg_price_raw:
            try:
                v = float(avg_price_raw)
                if v > 0:
                    filled_price = v
            except (TypeError, ValueError):
                pass

        return {
            "order_id": data.get("uniqueorderid") or data.get("orderid", order_id),
            "status": _map_status(raw_status),
            "filled_avg_price": filled_price,
            "filled_at": data.get("updatetime"),
        }

    try:
        return await asyncio.to_thread(_call)
    except BrokerAPIError:
        raise
    except Exception as exc:
        raise BrokerAPIError(f"get_order failed: {exc}") from exc


async def cancel_order(order_id: str) -> bool:
    def _call() -> bool:
        obj = _get_session()
        result = obj.cancelOrder("ROBO", order_id)
        return bool(result.get("status"))

    try:
        return await asyncio.to_thread(_call)
    except Exception:
        return False


async def close_position(ticker: str) -> dict:
    def _call() -> dict:
        obj = _get_session()

        # Find current position to determine close direction and qty
        pos_result = obj.position()
        positions = pos_result.get("data") or [] if pos_result.get("status") else []

        tradingsymbol, symboltoken, exchange = _resolve_symbol(ticker)
        target_pos = None
        for p in positions:
            if p.get("tradingsymbol", "").upper() == tradingsymbol.upper():
                target_pos = p
                break

        if not target_pos or float(target_pos.get("netqty", 0)) == 0:
            raise BrokerAPIError(f"No open position found for {ticker}")

        net_qty = float(target_pos["netqty"])
        close_side = "SELL" if net_qty > 0 else "BUY"
        close_qty = abs(int(net_qty))

        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": tradingsymbol,
            "symboltoken": symboltoken,
            "transactiontype": close_side,
            "exchange": exchange,
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(close_qty),
        }

        result = obj.placeOrder(orderparams)
        if not result.get("status"):
            raise BrokerAPIError(f"close_position failed: {result.get('message')}")

        data = result.get("data", {})
        return {
            "order_id": data.get("uniqueorderid") or data.get("orderid"),
            "status": "accepted",
            "symbol": tradingsymbol,
        }

    try:
        return await asyncio.to_thread(_call)
    except BrokerAPIError:
        raise
    except Exception as exc:
        raise BrokerAPIError(f"close_position failed: {exc}") from exc
