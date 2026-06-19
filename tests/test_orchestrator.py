from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.orchestrator import OrchestratorState, compiled_graph, route_after_risk

_QUERY_ID = "00000000-0000-0000-0000-000000000001"

MOCK_RESEARCH = {
    "query_id": _QUERY_ID,
    "ticker": "AAPL",
    "sentiment_score": 0.7,
    "sentiment_label": "BULLISH",
    "sentiment_reasoning": "Positive earnings coverage",
    "rag_answer": "Strong iPhone growth expected",
    "rag_sources": [],
    "summary": "AAPL fundamentals look solid",
    "article_count": 5,
}

MOCK_QUANT_BUY = {
    "query_id": _QUERY_ID,
    "ticker": "AAPL",
    "interval": "1d",
    "period": "6mo",
    "indicators": {"macd_signal_label": "bullish_crossover", "rsi_zone": "neutral"},
    "quant_signal": "BUY",
    "current_price": 175.0,
    "atr_14": 2.5,
}

MOCK_RISK_PASS = {
    "query_id": _QUERY_ID,
    "ticker": "AAPL",
    "decision": "PASS",
    "reason": "All guardrails passed",
    "suggested_qty": 2,
    "stop_loss": 170.0,
    "take_profit": 182.5,
}

MOCK_RISK_BLOCK = {
    "query_id": _QUERY_ID,
    "ticker": "AAPL",
    "decision": "BLOCK",
    "reason": "Confidence below threshold",
    "suggested_qty": 0,
    "stop_loss": 170.0,
    "take_profit": 182.5,
}

MOCK_EXECUTION = {
    "query_id": _QUERY_ID,
    "ticker": "AAPL",
    "order_id": "abc-order-123",
    "status": "accepted",
    "filled_price": None,
    "timestamp": None,
}

MOCK_SYNTHESIS = {
    "signal": "BUY",
    "confidence": 0.82,
    "summary": "Strong buy signal based on MACD crossover and positive sentiment",
    "key_factors": ["Bullish MACD", "Positive sentiment", "Strong fundamentals"],
}


def _celery_mock(return_value: dict) -> MagicMock:
    async_result = MagicMock()
    async_result.get.return_value = return_value
    task = MagicMock()
    task.apply_async.return_value = async_result
    return task


def _db_mock() -> tuple[MagicMock, AsyncMock]:
    session = AsyncMock()
    session.add = MagicMock()  # add() is a sync call in SQLAlchemy
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    db_cls = MagicMock(return_value=ctx)
    return db_cls, session


# ---------------------------------------------------------------------------
# Unit tests: route_after_risk
# ---------------------------------------------------------------------------

def test_route_blocks_on_block_decision():
    state: OrchestratorState = {
        "query_id": "q1", "ticker": "AAPL", "query_text": "",
        "mode": "full_analysis",
        "research_result": None, "quant_result": None,
        "risk_result": {"decision": "BLOCK", "suggested_qty": 0, "reason": "test"},
        "execution_result": None, "final_signal": None,
        "confidence": None, "summary": None, "error": None,
    }
    assert route_after_risk(state) == "synthesize_node"


def test_route_skips_execution_in_signal_only_mode():
    state: OrchestratorState = {
        "query_id": "q1", "ticker": "AAPL", "query_text": "",
        "mode": "signal_only",
        "research_result": None, "quant_result": None,
        "risk_result": {"decision": "PASS", "suggested_qty": 5, "reason": "ok"},
        "execution_result": None, "final_signal": None,
        "confidence": None, "summary": None, "error": None,
    }
    assert route_after_risk(state) == "synthesize_node"


def test_route_skips_execution_when_qty_zero():
    state: OrchestratorState = {
        "query_id": "q1", "ticker": "AAPL", "query_text": "",
        "mode": "full_analysis",
        "research_result": None, "quant_result": None,
        "risk_result": {"decision": "PASS", "suggested_qty": 0, "reason": "too small"},
        "execution_result": None, "final_signal": None,
        "confidence": None, "summary": None, "error": None,
    }
    assert route_after_risk(state) == "synthesize_node"


def test_route_proceeds_to_execution_when_pass_with_qty():
    state: OrchestratorState = {
        "query_id": "q1", "ticker": "AAPL", "query_text": "",
        "mode": "full_analysis",
        "research_result": None, "quant_result": None,
        "risk_result": {"decision": "PASS", "suggested_qty": 2, "reason": "ok"},
        "execution_result": None, "final_signal": None,
        "confidence": None, "summary": None, "error": None,
    }
    assert route_after_risk(state) == "execution_node"


# ---------------------------------------------------------------------------
# Graph integration tests (sub-agents mocked)
# ---------------------------------------------------------------------------

@patch("app.agents.orchestrator.set_cache", new_callable=AsyncMock)
@patch("app.agents.orchestrator.AsyncSessionLocal")
@patch("app.agents.orchestrator.groq_synthesize_signal", new_callable=AsyncMock)
@patch("app.agents.orchestrator.run_execution_agent", new_callable=MagicMock)
@patch("app.agents.orchestrator.run_risk_agent", new_callable=MagicMock)
@patch("app.agents.orchestrator.run_quant_agent", new_callable=MagicMock)
@patch("app.agents.orchestrator.run_research_agent", new_callable=MagicMock)
def test_graph_pass_risk_routes_through_execution(
    mock_research, mock_quant, mock_risk, mock_exec,
    mock_synthesize, mock_db_cls, mock_cache,
):
    mock_research.apply_async.return_value = MagicMock(get=MagicMock(return_value=MOCK_RESEARCH))
    mock_quant.apply_async.return_value = MagicMock(get=MagicMock(return_value=MOCK_QUANT_BUY))
    mock_risk.apply_async.return_value = MagicMock(get=MagicMock(return_value=MOCK_RISK_PASS))
    mock_exec.apply_async.return_value = MagicMock(get=MagicMock(return_value=MOCK_EXECUTION))
    mock_synthesize.return_value = MOCK_SYNTHESIS

    db_cls, _ = _db_mock()
    mock_db_cls.side_effect = db_cls.side_effect
    mock_db_cls.return_value = db_cls.return_value

    initial_state: OrchestratorState = {
        "query_id": _QUERY_ID,
        "ticker": "AAPL",
        "query_text": "Analyze AAPL",
        "mode": "full_analysis",
        "research_result": None, "quant_result": None,
        "risk_result": None, "execution_result": None,
        "final_signal": None, "confidence": None,
        "summary": None, "error": None,
    }

    final_state = compiled_graph.invoke(initial_state)

    mock_research.apply_async.assert_called_once()
    mock_quant.apply_async.assert_called_once()
    mock_risk.apply_async.assert_called_once()
    mock_exec.apply_async.assert_called_once()  # PASS + qty > 0 → execution runs
    mock_synthesize.assert_called_once()

    assert final_state["final_signal"] == "BUY"
    assert final_state["confidence"] == 0.82
    assert final_state["execution_result"] == MOCK_EXECUTION
    assert final_state["research_result"] == MOCK_RESEARCH
    assert final_state["quant_result"] == MOCK_QUANT_BUY


@patch("app.agents.orchestrator.set_cache", new_callable=AsyncMock)
@patch("app.agents.orchestrator.AsyncSessionLocal")
@patch("app.agents.orchestrator.groq_synthesize_signal", new_callable=AsyncMock)
@patch("app.agents.orchestrator.run_execution_agent", new_callable=MagicMock)
@patch("app.agents.orchestrator.run_risk_agent", new_callable=MagicMock)
@patch("app.agents.orchestrator.run_quant_agent", new_callable=MagicMock)
@patch("app.agents.orchestrator.run_research_agent", new_callable=MagicMock)
def test_graph_block_risk_skips_execution(
    mock_research, mock_quant, mock_risk, mock_exec,
    mock_synthesize, mock_db_cls, mock_cache,
):
    mock_research.apply_async.return_value = MagicMock(get=MagicMock(return_value=MOCK_RESEARCH))
    mock_quant.apply_async.return_value = MagicMock(get=MagicMock(return_value=MOCK_QUANT_BUY))
    mock_risk.apply_async.return_value = MagicMock(get=MagicMock(return_value=MOCK_RISK_BLOCK))
    mock_synthesize.return_value = {**MOCK_SYNTHESIS, "signal": "HOLD", "confidence": 0.4}

    db_cls, _ = _db_mock()
    mock_db_cls.side_effect = db_cls.side_effect
    mock_db_cls.return_value = db_cls.return_value

    initial_state: OrchestratorState = {
        "query_id": _QUERY_ID,
        "ticker": "AAPL",
        "query_text": "Analyze AAPL",
        "mode": "full_analysis",
        "research_result": None, "quant_result": None,
        "risk_result": None, "execution_result": None,
        "final_signal": None, "confidence": None,
        "summary": None, "error": None,
    }

    final_state = compiled_graph.invoke(initial_state)

    mock_exec.apply_async.assert_not_called()  # BLOCK → skip execution
    mock_synthesize.assert_called_once()

    assert final_state["final_signal"] == "HOLD"
    assert final_state["execution_result"] is None
    assert final_state["risk_result"]["decision"] == "BLOCK"
