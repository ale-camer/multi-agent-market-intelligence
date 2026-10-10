# Issue 3: Message Passing Mechanisms

**Branch**: `feature/issue-3-message-passing`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #4)
**Milestone**: M1 - Core Infrastructure & Orchestrator Setup

## Objective
Implement structured, decoupled message-passing mechanisms for inter-agent communication. This includes strongly-typed message models (`AgentMessage`) with correlation tracking, a pub/sub `MessageBus` with topic and recipient routing, message history auditing, and integration adapters for LangGraph state channels.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/messaging/models.py` defines `AgentMessage` Pydantic model with `message_id`, `sender`, `recipient`, `message_type` (`MessageType` StrEnum), `payload`, `correlation_id`, `timestamp`, and `metadata`.
- [x] `src/multi_agent_market_intelligence/messaging/bus.py` implements `MessageBus` supporting pub/sub subscriptions by topic or recipient, synchronous and asynchronous message publishing, handler dispatching, message history tracking, and dead-letter capturing.
- [x] Correlation ID tracing ensuring end-to-end auditability across the decision pipeline (Research -> Trading -> Risk).
- [x] `src/multi_agent_market_intelligence/messaging/adapters.py` provides bidirectional conversion between `AgentMessage` and LangGraph state dictionaries.
- [x] `src/multi_agent_market_intelligence/messaging/__init__.py` exposes all messaging classes and functions.
- [x] `Makefile` updated to ensure `BRANCH` is evaluated in the same subshell during `gh pr create` in `finish-issue`.
- [x] Unit tests in `tests/unit/test_messaging.py` marked with `@pytest.mark.issue_3` covering message validation, pub/sub dispatch, filtering, async dispatch, history auditing, correlation tracing, and state adapter conversions.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=3` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=3 NAME=message-passing
```

### 2. Makefile Subshell Fix
- **File**: `Makefile`
- **Change**: In `finish-issue`, ensure `BRANCH=$$(git rev-parse --abbrev-ref HEAD)` is executed in the same subshell as `gh pr create` and `gh pr merge` so the branch name is never empty.

### 3. Message Models & Enums
- **File**: `src/multi_agent_market_intelligence/messaging/models.py`
- **Change**: Define:
  - `MessageType` (StrEnum): `DATA_REQUEST`, `RESEARCH_REPORT`, `SIGNAL_PROPOSAL`, `RISK_EVALUATION`, `SYSTEM_ALERT`, `COMMAND`, `HEARTBEAT`.
  - `MessagePriority` (StrEnum): `LOW`, `NORMAL`, `HIGH`, `URGENT`.
  - `AgentMessage` (BaseModel): strongly-typed envelope with UUID generation, sender, recipient, type, payload, correlation ID, timestamp, and priority. Supports comparison against raw dicts for testing.

### 4. In-Memory Message Bus
- **File**: `src/multi_agent_market_intelligence/messaging/bus.py`
- **Change**: Implement `MessageBus`:
  - `subscribe(recipient_or_topic: str, handler: Callable)`: registers subscriber callbacks (sync or async).
  - `publish(message: AgentMessage) -> None`: delivers message to matched recipients/subscribers in FIFO order.
  - `publish_async(message: AgentMessage) -> None`: asynchronous non-blocking delivery.
  - `history: list[AgentMessage]`: audit log of all published messages.
  - `get_conversation(correlation_id: str) -> list[AgentMessage]`: filters audit history by correlation ID.
  - `clear()`: resets bus state and subscriptions.

### 5. State Integration Adapters
- **File**: `src/multi_agent_market_intelligence/messaging/adapters.py`
- **Change**: Provide helpers to convert `AgentMessage` to/from LangGraph `dict[str, Any]` message formats used in `MarketIntelligenceState`.

### 6. Package Exports
- **File**: `src/multi_agent_market_intelligence/messaging/__init__.py`
- **Change**: Export `AgentMessage`, `MessageType`, `MessagePriority`, `MessageBus`, and adapter utilities.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `AgentMessage`, `MessageBus`, and `MessageType`.

### 7. Unit Testing
- **File**: `tests/unit/test_messaging.py`
- **Change**: Implement comprehensive unit tests tagged with `@pytest.mark.issue_3`:
  - Envelope validation and default UUID/timestamp generation.
  - Direct message routing by recipient and broadcast topic routing (`*`).
  - Async publishing and subscription execution.
  - Correlation ID tracing across simulated multi-step agent conversations.
  - State adapter serialization and deserialization.
  - Dead-letter logging when no subscribers match recipient.

### 8. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=3
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=3 MSG="feat(messaging): implement agent message schema and message bus"
```

## Decisions
- **Decoupled In-Memory Bus**: Use an in-memory `MessageBus` with async/sync support rather than external message brokers (e.g. RabbitMQ/Kafka) to keep paper trading and agent tests 100% self-contained and fast.
- **Correlation ID for Multi-Agent Tracing**: Include `correlation_id` in `AgentMessage` so entire decision lifecycles (research report -> signal generation -> risk veto/approval) can be traced unambiguously in audits.
- **Envelope Pattern**: Use an explicit `AgentMessage` envelope separating routing metadata (`sender`, `recipient`, `message_type`, `priority`) from the domain `payload` (`dict[str, Any]`), enabling loose coupling between agent implementations.
