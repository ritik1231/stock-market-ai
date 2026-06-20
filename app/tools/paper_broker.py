"""Self-contained paper trading engine.

Simulates order fills using real yfinance prices.  No brokerage account needed.
State is persisted in:
  - Postgres trades table  (fills / position history)
  - Redis                  (in-flight order details, 24-h TTL)

Starting cash is controlled by the PAPER_STARTING_CASH env var (default ₹10 lakh).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models.trading import Trade
from app.tools.cache import build_key, get_cache, set_cache

logger = logging.getLogger(__name__)
settings = get_settings()

_ORDER_TTL = 24 * 3600  # seconds — how long to keep order details in Redis


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _current_price(ticker: str, fallback: float) -> float:
    try:
        from app.tools.price_fetcher import get_latest_price, normalise_ticker
        return await get_latest_price(normalise_ticker(ticker))
    except Exception:
        return fallback


async def _all_paper_fills() -> list[Trade]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Trade).where(
                Trade.paper_mode.is_(True),
                Trade.status == "filled",
                Trade.filled_price.isnot(None),
            )
        )
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Public interface — mirrors broker module interface exactly
# ---------------------------------------------------------------------------

async def get_account() -> dict:
    cash = float(settings.PAPER_STARTING_CASH)
    for trade in await _all_paper_fills():
        amount = float(trade.filled_price) * trade.qty
        if trade.action.upper() == "BUY":
            cash -= amount
        else:
            cash += amount

    positions = await get_positions()
    positions_value = sum(p["market_value"] for p in positions)
    equity = cash + positions_value

    return {
        "equity": round(equity, 2),
        "buying_power": round(cash, 2),
        "portfolio_value": round(equity, 2),
        "cash": round(cash, 2),
        "used_margin": round(positions_value, 2),
        "available_cash": round(cash, 2),
    }


async def get_positions() -> list[dict]:
    holdings: dict[str, dict] = {}

    for trade in await _all_paper_fills():
        t = trade.ticker.upper()
        if t not in holdings:
            holdings[t] = {"qty": 0, "cost": 0.0}
        qty = trade.qty
        price = float(trade.filled_price)
        if trade.action.upper() == "BUY":
            holdings[t]["qty"] += qty
            holdings[t]["cost"] += price * qty
        else:
            holdings[t]["qty"] -= qty
            holdings[t]["cost"] -= price * qty

    positions = []
    for ticker, h in holdings.items():
        net_qty = h["qty"]
        if net_qty <= 0:
            continue
        avg_entry = h["cost"] / net_qty
        current = await _current_price(ticker, avg_entry)
        unrealized = (current - avg_entry) * net_qty
        positions.append({
            "ticker": ticker,
            "qty": float(net_qty),
            "avg_entry": round(avg_entry, 4),
            "current_price": round(current, 2),
            "unrealized_pnl": round(unrealized, 2),
            "market_value": round(current * net_qty, 2),
        })

    return positions


async def place_order(
    ticker: str,
    action: str,
    qty: int,
    limit_price: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    from app.tools.price_fetcher import normalise_ticker
    ticker = normalise_ticker(ticker)
    fill_price = await _current_price(ticker, limit_price)
    order_id = f"paper-{uuid.uuid4().hex[:16]}"
    filled_at = datetime.now(timezone.utc).isoformat()

    # Cache order details so get_order() can return them
    await set_cache(
        build_key("paper", "order", order_id),
        {
            "order_id": order_id,
            "status": "filled",
            "filled_avg_price": fill_price,
            "filled_at": filled_at,
        },
        ttl=_ORDER_TTL,
    )

    logger.info(
        "paper_order ticker=%s action=%s qty=%d fill_price=%.2f order_id=%s",
        ticker, action.upper(), qty, fill_price, order_id,
    )

    return {
        "order_id": order_id,
        "status": "accepted",
        "symbol": ticker,
        "qty": qty,
        "limit_price": fill_price,
        "created_at": filled_at,
    }


async def get_order(order_id: str) -> dict:
    data = await get_cache(build_key("paper", "order", order_id))
    if data:
        return {
            "order_id": data["order_id"],
            "status": "filled",
            "filled_avg_price": data.get("filled_avg_price"),
            "filled_at": data.get("filled_at"),
        }
    # Order not in cache (TTL expired) — report as filled
    return {
        "order_id": order_id,
        "status": "filled",
        "filled_avg_price": None,
        "filled_at": None,
    }


async def cancel_order(order_id: str) -> bool:
    # Paper orders fill instantly; nothing to cancel
    return False


async def close_position(ticker: str) -> dict:
    from app.tools.price_fetcher import normalise_ticker
    from app.tools.broker_errors import BrokerAPIError

    ticker = normalise_ticker(ticker)
    positions = await get_positions()
    pos = next(
        (p for p in positions if p["ticker"].upper() == ticker.upper()), None
    )
    if not pos or pos["qty"] <= 0:
        raise BrokerAPIError(f"No open paper position for {ticker}")

    return await place_order(
        ticker=ticker,
        action="SELL",
        qty=int(pos["qty"]),
        limit_price=pos["current_price"],
        stop_loss=0.0,
        take_profit=0.0,
    )
