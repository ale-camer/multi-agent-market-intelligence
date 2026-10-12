"""Unit tests for global risk limits configuration, parameter validation, and evaluation engine."""

import pytest
from pydantic import ValidationError

from multi_agent_market_intelligence.risk import (
    RiskCheckResult,
    RiskLimitsConfig,
    RiskViolationType,
    aggressive_risk_limits,
    conservative_risk_limits,
    moderate_risk_limits,
)
from multi_agent_market_intelligence.state.models import SignalAction


@pytest.mark.issue_16
def test_risk_limits_default_initialization() -> None:
    """Ensure RiskLimitsConfig initializes with sound quantitative defaults."""
    cfg = RiskLimitsConfig()

    assert cfg.max_position_size_pct == 0.20
    assert cfg.max_portfolio_drawdown_pct == 0.15
    assert cfg.max_daily_loss_pct == 0.05
    assert cfg.max_leverage == 1.0
    assert cfg.min_cash_buffer_pct == 0.10
    assert cfg.max_sector_exposure_pct == 0.35
    assert cfg.max_open_positions == 10
    assert cfg.stop_loss_required is True
    assert cfg.min_risk_reward_ratio == 1.5
    assert cfg.circuit_breaker_active is False


@pytest.mark.issue_16
def test_risk_limits_field_validations_and_bounds() -> None:
    """Ensure RiskLimitsConfig rejects out-of-bound and nonsensical risk parameters."""
    # max_position_size_pct bounds (0.0, 1.0]
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_position_size_pct=0.0)
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_position_size_pct=1.2)

    # max_portfolio_drawdown_pct bounds (0.0, 1.0]
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_portfolio_drawdown_pct=0.0)
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_portfolio_drawdown_pct=1.5)

    # max_daily_loss_pct bounds (0.0, 1.0]
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_daily_loss_pct=-0.05)
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_daily_loss_pct=1.1)

    # max_leverage >= 1.0
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_leverage=0.8)

    # min_cash_buffer_pct [0.0, 1.0)
    with pytest.raises(ValidationError):
        RiskLimitsConfig(min_cash_buffer_pct=-0.1)
    with pytest.raises(ValidationError):
        RiskLimitsConfig(min_cash_buffer_pct=1.0)

    # max_open_positions >= 1
    with pytest.raises(ValidationError):
        RiskLimitsConfig(max_open_positions=0)

    # min_risk_reward_ratio > 0.0
    with pytest.raises(ValidationError):
        RiskLimitsConfig(min_risk_reward_ratio=0.0)


@pytest.mark.issue_16
def test_risk_limits_preset_profiles() -> None:
    """Ensure predefined risk profile factories return appropriate calibrated presets."""
    cons = conservative_risk_limits()
    assert cons.max_position_size_pct == 0.10
    assert cons.max_portfolio_drawdown_pct == 0.10
    assert cons.max_daily_loss_pct == 0.03
    assert cons.min_cash_buffer_pct == 0.20
    assert cons.min_risk_reward_ratio == 2.0
    assert cons.max_open_positions == 8
    assert cons.stop_loss_required is True

    mod = moderate_risk_limits()
    assert mod.max_position_size_pct == 0.20
    assert mod.max_portfolio_drawdown_pct == 0.15
    assert mod.min_cash_buffer_pct == 0.10
    assert mod.min_risk_reward_ratio == 1.5

    agg = aggressive_risk_limits()
    assert agg.max_position_size_pct == 0.30
    assert agg.max_portfolio_drawdown_pct == 0.25
    assert agg.max_daily_loss_pct == 0.08
    assert agg.max_leverage == 1.5
    assert agg.min_cash_buffer_pct == 0.05
    assert agg.min_risk_reward_ratio == 1.2
    assert agg.max_open_positions == 15
    assert agg.stop_loss_required is False


@pytest.mark.issue_16
def test_validate_position_size_boundaries() -> None:
    """Ensure position sizing checks accurately identify permitted limits and breaches."""
    cfg = RiskLimitsConfig(max_position_size_pct=0.20)
    equity = 100_000.0

    # Within cap: 15,000 / 100,000 = 15% <= 20%
    ok, err = cfg.validate_position_size(15_000.0, equity)
    assert ok is True
    assert err is None

    # Exact boundary: 20,000 / 100,000 = 20% <= 20%
    ok, err = cfg.validate_position_size(20_000.0, equity)
    assert ok is True
    assert err is None

    # Breach: 25,000 / 100,000 = 25% > 20%
    ok, err = cfg.validate_position_size(25_000.0, equity)
    assert ok is False
    assert err is not None
    assert "exceeds maximum allowed" in err

    # Short position (negative value) checked via absolute value
    ok, err = cfg.validate_position_size(-18_000.0, equity)
    assert ok is True

    ok, err = cfg.validate_position_size(-22_000.0, equity)
    assert ok is False

    # Zero or negative equity protection
    ok, err = cfg.validate_position_size(5_000.0, 0.0)
    assert ok is False
    assert "zero or negative" in (err or "")


@pytest.mark.issue_16
def test_validate_cash_buffer_enforcement() -> None:
    """Ensure uncommitted cash buffer validation protects required liquidity."""
    cfg = RiskLimitsConfig(min_cash_buffer_pct=0.10)
    equity = 100_000.0

    # Sufficient liquidity: 15,000 / 100,000 = 15% >= 10%
    ok, err = cfg.validate_cash_buffer(15_000.0, equity)
    assert ok is True
    assert err is None

    # Exact threshold: 10,000 / 100,000 = 10% >= 10%
    ok, err = cfg.validate_cash_buffer(10_000.0, equity)
    assert ok is True
    assert err is None

    # Deficit: 8,000 / 100,000 = 8% < 10%
    ok, err = cfg.validate_cash_buffer(8_000.0, equity)
    assert ok is False
    assert err is not None
    assert "below required minimum" in err


@pytest.mark.issue_16
def test_validate_drawdown_and_daily_loss() -> None:
    """Ensure drawdown and intraday loss limits detect threshold breaches."""
    cfg = RiskLimitsConfig(max_portfolio_drawdown_pct=0.15, max_daily_loss_pct=0.05)

    # Drawdown evaluations
    ok, err = cfg.validate_drawdown(0.10)
    assert ok is True

    ok, err = cfg.validate_drawdown(0.15)
    assert ok is True

    ok, err = cfg.validate_drawdown(0.18)
    assert ok is False
    assert "exceeds maximum threshold" in (err or "")

    # Negative convention for drawdown input handled via abs()
    ok, err = cfg.validate_drawdown(-0.20)
    assert ok is False

    # Daily loss evaluations
    ok, err = cfg.validate_daily_loss(0.03)
    assert ok is True

    ok, err = cfg.validate_daily_loss(0.05)
    assert ok is True

    ok, err = cfg.validate_daily_loss(0.07)
    assert ok is False
    assert "exceeds maximum allowed" in (err or "")


@pytest.mark.issue_16
def test_validate_leverage_limits() -> None:
    """Ensure leverage validation enforces portfolio gearing caps."""
    cfg = RiskLimitsConfig(max_leverage=1.0)
    equity = 100_000.0

    ok, err = cfg.validate_leverage(90_000.0, equity)
    assert ok is True

    ok, err = cfg.validate_leverage(100_000.0, equity)
    assert ok is True

    ok, err = cfg.validate_leverage(120_000.0, equity)
    assert ok is False
    assert "exceeds maximum allowed" in (err or "")

    # Leveraged profile allows up to 1.5x
    agg = aggressive_risk_limits()
    ok, err = agg.validate_leverage(140_000.0, equity)
    assert ok is True

    ok, err = agg.validate_leverage(160_000.0, equity)
    assert ok is False


@pytest.mark.issue_16
def test_validate_open_positions_count() -> None:
    """Ensure open positions validation restricts excessive diversification."""
    cfg = RiskLimitsConfig(max_open_positions=10)

    ok, err = cfg.validate_open_positions_count(5)
    assert ok is True

    ok, err = cfg.validate_open_positions_count(9)
    assert ok is True

    ok, err = cfg.validate_open_positions_count(10)
    assert ok is False
    assert "reached or exceeded maximum" in (err or "")


@pytest.mark.issue_16
def test_validate_risk_reward_ratio_buy_and_sell() -> None:
    """Ensure trade geometry and risk/reward ratio are accurately validated for BUY and SELL."""
    cfg = RiskLimitsConfig(min_risk_reward_ratio=1.5, stop_loss_required=True)

    # 1. Valid BUY: entry 100, stop 90 (risk 10), target 120 (reward 20) -> RR 2.0 >= 1.5
    ok, err = cfg.validate_risk_reward(120.0, 90.0, 100.0, SignalAction.BUY)
    assert ok is True
    assert err is None

    # 2. Substandard BUY: entry 100, stop 90 (risk 10), target 110 (reward 10) -> RR 1.0 < 1.5
    ok, err = cfg.validate_risk_reward(110.0, 90.0, 100.0, SignalAction.BUY)
    assert ok is False
    assert "below minimum required" in (err or "")

    # 3. Inverted BUY geometry: stop above entry or target below entry
    ok, err = cfg.validate_risk_reward(120.0, 105.0, 100.0, SignalAction.BUY)
    assert ok is False
    assert "must be below current price" in (err or "")

    ok, err = cfg.validate_risk_reward(95.0, 90.0, 100.0, SignalAction.BUY)
    assert ok is False
    assert "must be above current price" in (err or "")

    # 4. Valid SELL: entry 100, stop 110 (risk 10), target 80 (reward 20) -> RR 2.0 >= 1.5
    ok, err = cfg.validate_risk_reward(80.0, 110.0, 100.0, SignalAction.SELL)
    assert ok is True
    assert err is None

    # 5. Substandard SELL: entry 100, stop 110 (risk 10), target 90 (reward 10) -> RR 1.0 < 1.5
    ok, err = cfg.validate_risk_reward(90.0, 110.0, 100.0, SignalAction.SELL)
    assert ok is False
    assert "below minimum required" in (err or "")

    # 6. Inverted SELL geometry
    ok, err = cfg.validate_risk_reward(80.0, 95.0, 100.0, SignalAction.SELL)
    assert ok is False
    assert "must be above current price" in (err or "")

    # 7. HOLD signals always pass
    ok, err = cfg.validate_risk_reward(None, None, 100.0, SignalAction.HOLD)
    assert ok is True


@pytest.mark.issue_16
def test_validate_stop_loss_requirement() -> None:
    """Ensure stop loss mandate is strictly enforced when required."""
    cfg = RiskLimitsConfig(stop_loss_required=True)

    ok, err = cfg.validate_risk_reward(120.0, None, 100.0, SignalAction.BUY)
    assert ok is False
    assert "Stop loss is required" in (err or "")

    ok, err = cfg.validate_risk_reward(120.0, 0.0, 100.0, SignalAction.BUY)
    assert ok is False
    assert "Stop loss is required" in (err or "")

    # When not required
    optional_cfg = RiskLimitsConfig(stop_loss_required=False)
    ok, err = optional_cfg.validate_risk_reward(120.0, None, 100.0, SignalAction.BUY)
    assert ok is True


@pytest.mark.issue_16
def test_circuit_breaker_immediate_halt() -> None:
    """Ensure active circuit breaker halts execution with explicit violation."""
    cfg = RiskLimitsConfig(circuit_breaker_active=True)

    res = cfg.evaluate_limits(
        position_value=10_000.0,
        total_equity=100_000.0,
        cash=20_000.0,
    )
    assert res.passed is False
    assert RiskViolationType.CIRCUIT_BREAKER_ACTIVE in res.violations
    assert any("Circuit breaker is currently active" in r for r in res.reasons)


@pytest.mark.issue_16
def test_evaluate_limits_composite_check() -> None:
    """Ensure evaluate_limits conducts aggregate evaluation and collects multiple breaches."""
    cfg = RiskLimitsConfig(
        max_position_size_pct=0.20,
        min_cash_buffer_pct=0.10,
        min_risk_reward_ratio=1.5,
    )

    # 1. Clean compliant scenario
    clean_res = cfg.evaluate_limits(
        position_value=15_000.0,
        total_equity=100_000.0,
        cash=20_000.0,
        current_drawdown_pct=0.05,
        daily_loss_pct=0.01,
        total_exposure=80_000.0,
        current_positions=4,
        target_price=120.0,
        stop_loss=90.0,
        current_price=100.0,
        action=SignalAction.BUY,
    )
    assert clean_res.passed is True
    assert clean_res.is_clean() is True
    assert len(clean_res.violations) == 0

    # 2. Multi-violation scenario: position cap breach, cash deficit, and bad risk-reward
    breach_res = cfg.evaluate_limits(
        position_value=30_000.0,  # 30% > 20%
        total_equity=100_000.0,
        cash=5_000.0,  # 5% < 10%
        current_positions=12,  # 12 >= 10
        target_price=105.0,  # RR 0.5 < 1.5
        stop_loss=90.0,
        current_price=100.0,
        action=SignalAction.BUY,
    )
    assert breach_res.passed is False
    assert breach_res.is_clean() is False
    assert RiskViolationType.EXCESSIVE_POSITION_SIZE in breach_res.violations
    assert RiskViolationType.INSUFFICIENT_CASH_BUFFER in breach_res.violations
    assert RiskViolationType.MAX_CONCURRENT_POSITIONS_EXCEEDED in breach_res.violations
    assert RiskViolationType.INSUFFICIENT_RISK_REWARD in breach_res.violations
    assert len(breach_res.reasons) >= 4


@pytest.mark.issue_16
def test_risk_limits_serialization_roundtrip() -> None:
    """Ensure RiskLimitsConfig and RiskCheckResult serialize to and from dicts losslessly."""
    cfg = RiskLimitsConfig(
        max_position_size_pct=0.15,
        max_leverage=1.2,
        min_risk_reward_ratio=1.8,
    )
    data = cfg.to_dict()
    assert isinstance(data, dict)
    assert data["max_position_size_pct"] == 0.15
    assert data["max_leverage"] == 1.2
    assert data["min_risk_reward_ratio"] == 1.8

    loaded = RiskLimitsConfig.from_dict(data)
    assert loaded == cfg

    # RiskCheckResult serialization
    res = RiskCheckResult()
    res.add_violation(RiskViolationType.EXCESSIVE_POSITION_SIZE, "Position exceeds allocation cap.")
    res_dict = res.to_dict()
    assert res_dict["passed"] is False
    assert res_dict["violations"] == ["EXCESSIVE_POSITION_SIZE"]
    assert len(res_dict["reasons"]) == 1
