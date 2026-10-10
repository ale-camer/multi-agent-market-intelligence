# Issue 1: Orchestrator Base Class and DAG Design

**Branch**: `feature/issue-1-orchestrator-base-dag`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #1)
**Milestone**: M1 - Core Infrastructure & Orchestrator Setup

## Objective
Design and implement the foundation of the central multi-agent orchestrator using LangGraph. This encompasses an extensible abstract base orchestrator (`BaseOrchestrator`), an initial execution state schema, and the core Directed Acyclic Graph (DAG) workflow topology that sequences the Research Agent, Trading Analyst, and Risk & Portfolio Manager nodes with lifecycle compilation and execution capabilities.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/orchestrator/base.py` defines `BaseOrchestrator` abstract class with lifecycle contract (`build_graph`, `compile`, `run`, `invoke`).
- [x] `src/multi_agent_market_intelligence/orchestrator/schema.py` defines baseline `OrchestratorState` TypedDict and node handler type aliases.
- [x] `src/multi_agent_market_intelligence/orchestrator/graph.py` defines `MarketIntelligenceOrchestrator` constructing the sequential DAG topology (`START -> research -> trading_analyst -> risk_manager -> END`) using LangGraph `StateGraph`.
- [x] Pluggable node handler registration supporting default passthroughs and custom callable handler injection.
- [x] Graph compilation validation verifying valid graph build, node connectivity, and execution integrity without cycles.
- [x] Clean package exports in `src/multi_agent_market_intelligence/orchestrator/__init__.py`.
- [x] Unit tests in `tests/unit/test_orchestrator.py` marked with `@pytest.mark.issue_1` validating base contract enforcement, DAG compilation, execution path, custom node overrides, and error handling.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=1` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=1 NAME=orchestrator-base-dag
```

### 2. Base Orchestrator Abstract Class
- **File**: `src/multi_agent_market_intelligence/orchestrator/base.py`
- **Change**: Define `BaseOrchestrator[StateT]` as an abstract base class (`ABC`) inheriting from `Generic[StateT]`. Declare abstract methods `build_graph() -> StateGraph`, `compile() -> Any`, and execution methods `run(initial_state: StateT) -> StateT`. Include state validation and graph compilation status guards.

### 3. State & Node Handler Interfaces
- **File**: `src/multi_agent_market_intelligence/orchestrator/schema.py`
- **Change**: Define baseline `OrchestratorState` (`TypedDict`) with fields (`messages`, `context`, `signals`, `decisions`, `current_step`, `errors`) providing initial structure until Issue 2 state management protocol. Define `NodeHandler` type alias.

### 4. Market Intelligence DAG Implementation
- **File**: `src/multi_agent_market_intelligence/orchestrator/graph.py`
- **Change**: Implement `MarketIntelligenceOrchestrator(BaseOrchestrator[OrchestratorState])`. Construct the standard DAG topology linking:
  - `START` -> `research`
  - `research` -> `trading_analyst`
  - `trading_analyst` -> `risk_manager`
  - `risk_manager` -> `END`
  Support configurable node handlers for research, trading analysis, and risk management with deterministic default passthrough behaviors.

### 5. Package Exports
- **File**: `src/multi_agent_market_intelligence/orchestrator/__init__.py`
- **Change**: Export `BaseOrchestrator`, `MarketIntelligenceOrchestrator`, `OrchestratorState`, and `NodeNames` constants.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Expose orchestrator module exports.

### 6. Unit Testing
- **File**: `tests/unit/test_orchestrator.py`
- **Change**: Implement comprehensive unit tests tagged with `@pytest.mark.issue_1`:
  - Enforce `BaseOrchestrator` abstract class instantiation prevention.
  - Verify DAG compilation and LangGraph `StateGraph` structure.
  - Verify execution flow sequentially invoking `research -> trading_analyst -> risk_manager`.
  - Verify custom node handler overrides updating state correctly.
  - Verify error handling when invalid states or failed nodes are processed.

### 7. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=1
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=1 MSG="feat(orchestrator): implement base orchestrator and dag design"
```

## Decisions
- **LangGraph StateGraph as DAG engine**: Use `langgraph.graph.StateGraph` as the core execution graph backend to satisfy architecture requirements and enable robust multi-agent orchestration.
- **Generic BaseOrchestrator**: Parameterize `BaseOrchestrator` by generic `StateT` so that Issue 2 (State management protocol) can easily introduce custom state protocols or Pydantic models without refactoring the base interface.
- **Pluggable Node Handlers**: Nodes in `MarketIntelligenceOrchestrator` default to lightweight functional passthroughs while allowing explicit injection of custom functions or agent instances, paving the way for Issue 4 (`Base Agent interface`).
- **Separation of Concerns**: Keep base class (`base.py`), schemas (`schema.py`), and concrete graph topology (`graph.py`) modularized within `src/multi_agent_market_intelligence/orchestrator/`.
