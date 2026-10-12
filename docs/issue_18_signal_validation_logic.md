# Issue 18: Signal Validation Logic

**Branch**: `feature/issue-18-signal-validation-logic`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #19)
**Milestone**: M4 - Risk & Portfolio Manager Implementation

## Objective
Implement an autonomous, high-precision `SignalRiskValidator` engine for Milestone 4 (Risk & Portfolio Manager Implementation). The validator evaluates incoming `TradingSignal` proposals against the active portfolio balance sheet (`PortfolioTracker` or `PortfolioSnapshot`) and global risk guardrails (`RiskLimitsConfig`). It enforces multi-layered checks (circuit breaker, portfolio drawdown, daily loss limit, open positions cap, stop-loss requirements, and risk-to-reward asymmetry) and dynamically determines or scales position size to satisfy single-asset concentration, sector allocation, minimum cash reserve, and gross leverage limits. The engine produces fully audited `RiskDecision` records (`APPROVED`, `MODIFIED`, or `REJECTED`) containing approved unit sizing, maximum loss constraints, violation diagnostics, and rich telemetry metrics, establishing the algorithmic core for the Risk & Portfolio Manager agent execution flow (Issue 19).

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/risk/validation.py` implements `SignalRiskValidator` (with alias `SignalValidator`):
  - Initialization:
    - `limits: RiskLimitsConfig | None = None` (defaults to standard `RiskLimitsConfig()`)
    - `risk_per_trade_pct: float = 0.02` (fraction of total equity risked per trade based on stop distance)
    - `allow_position_scaling: bool = True` (allows scaling down oversized trades to fit limits via `MODIFIED` status)
  - Core signal evaluation:
    - `validate_signal(signal: TradingSignal, portfolio: PortfolioTracker | PortfolioSnapshot | dict[str, Any], current_price: float | None = None, proposed_size: float | None = None, sector: str | None = None) -> RiskDecision`:
      - Pre-check 1: Circuit breaker active → `REJECTED` (`RiskViolationType.CIRCUIT_BREAKER_ACTIVE`).
      - Pre-check 2: Portfolio drawdown exceeded → `REJECTED` (`RiskViolationType.MAX_PORTFOLIO_DRAWDOWN_EXCEEDED`).
      - Pre-check 3: Daily loss limit exceeded → `REJECTED` (`RiskViolationType.MAX_DAILY_LOSS_EXCEEDED`).
      - Pre-check 4: Open positions cap reached → `REJECTED` (`RiskViolationType.MAX_CONCURRENT_POSITIONS_EXCEEDED`) when opening new symbols.
      - Pre-check 5: Stop-loss presence and geometry:
        - When `limits.stop_loss_required` is True: missing or non-positive stop-loss → `REJECTED` (`RiskViolationType.MISSING_STOP_LOSS`).
        - For BUY: stop-loss must be strictly below market entry price.
        - For SELL: stop-loss must be strictly above market entry price.
      - Pre-check 6: Risk-to-reward ratio:
        - Evaluates $(target\_price - current\_price) / (current\_price - stop\_loss)$ for BUY.
        - Rejects with `RiskViolationType.INSUFFICIENT_RISK_REWARD` if below `limits.min_risk_reward_ratio`.
      - Action handling:
        - `HOLD`: returns `DecisionStatus.APPROVED` with `approved_size = 0.0` and informational reasoning.
        - `SELL`: verifies existing held position. Rejects if no position exists or if quantity requested is invalid. Approves up to held quantity.
        - `BUY`: performs quantitative position sizing and capacity checks:
          - Computes baseline sizing (from `proposed_size` or volatility/stop distance: $(total\_equity \times risk\_per\_trade\_pct) / |entry\_price - stop\_loss|$).
          - Evaluates capacity ceilings:
            1. Single-position concentration: $(max\_position\_size\_pct \times total\_equity) - current\_position\_value$
            2. Sector allocation cap: $(max\_sector\_exposure\_pct \times total\_equity) - current\_sector\_exposure$
            3. Cash reserve buffer: $cash - (min\_cash\_buffer\_pct \times total\_equity)$
            4. Gross leverage cap: $(max\_leverage \times total\_equity) - gross\_exposure$
          - Determines max permitted units: $\max(0.0, \min(cap_{single}, cap_{sector}, cap_{cash}, cap_{leverage}) / entry\_price)$.
          - If max permitted units $\le 0.0$: `REJECTED` with specific violation (`EXCESSIVE_POSITION_SIZE`, `MAX_SECTOR_EXPOSURE_EXCEEDED`, `INSUFFICIENT_CASH_BUFFER`, or `EXCESSIVE_LEVERAGE`).
          - If proposed units $>$ max permitted units and `allow_position_scaling` is True: `MODIFIED` with `approved_size = max_permitted_units`.
          - If proposed units $\le$ max permitted units: `APPROVED` with `approved_size = proposed_units`.
      - Computes `max_loss_limit = approved_size * abs(entry_price - stop_loss)` when stop-loss is defined.
      - Populates comprehensive `metrics` dictionary in `RiskDecision` (risk-reward ratio, proposed size, approved size, max permitted size, position weight, sector exposure, cash buffer pct, leverage, violations).
  - Batch signal evaluation:
    - `validate_signals_batch(signals: list[TradingSignal], portfolio: PortfolioTracker | PortfolioSnapshot | dict[str, Any], prices: dict[str, float] | None = None, proposed_sizes: dict[str, float] | None = None, sectors: dict[str, str] | None = None, track_cumulative_capacity: bool = True) -> list[RiskDecision]`:
      - Evaluates multiple signals in sequence.
      - When `track_cumulative_capacity` is True, updates internal simulated cash and exposure so multiple approved BUY orders do not collectively exceed cash buffer or leverage limits.
- [x] `src/multi_agent_market_intelligence/risk/__init__.py` exposes `SignalRiskValidator` and `SignalValidator`.
- [x] `src/multi_agent_market_intelligence/__init__.py` re-exports `SignalRiskValidator` and `SignalValidator`.
- [x] Unit tests in `tests/unit/test_signal_validator.py` tagged with `@pytest.mark.issue_18` covering:
  - Immediate rejection when circuit breaker is active.
  - Rejection when portfolio drawdown limit is breached.
  - Rejection when daily loss limit is breached.
  - Rejection when concurrent open positions limit is reached for new symbols, but passing for existing symbols.
  - Rejection when stop-loss is missing, non-positive, or geometrically inverted.
  - Rejection when risk-to-reward ratio falls below configured threshold.
  - Safe approval and zero-size allocation for HOLD signals.
  - Validation of SELL signals for held positions vs non-existent positions.
  - Risk-based position sizing via stop-loss distance and risk-per-trade fraction.
  - Position size modification (scaling down) when exceeding single-position concentration limit.
  - Position size modification when constrained by sector allocation limit.
  - Position size modification when constrained by minimum cash buffer requirement.
  - Position size modification when constrained by gross leverage limit.
  - Sequential batch signal validation with cumulative allocation tracking.
  - Snapshot and dict hydration compatibility with LangGraph state.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=18` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=18 NAME=signal-validation-logic
```

### 2. Signal Risk Validator Engine
- **File**: `src/multi_agent_market_intelligence/risk/validation.py`
- **Change**: Implement `SignalRiskValidator` (and alias `SignalValidator`):
  - Pre-trade policy checks: circuit breaker, drawdown, daily loss, open positions, stop-loss presence, geometry, risk/reward ratio.
  - Dynamic position sizing algorithms: fractional risk per trade, stop distance, capital capacity ceilings.
  - Capital capacity clamping across single position, sector, cash buffer, and leverage boundaries.
  - Single signal validation generating `RiskDecision` (APPROVED, MODIFIED, REJECTED).
  - Multi-signal batch validation with cumulative capacity tracking.

### 3. Package Exports
- **File**: `src/multi_agent_market_intelligence/risk/__init__.py`
- **Change**: Export `SignalRiskValidator` and `SignalValidator`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `SignalRiskValidator` and `SignalValidator`.

### 4. Unit Testing
- **File**: `tests/unit/test_signal_validator.py`
- **Change**: Implement comprehensive test suite tagged with `@pytest.mark.issue_18`:
  - `test_signal_validator_circuit_breaker_active_rejection`
  - `test_signal_validator_drawdown_and_daily_loss_rejection`
  - `test_signal_validator_concurrent_positions_limit`
  - `test_signal_validator_stop_loss_missing_and_geometry`
  - `test_signal_validator_risk_reward_ratio_validation`
  - `test_signal_validator_hold_and_sell_action_handling`
  - `test_signal_validator_risk_based_position_sizing`
  - `test_signal_validator_position_size_concentration_scaling`
  - `test_signal_validator_sector_exposure_limit_scaling`
  - `test_signal_validator_cash_buffer_constraint_scaling`
  - `test_signal_validator_gross_leverage_limit_scaling`
  - `test_signal_validator_batch_validation_cumulative_capacity`
  - `test_signal_validator_state_snapshot_compatibility`

### 5. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=18
make test
```

### 6. Git & Issue Finish
```bash
make finish-issue ID=18 MSG="feat(risk): implement SignalRiskValidator engine and capacity sizing logic"
```

## Decisions
- **Unified Decision Flow with Tri-State Outcomes**: Following domain contracts in `DecisionStatus`, trades are `APPROVED` if fully within risk bounds, `MODIFIED` if approved after scaling down to respect capacity caps, or `REJECTED` if a hard rule is breached.
- **Multi-Constraint Capacity Clamping**: When sizing BUY signals, available units are bounded by the strictest of four simultaneous constraints: single-position cap, sector allocation limit, free cash above the required cash reserve, and gross leverage ceiling.
- **Cumulative Batch Allocation Tracking**: To prevent concurrent signals in the same execution cycle from simultaneously claiming the same pool of free cash or leverage, `validate_signals_batch` optionally decrements a simulated balance sheet as orders are approved.
- **Dual State Hydration**: `SignalRiskValidator` natively accepts either `PortfolioTracker`, `PortfolioSnapshot`, or raw state dictionaries, allowing zero-overhead integration within LangGraph workflows.
