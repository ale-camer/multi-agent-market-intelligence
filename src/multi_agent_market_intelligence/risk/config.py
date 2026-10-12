"""Global risk limits configuration, parameter validation, and evaluation engine."""

from typing import Any

from pydantic import Field

from multi_agent_market_intelligence.risk.models import (
    RiskCheckResult,
    RiskViolationType,
)
from multi_agent_market_intelligence.state.models import (
    DomainStateModel,
    SignalAction,
)


class RiskLimitsConfig(DomainStateModel):
    """Global portfolio risk policy parameters, thresholds, and validation rules."""

    max_position_size_pct: float = Field(
        default=0.20,
        gt=0.0,
        le=1.0,
        description="Maximum capital allocation to a single position as percentage of equity.",
    )
    max_portfolio_drawdown_pct: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        description="Maximum peak-to-trough drawdown percentage allowed before halt.",
    )
    max_daily_loss_pct: float = Field(
        default=0.05,
        gt=0.0,
        le=1.0,
        description="Maximum portfolio loss allowed in a single trading day.",
    )
    max_leverage: float = Field(
        default=1.0,
        ge=1.0,
        description="Maximum gross leverage ratio (total exposure / total equity).",
    )
    min_cash_buffer_pct: float = Field(
        default=0.10,
        ge=0.0,
        lt=1.0,
        description="Minimum cash buffer percentage required as liquidity reserve.",
    )
    max_sector_exposure_pct: float = Field(
        default=0.35,
        gt=0.0,
        le=1.0,
        description="Maximum capital allocation to a single industry sector.",
    )
    max_open_positions: int = Field(
        default=10,
        ge=1,
        description="Maximum concurrent open positions allowed in the portfolio.",
    )
    stop_loss_required: bool = Field(
        default=True,
        description="Whether every trading signal must define a valid non-null stop loss.",
    )
    min_risk_reward_ratio: float = Field(
        default=1.5,
        gt=0.0,
        description="Minimum required potential reward to potential risk distance ratio.",
    )
    circuit_breaker_active: bool = Field(
        default=False,
        description="Global kill-switch halting all new order approvals.",
    )

    def validate_position_size(
        self,
        position_value: float,
        total_equity: float,
    ) -> tuple[bool, str | None]:
        """Validate whether a position value adheres to maximum concentration cap.

        Args:
            position_value: Market value of the prospective or existing position.
            total_equity: Current total portfolio equity.

        Returns:
            Tuple of (is_valid, optional_error_message).
        """
        if total_equity <= 0.0:
            return False, "Portfolio equity is zero or negative."
        pos_pct = abs(position_value) / total_equity
        if pos_pct > self.max_position_size_pct:
            return (
                False,
                f"Position size {pos_pct:.2%} exceeds maximum allowed "
                f"{self.max_position_size_pct:.2%}.",
            )
        return True, None

    def validate_cash_buffer(
        self,
        cash: float,
        total_equity: float,
    ) -> tuple[bool, str | None]:
        """Validate whether remaining uncommitted cash meets minimum liquidity buffer.

        Args:
            cash: Free available cash balance.
            total_equity: Current total portfolio equity.

        Returns:
            Tuple of (is_valid, optional_error_message).
        """
        if total_equity <= 0.0:
            return False, "Portfolio equity is zero or negative."
        cash_pct = cash / total_equity
        if cash_pct < self.min_cash_buffer_pct:
            return (
                False,
                f"Available cash buffer {cash_pct:.2%} is below required minimum "
                f"{self.min_cash_buffer_pct:.2%}.",
            )
        return True, None

    def validate_drawdown(
        self,
        current_drawdown_pct: float,
    ) -> tuple[bool, str | None]:
        """Validate whether portfolio drawdown is within acceptable tolerance.

        Args:
            current_drawdown_pct: Cumulative peak-to-trough drawdown percentage.

        Returns:
            Tuple of (is_valid, optional_error_message).
        """
        dd = abs(current_drawdown_pct)
        if dd > self.max_portfolio_drawdown_pct:
            return (
                False,
                f"Current drawdown {dd:.2%} exceeds maximum threshold "
                f"{self.max_portfolio_drawdown_pct:.2%}.",
            )
        return True, None

    def validate_daily_loss(
        self,
        daily_loss_pct: float,
    ) -> tuple[bool, str | None]:
        """Validate whether intraday portfolio loss is within daily limit.

        Args:
            daily_loss_pct: Portfolio loss percentage experienced during current day.

        Returns:
            Tuple of (is_valid, optional_error_message).
        """
        loss = abs(daily_loss_pct)
        if loss > self.max_daily_loss_pct:
            return (
                False,
                f"Daily portfolio loss {loss:.2%} exceeds maximum allowed "
                f"{self.max_daily_loss_pct:.2%}.",
            )
        return True, None

    def validate_leverage(
        self,
        total_exposure: float,
        total_equity: float,
    ) -> tuple[bool, str | None]:
        """Validate whether gross portfolio leverage respects maximum leverage cap.

        Args:
            total_exposure: Aggregate gross value of all active positions.
            total_equity: Current total portfolio equity.

        Returns:
            Tuple of (is_valid, optional_error_message).
        """
        if total_equity <= 0.0:
            return False, "Portfolio equity is zero or negative."
        leverage = abs(total_exposure) / total_equity
        if leverage > self.max_leverage:
            return (
                False,
                f"Total leverage {leverage:.2f}x exceeds maximum allowed {self.max_leverage:.2f}x.",
            )
        return True, None

    def validate_open_positions_count(
        self,
        current_positions: int,
    ) -> tuple[bool, str | None]:
        """Validate whether current number of open positions allows adding another asset.

        Args:
            current_positions: Number of currently held positions.

        Returns:
            Tuple of (is_valid, optional_error_message).
        """
        if current_positions >= self.max_open_positions:
            return (
                False,
                f"Open positions count ({current_positions}) reached or exceeded maximum "
                f"{self.max_open_positions}.",
            )
        return True, None

    def validate_risk_reward(
        self,
        target_price: float | None,
        stop_loss: float | None,
        current_price: float,
        action: SignalAction | str,
    ) -> tuple[bool, str | None]:
        """Validate trade geometry, stop-loss presence, and risk/reward asymmetry.

        Args:
            target_price: Projected take-profit target price.
            stop_loss: Designated protective stop-loss price.
            current_price: Market entry price.
            action: Trading signal action (BUY, SELL, HOLD).

        Returns:
            Tuple of (is_valid, optional_error_message).
        """
        act_str = action.value if isinstance(action, SignalAction) else str(action).upper()
        if act_str == "HOLD":
            return True, None

        if self.stop_loss_required and (stop_loss is None or stop_loss <= 0.0):
            return False, "Stop loss is required but not provided or non-positive."

        if target_price is None or stop_loss is None:
            return True, None

        if current_price <= 0.0:
            return False, "Current price must be positive for risk-reward evaluation."

        if act_str == "BUY":
            risk = current_price - stop_loss
            reward = target_price - current_price
            if risk <= 0.0:
                return (
                    False,
                    f"BUY stop loss ({stop_loss:.2f}) must be below current price "
                    f"({current_price:.2f}).",
                )
            if reward <= 0.0:
                return (
                    False,
                    f"BUY target price ({target_price:.2f}) must be above current price "
                    f"({current_price:.2f}).",
                )
            rr_ratio = reward / risk
        elif act_str == "SELL":
            risk = stop_loss - current_price
            reward = current_price - target_price
            if risk <= 0.0:
                return (
                    False,
                    f"SELL stop loss ({stop_loss:.2f}) must be above current price "
                    f"({current_price:.2f}).",
                )
            if reward <= 0.0:
                return (
                    False,
                    f"SELL target price ({target_price:.2f}) must be below current price "
                    f"({current_price:.2f}).",
                )
            rr_ratio = reward / risk
        else:
            return True, None

        if rr_ratio < self.min_risk_reward_ratio:
            return (
                False,
                f"Risk-reward ratio ({rr_ratio:.2f}) is below minimum required "
                f"{self.min_risk_reward_ratio:.2f}.",
            )

        return True, None

    def evaluate_limits(
        self,
        position_value: float | None = None,
        total_equity: float | None = None,
        cash: float | None = None,
        current_drawdown_pct: float | None = None,
        daily_loss_pct: float | None = None,
        total_exposure: float | None = None,
        current_positions: int | None = None,
        target_price: float | None = None,
        stop_loss: float | None = None,
        current_price: float | None = None,
        action: SignalAction | str | None = None,
    ) -> RiskCheckResult:
        """Perform comprehensive evaluation of all applicable risk limits.

        Returns:
            RiskCheckResult detailing pass/fail status, violation types, and diagnostics.
        """
        result = RiskCheckResult()

        if self.circuit_breaker_active:
            result.add_violation(
                RiskViolationType.CIRCUIT_BREAKER_ACTIVE,
                "Trading halted: Circuit breaker is currently active.",
            )

        if current_drawdown_pct is not None:
            ok, msg = self.validate_drawdown(current_drawdown_pct)
            if not ok and msg:
                result.add_violation(RiskViolationType.MAX_PORTFOLIO_DRAWDOWN_EXCEEDED, msg)

        if daily_loss_pct is not None:
            ok, msg = self.validate_daily_loss(daily_loss_pct)
            if not ok and msg:
                result.add_violation(RiskViolationType.MAX_DAILY_LOSS_EXCEEDED, msg)

        if total_equity is not None:
            if position_value is not None:
                ok, msg = self.validate_position_size(position_value, total_equity)
                if not ok and msg:
                    result.add_violation(RiskViolationType.EXCESSIVE_POSITION_SIZE, msg)

            if cash is not None:
                ok, msg = self.validate_cash_buffer(cash, total_equity)
                if not ok and msg:
                    result.add_violation(RiskViolationType.INSUFFICIENT_CASH_BUFFER, msg)

            if total_exposure is not None:
                ok, msg = self.validate_leverage(total_exposure, total_equity)
                if not ok and msg:
                    result.add_violation(RiskViolationType.EXCESSIVE_LEVERAGE, msg)

        if current_positions is not None:
            ok, msg = self.validate_open_positions_count(current_positions)
            if not ok and msg:
                result.add_violation(RiskViolationType.MAX_CONCURRENT_POSITIONS_EXCEEDED, msg)

        if action is not None and current_price is not None:
            ok, msg = self.validate_risk_reward(target_price, stop_loss, current_price, action)
            if not ok and msg:
                if "Stop loss is required" in msg:
                    result.add_violation(RiskViolationType.MISSING_STOP_LOSS, msg)
                else:
                    result.add_violation(RiskViolationType.INSUFFICIENT_RISK_REWARD, msg)

        result.metrics = {
            "max_position_size_pct": self.max_position_size_pct,
            "max_portfolio_drawdown_pct": self.max_portfolio_drawdown_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_leverage": self.max_leverage,
            "min_cash_buffer_pct": self.min_cash_buffer_pct,
            "max_open_positions": self.max_open_positions,
            "circuit_breaker_active": self.circuit_breaker_active,
        }

        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary representation.

        Returns:
            Dictionary serialization of RiskLimitsConfig.
        """
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskLimitsConfig":
        """Instantiate RiskLimitsConfig from dictionary.

        Args:
            data: Configuration key-value dictionary.

        Returns:
            Validated RiskLimitsConfig instance.
        """
        return cls.model_validate(data)


def conservative_risk_limits() -> RiskLimitsConfig:
    """Create a conservative risk limits configuration for capital preservation."""
    return RiskLimitsConfig(
        max_position_size_pct=0.10,
        max_portfolio_drawdown_pct=0.10,
        max_daily_loss_pct=0.03,
        max_leverage=1.0,
        min_cash_buffer_pct=0.20,
        max_sector_exposure_pct=0.25,
        max_open_positions=8,
        stop_loss_required=True,
        min_risk_reward_ratio=2.0,
        circuit_breaker_active=False,
    )


def moderate_risk_limits() -> RiskLimitsConfig:
    """Create a standard moderate risk limits configuration for balanced growth."""
    return RiskLimitsConfig()


def aggressive_risk_limits() -> RiskLimitsConfig:
    """Create an aggressive risk limits configuration with higher risk tolerances."""
    return RiskLimitsConfig(
        max_position_size_pct=0.30,
        max_portfolio_drawdown_pct=0.25,
        max_daily_loss_pct=0.08,
        max_leverage=1.5,
        min_cash_buffer_pct=0.05,
        max_sector_exposure_pct=0.50,
        max_open_positions=15,
        stop_loss_required=False,
        min_risk_reward_ratio=1.2,
        circuit_breaker_active=False,
    )
