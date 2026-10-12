"""Unit tests for FastAPI setup, routing, schemas, and orchestrator execution."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from multi_agent_market_intelligence.api import (
    APISettings,
    app,
    create_app,
    get_orchestrator,
)
from multi_agent_market_intelligence.api.schemas import (
    AnalysisResponse,
    HealthResponse,
)
from multi_agent_market_intelligence.state.models import (
    AgentExecutionRecord,
    DecisionStatus,
    PortfolioSnapshot,
    RiskDecision,
    SignalAction,
    TradingSignal,
)
from multi_agent_market_intelligence.state.schema import create_market_state


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient fixture with default application instance."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.issue_21
def test_api_settings_defaults_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify APISettings defaults and environment variable parsing."""
    settings = APISettings()
    assert settings.title == "Multi-Agent Market Intelligence API"
    assert settings.version == "0.1.0"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.cors_origins == ["*"]
    assert settings.debug is False
    assert settings.default_cash == 100_000.0

    # Test environment variable overrides
    monkeypatch.setenv("API_TITLE", "Custom Intelligence API")
    monkeypatch.setenv("API_VERSION", "2.0.0")
    monkeypatch.setenv("API_CORS_ORIGINS", "https://app.com,https://api.com")
    monkeypatch.setenv("API_DEBUG", "true")
    monkeypatch.setenv("API_DEFAULT_CASH", "500000.0")

    env_settings = APISettings.from_env()
    assert env_settings.title == "Custom Intelligence API"
    assert env_settings.version == "2.0.0"
    assert env_settings.cors_origins == ["https://app.com", "https://api.com"]
    assert env_settings.debug is True
    assert env_settings.default_cash == 500_000.0


@pytest.mark.issue_21
def test_create_app_factory_and_root_endpoint() -> None:
    """Verify application factory instantiation and root metadata endpoint."""
    custom_settings = APISettings(
        title="Custom Market System",
        version="0.9.5",
        debug=True,
    )
    custom_app = create_app(custom_settings)
    client_custom = TestClient(custom_app)

    resp = client_custom.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "Custom Market System"
    assert data["version"] == "0.9.5"
    assert data["docs"] == "/docs"
    assert data["openapi"] == "/openapi.json"
    assert data["health"] == "/health"
    assert data["api_v1"] == "/api/v1"


@pytest.mark.issue_21
def test_health_endpoints_root_and_v1(client: TestClient) -> None:
    """Verify both top-level /health and versioned /api/v1/health endpoints."""
    # 1. Root /health probe
    resp_root = client.get("/health")
    assert resp_root.status_code == 200
    data_root = resp_root.json()
    assert data_root["status"] == "healthy"
    assert "timestamp" in data_root
    assert data_root["version"] == "0.1.0"
    health_obj = HealthResponse(**data_root)
    assert health_obj.status == "healthy"

    # 2. Versioned /api/v1/health probe
    resp_v1 = client.get("/api/v1/health")
    assert resp_v1.status_code == 200
    data_v1 = resp_v1.json()
    assert data_v1["status"] == "healthy"
    assert data_v1["service"] == data_root["service"]


@pytest.mark.issue_21
def test_analyze_endpoint_e2e_real_orchestrator(client: TestClient) -> None:
    """Verify end-to-end multi-agent pipeline execution through POST /api/v1/analyze."""
    payload = {"symbols": ["AAPL"]}
    resp = client.post("/api/v1/analyze", json=payload)

    assert resp.status_code == 200
    data = resp.json()

    # Telemetry and identifiers
    assert data["status"] == "SUCCESS"
    assert "correlation_id" in data and len(data["correlation_id"]) > 0
    assert data["symbols"] == ["AAPL"]
    assert data["execution_time_ms"] > 0.0

    # Domain models serialization integrity
    assert len(data["signals"]) > 0
    assert data["signals"][0]["symbol"] == "AAPL"

    assert len(data["decisions"]) > 0
    assert data["decisions"][0]["status"] in (
        DecisionStatus.APPROVED.value,
        DecisionStatus.MODIFIED.value,
    )

    portfolio = data["portfolio"]
    assert portfolio["total_equity"] > 0.0
    assert portfolio["cash"] > 0.0

    # Agent audit records
    assert len(data["records"]) > 0
    agent_names = {r["agent_name"].lower() for r in data["records"]}
    assert any("research" in n for n in agent_names)
    assert any("trading" in n for n in agent_names)
    assert any("risk" in n for n in agent_names)

    # Validates response model compatibility
    response_model = AnalysisResponse(**data)
    assert response_model.status == "SUCCESS"


@pytest.mark.issue_21
def test_analyze_endpoint_custom_correlation_and_cash(client: TestClient) -> None:
    """Verify custom initial cash and correlation ID propagation."""
    custom_corr = "test-corr-custom-999"
    payload = {
        "symbols": ["MSFT"],
        "initial_cash": 250_000.0,
        "correlation_id": custom_corr,
    }
    resp = client.post("/api/v1/analyze", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["correlation_id"] == custom_corr
    assert data["symbols"] == ["MSFT"]
    assert data["portfolio"]["total_equity"] > 0.0


@pytest.mark.issue_21
def test_analyze_validation_errors(client: TestClient) -> None:
    """Verify input validation rejection with HTTP 422 Unprocessable Entity."""
    # 1. Empty symbols list
    resp1 = client.post("/api/v1/analyze", json={"symbols": []})
    assert resp1.status_code == 422
    data1 = resp1.json()
    assert data1["error"] == "ValidationError"
    assert "detail" in data1

    # 2. Non-positive initial cash
    resp2 = client.post("/api/v1/analyze", json={"symbols": ["AAPL"], "initial_cash": -50.0})
    assert resp2.status_code == 422
    data2 = resp2.json()
    assert data2["error"] == "ValidationError"

    # 3. Missing required symbols field
    resp3 = client.post("/api/v1/analyze", json={"initial_cash": 100_000.0})
    assert resp3.status_code == 422


@pytest.mark.issue_21
def test_dependency_override_mock_orchestrator() -> None:
    """Verify FastAPI dependency injection override using custom mock orchestrator."""
    test_app = create_app()

    mock_orchestrator = MagicMock()
    mock_orchestrator.run.return_value = create_market_state(
        signals=[
            TradingSignal(
                symbol="TSLA",
                action=SignalAction.BUY,
                target_price=250.0,
                stop_loss=180.0,
            )
        ],
        decisions=[
            RiskDecision(
                status=DecisionStatus.APPROVED,
                approved_size=50.0,
                reason="Mock approved",
            )
        ],
        portfolio=PortfolioSnapshot(cash=80_000.0, total_equity=95_000.0),
        records=[AgentExecutionRecord(agent_name="MockAgent", step="mock_step", status="SUCCESS")],
    )

    test_app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator

    with TestClient(test_app) as test_client:
        resp = test_client.post(
            "/api/v1/analyze",
            json={"symbols": ["TSLA"], "correlation_id": "mock-corr-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbols"] == ["TSLA"]
        assert data["correlation_id"] == "mock-corr-001"
        assert len(data["signals"]) == 1
        assert data["signals"][0]["symbol"] == "TSLA"
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["reason"] == "Mock approved"
        assert data["portfolio"]["cash"] == 80_000.0

    test_app.dependency_overrides.clear()


@pytest.mark.issue_21
def test_openapi_and_docs_endpoints(client: TestClient) -> None:
    """Verify OpenAPI JSON schema specification and interactive documentation availability."""
    resp_openapi = client.get("/openapi.json")
    assert resp_openapi.status_code == 200
    schema = resp_openapi.json()
    assert schema["openapi"].startswith("3.")
    assert "/health" in schema["paths"]
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/analyze" in schema["paths"]

    resp_docs = client.get("/docs")
    assert resp_docs.status_code == 200
    assert "swagger" in resp_docs.text.lower() or "html" in resp_docs.text.lower()


@pytest.mark.issue_21
def test_cors_middleware_headers(client: TestClient) -> None:
    """Verify CORS headers are returned for preflight and standard requests."""
    resp = client.get("/health", headers={"Origin": "https://example.com"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") in ("*", "https://example.com")


@pytest.mark.issue_21
def test_analyze_orchestrator_failure_handling() -> None:
    """Verify unhandled orchestrator exceptions are returned as HTTP 500 error."""
    test_app = create_app()

    failing_orchestrator = MagicMock()
    failing_orchestrator.run.side_effect = RuntimeError("Simulated pipeline crash")
    test_app.dependency_overrides[get_orchestrator] = lambda: failing_orchestrator

    with TestClient(test_app) as test_client:
        resp = test_client.post("/api/v1/analyze", json={"symbols": ["NVDA"]})
        assert resp.status_code == 500
        data = resp.json()
        assert "Simulated pipeline crash" in data["detail"]

    test_app.dependency_overrides.clear()
