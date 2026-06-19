from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.agent import Signal
from app.schemas.signals import SignalResponse

router = APIRouter(tags=["signals"])


@router.get("/signal/{ticker}", response_model=SignalResponse)
async def get_signal(ticker: str, db: AsyncSession = Depends(get_db)):
    ticker = ticker.upper()
    row = await db.execute(
        select(Signal)
        .where(Signal.ticker == ticker)
        .order_by(desc(Signal.generated_at))
        .limit(1)
    )
    signal = row.scalar_one_or_none()
    if signal is None:
        raise HTTPException(status_code=404, detail=f"No signal found for {ticker}")
    return signal
