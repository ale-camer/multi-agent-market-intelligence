# Issue 15: Trading Analyst Signal Tests

**Branch**: `feature/issue-15-trading-analyst-signal-tests`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #16)
**Milestone**: M3 - Trading Analyst Implementation

## Objective
Establish a comprehensive end-to-end signal testing harness and edge-case validation suite for the `TradingAnalystAgent` and `TradingSignalGenerator`. Validate trading signal generation across diverse market regimes (strong bullish breakouts, severe bearish breakdowns, sideways/choppy conditions), factor discrepancy resolution (conflicting technical vs fundamental drivers), degenerate and extreme price time-series (flat prices, micro-volatility, sparse data, missing metrics), multi-asset batch evaluations, message broadcasting with payload validation, and multi-cycle LangGraph DAG orchestration integration. This completes Milestone 3 (Trading Analyst Implementation).

## Acceptance Criteria
- [x] `tests/unit/test_trading_analyst_signal_tests.py` marked with `@pytest.mark.issue_15` implements:
  - **Market Regime & Directional Dynamics**:
    - Strong Bullish Breakout: golden cross (EMA 12 > EMA 26, SMA 50), bullish MACD histogram, oversold rebound / momentum RSI, healthy fundamentals, and positive research sentiment producing a `BUY` signal with ATR-expanded target price and stop loss.
    - Crisis Bearish Breakdown: death cross, price below moving averages, negative MACD histogram, high debt/negative margins, and negative sentiment producing a `SELL` signal with risk-managed short stop loss and target price.
    - Neutral / Choppy Range: oscilating technicals around mean, mixed or near-zero indicators, balanced fundamentals producing a `HOLD` signal with `target_price=None` and `stop_loss=None`.
  - **Factor Conflict & Discrepancy Resolution**:
    - Discrepancy Scenarios: strong bullish technical momentum paired with distressed corporate fundamentals (negative margins, high leverage, elevated P/E) triggering conflict dampening, reduced confidence, and safe default to `HOLD`.
    - Partial / Incomplete Inputs: graceful fallback when fundamental metrics are absent, ATR is unavailable (default percentage stop-loss fallback), or research sentiment is neutral/omitted.
  - **Degenerate & Boundary Market Data**:
    - Constant / flat price series (zero price change across bars) verifying zero division protection in RSI, Bollinger Bands, and MACD.
    - Minimal bar history (< window lengths) verifying safe fallback without raising unhandled runtime exceptions.
    - Extreme price volatility shocks and gap movements.
  - **Batch & Multi-Asset Signal Generation**:
    - Multi-symbol evaluation asserting independent state calculation, distinct stop-loss/target levels, and isolated audit trails per ticker.
  - **Inter-Agent Messaging & Bus Broadcast Integrity**:
    - End-to-end event broadcasting where `TradingAnalystAgent` publishes `SIGNAL_PROPOSAL` to `recipient="risk_manager"` with correlation ID, complete signal payload, confidence metrics, and reasoning.
  - **Multi-Node & Multi-Cycle Orchestrator DAG Stress Testing**:
    - Compiled `MarketIntelligenceOrchestrator` execution running sequentially from Research Agent to Trading Analyst across multiple cycles, validating reducer state accumulation (`append_signals`, `append_artifacts`, `append_records`).
  - **Asynchronous Execution & Concurrency**:
    - Validation of `process_async` and `execute_async` under concurrent test execution.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=15` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=15 NAME=trading-analyst-signal-tests
```

### 2. Comprehensive Trading Analyst Signal Test Suite
- **File**: `tests/unit/test_trading_analyst_signal_tests.py`
- **Change**: Implement exhaustive test suite tagged with `@pytest.mark.issue_15`:
  - `test_trading_analyst_bullish_breakout_regime`: validates strong buy signal generation under aligned bullish technical, fundamental, and sentiment factors.
  - `test_trading_analyst_bearish_breakdown_regime`: validates sell signal generation under aligned bearish technical breakdown and negative fundamentals.
  - `test_trading_analyst_neutral_choppy_regime`: validates hold signal with null stop/target under sideways consolidation.
  - `test_trading_analyst_factor_conflict_dampening`: validates that conflicting factors (bullish technicals vs bearish fundamentals) dampen confidence and trigger safe hold.
  - `test_trading_analyst_missing_fundamentals_fallback`: validates signal generation relying on technicals and sentiment when fundamentals are unavailable.
  - `test_trading_analyst_missing_atr_percentage_stop_loss`: validates fallback to percentage-based stop loss and target price when ATR is None or zero.
  - `test_trading_analyst_flat_price_series_zero_division_safety`: validates numerical stability against zero variance and constant price time-series.
  - `test_trading_analyst_insufficient_bars_graceful_handling`: validates handling of sparse bar sequences shorter than standard indicator windows.
  - `test_trading_analyst_batch_multi_symbol_evaluation`: validates batch generation across diverse assets with distinct risk levels.
  - `test_trading_analyst_message_bus_proposal_contract`: validates structured payload and correlation ID preservation on MessageBus dispatch.
  - `test_trading_analyst_orchestrator_multi_cycle_dag_execution`: validates multi-cycle LangGraph DAG execution with state reducer accumulation.
  - `test_trading_analyst_async_execution_stress`: validates async lifecycle under asynchronous execution.

### 3. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=15
make test
```

### 4. Git & Issue Finish
```bash
make finish-issue ID=15 MSG="test(trading): implement comprehensive signal tests and edge-case harness for TradingAnalystAgent"
```

## Decisions
- **Deterministic Synthesized Market Scenarios**: Test scenarios synthesize realistic market conditions (such as trend breakouts, liquidity crunches, and sideways ranges) programmatically rather than mocking internal helper calls, ensuring genuine integration testing of indicators, fundamentals, and signal weighting logic.
- **Factor Conflict Safety**: In quantitative finance, high technical momentum in a fundamentally failing firm represents value trap or squeeze risk; explicit tests verify that factor conflict detection functions conservatively by triggering HOLD.
- **End-to-End Multi-Cycle DAG Validation**: Validating the full DAG (`ResearchAgent` -> `TradingAnalystAgent` -> `MarketIntelligenceOrchestrator`) across multiple consecutive execution cycles verifies state reducer stability before introducing Milestone 4 (Risk & Portfolio Manager).
