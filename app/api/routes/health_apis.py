from fastapi import APIRouter

from app.tools.rate_limiter import get_api_counters

router = APIRouter(tags=["health"])


@router.get("/health/apis")
async def api_rate_limit_health():
    """Show current rate-limit usage for every external API (read from Redis)."""
    return await get_api_counters()
