from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.tools.tax_calculator import get_tax_summary

router = APIRouter(tags=["tax"])


@router.get("/tax/summary")
async def tax_summary(
    year: int = Query(description="Starting year of the Indian financial year (e.g. 2025 → FY 2025-26)"),
    db: AsyncSession = Depends(get_db),
):
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=422, detail="year must be between 2000 and 2100")
    return await get_tax_summary(db, year)
