import logging
from datetime import date, datetime, timezone

import httpx

from app.tools.cache import get_cache, set_cache

logger = logging.getLogger(__name__)

_FII_DII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com",
    "Accept": "application/json",
}
_CACHE_TTL = 3600  # 1 hour

_BULLISH_THRESHOLD = 500    # crore
_BEARISH_THRESHOLD = -500   # crore


async def fetch_fii_dii_activity() -> dict:
    """
    Fetch FII and DII net buy/sell data from NSE.
    Returns {date, fii_net_crore, dii_net_crore, signal: BULLISH|BEARISH|NEUTRAL}.
    Cached for 1 hour per calendar day.
    """
    today = date.today().isoformat()
    cache_key = f"fii_dii:{today}"

    cached = await get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=10.0,
            follow_redirects=True,
        ) as client:
            resp = await client.get(_FII_DII_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("FII/DII fetch failed: %s", exc)
        return _neutral_response(today)

    fii_net = 0.0
    dii_net = 0.0

    try:
        if isinstance(data, list) and data:
            latest = data[0]
            fii_net = float(latest.get("fiiNet", 0) or 0)
            dii_net = float(latest.get("diiNet", 0) or 0)
            today = latest.get("date", today)
        elif isinstance(data, dict):
            entries = data.get("data", []) or []
            if entries:
                latest = entries[0]
                fii_net = float(latest.get("fiiNet", 0) or 0)
                dii_net = float(latest.get("diiNet", 0) or 0)
                today = latest.get("date", today)
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("FII/DII parse error: %s — raw: %r", exc, data)

    if fii_net > _BULLISH_THRESHOLD:
        signal = "BULLISH"
    elif fii_net < _BEARISH_THRESHOLD:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    result = {
        "date": today,
        "fii_net_crore": round(fii_net, 2),
        "dii_net_crore": round(dii_net, 2),
        "signal": signal,
    }

    await set_cache(cache_key, result, ttl=_CACHE_TTL)
    return result


def _neutral_response(today: str) -> dict:
    return {
        "date": today,
        "fii_net_crore": 0.0,
        "dii_net_crore": 0.0,
        "signal": "NEUTRAL",
    }
