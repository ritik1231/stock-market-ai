import asyncio
import logging
from typing import Optional, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.agents.execution_agent import ExecutionInput, run_execution_agent
from app.agents.quant_agent import QuantInput, run_quant_agent
from app.agents.research_agent import ResearchInput, run_research_agent
from app.agents.risk_agent import RiskInput, run_risk_agent
from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.models.agent import Signal
from app.tools.cache import set_cache
from app.tools.llm import groq_synthesize_signal

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict):
    query_id: str
    ticker: str
    query_text: str
    mode: str  # "signal_only" | "full_analysis"
    research_result: Optional[dict]
    quant_result: Optional[dict]
    risk_result: Optional[dict]
    execution_result: Optional[dict]
    final_signal: Optional[str]
    confidence: Optional[float]
    summary: Optional[str]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def _get(async_result, timeout):
    """Call .get() on a Celery AsyncResult from inside a task safely."""
    return async_result.get(timeout=timeout, disable_sync_subtasks=False)


def research_node(state: OrchestratorState) -> dict:
    payload = ResearchInput(
        query_id=state["query_id"],
        ticker=state["ticker"],
    ).model_dump()
    try:
        result = _get(run_research_agent.apply_async(args=[payload], queue="agent.research"), 120)
    except Exception as exc:
        logger.error("research_node failed for %s: %s", state["ticker"], exc)
        result = {"error": str(exc)}
    return {"research_result": result}


def quant_node(state: OrchestratorState) -> dict:
    payload = QuantInput(
        query_id=state["query_id"],
        ticker=state["ticker"],
    ).model_dump()
    try:
        result = _get(run_quant_agent.apply_async(args=[payload], queue="agent.quant"), 120)
    except Exception as exc:
        logger.error("quant_node failed for %s: %s", state["ticker"], exc)
        result = {"error": str(exc)}
    return {"quant_result": result}


def risk_node(state: OrchestratorState) -> dict:
    research = state.get("research_result") or {}
    quant = state.get("quant_result") or {}

    try:
        confidence = min(max(float(research.get("sentiment_score", 0.7)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.7

    payload = RiskInput(
        query_id=state["query_id"],
        ticker=state["ticker"],
        proposed_signal=quant.get("quant_signal", "HOLD"),
        atr_14=float(quant.get("atr_14") or 1.0),
        current_price=float(quant.get("current_price") or 100.0),
        confidence=confidence,
    ).model_dump()

    try:
        result = _get(run_risk_agent.apply_async(args=[payload], queue="agent.risk"), 60)
    except Exception as exc:
        logger.error("risk_node failed for %s: %s", state["ticker"], exc)
        result = {"decision": "BLOCK", "reason": str(exc), "suggested_qty": 0,
                  "stop_loss": 0.0, "take_profit": 0.0}
    return {"risk_result": result}


def execution_node(state: OrchestratorState) -> dict:
    risk = state.get("risk_result") or {}
    quant = state.get("quant_result") or {}

    payload = ExecutionInput(
        query_id=state["query_id"],
        ticker=state["ticker"],
        action=quant.get("quant_signal", "BUY"),
        qty=int(risk.get("suggested_qty", 1)),
        stop_loss=float(risk.get("stop_loss", 0.0)),
        take_profit=float(risk.get("take_profit", 0.0)),
        paper_mode=True,
    ).model_dump()

    try:
        result = _get(run_execution_agent.apply_async(args=[payload], queue="agent.execution"), 60)
    except Exception as exc:
        logger.error("execution_node failed for %s: %s", state["ticker"], exc)
        result = {"error": str(exc)}
    return {"execution_result": result}


def synthesize_node(state: OrchestratorState) -> dict:
    research = state.get("research_result") or {}
    quant = state.get("quant_result") or {}
    risk = state.get("risk_result") or {}

    # asyncio.run() creates a new event loop but asyncpg pool connections are
    # bound to the forked parent's loop. Use a fresh loop and dispose the pool
    # first so new connections are created in the correct loop.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        synthesis = loop.run_until_complete(_synthesize_and_persist(state, research, quant, risk))
    finally:
        loop.close()
        asyncio.set_event_loop(None)
    return {
        "final_signal": synthesis.get("signal", "HOLD"),
        "confidence": synthesis.get("confidence", 0.0),
        "summary": synthesis.get("summary", ""),
    }


async def _synthesize_and_persist(
    state: OrchestratorState,
    research: dict,
    quant: dict,
    risk: dict,
) -> dict:
    from app.db import engine as async_engine

    synthesis = await groq_synthesize_signal(research, quant, risk)

    signal_row = Signal(
        query_id=UUID(state["query_id"]),
        ticker=state["ticker"].upper(),
        signal=synthesis.get("signal", "HOLD"),
        confidence=synthesis.get("confidence"),
        quant_signal=quant.get("quant_signal"),
        sentiment_score=research.get("sentiment_score"),
        risk_decision=risk.get("decision"),
        summary=synthesis.get("summary"),
        raw_output={
            "research": research,
            "quant": quant,
            "risk": risk,
            "synthesis": synthesis,
            "execution": state.get("execution_result"),
        },
    )
    # Dispose stale pool connections from the forked parent process so that
    # new connections are created bound to the current event loop.
    await async_engine.dispose()
    async with AsyncSessionLocal() as db:
        db.add(signal_row)
        await db.commit()

    full_result = {
        "query_id": state["query_id"],
        "ticker": state["ticker"],
        "final_signal": synthesis.get("signal", "HOLD"),
        "confidence": synthesis.get("confidence"),
        "summary": synthesis.get("summary"),
        "key_factors": synthesis.get("key_factors", []),
        "research_result": research,
        "quant_result": quant,
        "risk_result": risk,
        "execution_result": state.get("execution_result"),
    }
    await set_cache(f"result:{state['query_id']}", full_result, ttl=3600)
    return synthesis


def error_node(state: OrchestratorState) -> dict:
    logger.error("Orchestrator error for %s: %s", state.get("ticker"), state.get("error"))
    return {"final_signal": "ERROR"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_after_risk(state: OrchestratorState) -> str:
    risk = state.get("risk_result") or {}
    if (
        risk.get("decision") == "BLOCK"
        or state.get("mode") == "signal_only"
        or risk.get("suggested_qty", 0) == 0
    ):
        return "synthesize_node"
    return "execution_node"


# ---------------------------------------------------------------------------
# Graph construction (Tasks 4.1 + 4.2)
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("research_node", research_node)
    graph.add_node("quant_node", quant_node)
    graph.add_node("risk_node", risk_node)
    graph.add_node("execution_node", execution_node)
    graph.add_node("synthesize_node", synthesize_node)
    graph.add_node("error_node", error_node)

    # Parallel fan-out from START
    graph.add_edge(START, "research_node")
    graph.add_edge(START, "quant_node")

    # Join at risk_node — both branches must complete before risk runs
    graph.add_edge("research_node", "risk_node")
    graph.add_edge("quant_node", "risk_node")

    # Conditional routing after risk assessment
    graph.add_conditional_edges(
        "risk_node",
        route_after_risk,
        {
            "execution_node": "execution_node",
            "synthesize_node": "synthesize_node",
        },
    )

    graph.add_edge("execution_node", "synthesize_node")
    graph.add_edge("synthesize_node", END)
    graph.add_edge("error_node", END)

    return graph


compiled_graph = _build_graph().compile()


# ---------------------------------------------------------------------------
# Celery task (Task 4.3)
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, queue="orchestrator.tasks", name="agents.orchestrator")
def run_orchestrator(self, payload: dict) -> dict:
    initial_state: OrchestratorState = {
        "query_id": payload["query_id"],
        "ticker": payload["ticker"],
        "query_text": payload.get("query_text", ""),
        "mode": payload.get("mode", "signal_only"),
        "research_result": None,
        "quant_result": None,
        "risk_result": None,
        "execution_result": None,
        "final_signal": None,
        "confidence": None,
        "summary": None,
        "error": None,
    }
    logger.info("orchestrator starting ticker=%s mode=%s", payload["ticker"], initial_state["mode"])
    final_state = compiled_graph.invoke(initial_state)
    logger.info(
        "orchestrator finished ticker=%s signal=%s confidence=%s",
        payload["ticker"],
        final_state.get("final_signal"),
        final_state.get("confidence"),
    )
    return dict(final_state)
