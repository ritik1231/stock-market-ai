import asyncio
import logging
from typing import Optional
from uuid import UUID

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_HWM_TTL = 365 * 24 * 3600  # 1 year — effectively permanent


class AlpacaAPIError(Exception):
    pass


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
