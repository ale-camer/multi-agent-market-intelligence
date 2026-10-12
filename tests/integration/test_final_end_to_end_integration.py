"""Final end-to-end integration tests validating full platform and delivery layers."""

import concurrent.futures
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from multi_agent_market_intelligence import (
    MarketIntelligenceOrchestrator,
    MessageBus,
    MessageType,
    NodeNames,
    ResearchAgent,
    RiskPortfolioManagerAgent,
    TradingAnalystAgent,
    create_market_state,
    create_research_node_handler,
    create_risk_manager_node_handler,
    create_trading_analyst_node_handler,
)
from multi_agent_market_intelligence.api import app, reset_portfolio_tracker
from multi_agent_market_intelligence.api.schemas import (
    AnalysisResponse,
    HealthResponse,
)


@pytest.fixture(autouse=True)
def clean_portfolio_state() -> Generator[None, None, None]:
    """Ensure each test runs against a clean, isolated portfolio tracker."""
    reset_portfolio_tracker(initial_cash=100_000.0)
    yield
    reset_portfolio_tracker(initial_cash=100_000.0)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient instance bound to the market intelligence FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.issue_25
def test_e2e_healthcheck_and_api_metadata(client: TestClient) -> None:
    """Verify healthcheck endpoint and OpenAPI schema availability and contracts."""
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert health_data["version"] == "0.1.0"
    parsed_health = HealthResponse(**health_data)
    assert parsed_health.status == "healthy"

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    openapi_spec = openapi_resp.json()
    assert openapi_spec["info"]["title"] == "Multi-Agent Market Intelligence API"
    paths = openapi_spec["paths"]
    assert "/health" in paths
    assert "/api/v1/analyze" in paths
    assert "/api/v1/portfolio" in paths


@pytest.mark.issue_25
def test_e2e_single_ticker_analysis_lifecycle(client: TestClient) -> None:
    """Verify complete HTTP execution flow for single-ticker market intelligence analysis."""
    corr_id = "e2e-single-aapl-001"
    request_payload = {
        "symbols": ["AAPL"],
        "initial_cash": 100_000.0,
        "correlation_id": corr_id,
    }

    resp = client.post("/api/v1/analyze", json=request_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["correlation_id"] == corr_id
    assert data["symbols"] == ["AAPL"]
    assert data["execution_time_ms"] > 0.0

    # Validate generated signals and decisions
    assert len(data["signals"]) >= 1
    signal = data["signals"][0]
    assert signal["symbol"] == "AAPL"
    assert signal["action"] in ["BUY", "SELL", "HOLD"]

    assert len(data["decisions"]) >= 1
    decision = data["decisions"][0]
    assert decision["status"] in ["APPROVED", "REJECTED", "MODIFIED"]

    # Validate agent execution records
    records = data["records"]
    assert len(records) == 3
    executed_names = {r["agent_name"].lower() for r in records}
    assert any("research" in name for name in executed_names)
    assert any("trading" in name for name in executed_names)
    assert any("risk" in name for name in executed_names)

    parsed_response = AnalysisResponse(**data)
    assert parsed_response.status == "SUCCESS"


@pytest.mark.issue_25
def test_e2e_multi_ticker_analysis_lifecycle(client: TestClient) -> None:
    """Verify autonomous DAG execution over a diversified multi-ticker investment basket."""
    symbols = ["AAPL", "NVDA", "MSFT"]
    corr_id = "e2e-multi-basket-002"
    request_payload = {
        "symbols": symbols,
        "initial_cash": 250_000.0,
        "correlation_id": corr_id,
    }

    resp = client.post("/api/v1/analyze", json=request_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["correlation_id"] == corr_id
    assert data["symbols"] == symbols
    assert len(data["signals"]) >= len(symbols)
    assert len(data["decisions"]) >= len(symbols)

    signal_symbols = {s["symbol"] for s in data["signals"]}
    for sym in symbols:
        assert sym in signal_symbols


@pytest.mark.issue_25
def test_e2e_multi_cycle_trading_and_portfolio_evolution(client: TestClient) -> None:
    """Verify multi-cycle trading lifecycle: analysis -> buy order -> sell liquidation."""
    # Reset to baseline
    reset_resp = client.post("/api/v1/portfolio/reset", json={"initial_cash": 100_000.0})
    assert reset_resp.status_code == 200

    # Cycle 1: Execute analysis to produce investment signals
    analysis_resp = client.post(
        "/api/v1/analyze",
        json={"symbols": ["AAPL"], "correlation_id": "e2e-cycle-1"},
    )
    assert analysis_resp.status_code == 200

    # Execute BUY trade based on approved proposal
    buy_payload = {
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100.0,
        "price": 150.0,
    }
    trade_buy_resp = client.post("/api/v1/portfolio/trade", json=buy_payload)
    assert trade_buy_resp.status_code == 200
    buy_data = trade_buy_resp.json()
    assert buy_data["action"] == "BUY"
    assert buy_data["quantity"] == 100.0
    assert buy_data["cost"] == 15_000.0

    # Verify updated cash via portfolio state
    state_buy_resp = client.get("/api/v1/portfolio")
    assert state_buy_resp.status_code == 200
    assert state_buy_resp.json()["cash"] == 85_000.0

    # Verify positions state
    pos_resp = client.get("/api/v1/portfolio/positions/AAPL")
    assert pos_resp.status_code == 200
    pos_data = pos_resp.json()
    assert pos_data["symbol"] == "AAPL"
    assert pos_data["quantity"] == 100.0
    assert pos_data["entry_price"] == 150.0

    # Cycle 2: Market price moves up, liquidate 50 shares
    sell_payload = {
        "symbol": "AAPL",
        "action": "SELL",
        "quantity": 50.0,
        "price": 180.0,
    }
    trade_sell_resp = client.post("/api/v1/portfolio/trade", json=sell_payload)
    assert trade_sell_resp.status_code == 200
    sell_data = trade_sell_resp.json()
    assert sell_data["action"] == "SELL"
    assert sell_data["quantity"] == 50.0
    assert sell_data["cost"] == 9_000.0

    # Verify updated cash after sale
    state_sell_resp = client.get("/api/v1/portfolio")
    assert state_sell_resp.status_code == 200
    assert state_sell_resp.json()["cash"] == 94_000.0

    # Verify trade history
    history_resp = client.get("/api/v1/portfolio/history")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["total_trades"] == 2
    assert len(history_data["history"]) == 2

    # Verify metrics
    metrics_resp = client.get("/api/v1/portfolio/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert metrics_data["total_equity"] >= 94_000.0


@pytest.mark.issue_25
def test_e2e_cash_deposit_and_withdrawal_lifecycle(client: TestClient) -> None:
    """Verify cash management endpoints: deposit, withdrawal, and overdraft rejection."""
    # Deposit capital
    dep_resp = client.post("/api/v1/portfolio/deposit", json={"amount": 50_000.0})
    assert dep_resp.status_code == 200
    dep_data = dep_resp.json()
    assert dep_data["transaction_type"] == "DEPOSIT"
    assert dep_data["new_cash"] == 150_000.0

    # Withdraw capital
    with_resp = client.post("/api/v1/portfolio/withdraw", json={"amount": 30_000.0})
    assert with_resp.status_code == 200
    with_data = with_resp.json()
    assert with_data["transaction_type"] == "WITHDRAWAL"
    assert with_data["new_cash"] == 120_000.0

    # Overdraft rejection
    overdraft_resp = client.post("/api/v1/portfolio/withdraw", json={"amount": 500_000.0})
    assert overdraft_resp.status_code == 400
    assert "Insufficient cash" in overdraft_resp.json()["detail"]


@pytest.mark.issue_25
def test_e2e_orchestrator_message_bus_event_flow_audit() -> None:
    """Verify live MessageBus event publication and audit trail across real agents."""
    bus = MessageBus()
    orchestrator_events: list[Any] = []

    bus.subscribe("orchestrator", lambda msg: orchestrator_events.append(msg))

    research_agent = ResearchAgent(message_bus=bus)
    trading_agent = TradingAnalystAgent(message_bus=bus)
    risk_agent = RiskPortfolioManagerAgent(message_bus=bus)

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=create_research_node_handler(research_agent),
        trading_analyst_handler=create_trading_analyst_node_handler(trading_agent),
        risk_manager_handler=create_risk_manager_node_handler(risk_agent),
    )

    corr_id = "e2e-audit-event-bus-999"
    state = create_market_state(context={"target_symbols": ["AAPL"], "correlation_id": corr_id})

    final_state = orchestrator.run(state)
    assert final_state["current_step"] == NodeNames.RISK_MANAGER
    assert len(final_state["decisions"]) >= 1

    # Verify risk evaluation event broadcast
    assert len(orchestrator_events) >= 1
    event = orchestrator_events[-1]
    assert event.message_type == MessageType.RISK_EVALUATION
    assert event.correlation_id == corr_id
    assert "risk" in event.sender.lower()


@pytest.mark.issue_25
def test_e2e_api_validation_error_boundaries(client: TestClient) -> None:
    """Verify input validation, business constraint rejections, and HTTP error boundaries."""
    # 422: Empty symbol list
    resp_empty = client.post("/api/v1/analyze", json={"symbols": []})
    assert resp_empty.status_code == 422

    # 422: Negative cash balance
    resp_neg_cash = client.post(
        "/api/v1/analyze", json={"symbols": ["AAPL"], "initial_cash": -50.0}
    )
    assert resp_neg_cash.status_code == 422

    # 400: Trade execution with insufficient cash
    resp_bad_buy = client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "BUY", "quantity": 100_000.0, "price": 500.0},
    )
    assert resp_bad_buy.status_code == 400
    assert "Insufficient cash" in resp_bad_buy.json()["detail"]

    # 400: Selling non-existent position
    resp_bad_sell = client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "UNKNOWN", "action": "SELL", "quantity": 10.0, "price": 100.0},
    )
    assert resp_bad_sell.status_code == 400
    assert "UNKNOWN" in resp_bad_sell.json()["detail"]

    # 404: Querying non-existent position
    resp_not_found = client.get("/api/v1/portfolio/positions/NONEXISTENT")
    assert resp_not_found.status_code == 404

    # 422: Negative deposit amount
    resp_neg_deposit = client.post("/api/v1/portfolio/deposit", json={"amount": -100.0})
    assert resp_neg_deposit.status_code == 422


@pytest.mark.issue_25
def test_e2e_concurrent_analysis_requests(client: TestClient) -> None:
    """Verify thread safety and isolation under concurrent client analysis requests."""

    def invoke_analysis(symbol: str, request_id: int) -> tuple[int, dict[str, Any]]:
        corr_id = f"concurrent-{request_id}-{symbol}"
        resp = client.post(
            "/api/v1/analyze",
            json={"symbols": [symbol], "correlation_id": corr_id},
        )
        return resp.status_code, resp.json()

    tickers = ["AAPL", "NVDA", "MSFT", "AAPL"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(invoke_analysis, ticker, idx) for idx, ticker in enumerate(tickers)
        ]
        results = [future.result() for future in futures]

    for status_code, body in results:
        assert status_code == 200
        assert body["status"] == "SUCCESS"
        assert len(body["records"]) == 3
        assert len(body["signals"]) >= 1
        assert len(body["decisions"]) >= 1
