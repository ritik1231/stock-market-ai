import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis = aioredis.from_url(
    get_settings().REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=2,
)


def build_key(*parts: str) -> str:
    return ":".join(parts)


async def get_cache(key: str) -> Optional[Any]:
    try:
        raw = await _redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Cache GET failed for %s: %s", key, exc)
        return None


async def set_cache(key: str, value: Any, ttl: int) -> None:
    try:
        await _redis_client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as exc:
        logger.warning("Cache SET failed for %s: %s", key, exc)


async def delete_cache(key: str) -> None:
    try:
        await _redis_client.delete(key)
    except Exception as exc:
        logger.warning("Cache DEL failed for %s: %s", key, exc)


async def rate_limit_check(api_name: str, max_calls: int, window_seconds: int) -> bool:
    """
    Fixed-window rate limiter via Redis INCR + EXPIRE.
    Returns True if the call is allowed, False if the limit is exceeded.
    Fails open (returns True) when Redis is unavailable.
    """
    key = build_key("ratelimit", api_name)
    try:
        current = await _redis_client.incr(key)
        if current == 1:
            await _redis_client.expire(key, window_seconds)
        return int(current) <= max_calls
    except Exception as exc:
        logger.warning("Rate limit check failed for %s: %s", api_name, exc)
        return True
