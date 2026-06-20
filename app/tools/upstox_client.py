"""Upstox v2 broker client — paper (sandbox) and live trading.

Setup:
  1. Register at https://developer.upstox.com/
  2. Create an app to get API_KEY + SECRET
  3. Complete the OAuth2 login flow to get an access_token
     (token is valid for 1 trading day — refresh daily)
  4. Set UPSTOX_ACCESS_TOKEN in .env
  5. Set UPSTOX_SANDBOX=true for sandbox (virtual funds), false for live

Instrument keys: Upstox uses NSE_EQ|<trading_symbol> format for most NSE equities.
Common symbols: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, WIPRO, ITC, SBIN
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.tools.broker_errors import BrokerAPIError, BrokerServerError

logger = logging.getLogger(__name__)
settings = get_settings()

_LIVE_BASE = "https://api.upstox.com"
_SANDBOX_BASE = "https://sandbox.upstox.com"

_ORDER_STATUS_MAP = {
    "complete": "filled",
    "cancelled": "canceled",
    "rejected": "rejected",
    "open": "accepted",
    "pending": "pending",
    "not modified": "accepted",
    "trigger pending": "pending",
    "after market order req received": "pending",
    "validation pending": "pending",
    "put order req received": "pending",
    "modify pending": "pending",
}

# In-memory instrument key cache: "RELIANCE.NS" → "NSE_EQ|RELIANCE"
_instrument_cache: dict[str, str] = {}


def _base() -> str:
    return _SANDBOX_BASE if settings.UPSTOX_SANDBOX else _LIVE_BASE


def _headers() -> dict:
    if not settings.UPSTOX_ACCESS_TOKEN:
        raise BrokerAPIError(
            "UPSTOX_ACCESS_TOKEN not configured — run the Upstox OAuth2 flow to get a token. "
            "See https://developer.upstox.com/docs/login-workflow"
        )
    return {
        "Authorization": f"Bearer {settings.UPSTOX_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _map_status(raw: str) -> str:
    return _ORDER_STATUS_MAP.get(raw.lower(), raw.lower())


def _instrument_key(ticker: str) -> str:
    """Convert NSE/BSE ticker to Upstox instrument_key.

    Upstox format: NSE_EQ|<trading_symbol> or BSE_EQ|<trading_symbol>
    E.g. "RELIANCE.NS" → "NSE_EQ|RELIANCE"
    """
    if ticker in _instrument_cache:
        return _instrument_cache[ticker]

    t = ticker.upper()
    if t.endswith(".BO"):
        exchange = "BSE_EQ"
        symbol = t[:-3]
    else:
        exchange = "NSE_EQ"
        symbol = t.replace(".NS", "")

    key = f"{exchange}|{symbol}"
    _instrument_cache[ticker] = key
    return key


def _raise_for_error(data: dict, context: str) -> None:
    if data.get("status") not in ("success", "ok"):
        msg = data.get("message") or data.get("errors") or "unknown error"
        err_code = str(data.get("error_code", ""))
        if any(code in err_code for code in ("UDAPI10000", "UDAPI10001", "5xx")):
            raise BrokerServerError(f"{context}: {msg}")
        raise BrokerAPIError(f"{context}: {msg}")


async def get_account() -> dict:
    try:
        async with httpx.AsyncClient(base_url=_base(), timeout=10) as client:
            resp = await client.get("/v2/user/fund-margin", headers=_headers())
            resp.raise_for_status()
            data = resp.json()
        _raise_for_error(data, "get_account")
        equity_data = (data.get("data") or {}).get("equity") or {}
        available = float(equity_data.get("available_margin", 0))
        used = float(equity_data.get("used_margin", 0))
        total = available + used
        return {
            "equity": round(total, 2),
            "buying_power": round(available, 2),
            "portfolio_value": round(total, 2),
            "cash": round(available, 2),
            "used_margin": round(used, 2),
            "available_cash": round(available, 2),
        }
    except BrokerAPIError:
        raise
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise BrokerServerError(f"get_account HTTP {exc.response.status_code}") from exc
        raise BrokerAPIError(f"get_account HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        raise BrokerAPIError(f"get_account failed: {exc}") from exc


async def get_positions() -> list[dict]:
    try:
        async with httpx.AsyncClient(base_url=_base(), timeout=10) as client:
            resp = await client.get("/v2/portfolio/short-term-positions", headers=_headers())
            resp.raise_for_status()
            data = resp.json()
        _raise_for_error(data, "get_positions")
        out = []
        for p in (data.get("data") or []):
            qty = float(p.get("quantity", 0))
            if qty == 0:
                continue
            price = float(p.get("last_price", 0))
            out.append({
                "ticker": p.get("tradingsymbol", "").replace("-EQ", ""),
                "qty": qty,
                "avg_entry": float(p.get("average_price", 0)),
                "current_price": price,
                "unrealized_pnl": float(p.get("pnl", 0)),
                "market_value": round(qty * price, 2),
            })
        return out
    except BrokerAPIError:
        raise
    except Exception as exc:
        raise BrokerAPIError(f"get_positions failed: {exc}") from exc


async def place_order(
    ticker: str,
    action: str,
    qty: int,
    limit_price: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    instrument = _instrument_key(ticker)
    payload = {
        "quantity": qty,
        "product": "D",
        "validity": "DAY",
        "price": round(limit_price, 2),
        "tag": "stockai",
        "instrument_token": instrument,
        "order_type": "LIMIT",
        "transaction_type": "BUY" if action.upper() == "BUY" else "SELL",
        "disclosed_quantity": 0,
        "trigger_price": round(stop_loss, 2) if stop_loss else 0,
        "is_amo": False,
    }
    try:
        async with httpx.AsyncClient(base_url=_base(), timeout=10) as client:
            resp = await client.post("/v2/order/place", headers=_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        _raise_for_error(data, "place_order")
        order_id = (data.get("data") or {}).get("order_id", "")
        return {
            "order_id": order_id,
            "status": "accepted",
            "symbol": instrument,
            "qty": qty,
            "limit_price": limit_price,
            "created_at": None,
        }
    except BrokerAPIError:
        raise
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise BrokerServerError(f"place_order HTTP {exc.response.status_code}") from exc
        raise BrokerAPIError(f"place_order HTTP {exc.response.status_code}: {exc.response.text}") from exc
    except Exception as exc:
        raise BrokerAPIError(f"place_order failed: {exc}") from exc


async def get_order(order_id: str) -> dict:
    try:
        async with httpx.AsyncClient(base_url=_base(), timeout=10) as client:
            resp = await client.get(
                "/v2/order/details",
                headers=_headers(),
                params={"order_id": order_id},
            )
            resp.raise_for_status()
            data = resp.json()
        _raise_for_error(data, "get_order")
        d = data.get("data") or {}
        raw_status = d.get("status", "unknown")
        avg_price = d.get("average_price")
        filled_price: Optional[float] = None
        if avg_price:
            try:
                v = float(avg_price)
                if v > 0:
                    filled_price = v
            except (TypeError, ValueError):
                pass
        return {
            "order_id": d.get("order_id", order_id),
            "status": _map_status(raw_status),
            "filled_avg_price": filled_price,
            "filled_at": d.get("exchange_timestamp") or d.get("order_timestamp"),
        }
    except BrokerAPIError:
        raise
    except Exception as exc:
        raise BrokerAPIError(f"get_order failed: {exc}") from exc


async def cancel_order(order_id: str) -> bool:
    try:
        async with httpx.AsyncClient(base_url=_base(), timeout=10) as client:
            resp = await client.delete(
                "/v2/order/cancel",
                headers=_headers(),
                params={"order_id": order_id},
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("status") == "success"
    except Exception:
        return False


async def close_position(ticker: str) -> dict:
    positions = await get_positions()
    clean = ticker.upper().replace(".NS", "").replace(".BO", "")
    pos = next(
        (p for p in positions if p["ticker"].upper().replace("-EQ", "") == clean),
        None,
    )
    if not pos or pos["qty"] <= 0:
        raise BrokerAPIError(f"No open Upstox position for {ticker}")

    return await place_order(
        ticker=ticker,
        action="SELL",
        qty=int(pos["qty"]),
        limit_price=pos["current_price"],
        stop_loss=0.0,
        take_profit=0.0,
    )
