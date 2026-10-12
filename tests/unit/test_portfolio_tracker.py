"""Unit tests for PortfolioTracker state management, accounting, and snapshotting engine."""

import pytest

from multi_agent_market_intelligence.risk import (
    PortfolioMetrics,
    PortfolioTracker,
    TradeExecution,
)
from multi_agent_market_intelligence.state.models import (
    PortfolioSnapshot,
    SignalAction,
)


@pytest.mark.issue_17
def test_portfolio_tracker_initial_state_and_cash_management() -> None:
    """Validate initial tracker accounting, deposits, withdrawals, and balance updates."""
    tracker = PortfolioTracker(initial_cash=100_000.0)

    assert tracker.cash == 100_000.0
    assert tracker.total_equity == 100_000.0
    assert tracker.peak_equity == 100_000.0
    assert tracker.starting_equity == 100_000.0
    assert tracker.realized_pnl == 0.0
    assert tracker.unrealized_pnl == 0.0
    assert tracker.gross_exposure == 0.0
    assert tracker.net_exposure == 0.0
    assert tracker.leverage == 0.0
    assert tracker.current_drawdown_pct == 0.0
    assert tracker.daily_pnl == 0.0
    assert tracker.daily_pnl_pct == 0.0
    assert tracker.positions == {}
    assert tracker.trade_history == []

    # Deposit cash
    new_cash = tracker.deposit_cash(25_000.0)
    assert new_cash == 125_000.0
    assert tracker.cash == 125_000.0
    assert tracker.total_equity == 125_000.0
    assert tracker.peak_equity == 125_000.0

    # Withdraw cash
    new_cash = tracker.withdraw_cash(15_000.0)
    assert new_cash == 110_000.0
    assert tracker.cash == 110_000.0
    assert tracker.total_equity == 110_000.0
    # Peak equity remains high watermark
    assert tracker.peak_equity == 125_000.0


@pytest.mark.issue_17
def test_portfolio_tracker_open_long_position() -> None:
    """Verify executing BUY trade creates position, deducts cash, and creates trade execution."""
    tracker = PortfolioTracker(initial_cash=50_000.0)

    exec1 = tracker.apply_trade(
        symbol="AAPL",
        action=SignalAction.BUY,
        quantity=100.0,
        price=150.0,
        commission=10.0,
    )

    assert isinstance(exec1, TradeExecution)
    assert exec1.symbol == "AAPL"
    assert exec1.action == SignalAction.BUY
    assert exec1.quantity == 100.0
    assert exec1.price == 150.0
    assert exec1.cost == 15_000.0
    assert exec1.commission == 10.0
    assert exec1.realized_pnl == 0.0

    # Cash: 50,000 - 15,000 - 10 = 34,990
    assert tracker.cash == 34_990.0
    pos = tracker.get_position("AAPL")
    assert pos is not None
    assert pos.symbol == "AAPL"
    assert pos.quantity == 100.0
    assert pos.entry_price == 150.0
    assert pos.current_price == 150.0
    assert pos.unrealized_pnl == 0.0

    # Total equity: 34,990 + 15,000 = 49,990 (decreased by commission)
    assert tracker.total_equity == 49_990.0
    assert tracker.gross_exposure == 15_000.0
    assert len(tracker.trade_history) == 1

    # String action acceptance
    exec2 = tracker.apply_trade(
        symbol="MSFT",
        action="BUY",
        quantity=50.0,
        price=300.0,
        commission=5.0,
    )
    assert exec2.symbol == "MSFT"
    assert exec2.action == SignalAction.BUY
    assert tracker.get_position("MSFT") is not None
    assert len(tracker.positions) == 2


@pytest.mark.issue_17
def test_portfolio_tracker_scale_position_average_entry_price() -> None:
    """Verify scaling into an existing position updates weighted average entry price."""
    tracker = PortfolioTracker(initial_cash=100_000.0)

    # First tranche: 100 AAPL @ $100.0 (Cost = $10,000)
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=100.0, price=100.0)
    pos = tracker.get_position("AAPL")
    assert pos is not None
    assert pos.entry_price == 100.0

    # Second tranche: 100 AAPL @ $120.0 (Cost = $12,000)
    # Total cost = $22,000, Total shares = 200, Weighted average = $110.0
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=100.0, price=120.0)
    pos = tracker.get_position("AAPL")
    assert pos is not None
    assert pos.quantity == 200.0
    assert pos.entry_price == pytest.approx(110.0)
    assert pos.current_price == 120.0
    # Unrealized PnL: (120 - 110) * 200 = 2,000
    assert pos.unrealized_pnl == pytest.approx(2_000.0)

    # Third tranche: 50 AAPL @ $140.0 (Cost = $7,000)
    # Total cost = 22,000 + 7,000 = 29,000. Total shares = 250.
    # Weighted average = 29,000 / 250 = 116.0
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=50.0, price=140.0)
    pos = tracker.get_position("AAPL")
    assert pos is not None
    assert pos.quantity == 250.0
    assert pos.entry_price == pytest.approx(116.0)
    assert pos.current_price == 140.0
    # Unrealized PnL: (140 - 116) * 250 = 6,000
    assert pos.unrealized_pnl == pytest.approx(6_000.0)


@pytest.mark.issue_17
def test_portfolio_tracker_partial_and_full_position_liquidation() -> None:
    """Verify partial sales calculate correct realized PnL and full sale removes position."""
    tracker = PortfolioTracker(initial_cash=100_000.0)

    # Buy 200 AAPL @ $100
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=200.0, price=100.0)
    assert tracker.cash == 80_000.0

    # Partial sale: 100 AAPL @ $120, commission $5
    # Realized PnL = (120 - 100) * 100 - 5 = 2,000 - 5 = 1,995
    # Cash proceeds = 100 * 120 - 5 = 11,995
    exec_sell1 = tracker.apply_trade(
        "AAPL",
        SignalAction.SELL,
        quantity=100.0,
        price=120.0,
        commission=5.0,
    )
    assert exec_sell1.realized_pnl == 1_995.0
    assert tracker.realized_pnl == 1_995.0
    assert tracker.cash == 91_995.0

    pos = tracker.get_position("AAPL")
    assert pos is not None
    assert pos.quantity == 100.0
    assert pos.entry_price == 100.0
    assert pos.current_price == 120.0

    # Full liquidation of remaining 100 AAPL @ $130, commission $5
    # Realized PnL = (130 - 100) * 100 - 5 = 3,000 - 5 = 2,995
    # Cumulative realized PnL = 1,995 + 2,995 = 4,990
    exec_sell2 = tracker.apply_trade(
        "AAPL",
        "SELL",
        quantity=100.0,
        price=130.0,
        commission=5.0,
    )
    assert exec_sell2.realized_pnl == 2_995.0
    assert tracker.realized_pnl == 4_990.0
    assert tracker.cash == 91_995.0 + 12_995.0  # 104,990.0

    # Position is completely liquidated and removed
    assert tracker.get_position("AAPL") is None
    assert "AAPL" not in tracker.positions
    assert tracker.unrealized_pnl == 0.0
    assert tracker.gross_exposure == 0.0


@pytest.mark.issue_17
def test_portfolio_tracker_mark_to_market_pricing_and_unrealized_pnl() -> None:
    """Verify mark-to-market single and batch pricing updates adjust unrealized PnL and equity."""
    tracker = PortfolioTracker(initial_cash=100_000.0)

    tracker.apply_trade("NVDA", SignalAction.BUY, quantity=100.0, price=100.0)
    tracker.apply_trade("GOOGL", SignalAction.BUY, quantity=50.0, price=150.0)

    assert tracker.unrealized_pnl == 0.0

    # Update NVDA single price
    tracker.update_market_price("NVDA", 120.0)
    nvda_pos = tracker.get_position("NVDA")
    assert nvda_pos is not None
    assert nvda_pos.current_price == 120.0
    assert nvda_pos.unrealized_pnl == pytest.approx(2_000.0)
    assert tracker.unrealized_pnl == pytest.approx(2_000.0)

    # Batch update prices
    tracker.update_market_prices({"NVDA": 130.0, "GOOGL": 140.0})
    nvda_pos = tracker.get_position("NVDA")
    googl_pos = tracker.get_position("GOOGL")
    assert nvda_pos is not None and googl_pos is not None
    assert nvda_pos.unrealized_pnl == pytest.approx(3_000.0)  # (130-100)*100
    assert googl_pos.unrealized_pnl == pytest.approx(-500.0)  # (140-150)*50

    # Net unrealized PnL = 3,000 - 500 = 2,500
    assert tracker.unrealized_pnl == pytest.approx(2_500.0)
    # Total equity = cash (82,500) + NVDA (13,000) + GOOGL (7,000) = 102,500
    assert tracker.total_equity == pytest.approx(102_500.0)


@pytest.mark.issue_17
def test_portfolio_tracker_peak_equity_and_drawdown_watermark() -> None:
    """Verify high-water mark peak equity tracking and percentage drawdown calculations."""
    tracker = PortfolioTracker(initial_cash=100_000.0)
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=500.0, price=100.0)

    assert tracker.peak_equity == 100_000.0
    assert tracker.current_drawdown_pct == 0.0

    # Market rises to 140. AAPL value = 70,000. Cash = 50,000. Equity = 120,000.
    tracker.update_market_price("AAPL", 140.0)
    assert tracker.total_equity == 120_000.0
    assert tracker.peak_equity == 120_000.0
    assert tracker.current_drawdown_pct == 0.0

    # Market drops to 108. AAPL value = 54,000. Cash = 50,000. Equity = 104,000.
    # Peak equity remains 120,000.
    # Drawdown = (120,000 - 104,000) / 120,000 = 16,000 / 120,000 = 0.13333333333333333
    tracker.update_market_price("AAPL", 108.0)
    assert tracker.total_equity == 104_000.0
    assert tracker.peak_equity == 120_000.0
    assert tracker.current_drawdown_pct == pytest.approx(16_000.0 / 120_000.0)


@pytest.mark.issue_17
def test_portfolio_tracker_daily_pnl_and_return_tracking() -> None:
    """Verify daily PnL and return tracking against baseline equity with reset capability."""
    tracker = PortfolioTracker(initial_cash=100_000.0, starting_equity=100_000.0)
    tracker.apply_trade("TSLA", SignalAction.BUY, quantity=200.0, price=200.0)

    # TSLA moves up to 220. Equity = 60,000 + 44,000 = 104,000.
    tracker.update_market_price("TSLA", 220.0)
    assert tracker.daily_pnl == 4_000.0
    assert tracker.daily_pnl_pct == pytest.approx(0.04)

    # Reset daily baseline for next day
    tracker.reset_daily_baseline()
    assert tracker.starting_equity == 104_000.0
    assert tracker.daily_pnl == 0.0
    assert tracker.daily_pnl_pct == 0.0

    # TSLA drops to 210. Equity = 60,000 + 42,000 = 102,000.
    tracker.update_market_price("TSLA", 210.0)
    assert tracker.daily_pnl == -2_000.0
    assert tracker.daily_pnl_pct == pytest.approx(-2_000.0 / 104_000.0)


@pytest.mark.issue_17
def test_portfolio_tracker_gross_net_exposure_and_leverage() -> None:
    """Verify gross and net exposures, leverage ratio, and PortfolioMetrics generation."""
    tracker = PortfolioTracker(initial_cash=100_000.0)

    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=200.0, price=150.0)  # 30,000
    tracker.apply_trade("MSFT", SignalAction.BUY, quantity=100.0, price=300.0)  # 30,000

    assert tracker.cash == 40_000.0
    assert tracker.gross_exposure == 60_000.0
    assert tracker.net_exposure == 60_000.0
    assert tracker.total_equity == 100_000.0
    assert tracker.leverage == pytest.approx(0.60)

    metrics = tracker.get_metrics()
    assert isinstance(metrics, PortfolioMetrics)
    assert metrics.total_equity == 100_000.0
    assert metrics.cash == 40_000.0
    assert metrics.gross_exposure == 60_000.0
    assert metrics.net_exposure == 60_000.0
    assert metrics.leverage == pytest.approx(0.60)
    assert metrics.positions_count == 2
    assert metrics.position_weights["AAPL"] == pytest.approx(0.30)
    assert metrics.position_weights["MSFT"] == pytest.approx(0.30)


@pytest.mark.issue_17
def test_portfolio_tracker_sector_exposure_aggregation() -> None:
    """Verify aggregate sector exposure calculations with symbol mappings."""
    mappings = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "XOM": "Energy",
    }
    tracker = PortfolioTracker(initial_cash=100_000.0, sector_mappings=mappings)

    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=100.0, price=150.0)  # 15,000
    tracker.apply_trade("MSFT", SignalAction.BUY, quantity=50.0, price=300.0)  # 15,000
    tracker.apply_trade("XOM", SignalAction.BUY, quantity=100.0, price=100.0)  # 10,000

    assert tracker.get_sector_exposure("Technology") == 30_000.0
    assert tracker.get_sector_exposure("Energy") == 10_000.0
    assert tracker.get_sector_exposure("Healthcare") == 0.0

    # Case-insensitive sector queries
    assert tracker.get_sector_exposure("technology") == 30_000.0
    assert tracker.get_sector_exposure("ENERGY") == 10_000.0

    # Dynamic registration of additional mapping
    tracker.set_sector_mappings({"JNJ": "Healthcare"})
    tracker.apply_trade("JNJ", SignalAction.BUY, quantity=50.0, price=160.0)  # 8,000
    assert tracker.get_sector_exposure("Healthcare") == 8_000.0


@pytest.mark.issue_17
def test_portfolio_tracker_snapshot_generation_and_hydration() -> None:
    """Verify bi-directional snapshot creation and state hydration roundtrip."""
    tracker = PortfolioTracker(initial_cash=100_000.0)
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=100.0, price=150.0)
    tracker.update_market_price("AAPL", 160.0)

    snapshot = tracker.create_snapshot()
    assert isinstance(snapshot, PortfolioSnapshot)
    assert snapshot.cash == 85_000.0
    assert "AAPL" in snapshot.positions
    assert snapshot.positions["AAPL"].quantity == 100.0
    assert snapshot.positions["AAPL"].current_price == 160.0
    assert snapshot.total_equity == 101_000.0
    assert snapshot.margin_used == 0.0

    # Hydrate new tracker from snapshot object
    hydrated_tracker = PortfolioTracker(initial_cash=0.0)
    hydrated_tracker.load_snapshot(snapshot)

    assert hydrated_tracker.cash == 85_000.0
    assert hydrated_tracker.total_equity == 101_000.0
    assert hydrated_tracker.get_position("AAPL") is not None
    assert hydrated_tracker.get_position("AAPL").quantity == 100.0
    assert hydrated_tracker.get_position("AAPL").unrealized_pnl == pytest.approx(1_000.0)

    # Hydrate another tracker from dictionary representation
    dict_tracker = PortfolioTracker(initial_cash=0.0)
    dict_tracker.load_snapshot(snapshot.model_dump())
    assert dict_tracker.cash == 85_000.0
    assert dict_tracker.total_equity == 101_000.0
    assert dict_tracker.get_position("AAPL") is not None


@pytest.mark.issue_17
def test_portfolio_tracker_defensive_error_handling() -> None:
    """Ensure tracker raises appropriate exceptions on invalid operations and parameters."""
    # Negative initial cash
    with pytest.raises(ValueError, match="Initial cash cannot be negative"):
        PortfolioTracker(initial_cash=-1000.0)

    # Negative starting equity
    with pytest.raises(ValueError, match="Starting equity cannot be negative"):
        PortfolioTracker(starting_equity=-500.0)

    tracker = PortfolioTracker(initial_cash=10_000.0)

    # Invalid cash deposit / withdrawal amounts
    with pytest.raises(ValueError, match="Deposit amount must be positive"):
        tracker.deposit_cash(-100.0)
    with pytest.raises(ValueError, match="Withdrawal amount must be positive"):
        tracker.withdraw_cash(0.0)
    with pytest.raises(ValueError, match="Insufficient cash for withdrawal"):
        tracker.withdraw_cash(20_000.0)

    # Invalid trade quantities and prices
    with pytest.raises(ValueError, match="Trade quantity must be positive"):
        tracker.apply_trade("AAPL", SignalAction.BUY, quantity=0.0, price=100.0)
    with pytest.raises(ValueError, match="Trade price must be positive"):
        tracker.apply_trade("AAPL", SignalAction.BUY, quantity=10.0, price=-50.0)
    with pytest.raises(ValueError, match="Commission cannot be negative"):
        tracker.apply_trade("AAPL", SignalAction.BUY, quantity=10.0, price=100.0, commission=-5.0)

    # Insufficient cash for BUY
    with pytest.raises(ValueError, match="Insufficient cash"):
        tracker.apply_trade("AAPL", SignalAction.BUY, quantity=1000.0, price=100.0)

    # Selling non-existent position
    with pytest.raises(ValueError, match="No existing position"):
        tracker.apply_trade("GOOGL", SignalAction.SELL, quantity=10.0, price=150.0)

    # Selling more than held
    tracker.apply_trade("AAPL", SignalAction.BUY, quantity=50.0, price=100.0)
    with pytest.raises(ValueError, match="Cannot sell more quantity"):
        tracker.apply_trade("AAPL", SignalAction.SELL, quantity=100.0, price=110.0)

    # Unsupported action
    with pytest.raises(ValueError, match="Cannot execute trade with action 'HOLD'"):
        tracker.apply_trade("AAPL", SignalAction.HOLD, quantity=10.0, price=100.0)
    with pytest.raises(ValueError, match="Unsupported trade action"):
        tracker.apply_trade("AAPL", "INVALID_ACTION", quantity=10.0, price=100.0)

    # Invalid market price update
    with pytest.raises(ValueError, match="Market price must be positive"):
        tracker.update_market_price("AAPL", 0.0)

    # Invalid snapshot type
    with pytest.raises(TypeError, match="Unsupported snapshot type"):
        tracker.load_snapshot("invalid_snapshot")  # type: ignore[arg-type]
