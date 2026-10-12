# Issue 19: Risk & Portfolio Manager Execution Flow

**Branch**: `feature/issue-19-risk-portfolio-manager-execution-flow`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #20)
**Milestone**: M4 - Risk & Portfolio Manager Implementation

## Objective
Implement the autonomous `RiskPortfolioManagerAgent` uniting risk limits configuration (Issue 16), portfolio state tracking (Issue 17), and signal validation logic (Issue 18) into a unified multi-agent execution flow. Subclassing `BaseAgent`, the `RiskPortfolioManagerAgent` ingests `MarketIntelligenceState`, extracts candidate `TradingSignal`s emitted by the Trading Analyst, synchronizes and hydrates active portfolio balance sheet state (`PortfolioTracker` and `PortfolioSnapshot`), executes rigorous multi-factor risk validation via `SignalRiskValidator`, optionally simulates and updates portfolio holdings and cash balances, appends typed `RiskDecision`s adhering to state channel reducers (`append_decisions`), broadcasts `RISK_EVALUATION` notifications across the `MessageBus`, and provides an orchestrator node handler adapter completing the full 3-agent LangGraph workflow DAG (`research` → `trading_analyst` → `risk_manager`).

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/risk/agent.py` implements `RiskPortfolioManagerAgent(BaseAgent)` (with alias `RiskManagerAgent`):
  - Constructor initialization:
    - `config: AgentConfig | None = None` (default role `AgentRole.RISK_MANAGER`, name `"RiskPortfolioManager"`, capabilities `["risk_limits_validation", "portfolio_state_tracking", "position_sizing", "decision_dispatch"]`)
    - `message_bus: MessageBus | None = None`
    - `validator: SignalRiskValidator | None = None`
    - `tracker: PortfolioTracker | None = None`
    - `auto_execute_trades: bool = True` (if True, executes approved/modified trades in tracker to update portfolio cash and position holdings)
    - `sector_mappings: dict[str, str] | None = None`
  - Core execution flow:
    - `process(state: MarketIntelligenceState) -> dict[str, Any]`:
      1. Ingests signals from `state.get("signals", [])` or `context.get("signals", [])`.
      2. Hydrates or synchronizes portfolio state from `state.get("portfolio")` into `PortfolioTracker`.
      3. Resolves market prices and sector mappings from state context or signal indicators.
      4. Executes batch signal validation via `validator.validate_signals_batch(...)` with cumulative capacity tracking.
      5. When `auto_execute_trades` is True, updates tracker positions and cash for approved and modified BUY/SELL trades.
      6. Generates updated `PortfolioSnapshot` from tracker (`tracker.create_snapshot()`).
      7. Broadcasts `RISK_EVALUATION` messages over `MessageBus` to recipient `"orchestrator"` with approval metrics and correlation IDs.
      8. Returns state update dict with `decisions`, `portfolio`, `current_step="risk_manager"`, `messages`, and context telemetry.
    - `process_async(state: MarketIntelligenceState) -> dict[str, Any]`:
      Provides asynchronous execution parity.
    - Node handler factory:
      `create_risk_manager_node_handler(agent: RiskPortfolioManagerAgent | None = None) -> NodeHandler`:
      Returns a callable adapter compatible with `MarketIntelligenceOrchestrator` and LangGraph DAG execution.
- [x] `src/multi_agent_market_intelligence/risk/__init__.py` exposes `RiskPortfolioManagerAgent`, `RiskManagerAgent`, and `create_risk_manager_node_handler`.
- [x] `src/multi_agent_market_intelligence/agents/__init__.py` re-exports `RiskPortfolioManagerAgent` and `RiskManagerAgent`.
- [x] `src/multi_agent_market_intelligence/__init__.py` re-exports `RiskPortfolioManagerAgent`, `RiskManagerAgent`, and `create_risk_manager_node_handler`.
- [x] Unit tests in `tests/unit/test_risk_manager_agent.py` tagged with `@pytest.mark.issue_19` covering:
  - Agent initialization with default and custom tools/config.
  - End-to-end `process` execution for single and batch signals.
  - Signal evaluation into `RiskDecision` (APPROVED, MODIFIED, REJECTED) with telemetry.
  - Dynamic portfolio hydration from `state["portfolio"]` (`PortfolioSnapshot` and raw dict).
  - Auto-execution updating internal `PortfolioTracker` cash balances and active positions.
  - Message broadcasting to `MessageBus` (`RISK_EVALUATION`) with correlation IDs.
  - Automated audit execution record tracking (`AgentExecutionRecord`) via template `execute(state)`.
  - Standalone node handler adapter execution.
  - Full 3-node LangGraph orchestrator DAG execution (`research` → `trading_analyst` → `risk_manager`).
  - Defensive error handling: empty signals list, missing portfolio, graceful fallbacks.
  - Asynchronous `process_async` execution.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=19` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=19 NAME=risk-portfolio-manager-execution-flow
```

### 2. Autonomous Risk & Portfolio Manager Agent
- **File**: `src/multi_agent_market_intelligence/risk/agent.py`
- **Change**: Implement `RiskPortfolioManagerAgent(BaseAgent)`:
  - Constructor accepting `config`, `message_bus`, `validator`, `tracker`, `auto_execute_trades`, `sector_mappings`.
  - Signal resolution and portfolio hydration helpers.
  - Synchronous `process(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Asynchronous `process_async(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Factory adapter `create_risk_manager_node_handler(agent: RiskPortfolioManagerAgent | None = None) -> NodeHandler`.

### 3. Package Exports
- **File**: `src/multi_agent_market_intelligence/risk/__init__.py`
- **Change**: Export `RiskPortfolioManagerAgent`, `RiskManagerAgent`, and `create_risk_manager_node_handler`.
- **File**: `src/multi_agent_market_intelligence/agents/__init__.py`
- **Change**: Re-export `RiskPortfolioManagerAgent` and `RiskManagerAgent`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `RiskPortfolioManagerAgent`, `RiskManagerAgent`, and `create_risk_manager_node_handler`.

### 4. Unit Testing
- **File**: `tests/unit/test_risk_manager_agent.py`
- **Change**: Implement comprehensive test suite tagged with `@pytest.mark.issue_19`:
  - `test_risk_manager_agent_initialization_defaults_and_custom`
  - `test_risk_manager_agent_process_single_signal`
  - `test_risk_manager_agent_process_batch_signals`
  - `test_risk_manager_agent_portfolio_hydration_from_state`
  - `test_risk_manager_agent_auto_execute_trades_updates_tracker`
  - `test_risk_manager_agent_message_bus_evaluation_broadcast`
  - `test_risk_manager_agent_audit_execution_record_tracking`
  - `test_risk_manager_agent_node_handler_adapter_execution`
  - `test_risk_manager_agent_full_three_node_dag_pipeline`
  - `test_risk_manager_agent_defensive_handling_empty_signals`
  - `test_risk_manager_agent_async_execution`

### 5. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=19
make test
```

### 6. Git & Issue Finish
```bash
make finish-issue ID=19 MSG="feat(risk): implement RiskPortfolioManager agent execution flow and orchestrator adapter"
```

## Decisions
- **Full Three-Node DAG Integration**: With `create_risk_manager_node_handler()`, the orchestrator completes the primary system loop: Research Agent extracts market intelligence → Trading Analyst computes technicals/signals → Risk Manager validates boundaries and manages portfolio capital.
- **Bi-Directional Balance Sheet Synchronization**: The agent accepts existing portfolio snapshots from prior workflow steps, dynamically hydrates a `PortfolioTracker`, updates positions for approved orders, and exports an updated `PortfolioSnapshot` into `state["portfolio"]`.
- **Configurable Auto-Execution**: To support both pure pre-trade validation (decision emission only) and active portfolio rebalancing, `auto_execute_trades` allows toggling whether approved orders immediately mutate tracker cash and position holdings.
- **Event-Driven Audit Notification**: In addition to appending `RiskDecision` records to state channels, the agent broadcasts structured `RISK_EVALUATION` messages across `MessageBus` to `recipient="orchestrator"`, providing centralized event tracing with correlation IDs.
