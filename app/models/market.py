from sqlalchemy import BigInteger, Boolean, Column, Date, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP as PGTIMESTAMP
from sqlalchemy.sql import func

from app.db import Base


class StocksWatchlist(Base):
    __tablename__ = "stocks_watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, unique=True)
    company = Column(Text)
    sector = Column(Text)
    is_active = Column(Boolean, default=True)
    added_at = Column(PGTIMESTAMP(timezone=True), server_default=func.now())


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint("ticker", "snapshot_date", name="uq_price_snapshots_ticker_date"),
        Index("ix_price_snapshots_ticker_date", "ticker", "snapshot_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    volume = Column(BigInteger)
    source = Column(String(32), default="yfinance")
    created_at = Column(PGTIMESTAMP(timezone=True), server_default=func.now())


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        Index("ix_news_articles_ticker_published_at", "ticker", "published_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20))
    headline = Column(Text, nullable=False)
    source = Column(String(128))
    url = Column(Text, unique=True)
    published_at = Column(PGTIMESTAMP(timezone=True))
    sentiment_score = Column(Numeric(4, 3))
    raw_content = Column(Text)
    ingested_at = Column(PGTIMESTAMP(timezone=True), server_default=func.now())
