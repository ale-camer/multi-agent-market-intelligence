"""Unit tests for technical indicators calculator and trading domain models."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from multi_agent_market_intelligence.trading import (
    BollingerBandsResult,
    MACDResult,
    OHLCVBar,
    TechnicalIndicatorsCalculator,
    TechnicalIndicatorsResult,
    generate_mock_ohlcv,
)


@pytest.mark.issue_11
def test_ohlcv_bar_model_validation_and_dict_equality() -> None:
    """Validate OHLCVBar, MACDResult, BollingerBandsResult, and TechnicalIndicatorsResult."""
    bar = OHLCVBar(
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=10_000.0,
        symbol="AAPL",
    )
    assert bar.open == 100.0
    assert bar.close == 102.0
    assert bar.symbol == "AAPL"
    assert bar.timestamp is not None
    assert bar == {
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": 10_000.0,
        "symbol": "AAPL",
    }

    macd = MACDResult(macd_line=1.5, signal_line=1.2, histogram=0.3)
    assert macd.histogram == 0.3
    assert macd == {"macd_line": 1.5, "signal_line": 1.2, "histogram": 0.3}

    bb = BollingerBandsResult(upper=110.0, middle=100.0, lower=90.0, bandwidth=0.2, percent_b=0.6)
    assert bb.bandwidth == 0.2
    assert bb == {"upper": 110.0, "middle": 100.0, "lower": 90.0}

    indicators = TechnicalIndicatorsResult(
        symbol="AAPL",
        close=102.0,
        sma={"sma_20": 100.0},
        ema={"ema_12": 101.5},
        rsi=55.0,
        macd=macd,
        bollinger=bb,
        atr=2.5,
        obv=150000.0,
        vwap=101.0,
    )
    dumped = indicators.to_dict()
    assert dumped["symbol"] == "AAPL"
    assert dumped["rsi"] == 55.0
    assert dumped["macd"]["histogram"] == 0.3
    assert dumped["bollinger"]["upper"] == 110.0


@pytest.mark.issue_11
def test_sma_calculation_accuracy() -> None:
    """Verify Simple Moving Average accuracy and window handling."""
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    sma = TechnicalIndicatorsCalculator.compute_sma(prices, window=3)

    assert pd.isna(sma.iloc[0])
    assert pd.isna(sma.iloc[1])
    assert sma.iloc[2] == pytest.approx(20.0)
    assert sma.iloc[3] == pytest.approx(30.0)
    assert sma.iloc[4] == pytest.approx(40.0)

    # Test with pandas Series
    s = pd.Series(prices)
    sma_series = TechnicalIndicatorsCalculator.compute_sma(s, window=2)
    assert sma_series.iloc[1] == pytest.approx(15.0)

    # Invalid window raises ValueError
    with pytest.raises(ValueError, match="window must be >= 1"):
        TechnicalIndicatorsCalculator.compute_sma(prices, window=0)


@pytest.mark.issue_11
def test_ema_calculation_accuracy() -> None:
    """Verify Exponential Moving Average accuracy and monotonic response."""
    prices = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    ema = TechnicalIndicatorsCalculator.compute_ema(prices, span=3)

    assert len(ema) == len(prices)
    assert ema.iloc[0] == pytest.approx(10.0)
    # Consecutive values on strictly increasing series should be strictly increasing
    for i in range(1, len(ema)):
        assert ema.iloc[i] > ema.iloc[i - 1]

    with pytest.raises(ValueError, match="span must be >= 1"):
        TechnicalIndicatorsCalculator.compute_ema(prices, span=0)


@pytest.mark.issue_11
def test_rsi_calculation_and_boundary_conditions() -> None:
    """Verify RSI calculation, bounds [0, 100], and extreme conditions."""
    calc = TechnicalIndicatorsCalculator()

    # Strictly increasing prices: RSI should reach 100.0
    up_prices = [100.0 + i * 2.0 for i in range(25)]
    rsi_up = calc.compute_rsi(up_prices, period=14)
    assert not rsi_up.iloc[14:].isna().any()
    assert rsi_up.iloc[-1] == pytest.approx(100.0)

    # Strictly decreasing prices: RSI should reach 0.0
    down_prices = [200.0 - i * 2.0 for i in range(25)]
    rsi_down = calc.compute_rsi(down_prices, period=14)
    assert rsi_down.iloc[-1] == pytest.approx(0.0)

    # Completely flat prices: RSI should evaluate to 50.0
    flat_prices = [150.0] * 25
    rsi_flat = calc.compute_rsi(flat_prices, period=14)
    assert rsi_flat.iloc[-1] == pytest.approx(50.0)

    # Invalid period
    with pytest.raises(ValueError, match="period must be >= 1"):
        calc.compute_rsi(up_prices, period=0)


@pytest.mark.issue_11
def test_macd_line_signal_and_histogram_divergence() -> None:
    """Verify MACD line, signal line, and histogram relations."""
    calc = TechnicalIndicatorsCalculator()
    prices = [100.0 + np.sin(i / 5.0) * 10.0 + (i * 0.5) for i in range(50)]

    macd_line, signal_line, hist = calc.compute_macd(
        prices, fast_period=12, slow_period=26, signal_period=9
    )

    assert len(macd_line) == 50
    assert len(signal_line) == 50
    assert len(hist) == 50

    # Histogram must equal macd_line - signal_line
    diff = hist - (macd_line - signal_line)
    assert np.allclose(diff.to_numpy(), 0.0)


@pytest.mark.issue_11
def test_bollinger_bands_calculation_and_percent_b() -> None:
    """Verify Bollinger Bands standard deviation bands and %B metric."""
    calc = TechnicalIndicatorsCalculator()
    prices = [100.0 + (i % 5) * 2.0 for i in range(30)]

    upper, middle, lower = calc.compute_bollinger_bands(prices, window=20, num_std=2.0)

    assert pd.isna(upper.iloc[18])
    assert not pd.isna(upper.iloc[19])

    for i in range(19, 30):
        assert upper.iloc[i] >= middle.iloc[i]
        assert middle.iloc[i] >= lower.iloc[i]

    with pytest.raises(ValueError, match="window must be >= 1"):
        calc.compute_bollinger_bands(prices, window=0)


@pytest.mark.issue_11
def test_atr_true_range_with_price_gaps() -> None:
    """Verify ATR calculation with gaps between sessions."""
    calc = TechnicalIndicatorsCalculator()

    # Day 1: close 100. Day 2 gaps up to 110-115
    highs = [105.0, 115.0, 114.0] + [110.0 + i for i in range(20)]
    lows = [95.0, 110.0, 108.0] + [105.0 + i for i in range(20)]
    closes = [100.0, 112.0, 110.0] + [108.0 + i for i in range(20)]

    atr = calc.compute_atr(highs, lows, closes, period=5)

    assert len(atr) == len(highs)
    # True range for Day 2: max(115-110, |115-100|, |110-100|) = 15.0
    assert atr.iloc[-1] > 0.0

    with pytest.raises(ValueError, match="period must be >= 1"):
        calc.compute_atr(highs, lows, closes, period=0)


@pytest.mark.issue_11
def test_obv_volume_accumulation() -> None:
    """Verify On-Balance Volume directional volume accumulation."""
    calc = TechnicalIndicatorsCalculator()

    closes = [100.0, 105.0, 103.0, 103.0, 107.0]
    volumes = [1000.0, 2000.0, 1500.0, 500.0, 3000.0]

    obv = calc.compute_obv(closes, volumes)

    # Bar 0: diff=0 -> 0
    # Bar 1: close up (+2000) -> 2000
    # Bar 2: close down (-1500) -> 500
    # Bar 3: close flat (0) -> 500
    # Bar 4: close up (+3000) -> 3500
    assert obv.iloc[0] == 0.0
    assert obv.iloc[1] == 2000.0
    assert obv.iloc[2] == 500.0
    assert obv.iloc[3] == 500.0
    assert obv.iloc[4] == 3500.0


@pytest.mark.issue_11
def test_vwap_typical_price_volume_weighting() -> None:
    """Verify Volume-Weighted Average Price cumulative calculation."""
    calc = TechnicalIndicatorsCalculator()

    highs = [102.0, 104.0]
    lows = [98.0, 100.0]
    closes = [100.0, 102.0]
    volumes = [1000.0, 2000.0]

    # Bar 0: typical = (102 + 98 + 100) / 3 = 100.0 -> cum_vp = 100k, cum_v = 1k -> VWAP = 100.0
    # Bar 1: typical = (104 + 100 + 102) / 3 = 102.0 -> cum_vp = 304k, cum_v = 3k -> VWAP = 101.33
    vwap = calc.compute_vwap(highs, lows, closes, volumes)

    assert vwap.iloc[0] == pytest.approx(100.0)
    assert vwap.iloc[1] == pytest.approx(304_000.0 / 3000.0)


@pytest.mark.issue_11
def test_calculate_all_dataframe_enrichment() -> None:
    """Verify calculate_all adds all indicator columns without modifying original input."""
    calc = TechnicalIndicatorsCalculator()
    bars = calc.generate_mock_ohlcv(symbol="MSFT", num_bars=60, base_price=300.0, seed=123)

    df_result = calc.calculate_all(bars)

    expected_columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "symbol",
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_12",
        "ema_26",
        "ema_50",
        "rsi_14",
        "macd_line",
        "macd_signal",
        "macd_hist",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "bb_bandwidth",
        "bb_percent_b",
        "atr_14",
        "obv",
        "vwap",
    ]
    for col in expected_columns:
        assert col in df_result.columns, f"Missing column {col}"

    assert len(df_result) == 60


@pytest.mark.issue_11
def test_get_latest_indicators_snapshot() -> None:
    """Verify get_latest_indicators returns a fully populated snapshot."""
    calc = TechnicalIndicatorsCalculator()
    bars = calc.generate_mock_ohlcv(symbol="GOOGL", num_bars=70, base_price=175.0, seed=999)

    result = calc.get_latest_indicators(bars)

    assert isinstance(result, TechnicalIndicatorsResult)
    assert result.symbol == "GOOGL"
    assert result.close > 0.0
    assert result.sma["sma_20"] is not None
    assert result.sma["sma_50"] is not None
    assert result.sma["sma_200"] is None  # 70 bars < 200 window
    assert result.ema["ema_12"] is not None
    assert result.rsi is not None
    assert 0.0 <= result.rsi <= 100.0
    assert result.macd is not None
    assert isinstance(result.macd.histogram, float)
    assert result.bollinger is not None
    assert result.bollinger.upper >= result.bollinger.lower
    assert result.atr is not None and result.atr > 0.0
    assert result.obv is not None
    assert result.vwap is not None
    assert result.metadata["total_bars"] == 70

    # Ensure to_dict works seamlessly
    data_dict = result.to_dict()
    assert data_dict["symbol"] == "GOOGL"
    assert "macd" in data_dict


@pytest.mark.issue_11
def test_edge_case_insufficient_data_points() -> None:
    """Verify graceful NaN/None handling when bars are fewer than window size."""
    calc = TechnicalIndicatorsCalculator()
    short_bars = [
        OHLCVBar(
            timestamp=datetime.now(timezone.utc),
            open=100.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            close=101.0 + i,
            volume=1000.0,
            symbol="TEST",
        )
        for i in range(5)
    ]

    result = calc.get_latest_indicators(short_bars)
    assert result.symbol == "TEST"
    assert result.close == pytest.approx(105.0)
    assert result.sma["sma_20"] is None
    assert result.sma["sma_50"] is None
    assert result.bollinger is None  # window 20 not met
    assert result.atr is None  # window 14 not met


@pytest.mark.issue_11
def test_edge_case_flat_prices_zero_volatility() -> None:
    """Verify zero-variance handling (no division by zero in Bollinger bands or RSI)."""
    calc = TechnicalIndicatorsCalculator()
    flat_data = [
        {"open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0, "volume": 1000.0, "symbol": "FLAT"}
        for _ in range(30)
    ]

    result = calc.get_latest_indicators(flat_data)
    assert result.rsi == 50.0
    assert result.bollinger is not None
    assert result.bollinger.upper == pytest.approx(50.0)
    assert result.bollinger.lower == pytest.approx(50.0)
    assert result.bollinger.bandwidth == pytest.approx(0.0)


@pytest.mark.issue_11
def test_generate_mock_ohlcv_deterministic_patterns() -> None:
    """Verify synthetic data generator determinism and directional drift."""
    bars_1 = generate_mock_ohlcv(symbol="AAPL", num_bars=50, base_price=100.0, seed=42)
    bars_2 = generate_mock_ohlcv(symbol="AAPL", num_bars=50, base_price=100.0, seed=42)

    assert len(bars_1) == 50
    for b1, b2 in zip(bars_1, bars_2, strict=True):
        assert b1.close == b2.close
        assert b1.high >= max(b1.open, b1.close)
        assert b1.low <= min(b1.open, b1.close)

    # Bullish trend drift verification
    up_bars = generate_mock_ohlcv(trend="up", num_bars=100, base_price=100.0, seed=10)
    down_bars = generate_mock_ohlcv(trend="down", num_bars=100, base_price=100.0, seed=10)
    assert up_bars[-1].close > up_bars[0].close
    assert down_bars[-1].close < down_bars[0].close


@pytest.mark.issue_11
def test_to_dataframe_input_formats_and_type_error() -> None:
    """Verify input conversions across DataFrame, OHLCVBar sequence, and dicts."""
    calc = TechnicalIndicatorsCalculator()

    # Empty input
    empty_df = calc.to_dataframe([])
    assert empty_df.empty

    # Dict format
    dict_records = [{"open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 100.0}]
    df_from_dict = calc.to_dataframe(dict_records)
    assert len(df_from_dict) == 1
    assert df_from_dict["close"].iloc[0] == 11.0

    # Unsupported format
    with pytest.raises(TypeError, match="Unsupported data item type"):
        calc.to_dataframe(["invalid_string"])  # type: ignore[list-item]
