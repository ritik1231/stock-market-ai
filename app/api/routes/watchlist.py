from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.market import StocksWatchlist

router = APIRouter(tags=["watchlist"])


class WatchlistItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    company: str | None = None
    sector: str | None = None
    is_active: bool


class AddTickerRequest(BaseModel):
    ticker: str
    company: str | None = None
    sector: str | None = None


@router.get("/watchlist", response_model=list[WatchlistItem])
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StocksWatchlist).where(StocksWatchlist.is_active == True).order_by(StocksWatchlist.ticker)
    )
    return result.scalars().all()


@router.post("/watchlist", response_model=WatchlistItem, status_code=201)
async def add_to_watchlist(body: AddTickerRequest, db: AsyncSession = Depends(get_db)):
    ticker = body.ticker.strip().upper()
    existing = await db.execute(select(StocksWatchlist).where(StocksWatchlist.ticker == ticker))
    row = existing.scalar_one_or_none()
    if row:
        if not row.is_active:
            row.is_active = True
            await db.commit()
            await db.refresh(row)
        return row
    item = StocksWatchlist(ticker=ticker, company=body.company, sector=body.sector, is_active=True)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/watchlist/{ticker}", status_code=204)
async def remove_from_watchlist(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StocksWatchlist).where(StocksWatchlist.ticker == ticker.strip().upper())
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Ticker not found")
    row.is_active = False
    await db.commit()
