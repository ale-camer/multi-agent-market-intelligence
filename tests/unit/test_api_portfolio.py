"""Unit tests for portfolio REST API endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from multi_agent_market_intelligence.api import (
    app,
    create_app,
    get_portfolio_tracker,
    reset_portfolio_tracker,
)
from multi_agent_market_intelligence.api.schemas import (
    CashTransactionResponse,
    PortfolioStateResponse,
    PositionsListResponse,
    TradeExecutionResponse,
    TradeHistoryResponse,
)
from multi_agent_market_intelligence.risk.portfolio import PortfolioTracker
from multi_agent_market_intelligence.state.models import Position, SignalAction


@pytest.fixture(autouse=True)
def clean_portfolio_state() -> Generator[None, None, None]:
    """Ensure each test starts with fresh baseline portfolio tracker."""
    reset_portfolio_tracker(initial_cash=100_000.0)
    yield
    reset_portfolio_tracker(initial_cash=100_000.0)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient fixture with default application instance."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.issue_22
def test_get_portfolio_state_default(client: TestClient) -> None:
    """Verify default portfolio state inspection."""
    resp = client.get("/api/v1/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cash"] == 100_000.0
    assert data["total_equity"] == 100_000.0
    assert data["gross_exposure"] == 0.0
    assert data["positions_count"] == 0
    assert data["positions"] == {}

    parsed = PortfolioStateResponse(**data)
    assert parsed.cash == 100_000.0


@pytest.mark.issue_22
def test_cash_deposit_flow(client: TestClient) -> None:
    """Verify cash deposit operation increases liquid cash and total equity."""
    payload = {"amount": 25_000.0}
    resp = client.post("/api/v1/portfolio/deposit", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["transaction_type"] == "DEPOSIT"
    assert data["amount"] == 25_000.0
    assert data["new_cash"] == 125_000.0
    assert data["total_equity"] == 125_000.0

    parsed = CashTransactionResponse(**data)
    assert parsed.amount == 25_000.0


@pytest.mark.issue_22
def test_cash_deposit_validation_error(client: TestClient) -> None:
    """Verify non-positive deposit amount returns 422 Unprocessable Entity."""
    resp = client.post("/api/v1/portfolio/deposit", json={"amount": -500.0})
    assert resp.status_code == 422


@pytest.mark.issue_22
def test_cash_withdraw_flow(client: TestClient) -> None:
    """Verify cash withdrawal decreases liquid cash."""
    payload = {"amount": 20_000.0}
    resp = client.post("/api/v1/portfolio/withdraw", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["transaction_type"] == "WITHDRAWAL"
    assert data["amount"] == 20_000.0
    assert data["new_cash"] == 80_000.0
    assert data["total_equity"] == 80_000.0


@pytest.mark.issue_22
def test_cash_withdraw_overdraft_error(client: TestClient) -> None:
    """Verify withdrawal exceeding available cash returns HTTP 400 Bad Request."""
    payload = {"amount": 999_999.0}
    resp = client.post("/api/v1/portfolio/withdraw", json=payload)

    assert resp.status_code == 400
    data = resp.json()
    assert "Insufficient cash" in data["detail"]


@pytest.mark.issue_22
def test_manual_trade_buy_execution(client: TestClient) -> None:
    """Verify manual BUY trade creates asset position and deducts cash."""
    payload = {
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100.0,
        "price": 150.0,
        "commission": 10.0,
    }
    resp = client.post("/api/v1/portfolio/trade", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["action"] == SignalAction.BUY.value
    assert data["quantity"] == 100.0
    assert data["price"] == 150.0
    assert data["cost"] == 15_000.0
    assert data["commission"] == 10.0

    parsed = TradeExecutionResponse(**data)
    assert parsed.symbol == "AAPL"

    # Verify updated portfolio balance sheet
    state_resp = client.get("/api/v1/portfolio")
    state_data = state_resp.json()
    assert state_data["cash"] == pytest.approx(100_000.0 - 15_000.0 - 10.0)
    assert state_data["positions_count"] == 1
    assert "AAPL" in state_data["positions"]


@pytest.mark.issue_22
def test_get_positions_and_single_position(client: TestClient) -> None:
    """Verify listing all active positions and single symbol lookup."""
    # Open AAPL and MSFT positions
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "BUY", "quantity": 100.0, "price": 150.0},
    )
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "MSFT", "action": "BUY", "quantity": 50.0, "price": 200.0},
    )

    # 1. List active positions
    resp_list = client.get("/api/v1/portfolio/positions")
    assert resp_list.status_code == 200
    data_list = resp_list.json()
    assert data_list["total_positions"] == 2
    symbols = {p["symbol"] for p in data_list["positions"]}
    assert symbols == {"AAPL", "MSFT"}
    PositionsListResponse(**data_list)

    # 2. Get specific position
    resp_single = client.get("/api/v1/portfolio/positions/AAPL")
    assert resp_single.status_code == 200
    data_single = resp_single.json()
    assert data_single["symbol"] == "AAPL"
    assert data_single["quantity"] == 100.0
    assert data_single["entry_price"] == 150.0
    Position(**data_single)

    # 3. Non-held symbol returns 404
    resp_404 = client.get("/api/v1/portfolio/positions/TSLA")
    assert resp_404.status_code == 404
    assert "not found" in resp_404.json()["detail"].lower()


@pytest.mark.issue_22
def test_manual_trade_sell_execution_and_realized_pnl(client: TestClient) -> None:
    """Verify manual SELL trade liquidates position and realizes profit."""
    # 1. Buy 100 AAPL @ $100 ($10,000 cost)
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "BUY", "quantity": 100.0, "price": 100.0},
    )

    # 2. Sell 50 AAPL @ $120 -> Realized PnL = (120 - 100) * 50 - 5 = $995
    resp_sell = client.post(
        "/api/v1/portfolio/trade",
        json={
            "symbol": "AAPL",
            "action": "SELL",
            "quantity": 50.0,
            "price": 120.0,
            "commission": 5.0,
        },
    )
    assert resp_sell.status_code == 200
    data_sell = resp_sell.json()
    assert data_sell["realized_pnl"] == 995.0

    # 3. Remaining position is 50 AAPL
    resp_pos = client.get("/api/v1/portfolio/positions/AAPL")
    assert resp_pos.status_code == 200
    assert resp_pos.json()["quantity"] == 50.0


@pytest.mark.issue_22
def test_manual_trade_oversell_error(client: TestClient) -> None:
    """Verify attempting to sell more units than held returns HTTP 400."""
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "BUY", "quantity": 20.0, "price": 100.0},
    )

    resp = client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "SELL", "quantity": 50.0, "price": 120.0},
    )
    assert resp.status_code == 400
    assert "Cannot sell" in resp.json()["detail"]


@pytest.mark.issue_22
def test_get_portfolio_metrics(client: TestClient) -> None:
    """Verify portfolio quantitative risk metrics endpoint."""
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "BUY", "quantity": 100.0, "price": 100.0},
    )

    resp = client.get("/api/v1/portfolio/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_equity" in data
    assert "leverage" in data
    assert "drawdown_pct" in data
    assert "position_weights" in data
    assert "AAPL" in data["position_weights"]


@pytest.mark.issue_22
def test_get_trade_history(client: TestClient) -> None:
    """Verify chronological trade audit history retrieval."""
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "BUY", "quantity": 10.0, "price": 100.0},
    )
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "MSFT", "action": "BUY", "quantity": 20.0, "price": 200.0},
    )

    resp = client.get("/api/v1/portfolio/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_trades"] == 2
    assert len(data["history"]) == 2
    assert data["history"][0]["symbol"] == "AAPL"
    assert data["history"][1]["symbol"] == "MSFT"
    TradeHistoryResponse(**data)


@pytest.mark.issue_22
def test_portfolio_reset_endpoint(client: TestClient) -> None:
    """Verify portfolio reset re-initializes balance sheet and clears positions."""
    # Build state
    client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "action": "BUY", "quantity": 50.0, "price": 100.0},
    )
    assert client.get("/api/v1/portfolio/positions").json()["total_positions"] == 1

    # Reset
    resp = client.post("/api/v1/portfolio/reset", json={"initial_cash": 200_000.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["cash"] == 200_000.0
    assert data["total_equity"] == 200_000.0
    assert data["positions_count"] == 0
    assert data["positions"] == {}

    # Verify positions cleared
    assert client.get("/api/v1/portfolio/positions").json()["total_positions"] == 0


@pytest.mark.issue_22
def test_dependency_override_isolated_tracker() -> None:
    """Verify isolated portfolio tracker injection via dependency overrides."""
    custom_tracker = PortfolioTracker(initial_cash=50_000.0)
    test_app = create_app()
    test_app.dependency_overrides[get_portfolio_tracker] = lambda: custom_tracker

    with TestClient(test_app) as isolated_client:
        resp = isolated_client.get("/api/v1/portfolio")
        assert resp.status_code == 200
        assert resp.json()["cash"] == 50_000.0

        isolated_client.post("/api/v1/portfolio/deposit", json={"amount": 10_000.0})
        assert custom_tracker.cash == 60_000.0

    test_app.dependency_overrides.clear()
