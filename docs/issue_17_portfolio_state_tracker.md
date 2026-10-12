# Issue 17: Portfolio State Tracker

**Branch**: `feature/issue-17-portfolio-state-tracker`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #18)
**Milestone**: M4 - Risk & Portfolio Manager Implementation

## Objective
Implement an autonomous, high-precision `PortfolioTracker` state management engine for Milestone 4 (Risk & Portfolio Manager Implementation). The tracker maintains real-time accounting of cash balances, active asset positions, weighted average entry costs, mark-to-market valuations, realized and unrealized PnL, peak equity watermarks, drawdown percentages, gross/net exposures, and leverage ratios. It directly bridges with `MarketIntelligenceState["portfolio"]` via typed `PortfolioSnapshot` generation and hydration, providing the quantitative balance sheet foundation required for downstream Signal Validation (Issue 18) and the Risk & Portfolio Manager agent execution flow (Issue 19).

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/risk/models.py` defines extended portfolio accounting models inheriting from `DomainStateModel`:
  - `TradeExecution(DomainStateModel)`:
    - `symbol: str`
    - `action: SignalAction`
    - `quantity: float`
    - `price: float`
    - `cost: float`
    - `realized_pnl: float = 0.0`
    - `commission: float = 0.0`
    - `timestamp: datetime`
  - `PortfolioMetrics(DomainStateModel)`:
    - `total_equity: float`
    - `cash: float`
    - `gross_exposure: float`
    - `net_exposure: float`
    - `leverage: float`
    - `drawdown_pct: float`
    - `peak_equity: float`
    - `daily_pnl: float`
    - `daily_pnl_pct: float`
    - `positions_count: int`
    - `position_weights: dict[str, float]`
- [x] `src/multi_agent_market_intelligence/risk/portfolio.py` implements `PortfolioTracker`:
  - Initialization:
    - `initial_cash: float = 100_000.0`
    - `starting_equity: float | None = None`
    - `positions: dict[str, Position] | None = None`
    - `sector_mappings: dict[str, str] | None = None`
  - Cash management:
    - `deposit_cash(amount: float) -> float`
    - `withdraw_cash(amount: float) -> float` (with overdraft protection)
  - Mark-to-market pricing:
    - `update_market_price(symbol: str, price: float) -> None`
    - `update_market_prices(prices: dict[str, float]) -> None`
  - Trade execution engine:
    - `apply_trade(symbol: str, action: SignalAction | str, quantity: float, price: float, commission: float = 0.0) -> TradeExecution`:
      - Handles BUY: increases position quantity, calculates weighted average entry price, deducts total cost from cash.
      - Handles SELL: reduces position quantity, calculates realized PnL against entry cost basis, credits proceeds to cash.
      - Liquidates position when remaining quantity reaches zero.
      - Records execution into `trade_history: list[TradeExecution]`.
  - Financial accounting properties:
    - `total_equity: float` ($cash + \sum (quantity \times current\_price)$)
    - `cash: float`
    - `unrealized_pnl: float`
    - `realized_pnl: float`
    - `gross_exposure: float` ($\sum |quantity \times current\_price|$)
    - `net_exposure: float` ($\sum (quantity \times current\_price)$)
    - `leverage: float` ($gross\_exposure / total\_equity$)
    - `current_drawdown_pct: float` ($(peak\_equity - total\_equity) / peak\_equity$)
    - `daily_pnl: float` ($total\_equity - starting\_equity$)
    - `daily_pnl_pct: float` ($daily\_pnl / starting\_equity$)
    - `get_metrics() -> PortfolioMetrics`
    - `get_position(symbol: str) -> Position | None`
    - `get_sector_exposure(sector: str) -> float`
  - State snapshotting & inter-agent contracts:
    - `create_snapshot() -> PortfolioSnapshot`:
      Emits typed `PortfolioSnapshot` matching `MarketIntelligenceState["portfolio"]`.
    - `load_snapshot(snapshot: PortfolioSnapshot | dict[str, Any]) -> None`:
      Hydrates tracker state from existing state snapshot.
    - `reset_daily_baseline() -> None`:
      Resets starting equity baseline for new trading session.
- [x] `src/multi_agent_market_intelligence/risk/__init__.py` exposes `PortfolioTracker`, `TradeExecution`, and `PortfolioMetrics`.
- [x] `src/multi_agent_market_intelligence/__init__.py` re-exports public tracker models and classes.
- [x] Unit tests in `tests/unit/test_portfolio_tracker.py` tagged with `@pytest.mark.issue_17` covering:
  - Initial configuration, cash deposits, withdrawals, and overdraft prevention.
  - Position opening, scaling (weighted average entry price), partial sales, and complete liquidation.
  - Accurate realized and unrealized PnL calculation across market cycles.
  - Mark-to-market pricing updates altering total equity.
  - Watermark tracking and peak-to-trough drawdown calculation.
  - Daily PnL and return tracking against baseline equity.
  - Gross and net exposure calculation and leverage metrics.
  - Sector allocation exposure calculation.
  - Full snapshot generation and hydration roundtrip with `MarketIntelligenceState`.
  - Defensive error handling (insufficient cash, non-positive prices/quantities).
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=17` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=17 NAME=portfolio-state-tracker
```

### 2. Extended Accounting Models
- **File**: `src/multi_agent_market_intelligence/risk/models.py`
- **Change**: Implement `TradeExecution` and `PortfolioMetrics`:
  - `TradeExecution` recording trade details, cost basis, realized PnL, and commissions.
  - `PortfolioMetrics` providing a comprehensive snapshot of portfolio health.

### 3. Comprehensive Portfolio State Tracker
- **File**: `src/multi_agent_market_intelligence/risk/portfolio.py`
- **Change**: Implement `PortfolioTracker`:
  - Real-time position tracking with weighted average entry price.
  - Multi-asset mark-to-market price updates.
  - Cash management with overdraft validation.
  - High-water mark equity and drawdown tracking.
  - Trade execution engine computing realized PnL.
  - Exposure, leverage, and sector allocation calculation.
  - `create_snapshot()` and `load_snapshot()` integration with `PortfolioSnapshot`.

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/risk/__init__.py`
- **Change**: Export `PortfolioTracker`, `TradeExecution`, and `PortfolioMetrics`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `PortfolioTracker`, `TradeExecution`, and `PortfolioMetrics`.

### 5. Unit Testing
- **File**: `tests/unit/test_portfolio_tracker.py`
- **Change**: Implement exhaustive test suite tagged with `@pytest.mark.issue_17`:
  - `test_portfolio_tracker_initial_state_and_cash_management`
  - `test_portfolio_tracker_open_long_position`
  - `test_portfolio_tracker_scale_position_average_entry_price`
  - `test_portfolio_tracker_partial_and_full_position_liquidation`
  - `test_portfolio_tracker_mark_to_market_pricing_and_unrealized_pnl`
  - `test_portfolio_tracker_peak_equity_and_drawdown_watermark`
  - `test_portfolio_tracker_daily_pnl_and_return_tracking`
  - `test_portfolio_tracker_gross_net_exposure_and_leverage`
  - `test_portfolio_tracker_sector_exposure_aggregation`
  - `test_portfolio_tracker_snapshot_generation_and_hydration`
  - `test_portfolio_tracker_defensive_error_handling`

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=17
make test
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=17 MSG="feat(risk): implement PortfolioTracker state management engine"
```

## Decisions
- **Weighted Average Cost Basis Accounting**: When scaling into an existing position across multiple fill prices, `PortfolioTracker` dynamically updates the average entry price weighted by share volume, guaranteeing precise realized PnL calculations upon liquidation.
- **Bi-Directional State Hydration**: To support stateless or distributed LangGraph DAG workflows, `PortfolioTracker` can both serialize into an immutable `PortfolioSnapshot` and hydrate from an existing state snapshot without data loss.
- **High-Water Mark Drawdown Tracking**: Peak equity is automatically updated whenever total portfolio equity exceeds the prior maximum, enabling continuous evaluation of portfolio drawdown against `RiskLimitsConfig.max_portfolio_drawdown_pct`.
- **Integrated Overdraft Prevention**: The tracker rejects trades or cash withdrawals exceeding available free capital, preventing invalid negative cash states.
