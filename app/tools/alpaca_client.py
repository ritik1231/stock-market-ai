import asyncio
import logging
from typing import Optional
from uuid import UUID

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_HWM_TTL = 365 * 24 * 3600  # 1 year — effectively permanent


class AlpacaAPIError(Exception):
    pass


class AlpacaServerError(AlpacaAPIError):
    """5xx / transient server errors from Alpaca — safe to retry."""


def _make_client():
    from alpaca.trading.client import TradingClient

    if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
        raise AlpacaAPIError("Alpaca API keys not configured")
    return TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=True,
    )


async def get_account() -> dict:
    def _call() -> dict:
        client = _make_client()
        acct = client.get_account()
        return {
            "equity": float(acct.equity or 0),
            "buying_power": float(acct.buying_power or 0),
            "portfolio_value": float(acct.portfolio_value or 0),
            "cash": float(acct.cash or 0),
        }

    try:
        return await asyncio.to_thread(_call)
    except AlpacaAPIError:
        raise
    except Exception as exc:
        raise AlpacaAPIError(f"get_account failed: {exc}") from exc


async def get_positions() -> list[dict]:
    def _call() -> list[dict]:
        client = _make_client()
        return [
            {
                "ticker": p.symbol,
                "qty": float(p.qty or 0),
                "avg_entry": float(p.avg_entry_price or 0),
                "current_price": float(p.current_price or 0),
                "unrealized_pnl": float(p.unrealized_pl or 0),
                "market_value": float(p.market_value or 0),
            }
            for p in client.get_all_positions()
        ]

    try:
        return await asyncio.to_thread(_call)
    except AlpacaAPIError:
        raise
    except Exception as exc:
        raise AlpacaAPIError(f"get_positions failed: {exc}") from exc


@retry(
    retry=retry_if_exception_type(AlpacaServerError),
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
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            StopLossRequest,
            TakeProfitRequest,
        )

        client = _make_client()
        side = OrderSide.BUY if action.upper() == "BUY" else OrderSide.SELL
        request = LimitOrderRequest(
            symbol=ticker,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=round(take_profit, 2)),
            stop_loss=StopLossRequest(stop_price=round(stop_loss, 2)),
        )
        order = client.submit_order(order_data=request)
        return {
            "order_id": str(order.id),
            "status": str(order.status.value) if order.status else "unknown",
            "symbol": order.symbol,
            "qty": int(float(order.qty)) if order.qty else qty,
            "limit_price": float(order.limit_price) if order.limit_price else limit_price,
            "created_at": str(order.created_at) if order.created_at else None,
        }

    try:
        return await asyncio.to_thread(_call)
    except AlpacaAPIError:
        raise
    except Exception as exc:
        exc_str = str(exc)
        if any(code in exc_str for code in ("500", "502", "503", "504", "server_error")):
            raise AlpacaServerError(f"place_order server error (retryable): {exc}") from exc
        raise AlpacaAPIError(f"place_order failed: {exc}") from exc


async def get_order(order_id: str) -> dict:
    def _call() -> dict:
        client = _make_client()
        order = client.get_order_by_id(UUID(order_id))
        filled_price: Optional[float] = None
        if order.filled_avg_price:
            filled_price = float(order.filled_avg_price)
        return {
            "order_id": str(order.id),
            "status": str(order.status.value) if order.status else "unknown",
            "filled_avg_price": filled_price,
            "filled_at": str(order.filled_at) if order.filled_at else None,
        }

    try:
        return await asyncio.to_thread(_call)
    except AlpacaAPIError:
        raise
    except Exception as exc:
        raise AlpacaAPIError(f"get_order failed: {exc}") from exc


async def cancel_order(order_id: str) -> bool:
    def _call() -> bool:
        client = _make_client()
        try:
            client.cancel_order_by_id(UUID(order_id))
            return True
        except Exception:
            return False

    try:
        return await asyncio.to_thread(_call)
    except Exception:
        return False


async def close_position(ticker: str) -> dict:
    def _call() -> dict:
        client = _make_client()
        result = client.close_position(ticker.upper())
        return {
            "order_id": str(result.id) if result.id else None,
            "status": str(result.status.value) if result.status else "unknown",
            "symbol": result.symbol,
        }

    try:
        return await asyncio.to_thread(_call)
    except AlpacaAPIError:
        raise
    except Exception as exc:
        raise AlpacaAPIError(f"close_position failed: {exc}") from exc
