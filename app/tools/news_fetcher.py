import asyncio
import calendar
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
from newsapi import NewsApiClient
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.market import NewsArticle
from app.tools.cache import build_key, get_cache, set_cache

logger = logging.getLogger(__name__)
settings = get_settings()

_NEWS_DEDUP_TTL = 7 * 24 * 60 * 60  # 7 days


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


async def fetch_news_newsapi(ticker: str, days: int = 7) -> list[dict]:
    if not settings.NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set; skipping NewsAPI fetch")
        return []

    from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    def _call() -> list[dict]:
        client = NewsApiClient(api_key=settings.NEWSAPI_KEY)
        response = client.get_everything(
            q=ticker,
            from_param=from_date,
            language="en",
            sort_by="publishedAt",
            page_size=20,
        )
        articles = []
        for art in response.get("articles", []):
            url = art.get("url") or ""
            if not url:
                continue
            articles.append({
                "headline": art.get("title") or "",
                "source": (art.get("source") or {}).get("name") or "",
                "url": url,
                "published_at": art.get("publishedAt") or "",
                "content": art.get("description") or art.get("content") or "",
            })
        return articles

    try:
        return await asyncio.to_thread(_call)
    except Exception as exc:
        logger.error("NewsAPI fetch failed for %s: %s", ticker, exc)
        return []


async def fetch_news_rss(ticker: str) -> list[dict]:
    rss_url = f"https://finance.yahoo.com/rss/headline?s={ticker}"

    def _parse() -> list[dict]:
        feed = feedparser.parse(rss_url)
        articles = []
        for entry in feed.entries:
            url = entry.get("link") or ""
            if not url:
                continue
            published_at = ""
            if entry.get("published_parsed"):
                ts = calendar.timegm(entry.published_parsed)
                published_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            articles.append({
                "headline": entry.get("title") or "",
                "source": "Yahoo Finance RSS",
                "url": url,
                "published_at": published_at,
                "content": entry.get("summary") or "",
            })
        return articles

    try:
        return await asyncio.to_thread(_parse)
    except Exception as exc:
        logger.error("RSS fetch failed for %s: %s", ticker, exc)
        return []


async def ingest_news(ticker: str, days: int = 7, db: AsyncSession = None) -> list[dict]:
    """
    Fetch from NewsAPI + Yahoo RSS, deduplicate, Redis-dedup, and upsert into news_articles.
    Returns the combined deduplicated article list (before Redis/DB filtering).
    """
    api_articles = await fetch_news_newsapi(ticker, days)
    rss_articles = await fetch_news_rss(ticker)

    # In-batch dedup by URL
    seen_in_batch: set[str] = set()
    combined: list[dict] = []
    for art in api_articles + rss_articles:
        url = art.get("url", "")
        if not url or url in seen_in_batch:
            continue
        seen_in_batch.add(url)
        combined.append(art)

    if not combined or db is None:
        return combined

    # Redis dedup + DB upsert
    rows_to_insert = []
    for art in combined:
        url = art["url"]
        dedup_key = build_key("news", "seen", _url_hash(url))
        if await get_cache(dedup_key) is not None:
            continue

        rows_to_insert.append({
            "ticker": ticker.upper(),
            "headline": art["headline"],
            "source": art.get("source", ""),
            "url": url,
            "published_at": _parse_dt(art.get("published_at", "")),
            "raw_content": art.get("content", ""),
        })

    if rows_to_insert:
        stmt = (
            pg_insert(NewsArticle)
            .values(rows_to_insert)
            .on_conflict_do_nothing(index_elements=["url"])
        )
        await db.execute(stmt)
        await db.commit()

        for row in rows_to_insert:
            dedup_key = build_key("news", "seen", _url_hash(row["url"]))
            await set_cache(dedup_key, 1, _NEWS_DEDUP_TTL)

        logger.info("Ingested %d new articles for %s", len(rows_to_insert), ticker)

    return combined
