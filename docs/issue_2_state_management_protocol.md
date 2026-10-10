# Issue 2: State Management Protocol

**Branch**: `feature/issue-2-state-protocol`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #3)
**Milestone**: M1 - Core Infrastructure & Orchestrator Setup

## Objective
Establish a robust, strongly-typed state management protocol and domain models for the multi-agent system. This protocol provides immutable, auditable state tracking across the Research Agent, Trading Analyst, and Risk & Portfolio Manager, featuring Pydantic domain models, LangGraph reducers for deterministic channel merging, and state snapshotting.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/state/models.py` defines strongly typed Pydantic models for domain entities: `ResearchArtifact`, `TradingSignal` (with `SignalAction` enum: BUY, SELL, HOLD), `RiskDecision` (with `DecisionStatus` enum: APPROVED, REJECTED, MODIFIED), `Position`, `PortfolioSnapshot`, and `AgentExecutionRecord`.
- [x] `src/multi_agent_market_intelligence/state/reducers.py` defines deterministic, append-only reducer functions (`add_messages`, `add_signals`, `add_artifacts`, `add_decisions`, `add_records`, `merge_context`) supporting both Pydantic models and dictionaries.
- [x] `src/multi_agent_market_intelligence/state/protocol.py` defines `StateProtocol` specifying state inspection, snapshotting, serialization, and transition validation.
- [x] `src/multi_agent_market_intelligence/state/schema.py` defines the unified `MarketIntelligenceState` TypedDict leveraging `Annotated` reducer channels for LangGraph.
- [x] `src/multi_agent_market_intelligence/state/__init__.py` exposes all public models, schemas, and reducers.
- [x] `src/multi_agent_market_intelligence/orchestrator/` seamlessly adopts `MarketIntelligenceState` while maintaining backward compatibility with `OrchestratorState`.
- [x] `Makefile` updated to use `--head $$BRANCH` in `finish-issue` for reliable GitHub PR automation.
- [x] Unit tests in `tests/unit/test_state.py` marked with `@pytest.mark.issue_2` verifying model validations, reducer merges, serialization/deserialization, protocol compliance, and DAG execution using the new state schema.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=2` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=2 NAME=state-protocol
```

### 2. Makefile Automation Polish
- **File**: `Makefile`
- **Change**: In `finish-issue`, update `gh pr create` to use `--head $$BRANCH` instead of `--head HEAD` to ensure reliable branch resolution in the GitHub CLI.

### 3. Domain State Models
- **File**: `src/multi_agent_market_intelligence/state/models.py`
- **Change**: Implement domain models with strict typing, validation, and JSON serialization:
  - `SignalAction` (StrEnum): `BUY`, `SELL`, `HOLD`.
  - `DecisionStatus` (StrEnum): `APPROVED`, `REJECTED`, `MODIFIED`.
  - `ResearchArtifact`: headline, summary, sentiment score (-1.0 to 1.0), source, timestamp, metadata.
  - `TradingSignal`: symbol, action (`SignalAction`), confidence (0.0 to 1.0), target_price, stop_loss, reasoning, timestamp.
  - `RiskDecision`: status (`DecisionStatus`), original_signal, approved_size, max_loss_limit, reason, timestamp.
  - `Position`: symbol, quantity, entry_price, current_price, unrealized_pnl.
  - `PortfolioSnapshot`: cash, positions, total_equity, margin_used, timestamp.
  - `AgentExecutionRecord`: agent_name, step, status, execution_time_ms, timestamp, logs.

### 4. State Reducers & Channel Merging
- **File**: `src/multi_agent_market_intelligence/state/reducers.py`
- **Change**: Implement deterministic reducers for LangGraph state channels:
  - `append_signals`: appends new signals or converts dicts to `TradingSignal`.
  - `append_artifacts`: appends research artifacts.
  - `append_decisions`: appends risk decisions.
  - `append_records`: appends execution audit records.
  - `merge_dict`: merges dictionary updates shallowly or deeply without data loss.

### 5. State Management Protocol & Schema
- **File**: `src/multi_agent_market_intelligence/state/protocol.py`
- **Change**: Define `StateProtocol` (runtime checkable `typing.Protocol`) requiring `snapshot()`, `to_dict()`, `get_signals()`, `get_decisions()`, and `validate_transition()`.
- **File**: `src/multi_agent_market_intelligence/state/schema.py`
- **Change**: Define `MarketIntelligenceState` TypedDict combining typed domain channels with `Annotated` reducers.

### 6. Orchestrator Integration & Backward Compatibility
- **File**: `src/multi_agent_market_intelligence/orchestrator/schema.py`
- **Change**: Re-export `MarketIntelligenceState` and alias `OrchestratorState` to preserve backward compatibility.
- **File**: `src/multi_agent_market_intelligence/orchestrator/graph.py`
- **Change**: Update default handlers to produce structured domain outputs when processed by `MarketIntelligenceState`.

### 7. Package Exports
- **File**: `src/multi_agent_market_intelligence/state/__init__.py`
- **Change**: Export all public models, reducers, protocols, and schema types.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Expose `MarketIntelligenceState`, `TradingSignal`, `RiskDecision`, and `ResearchArtifact`.

### 8. Unit Testing
- **File**: `tests/unit/test_state.py`
- **Change**: Implement comprehensive unit tests tagged with `@pytest.mark.issue_2`:
  - Model validations: valid values, boundary checks (sentiment [-1, 1], confidence [0, 1]), enums.
  - Reducer behaviors: idempotency, list merging, handling mixed dict/model inputs.
  - Serialization: roundtrip `model_dump` and JSON serialization.
  - StateProtocol validation: conformance of state container.
  - Orchestrator DAG end-to-end execution with typed `MarketIntelligenceState`.

### 9. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=2
```

### 10. Git & Issue Finish
```bash
make finish-issue ID=2 MSG="feat(state): implement state management protocol and domain models"
```

## Decisions
- **Pydantic V2 Domain Models**: Use Pydantic models for domain entities (`TradingSignal`, `RiskDecision`, `ResearchArtifact`, `PortfolioSnapshot`) to ensure runtime data validation, schema enforcement, and seamless serialization.
- **Annotated Reducers in LangGraph State**: Use `Annotated[list[T], append_reducer]` channels in `MarketIntelligenceState` to ensure graph nodes perform pure append operations without risking overwrites during multi-agent handoffs.
- **Loose Coupling with Dict Compatibility**: Reducers accept both instantiated Pydantic models and raw dictionaries to allow agents to produce lightweight dict updates or typed objects interchangeably.
- **Backward Compatibility**: `OrchestratorState` remains available as an alias to avoid breaking any callers from Issue 1.
