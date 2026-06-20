from app.exceptions import RateLimitError
from app.tools.cache import build_key, get_cache, rate_limit_check

RATE_LIMITS: dict[str, dict] = {
    "newsapi":  {"max_calls": 90,   "window_seconds": 3600},
    "edgar":    {"max_calls": 9,    "window_seconds": 1},
    "groq":     {"max_calls": 30,   "window_seconds": 60},
    "angel":    {"max_calls": 180,  "window_seconds": 60},
    "nse":      {"max_calls": 30,   "window_seconds": 60},
    "bse":      {"max_calls": 5,    "window_seconds": 60},
    "yfinance": {"max_calls": 1900, "window_seconds": 3600},
}


async def check_rate_limit(api_name: str) -> None:
    """Raise RateLimitError if the named API is over its limit; fail-open if Redis is down."""
    config = RATE_LIMITS.get(api_name)
    if config is None:
        return
    allowed = await rate_limit_check(api_name, config["max_calls"], config["window_seconds"])
    if not allowed:
        raise RateLimitError(
            f"{api_name} rate limit exceeded "
            f"({config['max_calls']} calls per {config['window_seconds']}s)"
        )


async def get_api_counters() -> dict[str, dict]:
    """Return current call counts for all tracked APIs (for health monitoring)."""
    counters: dict[str, dict] = {}
    for api_name, config in RATE_LIMITS.items():
        key = build_key("ratelimit", api_name)
        current = await get_cache(key)
        counters[api_name] = {
            "current_calls": int(current) if current is not None else 0,
            "max_calls": config["max_calls"],
            "window_seconds": config["window_seconds"],
        }
    return counters
