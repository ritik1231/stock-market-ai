"""Dead Letter Queue consumer and orchestrator health watchdog."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.models.agent import AgentRunLog, Alert

logger = structlog.get_logger()

_STUCK_THRESHOLD_MINUTES = 10


@celery_app.task(name="workers.process_dlq_message")
def process_dlq_message(message: dict) -> None:
    """Process a single dead-lettered task message.

    Expected message keys: task_name, query_id, ticker, error, retry_count.
    """
    asyncio.run(_process_dlq_message_async(message))


async def _process_dlq_message_async(message: dict) -> None:
    task_name = message.get("task_name", "unknown")
    query_id_str = message.get("query_id", str(uuid4()))
    ticker = message.get("ticker", "unknown")
    error = message.get("error", "")
    retry_count = int(message.get("retry_count", 0))

    logger.warning(
        "dlq_message_received",
        task_name=task_name,
        ticker=ticker,
        query_id=query_id_str,
        retry_count=retry_count,
        error=error,
    )

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        # Log to agent_run_logs with status=dead_letter
        try:
            query_uuid = UUID(query_id_str)
        except (ValueError, AttributeError):
            query_uuid = uuid4()

        db.add(AgentRunLog(
            query_id=query_uuid,
            agent_name=task_name,
            task_input=message,
            task_output=None,
            status="dead_letter",
            error_message=error,
            latency_ms=0,
            started_at=now,
            finished_at=now,
        ))

        # Check if this ticker has failed more than once in the last hour
        one_hour_ago = now - timedelta(hours=1)
        result = await db.execute(
            select(AgentRunLog)
            .where(AgentRunLog.status == "dead_letter")
            .where(AgentRunLog.started_at >= one_hour_ago)
            .where(AgentRunLog.task_input["ticker"].as_string() == ticker)
        )
        recent_failures = result.scalars().all()

        if len(recent_failures) >= 1:  # >1 total including current
            db.add(Alert(
                alert_type="repeated_dlq_failure",
                message=(
                    f"Task '{task_name}' for ticker '{ticker}' has failed "
                    f"{len(recent_failures) + 1} time(s) in the last hour. "
                    f"Latest error: {error}"
                ),
            ))
            logger.error(
                "repeated_dlq_failure_alert",
                ticker=ticker,
                task_name=task_name,
                failure_count=len(recent_failures) + 1,
            )

        await db.commit()


@celery_app.task(name="workers.check_orchestrator_health")
def check_orchestrator_health() -> None:
    """Beat watchdog: flag agent runs stuck in 'started' for > 10 minutes."""
    asyncio.run(_check_orchestrator_health_async())


async def _check_orchestrator_health_async() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_STUCK_THRESHOLD_MINUTES)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentRunLog)
            .where(AgentRunLog.status == "started")
            .where(AgentRunLog.started_at < cutoff)
        )
        stuck_tasks = result.scalars().all()

        if not stuck_tasks:
            return

        for task in stuck_tasks:
            db.add(Alert(
                alert_type="stuck_task",
                message=(
                    f"Agent '{task.agent_name}' for query {task.query_id} "
                    f"has been in 'started' status since {task.started_at.isoformat()}. "
                    f"Threshold: {_STUCK_THRESHOLD_MINUTES} minutes."
                ),
            ))
            logger.warning(
                "stuck_task_detected",
                agent=task.agent_name,
                query_id=str(task.query_id),
                started_at=str(task.started_at),
            )

        await db.commit()
        logger.info("check_orchestrator_health completed", stuck_count=len(stuck_tasks))
