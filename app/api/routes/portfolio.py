from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.agent import AgentRunLog
from app.schemas.portfolio import PortfolioResponse, PositionSchema
from app.tools import broker
from app.tools.broker_errors import BrokerAPIError
from app.tools.cache import get_cache, set_cache

router = APIRouter(tags=["portfolio"])

_CACHE_KEY = "portfolio:snapshot"
_CACHE_TTL = 60


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    cached = await get_cache(_CACHE_KEY)
    if cached is not None:
        return PortfolioResponse(**cached)

    try:
        account, positions = await _fetch_portfolio()
    except BrokerAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    response = PortfolioResponse(
        equity=account["equity"],
        buying_power=account["buying_power"],
        portfolio_value=account["portfolio_value"],
        cash=account["cash"],
        positions=[PositionSchema(**p) for p in positions],
    )
    await set_cache(_CACHE_KEY, response.model_dump(), ttl=_CACHE_TTL)
    return response


async def _fetch_portfolio():
    return await broker.get_account(), await broker.get_positions()


class PnlDataPoint(BaseModel):
    date: datetime
    portfolio_value: float
    daily_pnl: Optional[float] = None


@router.get("/portfolio/history", response_model=list[PnlDataPoint])
async def get_portfolio_history(
    limit: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return historical P&L data from portfolio_tracker agent logs."""
    result = await db.execute(
        select(AgentRunLog)
        .where(AgentRunLog.agent_name == "portfolio_tracker")
        .order_by(asc(AgentRunLog.started_at))
        .limit(limit)
    )
    rows = result.scalars().all()
    points = []
    for row in rows:
        output = row.task_output or {}
        if output.get("portfolio_value") and row.started_at:
            points.append(PnlDataPoint(
                date=row.started_at,
                portfolio_value=float(output["portfolio_value"]),
                daily_pnl=float(output["daily_pnl"]) if output.get("daily_pnl") is not None else None,
            ))
    return points
