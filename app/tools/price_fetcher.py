import asyncio
import json
import logging
from typing import Optional

import pandas as pd
import redis.asyncio as aioredis
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.market import PriceSnapshot

logger = logging.getLogger(__name__)
settings = get_settings()

_INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
_TTL_INTRADAY = 5 * 60       # 5 minutes
_TTL_DAILY = 24 * 60 * 60    # 24 hours


def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)


def _cache_ttl(interval: str) -> int:
    return _TTL_INTRADAY if interval in _INTRADAY_INTERVALS else _TTL_DAILY


@retry(
    retry=retry_if_exception_type((ConnectionError, OSError, TimeoutError)),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _fetch_yfinance(ticker: str, interval: str, period: str) -> pd.DataFrame:
    raw = yf.Ticker(ticker).history(period=period, interval=interval)
    raw = raw.reset_index()
    raw.columns = [c.lower() for c in raw.columns]
    if "datetime" in raw.columns and "date" not in raw.columns:
        raw = raw.rename(columns={"datetime": "date"})
    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in raw.columns]
    return raw[keep].copy()


async def fetch_ohlcv(ticker: str, interval: str = "1d", period: str = "6mo") -> pd.DataFrame:
    cache_key = f"ohlcv:{ticker.upper()}:{interval}"
    ttl = _cache_ttl(interval)

    try:
        r = _redis()
        cached = await r.get(cache_key)
        await r.aclose()
        if cached:
            logger.debug("Cache hit for %s", cache_key)
            return pd.DataFrame(json.loads(cached))
    except Exception as exc:
        logger.warning("Redis read skipped (%s): %s", cache_key, exc)

    df = await asyncio.to_thread(_fetch_yfinance, ticker, interval, period)

    try:
        r = _redis()
        await r.set(cache_key, df.to_json(orient="records"), ex=ttl)
        await r.aclose()
    except Exception as exc:
        logger.warning("Redis write skipped (%s): %s", cache_key, exc)

    return df


async def get_latest_price(ticker: str) -> float:
    df = await fetch_ohlcv(ticker, interval="1d", period="5d")
    return float(df["close"].iloc[-1])


async def save_price_snapshot(ticker: str, df: pd.DataFrame, db: AsyncSession) -> None:
    if df.empty:
        return

    rows = []
    for _, row in df.iterrows():
        snap_date = row["date"]
        if hasattr(snap_date, "date"):
            snap_date = snap_date.date()

        rows.append({
            "ticker": ticker.upper(),
            "snapshot_date": snap_date,
            "open": _to_decimal(row.get("open")),
            "high": _to_decimal(row.get("high")),
            "low": _to_decimal(row.get("low")),
            "close": _to_decimal(row.get("close")),
            "volume": _to_int(row.get("volume")),
            "source": "yfinance",
        })

    stmt = (
        pg_insert(PriceSnapshot)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["ticker", "snapshot_date"])
    )
    await db.execute(stmt)
    await db.commit()
    logger.info("Upserted %d price snapshots for %s", len(rows), ticker)


def _to_decimal(val) -> Optional[float]:
    try:
        v = float(val)
        return round(v, 4) if v == v else None  # NaN check
    except (TypeError, ValueError):
        return None


def _to_int(val) -> Optional[int]:
    try:
        v = int(val)
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None
