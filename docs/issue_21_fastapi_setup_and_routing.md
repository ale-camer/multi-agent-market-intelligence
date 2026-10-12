# Issue 21: FastAPI Setup and Routing

**Branch**: `feature/issue-21-fastapi-setup-and-routing`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #21)
**Milestone**: M5 - FastAPI API, Integration & Delivery

## Objective
Establish the FastAPI web service API layer for the Multi-Agent Market Intelligence platform, inaugurating Milestone 5 (FastAPI API, Integration & Delivery). Provide an asynchronous application factory (`create_app`), modular configuration settings (`APISettings`), structured request and response validation models using Pydantic, dependency injection for orchestrator components, standard CORS middleware, global exception handling, and a modular router hierarchy:
- Root `/` metadata endpoint and `/health` probes (both top-level and versioned at `/api/v1/health`).
- Versioned analysis endpoint `POST /api/v1/analyze` triggering the 3-agent intelligence DAG (`research` → `trading_analyst` → `risk_manager`) via HTTP.
- Extensible router foundation prepared for subsequent portfolio management endpoints (Issue 22).

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/api/config.py` implements:
  - `APISettings`: Pydantic settings model with `title`, `version`, `description`, `api_v1_prefix` (`"/api/v1"`), `cors_origins: list[str] = ["*"]`, `debug: bool = False`, and `default_cash: float = 100_000.0`.
- [x] `src/multi_agent_market_intelligence/api/schemas.py` defines typed Pydantic models:
  - `HealthResponse`: service health status, timestamp, service name, and version.
  - `AnalysisRequest`: `symbols: list[str]` (non-empty), optional `initial_cash: float = 100_000.0` (> 0), optional `correlation_id: str | None = None`.
  - `AnalysisResponse`: workflow execution status, `correlation_id`, analyzed symbols, emitted `signals: list[TradingSignal]`, validated `decisions: list[RiskDecision]`, final `portfolio: PortfolioSnapshot`, agent audit logs `records: list[AgentExecutionRecord]`, and total `execution_time_ms: float`.
  - `ErrorResponse`: standardized error envelope with `error: str`, `detail: str | list[Any]`, and UTC timestamp.
- [x] `src/multi_agent_market_intelligence/api/dependencies.py` implements dependency providers:
  - `get_settings() -> APISettings`: returns cached or configurable application settings.
  - `get_orchestrator() -> MarketIntelligenceOrchestrator`: provides configured 3-agent orchestrator instance, easily overridden via `app.dependency_overrides`.
- [x] `src/multi_agent_market_intelligence/api/routers/health.py` implements:
  - `GET /health` and `GET /api/v1/health` returning `HealthResponse`.
- [x] `src/multi_agent_market_intelligence/api/routers/analysis.py` implements:
  - `POST /api/v1/analyze`: receives `AnalysisRequest`, executes `MarketIntelligenceOrchestrator`, and returns `AnalysisResponse`.
- [x] `src/multi_agent_market_intelligence/api/routers/__init__.py`:
  - Assembles sub-routers into `api_v1_router` mounted under `/api/v1`.
- [x] `src/multi_agent_market_intelligence/api/app.py` implements:
  - `create_app(settings: APISettings | None = None) -> FastAPI`: application factory configuring title, OpenAPI/docs URLs, CORS middleware, global exception handlers, and routing.
  - `GET /`: returns service metadata, documentation links, and version info.
  - Top-level `app: FastAPI = create_app()` instance for ASGI servers (Uvicorn).
- [x] `src/multi_agent_market_intelligence/api/__init__.py` exposes:
  - `create_app`, `app`, `APISettings`, `HealthResponse`, `AnalysisRequest`, `AnalysisResponse`, `get_orchestrator`, `get_settings`.
- [x] `src/multi_agent_market_intelligence/__init__.py` re-exports `create_app` and `app`.
- [x] `tests/unit/test_api_setup.py` marked with `@pytest.mark.issue_21` implements comprehensive tests:
  - Application factory initialization with default and custom settings.
  - Root `GET /` and health probe `GET /health` and `GET /api/v1/health`.
  - End-to-end `POST /api/v1/analyze` workflow execution using `TestClient`.
  - Input validation and rejection (e.g. empty symbols list, negative cash -> HTTP 422).
  - Dependency injection override test (substituting custom or mock orchestrator).
  - OpenAPI schema accessibility (`GET /openapi.json` and `GET /docs`).
  - CORS header validation.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=21` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=21 NAME=fastapi-setup-and-routing
```

### 2. API Configuration & Pydantic Schemas
- **Files**:
  - `src/multi_agent_market_intelligence/api/config.py`
  - `src/multi_agent_market_intelligence/api/schemas.py`
- **Change**: Define `APISettings`, `HealthResponse`, `AnalysisRequest`, `AnalysisResponse`, and `ErrorResponse`.

### 3. Dependency Providers
- **File**: `src/multi_agent_market_intelligence/api/dependencies.py`
- **Change**: Implement `get_settings` and `get_orchestrator` dependency resolvers.

### 4. Modular Routers
- **Files**:
  - `src/multi_agent_market_intelligence/api/routers/health.py`
  - `src/multi_agent_market_intelligence/api/routers/analysis.py`
  - `src/multi_agent_market_intelligence/api/routers/__init__.py`
- **Change**: Implement health probes and multi-agent pipeline analysis endpoints.

### 5. Application Factory & ASGI Entrypoint
- **Files**:
  - `src/multi_agent_market_intelligence/api/app.py`
  - `src/multi_agent_market_intelligence/api/__init__.py`
  - `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Implement `create_app`, configure middleware/exception handlers, and expose package exports.

### 6. API Unit & Routing Tests
- **File**: `tests/unit/test_api_setup.py`
- **Change**: Implement test suite tagged with `@pytest.mark.issue_21` verifying all endpoints, validations, and dependency overrides.

### 7. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=21
make test
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=21 MSG="feat(api): implement FastAPI setup, routing, and orchestrator analysis endpoints"
```

## Decisions
- **Application Factory Pattern (`create_app`)**: Allows cleanly instantiated FastAPI instances with custom configurations for production, unit testing, and container environments without shared global state.
- **Dual Health Endpoints**: Both `/health` (standard for Docker / Kubernetes liveness and readiness probes) and `/api/v1/health` (versioned namespace) are provided.
- **FastAPI Dependency Injection for Orchestration**: Wiring `MarketIntelligenceOrchestrator` through `Depends(get_orchestrator)` enables clean decoupling, lazy initialization, and direct testing overrides via `app.dependency_overrides`.
- **Domain-Aligned Schema Wrapping**: Analysis request and response schemas directly leverage existing Pydantic domain models (`TradingSignal`, `RiskDecision`, `PortfolioSnapshot`, `AgentExecutionRecord`), ensuring consistent serialization without duplicate model definitions.
