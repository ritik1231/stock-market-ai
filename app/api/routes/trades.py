import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.execution_agent import ExecutionInput, LiveTradingNotPermittedError, run_execution_agent
from app.config import get_settings
from app.db import get_db
from app.models.trading import Trade
from app.schemas.trades import TradeRecord, TradeRequest, TradeResponse
from app.tools.alpaca_client import AlpacaAPIError

router = APIRouter(tags=["trades"])
settings = get_settings()


@router.post("/trade", response_model=TradeResponse)
async def place_trade(body: TradeRequest):
    if not settings.PAPER_MODE:
        raise HTTPException(status_code=403, detail="Live trading is not permitted")

    query_id = str(uuid.uuid4())

    # Build execution payload using current price-derived stop/take-profit if not supplied
    payload = ExecutionInput(
        query_id=query_id,
        ticker=body.ticker,
        action=body.action,
        qty=body.qty,
        stop_loss=body.stop_loss or 0.0,
        take_profit=body.take_profit or 0.0,
        paper_mode=True,
    ).model_dump()

    try:
        result = run_execution_agent.apply_async(args=[payload], queue="agent.execution").get(timeout=30)
    except LiveTradingNotPermittedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except AlpacaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return TradeResponse(
        query_id=query_id,
        ticker=body.ticker,
        order_id=result.get("order_id", ""),
        status=result.get("status", "unknown"),
        filled_price=result.get("filled_price"),
        timestamp=result.get("timestamp"),
    )


@router.get("/trades", response_model=list[TradeRecord])
async def list_trades(
    ticker: str | None = Query(default=None, description="Filter by ticker symbol"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Trade).order_by(desc(Trade.submitted_at)).limit(limit).offset(offset)
    if ticker:
        query = query.where(Trade.ticker == ticker.upper())

    rows = await db.execute(query)
    return rows.scalars().all()
