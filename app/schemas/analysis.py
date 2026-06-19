import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AnalyzeRequest(BaseModel):
    ticker: str
    mode: str = "signal_only"  # "signal_only" | "full_analysis"
    lookback_days: int = 7

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase_alphanumeric(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r"^[A-Z0-9]{1,10}$", v):
            raise ValueError("ticker must be 1–10 uppercase alphanumeric characters")
        return v

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in ("signal_only", "full_analysis"):
            raise ValueError("mode must be 'signal_only' or 'full_analysis'")
        return v

    @field_validator("lookback_days")
    @classmethod
    def positive_lookback(cls, v: int) -> int:
        if v < 1 or v > 90:
            raise ValueError("lookback_days must be between 1 and 90")
        return v


class AnalyzeResponse(BaseModel):
    """Returned immediately (HTTP 202) when an analysis job is accepted."""
    model_config = ConfigDict(from_attributes=True)

    query_id: str
    ticker: str
    status: str = "queued"
    poll_url: str


class AnalysisResult(BaseModel):
    """Full async result returned once the orchestrator completes."""
    model_config = ConfigDict(from_attributes=True)

    query_id: str
    ticker: str
    status: str  # "completed" | "pending" | "error"
    final_signal: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    key_factors: Optional[list[str]] = None
    research_result: Optional[dict] = None
    quant_result: Optional[dict] = None
    risk_result: Optional[dict] = None
    execution_result: Optional[dict] = None
