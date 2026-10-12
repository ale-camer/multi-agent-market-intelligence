# Issue 22: API Endpoints for Portfolio

**Branch**: `feature/issue-22-api-endpoints-for-portfolio`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #22)
**Milestone**: M5 - FastAPI API, Integration & Delivery

## Objective
Implement dedicated RESTful API endpoints for real-time portfolio management, balance sheet accounting, position tracking, cash deposits/withdrawals, manual trade execution, and quantitative risk telemetry under `/api/v1/portfolio`. Connect the endpoints to a thread-safe, dependency-injected `PortfolioTracker` instance, expanding the FastAPI web tier constructed in Issue 21 and preparing the system for containerized delivery (Issue 23).

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/api/schemas.py` extends domain schemas with:
  - `PortfolioStateResponse`: summary of active portfolio state, liquid cash, total equity, gross/net exposure, leverage ratio, drawdown percentage, daily/unrealized/realized PnL, active position count, and positions map.
  - `CashTransactionRequest`: `amount: float = Field(gt=0.0)` for deposit and withdrawal requests.
  - `CashTransactionResponse`: transaction type (`"DEPOSIT"` / `"WITHDRAWAL"`), amount, updated cash, total equity, and UTC timestamp.
  - `TradeExecutionRequest`: `symbol: str` (non-empty uppercase), `action: SignalAction`, `quantity: float = Field(gt=0.0)`, `price: float = Field(gt=0.0)`, `commission: float = Field(default=0.0, ge=0.0)`.
  - `TradeExecutionResponse`: trade execution confirmation with symbol, action, quantity, price, total cost, realized PnL, commission, and UTC timestamp.
  - `PositionsListResponse`: `positions: list[Position]`, `total_positions: int`.
  - `TradeHistoryResponse`: `history: list[TradeExecution]`, `total_trades: int`.
  - `PortfolioResetRequest`: optional `initial_cash: float = Field(default=100_000.0, gt=0.0)`.
- [x] `src/multi_agent_market_intelligence/api/dependencies.py` implements:
  - `get_portfolio_tracker() -> PortfolioTracker`: dependency provider supplying singleton/stateful portfolio accounting tracker, customizable via `app.dependency_overrides`.
- [x] `src/multi_agent_market_intelligence/api/routers/portfolio.py` implements:
  - `GET /api/v1/portfolio`: returns current `PortfolioStateResponse`.
  - `GET /api/v1/portfolio/positions`: returns `PositionsListResponse` containing all currently open positions.
  - `GET /api/v1/portfolio/positions/{symbol}`: returns `Position` domain model for requested symbol; raises HTTP 404 if symbol is not currently held.
  - `GET /api/v1/portfolio/metrics`: returns `PortfolioMetrics` model with full quantitative risk indicators.
  - `GET /api/v1/portfolio/history`: returns `TradeHistoryResponse` with chronological trade audit logs.
  - `POST /api/v1/portfolio/deposit`: ingests `CashTransactionRequest`, deposits cash into tracker, returns `CashTransactionResponse`.
  - `POST /api/v1/portfolio/withdraw`: ingests `CashTransactionRequest`, withdraws cash from tracker (raises HTTP 400 on overdraft attempt), returns `CashTransactionResponse`.
  - `POST /api/v1/portfolio/trade`: ingests `TradeExecutionRequest`, executes trade transaction on tracker (raises HTTP 400 on invalid trade or selling non-held units), returns `TradeExecutionResponse`.
  - `POST /api/v1/portfolio/reset`: re-initializes tracker with given `initial_cash`, returns updated `PortfolioStateResponse`.
- [x] `src/multi_agent_market_intelligence/api/routers/__init__.py`:
  - Mounts `portfolio_router` onto `api_v1_router` under prefix `/portfolio`.
- [x] `src/multi_agent_market_intelligence/api/__init__.py`:
  - Re-exports portfolio schemas and router components.
- [x] `tests/unit/test_api_portfolio.py` marked with `@pytest.mark.issue_22` implements comprehensive unit tests:
  - Default portfolio inspection (`GET /api/v1/portfolio`).
  - Cash deposit flow (`POST /api/v1/portfolio/deposit`) with balance verification.
  - Cash withdrawal flow (`POST /api/v1/portfolio/withdraw`) and overdraft rejection (HTTP 400).
  - Manual trade execution (`POST /api/v1/portfolio/trade`) for BUY orders, verifying position creation and cash reduction.
  - Active positions listing (`GET /api/v1/portfolio/positions`) and symbol lookup (`GET /api/v1/portfolio/positions/{symbol}`).
  - Position not found error handling (HTTP 404).
  - Manual SELL trade execution verifying cash recovery, position reduction, and realized PnL.
  - Overselling rejection (HTTP 400).
  - Quantitative metrics extraction (`GET /api/v1/portfolio/metrics`).
  - Trade execution audit history (`GET /api/v1/portfolio/history`).
  - Portfolio reset endpoint (`POST /api/v1/portfolio/reset`).
  - Validation rejections (HTTP 422 for non-positive amounts, invalid actions, or empty symbols).
  - Dependency injection override test for isolated testing.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=22` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=22 NAME=api-endpoints-for-portfolio
```

### 2. Portfolio Pydantic Schemas
- **File**: `src/multi_agent_market_intelligence/api/schemas.py`
- **Change**: Define `PortfolioStateResponse`, `CashTransactionRequest`, `CashTransactionResponse`, `TradeExecutionRequest`, `TradeExecutionResponse`, `PositionsListResponse`, `TradeHistoryResponse`, and `PortfolioResetRequest`.

### 3. Portfolio Dependency Provider
- **File**: `src/multi_agent_market_intelligence/api/dependencies.py`
- **Change**: Implement `get_portfolio_tracker()` dependency provider with state management.

### 4. Portfolio Router Endpoints
- **Files**:
  - `src/multi_agent_market_intelligence/api/routers/portfolio.py`
  - `src/multi_agent_market_intelligence/api/routers/__init__.py`
- **Change**: Implement state inspection, position management, cash operations, manual trading, metrics, and audit history endpoints; mount under `/portfolio`.

### 5. Package Exports
- **File**: `src/multi_agent_market_intelligence/api/__init__.py`
- **Change**: Re-export portfolio schemas and router artifacts.

### 6. Portfolio API Test Suite
- **File**: `tests/unit/test_api_portfolio.py`
- **Change**: Implement unit and integration tests tagged with `@pytest.mark.issue_22` covering all endpoints, edge cases, and status codes.

### 7. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=22
make test
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=22 MSG="feat(api): implement portfolio state, positions, cash, and trade execution endpoints"
```

## Decisions
- **Unified Portfolio Engine Integration**: Reuses existing production `PortfolioTracker`, `PortfolioMetrics`, `TradeExecution`, and `Position` domain models from M4 without redundant logic or schema drift.
- **Atomic Cash & Trade Operations**: Validates withdrawals against liquid cash reserves and SELL trades against currently held quantities before modifying portfolio state, returning clear HTTP 400 Bad Request messages on violations.
- **RESTful Resource Hierarchy**: Positions are structured as sub-resources (`/api/v1/portfolio/positions` and `/api/v1/portfolio/positions/{symbol}`) providing standard 404 responses when an asset is not actively open.
- **Dependency Inversion for Isolated Testing**: Uses `get_portfolio_tracker` provider allowing isolated in-memory testing via `app.dependency_overrides[get_portfolio_tracker]` without cross-test state leakage.
