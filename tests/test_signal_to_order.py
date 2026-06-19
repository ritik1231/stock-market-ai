"""End-to-end integration test for the signal-to-order pipeline.

Requires:
  - Docker Compose stack running (postgres, redis, rabbitmq)
  - Celery worker and beat running
  - Real Alpaca paper credentials in .env
  - uvicorn server running at http://localhost:8000

Run with:
  pytest tests/test_signal_to_order.py -m integration -v

Excluded from CI by default (no ``-m integration`` flag).
"""

import time

import httpx
import pytest

BASE_URL = "http://localhost:8000"
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 60


@pytest.mark.integration
def test_signal_to_order_pipeline():
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        # Step 1: Trigger analysis
        resp = client.post("/analyze", json={"ticker": "AAPL", "mode": "full_analysis"})
        assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
        body = resp.json()
        query_id = body["query_id"]
        assert query_id
        assert body["ticker"] == "AAPL"

        # Step 2: Poll until complete or timeout
        result = None
        deadline = time.time() + POLL_TIMEOUT_S
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_S)
            poll = client.get(f"/analysis/{query_id}")
            if poll.status_code == 200:
                result = poll.json()
                break

        assert result is not None, f"Analysis did not complete within {POLL_TIMEOUT_S}s"
        assert result["final_signal"] in ("BUY", "SELL", "HOLD"), (
            f"Unexpected signal: {result['final_signal']}"
        )

        # Step 3: Place a paper trade if BUY signal
        if result["final_signal"] == "BUY":
            trade_resp = client.post(
                "/trade",
                json={"ticker": "AAPL", "action": "BUY", "qty": 1},
            )
            assert trade_resp.status_code == 200, (
                f"Trade failed: {trade_resp.status_code} {trade_resp.text}"
            )
            trade = trade_resp.json()
            assert trade["status"] in (
                "accepted", "filled", "pending_new", "new", "partially_filled"
            ), f"Unexpected order status: {trade['status']}"

            # Step 4: Verify trade is recorded
            trades_resp = client.get("/trades?ticker=AAPL&limit=5")
            assert trades_resp.status_code == 200
            trades = trades_resp.json()
            assert len(trades) > 0, "Trade should be recorded in the trades table"

            # Step 5: Check portfolio
            portfolio_resp = client.get("/portfolio")
            assert portfolio_resp.status_code == 200
            portfolio = portfolio_resp.json()
            assert "positions" in portfolio
            assert "portfolio_value" in portfolio


@pytest.mark.integration
def test_health_check_passes():
    """Smoke test: confirm the server is up and both DB and Redis are reachable."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        assert body["redis"] == "ok"


@pytest.mark.integration
def test_analyze_invalid_ticker_rejected():
    """Validation smoke test: bad ticker should return 422."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        resp = client.post("/analyze", json={"ticker": "!invalid!", "mode": "signal_only"})
        assert resp.status_code == 422


@pytest.mark.integration
def test_signal_not_found_returns_404():
    """Unknown ticker should return 404 from /signal endpoint."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        resp = client.get("/signal/ZZZZZ")
        assert resp.status_code == 404
