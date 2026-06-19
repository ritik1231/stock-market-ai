from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRunLog


async def write_agent_log(
    db: AsyncSession,
    query_id: str,
    agent_name: str,
    task_input: dict,
    task_output: Optional[dict],
    status: str,
    error_message: Optional[str],
    started_at: datetime,
    finished_at: datetime,
) -> None:
    """Insert a single agent run row; commit the session."""
    latency_ms = int((finished_at - started_at).total_seconds() * 1000)
    db.add(AgentRunLog(
        query_id=UUID(query_id),
        agent_name=agent_name,
        task_input=task_input,
        task_output=task_output,
        status=status,
        error_message=error_message,
        latency_ms=latency_ms,
        started_at=started_at,
        finished_at=finished_at,
    ))
    await db.commit()


async def get_agent_logs_for_query(db: AsyncSession, query_id: str) -> list[AgentRunLog]:
    """Return all agent run logs for a query, ordered by started_at."""
    result = await db.execute(
        select(AgentRunLog)
        .where(AgentRunLog.query_id == UUID(query_id))
        .order_by(AgentRunLog.started_at)
    )
    return list(result.scalars().all())
