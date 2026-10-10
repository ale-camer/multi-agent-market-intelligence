# Issue 4: Base Agent Interface

**Branch**: `feature/issue-4-base-agent-interface`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #5)
**Milestone**: M1 - Core Infrastructure & Orchestrator Setup

## Objective
Establish the foundational `BaseAgent` abstract interface and lifecycle contract for all specialized agents (Research Agent, Trading Analyst, Risk & Portfolio Manager). This includes unified execution workflows (sync and async), automated latency and execution audit logging (`AgentExecutionRecord`), message bus integration, error handling, and LangGraph node handler adapters.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/agents/schema.py` defines `AgentRole` (StrEnum: `RESEARCH`, `TRADING_ANALYST`, `RISK_MANAGER`, `ORCHESTRATOR`), `AgentStatus` (StrEnum: `IDLE`, `RUNNING`, `SUCCESS`, `ERROR`), and `AgentConfig` Pydantic model.
- [x] `src/multi_agent_market_intelligence/agents/base.py` defines `BaseAgent` abstract class requiring `process(state: MarketIntelligenceState) -> dict[str, Any]` and `process_async(state: MarketIntelligenceState) -> dict[str, Any]`.
- [x] Automated execution wrapping in `execute(state)` and `execute_async(state)` measuring execution duration, creating `AgentExecutionRecord`, and capturing errors into state.
- [x] Direct integration with `MessageBus` for publishing and handling correlated messages (`send_message`, `receive_message`).
- [x] Node adapter method `as_node_handler() -> NodeHandler` allowing seamless registration into `MarketIntelligenceOrchestrator`.
- [x] `src/multi_agent_market_intelligence/agents/__init__.py` exposes all public agent abstractions.
- [x] Unit tests in `tests/unit/test_agents.py` marked with `@pytest.mark.issue_4` verifying abstract enforcement, sync/async execution, latency recording, error handling, message bus dispatch, and orchestrator node integration.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=4` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=4 NAME=base-agent-interface
```

### 2. Agent Metadata, Enums & Configurations
- **File**: `src/multi_agent_market_intelligence/agents/schema.py`
- **Change**: Define:
  - `AgentRole` (StrEnum): `RESEARCH`, `TRADING_ANALYST`, `RISK_MANAGER`, `ORCHESTRATOR`, `GENERAL`.
  - `AgentStatus` (StrEnum): `IDLE`, `RUNNING`, `SUCCESS`, `ERROR`, `PAUSED`.
  - `AgentConfig` (BaseModel): name, role, capabilities list, system_prompt, timeout_seconds, metadata.

### 3. Base Agent Abstract Class
- **File**: `src/multi_agent_market_intelligence/agents/base.py`
- **Change**: Implement `BaseAgent(ABC)`:
  - Constructor accepting `config: AgentConfig | None = None, message_bus: MessageBus | None = None`.
  - Abstract methods:
    - `process(state: MarketIntelligenceState) -> dict[str, Any]`
    - `process_async(state: MarketIntelligenceState) -> dict[str, Any]` (with default delegating to thread/process).
  - Wrapper methods:
    - `execute(state: MarketIntelligenceState) -> dict[str, Any]`: records start time, sets status to `RUNNING`, invokes `process`, computes duration ms, appends `AgentExecutionRecord` to output, handles exceptions gracefully.
    - `execute_async(state: MarketIntelligenceState) -> dict[str, Any]`: async counterpart.
  - Messaging helpers:
    - `send_message(recipient, message_type, payload, correlation_id) -> AgentMessage | None`
    - `receive_message(message: AgentMessage) -> None`
  - Adapter:
    - `as_node_handler() -> NodeHandler`: returns callable compatible with LangGraph nodes.

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/agents/__init__.py`
- **Change**: Export `BaseAgent`, `AgentRole`, `AgentStatus`, and `AgentConfig`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `BaseAgent`, `AgentRole`, `AgentStatus`, and `AgentConfig`.

### 5. Unit Testing
- **File**: `tests/unit/test_agents.py`
- **Change**: Implement comprehensive unit tests tagged with `@pytest.mark.issue_4`:
  - `BaseAgent` abstract class instantiation prevention.
  - Concrete test agent execution verifying return dictionary and status lifecycle (`IDLE -> RUNNING -> SUCCESS`).
  - Automated `AgentExecutionRecord` creation with duration and step information.
  - Error capture wrapping: failing agent produces status `ERROR` and error records without crashing orchestrator.
  - Asynchronous execution via `execute_async`.
  - Message sending and receiving through `MessageBus`.
  - End-to-end integration: plug agent into `MarketIntelligenceOrchestrator` via `as_node_handler()`.

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=4
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=4 MSG="feat(agents): implement base agent interface and execution lifecycle"
```

## Decisions
- **Separation of Template Execution and Business Logic**: `execute()` serves as the template method handling latency metrics, status transitions, and audit records, while subclasses implement domain logic exclusively in `process()`.
- **LangGraph Node Compatibility**: Provide `as_node_handler()` so any `BaseAgent` instance can immediately serve as a callable node handler in `MarketIntelligenceOrchestrator`, ensuring high cohesion and low coupling across milestones M1, M2, M3, and M4.
- **Resilient Error Isolation**: Exceptions during agent execution are caught by the template wrapper, recording an error status and appending execution logs to state rather than immediately aborting the graph, supporting robust paper trading pipelines.
