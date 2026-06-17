import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_SEC = "https://www.sec.gov"
_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"

_HEADERS = {
    "User-Agent": "StockMarketAI Research Bot techteam@collegedekho.com",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/html, application/atom+xml",
}


async def _get_with_backoff(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
) -> httpx.Response:
    delay = 1.0
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(url)
            if resp.status_code == 429:
                if attempt == max_retries:
                    resp.raise_for_status()
                logger.warning("EDGAR 429 on attempt %d; retrying in %.1fs", attempt + 1, delay)
                await asyncio.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                raise
            await asyncio.sleep(delay)
            delay *= 2
    raise last_exc  # unreachable but satisfies type checker


async def get_cik_for_ticker(ticker: str) -> str:
    """
    Look up the SEC CIK for a ticker symbol via the EDGAR browse-edgar Atom feed.
    Returns the numeric CIK string (without leading zeros).
    """
    url = (
        f"{_BASE_SEC}/cgi-bin/browse-edgar"
        f"?action=getcompany&ticker={ticker}&output=atom"
    )
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15.0) as client:
        resp = await _get_with_backoff(client, url)

    text = resp.text

    # Fast path: regex scan for CIK= in the raw XML/Atom response
    match = re.search(r"CIK=0*(\d+)", text)
    if match:
        return match.group(1)

    # Fallback: feedparser link traversal
    feed = feedparser.parse(text)
    for link in feed.feed.get("links", []):
        href = link.get("href", "")
        m = re.search(r"CIK=0*(\d+)", href)
        if m:
            return m.group(1)
    for entry in feed.entries:
        for link in entry.get("links", []):
            href = link.get("href", "")
            m = re.search(r"CIK=0*(\d+)", href)
            if m:
                return m.group(1)

    raise ValueError(f"CIK not found for ticker: {ticker}")


async def fetch_filings(
    ticker: str,
    form_types: list[str],
    max_results: int = 5,
) -> list[dict]:
    """
    Query EDGAR EFTS full-text search for filings matching the ticker and form types.
    Returns list of {accession_no, filing_type, filing_date, document_url}.
    """
    start_date = (datetime.utcnow() - timedelta(days=730)).strftime("%Y-%m-%d")
    end_date = datetime.utcnow().strftime("%Y-%m-%d")

    results: list[dict] = []

    async with httpx.AsyncClient(headers=_HEADERS, timeout=30.0) as client:
        for form_type in form_types:
            params = {
                "q": f'"{ticker}"',
                "forms": form_type,
                "dateRange": "custom",
                "startdt": start_date,
                "enddt": end_date,
            }
            url = f"{_EFTS_URL}?{urlencode(params)}"

            try:
                resp = await _get_with_backoff(client, url)
                data = resp.json()
            except Exception as exc:
                logger.error("EFTS search failed for %s/%s: %s", ticker, form_type, exc)
                await asyncio.sleep(0.1)
                continue

            hits = data.get("hits", {}).get("hits", [])
            for hit in hits[:max_results]:
                src = hit.get("_source", {})
                accession_no = src.get("accession_no") or hit.get("_id", "")
                if not accession_no:
                    continue

                # Derive CIK from the accession number prefix (zero-padded 10-digit CIK)
                cik_raw = accession_no.split("-")[0]
                cik = cik_raw.lstrip("0") or "0"
                accession_nodash = accession_no.replace("-", "")

                # Point to the filing index page; fetch_filing_text will navigate to primary doc
                document_url = (
                    f"{_BASE_SEC}/Archives/edgar/data/{cik}"
                    f"/{accession_nodash}/{accession_nodash}-index.htm"
                )

                results.append({
                    "accession_no": accession_no,
                    "filing_type": src.get("form_type") or form_type,
                    "filing_date": src.get("file_date") or "",
                    "document_url": document_url,
                })

                if len(results) >= max_results:
                    break

            await asyncio.sleep(0.1)

            if len(results) >= max_results:
                break

    return results


def _primary_doc_url(soup: BeautifulSoup, index_url: str) -> Optional[str]:
    """
    Parse an EDGAR filing index page to extract the URL of the primary text document.
    """
    base = index_url.rsplit("/", 1)[0]
    preferred_exts = (".htm", ".html", ".txt")

    for row in soup.find_all("tr"):
        link = row.find("a", href=True)
        if not link:
            continue
        href: str = link["href"]
        if "-index" in href.lower():
            continue
        lower = href.lower()
        if any(lower.endswith(ext) for ext in preferred_exts):
            if href.startswith("http"):
                return href
            return f"{_BASE_SEC}{href}" if href.startswith("/") else f"{base}/{href}"

    return None


async def fetch_filing_text(document_url: str) -> str:
    """
    Fetch a filing from SEC EDGAR and return its plain text (HTML stripped).
    If document_url points to a filing index page, follows the primary document link.
    """
    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        resp = await _get_with_backoff(client, document_url)
        soup = BeautifulSoup(resp.text, "lxml")

        if document_url.endswith("-index.htm"):
            primary_url = _primary_doc_url(soup, document_url)
            if primary_url and primary_url != document_url:
                await asyncio.sleep(0.1)
                resp = await _get_with_backoff(client, primary_url)
                soup = BeautifulSoup(resp.text, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "head"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()
