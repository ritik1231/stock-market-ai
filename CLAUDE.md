# Stock Market AI — Claude Code Guide

Agentic, multi-agent AI system targeting **Indian equity markets (NSE/BSE)**. Ingests market data + news + filings, generates trading signals, executes paper trades via Alpaca. Educational/research only — no real-money trading.

**Market hours:** NSE/BSE 9:15 AM – 3:30 PM IST, Monday–Friday. Celery Beat runs in `Asia/Kolkata` timezone.

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI 0.111 + uvicorn |
| Task queue | Celery 5 + RabbitMQ |
| Agent graph | LangGraph |
| LLM | Groq (llama-3.3-70b-versatile) |
| DB | PostgreSQL 16 + pgvector |
| Cache / broker backend | Redis 7 |
| ORM / migrations | SQLAlchemy 2 async + Alembic |
| Market data | yfinance |
| Technical analysis | pandas-ta |
| News | NewsAPI + feedparser (Yahoo RSS) |
| SEC filings | EDGAR EFTS API + BeautifulSoup |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 (384-dim) |
| Paper trading | alpaca-py |
| Validation | Pydantic v2 |
| Observability | structlog + tenacity |

## Project Layout

```
app/
  main.py              # FastAPI app, /health endpoint, lifespan
  config.py            # Pydantic Settings (reads .env), get_settings() cached
  celery_app.py        # Celery instance, 5 queues, dead-letter exchange
  db/__init__.py       # async SQLAlchemy engine, Base, get_db()
  models/
    market.py          # StocksWatchlist, PriceSnapshot, NewsArticle
    agent.py           # AgentRunLog, Signal, FilingChunk
    trading.py         # Trade
  tools/
    cache.py           # Redis singleton: get/set/delete/rate_limit_check/build_key
    price_fetcher.py   # fetch_ohlcv, get_latest_price, save_price_snapshot
    news_fetcher.py    # fetch_news_newsapi, fetch_news_rss, ingest_news
    edgar_fetcher.py   # get_cik_for_ticker, fetch_filings, fetch_filing_text
  agents/              # (Phase 3+) research, quant, risk, execution agents
  api/routes/          # (Phase 5+) analysis, signals, portfolio, trades routes
  schemas/             # (Phase 5+) Pydantic v2 request/response schemas
alembic/               # DB migrations
  versions/a1b2c3d4e5f6_initial_migration.py  # all 7 tables
tests/
  test_price_fetcher.py
docker/init.sql        # CREATE EXTENSION IF NOT EXISTS vector
docker-compose.yml     # postgres (pgvector), redis, rabbitmq
PHASES.md              # Full task-by-task build plan (source of truth)
SYSTEM_DESIGN.md       # Architecture, DB schema, API contracts
```

## Phase Progress

- **Phase 0** ✅ — Scaffold: FastAPI, Docker Compose, config, Celery, Alembic
- **Phase 1** ✅ — Data layer: DB models + migration, price fetcher, news fetcher, EDGAR fetcher, Redis cache utils
- **Phase 2** ✅ — Tool library: indicators, Groq LLM wrapper, embedder, RAG retrieval
- **Phase 3** ✅ — Agents: Research, Quant, Risk, Execution (Celery tasks)
- **Phase 4** ✅ — LangGraph orchestrator: state graph, node implementations, Celery task, tests
- **Phase 5** ✅ — API routes: schemas, /analyze, /analysis, /signal, /portfolio, /trade, /trades, middleware
- **Phase 6** ✅ — Paper trading loop: alpaca client (cancel/close), portfolio tracker, Celery Beat schedule, integration tests
- **Phase 7** ✅ — Observability: structlog, tenacity retries, audit trail, rate limiter, DLQ consumer, alerts table, watchdog
- **Phase 8** — React frontend (optional)

Always check PHASES.md for exact task specs before implementing any phase task.

## Local Dev Setup

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Activate venv and install deps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Copy env and fill in API keys
cp .env.example .env

# 4. Run DB migration
alembic upgrade head

# 5. Start API server
uvicorn app.main:app --reload

# 6. Run tests
pytest tests/ -v
```

## Environment Variables (`.env`)

| Key | Required for |
|---|---|
| `DATABASE_URL` | All DB operations (default: localhost:5432) |
| `REDIS_URL` | Caching, rate limiting, Celery backend |
| `RABBITMQ_URL` | Celery broker |
| `NEWSAPI_KEY` | NewsAPI fetcher (RSS works without it) |
| `GROQ_API_KEY` | Phase 2+ LLM calls |
| `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` | Phase 3+ paper trading |
| `PAPER_MODE=true` | Safety gate — must stay true |

## Key Design Decisions

- **Orchestrator** (`app/agents/orchestrator.py`) — `compiled_graph` is a module-level LangGraph `StateGraph`; `run_orchestrator` is the Celery task. Fan-out: START → research + quant (parallel); join → risk → conditional → execution or synthesize → END. Result cached in Redis at `result:{query_id}`.
- **Agents never talk to each other directly** — all coordination through LangGraph orchestrator state
- **Redis cache is fail-open** — if Redis is down, cache misses and rate limit checks pass through silently
- **News dedup** uses `news:seen:{md5(url)}` Redis key (7-day TTL) to avoid re-inserting articles
- **EDGAR document URLs** point to the filing index page (`-index.htm`); `fetch_filing_text` follows the primary document link automatically
- **CIK extraction** from EDGAR uses regex on `CIK=\d+` pattern in the Atom feed response
- **Rate limiter** (`cache.rate_limit_check`) is fixed-window via Redis INCR + EXPIRE
- `PAPER_MODE=false` raises `LiveTradingNotPermittedError` in the Execution Agent — hard safety gate

## DB Tables (all in PostgreSQL)

`stocks_watchlist`, `price_snapshots`, `signals`, `agent_run_logs`, `news_articles`, `filing_chunks` (VECTOR(384)), `trades`

## Running Individual Tools (quick smoke tests)

```python
# Price fetcher
import asyncio
from app.tools.price_fetcher import fetch_ohlcv, get_latest_price
asyncio.run(get_latest_price("AAPL"))

# EDGAR (no key needed)
from app.tools.edgar_fetcher import get_cik_for_ticker, fetch_filings
asyncio.run(get_cik_for_ticker("AAPL"))

# News RSS (no key needed)
from app.tools.news_fetcher import fetch_news_rss
asyncio.run(fetch_news_rss("AAPL"))

# Cache utils
from app.tools.cache import build_key, set_cache, get_cache
# requires Redis running
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok","redis":"ok"}
```

Swagger UI: http://localhost:8000/docs
RabbitMQ UI: http://localhost:15672 (guest/guest)
