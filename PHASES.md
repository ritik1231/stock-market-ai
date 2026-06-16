# Agentic Stock Market AI — Development Phases

Each task is scoped to one focused coding session. Task descriptions include enough context to start a fresh AI conversation with "Let's work on Phase X, Task X.Y."

---

## Phase 0 — Project Scaffold

**Goal:** Create the repo structure, virtual environment, Docker Compose stack, and a running FastAPI skeleton with a health check endpoint. Nothing AI-specific yet — just a working local foundation.

---

### Task 0.1 — Repo structure and Python environment

Create the top-level directory layout for the project. Initialize a Python 3.11 virtual environment using `venv`. Create a `pyproject.toml` using `setuptools` as the build backend. Add a `.gitignore` appropriate for Python projects (exclude `__pycache__`, `.env`, `*.pyc`, `venv/`, `*.egg-info`).

**Directory layout to create:**
```
stock_market_project/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       └── __init__.py
│   ├── agents/
│   │   └── __init__.py
│   ├── tools/
│   │   └── __init__.py
│   ├── db/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   └── schemas/
│       └── __init__.py
├── alembic/
├── tests/
├── docker/
├── .env.example
├── pyproject.toml
└── requirements.txt
```

No logic yet — just the skeleton files with empty `__init__.py` and placeholder comments.

---

### Task 0.2 — Environment configuration with Pydantic Settings

In `app/config.py`, create a `Settings` class using `pydantic-settings` (v2) that reads all config from environment variables. Include:

- `DATABASE_URL` (PostgreSQL DSN)
- `REDIS_URL`
- `RABBITMQ_URL`
- `GROQ_API_KEY`
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`
- `NEWSAPI_KEY`
- `PAPER_MODE` (bool, default `True`)
- `LOG_LEVEL` (default `INFO`)
- `CELERY_BROKER_URL` (same as `RABBITMQ_URL`)
- `CELERY_RESULT_BACKEND` (same as `REDIS_URL`)

Use `model_config = SettingsConfigDict(env_file=".env")`. Export a `get_settings()` function cached with `@lru_cache`. Create `.env.example` with placeholder values for all fields.

**Depends on:** Task 0.1

---

### Task 0.3 — Docker Compose stack (PostgreSQL, Redis, RabbitMQ)

Create `docker-compose.yml` at the project root. Define three services:

1. **postgres** — image `postgres:16`, port `5432`, env vars `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, volume `pgdata`. Enable pgvector by using image `pgvector/pgvector:pg16` instead of plain postgres.
2. **redis** — image `redis:7-alpine`, port `6379`, volume `redisdata`.
3. **rabbitmq** — image `rabbitmq:3.13-management`, ports `5672` and `15672` (management UI), env vars `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`.

Add a `healthcheck` for each service. Create `docker/init.sql` that runs `CREATE EXTENSION IF NOT EXISTS vector;` to enable pgvector on startup.

**Depends on:** Task 0.1

---

### Task 0.4 — FastAPI app skeleton with health check

In `app/main.py`, create the FastAPI application instance. Wire up:

- `GET /health` endpoint that checks database connectivity (SQLAlchemy ping), Redis ping, and returns a JSON `{"status": "ok", "db": "ok", "redis": "ok"}` or appropriate error status per service
- CORS middleware allowing all origins (tighten later)
- A startup event that logs the app version and config summary (mask secrets)
- Include a router from `app/api/routes/` (empty for now)

Install: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy`, `asyncpg`, `redis[asyncio]`.

In `app/db/__init__.py`, create an async SQLAlchemy engine and `get_db()` dependency using `asyncpg` as the driver.

**Depends on:** Tasks 0.2, 0.3

---

### Task 0.5 — Celery app and RabbitMQ connection

Create `app/celery_app.py` with a Celery instance configured to:
- Use RabbitMQ as the broker (`RABBITMQ_URL` from settings)
- Use Redis as the result backend (`REDIS_URL` from settings)
- Set `task_serializer = "json"`, `result_serializer = "json"`, `accept_content = ["json"]`
- Set `task_track_started = True` and `task_acks_late = True`
- Configure the dead letter exchange: all queues should have `x-dead-letter-exchange = "stock.dead_letter"`

Define the four agent queues (`agent.research`, `agent.quant`, `agent.risk`, `agent.execution`) and the orchestrator queue (`orchestrator.tasks`) as Celery queue objects. Verify connectivity by running `celery -A app.celery_app inspect ping`.

**Depends on:** Task 0.2

---

## Phase 1 — Data Layer

**Goal:** Build reliable data ingestion for price history, news, and SEC filings. Set up the full PostgreSQL schema with Alembic migrations and a Redis caching layer.

---

### Task 1.1 — Alembic setup and initial migration

Initialize Alembic in the project root (`alembic init alembic`). Configure `alembic/env.py` to use the `DATABASE_URL` from `app/config.Settings` and import all SQLAlchemy models from `app/models/`.

Create the initial migration that defines all six tables from the system design:
- `stocks_watchlist`
- `price_snapshots`
- `signals`
- `agent_run_logs`
- `news_articles`
- `filing_chunks` (with `VECTOR(384)` column — import `pgvector.sqlalchemy`)
- `trades`

Include all indexes defined in the schema. Add the `CREATE EXTENSION IF NOT EXISTS vector` statement inside the migration's `upgrade()` function before creating tables.

Define corresponding SQLAlchemy ORM models in `app/models/` (one file per table group: `market.py`, `agent.py`, `trading.py`).

**Depends on:** Task 0.3, Task 0.4

---

### Task 1.2 — yfinance price fetcher with Redis caching

Create `app/tools/price_fetcher.py`. Implement:

- `fetch_ohlcv(ticker: str, interval: str, period: str) -> pd.DataFrame` — calls `yfinance.Ticker(ticker).history(period=period, interval=interval)`, returns a clean DataFrame with columns `[open, high, low, close, volume, date]`
- `get_latest_price(ticker: str) -> float` — returns last close price
- Redis caching wrapper: before calling yfinance, check `ohlcv:{ticker}:{interval}` in Redis. Cache for 5 min (intraday) or 24h (daily). Serialize DataFrame to JSON with `df.to_json(orient="records")`.
- `save_price_snapshot(ticker: str, df: pd.DataFrame, db: AsyncSession)` — upserts daily rows into `price_snapshots` table using SQLAlchemy `insert(...).on_conflict_do_nothing()`

Write a simple test in `tests/test_price_fetcher.py` that fetches AAPL daily data and asserts the DataFrame has the expected columns.

**Depends on:** Task 1.1, Task 0.4

---

### Task 1.3 — News ingestion (NewsAPI + RSS)

Create `app/tools/news_fetcher.py`. Implement:

- `fetch_news_newsapi(ticker: str, days: int) -> list[dict]` — calls NewsAPI `/v2/everything` with `q=ticker`, `from=today-days`, returns list of `{headline, source, url, published_at, content}` dicts. Requires `NEWSAPI_KEY` from settings.
- `fetch_news_rss(ticker: str) -> list[dict]` — uses `feedparser` to pull from Yahoo Finance RSS (`https://finance.yahoo.com/rss/headline?s={ticker}`) and returns same dict format.
- `ingest_news(ticker: str, days: int, db: AsyncSession)` — calls both fetchers, deduplicates by URL, upserts into `news_articles` table (skip on URL conflict).
- Redis dedup: before inserting, check `news:seen:{url_hash}` key to skip already-processed articles.

Install: `newsapi-python`, `feedparser`.

**Depends on:** Task 1.1

---

### Task 1.4 — SEC EDGAR filing fetcher

Create `app/tools/edgar_fetcher.py`. Implement:

- `fetch_filings(ticker: str, form_types: list[str], max_results: int) -> list[dict]` — queries the EDGAR EFTS full-text search API (`https://efts.sec.gov/LATEST/search-index?q={ticker}&dateRange=custom&...&forms={form_type}`) and returns a list of `{accession_no, filing_type, filing_date, document_url}` dicts. No API key required; set a descriptive `User-Agent` header as required by SEC.
- `fetch_filing_text(document_url: str) -> str` — fetches the raw filing text from `https://www.sec.gov/Archives/edgar/...` and strips HTML using `BeautifulSoup`.
- `get_cik_for_ticker(ticker: str) -> str` — looks up CIK from `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&ticker={ticker}&output=atom`.
- Respect rate limiting: use `asyncio.sleep(0.1)` between requests and handle 429 with exponential backoff.

Install: `httpx`, `beautifulsoup4`, `lxml`.

**Depends on:** Task 0.2

---

### Task 1.5 — Redis caching layer utilities

Create `app/tools/cache.py` as a centralized Redis utility module. Implement:

- `get_cache(key: str) -> str | None` — async Redis GET with JSON deserialization
- `set_cache(key: str, value: Any, ttl: int)` — async Redis SET with JSON serialization and EX ttl
- `delete_cache(key: str)` — async Redis DEL
- `rate_limit_check(api_name: str, max_calls: int, window_seconds: int) -> bool` — uses Redis INCR + EXPIRE to implement a sliding-window rate limiter. Returns `True` if call is allowed, `False` if limit exceeded.
- `build_key(*parts: str) -> str` — joins parts with `:` to form a namespaced Redis key

Use the async Redis client (`redis.asyncio`). Initialize the client once using the `REDIS_URL` from settings and expose it as a module-level singleton.

**Depends on:** Task 0.2, Task 0.4

---

## Phase 2 — Tool Library

**Goal:** Build the reusable tools that agents will call — technical indicators, sentiment scoring via Groq, SEC filing chunker and embedder, and a RAG retrieval function.

---

### Task 2.1 — Technical indicator calculator

Create `app/tools/indicators.py`. Implement:

- `calculate_indicators(df: pd.DataFrame) -> dict` — takes an OHLCV DataFrame from the price fetcher and returns a flat dict of indicator values:
  - `rsi_14`: RSI over 14 periods (from `pandas_ta`)
  - `macd_line`, `macd_signal`, `macd_hist`: MACD(12,26,9)
  - `bb_upper`, `bb_middle`, `bb_lower`: Bollinger Bands(20,2)
  - `sma_50`, `sma_200`: Simple moving averages
  - `atr_14`: Average True Range over 14 periods
  - `ema_20`: Exponential moving average
  - `volume_sma_20`: 20-day average volume
- `interpret_indicators(indicators: dict) -> dict` — adds human-readable signals:
  - `macd_signal_label`: `"bullish_crossover" | "bearish_crossover" | "neutral"`
  - `bb_position`: `"upper_band" | "lower_band" | "middle"`
  - `sma_cross`: `"golden_cross" | "death_cross" | "none"`
  - `rsi_zone`: `"overbought" | "oversold" | "neutral"`

All values should be rounded to 4 decimal places. Return `None` for any indicator that cannot be calculated (insufficient data).

Install: `pandas-ta`, `pandas`, `numpy`.

**Depends on:** Task 1.2

---

### Task 2.2 — Groq LLM client wrapper

Create `app/tools/llm.py` as a thin wrapper around the Groq Python SDK. Implement:

- `groq_complete(system_prompt: str, user_prompt: str, model: str = "llama-3.3-70b-versatile", max_tokens: int = 1024, temperature: float = 0.1) -> str` — makes a chat completion call, returns the response text. Handles `RateLimitError` with up to 3 retries using exponential backoff (1s, 2s, 4s).
- `groq_sentiment(text: str, ticker: str) -> dict` — system prompt instructs the model to return JSON `{"score": float, "label": "BULLISH|BEARISH|NEUTRAL", "reasoning": str}`. Parse and validate the JSON response; retry once if JSON is malformed.
- `groq_summarize(text: str, context: str, max_words: int = 200) -> str` — general-purpose summarization with a concise system prompt.
- `groq_synthesize_signal(research: dict, quant: dict, risk: dict) -> dict` — structured prompt that combines all sub-agent outputs and asks the model to return `{"signal": "BUY|SELL|HOLD", "confidence": float, "summary": str, "key_factors": list[str]}`.

All functions log their token usage to a module-level counter for monitoring.

Install: `groq`.

**Depends on:** Task 0.2

---

### Task 2.3 — SEC filing chunker and pgvector embedder

Create `app/tools/embedder.py`. Implement:

- `chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]` — splits text into overlapping token-approximate chunks using a simple word-count heuristic (1 token ≈ 0.75 words). Returns a list of chunk strings.
- `embed_chunks(chunks: list[str]) -> list[list[float]]` — loads `sentence-transformers/all-MiniLM-L6-v2` locally using the `sentence-transformers` library. Encodes all chunks in a single batch call. Returns list of 384-dim float vectors.
- `ingest_filing(ticker: str, filing_type: str, filing_date: str, accession_no: str, text: str, db: AsyncSession)` — orchestrates the full pipeline: chunk → embed → bulk insert into `filing_chunks`. Uses SQLAlchemy bulk insert; skip rows where `(ticker, accession_no, chunk_index)` already exists.
- `ingest_news_for_rag(article: dict, db: AsyncSession)` — same pipeline but for news articles; uses `filing_type='news'`.

Install: `sentence-transformers`, `pgvector`, `torch` (CPU-only: `torch==2.3.0+cpu`).

**Depends on:** Task 1.1, Task 1.4

---

### Task 2.4 — RAG retrieval tool

Create `app/tools/rag.py`. Implement:

- `retrieve_context(ticker: str, query: str, db: AsyncSession, top_k: int = 5, filing_types: list[str] | None = None) -> list[dict]` — embeds the query using the same `all-MiniLM-L6-v2` model, performs a pgvector cosine similarity search against `filing_chunks`, filters by `ticker` and optionally by `filing_type`, returns top-k results as `[{"chunk_text": str, "similarity": float, "filing_type": str, "filing_date": str}]`.

  SQL used:
  ```sql
  SELECT chunk_text, filing_type, filing_date,
         1 - (embedding <=> :query_vec) AS similarity
  FROM filing_chunks
  WHERE ticker = :ticker
  ORDER BY embedding <=> :query_vec
  LIMIT :top_k
  ```

- `format_context_for_prompt(results: list[dict]) -> str` — formats retrieved chunks into a numbered context block suitable for injection into a Groq prompt.
- `rag_answer(ticker: str, query: str, db: AsyncSession) -> dict` — full pipeline: retrieve → format → call `groq_complete()` with context injected → return `{"answer": str, "sources": list}`.

**Depends on:** Task 2.3, Task 2.2

---

## Phase 3 — Agent Implementation

**Goal:** Implement each of the four agents as standalone Celery tasks with clearly defined JSON input/output contracts. Each agent should be independently testable by sending it a raw JSON payload.

---

### Task 3.1 — Research Agent

Create `app/agents/research_agent.py`. Define a Celery task `run_research_agent` bound to the `agent.research` queue:

```python
@celery_app.task(bind=True, queue="agent.research", name="agents.research")
def run_research_agent(self, payload: dict) -> dict:
    ...
```

**Input schema** (validated with Pydantic):
```python
class ResearchInput(BaseModel):
    query_id: str
    ticker: str
    lookback_days: int = 7
```

**Pipeline inside the task:**
1. Call `fetch_news_newsapi(ticker, lookback_days)` + `fetch_news_rss(ticker)` → combine and deduplicate
2. Concatenate article headlines + snippets (truncated to 4000 chars)
3. Call `groq_sentiment(combined_text, ticker)` → sentiment score + label
4. Call `rag_answer(ticker, f"What are the main risks and opportunities for {ticker}?")` → SEC context
5. Call `groq_summarize(combined_text + rag_context, ...)` → narrative summary
6. Write result to `agent_run_logs` table (status, latency, input, output)
7. Return structured JSON matching `ResearchOutput` schema

Log the task's start/finish timestamps and compute latency. Handle exceptions by writing `status="error"` to the log and re-raising so Celery marks the task as failed.

**Depends on:** Task 1.3, Task 2.2, Task 2.4, Task 0.5, Task 1.1

---

### Task 3.2 — Quant Agent

Create `app/agents/quant_agent.py`. Define Celery task `run_quant_agent` on queue `agent.quant`.

**Input schema:**
```python
class QuantInput(BaseModel):
    query_id: str
    ticker: str
    interval: str = "1d"
    period: str = "6mo"
```

**Pipeline:**
1. Call `fetch_ohlcv(ticker, interval, period)` with Redis cache check (Task 1.2 / 1.5)
2. Call `calculate_indicators(df)` → raw indicator dict (Task 2.1)
3. Call `interpret_indicators(indicators)` → labeled signals
4. Determine `quant_signal`:
   - `BUY` if: RSI < 70 AND MACD bullish crossover AND close > SMA_50
   - `SELL` if: RSI > 70 OR MACD bearish crossover AND close < SMA_50
   - `HOLD` otherwise
5. Build `QuantOutput` with all indicator values + signal
6. Write to `agent_run_logs`
7. Return structured JSON

**Depends on:** Task 1.2, Task 2.1, Task 1.5, Task 0.5, Task 1.1

---

### Task 3.3 — Risk Agent

Create `app/agents/risk_agent.py`. Define Celery task `run_risk_agent` on queue `agent.risk`.

**Input schema:**
```python
class RiskInput(BaseModel):
    query_id: str
    ticker: str
    proposed_signal: str       # BUY | SELL | HOLD
    atr_14: float
    current_price: float
    confidence: float
```

**Pipeline:**
1. Fetch current portfolio state via Alpaca API (`GET /v2/account` and `GET /v2/positions`) — wrap in `app/tools/alpaca_client.py` (create this thin client here)
2. Run all guardrail checks (see SYSTEM_DESIGN.md §10):
   - Position concentration check
   - Open position count check
   - Drawdown check (compare portfolio equity to high-water mark stored in Redis `portfolio:hwm`)
   - Confidence threshold check
3. Calculate position size: `qty = floor((portfolio_value * 0.01) / (2 * atr_14))`; cap at 5% portfolio value
4. Calculate stop loss: `entry_price - 2 * atr_14`; take profit: `entry_price + 3 * atr_14`
5. Return `RiskOutput` with `decision`, `reason`, `suggested_qty`, `stop_loss`, `take_profit`
6. Write to `agent_run_logs`

**Depends on:** Task 0.2, Task 0.5, Task 1.1 (for logging)

---

### Task 3.4 — Execution Agent

Create `app/agents/execution_agent.py`. Define Celery task `run_execution_agent` on queue `agent.execution`.

**Input schema:**
```python
class ExecutionInput(BaseModel):
    query_id: str
    ticker: str
    action: str          # BUY | SELL
    qty: int
    stop_loss: float
    take_profit: float
    paper_mode: bool = True
```

**Pipeline:**
1. Assert `paper_mode is True` — raise `LiveTradingNotPermittedError` if False (safety gate)
2. Call Alpaca paper trading API `POST /v2/orders` with:
   - `symbol`, `qty`, `side`, `type="limit"` (use last price + 0.5% slippage as limit), `time_in_force="day"`
   - Attach stop-loss as a bracket order leg
3. Poll `GET /v2/orders/{order_id}` up to 5 times (2-second intervals) for fill status
4. Upsert result into `trades` table
5. Write to `agent_run_logs`
6. Return `ExecutionOutput` with `order_id`, `status`, `filled_price`, `timestamp`

Alpaca client lives in `app/tools/alpaca_client.py`. Use the `alpaca-trade-api` or `alpaca-py` library.

Install: `alpaca-py`.

**Depends on:** Task 0.2, Task 0.5, Task 1.1, Task 3.3

---

## Phase 4 — Orchestrator

**Goal:** Build the LangGraph state graph that routes work to sub-agents, aggregates results, and synthesizes the final signal + report.

---

### Task 4.1 — LangGraph state definition and graph skeleton

Create `app/agents/orchestrator.py`. Define the shared state TypedDict:

```python
class OrchestratorState(TypedDict):
    query_id: str
    ticker: str
    query_text: str
    mode: str
    research_result: ResearchOutput | None
    quant_result: QuantOutput | None
    risk_result: RiskOutput | None
    execution_result: ExecutionOutput | None
    final_signal: str | None
    confidence: float | None
    summary: str | None
    error: str | None
```

Define the graph using `StateGraph(OrchestratorState)`. Add nodes: `research_node`, `quant_node`, `risk_node`, `execution_node`, `synthesize_node`, `error_node`. Wire edges:
- `START → research_node` and `START → quant_node` (parallel fan-out)
- `research_node + quant_node → risk_node` (both must complete first; use `add_edge` with list)
- `risk_node → execution_node` (conditional: only if risk decision is PASS and mode includes execution)
- `execution_node → synthesize_node`
- `synthesize_node → END`

Compile the graph with `graph.compile()`.

Install: `langgraph`.

**Depends on:** Tasks 3.1–3.4

---

### Task 4.2 — Orchestrator node implementations

In `app/agents/orchestrator.py`, implement each node function. Each node function receives the full `OrchestratorState` and returns a partial state update dict.

- `research_node(state)` — calls `run_research_agent.apply_async(payload, queue="agent.research")`, blocks on `.get(timeout=120)`, returns `{"research_result": result}`
- `quant_node(state)` — same pattern for quant agent
- `risk_node(state)` — merges research + quant results into risk input, dispatches risk agent
- `execution_node(state)` — builds execution input from risk result, dispatches execution agent; skip if `mode == "signal_only"`
- `synthesize_node(state)` — calls `groq_synthesize_signal(research, quant, risk)` (Task 2.2), writes the complete signal row to `signals` table, returns final state
- `error_node(state)` — logs the error, returns `{"final_signal": "ERROR"}`

Add a conditional edge from `risk_node` using a router function:
```python
def route_after_risk(state) -> str:
    if state["risk_result"].decision == "BLOCK" or state["mode"] == "signal_only":
        return "synthesize_node"
    return "execution_node"
```

**Depends on:** Task 4.1, Task 2.2

---

### Task 4.3 — Orchestrator as a Celery task

Wrap the LangGraph orchestrator in a Celery task so it can be triggered from FastAPI via RabbitMQ.

Create `run_orchestrator` Celery task in `app/agents/orchestrator.py`:

```python
@celery_app.task(bind=True, queue="orchestrator.tasks", name="agents.orchestrator")
def run_orchestrator(self, payload: dict) -> dict:
    initial_state = OrchestratorState(**payload, research_result=None, ...)
    final_state = compiled_graph.invoke(initial_state)
    return final_state
```

Store the task result in Redis so FastAPI can poll it: `set_cache(f"result:{query_id}", final_state, ttl=3600)`.

Write an integration test in `tests/test_orchestrator.py` that mocks all four sub-agent Celery tasks (use `unittest.mock.patch`) and verifies the state graph routes correctly for both `PASS` and `BLOCK` risk outcomes.

**Depends on:** Tasks 4.1, 4.2, Task 0.5, Task 1.5

---

## Phase 5 — API Layer

**Goal:** Wire the orchestrator and data layer into a complete FastAPI application with proper request validation, async background dispatch, and response schemas.

---

### Task 5.1 — Pydantic v2 request and response schemas

Create `app/schemas/` with one file per domain:

- `app/schemas/analysis.py` — `AnalyzeRequest`, `AnalyzeResponse` (202 accepted), `AnalysisResult` (full async result)
- `app/schemas/signals.py` — `SignalResponse`
- `app/schemas/trades.py` — `TradeRequest`, `TradeResponse`
- `app/schemas/portfolio.py` — `PositionSchema`, `PortfolioResponse`
- `app/schemas/health.py` — `HealthResponse`

All schemas use Pydantic v2 (`model_config = ConfigDict(from_attributes=True)`). Add field validators where needed (e.g., ticker must be uppercase alphanumeric, qty must be positive). Include docstrings on each schema class.

**Depends on:** Tasks 3.1–3.4

---

### Task 5.2 — /analyze and /analysis/{query_id} routes

Create `app/api/routes/analysis.py`. Implement:

- `POST /analyze` — validates `AnalyzeRequest`, generates a UUID `query_id`, stores initial status in Redis (`analysis:{query_id}:status = "queued"`), publishes `run_orchestrator.apply_async(payload, queue="orchestrator.tasks")`, returns 202 with `query_id` and `poll_url`.
- `GET /analysis/{query_id}` — checks Redis for `result:{query_id}` (Task 4.3); if present, deserializes and returns full `AnalysisResult`; if not, returns `{"status": "pending"}` with 202; if Celery task shows failure, return 500 with error.

Use `AsyncSession` dependency injection via `Depends(get_db)`. Mount this router in `app/main.py` with prefix `/`.

**Depends on:** Task 5.1, Task 4.3, Task 0.4

---

### Task 5.3 — /signal and /portfolio routes

Create `app/api/routes/signals.py`:
- `GET /signal/{ticker}` — queries `signals` table for the most recent row with that ticker; returns `SignalResponse`. If no signal exists, returns 404.

Create `app/api/routes/portfolio.py`:
- `GET /portfolio` — calls `alpaca_client.get_account()` and `alpaca_client.get_positions()`, maps to `PortfolioResponse` schema, caches result in Redis for 60 seconds.

Mount both routers in `app/main.py`.

**Depends on:** Task 5.1, Task 3.3 (for alpaca_client), Task 1.5

---

### Task 5.4 — /trade route and manual order endpoint

Create `app/api/routes/trades.py`:
- `POST /trade` — validates `TradeRequest`, checks `PAPER_MODE` setting (return 403 if False), calls `run_execution_agent.apply_async(...)` synchronously (`.get(timeout=30)`), writes result to `trades` table, returns `TradeResponse` with order status.
- `GET /trades` — returns paginated list of all trades from `trades` table with optional `?ticker=` filter and `?limit=` / `?offset=` query params.

Add HTTP exception handlers for common errors: `AlpacaAPIError → 502`, `RateLimitError → 429`, `LiveTradingNotPermittedError → 403`.

**Depends on:** Task 5.1, Task 3.4, Task 1.1

---

### Task 5.5 — Request middleware and error handling

In `app/main.py`, add:

- A request timing middleware that logs method, path, status code, and latency using `structlog` on every request
- A global exception handler for unhandled exceptions that returns `{"error": "internal_server_error", "detail": str(e)}` with status 500 and logs the full traceback
- Request ID middleware: generate a UUID per request, attach to `request.state.request_id`, and include it in the response `X-Request-ID` header

Install: `structlog`.

**Depends on:** Task 0.4

---

## Phase 6 — Paper Trading Loop

**Goal:** Implement the full signal-to-order pipeline with Alpaca, a portfolio state tracker, and end-of-day P&L logging.

---

### Task 6.1 — Alpaca client wrapper

Create `app/tools/alpaca_client.py` as a comprehensive wrapper around `alpaca-py`. Implement:

- `get_account() -> dict` — returns account equity, buying power, portfolio value
- `get_positions() -> list[dict]` — returns all open positions with `ticker, qty, avg_entry, current_price, unrealized_pnl`
- `place_order(ticker, action, qty, limit_price, stop_loss) -> dict` — places a bracket order (limit + stop-loss leg), returns order dict
- `get_order(order_id) -> dict` — fetches order status and fill details
- `cancel_order(order_id) -> bool`
- `close_position(ticker) -> dict` — market-close a position

All methods use the Alpaca paper trading base URL from `settings.ALPACA_BASE_URL`. Raise a custom `AlpacaAPIError` on non-2xx responses. Log all API calls with ticker, action, and response status.

**Depends on:** Task 0.2

---

### Task 6.2 — Portfolio tracker

Create `app/tools/portfolio_tracker.py`. Implement:

- `get_portfolio_snapshot() -> PortfolioSnapshot` — calls `alpaca_client.get_account()` and `get_positions()`, returns a dataclass with total value, cash, positions list, and daily P&L
- `update_high_water_mark(portfolio_value: float)` — reads `portfolio:hwm` from Redis; if current value > HWM, update it. Used by the risk agent for drawdown checks.
- `calculate_drawdown(portfolio_value: float) -> float` — returns `(hwm - current_value) / hwm` as a fraction
- `log_daily_pnl(db: AsyncSession)` — called at EOD; records a summary row to `agent_run_logs` with `agent_name="portfolio_tracker"` and the day's P&L in `task_output`

**Depends on:** Task 6.1, Task 1.5, Task 1.1

---

### Task 6.3 — Scheduled daily analysis pipeline (Celery Beat)

Add Celery Beat scheduling to `app/celery_app.py`. Define a beat schedule that:

- Runs `daily_watchlist_analysis` every weekday at 9:35 AM ET (after market open)
- Runs `log_daily_pnl` every weekday at 4:05 PM ET (after market close)

Create `app/agents/scheduled_tasks.py`:
- `daily_watchlist_analysis()` — reads all active tickers from `stocks_watchlist`, dispatches a `run_orchestrator` task per ticker with `mode="full_analysis"`, logs the batch run
- `end_of_day_pnl_log()` — calls `portfolio_tracker.log_daily_pnl()`

Configure with `celery_app.conf.beat_schedule = {...}` and `timezone = "America/New_York"`.

Install: `celery[redis]` (for beat scheduler persistence).

**Depends on:** Task 4.3, Task 6.2, Task 0.5

---

### Task 6.4 — Signal-to-order integration test

Create `tests/test_signal_to_order.py`. Write an end-to-end integration test (using Alpaca paper sandbox credentials) that:

1. Triggers `POST /analyze` for AAPL with mode `full_analysis`
2. Polls `GET /analysis/{query_id}` every 5 seconds until status is complete or timeout (60s)
3. Asserts the response contains a valid `final_signal` (BUY/SELL/HOLD)
4. If signal is BUY, calls `POST /trade` with qty=1 and asserts the response status is `accepted` or `filled`
5. Calls `GET /portfolio` and asserts AAPL appears in positions (or that the trade was recorded in the `trades` table)

This test requires a running Docker Compose stack and real Alpaca paper credentials. Mark it with `@pytest.mark.integration` so it's excluded from CI by default.

**Depends on:** Tasks 5.2, 5.4, 6.1

---

## Phase 7 — Observability & Hardening

**Goal:** Add structured logging throughout, a full agent audit trail, retry logic, rate-limit handling, and basic alerting so the system is production-ready for paper trading.

---

### Task 7.1 — Structured logging with structlog

Configure `structlog` in a new `app/logging_config.py` module. Set up:

- JSON renderer for production (`LOG_LEVEL=INFO`), colored console renderer for development
- Bind `request_id`, `ticker`, `agent_name`, and `query_id` to the logger context wherever available
- Wrap all Celery task functions with a `@log_agent_task` decorator that automatically logs task start (with input payload) and task finish (with output summary and latency_ms)
- Replace all existing `print()` statements in agent files with structured log calls

Import and initialize the logging config in `app/main.py` startup and in `app/celery_app.py`.

**Depends on:** Tasks 3.1–3.4, Task 0.4

---

### Task 7.2 — Retry logic and error resilience

Add retry logic to all external API calls:

- In `app/tools/llm.py`: wrap `groq_complete()` with a retry decorator using `tenacity` — `retry=retry_if_exception_type(RateLimitError)`, `wait=wait_exponential(multiplier=1, min=1, max=16)`, `stop=stop_after_attempt(4)`
- In `app/tools/price_fetcher.py`: add `@retry` on `fetch_ohlcv()` with same pattern, catching `yfinance` connection errors
- In `app/tools/alpaca_client.py`: add retry on 5xx responses only (not 4xx); wrap `place_order()` with idempotency check (look up `correlation_id` in `trades` table before placing)
- In Celery task definitions: set `max_retries=3`, `default_retry_delay=10` on all agent tasks; call `self.retry(exc=exc, countdown=10)` in the except block

Install: `tenacity`.

**Depends on:** Tasks 3.1–3.4, Task 6.1, Task 2.2

---

### Task 7.3 — Agent run audit trail in PostgreSQL

Ensure the `agent_run_logs` table is written consistently across all agents. Create `app/db/audit.py`:

- `write_agent_log(db, query_id, agent_name, task_input, task_output, status, error_message, started_at, finished_at)` — single async function that inserts a row into `agent_run_logs`. All agent tasks must call this at the end of their execution (both success and failure paths).
- `get_agent_logs_for_query(db, query_id) -> list[AgentRunLog]` — retrieves all log rows for a given query_id, ordered by `started_at`

Add a new FastAPI route `GET /query/{query_id}/logs` that returns the full agent run trail for debugging — include input/output payloads, latency, and status for each agent.

**Depends on:** Tasks 3.1–3.4, Task 1.1, Task 5.3

---

### Task 7.4 — Rate limit handling and API health monitoring

Create `app/tools/rate_limiter.py` with per-API rate limit configs:

```python
RATE_LIMITS = {
    "newsapi": {"max_calls": 90, "window_seconds": 3600},
    "edgar": {"max_calls": 9, "window_seconds": 1},
    "groq": {"max_calls": 30, "window_seconds": 60},
    "alpaca": {"max_calls": 190, "window_seconds": 60},
    "yfinance": {"max_calls": 1900, "window_seconds": 3600},
}
```

Wrap all external API calls with a check to `rate_limit_check(api_name, ...)` from `app/tools/cache.py` (Task 1.5). If the limit is exceeded, raise a `RateLimitExceeded` exception that Celery will catch and retry with exponential backoff.

Add a `GET /health/apis` endpoint that shows current rate-limit counter values for each API from Redis so operators can see usage at a glance.

**Depends on:** Task 1.5, Tasks 3.1–3.4

---

### Task 7.5 — Dead letter queue consumer and alerting

Create `app/workers/dlq_consumer.py` — a Celery task that consumes from the `dead_letter.failed_tasks` queue:

- Logs the failed message details (task name, query_id, error, retry_count) to `agent_run_logs` with `status="dead_letter"`
- If a task has failed more than once for the same ticker in the last hour, write an alert row to a new `alerts` table (`CREATE TABLE alerts (id SERIAL PRIMARY KEY, alert_type VARCHAR(64), message TEXT, created_at TIMESTAMPTZ DEFAULT NOW())`)
- Provides a `GET /alerts` FastAPI endpoint returning recent alerts

Also add a simple watchdog: create a Celery Beat task `check_orchestrator_health` that runs every 5 minutes, checks if any `agent_run_logs` row has been stuck in `status="started"` for more than 10 minutes, and writes an alert if found.

**Depends on:** Task 0.5, Task 1.1, Task 7.1

---

## Phase 8 — Frontend Dashboard (Optional)

**Goal:** A React dashboard that displays the watchlist, latest signals, portfolio performance, and agent run history. Connects to the FastAPI backend.

---

### Task 8.1 — React project setup

Bootstrap a React 18 + TypeScript project inside `frontend/` using Vite (`npm create vite@latest frontend -- --template react-ts`). Install:
- `@tanstack/react-query` for data fetching and caching
- `recharts` for charts
- `tailwindcss` for styling
- `axios` for HTTP

Create `frontend/src/api/client.ts` with an `axios` instance pointing to `http://localhost:8000`. Create typed API functions for each FastAPI endpoint: `analyzeStock`, `getSignal`, `getPortfolio`, `getTrades`, `getAnalysisResult`.

Configure Vite proxy in `vite.config.ts` to forward `/api` requests to `localhost:8000` in development.

**Depends on:** Phase 5 (all routes must be implemented)

---

### Task 8.2 — Watchlist and signal cards

Create `frontend/src/components/WatchlistPanel.tsx`. Implement:

- Fetches the active watchlist from `GET /watchlist` (add this endpoint to FastAPI: reads `stocks_watchlist` table)
- For each ticker, shows the latest signal badge (`BUY` = green, `SELL` = red, `HOLD` = yellow), confidence score, and a "Run Analysis" button
- Clicking "Run Analysis" calls `POST /analyze` and shows a loading spinner while polling `GET /analysis/{query_id}` every 3 seconds
- When analysis completes, updates the signal badge in place and shows a toast with the summary

Use `useQuery` from React Query for the watchlist fetch (30-second refetch interval) and `useMutation` for triggering analysis.

**Depends on:** Task 8.1, Task 5.2, Task 5.3

---

### Task 8.3 — Portfolio performance chart

Create `frontend/src/components/PortfolioPanel.tsx`. Implement:

- Calls `GET /portfolio` (60-second auto-refresh via React Query)
- Shows total portfolio value, cash available, and daily P&L (color-coded positive/negative)
- A `recharts` `AreaChart` showing equity curve over time — fetch historical P&L data from `agent_run_logs` where `agent_name="portfolio_tracker"` (add a `GET /portfolio/history` endpoint to FastAPI)
- A positions table with columns: Ticker, Qty, Avg Entry, Current Price, Unrealized P&L, P&L %

**Depends on:** Task 8.1, Task 5.3, Task 6.2

---

### Task 8.4 — Agent run history viewer

Create `frontend/src/components/AgentRunHistory.tsx`. Implement:

- Calls `GET /query/{query_id}/logs` to show the full agent audit trail for a selected query
- Timeline view showing each agent (Research → Quant → Risk → Execution → Synthesize) with:
  - Status indicator (success = green checkmark, error = red X, blocked = orange)
  - Latency bar
  - Expandable JSON accordion showing the raw `task_input` and `task_output`
- A global `GET /runs` endpoint (add to FastAPI: recent `agent_run_logs` grouped by `query_id`, last 50 queries) populates a sidebar list where clicking a query loads its full trace

**Depends on:** Task 8.1, Task 7.3

---

### Task 8.5 — Docker Compose integration for frontend

Add a `frontend` service to `docker-compose.yml`:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  ports:
    - "5173:5173"
  environment:
    - VITE_API_URL=http://localhost:8000
  depends_on:
    - app
```

Create `frontend/Dockerfile` using a multi-stage build: Node 20 Alpine for build, Nginx for serving the production bundle. Create `frontend/nginx.conf` that proxies `/api` to the FastAPI container.

Also add an `app` service to `docker-compose.yml` for the FastAPI server itself (Python 3.11 slim, runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`), a `worker` service for Celery workers, and a `beat` service for Celery Beat.

**Depends on:** Tasks 8.1–8.4, Task 0.3

---

## Appendix: Dependency Summary

| Phase | Key External Dependencies |
|---|---|
| 0 | fastapi, uvicorn, pydantic-settings, celery, redis, sqlalchemy, asyncpg |
| 1 | yfinance, newsapi-python, feedparser, httpx, beautifulsoup4, alembic, pgvector |
| 2 | pandas-ta, groq, sentence-transformers, torch (CPU) |
| 3 | langgraph (imported in Phase 4, agents in Phase 3) |
| 4 | langgraph |
| 5 | (no new dependencies) |
| 6 | alpaca-py |
| 7 | tenacity, structlog |
| 8 | React 18, Vite, TailwindCSS, Recharts, Tanstack Query |
