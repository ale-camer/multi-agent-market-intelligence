# Issue 5: Orchestrator Integration Tests Setup

**Branch**: `feature/issue-5-orchestrator-integration-tests`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #6)
**Milestone**: M1 - Core Infrastructure & Orchestrator Setup

## Objective
Establish the integration testing harness and end-to-end multi-agent pipeline test suite in `tests/integration/`. Validate seamless integration between the LangGraph Orchestrator, State Management Protocol, MessageBus, and BaseAgent abstractions across full market intelligence cycles, error recovery scenarios, and sequential paper trading portfolio updates.

## Acceptance Criteria
- [x] `tests/integration/conftest.py` provides shared fixtures for `MessageBus`, pipeline mock agents (Research, Trading Analyst, Risk Manager), and initial portfolio state.
- [x] `tests/integration/test_orchestrator_pipeline.py` implements end-to-end multi-agent integration tests:
  - Full execution pipeline (`research -> trading_analyst -> risk_manager`).
  - Validation of state reducers preserving artifacts, signals, decisions, and execution records.
  - End-to-end message passing via `MessageBus` verifying correlation ID preservation.
  - Sequential multi-cycle execution demonstrating portfolio state evolution.
- [x] `tests/integration/test_pipeline_resilience.py` tests resilience and edge cases:
  - Partial agent failure handling without pipeline crashing.
  - Concurrent orchestrator executions across multiple symbols without state cross-talk.
  - Empty or unexpected payload validation.
- [x] All integration tests marked with `@pytest.mark.issue_5`.
- [x] `make test-integration`, `make test-issue ID=5`, and `make check` pass cleanly.
- [x] Closes Issue 5 and completes Milestone 1 (`M1 - Core Infrastructure & Orchestrator Setup`).

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=5 NAME=orchestrator-integration-tests
```

### 2. Integration Test Fixtures & Harness
- **File**: `tests/integration/conftest.py`
- **Change**: Define reusable pytest fixtures:
  - `shared_bus`: a clean `MessageBus` instance.
  - `simulated_research_agent`: `BaseAgent` simulating news retrieval and publishing `RESEARCH_REPORT`.
  - `simulated_analyst_agent`: `BaseAgent` analyzing sentiment/indicators and generating `TradingSignal`.
  - `simulated_risk_agent`: `BaseAgent` validating limits against `PortfolioSnapshot` and creating `RiskDecision`.
  - `configured_orchestrator`: `MarketIntelligenceOrchestrator` with the simulated agents wired in.

### 3. End-to-End Pipeline Integration Tests
- **File**: `tests/integration/test_orchestrator_pipeline.py`
- **Change**: Implement integration tests tagged `@pytest.mark.issue_5`:
  - `test_e2e_market_intelligence_pipeline_success`: verify complete flow generating `ResearchArtifact`, `TradingSignal`, `RiskDecision`, and `AgentExecutionRecord`s in order.
  - `test_e2e_message_bus_correlation_tracking`: verify messages published across nodes share identical `correlation_id` across the bus history.
  - `test_e2e_portfolio_state_multi_cycle_evolution`: execute consecutive pipeline runs and assert portfolio cash, positions, and equity update sequentially.

### 4. Pipeline Resilience & Concurrency Tests
- **File**: `tests/integration/test_pipeline_resilience.py`
- **Change**: Implement resilience tests tagged `@pytest.mark.issue_5`:
  - `test_pipeline_recovers_from_research_failure`: verify downstream agents handle empty research cleanly when research fails.
  - `test_concurrent_orchestrator_runs`: run multiple independent workflows simultaneously with different tickers, verifying state isolation.
  - `test_risk_manager_veto_flow`: verify risk agent rejection halts order sizing and logs clear veto rationale.

### 5. Verification & Quality Gates
```bash
make format
make check
make test-integration
make test-issue ID=5
```

### 6. Git & Issue Finish
```bash
make finish-issue ID=5 MSG="test(orchestration): setup integration test harness and multi-agent pipeline tests"
```

### 7. Milestone 1 Closing
```bash
make finish-milestone MILESTONE=M1
```

## Decisions
- **Simulated Agents over Raw Mocks**: Build realistic simulated `BaseAgent` subclasses for integration testing rather than shallow `unittest.mock.Mock` objects, ensuring the actual `BaseAgent` execution lifecycle, latency timing, and message bus communication are genuinely exercised.
- **Dedicated Resilience Test Suite**: Separate happy-path pipeline tests (`test_orchestrator_pipeline.py`) from fault-tolerance and concurrency tests (`test_pipeline_resilience.py`) for clarity and maintainability.
- **Milestone 1 Completion**: Issue 5 represents the final deliverable of Milestone 1, verifying that all core infrastructure components operate cohesively before implementing specialized agents in Milestone 2.
