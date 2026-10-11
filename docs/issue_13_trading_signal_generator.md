# Issue 13: Trading Signal Generator

**Branch**: `feature/issue-13-trading-signal-generator`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #14)
**Milestone**: M3 - Trading Analyst Implementation

## Objective
Implement a multi-factor Trading Signal Generator that synthesizes quantitative technical indicators (Issue 11), corporate fundamental metrics (Issue 12), and research sentiment (Milestone 2) into deterministic, actionable `TradingSignal`s. The generator evaluates momentum, trend alignment, volatility boundaries, valuation, financial solvency, and news sentiment using configurable strategy weights and decision thresholds. For directional signals (`BUY`, `SELL`), it dynamically calculates risk parameters (`target_price`, `stop_loss`) using volatility-based Average True Range (ATR) multiples and risk-reward ratios, providing transparent reasoning and indicator snapshots for downstream validation by the Risk & Portfolio Manager (Milestone 4).

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/trading/models.py` defines `SignalStrategyConfig(DomainStateModel)`:
  - Weights: `technical_weight: float = 0.50`, `fundamental_weight: float = 0.35`, `sentiment_weight: float = 0.15`
  - Thresholds: `buy_threshold: float = 0.25`, `sell_threshold: float = -0.25`, `min_confidence: float = 0.30`
  - Technical parameters: `rsi_oversold: float = 30.0`, `rsi_overbought: float = 70.0`, `macd_weight: float = 0.35`, `rsi_weight: float = 0.35`, `trend_weight: float = 0.30`
  - Risk parameters: `atr_stop_multiplier: float = 2.0`, `risk_reward_ratio: float = 2.0`, `default_stop_loss_pct: float = 0.05`
- [x] `src/multi_agent_market_intelligence/trading/signals.py` implements `TradingSignalGenerator`:
  - `__init__(config: SignalStrategyConfig | None = None)`: initializes with default or custom strategy parameters.
  - `evaluate_technical_score(indicators: TechnicalIndicatorsResult | dict[str, Any]) -> tuple[float, list[str]]`: evaluates RSI, MACD, Moving Averages, Bollinger Bands, and VWAP, returning normalized score in $[-1.0, 1.0]$ and reason items.
  - `evaluate_fundamental_score(fundamentals: FundamentalMetrics | dict[str, Any] | None) -> tuple[float, list[str]]`: evaluates valuation (P/E), profitability margins, solvency (D/E, current ratio), and revenue growth, returning score in $[-1.0, 1.0]$ and reason items.
  - `calculate_risk_levels(current_price: float, action: SignalAction, atr: float | None = None) -> tuple[float | None, float | None]`: computes volatility-adaptive target price and stop loss.
  - `generate_signal(symbol: str, indicators: TechnicalIndicatorsResult | dict[str, Any], fundamentals: FundamentalMetrics | dict[str, Any] | None = None, sentiment_score: float | None = None, current_price: float | None = None) -> TradingSignal`: evaluates composite score, resolves `SignalAction` (`BUY`, `SELL`, `HOLD`), computes confidence and risk levels, and attaches indicator snapshots.
  - `generate_signals_batch(data_items: list[dict[str, Any]]) -> list[TradingSignal]`: batch generates signals across multiple assets.
- [x] `src/multi_agent_market_intelligence/trading/__init__.py` and `src/multi_agent_market_intelligence/__init__.py` export `SignalStrategyConfig` and `TradingSignalGenerator`.
- [x] Unit tests in `tests/unit/test_trading_signals.py` tagged with `@pytest.mark.issue_13` covering:
  - Strong Bullish confluence (oversold RSI + positive MACD + strong fundamentals + positive sentiment) -> `BUY` with valid target and stop loss.
  - Strong Bearish confluence (overbought RSI + negative MACD + distressed fundamentals + negative sentiment) -> `SELL` with valid target and stop loss.
  - Conflicting signals (bullish technicals + distressed fundamentals) -> `HOLD` or attenuated confidence.
  - Neutral baseline (neutral indicators and fundamentals) -> `HOLD`.
  - ATR volatility-based risk pricing vs default percentage stop loss fallback.
  - Configurable weight adjustments and threshold overrides.
  - Missing fundamental or sentiment data graceful degradation.
  - Batch generation across ticker lists.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=13` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=13 NAME=trading-signal-generator
```

### 2. Signal Strategy Configuration Model
- **File**: `src/multi_agent_market_intelligence/trading/models.py`
- **Change**: Define `SignalStrategyConfig(DomainStateModel)`:
  - Strategy weights (`technical_weight`, `fundamental_weight`, `sentiment_weight`).
  - Action thresholds (`buy_threshold`, `sell_threshold`, `min_confidence`).
  - Technical indicator bounds (`rsi_oversold`, `rsi_overbought`).
  - Risk parameters (`atr_stop_multiplier`, `risk_reward_ratio`, `default_stop_loss_pct`).

### 3. Trading Signal Generator Engine
- **File**: `src/multi_agent_market_intelligence/trading/signals.py`
- **Change**: Implement `TradingSignalGenerator`:
  - Sub-evaluators:
    - `evaluate_technical_score`: evaluates momentum (RSI), trend (EMA/SMA crossovers), MACD histogram, Bollinger %B, and VWAP.
    - `evaluate_fundamental_score`: evaluates valuation P/E, profitability margins, solvency leverage, and revenue growth.
    - `evaluate_sentiment_score`: incorporates sentiment in $[-1.0, 1.0]$.
  - Dynamic risk sizing: `calculate_risk_levels` with ATR-based stop loss and target price.
  - Composite synthesizer: `generate_signal` producing strongly-typed `TradingSignal`s adhering to state schema reducers.
  - Batch executor: `generate_signals_batch`.

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/trading/__init__.py`
- **Change**: Export `SignalStrategyConfig`, `TradingSignalGenerator`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `SignalStrategyConfig` and `TradingSignalGenerator`.

### 5. Unit Testing
- **File**: `tests/unit/test_trading_signals.py`
- **Change**: Implement comprehensive test suite tagged with `@pytest.mark.issue_13`:
  - `test_signal_strategy_config_defaults_and_validation`
  - `test_generate_signal_bullish_confluence_produces_buy`
  - `test_generate_signal_bearish_confluence_produces_sell`
  - `test_generate_signal_conflicting_factors_produces_hold`
  - `test_generate_signal_neutral_baseline_produces_hold`
  - `test_risk_levels_atr_pricing_and_reward_ratio`
  - `test_risk_levels_percentage_fallback_without_atr`
  - `test_strategy_config_custom_thresholds_and_weights`
  - `test_graceful_handling_missing_fundamentals_or_sentiment`
  - `test_generate_signals_batch_execution`
  - `test_trading_signal_dictionary_and_state_reducer_compatibility`

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=13
make test
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=13 MSG="feat(trading): implement multi-factor trading signal generator and strategy configuration"
```

## Decisions
- **Multi-Factor Weighted Scoring Framework**: Rather than relying on rigid boolean rules, the generator computes a normalized composite score in $[-1.0, 1.0]$ blending technical, fundamental, and sentiment dimensions with configurable weights. This allows nuanced trade generation that handles conflicting signals smoothly.
- **Adaptive ATR Risk Sizing with Fallback**: Risk parameters (`stop_loss`, `target_price`) are dynamically derived using Average True Range (ATR) multiples ($2 \times \text{ATR}$) to adapt stops to current asset volatility. When historical ATR is unavailable, the generator defaults to a defensive fixed percentage ($5\%$) to guarantee valid risk parameters.
- **Transparent Reasoning Traces**: Every generated `TradingSignal` populates the `reasoning` attribute with an itemized string of supporting factors (e.g., `"RSI oversold (26.4); Bullish MACD crossover; High operating margin (28.0%); Strong net sentiment (+0.42)"`) for full explainability and downstream audit logging.
- **State Reducer Seamlessness**: The output strictly matches `TradingSignal` from `multi_agent_market_intelligence.state.models`, ensuring immediate compatibility with the orchestrator state reducer channel `append_signals`.
