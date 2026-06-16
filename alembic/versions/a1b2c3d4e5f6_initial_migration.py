"""initial migration

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-16

"""
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE stocks_watchlist (
            id          SERIAL PRIMARY KEY,
            ticker      VARCHAR(10) NOT NULL UNIQUE,
            company     TEXT,
            sector      TEXT,
            is_active   BOOLEAN DEFAULT TRUE,
            added_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE price_snapshots (
            id            BIGSERIAL PRIMARY KEY,
            ticker        VARCHAR(10) NOT NULL,
            snapshot_date DATE NOT NULL,
            open          NUMERIC(12,4),
            high          NUMERIC(12,4),
            low           NUMERIC(12,4),
            close         NUMERIC(12,4),
            volume        BIGINT,
            source        VARCHAR(32) DEFAULT 'yfinance',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (ticker, snapshot_date)
        )
    """)
    op.execute("CREATE INDEX ix_price_snapshots_ticker_date ON price_snapshots (ticker, snapshot_date DESC)")

    op.execute("""
        CREATE TABLE signals (
            id              BIGSERIAL PRIMARY KEY,
            query_id        UUID NOT NULL,
            ticker          VARCHAR(10) NOT NULL,
            signal          VARCHAR(8) NOT NULL,
            confidence      NUMERIC(4,3),
            quant_signal    VARCHAR(8),
            sentiment_score NUMERIC(4,3),
            risk_decision   VARCHAR(8),
            summary         TEXT,
            raw_output      JSONB,
            generated_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_signals_ticker_generated_at ON signals (ticker, generated_at DESC)")

    op.execute("""
        CREATE TABLE agent_run_logs (
            id            BIGSERIAL PRIMARY KEY,
            query_id      UUID NOT NULL,
            agent_name    VARCHAR(32) NOT NULL,
            task_input    JSONB,
            task_output   JSONB,
            status        VARCHAR(16) NOT NULL,
            error_message TEXT,
            latency_ms    INTEGER,
            started_at    TIMESTAMPTZ,
            finished_at   TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX ix_agent_run_logs_query_id ON agent_run_logs (query_id)")
    op.execute("CREATE INDEX ix_agent_run_logs_agent_name_started_at ON agent_run_logs (agent_name, started_at DESC)")

    op.execute("""
        CREATE TABLE news_articles (
            id              BIGSERIAL PRIMARY KEY,
            ticker          VARCHAR(10),
            headline        TEXT NOT NULL,
            source          VARCHAR(128),
            url             TEXT UNIQUE,
            published_at    TIMESTAMPTZ,
            sentiment_score NUMERIC(4,3),
            raw_content     TEXT,
            ingested_at     TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_news_articles_ticker_published_at ON news_articles (ticker, published_at DESC)")

    op.execute("""
        CREATE TABLE filing_chunks (
            id           BIGSERIAL PRIMARY KEY,
            ticker       VARCHAR(10) NOT NULL,
            filing_type  VARCHAR(16),
            filing_date  DATE,
            accession_no VARCHAR(32),
            chunk_index  INTEGER,
            chunk_text   TEXT NOT NULL,
            embedding    VECTOR(384),
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    # ivfflat index requires data; create after first bulk ingest if empty at migration time
    op.execute("CREATE INDEX ix_filing_chunks_embedding ON filing_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX ix_filing_chunks_ticker_filing_date ON filing_chunks (ticker, filing_date DESC)")

    op.execute("""
        CREATE TABLE trades (
            id               BIGSERIAL PRIMARY KEY,
            query_id         UUID,
            alpaca_order_id  TEXT UNIQUE,
            ticker           VARCHAR(10) NOT NULL,
            action           VARCHAR(8) NOT NULL,
            qty              INTEGER NOT NULL,
            submitted_price  NUMERIC(12,4),
            filled_price     NUMERIC(12,4),
            stop_loss        NUMERIC(12,4),
            take_profit      NUMERIC(12,4),
            status           VARCHAR(16),
            paper_mode       BOOLEAN DEFAULT TRUE,
            submitted_at     TIMESTAMPTZ DEFAULT NOW(),
            filled_at        TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX ix_trades_ticker_submitted_at ON trades (ticker, submitted_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trades")
    op.execute("DROP TABLE IF EXISTS filing_chunks")
    op.execute("DROP TABLE IF EXISTS news_articles")
    op.execute("DROP TABLE IF EXISTS agent_run_logs")
    op.execute("DROP TABLE IF EXISTS signals")
    op.execute("DROP TABLE IF EXISTS price_snapshots")
    op.execute("DROP TABLE IF EXISTS stocks_watchlist")
