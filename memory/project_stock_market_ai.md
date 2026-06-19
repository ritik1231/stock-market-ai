---
name: project-stock-market-ai
description: Phase progress, key files, and design decisions for the agentic stock market AI system
metadata:
  type: project
---

Agentic trading system: FastAPI + Celery + LangGraph + PostgreSQL/pgvector + Groq LLM. Educational/paper-trading only.

**Why:** Multi-phase build plan tracked in PHASES.md; always check there before implementing.

**How to apply:** Use phase progress below to know what's done and what to build next.

## Phase progress (as of 2026-06-20)
- Phase 0 ✅ Scaffold (FastAPI, Docker Compose, Celery, Alembic)
- Phase 1 ✅ Data layer (price/news/EDGAR fetchers, DB models, Redis cache)
- Phase 2 ✅ Tool library (indicators, Groq LLM wrapper, embedder, RAG)
- Phase 3 ✅ Agents (Research, Quant, Risk, Execution — all Celery tasks)
- Phase 4 ✅ LangGraph orchestrator — `app/agents/orchestrator.py`
- Phase 5 ⬜ API routes (FastAPI endpoints for analyze, signals, portfolio, trades)
- Phase 6 ⬜ Paper trading loop + Celery Beat scheduler
- Phase 7 ⬜ Observability, retry logic, rate limiting, DLQ consumer
- Phase 8 ⬜ React frontend (optional)

## Key files
- `app/agents/orchestrator.py` — `OrchestratorState` TypedDict, `compiled_graph`, `run_orchestrator` Celery task
- `app/agents/{research,quant,risk,execution}_agent.py` — individual Celery agent tasks
- `app/tools/llm.py` — `groq_synthesize_signal`, `groq_sentiment`, `groq_summarize`
- `app/tools/rag.py` — `retrieve_context`, `rag_answer`
- `app/tools/embedder.py` — `chunk_text`, `embed_chunks`, `ingest_filing`
- `tests/test_orchestrator.py` — 6 tests (4 unit, 2 graph integration with mocked sub-agents)

## Orchestrator design
Fan-out from START → research_node + quant_node (parallel Celery dispatches); join → risk_node; conditional → execution_node (PASS + qty>0 + mode=full_analysis) or synthesize_node; synthesize writes Signal row to DB and caches result at `result:{query_id}` in Redis (TTL 3600s).
