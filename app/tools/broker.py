"""Broker routing layer.

Selects the active broker implementation based on the BROKER env var:

  BROKER=paper   (default) — paper_broker: zero-account simulation, yfinance prices + Postgres
  BROKER=upstox            — upstox_client: Upstox v2 API, sandbox or live
  BROKER=angel             — angel_client:  Angel One SmartAPI, live only (requires Demat + pyotp)

All three modules expose the same six async functions, so callers import from here
and are never aware of which backend is active.
"""

from app.config import get_settings
from app.tools.broker_errors import BrokerAPIError, BrokerServerError  # noqa: F401 — re-exported

settings = get_settings()


def _mod():
    backend = (settings.BROKER or "paper").lower()
    if backend == "upstox":
        from app.tools import upstox_client as m
    elif backend == "angel":
        from app.tools import angel_client as m
    else:
        from app.tools import paper_broker as m
    return m


async def get_account() -> dict:
    return await _mod().get_account()


async def get_positions() -> list[dict]:
    return await _mod().get_positions()


async def place_order(
    ticker: str,
    action: str,
    qty: int,
    limit_price: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    return await _mod().place_order(ticker, action, qty, limit_price, stop_loss, take_profit)


async def get_order(order_id: str) -> dict:
    return await _mod().get_order(order_id)


async def cancel_order(order_id: str) -> bool:
    return await _mod().cancel_order(order_id)


async def close_position(ticker: str) -> dict:
    return await _mod().close_position(ticker)
