# Issue 20: Risk Manager Integration Tests

**Branch**: `feature/issue-20-risk-manager-integration-tests`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #21)
**Milestone**: M4 - Risk & Portfolio Manager Implementation

## Objective
Establish a comprehensive end-to-end integration and stress testing suite for the Risk & Portfolio Manager components, closing Milestone 4 (Risk & Portfolio Manager Implementation). Validate the unified multi-agent orchestrator pipeline (`research` → `trading_analyst` → `risk_manager`) using real production agents and adapters, multi-cycle trading and portfolio balance sheet evolution, multi-factor risk boundary enforcement (circuit breakers, drawdown limits, daily loss limits, sector concentration ceilings, cash reserve buffers, gross leverage caps, concurrent position limits), inter-agent message broadcasting via `MessageBus` with correlation ID propagation, corrupted/degenerate signal resilience, and concurrent asynchronous DAG execution.

## Acceptance Criteria
- [x] `tests/integration/test_risk_manager_integration.py` marked with `@pytest.mark.issue_20` implements:
  - **End-to-End Real Agent Pipeline Integration**:
    - Full 3-node DAG execution (`MarketIntelligenceOrchestrator`) powered by real agent handlers (`create_research_node_handler`, `create_trading_analyst_node_handler`, `create_risk_manager_node_handler`).
    - Verifies complete lifecycle: news/sentiment research extraction → technical/fundamental signal generation → risk validation and portfolio position execution.
    - Validates state reducers across channels: `artifacts`, `signals`, `decisions`, `portfolio`, `messages`, and `records`.
  - **Multi-Cycle Trading & Balance Sheet Evolution**:
    - Multi-session execution across sequential trading cycles (Day 1: entry BUY → Day 2: price update & scaling → Day 3: take-profit SELL liquidation).
    - Verifies weighted average entry prices, realized/unrealized PnL, cash credits/debits, and `PortfolioSnapshot` consistency across cycles.
  - **Multi-Factor Risk Boundary Enforcement in Orchestrator**:
    - Circuit Breaker Activation: halts new orders and returns `CIRCUIT_BREAKER_ACTIVE` rejections across the pipeline.
    - Max Drawdown Breach: restricts new risk accumulation (`MAX_PORTFOLIO_DRAWDOWN_EXCEEDED`) while safely permitting liquidation/de-risking SELL orders.
    - Max Daily Loss Exceeded: halts trading session upon breaching daily loss limits (`MAX_DAILY_LOSS_EXCEEDED`).
    - Sector Concentration Limit: clamps or modifies orders when multi-asset allocations in a shared sector reach `max_sector_exposure_pct`.
    - Cash Reserve Buffer: clamps BUY order sizing to preserve minimum required liquid cash buffer (`min_cash_buffer_pct`).
    - Gross Leverage Cap: limits position expansion to respect maximum allowable leverage ratio (`max_leverage`).
    - Concurrent Positions Cap: rejects BUY orders for new assets once open position slots reach `max_open_positions`.
  - **Inter-Agent Event Communication & Message Bus Flow**:
    - Shared `MessageBus` verifying event flow across nodes: `RESEARCH_REPORT` → `SIGNAL_PROPOSAL` → `RISK_EVALUATION`.
    - Asserts correlation ID persistence and structured payload integrity throughout the message chain.
  - **Degenerate Signal & Anomaly Resilience**:
    - Ingests invalid, missing, or geometrically inverted signals without unhandled exceptions.
    - Empty context, missing market prices, or zero-confidence signal fallbacks.
  - **Asynchronous Execution & Concurrency**:
    - Validates asynchronous execution (`arun` / `ainvoke`) under concurrent multi-agent pipeline invocations.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=20` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=20 NAME=risk-manager-integration-tests
```

### 2. Risk Manager Integration Test Suite
- **File**: `tests/integration/test_risk_manager_integration.py`
- **Change**: Implement comprehensive integration test suite tagged with `@pytest.mark.issue_20`:
  - `test_risk_manager_e2e_three_agent_pipeline_success`
  - `test_risk_manager_multi_cycle_trading_portfolio_evolution`
  - `test_risk_manager_circuit_breaker_pipeline_rejection`
  - `test_risk_manager_drawdown_limit_pipeline_veto`
  - `test_risk_manager_daily_loss_limit_pipeline_veto`
  - `test_risk_manager_sector_concentration_limit_scaling`
  - `test_risk_manager_cash_buffer_reserve_protection`
  - `test_risk_manager_gross_leverage_cap_protection`
  - `test_risk_manager_concurrent_positions_cap_rejection`
  - `test_risk_manager_message_bus_inter_agent_event_flow`
  - `test_risk_manager_corrupted_signal_resilience`
  - `test_risk_manager_pipeline_async_execution`

### 3. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=20
make test
```

### 4. Git & Issue Finish
```bash
make finish-issue ID=20 MSG="test(risk): implement comprehensive integration tests closing Milestone 4"
```

## Decisions
- **Full Production Component Wiring**: Tests assemble genuine production agent instances (`ResearchAgent`, `TradingAnalystAgent`, `RiskPortfolioManagerAgent`) rather than mocks, providing true end-to-end integration validation across all Milestone 2, 3, and 4 deliverables.
- **Realistic Multi-Cycle Portfolio State Progression**: Sequential multi-cycle pipeline invocations verify state channel reducers and balance sheet mark-to-market accuracy across market sessions without state leakage or reset.
- **Comprehensive Boundary Stress Testing**: Tests verify both active and defensive enforcement: hard rejections when limits are violated, proportional scaling when capacity allows partial fills, and unblocked liquidation flows when de-risking during distress.
