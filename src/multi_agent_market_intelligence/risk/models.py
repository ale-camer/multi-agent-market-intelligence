"""Risk management domain models, violation classifications, and evaluation results."""

from enum import StrEnum
from typing import Any

from pydantic import Field

from multi_agent_market_intelligence.state.models import DomainStateModel


class RiskViolationType(StrEnum):
    """Enumeration of discrete risk policy and limit violation categories."""

    EXCESSIVE_POSITION_SIZE = "EXCESSIVE_POSITION_SIZE"
    MAX_PORTFOLIO_DRAWDOWN_EXCEEDED = "MAX_PORTFOLIO_DRAWDOWN_EXCEEDED"
    MAX_DAILY_LOSS_EXCEEDED = "MAX_DAILY_LOSS_EXCEEDED"
    EXCESSIVE_LEVERAGE = "EXCESSIVE_LEVERAGE"
    INSUFFICIENT_CASH_BUFFER = "INSUFFICIENT_CASH_BUFFER"
    MAX_SECTOR_EXPOSURE_EXCEEDED = "MAX_SECTOR_EXPOSURE_EXCEEDED"
    MAX_CONCURRENT_POSITIONS_EXCEEDED = "MAX_CONCURRENT_POSITIONS_EXCEEDED"
    MISSING_STOP_LOSS = "MISSING_STOP_LOSS"
    INSUFFICIENT_RISK_REWARD = "INSUFFICIENT_RISK_REWARD"
    CIRCUIT_BREAKER_ACTIVE = "CIRCUIT_BREAKER_ACTIVE"


class RiskCheckResult(DomainStateModel):
    """Outcome container of a quantitative risk evaluation check."""

    passed: bool = True
    violations: list[RiskViolationType] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    adjusted_size: float | None = None

    def add_violation(self, violation: RiskViolationType, reason: str) -> None:
        """Record a risk rule violation and mark check as failed.

        Args:
            violation: Classification of the risk rule breach.
            reason: Human-readable diagnostic description of the violation.
        """
        self.passed = False
        self.violations.append(violation)
        self.reasons.append(reason)

    def is_clean(self) -> bool:
        """Check whether the risk evaluation passed with zero violations.

        Returns:
            True if passed and violations list is empty, False otherwise.
        """
        return self.passed and len(self.violations) == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert result model to standard dictionary.

        Returns:
            Dictionary serialization of RiskCheckResult.
        """
        return self.model_dump()
