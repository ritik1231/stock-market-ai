import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from pydantic import BaseModel

from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.logging_config import log_agent_task
from app.models.agent import AgentRunLog
from app.tools.indicators import calculate_indicators, interpret_indicators
from app.tools.price_fetcher import fetch_ohlcv

logger = structlog.get_logger(__name__)


class QuantInput(BaseModel):
    query_id: str
    ticker: str
    interval: str = "1d"
    period: str = "6mo"


class QuantOutput(BaseModel):
    query_id: str
    ticker: str
    interval: str
    period: str
    indicators: dict
    quant_signal: str  # BUY | SELL | HOLD
    current_price: Optional[float]
    atr_14: Optional[float]


def _determine_signal(raw_indicators: dict, labeled: dict, current_price: Optional[float]) -> str:
    rsi = raw_indicators.get("rsi_14")
    macd_label = labeled.get("macd_signal_label", "neutral")
    sma_50 = raw_indicators.get("sma_50")

    if rsi is None:
        return "HOLD"

    # BUY: RSI < 70 AND MACD bullish crossover AND close > SMA_50
    if (
        rsi < 70
        and macd_label == "bullish_crossover"
        and current_price is not None
        and sma_50 is not None
        and current_price > sma_50
    ):
        return "BUY"

    # SELL: RSI > 70 OR (MACD bearish crossover AND close < SMA_50)
    if rsi > 70 or (
        macd_label == "bearish_crossover"
        and current_price is not None
        and sma_50 is not None
        and current_price < sma_50
    ):
        return "SELL"

    return "HOLD"


async def _run_quant(input_data: QuantInput) -> QuantOutput:
    from app.db import engine as _engine
    await _engine.dispose()

    ticker = input_data.ticker.upper()

    # Step 1: Fetch OHLCV (Redis-cached inside fetch_ohlcv)
    df = await fetch_ohlcv(ticker, input_data.interval, input_data.period)

    if df.empty:
        return QuantOutput(
            query_id=input_data.query_id,
            ticker=ticker,
            interval=input_data.interval,
            period=input_data.period,
            indicators={},
            quant_signal="HOLD",
            current_price=None,
            atr_14=None,
        )

    # Step 2 & 3: Calculate and interpret indicators
    raw_indicators = calculate_indicators(df)
    labeled = interpret_indicators(raw_indicators)

    current_price: Optional[float] = None
    if not df.empty and "close" in df.columns:
        current_price = round(float(df["close"].iloc[-1]), 4)

    atr_14 = raw_indicators.get("atr_14")

    # Step 4: Determine quant signal
    quant_signal = _determine_signal(raw_indicators, labeled, current_price)

    return QuantOutput(
        query_id=input_data.query_id,
        ticker=ticker,
        interval=input_data.interval,
        period=input_data.period,
        indicators=labeled,
        quant_signal=quant_signal,
        current_price=current_price,
        atr_14=atr_14,
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
        agent_name="quant",
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


async def _execute(input_data: QuantInput, payload: dict) -> dict:
    started_at = datetime.now(timezone.utc)
    exc_to_raise: Optional[Exception] = None
    output_dict: Optional[dict] = None
    status = "success"

    try:
        output = await _run_quant(input_data)
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

    latency_ms = int((finished_at - started_at).total_seconds() * 1000)
    logger.info(
        "quant_agent finished ticker=%s signal=%s latency_ms=%d",
        input_data.ticker,
        output_dict.get("quant_signal"),
        latency_ms,
    )
    return output_dict


@celery_app.task(bind=True, queue="agent.quant", name="agents.quant", max_retries=3, default_retry_delay=10)
@log_agent_task
def run_quant_agent(self, payload: dict) -> dict:
    try:
        input_data = QuantInput(**payload)
        return asyncio.run(_execute(input_data, payload))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
