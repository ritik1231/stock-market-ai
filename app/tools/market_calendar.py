import zoneinfo
from datetime import date, datetime

_IST = zoneinfo.ZoneInfo("Asia/Kolkata")
_MARKET_OPEN = (9, 15)   # 9:15 AM IST
_MARKET_CLOSE = (15, 30) # 3:30 PM IST

# NSE holidays — update each year via https://www.nseindia.com/products-services/equity-market-holidays
_NSE_HOLIDAYS: set[str] = {
    # 2025
    "2025-01-26",  # Republic Day
    "2025-02-26",  # Mahashivratri
    "2025-03-14",  # Holi
    "2025-04-14",  # Dr. Ambedkar Jayanti
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-08-15",  # Independence Day
    "2025-08-27",  # Ganesh Chaturthi
    "2025-10-02",  # Gandhi Jayanti
    "2025-10-24",  # Diwali Laxmi Puja
    "2025-10-27",  # Diwali Balipratipada
    "2025-11-05",  # Gurunanak Jayanti
    "2025-12-25",  # Christmas
    # 2026
    "2026-01-26",  # Republic Day
    "2026-02-26",  # Mahashivratri
    "2026-03-17",  # Holi
    "2026-03-31",  # Ram Navami
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-08-15",  # Independence Day
    "2026-09-19",  # Ganesh Chaturthi
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-14",  # Dussehra
    "2026-11-01",  # Diwali Laxmi Puja
    "2026-11-02",  # Diwali Balipratipada
    "2026-11-23",  # Gurunanak Jayanti
    "2026-12-25",  # Christmas
}


def is_trading_day(d: date) -> bool:
    """Return False on weekends and NSE holidays."""
    if d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False
    return d.isoformat() not in _NSE_HOLIDAYS


def is_market_open() -> bool:
    """Return True if current IST time falls within NSE/BSE trading hours (Mon–Fri 9:15–15:30)."""
    now_ist = datetime.now(tz=_IST)
    if not is_trading_day(now_ist.date()):
        return False
    h, m = now_ist.hour, now_ist.minute
    return _MARKET_OPEN <= (h, m) <= _MARKET_CLOSE
