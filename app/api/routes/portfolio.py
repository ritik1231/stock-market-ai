from fastapi import APIRouter, HTTPException

from app.schemas.portfolio import PortfolioResponse, PositionSchema
from app.tools import alpaca_client
from app.tools.alpaca_client import AlpacaAPIError
from app.tools.cache import get_cache, set_cache

router = APIRouter(tags=["portfolio"])

_CACHE_KEY = "portfolio:snapshot"
_CACHE_TTL = 60


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    cached = await get_cache(_CACHE_KEY)
    if cached is not None:
        return PortfolioResponse(**cached)

    try:
        account, positions = await _fetch_portfolio()
    except AlpacaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    response = PortfolioResponse(
        equity=account["equity"],
        buying_power=account["buying_power"],
        portfolio_value=account["portfolio_value"],
        cash=account["cash"],
        positions=[PositionSchema(**p) for p in positions],
    )
    await set_cache(_CACHE_KEY, response.model_dump(), ttl=_CACHE_TTL)
    return response


async def _fetch_portfolio():
    return await alpaca_client.get_account(), await alpaca_client.get_positions()
