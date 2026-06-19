import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.logging_config import log_agent_task
from app.models.agent import AgentRunLog
from app.tools.llm import groq_sentiment, groq_summarize
from app.tools.news_fetcher import fetch_news_newsapi, fetch_news_rss
from app.tools.rag import format_context_for_prompt, rag_answer

logger = structlog.get_logger(__name__)


class ResearchInput(BaseModel):
    query_id: str
    ticker: str
    lookback_days: int = 7


class ResearchOutput(BaseModel):
    query_id: str
    ticker: str
    sentiment_score: float
    sentiment_label: str
    sentiment_reasoning: str
    rag_answer: str
    rag_sources: list[dict]
    summary: str
    article_count: int


async def _run_research(input_data: ResearchInput) -> ResearchOutput:
    ticker = input_data.ticker.upper()

    # Step 1: Fetch news from both sources concurrently and deduplicate by URL
    newsapi_articles, rss_articles = await asyncio.gather(
        fetch_news_newsapi(ticker, input_data.lookback_days),
        fetch_news_rss(ticker),
    )

    seen_urls: set[str] = set()
    articles: list[dict] = []
    for article in newsapi_articles + rss_articles:
        url = article.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            articles.append(article)

    # Step 2: Build combined text from headlines + snippets (truncated to 4000 chars)
    parts = []
    for a in articles:
        headline = a.get("headline", "")
        snippet = a.get("content", "")
        if headline:
            parts.append(f"{headline}. {snippet}".strip())
    combined_text = " ".join(parts)[:4000]

    # Step 3: Sentiment analysis via Groq
    if combined_text.strip():
        sentiment = await groq_sentiment(combined_text, ticker)
    else:
        sentiment = {"score": 0.0, "label": "NEUTRAL", "reasoning": "No news found"}

    # Step 4: RAG answer for risks and opportunities
    async with AsyncSessionLocal() as db:
        rag_result = await rag_answer(
            ticker,
            f"What are the main risks and opportunities for {ticker}?",
            db,
        )

    rag_context = rag_result.get("answer", "No SEC context available.")
    rag_sources = rag_result.get("sources", [])

    # Step 5: Summarize news + SEC context
    summary = await groq_summarize(combined_text, rag_context, max_words=200)

    return ResearchOutput(
        query_id=input_data.query_id,
        ticker=ticker,
        sentiment_score=float(sentiment.get("score", 0.0)),
        sentiment_label=sentiment.get("label", "NEUTRAL"),
        sentiment_reasoning=sentiment.get("reasoning", ""),
        rag_answer=rag_context,
        rag_sources=rag_sources,
        summary=summary,
        article_count=len(articles),
    )


async def _write_log(
    query_id: str,
    task_input: dict,
    task_output: Optional[dict],
    status: str,
    error_message: Optional[str],
    started_at: datetime,
    finished_at: datetime,
) -> None:
    latency_ms = int((finished_at - started_at).total_seconds() * 1000)
    log_entry = AgentRunLog(
        query_id=UUID(query_id),
        agent_name="research",
        task_input=task_input,
        task_output=task_output,
        status=status,
        error_message=error_message,
        latency_ms=latency_ms,
        started_at=started_at,
        finished_at=finished_at,
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(log_entry)
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to write agent_run_log: %s", exc)


async def _execute(input_data: ResearchInput, payload: dict) -> dict:
    started_at = datetime.now(timezone.utc)
    exc_to_raise: Optional[Exception] = None
    output_dict: Optional[dict] = None
    status = "success"

    try:
        output = await _run_research(input_data)
        output_dict = output.model_dump()
    except Exception as exc:
        exc_to_raise = exc
        status = "error"

    finished_at = datetime.now(timezone.utc)
    await _write_log(
        query_id=input_data.query_id,
        task_input=payload,
        task_output=output_dict,
        status=status,
        error_message=str(exc_to_raise) if exc_to_raise else None,
        started_at=started_at,
        finished_at=finished_at,
    )

    if exc_to_raise:
        raise exc_to_raise

    latency_ms = int((finished_at - started_at).total_seconds() * 1000)
    logger.info(
        "research_agent finished ticker=%s latency_ms=%d",
        input_data.ticker,
        latency_ms,
    )
    return output_dict


@celery_app.task(bind=True, queue="agent.research", name="agents.research", max_retries=3, default_retry_delay=10)
@log_agent_task
def run_research_agent(self, payload: dict) -> dict:
    try:
        input_data = ResearchInput(**payload)
        return asyncio.run(_execute(input_data, payload))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
