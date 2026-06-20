import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.embedder import embed_chunks
from app.tools.llm import groq_complete

logger = logging.getLogger(__name__)


async def retrieve_context(
    ticker: str,
    query: str,
    db: AsyncSession,
    top_k: int = 5,
    filing_types: list[str] | None = None,
) -> list[dict]:
    """Embed query and return top-k chunks via pgvector cosine similarity."""
    query_vec = embed_chunks([query])[0]
    # Format as PostgreSQL vector literal: '[v1,v2,...]'
    query_vec_str = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"

    where_parts = ["ticker = :ticker", "embedding IS NOT NULL"]
    params: dict = {"ticker": ticker, "top_k": top_k, "query_vec": query_vec_str}

    if filing_types:
        where_parts.append("filing_type = ANY(:filing_types)")
        params["filing_types"] = filing_types

    where_sql = " AND ".join(where_parts)
    sql = text(f"""
        SELECT chunk_text, filing_type, filing_date,
               1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM filing_chunks
        WHERE {where_sql}
        ORDER BY embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "chunk_text": row.chunk_text,
            "similarity": round(float(row.similarity), 4) if row.similarity is not None else 0.0,
            "filing_type": row.filing_type,
            "filing_date": str(row.filing_date) if row.filing_date else None,
        }
        for row in rows
    ]


def format_context_for_prompt(results: list[dict]) -> str:
    """Format retrieved chunks into a numbered context block for Groq prompt injection."""
    if not results:
        return "No relevant context found."

    lines = ["Relevant context from filings and news:\n"]
    for i, r in enumerate(results, 1):
        meta = (
            f"[{r.get('filing_type', 'unknown')} | "
            f"{r.get('filing_date', 'N/A')} | "
            f"similarity: {r.get('similarity', 0):.3f}]"
        )
        lines.append(f"{i}. {meta}\n{r['chunk_text']}\n")

    return "\n".join(lines)


async def rag_answer(ticker: str, query: str, db: AsyncSession) -> dict:
    """Retrieve relevant chunks, inject into a Groq prompt, return answer + sources."""
    results = await retrieve_context(ticker, query, db)
    context = format_context_for_prompt(results)

    from app.tools.llm import _INDIA_CONTEXT

    system_prompt = (
        "You are a financial analyst with access to BSE/NSE filings and Indian market news. "
        "Answer the question using only the provided context. "
        "Be concise and cite the source type (filing/news) when relevant. "
        + _INDIA_CONTEXT
    )
    user_prompt = f"Question: {query}\n\n{context}"

    answer = await groq_complete(system_prompt, user_prompt, max_tokens=512)

    sources = [
        {
            "filing_type": r.get("filing_type"),
            "filing_date": r.get("filing_date"),
            "similarity": r.get("similarity"),
        }
        for r in results
    ]

    return {"answer": answer, "sources": sources}
