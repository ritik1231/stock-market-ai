from sqlalchemy import BigInteger, Column, Date, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP as PGTIMESTAMP, UUID
from sqlalchemy.sql import func

try:
    from pgvector.sqlalchemy import Vector
    _embedding_col = lambda: Column(Vector(384))  # noqa: E731
except ImportError:
    _embedding_col = lambda: Column(Text)  # fallback until pgvector is installed  # noqa: E731

from app.db import Base


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_ticker_generated_at", "ticker", "generated_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_id = Column(UUID(as_uuid=True), nullable=False)
    ticker = Column(String(10), nullable=False)
    signal = Column(String(8), nullable=False)
    confidence = Column(Numeric(4, 3))
    quant_signal = Column(String(8))
    sentiment_score = Column(Numeric(4, 3))
    risk_decision = Column(String(8))
    summary = Column(Text)
    raw_output = Column(JSONB)
    generated_at = Column(PGTIMESTAMP(timezone=True), server_default=func.now())


class AgentRunLog(Base):
    __tablename__ = "agent_run_logs"
    __table_args__ = (
        Index("ix_agent_run_logs_query_id", "query_id"),
        Index("ix_agent_run_logs_agent_name_started_at", "agent_name", "started_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_id = Column(UUID(as_uuid=True), nullable=False)
    agent_name = Column(String(32), nullable=False)
    task_input = Column(JSONB)
    task_output = Column(JSONB)
    status = Column(String(16), nullable=False)
    error_message = Column(Text)
    latency_ms = Column(Integer)
    started_at = Column(PGTIMESTAMP(timezone=True))
    finished_at = Column(PGTIMESTAMP(timezone=True))


class FilingChunk(Base):
    __tablename__ = "filing_chunks"
    __table_args__ = (
        Index("ix_filing_chunks_ticker_filing_date", "ticker", "filing_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    filing_type = Column(String(16))
    filing_date = Column(Date)
    accession_no = Column(String(32))
    chunk_index = Column(Integer)
    chunk_text = Column(Text, nullable=False)
    embedding = _embedding_col()
    created_at = Column(PGTIMESTAMP(timezone=True), server_default=func.now())
