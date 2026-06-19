import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.models.agent import AgentRunLog
from app.tools import alpaca_client
from app.tools.cache import get_cache, set_cache

logger = logging.getLogger(__name__)

_HWM_KEY = "portfolio:hwm"
_HWM_TTL = 365 * 24 * 3600  # ~1 year — effectively permanent

_CONFIDENCE_THRESHOLD = 0.5
_MAX_OPEN_POSITIONS = 10
_MAX_DRAWDOWN = 0.20
_MAX_CONCENTRATION = 0.05  # 5% per position


class RiskInput(BaseModel):
    query_id: str
    ticker: str
    proposed_signal: str  # BUY | SELL | HOLD
    atr_14: float
    current_price: float
    confidence: float


class RiskOutput(BaseModel):
    query_id: str
    ticker: str
    decision: str  # PASS | BLOCK
    reason: str
    suggested_qty: int
    stop_loss: float
    take_profit: float


async def _run_risk(input_data: RiskInput) -> RiskOutput:
    ticker = input_data.ticker.upper()
    atr = input_data.atr_14
    price = input_data.current_price
    signal = input_data.proposed_signal.upper()

    stop_loss = round(price - 2 * atr, 4)
    take_profit = round(price + 3 * atr, 4)

    # Non-BUY signals need no position sizing — pass straight through
    if signal != "BUY":
        return RiskOutput(
            query_id=input_data.query_id,
            ticker=ticker,
            decision="PASS",
            reason=f"Signal is {signal}, no position entry needed",
            suggested_qty=0,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    # --- Guardrail: confidence threshold ---
    if input_data.confidence < _CONFIDENCE_THRESHOLD:
        return RiskOutput(
            query_id=input_data.query_id,
            ticker=ticker,
            decision="BLOCK",
            reason=(
                f"Confidence {input_data.confidence:.2f} below "
                f"threshold {_CONFIDENCE_THRESHOLD}"
            ),
            suggested_qty=0,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    # --- Fetch portfolio state (fail-soft: use defaults if Alpaca unavailable) ---
    try:
        account = await alpaca_client.get_account()
        positions = await alpaca_client.get_positions()
    except Exception as exc:
        logger.warning("Alpaca unavailable, using defaults: %s", exc)
        account = {"portfolio_value": 10_000.0, "equity": 10_000.0}
        positions = []

    portfolio_value = float(account.get("portfolio_value", 10_000.0))

    # --- Update high-water mark in Redis ---
    hwm_raw = await get_cache(_HWM_KEY)
    hwm = float(hwm_raw) if hwm_raw is not None else portfolio_value
    if portfolio_value > hwm:
        hwm = portfolio_value
        await set_cache(_HWM_KEY, hwm, ttl=_HWM_TTL)

    # --- Guardrail: portfolio drawdown ---
    if hwm > 0:
        drawdown = (hwm - portfolio_value) / hwm
        if drawdown > _MAX_DRAWDOWN:
            return RiskOutput(
                query_id=input_data.query_id,
                ticker=ticker,
                decision="BLOCK",
                reason=(
                    f"Portfolio drawdown {drawdown:.1%} exceeds "
                    f"{_MAX_DRAWDOWN:.0%} limit"
                ),
                suggested_qty=0,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

    # --- Guardrail: max open positions ---
    if len(positions) >= _MAX_OPEN_POSITIONS:
        return RiskOutput(
            query_id=input_data.query_id,
            ticker=ticker,
            decision="BLOCK",
            reason=f"Max open positions ({_MAX_OPEN_POSITIONS}) already reached",
            suggested_qty=0,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    # --- Position sizing ---
    stop_distance = 2 * atr
    raw_qty = math.floor((portfolio_value * 0.01) / stop_distance) if stop_distance > 0 else 0
    position_cap = math.floor((portfolio_value * _MAX_CONCENTRATION) / price) if price > 0 else 0
    suggested_qty = max(0, min(raw_qty, position_cap))

    # --- Guardrail: position concentration ---
    existing_value = sum(
        p.get("market_value", 0.0)
        for p in positions
        if p.get("ticker", "").upper() == ticker
    )
    if (existing_value + suggested_qty * price) > portfolio_value * _MAX_CONCENTRATION:
        return RiskOutput(
            query_id=input_data.query_id,
            ticker=ticker,
            decision="BLOCK",
            reason=(
                f"Adding {suggested_qty} shares would exceed "
                f"{_MAX_CONCENTRATION:.0%} portfolio concentration limit"
            ),
            suggested_qty=0,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    if suggested_qty == 0:
        return RiskOutput(
            query_id=input_data.query_id,
            ticker=ticker,
            decision="BLOCK",
            reason="Calculated qty is 0 — portfolio too small for this ATR level",
            suggested_qty=0,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    return RiskOutput(
        query_id=input_data.query_id,
        ticker=ticker,
        decision="PASS",
        reason="All guardrails passed",
        suggested_qty=suggested_qty,
        stop_loss=stop_loss,
        take_profit=take_profit,
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
        agent_name="risk",
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


async def _execute(input_data: RiskInput, payload: dict) -> dict:
    started_at = datetime.now(timezone.utc)
    exc_to_raise: Optional[Exception] = None
    output_dict: Optional[dict] = None
    status = "success"

    try:
        output = await _run_risk(input_data)
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
        "risk_agent finished ticker=%s decision=%s qty=%s",
        input_data.ticker,
        output_dict.get("decision"),
        output_dict.get("suggested_qty"),
    )
    return output_dict


@celery_app.task(bind=True, queue="agent.risk", name="agents.risk")
def run_risk_agent(self, payload: dict) -> dict:
    input_data = RiskInput(**payload)
    return asyncio.run(_execute(input_data, payload))
