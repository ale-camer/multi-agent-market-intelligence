# Issue 14: Trading Analyst Execution Flow

**Branch**: `feature/issue-14-trading-analyst-execution-flow`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #15)
**Milestone**: M3 - Trading Analyst Implementation

## Objective
Implement the autonomous `TradingAnalystAgent` uniting technical indicator calculations (Issue 11), fundamental data loading (Issue 12), and signal generation (Issue 13) into an end-to-end multi-agent execution flow. Subclassing `BaseAgent`, the `TradingAnalystAgent` ingests `MarketIntelligenceState`, resolves research artifacts and sentiment from the Research Agent (Milestone 2), executes quantitative and qualitative evaluations per target symbol, produces strongly-typed `TradingSignal`s adhering to state channel reducers (`append_signals`), broadcasts `SIGNAL_PROPOSAL` notifications across the `MessageBus`, and provides an orchestrator node handler adapter for seamless LangGraph DAG execution.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/trading/agent.py` implements `TradingAnalystAgent(BaseAgent)`:
  - Initializes with configurable `AgentConfig` (default role `AgentRole.TRADING_ANALYST`, name `"TradingAnalyst"`), `MessageBus`, `TechnicalIndicatorsCalculator`, `FundamentalDataLoader`, `TradingSignalGenerator`, and default `symbols`.
  - Implements `process(state: MarketIntelligenceState) -> dict[str, Any]` executing the full trading analysis lifecycle:
    1. Resolves target symbols from state context (or defaults).
    2. Ingests sentiment from state `artifacts` produced by the Research Agent.
    3. Retrieves or computes technical indicators (`TechnicalIndicatorsResult`) for each symbol.
    4. Retrieves or loads fundamental corporate metrics (`FundamentalMetrics`) for each symbol.
    5. Generates typed `TradingSignal`s via `TradingSignalGenerator`.
    6. Publishes `SIGNAL_PROPOSAL` messages over `MessageBus` to `recipient="risk_manager"`.
    7. Returns state update dict with `signals`, `current_step="trading_analyst"`, `messages`, and context enrichment.
  - Implements `process_async(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Provides `create_trading_analyst_node_handler(agent: TradingAnalystAgent | None = None)` producing a callable `NodeHandler` compatible with `MarketIntelligenceOrchestrator`.
- [x] `src/multi_agent_market_intelligence/trading/__init__.py` exposes `TradingAnalystAgent` and `create_trading_analyst_node_handler`.
- [x] `src/multi_agent_market_intelligence/agents/__init__.py` and `src/multi_agent_market_intelligence/__init__.py` re-export `TradingAnalystAgent` and `create_trading_analyst_node_handler`.
- [x] Unit tests in `tests/unit/test_trading_analyst_agent.py` tagged with `@pytest.mark.issue_14` validating:
  - Agent initialization with default and custom tools/config.
  - End-to-end `process` execution for single and multiple symbols.
  - Integration with Research Agent sentiment artifacts from state.
  - Message broadcasting to `MessageBus` with correlation IDs.
  - Audit logging via template `execute(state)` producing `AgentExecutionRecord`.
  - Standalone node handler adapter execution.
  - Multi-agent LangGraph orchestrator DAG execution (`research` -> `trading_analyst`).
  - Error isolation: empty context, missing market data, graceful fallbacks.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=14` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=14 NAME=trading-analyst-execution-flow
```

### 2. Autonomous Trading Analyst Agent
- **File**: `src/multi_agent_market_intelligence/trading/agent.py`
- **Change**: Implement `TradingAnalystAgent(BaseAgent)`:
  - Constructor accepting `config`, `message_bus`, `indicators_calculator`, `fundamental_loader`, `signal_generator`, `symbols`.
  - Sentiment resolution helper `_extract_symbol_sentiment(artifacts, symbol)`.
  - Synchronous `process(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Asynchronous `process_async(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Factory adapter `create_trading_analyst_node_handler(agent: TradingAnalystAgent | None = None) -> Callable[[OrchestratorState], dict[str, Any]]`.

### 3. Package Exports
- **File**: `src/multi_agent_market_intelligence/trading/__init__.py`
- **Change**: Export `TradingAnalystAgent` and `create_trading_analyst_node_handler`.
- **File**: `src/multi_agent_market_intelligence/agents/__init__.py`
- **Change**: Re-export `TradingAnalystAgent`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `TradingAnalystAgent` and `create_trading_analyst_node_handler`.

### 4. Unit Testing
- **File**: `tests/unit/test_trading_analyst_agent.py`
- **Change**: Implement comprehensive test suite tagged with `@pytest.mark.issue_14`:
  - `test_trading_analyst_initialization_defaults_and_custom`
  - `test_trading_analyst_process_single_symbol`
  - `test_trading_analyst_process_multiple_symbols`
  - `test_trading_analyst_ingests_research_sentiment_artifacts`
  - `test_trading_analyst_message_bus_signal_proposal_broadcast`
  - `test_trading_analyst_audit_execution_record_tracking`
  - `test_trading_analyst_node_handler_adapter_execution`
  - `test_trading_analyst_orchestrator_multi_node_dag_pipeline`
  - `test_trading_analyst_defensive_error_handling_empty_context`
  - `test_trading_analyst_async_execution`

### 5. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=14
make test
```

### 6. Git & Issue Finish
```bash
make finish-issue ID=14 MSG="feat(trading): implement TradingAnalyst agent execution flow and orchestrator adapter"
```

## Decisions
- **Cross-Agent Intelligence Synthesis**: `TradingAnalystAgent` inspects `state.get("artifacts", [])` to locate `ResearchArtifact`s from the Research Agent, calculating net symbol sentiment to inform and weight signal generation.
- **Event-Driven Signal Dispatching**: In addition to appending `TradingSignal`s directly to state channels, the agent publishes `SIGNAL_PROPOSAL` messages via `MessageBus` to `risk_manager`, creating an explicit event trail with correlation IDs.
- **Dual Execution Modality**: The agent supports direct invocation via `execute(state)` (with automated audit timing and `AgentExecutionRecord` logging) and compiled LangGraph DAG execution via `create_trading_analyst_node_handler()`.
- **Autonomous Fallback Data Generation**: In offline, testing, or development environments where external market feeds are absent, the agent seamlessly leverages `generate_mock_ohlcv()` and `fetch_fundamentals()` to avoid pipeline failures while preserving determinism.
