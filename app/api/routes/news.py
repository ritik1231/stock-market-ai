from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.market import NewsArticle, StocksWatchlist
from app.tools.news_fetcher import ingest_news

router = APIRouter(tags=["news"])


class NewsItem(BaseModel):
    id: int
    ticker: Optional[str] = None
    headline: str
    source: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    sentiment_score: Optional[float] = None
    ingested_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NewsRefreshResponse(BaseModel):
    ingested: int
    tickers: list[str]


@router.get("/news", response_model=list[NewsItem])
async def get_news(
    ticker: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(NewsArticle).order_by(desc(NewsArticle.published_at)).limit(limit)
    if ticker:
        q = q.where(NewsArticle.ticker == ticker.upper())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/news/refresh", response_model=NewsRefreshResponse)
async def refresh_news(db: AsyncSession = Depends(get_db)):
    """Fetch and ingest latest news for all active watchlist tickers."""
    result = await db.execute(
        select(StocksWatchlist.ticker).where(StocksWatchlist.is_active.is_(True))
    )
    tickers = list(result.scalars().all())

    total_ingested = 0
    for ticker in tickers:
        articles = await ingest_news(ticker, db=db)
        total_ingested += len(articles)

    return NewsRefreshResponse(ingested=total_ingested, tickers=tickers)
