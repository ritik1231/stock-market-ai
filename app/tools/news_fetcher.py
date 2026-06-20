import asyncio
import calendar
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.market import NewsArticle
from app.tools.cache import build_key, get_cache, set_cache

logger = logging.getLogger(__name__)
settings = get_settings()

_NEWS_DEDUP_TTL = 7 * 24 * 60 * 60  # 7 days

INDIAN_NEWS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2143429.cms",
    "https://www.business-standard.com/rss/markets/companies.rss",
    "https://www.livemint.com/rss/markets",
]


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


def _parse_feed_entry(entry: feedparser.FeedParserDict, source_name: str) -> Optional[dict]:
    url = entry.get("link") or ""
    if not url:
        return None
    published_at = ""
    if entry.get("published_parsed"):
        ts = calendar.timegm(entry.published_parsed)
        published_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return {
        "headline": entry.get("title") or "",
        "source": source_name,
        "url": url,
        "published_at": published_at,
        "content": entry.get("summary") or entry.get("description") or "",
    }


def _parse_feed(url: str, source_name: str) -> list[dict]:
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries:
        item = _parse_feed_entry(entry, source_name)
        if item:
            articles.append(item)
    return articles


async def fetch_news_india(ticker: str) -> list[dict]:
    """Fetch news from Indian financial RSS feeds for the given ticker.

    Pulls from MoneyControl (ticker-specific), Economic Times, Business Standard,
    and LiveMint. Deduplicates by URL.
    """
    clean = ticker.replace(".NS", "").replace(".BO", "").upper()

    feeds_with_names = [
        (f"https://www.moneycontrol.com/rss/{clean}.xml", "MoneyControl"),
        (INDIAN_NEWS_FEEDS[0], "Economic Times"),
        (INDIAN_NEWS_FEEDS[1], "Business Standard"),
        (INDIAN_NEWS_FEEDS[2], "LiveMint"),
    ]

    def _fetch_all() -> list[dict]:
        seen: set[str] = set()
        combined: list[dict] = []
        for feed_url, name in feeds_with_names:
            try:
                for item in _parse_feed(feed_url, name):
                    u = item["url"]
                    if u and u not in seen:
                        seen.add(u)
                        combined.append(item)
            except Exception as exc:
                logger.warning("Feed error (%s): %s", feed_url, exc)
        return combined

    try:
        return await asyncio.to_thread(_fetch_all)
    except Exception as exc:
        logger.error("fetch_news_india failed for %s: %s", ticker, exc)
        return []


async def ingest_news(ticker: str, days: int = 7, db: AsyncSession = None) -> list[dict]:
    """Fetch Indian news, Redis-dedup, and upsert into news_articles.

    Returns the combined article list before DB filtering.
    """
    articles = await fetch_news_india(ticker)

    if not articles or db is None:
        return articles

    rows_to_insert = []
    for art in articles:
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

    return articles
