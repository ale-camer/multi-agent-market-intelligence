"""State protocol definition and state container adapter."""

import copy
from typing import Any, Protocol, runtime_checkable

from multi_agent_market_intelligence.state.models import (
    ResearchArtifact,
    RiskDecision,
    TradingSignal,
)


@runtime_checkable
class StateProtocol(Protocol):
    """Protocol defining audit inspection and lifecycle contracts for workflow states."""

    def snapshot(self) -> dict[str, Any]:
        """Produce an isolated, serializable snapshot of the current state."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert state into a standard dictionary representation."""
        ...

    def get_signals(self) -> list[TradingSignal]:
        """Retrieve all generated trading signals."""
        ...

    def get_decisions(self) -> list[RiskDecision]:
        """Retrieve all validated risk decisions."""
        ...

    def get_artifacts(self) -> list[ResearchArtifact]:
        """Retrieve all research artifacts."""
        ...

    def validate_transition(self, next_step: str) -> bool:
        """Validate whether a transition to the next step is legitimate."""
        ...


class StateContainer:
    """Concrete state container implementing StateProtocol for audit and validation."""

    VALID_TRANSITIONS: dict[str, set[str]] = {
        "init": {"research"},
        "research": {"trading_analyst", "error"},
        "trading_analyst": {"risk_manager", "error"},
        "risk_manager": {"complete", "error"},
        "complete": set(),
        "error": set(),
    }

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(state) if state is not None else {}

    @property
    def current_step(self) -> str:
        """Return the current step identifier."""
        step = self._data.get("current_step", "init")
        return str(step)

    def snapshot(self) -> dict[str, Any]:
        """Produce a deep copy dictionary snapshot of state data."""
        return copy.deepcopy(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        """Return the state data dictionary with serialized models."""
        result: dict[str, Any] = {}
        for key, val in self._data.items():
            if isinstance(val, list):
                result[key] = [
                    item.model_dump() if hasattr(item, "model_dump") else item for item in val
                ]
            elif hasattr(val, "model_dump"):
                result[key] = val.model_dump()
            else:
                result[key] = val
        return result

    def get_signals(self) -> list[TradingSignal]:
        """Retrieve all trading signals, converting dicts to models if necessary."""
        raw_signals = self._data.get("signals", [])
        signals: list[TradingSignal] = []
        for s in raw_signals:
            if isinstance(s, TradingSignal):
                signals.append(s)
            elif isinstance(s, dict):
                signals.append(TradingSignal.model_validate(s))
        return signals

    def get_decisions(self) -> list[RiskDecision]:
        """Retrieve all risk decisions, converting dicts to models if necessary."""
        raw_decisions = self._data.get("decisions", [])
        decisions: list[RiskDecision] = []
        for d in raw_decisions:
            if isinstance(d, RiskDecision):
                decisions.append(d)
            elif isinstance(d, dict):
                decisions.append(RiskDecision.model_validate(d))
        return decisions

    def get_artifacts(self) -> list[ResearchArtifact]:
        """Retrieve all research artifacts, converting dicts to models if necessary."""
        raw_artifacts = self._data.get("artifacts", [])
        artifacts: list[ResearchArtifact] = []
        for a in raw_artifacts:
            if isinstance(a, ResearchArtifact):
                artifacts.append(a)
            elif isinstance(a, dict):
                artifacts.append(ResearchArtifact.model_validate(a))
        return artifacts

    def validate_transition(self, next_step: str) -> bool:
        """Validate whether the state transition to next_step is valid from current_step."""
        current = self.current_step
        allowed = self.VALID_TRANSITIONS.get(current, set())
        return next_step in allowed
