from datetime import date
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import Trade

# Indian equity LTCG/STCG rates (Budget 2023-24)
_LTCG_RATE = 0.10          # 10%
_STCG_RATE = 0.15          # 15%
_LTCG_EXEMPTION = 100_000  # ₹1,00,000 per financial year


def classify_trade(buy_date: date, sell_date: date) -> str:
    """Return 'LTCG' if held for more than 365 days, else 'STCG'."""
    return "LTCG" if (sell_date - buy_date).days > 365 else "STCG"


def calculate_tax(gains: float, classification: str) -> dict:
    """
    LTCG: 10% on gains above ₹1,00,000 exemption (listed equity).
    STCG: 15% flat (Section 111A, listed equity).
    """
    if classification == "LTCG":
        taxable_gain = max(0.0, gains - _LTCG_EXEMPTION)
        tax_amount = round(taxable_gain * _LTCG_RATE, 2)
        effective_rate = (_LTCG_RATE * taxable_gain / gains) if gains > 0 else 0.0
    else:
        taxable_gain = max(0.0, gains)
        tax_amount = round(taxable_gain * _STCG_RATE, 2)
        effective_rate = _STCG_RATE if gains > 0 else 0.0

    return {
        "tax_type": classification,
        "gross_gain": round(gains, 2),
        "taxable_gain": round(taxable_gain, 2),
        "tax_amount": tax_amount,
        "effective_rate": round(effective_rate * 100, 2),
    }


async def get_tax_summary(db: AsyncSession, year: int) -> dict:
    """
    Aggregate all closed trades for the Indian financial year (Apr 1 – Mar 31).
    `year` is the starting year of the FY, e.g. year=2025 → FY 2025-26.
    """
    fy_start = date(year, 4, 1)
    fy_end = date(year + 1, 3, 31)

    result = await db.execute(
        select(Trade).where(
            and_(
                Trade.status == "filled",
                Trade.filled_at.isnot(None),
                Trade.filled_at >= fy_start,
                Trade.filled_at <= fy_end,
                Trade.filled_price.isnot(None),
                Trade.submitted_price.isnot(None),
            )
        )
    )
    trades = result.scalars().all()

    ltcg_gains = 0.0
    stcg_gains = 0.0
    trade_details = []

    for trade in trades:
        if trade.action.upper() != "SELL":
            continue

        buy_date_val: Optional[date] = getattr(trade, "buy_date", None)
        sell_date_val: Optional[date] = (
            trade.filled_at.date() if trade.filled_at else None
        )

        if not sell_date_val:
            continue

        # Use buy_date if available, else fall back to submitted_at date
        if buy_date_val is None and trade.submitted_at:
            buy_date_val = trade.submitted_at.date()

        if buy_date_val is None:
            continue

        gain = float(trade.filled_price - trade.submitted_price) * float(trade.qty)
        classification = classify_trade(buy_date_val, sell_date_val)

        if classification == "LTCG":
            ltcg_gains += gain
        else:
            stcg_gains += gain

        trade_details.append({
            "ticker": trade.ticker,
            "qty": trade.qty,
            "buy_date": buy_date_val.isoformat(),
            "sell_date": sell_date_val.isoformat(),
            "gain": round(gain, 2),
            "classification": classification,
        })

    ltcg_tax = calculate_tax(ltcg_gains, "LTCG")
    stcg_tax = calculate_tax(stcg_gains, "STCG")

    return {
        "financial_year": f"{year}-{year + 1}",
        "ltcg": ltcg_tax,
        "stcg": stcg_tax,
        "total_tax_liability": round(ltcg_tax["tax_amount"] + stcg_tax["tax_amount"], 2),
        "trade_count": len(trade_details),
        "trades": trade_details,
    }
