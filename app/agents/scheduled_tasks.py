import asyncio
import logging
import uuid

from sqlalchemy import select

from app.agents.orchestrator import run_orchestrator
from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.models.market import StocksWatchlist
from app.tools.portfolio_tracker import log_daily_pnl

logger = logging.getLogger(__name__)


@celery_app.task(name="scheduled.daily_watchlist_analysis")
def daily_watchlist_analysis():
    asyncio.run(_daily_watchlist_analysis_async())


async def _daily_watchlist_analysis_async():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StocksWatchlist).where(StocksWatchlist.is_active.is_(True))
        )
        watchlist = result.scalars().all()

    dispatched = 0
    for stock in watchlist:
        payload = {
            "query_id": str(uuid.uuid4()),
            "ticker": stock.ticker,
            "mode": "full_analysis",
            "query_text": f"Daily analysis for {stock.ticker}",
        }
        run_orchestrator.apply_async(args=[payload], queue="orchestrator.tasks")
        dispatched += 1

    logger.info("daily_watchlist_analysis dispatched ticker_count=%d", dispatched)


@celery_app.task(name="scheduled.end_of_day_pnl_log")
def end_of_day_pnl_log():
    asyncio.run(_end_of_day_pnl_log_async())


async def _end_of_day_pnl_log_async():
    async with AsyncSessionLocal() as db:
        await log_daily_pnl(db)
    logger.info("end_of_day_pnl_log completed")
