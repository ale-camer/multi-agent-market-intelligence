# Issue 10: Research Agent Mock Tests

**Branch**: `feature/issue-10-research-agent-mock-tests`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #11)
**Milestone**: M2 - Research Agent Implementation

## Objective
Establish a dedicated mock test suite and edge-case testing harness for the `ResearchAgent`. Validate end-to-end intelligence extraction, network fault isolation (timeouts, HTTP 500, malformed HTML), multi-format filing ingestion, market sentiment extremes (bullish consensus, crisis bearish, conflicting/mixed signals), asynchronous execution, and multi-cycle LangGraph DAG orchestration integration. This completes Milestone 2 (Research Agent Implementation).

## Acceptance Criteria
- [x] `tests/unit/test_research_agent_mocks.py` marked with `@pytest.mark.issue_10` implements:
  - **Network & Provider Fault Isolation**: Mocked HTTP GET sessions simulating server 500 errors, network timeouts, malformed payloads, and partial HTML, verifying graceful error degradation.
  - **Multi-Format Filing Ingestion**: Testing report loading from dynamic directories with varied formats (JSON, TXT, HTML) and edge cases (missing sections, corrupt keys).
  - **Sentiment Extremes & Mixed Signals**:
    - Unanimous Bullish scenario (all positive news & disclosures).
    - Crisis Bearish scenario (guidance cuts, litigation, fraud, debt defaults).
    - Conflicting/Mixed signals (positive headline results counteracted by cautionary forward risk disclosures).
    - Neutral/Low-confidence baseline.
  - **MessageBus Event Broadcasting**: Verification of `RESEARCH_REPORT` message dispatch with correlation IDs and complete composite payloads to downstream subscribers.
  - **Orchestrator DAG Integration**: Full multi-cycle LangGraph execution with real `ResearchAgent` connected via `create_research_node_handler()`, verifying artifact accumulation via `append_artifacts` without state mutation bugs.
  - **Asynchronous Execution Flow**: Testing `execute_async` under mock loads.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=10` pass cleanly.
- [x] Full test suite (`make test`) passes without regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=10 NAME=research-agent-mock-tests
```

### 2. Research Agent Mock Test Harness
- **File**: `tests/unit/test_research_agent_mocks.py`
- **Change**: Implement exhaustive test suite tagged with `@pytest.mark.issue_10`:
  - `test_research_agent_mock_http_network_errors`: tests HTTP 500, timeout, and connection errors with mocked session.
  - `test_research_agent_mock_malformed_html`: tests extracting from HTML with missing tags, broken body, or script-heavy tracking.
  - `test_research_agent_bullish_consensus_scenario`: simulates strong positive news and filing metrics, asserting bullish composite score.
  - `test_research_agent_crisis_bearish_scenario`: simulates severe headwinds, downgrades, and debt risks, asserting bearish composite score.
  - `test_research_agent_conflicting_signals_scenario`: simulates positive earnings beat combined with negative guidance, verifying balanced synthesis.
  - `test_research_agent_mock_filings_directory`: loads multiple mock filings from temporary directory with mixed formats.
  - `test_research_agent_message_bus_delivery_with_correlation`: verifies downstream inbox reception with preserved correlation IDs.
  - `test_research_agent_orchestrator_multi_cycle_dag`: runs compiled `MarketIntelligenceOrchestrator` across multiple cycles with real ResearchAgent.
  - `test_research_agent_execute_async_flow`: tests asynchronous execution lifecycle.

### 3. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=10
make test
```

### 4. Git & Issue Finish
```bash
make finish-issue ID=10 MSG="test(research): implement comprehensive mock tests and edge case harness for ResearchAgent"
```

## Decisions
- **100% Deterministic Offline Testing**: External network requests are mocked using `unittest.mock` and local file fixtures (`tmp_path`) to ensure zero reliance on third-party APIs and rapid test execution.
- **Mixed Signals Modeling**: Financial markets frequently produce conflicting intelligence (e.g. revenue beat paired with negative forward guidance); explicitly validating these edge cases ensures realistic sentiment resolution.
- **End-to-End DAG Multi-Cycle Validation**: Testing the real `ResearchAgent` within the LangGraph orchestrator confirms that state channels, reducers, and audit records operate seamlessly, providing high confidence for Milestone 2 closure.
