from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_id: UUID
    ticker: str
    signal: str
    confidence: Optional[float] = None
    quant_signal: Optional[str] = None
    sentiment_score: Optional[float] = None
    risk_decision: Optional[str] = None
    summary: Optional[str] = None
    generated_at: datetime
