import hashlib
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import FilingChunk

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping token-approximate chunks (1 token ≈ 0.75 words)."""
    words_per_chunk = int(chunk_size * 0.75)
    overlap_words = int(overlap * 0.75)

    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + words_per_chunk
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap_words

    return chunks


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Encode chunks in a single batch with all-MiniLM-L6-v2 (384-dim)."""
    if not chunks:
        return []
    model = _get_model()
    vectors = model.encode(chunks, show_progress_bar=False, batch_size=64)
    return [v.tolist() for v in vectors]


async def ingest_filing(
    ticker: str,
    filing_type: str,
    filing_date: str,
    accession_no: str,
    text: str,
    db: AsyncSession,
) -> int:
    """Chunk → embed → bulk insert into filing_chunks. Returns number of rows inserted."""
    # Skip if this accession_no is already present for this ticker
    exists = await db.execute(
        select(FilingChunk.id)
        .where(FilingChunk.ticker == ticker, FilingChunk.accession_no == accession_no)
        .limit(1)
    )
    if exists.scalar() is not None:
        logger.info("Already ingested ticker=%s accession_no=%s — skipping", ticker, accession_no)
        return 0

    chunks = chunk_text(text)
    if not chunks:
        return 0

    embeddings = embed_chunks(chunks)

    parsed_date: date | None = None
    if filing_date:
        try:
            parsed_date = date.fromisoformat(filing_date[:10])
        except ValueError:
            logger.warning("Cannot parse filing_date=%r", filing_date)

    rows = [
        FilingChunk(
            ticker=ticker,
            filing_type=filing_type,
            filing_date=parsed_date,
            accession_no=accession_no,
            chunk_index=idx,
            chunk_text=chunk,
            embedding=embedding,
        )
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    db.add_all(rows)
    await db.commit()
    logger.info("Ingested %d chunks ticker=%s accession_no=%s", len(rows), ticker, accession_no)
    return len(rows)


async def ingest_news_for_rag(article: dict, db: AsyncSession) -> int:
    """Embed a news article and store it in filing_chunks with filing_type='news'."""
    url = article.get("url", "")
    headline = article.get("headline", "")
    content = article.get("content", "")
    ticker = article.get("ticker", "")
    published_at = article.get("published_at", "")

    text = f"{headline}\n\n{content}".strip()
    if not text or not ticker:
        return 0

    accession_no = hashlib.md5(url.encode()).hexdigest()[:32]

    filing_date = ""
    if published_at:
        try:
            if hasattr(published_at, "date"):
                filing_date = published_at.date().isoformat()
            else:
                filing_date = str(published_at)[:10]
        except Exception:
            pass

    return await ingest_filing(
        ticker=ticker,
        filing_type="news",
        filing_date=filing_date,
        accession_no=accession_no,
        text=text,
        db=db,
    )
