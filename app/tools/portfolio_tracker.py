import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRunLog
from app.tools import alpaca_client
from app.tools.cache import get_cache, set_cache

logger = logging.getLogger(__name__)

_HWM_KEY = "portfolio:hwm"
_HWM_TTL = 365 * 24 * 3600  # ~1 year — effectively permanent


@dataclass
class PortfolioSnapshot:
    total_value: float
    cash: float
    equity: float
    buying_power: float
    positions: list[dict] = field(default_factory=list)
    daily_pnl: Optional[float] = None


async def get_portfolio_snapshot() -> PortfolioSnapshot:
    account, positions = await asyncio.gather(
        alpaca_client.get_account(),
        alpaca_client.get_positions(),
    )
    daily_pnl = sum(p.get("unrealized_pnl", 0.0) for p in positions)
    return PortfolioSnapshot(
        total_value=account["portfolio_value"],
        cash=account["cash"],
        equity=account["equity"],
        buying_power=account["buying_power"],
        positions=positions,
        daily_pnl=daily_pnl,
    )


async def update_high_water_mark(portfolio_value: float) -> float:
    """Read HWM from Redis; update if current value exceeds it. Returns the new HWM."""
    hwm_raw = await get_cache(_HWM_KEY)
    hwm = float(hwm_raw) if hwm_raw is not None else portfolio_value
    if portfolio_value > hwm:
        hwm = portfolio_value
        await set_cache(_HWM_KEY, hwm, ttl=_HWM_TTL)
    return hwm


async def calculate_drawdown(portfolio_value: float) -> float:
    """Return current drawdown fraction relative to the stored high-water mark."""
    hwm_raw = await get_cache(_HWM_KEY)
    hwm = float(hwm_raw) if hwm_raw is not None else portfolio_value
    if hwm <= 0:
        return 0.0
    return max(0.0, (hwm - portfolio_value) / hwm)


async def log_daily_pnl(db: AsyncSession) -> None:
    """Record an end-of-day P&L summary row to agent_run_logs."""
    now = datetime.now(timezone.utc)
    task_output: dict
    status = "success"
    error_message = None

    try:
        snapshot = await get_portfolio_snapshot()
        hwm = await update_high_water_mark(snapshot.total_value)
        drawdown = max(0.0, (hwm - snapshot.total_value) / hwm) if hwm > 0 else 0.0
        task_output = {
            "portfolio_value": snapshot.total_value,
            "equity": snapshot.equity,
            "cash": snapshot.cash,
            "daily_pnl": snapshot.daily_pnl,
            "position_count": len(snapshot.positions),
            "high_water_mark": hwm,
            "drawdown_pct": round(drawdown * 100, 2),
        }
        logger.info(
            "daily_pnl logged portfolio_value=%.2f daily_pnl=%.2f drawdown_pct=%.2f%%",
            snapshot.total_value,
            snapshot.daily_pnl or 0,
            drawdown * 100,
        )
    except Exception as exc:
        logger.error("log_daily_pnl failed: %s", exc)
        task_output = {"error": str(exc)}
        status = "error"
        error_message = str(exc)

    log_entry = AgentRunLog(
        query_id=uuid4(),
        agent_name="portfolio_tracker",
        task_input={},
        task_output=task_output,
        status=status,
        error_message=error_message,
        latency_ms=0,
        started_at=now,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    await db.commit()
