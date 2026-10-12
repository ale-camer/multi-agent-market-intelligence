"""Unit tests for SignalRiskValidator engine, capacity limits, and decision generation."""

import pytest

from multi_agent_market_intelligence.risk import (
    PortfolioTracker,
    RiskLimitsConfig,
    RiskViolationType,
    SignalRiskValidator,
    SignalValidator,
)
from multi_agent_market_intelligence.state.models import (
    DecisionStatus,
    PortfolioSnapshot,
    Position,
    SignalAction,
    TradingSignal,
)


@pytest.mark.issue_18
def test_signal_validator_circuit_breaker_active_rejection() -> None:
    """Verify immediate rejection when global circuit breaker is active."""
    limits = RiskLimitsConfig(circuit_breaker_active=True)
    validator = SignalRiskValidator(limits=limits)

    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=160.0,
        stop_loss=140.0,
        indicators={"close": 150.0},
    )
    portfolio = PortfolioTracker(initial_cash=100_000.0)

    decision = validator.validate_signal(signal, portfolio)

    assert decision.status == DecisionStatus.REJECTED
    assert decision.approved_size == 0.0
    assert "Circuit breaker is active" in decision.reason
    assert RiskViolationType.CIRCUIT_BREAKER_ACTIVE.value in decision.metrics["violations"]


@pytest.mark.issue_18
def test_signal_validator_drawdown_and_daily_loss_rejection() -> None:
    """Verify signal rejection when portfolio drawdown or daily loss threshold is breached."""
    limits = RiskLimitsConfig(max_portfolio_drawdown_pct=0.15, max_daily_loss_pct=0.05)
    validator = SignalRiskValidator(limits=limits)

    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=160.0,
        stop_loss=140.0,
        indicators={"close": 150.0},
    )

    # 1. Breach drawdown (20% > 15%)
    dd_portfolio = {
        "cash": 80_000.0,
        "total_equity": 80_000.0,
        "current_drawdown_pct": 0.20,
        "daily_pnl_pct": 0.0,
        "positions": {},
    }
    decision_dd = validator.validate_signal(signal, dd_portfolio)
    assert decision_dd.status == DecisionStatus.REJECTED
    assert (
        RiskViolationType.MAX_PORTFOLIO_DRAWDOWN_EXCEEDED.value in decision_dd.metrics["violations"]
    )

    # 2. Breach daily loss (-8% < -5%)
    loss_portfolio = {
        "cash": 92_000.0,
        "total_equity": 92_000.0,
        "current_drawdown_pct": 0.05,
        "daily_pnl_pct": -0.08,
        "positions": {},
    }
    decision_loss = validator.validate_signal(signal, loss_portfolio)
    assert decision_loss.status == DecisionStatus.REJECTED
    assert RiskViolationType.MAX_DAILY_LOSS_EXCEEDED.value in decision_loss.metrics["violations"]


@pytest.mark.issue_18
def test_signal_validator_concurrent_positions_limit() -> None:
    """Verify max open positions cap rejects new assets but permits scaling existing ones."""
    limits = RiskLimitsConfig(max_open_positions=2)
    validator = SignalRiskValidator(limits=limits)

    tracker = PortfolioTracker(initial_cash=100_000.0)
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=100.0, price=100.0)
    tracker.apply_trade("MSFT", SignalAction.BUY, quantity=50.0, price=200.0)
    assert len(tracker.positions) == 2

    # New symbol NVDA must be rejected
    nvda_signal = TradingSignal(
        symbol="NVDA",
        action=SignalAction.BUY,
        target_price=150.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    decision_new = validator.validate_signal(nvda_signal, tracker)
    assert decision_new.status == DecisionStatus.REJECTED
    assert (
        RiskViolationType.MAX_CONCURRENT_POSITIONS_EXCEEDED.value
        in decision_new.metrics["violations"]
    )

    # Existing symbol AAPL is not rejected by positions cap
    aapl_signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=120.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    decision_existing = validator.validate_signal(aapl_signal, tracker, proposed_size=20.0)
    assert decision_existing.status == DecisionStatus.APPROVED
    assert decision_existing.approved_size == 20.0


@pytest.mark.issue_18
def test_signal_validator_stop_loss_missing_and_geometry() -> None:
    """Verify rejection when stop-loss is missing, non-positive, or geometrically inverted."""
    limits = RiskLimitsConfig(stop_loss_required=True)
    validator = SignalRiskValidator(limits=limits)
    portfolio = PortfolioTracker(initial_cash=100_000.0)

    # Missing stop loss
    sig_missing = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=120.0,
        stop_loss=None,
        indicators={"close": 100.0},
    )
    dec_missing = validator.validate_signal(sig_missing, portfolio)
    assert dec_missing.status == DecisionStatus.REJECTED
    assert RiskViolationType.MISSING_STOP_LOSS.value in dec_missing.metrics["violations"]

    # Non-positive stop loss
    sig_nonpos = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=120.0,
        stop_loss=-5.0,
        indicators={"close": 100.0},
    )
    dec_nonpos = validator.validate_signal(sig_nonpos, portfolio)
    assert dec_nonpos.status == DecisionStatus.REJECTED

    # Inverted geometry (stop loss above entry price for BUY)
    sig_inverted = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=120.0,
        stop_loss=105.0,
        indicators={"close": 100.0},
    )
    dec_inverted = validator.validate_signal(sig_inverted, portfolio)
    assert dec_inverted.status == DecisionStatus.REJECTED
    assert "must be strictly below entry price" in dec_inverted.reason


@pytest.mark.issue_18
def test_signal_validator_risk_reward_ratio_validation() -> None:
    """Verify rejection when trade risk-to-reward ratio falls below required threshold."""
    limits = RiskLimitsConfig(min_risk_reward_ratio=2.0)
    validator = SignalRiskValidator(limits=limits)
    portfolio = PortfolioTracker(initial_cash=100_000.0)

    # Reward = 10, Risk = 10 -> R/R = 1.0 (< 2.0)
    bad_rr = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=110.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    dec_bad = validator.validate_signal(bad_rr, portfolio)
    assert dec_bad.status == DecisionStatus.REJECTED
    assert RiskViolationType.INSUFFICIENT_RISK_REWARD.value in dec_bad.metrics["violations"]

    # Reward = 25, Risk = 10 -> R/R = 2.5 (>= 2.0)
    good_rr = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=125.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    dec_good = validator.validate_signal(good_rr, portfolio, proposed_size=50.0)
    assert dec_good.status == DecisionStatus.APPROVED
    assert dec_good.metrics["risk_reward_ratio"] == 2.5


@pytest.mark.issue_18
def test_signal_validator_hold_and_sell_action_handling() -> None:
    """Verify benign approval of HOLD and accurate validation of SELL orders."""
    validator = SignalRiskValidator()
    tracker = PortfolioTracker(initial_cash=100_000.0)
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=100.0, price=100.0)

    # HOLD action
    hold_sig = TradingSignal(symbol="AAPL", action=SignalAction.HOLD)
    dec_hold = validator.validate_signal(hold_sig, tracker)
    assert dec_hold.status == DecisionStatus.APPROVED
    assert dec_hold.approved_size == 0.0

    # SELL non-held symbol TSLA
    sell_missing = TradingSignal(symbol="TSLA", action=SignalAction.SELL)
    dec_sell_missing = validator.validate_signal(sell_missing, tracker)
    assert dec_sell_missing.status == DecisionStatus.REJECTED

    # SELL held symbol AAPL: default full liquidation
    sell_full = TradingSignal(symbol="AAPL", action=SignalAction.SELL)
    dec_sell_full = validator.validate_signal(sell_full, tracker)
    assert dec_sell_full.status == DecisionStatus.APPROVED
    assert dec_sell_full.approved_size == 100.0

    # SELL held symbol AAPL: partial size
    dec_sell_part = validator.validate_signal(sell_full, tracker, proposed_size=40.0)
    assert dec_sell_part.status == DecisionStatus.APPROVED
    assert dec_sell_part.approved_size == 40.0

    # SELL held symbol AAPL: oversized request scaled down
    dec_sell_over = validator.validate_signal(sell_full, tracker, proposed_size=150.0)
    assert dec_sell_over.status == DecisionStatus.MODIFIED
    assert dec_sell_over.approved_size == 100.0


@pytest.mark.issue_18
def test_signal_validator_risk_based_position_sizing() -> None:
    """Verify position sizing calculation based on stop distance and risk-per-trade budget."""
    limits = RiskLimitsConfig(max_position_size_pct=0.20, min_risk_reward_ratio=1.5)
    validator = SignalRiskValidator(limits=limits, risk_per_trade_pct=0.02)
    portfolio = PortfolioTracker(initial_cash=100_000.0)

    # Total equity = $100,000. Risk budget (2%) = $2,000.
    # Price = $100, Stop = $80 -> Risk per share = $20.
    # Desired units = 2,000 / 20 = 100 shares. Total value = $10,000 (10% of equity < 20% cap).
    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    decision = validator.validate_signal(signal, portfolio)

    assert decision.status == DecisionStatus.APPROVED
    assert decision.approved_size == 100.0
    assert decision.max_loss_limit == 2_000.0
    assert decision.metrics["position_weight_pct"] == 0.10


@pytest.mark.issue_18
def test_signal_validator_position_size_concentration_scaling() -> None:
    """Verify oversized trade scaling when constrained by single-position concentration cap."""
    limits = RiskLimitsConfig(max_position_size_pct=0.20)  # Max $20,000
    validator = SignalRiskValidator(limits=limits, allow_position_scaling=True)

    tracker = PortfolioTracker(initial_cash=100_000.0)
    # Already holds 50 AAPL @ $100 = $5,000. Remaining cap = $15,000 (150 shares).
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=50.0, price=100.0)

    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=130.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    # Requested 200 shares ($20,000)
    decision = validator.validate_signal(signal, tracker, proposed_size=200.0)

    assert decision.status == DecisionStatus.MODIFIED
    assert decision.approved_size == 150.0
    assert RiskViolationType.EXCESSIVE_POSITION_SIZE.value in decision.metrics["violations"]

    # When scaling is disabled, order is rejected
    strict_validator = SignalRiskValidator(limits=limits, allow_position_scaling=False)
    dec_strict = strict_validator.validate_signal(signal, tracker, proposed_size=200.0)
    assert dec_strict.status == DecisionStatus.REJECTED


@pytest.mark.issue_18
def test_signal_validator_sector_exposure_limit_scaling() -> None:
    """Verify trade scaling when constrained by aggregate sector allocation ceiling."""
    limits = RiskLimitsConfig(max_sector_exposure_pct=0.30)  # Max $30,000 in sector
    validator = SignalRiskValidator(limits=limits)

    # Technology already holds $20,000 in AAPL
    tracker = PortfolioTracker(
        initial_cash=100_000.0,
        sector_mappings={"AAPL": "Technology", "MSFT": "Technology"},
    )
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=200.0, price=100.0)

    # BUY MSFT @ $200. Remaining tech capacity = $10,000 -> max 50 shares.
    signal = TradingSignal(
        symbol="MSFT",
        action=SignalAction.BUY,
        target_price=260.0,
        stop_loss=170.0,
        indicators={"close": 200.0},
    )
    decision = validator.validate_signal(signal, tracker, proposed_size=100.0, sector="Technology")

    assert decision.status == DecisionStatus.MODIFIED
    assert decision.approved_size == 50.0
    assert RiskViolationType.MAX_SECTOR_EXPOSURE_EXCEEDED.value in decision.metrics["violations"]


@pytest.mark.issue_18
def test_signal_validator_cash_buffer_constraint_scaling() -> None:
    """Verify trade scaling when constrained by minimum cash reserve requirements."""
    # Equity $100,000. Must keep 10% ($10,000) in cash.
    limits = RiskLimitsConfig(min_cash_buffer_pct=0.10, max_position_size_pct=0.50)
    validator = SignalRiskValidator(limits=limits)

    # Start with $25,000 cash. Free cash above buffer = $15,000.
    portfolio = {
        "cash": 25_000.0,
        "total_equity": 100_000.0,
        "positions": {
            "SPY": Position(symbol="SPY", quantity=750.0, entry_price=100.0, current_price=100.0)
        },
    }

    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=130.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    # Requested 200 shares ($20,000). Max by cash buffer = $15,000 / 100 = 150 shares.
    decision = validator.validate_signal(signal, portfolio, proposed_size=200.0)

    assert decision.status == DecisionStatus.MODIFIED
    assert decision.approved_size == 150.0
    assert RiskViolationType.INSUFFICIENT_CASH_BUFFER.value in decision.metrics["violations"]


@pytest.mark.issue_18
def test_signal_validator_gross_leverage_limit_scaling() -> None:
    """Verify trade scaling when constrained by gross portfolio leverage limits."""
    # Equity $100,000, max leverage = 1.2x (Max gross exposure = $120,000)
    limits = RiskLimitsConfig(max_leverage=1.2, max_position_size_pct=0.50)
    validator = SignalRiskValidator(limits=limits)

    # Current exposure = $110,000. Remaining capacity = $10,000.
    portfolio = {
        "cash": 50_000.0,
        "total_equity": 100_000.0,
        "positions": {
            "SPY": Position(symbol="SPY", quantity=1100.0, entry_price=100.0, current_price=100.0)
        },
    }

    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=70.0,
        stop_loss=40.0,
        indicators={"close": 50.0},
    )
    # Requested 300 shares ($15,000). Max by leverage = $10,000 / 50 = 200 shares.
    decision = validator.validate_signal(signal, portfolio, proposed_size=300.0)

    assert decision.status == DecisionStatus.MODIFIED
    assert decision.approved_size == 200.0
    assert RiskViolationType.EXCESSIVE_LEVERAGE.value in decision.metrics["violations"]


@pytest.mark.issue_18
def test_signal_validator_batch_validation_cumulative_capacity() -> None:
    """Verify multi-signal batch evaluation decrements cumulative capital across signals."""
    # Cash = $30,000, min buffer = 10% ($10,000). Total available cash = $20,000.
    limits = RiskLimitsConfig(min_cash_buffer_pct=0.10, max_position_size_pct=0.30)
    validator = SignalValidator(limits=limits)

    portfolio = {
        "cash": 30_000.0,
        "total_equity": 100_000.0,
        "positions": {},
    }

    sig1 = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=130.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    sig2 = TradingSignal(
        symbol="MSFT",
        action=SignalAction.BUY,
        target_price=130.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )

    # Both ask for 120 units ($12,000 each = $24,000 total > $20,000 available)
    decisions = validator.validate_signals_batch(
        signals=[sig1, sig2],
        portfolio=portfolio,
        proposed_sizes={"AAPL": 120.0, "MSFT": 120.0},
        track_cumulative_capacity=True,
    )

    assert len(decisions) == 2
    # First signal gets approved for full 120 units ($12,000)
    assert decisions[0].status == DecisionStatus.APPROVED
    assert decisions[0].approved_size == 120.0

    # Second signal gets scaled down to remaining $8,000 -> 80 units
    assert decisions[1].status == DecisionStatus.MODIFIED
    assert decisions[1].approved_size == 80.0


@pytest.mark.issue_18
def test_signal_validator_state_snapshot_compatibility() -> None:
    """Verify validator works seamlessly with typed PortfolioSnapshot and raw dicts."""
    validator = SignalRiskValidator()

    # Snapshot object
    pos = Position(symbol="AAPL", quantity=100.0, entry_price=150.0, current_price=150.0)
    snapshot = PortfolioSnapshot(
        cash=85_000.0,
        positions={"AAPL": pos},
        total_equity=100_000.0,
    )

    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=180.0,
        stop_loss=140.0,
        indicators={"close": 150.0},
    )

    decision_snap = validator.validate_signal(signal, snapshot, proposed_size=50.0)
    assert decision_snap.status in (DecisionStatus.APPROVED, DecisionStatus.MODIFIED)

    # Serialization roundtrip check
    dumped = decision_snap.model_dump()
    assert dumped["status"] in ("APPROVED", "MODIFIED")
    assert dumped["approved_size"] > 0.0
