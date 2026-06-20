import asyncio
import logging
from typing import Optional

import yfinance as yf
from fastapi import APIRouter
from pydantic import BaseModel

from app.tools.cache import get_cache, set_cache

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market"])

_INDICES = [
    {"key": "nifty50",   "symbol": "^NSEI",    "name": "Nifty 50"},
    {"key": "sensex",    "symbol": "^BSESN",   "name": "Sensex"},
    {"key": "banknifty", "symbol": "^NSEBANK",  "name": "Bank Nifty"},
    {"key": "niftyit",   "symbol": "^CNXIT",   "name": "Nifty IT"},
    {"key": "usdinr",    "symbol": "USDINR=X", "name": "USD/INR"},
]
_CACHE_TTL = 60  # 60 seconds


class IndexQuote(BaseModel):
    key: str
    symbol: str
    name: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    error: Optional[str] = None


def _fetch_quote(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = float(info.last_price) if info.last_price else None
        prev = float(info.previous_close) if info.previous_close else None
        change = round(price - prev, 2) if price and prev else None
        change_pct = round((change / prev) * 100, 2) if change and prev else None
        return {"price": price, "change": change, "change_pct": change_pct, "error": None}
    except Exception as exc:
        logger.warning("Quote fetch failed for %s: %s", symbol, exc)
        return {"price": None, "change": None, "change_pct": None, "error": str(exc)}


@router.get("/market/indices", response_model=list[IndexQuote])
async def get_market_indices():
    cache_key = "market:indices"
    cached = await get_cache(cache_key)
    if cached is not None:
        return cached

    def _fetch_all():
        results = []
        for idx in _INDICES:
            q = _fetch_quote(idx["symbol"])
            results.append({**idx, **q})
        return results

    data = await asyncio.to_thread(_fetch_all)
    await set_cache(cache_key, data, _CACHE_TTL)
    return data
