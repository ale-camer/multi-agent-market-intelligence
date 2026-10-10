"""Schema definitions and type contracts for the orchestrator."""

from collections.abc import Callable
from typing import Any, TypedDict


class OrchestratorState(TypedDict, total=False):
    """Execution state for the market intelligence orchestrator.

    Fields are optional (total=False) to allow node handlers to return partial
    state updates that are merged by LangGraph reducers.
    """

    messages: list[dict[str, Any]]
    context: dict[str, Any]
    signals: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    current_step: str
    errors: list[str]


# Node handler contract: receives state, returns partial state updates
NodeHandler = Callable[[OrchestratorState], dict[str, Any]]


class NodeNames:
    """Standard node identifiers for the market intelligence DAG."""

    RESEARCH: str = "research"
    TRADING_ANALYST: str = "trading_analyst"
    RISK_MANAGER: str = "risk_manager"


def create_initial_state(
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    signals: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    current_step: str = "init",
    errors: list[str] | None = None,
) -> OrchestratorState:
    """Helper factory to create a cleanly initialized OrchestratorState dictionary."""
    return {
        "messages": messages if messages is not None else [],
        "context": context if context is not None else {},
        "signals": signals if signals is not None else [],
        "decisions": decisions if decisions is not None else [],
        "current_step": current_step,
        "errors": errors if errors is not None else [],
    }
