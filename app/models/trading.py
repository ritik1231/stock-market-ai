from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP as PGTIMESTAMP, UUID
from sqlalchemy.sql import func

from app.db import Base


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_ticker_submitted_at", "ticker", "submitted_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_id = Column(UUID(as_uuid=True))
    alpaca_order_id = Column(Text, unique=True)
    ticker = Column(String(10), nullable=False)
    action = Column(String(8), nullable=False)
    qty = Column(Integer, nullable=False)
    submitted_price = Column(Numeric(12, 4))
    filled_price = Column(Numeric(12, 4))
    stop_loss = Column(Numeric(12, 4))
    take_profit = Column(Numeric(12, 4))
    status = Column(String(16))
    paper_mode = Column(Boolean, default=True)
    submitted_at = Column(PGTIMESTAMP(timezone=True), server_default=func.now())
    filled_at = Column(PGTIMESTAMP(timezone=True))
