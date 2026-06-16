# Agentic Stock Market AI — System Design

---

## 1. Project Overview

### What It Does

An autonomous, multi-agent AI system that ingests market data, news, and SEC filings, performs quantitative and qualitative analysis, generates trading signals, and executes paper trades — all driven by natural language queries or a scheduled pipeline.

### Goals

- Accept a ticker or natural language query ("Is NVDA a buy this week?") and return a structured signal with justification
- Automate the full research → analysis → risk-check → execution loop via coordinated AI agents
- Maintain a live portfolio in Alpaca paper trading with end-of-day P&L tracking
- Support RAG-based reasoning over SEC filings and news with source attribution
- Provide a full audit trail of every agent decision

### Non-Goals

- **No live/real-money trading** — paper trading only in this system
- **No proprietary data feeds** — only public APIs (yfinance, NewsAPI, EDGAR)
- **No high-frequency trading** — signals are generated on minute-to-daily timeframes
- **No cross-exchange arbitrage** — single US equity market scope
- **No financial advice** — output is educational and research-oriented only

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Gateway                          │
│         POST /analyze  │  GET /signal  │  POST /trade           │
└─────────────────────────────┬───────────────────────────────────┘
                              │ publishes task
                              ▼
                    ┌─────────────────┐
                    │   RabbitMQ      │  (task dispatch bus)
                    └────────┬────────┘
                             │ consumes
                             ▼
                 ┌───────────────────────┐
                 │   LangGraph           │
                 │   Orchestrator Agent  │  (Celery worker)
                 └──┬──────┬──────┬─────┘
                    │      │      │
          ┌─────────┘  ┌───┘  ┌───┘
          ▼            ▼      ▼      ▼
   ┌──────────┐ ┌────────┐ ┌──────┐ ┌───────────┐
   │ Research │ │ Quant  │ │ Risk │ │ Execution │
   │  Agent   │ │ Agent  │ │Agent │ │  Agent    │
   └────┬─────┘ └───┬────┘ └──┬───┘ └─────┬─────┘
        │           │         │           │
        ▼           ▼         ▼           ▼
   ┌──────────────────────────────────────────┐
   │            Tool Layer                    │
   │  yfinance │ pandas-ta │ pgvector RAG     │
   │  Groq LLM │ NewsAPI   │ Alpaca API       │
   └──────────────────────────────────────────┘
        │           │         │           │
        ▼           ▼         ▼           ▼
   ┌──────────────────────────────────────────┐
   │           Data Layer                     │
   │  PostgreSQL (+ pgvector) │ Redis Cache   │
   └──────────────────────────────────────────┘
```

### Multi-Agent Design Philosophy

Each agent is a single-responsibility Celery worker with a defined JSON contract. The LangGraph orchestrator holds the state graph, routes tasks, waits for agent results, and synthesizes the final output. Agents do not communicate with each other directly — all coordination passes through the orchestrator.

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API server | FastAPI 0.111 | HTTP gateway, request validation, background dispatch |
| Task queue | Celery 5.x + RabbitMQ 3.x | Async agent worker dispatch |
| Message broker | RabbitMQ | Durable task routing between orchestrator and agents |
| Agent orchestration | LangGraph 0.2 | Stateful multi-agent graph with conditional routing |
| LLM inference | Groq (llama-3.3-70b-versatile) | Fast LLM calls for summarization, sentiment, synthesis |
| Market data | yfinance | OHLCV price history, fundamentals |
| Technical analysis | pandas-ta | RSI, MACD, Bollinger Bands, SMA, EMA, ATR |
| News ingestion | NewsAPI + feedparser (RSS) | News articles for sentiment |
| SEC filings | EDGAR EFTS full-text search API | 10-K, 10-Q, 8-K filings |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Local embedding for RAG |
| Vector store | pgvector (PostgreSQL extension) | Embedding storage and ANN retrieval |
| Relational DB | PostgreSQL 16 | All structured data, audit logs |
| Cache | Redis 7 | Price cache, rate-limit counters, deduplication |
| Paper trading | Alpaca Trade API v2 | Order placement, portfolio state |
| Validation | Pydantic v2 | Request/response schemas |
| Migrations | Alembic | DB schema versioning |
| Containerization | Docker Compose | Local dev environment |
| Observability | structlog + PostgreSQL audit table | Structured logs, agent run history |

---

## 4. Agent Definitions

### 4.1 Orchestrator (LangGraph)

**Responsibility:** Receives the parsed user request, constructs the execution graph, dispatches tasks to sub-agents via Celery, collects results, and synthesizes the final signal + report.

**Inputs:**
```json
{
  "query_id": "uuid",
  "ticker": "NVDA",
  "query_text": "Is NVDA a buy this week?",
  "mode": "full_analysis | signal_only | risk_check"
}
```

**Outputs:**
```json
{
  "query_id": "uuid",
  "ticker": "NVDA",
  "final_signal": "BUY | SELL | HOLD",
  "confidence": 0.78,
  "summary": "...",
  "sub_reports": { "research": {...}, "quant": {...}, "risk": {...} },
  "execution_result": {...}
}
```

**Graph nodes:** `start → research → quant → risk → [execute | hold] → synthesize → end`

**Conditional edges:**
- If risk agent returns `BLOCK`, skip execution node
- If confidence < 0.5, route to `hold` instead of `execute`

---

### 4.2 Research Agent

**Responsibility:** Gathers and interprets qualitative information about a ticker — news sentiment, SEC filing summaries, analyst narrative.

**Inputs:**
```json
{ "ticker": "NVDA", "lookback_days": 7 }
```

**Outputs:**
```json
{
  "sentiment_score": 0.65,
  "sentiment_label": "BULLISH",
  "news_summary": "...",
  "filing_summary": "...",
  "sources": ["url1", "url2"],
  "key_risks": ["export controls", "inventory correction"]
}
```

**Tools called:**
- `fetch_news(ticker, days)` → NewsAPI + RSS
- `rag_retrieve(ticker, query)` → pgvector similarity search on EDGAR chunks
- `groq_summarize(text)` → LLM call for narrative synthesis
- `groq_sentiment(text)` → LLM call for sentiment scoring

---

### 4.3 Quant Agent

**Responsibility:** Computes technical indicators from price data and generates a quantitative signal.

**Inputs:**
```json
{ "ticker": "NVDA", "interval": "1d", "period": "6mo" }
```

**Outputs:**
```json
{
  "quant_signal": "BUY",
  "indicators": {
    "rsi_14": 58.3,
    "macd_signal": "bullish_crossover",
    "bb_position": "lower_band",
    "sma_50_200_cross": "golden_cross",
    "atr_14": 12.4
  },
  "price_data_snapshot": { "close": 875.2, "volume": 42000000 }
}
```

**Tools called:**
- `fetch_ohlcv(ticker, interval, period)` → yfinance
- `calculate_indicators(df)` → pandas-ta pipeline
- `check_redis_cache(key)` / `set_redis_cache(key, value, ttl)` → cache OHLCV

---

### 4.4 Risk Agent

**Responsibility:** Validates the proposed trade against portfolio risk rules and returns a PASS/BLOCK decision with position sizing.

**Inputs:**
```json
{
  "ticker": "NVDA",
  "proposed_signal": "BUY",
  "portfolio_state": { "total_value": 100000, "positions": {...} },
  "atr_14": 12.4
}
```

**Outputs:**
```json
{
  "decision": "PASS | BLOCK",
  "reason": "...",
  "suggested_qty": 10,
  "suggested_stop_loss": 850.0,
  "suggested_take_profit": 920.0,
  "position_size_pct": 0.05
}
```

**Rules enforced:**
- Max 5% of portfolio in any single position
- Max 20% drawdown from portfolio peak triggers full halt
- ATR-based stop loss (2× ATR below entry)
- No more than 10 open positions simultaneously

**Tools called:**
- `get_portfolio_state()` → Alpaca API
- `calculate_position_size(portfolio_value, atr, risk_pct)` → internal rule engine

---

### 4.5 Execution Agent

**Responsibility:** Places paper trades on Alpaca and records the order in the database.

**Inputs:**
```json
{
  "ticker": "NVDA",
  "action": "BUY",
  "qty": 10,
  "stop_loss": 850.0,
  "take_profit": 920.0,
  "paper_mode": true
}
```

**Outputs:**
```json
{
  "order_id": "alpaca-uuid",
  "status": "accepted | rejected | filled",
  "filled_price": 876.5,
  "timestamp": "2026-06-12T14:32:00Z"
}
```

**Tools called:**
- `alpaca_place_order(...)` → Alpaca paper trading REST API
- `db_insert_trade(...)` → write to `trades` table
- `alpaca_get_order_status(order_id)` → poll for fill confirmation

---

## 5. Data Flow

```
User Request (POST /analyze)
  │
  ▼
FastAPI validates request (Pydantic v2)
  │
  ▼
Publishes AnalysisTask message to RabbitMQ
  │
  ▼
Orchestrator Celery worker picks up task
  │
  ├──► Dispatch ResearchTask → Research Agent worker
  │         └─ fetch_news() + rag_retrieve() + groq_summarize()
  │         └─ Returns research_report JSON
  │
  ├──► Dispatch QuantTask → Quant Agent worker
  │         └─ fetch_ohlcv() → calculate_indicators()
  │         └─ Returns quant_report JSON
  │
  ▼ (both complete)
Orchestrator merges results
  │
  ├──► Dispatch RiskTask → Risk Agent worker
  │         └─ evaluate rules against quant + portfolio state
  │         └─ Returns risk_decision JSON
  │
  ▼
  ├── If BLOCK → signal = HOLD, skip execution
  │
  └── If PASS →
        ├──► Dispatch ExecutionTask → Execution Agent worker
        │         └─ alpaca_place_order()
        │         └─ db_insert_trade()
        │         └─ Returns execution_result JSON
        │
        ▼
Orchestrator calls groq_synthesize(all_reports)
  │
  ▼
Writes final signal + all sub-reports to agent_run_logs
  │
  ▼
FastAPI returns AnalysisResponse to caller
```

---

## 6. Database Schema

All tables in PostgreSQL 16. pgvector extension enabled on the same database.

```sql
-- Watchlist of tracked tickers
CREATE TABLE stocks_watchlist (
    id          SERIAL PRIMARY KEY,
    ticker      VARCHAR(10) NOT NULL UNIQUE,
    company     TEXT,
    sector      TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

-- OHLCV snapshots (daily)
CREATE TABLE price_snapshots (
    id          BIGSERIAL PRIMARY KEY,
    ticker      VARCHAR(10) NOT NULL,
    snapshot_date DATE NOT NULL,
    open        NUMERIC(12,4),
    high        NUMERIC(12,4),
    low         NUMERIC(12,4),
    close       NUMERIC(12,4),
    volume      BIGINT,
    source      VARCHAR(32) DEFAULT 'yfinance',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, snapshot_date)
);
CREATE INDEX ON price_snapshots (ticker, snapshot_date DESC);

-- Agent-generated signals
CREATE TABLE signals (
    id              BIGSERIAL PRIMARY KEY,
    query_id        UUID NOT NULL,
    ticker          VARCHAR(10) NOT NULL,
    signal          VARCHAR(8) NOT NULL,   -- BUY | SELL | HOLD
    confidence      NUMERIC(4,3),
    quant_signal    VARCHAR(8),
    sentiment_score NUMERIC(4,3),
    risk_decision   VARCHAR(8),
    summary         TEXT,
    raw_output      JSONB,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON signals (ticker, generated_at DESC);

-- Full audit log for every agent invocation
CREATE TABLE agent_run_logs (
    id              BIGSERIAL PRIMARY KEY,
    query_id        UUID NOT NULL,
    agent_name      VARCHAR(32) NOT NULL,
    task_input      JSONB,
    task_output     JSONB,
    status          VARCHAR(16) NOT NULL,  -- success | error | blocked
    error_message   TEXT,
    latency_ms      INTEGER,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);
CREATE INDEX ON agent_run_logs (query_id);
CREATE INDEX ON agent_run_logs (agent_name, started_at DESC);

-- News articles ingested
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
);
CREATE INDEX ON news_articles (ticker, published_at DESC);

-- SEC EDGAR filings and their vector chunks
CREATE TABLE filing_chunks (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    filing_type     VARCHAR(16),           -- 10-K, 10-Q, 8-K
    filing_date     DATE,
    accession_no    VARCHAR(32),
    chunk_index     INTEGER,
    chunk_text      TEXT NOT NULL,
    embedding       VECTOR(384),           -- all-MiniLM-L6-v2 dimensions
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON filing_chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON filing_chunks (ticker, filing_date DESC);

-- Paper trades placed via Alpaca
CREATE TABLE trades (
    id              BIGSERIAL PRIMARY KEY,
    query_id        UUID,
    alpaca_order_id TEXT UNIQUE,
    ticker          VARCHAR(10) NOT NULL,
    action          VARCHAR(8) NOT NULL,   -- BUY | SELL
    qty             INTEGER NOT NULL,
    submitted_price NUMERIC(12,4),
    filled_price    NUMERIC(12,4),
    stop_loss       NUMERIC(12,4),
    take_profit     NUMERIC(12,4),
    status          VARCHAR(16),           -- accepted | filled | cancelled | rejected
    paper_mode      BOOLEAN DEFAULT TRUE,
    submitted_at    TIMESTAMPTZ DEFAULT NOW(),
    filled_at       TIMESTAMPTZ
);
CREATE INDEX ON trades (ticker, submitted_at DESC);
```

---

## 7. API Contracts

### POST /analyze

Trigger a full multi-agent analysis for a ticker.

**Request:**
```json
{
  "ticker": "NVDA",
  "query_text": "Is NVDA a buy this week?",
  "mode": "full_analysis"
}
```

**Response (202 Accepted):**
```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "poll_url": "/analysis/550e8400-e29b-41d4-a716-446655440000"
}
```

**Async result (GET /analysis/{query_id}):**
```json
{
  "query_id": "...",
  "ticker": "NVDA",
  "final_signal": "BUY",
  "confidence": 0.78,
  "summary": "NVDA shows bullish momentum...",
  "sub_reports": {
    "research": { "sentiment_score": 0.65, "news_summary": "..." },
    "quant": { "rsi_14": 58.3, "macd_signal": "bullish_crossover" },
    "risk": { "decision": "PASS", "suggested_qty": 10 }
  },
  "execution_result": { "order_id": "...", "status": "filled" },
  "generated_at": "2026-06-12T14:35:00Z"
}
```

---

### GET /signal/{ticker}

Returns the most recent cached signal for a ticker.

**Response (200):**
```json
{
  "ticker": "NVDA",
  "signal": "BUY",
  "confidence": 0.78,
  "generated_at": "2026-06-12T14:35:00Z",
  "summary": "..."
}
```

---

### POST /trade

Manually place a paper trade (bypasses agent pipeline).

**Request:**
```json
{
  "ticker": "NVDA",
  "action": "BUY",
  "qty": 5,
  "paper_mode": true
}
```

**Response (201):**
```json
{
  "trade_id": 42,
  "alpaca_order_id": "...",
  "status": "accepted"
}
```

---

### GET /portfolio

Returns current Alpaca paper portfolio state.

**Response (200):**
```json
{
  "total_value": 102340.50,
  "cash": 45200.00,
  "positions": [
    {
      "ticker": "NVDA",
      "qty": 10,
      "avg_entry": 876.5,
      "current_price": 902.1,
      "unrealized_pnl": 256.00,
      "unrealized_pnl_pct": 0.029
    }
  ],
  "daily_pnl": 812.00,
  "as_of": "2026-06-12T16:00:00Z"
}
```

---

### GET /health

```json
{ "status": "ok", "db": "ok", "redis": "ok", "rabbitmq": "ok" }
```

---

## 8. Message Queue Design

### RabbitMQ Topology

```
Exchange: stock.orchestrator   (type: direct, durable)
Exchange: stock.agents         (type: direct, durable)
Exchange: stock.dead_letter    (type: fanout, durable)

Queues:
  orchestrator.tasks          routing_key: orchestrate
  agent.research              routing_key: research
  agent.quant                 routing_key: quant
  agent.risk                  routing_key: risk
  agent.execution             routing_key: execute
  dead_letter.failed_tasks    (DLX for all agent queues)
```

### Message Envelope

```json
{
  "task_id": "uuid",
  "query_id": "uuid",
  "agent": "research | quant | risk | execution",
  "payload": { ... },
  "retry_count": 0,
  "max_retries": 3,
  "published_at": "2026-06-12T14:32:00Z",
  "correlation_id": "uuid"
}
```

### Flow

1. FastAPI publishes to `stock.orchestrator` with routing key `orchestrate`
2. Orchestrator worker consumes, fans out sub-tasks to `stock.agents` exchange with per-agent routing keys
3. Each agent worker consumes its dedicated queue, processes, and publishes result back to orchestrator via a reply queue (Celery result backend in Redis)
4. On failure after max retries, message is routed to `dead_letter.failed_tasks` for manual inspection

---

## 9. RAG Pipeline

### Ingestion

```
SEC EDGAR API
  └── Fetch 10-K/10-Q/8-K filing text for ticker
        └── Clean and strip HTML/XBRL markup
              └── Chunk text (512 tokens, 64-token overlap)
                    └── Embed each chunk (all-MiniLM-L6-v2, 384-dim)
                          └── Upsert into filing_chunks table
                                (ticker, filing_type, filing_date,
                                 chunk_index, chunk_text, embedding)
```

### Retrieval (at query time)

```python
query_text = f"What are the main risks for {ticker}?"
query_embedding = embedder.encode(query_text)   # 384-dim vector

# pgvector ANN search
results = db.execute("""
    SELECT chunk_text, filing_type, filing_date,
           1 - (embedding <=> :qvec) AS similarity
    FROM filing_chunks
    WHERE ticker = :ticker
    ORDER BY embedding <=> :qvec
    LIMIT 5
""", {"qvec": query_embedding, "ticker": ticker})
```

### Context Injection

The top-5 chunks are concatenated and injected into the Groq prompt:

```
You are a financial analyst. Use the following SEC filing excerpts for {ticker}
to answer the question: "{query}"

--- CONTEXT ---
{chunk_1_text}
...
{chunk_5_text}
--- END CONTEXT ---
```

### News Embeddings

News articles undergo the same pipeline (chunk → embed → store in `filing_chunks` with `filing_type='news'`) so both SEC filings and news share a single RAG retrieval path.

---

## 10. Risk & Guardrails

### Position Sizing (Kelly-inspired, capped)

```
risk_per_trade = 0.01 × portfolio_value          (1% risk per trade)
stop_distance  = 2 × ATR_14
qty            = floor(risk_per_trade / stop_distance)
position_cap   = floor(0.05 × portfolio_value / current_price)
final_qty      = min(qty, position_cap)
```

### Hard Guardrails

| Rule | Threshold | Action |
|---|---|---|
| Max single position | 5% of portfolio | Risk agent BLOCK |
| Max open positions | 10 concurrent | Risk agent BLOCK |
| Portfolio drawdown | 20% from peak | Halt all new trades |
| Daily loss limit | 5% of portfolio | Halt until next day |
| Confidence threshold | < 0.5 | Force HOLD, no execution |
| Paper-only flag | `PAPER_MODE=true` in env | Execution agent refuses live API |

### Paper-Only Mode

`PAPER_MODE` is read from environment. The Execution Agent checks this flag before every order. If `PAPER_MODE=false` is detected in a non-explicitly-approved environment, the agent raises a `LiveTradingNotPermittedError` and halts.

---

## 11. Scalability Notes

### Worker Scaling

- Each agent type is an independent Celery worker pool — scale them independently via Docker Compose replicas or Kubernetes HPA
- Research and Quant agents are stateless; spin up N replicas freely
- Execution agent should have exactly 1 replica per environment to avoid duplicate orders

### API Rate Limiting

| API | Limit | Strategy |
|---|---|---|
| yfinance | Unofficial; ~2000 req/hr | Redis counter + exponential backoff |
| NewsAPI | 100 req/day (free), 500/day (paid) | Cache all results 15 min in Redis |
| EDGAR EFTS | 10 req/sec | Token bucket in Redis |
| Groq | Varies by tier | Retry with 429 handling + jitter |
| Alpaca | 200 req/min | Redis rate-limit middleware |

### Redis Caching Strategy

| Data | Cache Key | TTL |
|---|---|---|
| OHLCV (daily) | `ohlcv:{ticker}:{date}` | 24h |
| OHLCV (intraday) | `ohlcv:{ticker}:{interval}` | 5 min |
| Indicators | `indicators:{ticker}:{date}` | 1h |
| News sentiment | `sentiment:{ticker}` | 30 min |
| Latest signal | `signal:{ticker}` | 15 min |
| Portfolio state | `portfolio:alpaca` | 60 sec |

### Database Scaling

- `price_snapshots` and `agent_run_logs` are append-only; partition by month after 6 months of data
- Add read replica for reporting queries (portfolio dashboard) vs write-primary for agent writes
- `filing_chunks` embedding index: use `ivfflat` with `lists=100` for up to ~1M chunks; migrate to `hnsw` beyond that
