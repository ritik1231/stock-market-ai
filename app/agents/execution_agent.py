import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.logging_config import log_agent_task
from app.models.agent import AgentRunLog
from app.models.trading import Trade
from app.tools import alpaca_client
from app.tools.alpaca_client import AlpacaAPIError

logger = structlog.get_logger(__name__)

_POLL_ATTEMPTS = 5
_POLL_INTERVAL_S = 2
_LIMIT_SLIPPAGE = 0.005  # 0.5%


class LiveTradingNotPermittedError(Exception):
    pass


class ExecutionInput(BaseModel):
    query_id: str
    ticker: str
    action: str       # BUY | SELL
    qty: int
    stop_loss: float
    take_profit: float
    paper_mode: bool = True


class ExecutionOutput(BaseModel):
    query_id: str
    ticker: str
    order_id: str
    status: str
    filled_price: Optional[float]
    timestamp: Optional[str]


def _limit_price(action: str, current_price: float) -> float:
    if action.upper() == "BUY":
        return round(current_price * (1 + _LIMIT_SLIPPAGE), 2)
    return round(current_price * (1 - _LIMIT_SLIPPAGE), 2)


async def _poll_order(order_id: str) -> dict:
    result: dict = {"order_id": order_id, "status": "unknown", "filled_avg_price": None, "filled_at": None}
    for attempt in range(_POLL_ATTEMPTS):
        try:
            result = await alpaca_client.get_order(order_id)
            if result.get("status") in ("filled", "canceled", "expired", "rejected"):
                break
        except AlpacaAPIError as exc:
            logger.warning("Poll attempt %d failed: %s", attempt + 1, exc)
        if attempt < _POLL_ATTEMPTS - 1:
            await asyncio.sleep(_POLL_INTERVAL_S)
    return result


async def _upsert_trade(
    query_id: str,
    ticker: str,
    action: str,
    qty: int,
    limit_price: float,
    stop_loss: float,
    take_profit: float,
    paper_mode: bool,
    order: dict,
) -> None:
    filled_price = order.get("filled_avg_price")
    filled_at_raw = order.get("filled_at")
    filled_at: Optional[datetime] = None
    if filled_at_raw and filled_at_raw != "None":
        try:
            filled_at = datetime.fromisoformat(str(filled_at_raw).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    stmt = (
        pg_insert(Trade)
        .values(
            query_id=UUID(query_id),
            alpaca_order_id=order.get("order_id"),
            ticker=ticker,
            action=action.upper(),
            qty=qty,
            submitted_price=round(limit_price, 4),
            filled_price=round(float(filled_price), 4) if filled_price else None,
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            status=order.get("status", "unknown"),
            paper_mode=paper_mode,
            filled_at=filled_at,
        )
        .on_conflict_do_update(
            index_elements=["alpaca_order_id"],
            set_={
                "status": order.get("status", "unknown"),
                "filled_price": round(float(filled_price), 4) if filled_price else None,
                "filled_at": filled_at,
            },
        )
    )
    async with AsyncSessionLocal() as db:
        await db.execute(stmt)
        await db.commit()


async def _get_existing_trade(query_id: str) -> Optional[dict]:
    """Return order details if a trade for this query_id was already placed."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Trade).where(Trade.query_id == UUID(query_id))
        )
        trade = result.scalar_one_or_none()
        if trade and trade.alpaca_order_id:
            return {
                "order_id": trade.alpaca_order_id,
                "status": trade.status or "unknown",
                "filled_avg_price": float(trade.filled_price) if trade.filled_price else None,
                "filled_at": str(trade.filled_at) if trade.filled_at else None,
            }
    return None


async def _run_execution(input_data: ExecutionInput) -> ExecutionOutput:
    from app.db import engine as _engine
    await _engine.dispose()

    # Step 1: Hard safety gate
    if not input_data.paper_mode:
        raise LiveTradingNotPermittedError(
            "paper_mode is False — live trading is not permitted"
        )

    ticker = input_data.ticker.upper()
    action = input_data.action.upper()

    # Idempotency: return existing order if one was already placed for this query_id
    existing = await _get_existing_trade(input_data.query_id)
    if existing:
        logger.info("idempotency_hit", query_id=input_data.query_id, order_id=existing["order_id"])
        return ExecutionOutput(
            query_id=input_data.query_id,
            ticker=ticker,
            order_id=existing["order_id"],
            status=existing["status"],
            filled_price=existing["filled_avg_price"],
            timestamp=existing["filled_at"],
        )

    # Step 2: Place bracket limit order
    # Use current market price (last close) for slippage calculation
    from app.tools.price_fetcher import get_latest_price

    try:
        current_price = await get_latest_price(ticker)
    except Exception as exc:
        logger.warning("Could not fetch latest price for %s: %s — using take_profit as reference", ticker, exc)
        # Fall back: estimate from take_profit and ATR-based spread
        current_price = input_data.take_profit / 1.015  # rough back-calc

    lp = _limit_price(action, current_price)

    order = await alpaca_client.place_order(
        ticker=ticker,
        action=action,
        qty=input_data.qty,
        limit_price=lp,
        stop_loss=input_data.stop_loss,
        take_profit=input_data.take_profit,
    )
    order_id = order["order_id"]

    # Step 3: Poll for fill status
    filled_order = await _poll_order(order_id)

    # Step 4: Upsert into trades table
    await _upsert_trade(
        query_id=input_data.query_id,
        ticker=ticker,
        action=action,
        qty=input_data.qty,
        limit_price=lp,
        stop_loss=input_data.stop_loss,
        take_profit=input_data.take_profit,
        paper_mode=input_data.paper_mode,
        order=filled_order,
    )

    return ExecutionOutput(
        query_id=input_data.query_id,
        ticker=ticker,
        order_id=order_id,
        status=filled_order.get("status", "unknown"),
        filled_price=filled_order.get("filled_avg_price"),
        timestamp=filled_order.get("filled_at"),
    )


async def _write_log(
    query_id: str,
    task_input: dict,
    task_output: Optional[dict],
    status: str,
    error_message: Optional[str],
    started_at: datetime,
    finished_at: datetime,
) -> None:
    latency_ms = int((finished_at - started_at).total_seconds() * 1000)
    log_entry = AgentRunLog(
        query_id=UUID(query_id),
        agent_name="execution",
        task_input=task_input,
        task_output=task_output,
        status=status,
        error_message=error_message,
        latency_ms=latency_ms,
        started_at=started_at,
        finished_at=finished_at,
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(log_entry)
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to write agent_run_log: %s", exc)


async def _execute(input_data: ExecutionInput, payload: dict) -> dict:
    started_at = datetime.now(timezone.utc)
    exc_to_raise: Optional[Exception] = None
    output_dict: Optional[dict] = None
    status = "success"

    try:
        output = await _run_execution(input_data)
        output_dict = output.model_dump()
    except Exception as exc:
        exc_to_raise = exc
        status = "error"

    finished_at = datetime.now(timezone.utc)
    await _write_log(
        query_id=input_data.query_id,
        task_input=payload,
        task_output=output_dict,
        status=status,
        error_message=str(exc_to_raise) if exc_to_raise else None,
        started_at=started_at,
        finished_at=finished_at,
    )

    if exc_to_raise:
        raise exc_to_raise

    logger.info(
        "execution_agent finished ticker=%s order=%s status=%s",
        input_data.ticker,
        output_dict.get("order_id"),
        output_dict.get("status"),
    )
    return output_dict


@celery_app.task(bind=True, queue="agent.execution", name="agents.execution", max_retries=3, default_retry_delay=10)
@log_agent_task
def run_execution_agent(self, payload: dict) -> dict:
    try:
        input_data = ExecutionInput(**payload)
        return asyncio.run(_execute(input_data, payload))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
