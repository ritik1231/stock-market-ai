import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class TradeRequest(BaseModel):
    ticker: str
    action: str  # BUY | SELL
    qty: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r"^[A-Z0-9.\-\^&]{1,20}$", v):
            raise ValueError("ticker must be 1–20 uppercase alphanumeric characters (dots/hyphens allowed for NSE/BSE)")
        return v

    @field_validator("action")
    @classmethod
    def valid_action(cls, v: str) -> str:
        v = v.upper()
        if v not in ("BUY", "SELL"):
            raise ValueError("action must be BUY or SELL")
        return v

    @field_validator("qty")
    @classmethod
    def positive_qty(cls, v: int) -> int:
        if v < 1:
            raise ValueError("qty must be a positive integer")
        return v


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query_id: str
    ticker: str
    order_id: str
    status: str
    filled_price: Optional[float] = None
    timestamp: Optional[str] = None


class TradeRecord(BaseModel):
    """Represents a single row from the trades table."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_id: Optional[UUID] = None
    broker_order_id: Optional[str] = None
    ticker: str
    action: str
    qty: int
    submitted_price: Optional[float] = None
    filled_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: Optional[str] = None
    paper_mode: bool
    submitted_at: datetime
    filled_at: Optional[datetime] = None
