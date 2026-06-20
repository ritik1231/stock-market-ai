from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.agent import AgentRunLog

router = APIRouter(tags=["runs"])


class RunSummary(BaseModel):
    query_id: UUID
    tickers: list[str]
    agent_count: int
    latest_status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class AgentLogDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_id: UUID
    agent_name: str
    task_input: Optional[dict] = None
    task_output: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@router.get("/runs", response_model=list[RunSummary])
async def get_recent_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Return last N queries grouped by query_id, newest first."""
    subq = (
        select(
            AgentRunLog.query_id,
            func.max(AgentRunLog.started_at).label("last_started"),
        )
        .group_by(AgentRunLog.query_id)
        .order_by(desc(func.max(AgentRunLog.started_at)))
        .limit(limit)
        .subquery()
    )

    result = await db.execute(
        select(AgentRunLog).join(subq, AgentRunLog.query_id == subq.c.query_id)
    )
    rows = result.scalars().all()

    grouped: dict[UUID, list[AgentRunLog]] = {}
    for row in rows:
        grouped.setdefault(row.query_id, []).append(row)

    summaries = []
    for qid, logs in grouped.items():
        tickers = list({
            (l.task_input or {}).get("ticker", "")
            for l in logs
            if (l.task_input or {}).get("ticker")
        })
        statuses = [l.status for l in logs]
        latest_status = "error" if "error" in statuses else ("started" if "started" in statuses else "success")
        started_ats = [l.started_at for l in logs if l.started_at]
        finished_ats = [l.finished_at for l in logs if l.finished_at]
        summaries.append(RunSummary(
            query_id=qid,
            tickers=tickers,
            agent_count=len(logs),
            latest_status=latest_status,
            started_at=min(started_ats) if started_ats else None,
            finished_at=max(finished_ats) if finished_ats else None,
        ))

    summaries.sort(key=lambda s: s.started_at or datetime.min, reverse=True)
    return summaries
