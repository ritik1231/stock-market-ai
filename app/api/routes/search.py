from fastapi import APIRouter, Query
from pydantic import BaseModel
import httpx

router = APIRouter(tags=["search"])

_YF_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


class SearchResult(BaseModel):
    ticker: str
    name: str
    exchange: str
    type: str


@router.get("/search", response_model=list[SearchResult])
async def search_stocks(q: str = Query(min_length=1, max_length=50)):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                _YF_SEARCH,
                params={"q": q, "lang": "en-US", "region": "IN", "quotesCount": 10, "newsCount": 0},
                headers=_HEADERS,
            )
            resp.raise_for_status()
            quotes = resp.json().get("quotes", [])
    except Exception:
        return []

    results = []
    for q in quotes:
        symbol = q.get("symbol", "")
        name = q.get("longname") or q.get("shortname") or symbol
        exchange = q.get("exchange", "")
        qtype = q.get("quoteType", "")
        if symbol and qtype in ("EQUITY", "ETF", "MUTUALFUND"):
            results.append(SearchResult(ticker=symbol, name=name, exchange=exchange, type=qtype))
    return results
