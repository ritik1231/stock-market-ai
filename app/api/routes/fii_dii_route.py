from fastapi import APIRouter
from app.tools.fii_dii import fetch_fii_dii_activity

router = APIRouter(tags=["market"])


@router.get("/fii-dii")
async def get_fii_dii():
    """Return today's FII/DII net activity from NSE."""
    return await fetch_fii_dii_activity()
