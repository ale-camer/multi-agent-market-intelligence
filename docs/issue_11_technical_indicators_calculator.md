# Issue 11: Technical Indicators Calculator

**Branch**: `feature/issue-11-technical-indicators-calculator`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #12)
**Milestone**: M3 - Trading Analyst Implementation

## Objective
Implement a robust, vectorized Technical Indicators Calculator for the Trading Analyst module. This forms the analytical foundation for Milestone 3 by processing time-series market price data (OHLCV bars) and computing key quantitative indicators: Moving Averages (SMA, EMA), Momentum (RSI), Trend/Convergence (MACD), Volatility (Bollinger Bands, ATR), and Volume analysis (OBV, VWAP). The module provides strongly-typed domain models (`OHLCVBar`, `TechnicalIndicatorsResult`), comprehensive validation (insufficient history, zero-variance, NaN handling), synthetic market data generation for offline testing, and direct compatibility with `TradingSignal.indicators`.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/trading/models.py` defines domain models inheriting from `DomainStateModel`:
  - `OHLCVBar`: `timestamp: datetime`, `open: float`, `high: float`, `low: float`, `close: float`, `volume: float = 0.0`, `symbol: str | None = None`.
  - `MACDResult`: `macd_line: float`, `signal_line: float`, `histogram: float`.
  - `BollingerBandsResult`: `upper: float`, `middle: float`, `lower: float`, `bandwidth: float`, `percent_b: float`.
  - `TechnicalIndicatorsResult`: `symbol: str | None = None`, `timestamp: datetime`, `close: float`, `sma: dict[str, float | None]`, `ema: dict[str, float | None]`, `rsi: float | None`, `macd: MACDResult | None`, `bollinger: BollingerBandsResult | None`, `atr: float | None`, `obv: float | None`, `vwap: float | None`, `metadata: dict[str, Any]`.
- [x] `src/multi_agent_market_intelligence/trading/indicators.py` implements `TechnicalIndicatorsCalculator`:
  - `compute_sma(prices: pd.Series | list[float], window: int) -> pd.Series | list[float]`.
  - `compute_ema(prices: pd.Series | list[float], span: int) -> pd.Series | list[float]`.
  - `compute_rsi(prices: pd.Series | list[float], period: int = 14) -> pd.Series | list[float]` using Wilder's exponential smoothing with bounds $[0.0, 100.0]$.
  - `compute_macd(prices: pd.Series | list[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]`.
  - `compute_bollinger_bands(prices: pd.Series | list[float], window: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]`.
  - `compute_atr(high: pd.Series | list[float], low: pd.Series | list[float], close: pd.Series | list[float], period: int = 14) -> pd.Series | list[float]`.
  - `compute_obv(close: pd.Series | list[float], volume: pd.Series | list[float]) -> pd.Series | list[float]`.
  - `compute_vwap(high: pd.Series | list[float], low: pd.Series | list[float], close: pd.Series | list[float], volume: pd.Series | list[float]) -> pd.Series | list[float]`.
  - `calculate_all(data: pd.DataFrame | list[OHLCVBar] | list[dict[str, Any]]) -> pd.DataFrame` enriching data with all indicator columns.
  - `get_latest_indicators(data: pd.DataFrame | list[OHLCVBar] | list[dict[str, Any]], symbol: str | None = None) -> TechnicalIndicatorsResult` producing typed snapshot for `TradingSignal.indicators`.
  - `generate_mock_ohlcv(symbol: str = "AAPL", num_bars: int = 100, base_price: float = 150.0, trend: str = "neutral", seed: int | None = 42) -> list[OHLCVBar]` producing deterministic synthetic price series.
- [x] `src/multi_agent_market_intelligence/trading/__init__.py` and `src/multi_agent_market_intelligence/__init__.py` export all public models and calculator tools.
- [x] Unit tests in `tests/unit/test_technical_indicators.py` tagged with `@pytest.mark.issue_11` covering:
  - Mathematical correctness against known numerical series (SMA, EMA, RSI, MACD, Bollinger, ATR, OBV, VWAP).
  - Edge cases: fewer data points than indicator window, constant/zero-volatility prices, zero volume, NaN/missing values.
  - Multi-input format conversion (`DataFrame`, `list[OHLCVBar]`, `list[dict]`).
  - Synthetic data generation determinism and structure.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=11` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=11 NAME=technical-indicators-calculator
```

### 2. Trading Domain Models
- **File**: `src/multi_agent_market_intelligence/trading/models.py`
- **Change**: Define `OHLCVBar`, `MACDResult`, `BollingerBandsResult`, and `TechnicalIndicatorsResult` inheriting from `DomainStateModel` (supporting dict comparisons and Pydantic serialization).

### 3. Technical Indicators Calculator Engine
- **File**: `src/multi_agent_market_intelligence/trading/indicators.py`
- **Change**: Implement `TechnicalIndicatorsCalculator`:
  - Static and instance methods for vectorized calculation with pandas/numpy:
    - `compute_sma`
    - `compute_ema`
    - `compute_rsi` (Wilder's exponential smoothing)
    - `compute_macd` (fast, slow, signal, histogram)
    - `compute_bollinger_bands` (upper, middle, lower, bandwidth, %B)
    - `compute_atr` (True Range with gap handling and Wilder smoothing)
    - `compute_obv` (directional cumulative volume)
    - `compute_vwap` (typical price cumulative volume weighting)
  - Data ingestion adapter: `to_dataframe` supporting `DataFrame`, `list[OHLCVBar]`, and `list[dict[str, Any]]` with sorting and column normalization.
  - High-level methods:
    - `calculate_all(data) -> pd.DataFrame`
    - `get_latest_indicators(data, symbol) -> TechnicalIndicatorsResult`
    - `generate_mock_ohlcv(symbol, num_bars, base_price, trend, seed) -> list[OHLCVBar]`

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/trading/__init__.py`
- **Change**: Export `OHLCVBar`, `MACDResult`, `BollingerBandsResult`, `TechnicalIndicatorsResult`, `TechnicalIndicatorsCalculator`, `generate_mock_ohlcv`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export public trading types and `TechnicalIndicatorsCalculator`.

### 5. Unit Testing
- **File**: `tests/unit/test_technical_indicators.py`
- **Change**: Implement exhaustive test suite tagged with `@pytest.mark.issue_11`:
  - `test_ohlcv_bar_model_validation_and_dict_equality`
  - `test_sma_calculation_accuracy`
  - `test_ema_calculation_accuracy`
  - `test_rsi_calculation_and_boundary_conditions` (extremes 0, 100, neutral 50)
  - `test_macd_line_signal_and_histogram_divergence`
  - `test_bollinger_bands_calculation_and_percent_b`
  - `test_atr_true_range_with_price_gaps`
  - `test_obv_volume_accumulation`
  - `test_vwap_typical_price_volume_weighting`
  - `test_calculate_all_dataframe_enrichment`
  - `test_get_latest_indicators_snapshot`
  - `test_edge_case_insufficient_data_points`
  - `test_edge_case_flat_prices_zero_volatility`
  - `test_generate_mock_ohlcv_deterministic_patterns`

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=11
make test
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=11 MSG="feat(trading): implement technical indicators calculator and domain models"
```

## Decisions
- **Vectorized Pandas/Numpy Implementation**: Utilize pandas rolling/ewm primitives to ensure fast vector calculations while preserving full precision and compatibility with data pipelines.
- **Wilder's Smoothing for RSI & ATR**: Implement standard market-standard Wilder smoothing ($\alpha = 1/\text{period}$) rather than simple moving averages to align with industry expectations.
- **Graceful Insufficient Data Degradation**: For datasets with fewer rows than an indicator's required lookback window, compute functions return `NaN` (or `None` in typed result models) rather than raising exceptions, enabling partial indicators calculation when historical depth is limited.
- **Multi-Format Input Support**: The calculator accepts pandas `DataFrame`, `list[OHLCVBar]`, or raw `list[dict[str, Any]]` to minimize adapter overhead across agents and orchestrator state protocols.
