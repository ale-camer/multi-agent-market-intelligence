# Issue 16: Global Risk Limits Configuration

**Branch**: `feature/issue-16-global-risk-limits-configuration`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #17)
**Milestone**: M4 - Risk & Portfolio Manager Implementation

## Objective
Establish the foundational risk governance and quantitative limits configuration engine for Milestone 4 (Risk & Portfolio Manager Implementation). Implement strongly-typed risk configuration models (`RiskLimitsConfig`), breach violation classifications (`RiskViolationType`), verification outcomes (`RiskCheckResult`), and dynamic evaluation logic. The module enforces global portfolio-level boundaries including maximum single-position concentration, maximum portfolio drawdown, maximum daily loss, gross/net leverage caps, minimum cash reserves, sector allocation constraints, minimum risk-reward ratio, stop-loss requirements, and circuit-breaker triggers. This establishes the quantitative guardrails for downstream portfolio tracking (Issue 17), signal validation (Issue 18), and autonomous Risk & Portfolio Manager agent execution (Issue 19).

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/risk/models.py` defines strongly-typed risk models inheriting from `DomainStateModel`:
  - `RiskViolationType(StrEnum)`:
    - `EXCESSIVE_POSITION_SIZE = "EXCESSIVE_POSITION_SIZE"`
    - `MAX_PORTFOLIO_DRAWDOWN_EXCEEDED = "MAX_PORTFOLIO_DRAWDOWN_EXCEEDED"`
    - `MAX_DAILY_LOSS_EXCEEDED = "MAX_DAILY_LOSS_EXCEEDED"`
    - `EXCESSIVE_LEVERAGE = "EXCESSIVE_LEVERAGE"`
    - `INSUFFICIENT_CASH_BUFFER = "INSUFFICIENT_CASH_BUFFER"`
    - `MAX_SECTOR_EXPOSURE_EXCEEDED = "MAX_SECTOR_EXPOSURE_EXCEEDED"`
    - `MAX_CONCURRENT_POSITIONS_EXCEEDED = "MAX_CONCURRENT_POSITIONS_EXCEEDED"`
    - `MISSING_STOP_LOSS = "MISSING_STOP_LOSS"`
    - `INSUFFICIENT_RISK_REWARD = "INSUFFICIENT_RISK_REWARD"`
    - `CIRCUIT_BREAKER_ACTIVE = "CIRCUIT_BREAKER_ACTIVE"`
  - `RiskCheckResult(DomainStateModel)`:
    - `passed: bool = True`
    - `violations: list[RiskViolationType] = Field(default_factory=list)`
    - `reasons: list[str] = Field(default_factory=list)`
    - `metrics: dict[str, Any] = Field(default_factory=dict)`
    - `adjusted_size: float | None = None`
    - Helper methods: `add_violation(violation: RiskViolationType, reason: str) -> None`, `is_clean() -> bool`.
- [x] `src/multi_agent_market_intelligence/risk/config.py` implements `RiskLimitsConfig`:
  - Configurable parameters with robust Pydantic field validation:
    - `max_position_size_pct: float = 0.20` ($0.0 < x \le 1.0$)
    - `max_portfolio_drawdown_pct: float = 0.15` ($0.0 < x \le 1.0$)
    - `max_daily_loss_pct: float = 0.05` ($0.0 < x \le 1.0$)
    - `max_leverage: float = 1.0` ($x \ge 1.0$)
    - `min_cash_buffer_pct: float = 0.10` ($0.0 \le x < 1.0$)
    - `max_sector_exposure_pct: float = 0.35` ($0.0 < x \le 1.0$)
    - `max_open_positions: int = 10` ($x \ge 1$)
    - `stop_loss_required: bool = True`
    - `min_risk_reward_ratio: float = 1.5` ($x > 0.0$)
    - `circuit_breaker_active: bool = False`
  - Limit verification helper methods:
    - `validate_position_size(position_value: float, total_equity: float) -> tuple[bool, str | None]`
    - `validate_cash_buffer(cash: float, total_equity: float) -> tuple[bool, str | None]`
    - `validate_drawdown(current_drawdown_pct: float) -> tuple[bool, str | None]`
    - `validate_daily_loss(daily_loss_pct: float) -> tuple[bool, str | None]`
    - `validate_leverage(total_exposure: float, total_equity: float) -> tuple[bool, str | None]`
    - `validate_open_positions_count(current_positions: int) -> tuple[bool, str | None]`
    - `validate_risk_reward(target_price: float | None, stop_loss: float | None, current_price: float, action: SignalAction | str) -> tuple[bool, str | None]`
    - `evaluate_limits(...) -> RiskCheckResult` executing holistic risk parameter checks.
  - Profile preset factories:
    - `conservative_risk_limits() -> RiskLimitsConfig`
    - `moderate_risk_limits() -> RiskLimitsConfig`
    - `aggressive_risk_limits() -> RiskLimitsConfig`
  - Deserialization and export:
    - `to_dict() -> dict[str, Any]`
    - `from_dict(data: dict[str, Any]) -> RiskLimitsConfig`
- [x] `src/multi_agent_market_intelligence/risk/__init__.py` exposes `RiskLimitsConfig`, `RiskViolationType`, `RiskCheckResult`, and preset factories.
- [x] `src/multi_agent_market_intelligence/__init__.py` re-export public risk models and configurations.
- [x] Unit tests in `tests/unit/test_risk_limits.py` tagged with `@pytest.mark.issue_16` covering:
  - Default initialization, parameter boundary validations, and invalid value rejections.
  - Pre-configured profiles (`conservative`, `moderate`, `aggressive`).
  - Position sizing constraint checks (within limit vs breach vs exact boundary).
  - Cash buffer requirement checks.
  - Drawdown and daily loss breach evaluations.
  - Leverage calculations and limits.
  - Risk/reward ratio evaluations for both BUY and SELL actions.
  - Stop loss requirement enforcement.
  - Circuit breaker trip behavior.
  - Serialization to/from dictionary and JSON schemas.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=16` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=16 NAME=global-risk-limits-configuration
```

### 2. Risk Models and Violations
- **File**: `src/multi_agent_market_intelligence/risk/models.py`
- **Change**: Implement `RiskViolationType(StrEnum)` and `RiskCheckResult(DomainStateModel)`:
  - Enumeration of all discrete risk violation categories.
  - Outcome container with violation list, reasons, metrics, and sizing adjustments.

### 3. Global Risk Limits Configuration Engine
- **File**: `src/multi_agent_market_intelligence/risk/config.py`
- **Change**: Implement `RiskLimitsConfig(BaseModel)`:
  - Validated Pydantic fields for position caps, drawdown limits, leverage, cash reserves, and risk/reward minimums.
  - Granular validation helper methods for each dimension.
  - Composite `evaluate_limits(...)` method generating `RiskCheckResult`.
  - Preset factories: `conservative_risk_limits()`, `moderate_risk_limits()`, `aggressive_risk_limits()`.
  - `to_dict()` and `from_dict()`.

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/risk/__init__.py`
- **Change**: Export all public models and factories.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `RiskLimitsConfig`, `RiskViolationType`, `RiskCheckResult`, and preset factories.

### 5. Unit Testing
- **File**: `tests/unit/test_risk_limits.py`
- **Change**: Implement exhaustive test suite tagged with `@pytest.mark.issue_16`:
  - `test_risk_limits_default_initialization`
  - `test_risk_limits_field_validations_and_bounds`
  - `test_risk_limits_preset_profiles`
  - `test_validate_position_size_boundaries`
  - `test_validate_cash_buffer_enforcement`
  - `test_validate_drawdown_and_daily_loss`
  - `test_validate_leverage_limits`
  - `test_validate_open_positions_count`
  - `test_validate_risk_reward_ratio_buy_and_sell`
  - `test_validate_stop_loss_requirement`
  - `test_circuit_breaker_immediate_halt`
  - `test_evaluate_limits_composite_check`
  - `test_risk_limits_serialization_roundtrip`

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=16
make test
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=16 MSG="feat(risk): implement global risk limits configuration and validation engine"
```

## Decisions
- **Hierarchical Governance Architecture**: Risk parameters are encapsulated in a validated Pydantic model (`RiskLimitsConfig`) separating static governance from dynamic state tracking, ensuring risk tolerances can be customized per investment mandate without code alterations.
- **Itemized Violation Diagnostics**: Rather than a binary pass/fail boolean, `RiskCheckResult` provides itemized `RiskViolationType` members and explanatory messages, ensuring downstream agents and audit logs receive granular diagnostic rationale.
- **Directional Risk/Reward Calculus**: Risk/reward validation accounts for trade geometry in both long (`BUY`) and short (`SELL`) positions, rejecting orders with unfavorable asymmetry before position sizing calculations occur.
- **Circuit Breaker Fail-Safe**: A `circuit_breaker_active` flag provides a global kill-switch halting all trade proposals during periods of market stress or operational anomalies.
