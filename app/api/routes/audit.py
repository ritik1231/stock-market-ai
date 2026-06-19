from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.audit import get_agent_logs_for_query
from app.models.agent import Alert

router = APIRouter(tags=["audit"])


class AgentLogResponse(BaseModel):
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


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime


@router.get("/query/{query_id}/logs", response_model=list[AgentLogResponse])
async def get_query_logs(query_id: str, db: AsyncSession = Depends(get_db)):
    """Return the full agent audit trail for a query, ordered by started_at."""
    return await get_agent_logs_for_query(db, query_id)


@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return recent system alerts, newest first."""
    result = await db.execute(
        select(Alert).order_by(desc(Alert.created_at)).limit(limit).offset(offset)
    )
    return result.scalars().all()
