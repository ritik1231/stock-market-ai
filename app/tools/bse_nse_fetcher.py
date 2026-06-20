import io
import logging
from typing import Optional

import httpx

from app.tools.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

_BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html",
    "Referer": "https://www.bseindia.com",
}
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html",
    "Referer": "https://www.nseindia.com",
    "Accept-Language": "en-US,en;q=0.9",
}

_BSE_SEARCH_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    "?Group=&Scripcode=&shname={symbol}&scripname=&industry=&segment=Equity&status=Active"
)
_BSE_ANNOUNCEMENTS_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w?scripcode={bse_code}"
)
_NSE_FILINGS_URL = (
    "https://nsearchives.nseindia.com/corporates/symbol-wise/{ticker}/"
)


def get_bse_code(ticker: str) -> str:
    """Strip .NS/.BO suffix to derive a clean symbol for BSE code lookup."""
    return ticker.replace(".NS", "").replace(".BO", "").upper()


async def _lookup_bse_numeric_code(symbol: str) -> Optional[str]:
    """Query BSE search API to get the numeric scrip code for a symbol."""
    url = _BSE_SEARCH_URL.format(symbol=symbol)
    try:
        async with httpx.AsyncClient(headers=_BSE_HEADERS, timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                return str(data[0].get("SCRIP_CD", ""))
            if isinstance(data, dict):
                items = data.get("Table", data.get("data", []))
                if items:
                    return str(items[0].get("SCRIP_CD", ""))
    except Exception as exc:
        logger.warning("BSE code lookup failed for %s: %s", symbol, exc)
    return None


async def fetch_bse_announcements(ticker: str, max_results: int = 10) -> list[dict]:
    """Fetch corporate announcements from BSE for a given ticker.

    Returns list of {filing_type, filing_date, document_url, description}.
    """
    await check_rate_limit("bse")

    symbol = get_bse_code(ticker)
    bse_code = await _lookup_bse_numeric_code(symbol)
    if not bse_code:
        logger.warning("Cannot resolve BSE numeric code for %s", ticker)
        return []

    url = _BSE_ANNOUNCEMENTS_URL.format(bse_code=bse_code)
    try:
        async with httpx.AsyncClient(headers=_BSE_HEADERS, timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("BSE announcements fetch failed for %s: %s", ticker, exc)
        return []

    announcements = []
    items = data if isinstance(data, list) else data.get("Table", data.get("data", []))
    for item in items[:max_results]:
        announcements.append({
            "filing_type": item.get("category") or item.get("CATEGORYNAME") or "announcement",
            "filing_date": item.get("DT_TM") or item.get("NEWS_DT") or "",
            "document_url": item.get("ATTACHMENTNAME") or item.get("PDFLINKANYEWHERE") or "",
            "description": item.get("NEWSSUB") or item.get("headline") or "",
        })

    return announcements


async def fetch_nse_filings(ticker: str) -> list[dict]:
    """Fetch corporate filings from NSE archives for a given ticker.

    Returns list of {filing_type, filing_date, document_url, description}.
    """
    await check_rate_limit("nse")

    # Strip exchange suffix for NSE symbol
    symbol = ticker.replace(".NS", "").replace(".BO", "").upper()
    url = _NSE_FILINGS_URL.format(ticker=symbol)

    try:
        async with httpx.AsyncClient(headers=_NSE_HEADERS, timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("NSE filings fetch failed for %s: %s", ticker, exc)
        return []

    filings = []
    items = data if isinstance(data, list) else data.get("data", [])
    for item in items[:10]:
        filings.append({
            "filing_type": item.get("seq_filing_type") or item.get("filing_type") or "filing",
            "filing_date": item.get("timestamp") or item.get("filing_date") or "",
            "document_url": item.get("url") or "",
            "description": item.get("subject") or item.get("description") or "",
        })

    return filings


async def fetch_filing_pdf(document_url: str) -> str:
    """Download a PDF from the given URL and extract plain text using pdfminer.six."""
    if not document_url:
        return ""

    try:
        async with httpx.AsyncClient(
            headers={**_BSE_HEADERS, "Accept": "application/pdf"},
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            resp = await client.get(document_url)
            resp.raise_for_status()
            pdf_bytes = resp.content
    except Exception as exc:
        logger.error("PDF download failed (%s): %s", document_url, exc)
        return ""

    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams

        output = io.StringIO()
        extract_text_to_fp(
            io.BytesIO(pdf_bytes),
            output,
            laparams=LAParams(),
            output_type="text",
            codec="utf-8",
        )
        text = output.getvalue()
        import re
        return re.sub(r"\s+", " ", text).strip()
    except Exception as exc:
        logger.error("PDF text extraction failed: %s", exc)
        return ""
