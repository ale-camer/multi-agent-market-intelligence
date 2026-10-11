"""Unit tests for multi-factor quantitative trading signal generation."""

import pytest

from multi_agent_market_intelligence.state.models import SignalAction, TradingSignal
from multi_agent_market_intelligence.state.reducers import append_signals
from multi_agent_market_intelligence.trading import (
    BollingerBandsResult,
    FundamentalMetrics,
    MACDResult,
    SignalStrategyConfig,
    TechnicalIndicatorsResult,
    TradingSignalGenerator,
)


@pytest.fixture
def bullish_indicators() -> TechnicalIndicatorsResult:
    """Fixture providing technical indicators with a strong bullish posture."""
    return TechnicalIndicatorsResult(
        symbol="AAPL",
        close=150.0,
        sma={"sma_20": 145.0, "sma_50": 140.0, "sma_200": 130.0},
        ema={"ema_12": 152.0, "ema_26": 147.0},
        rsi=26.5,  # Oversold -> strong buy reversal indicator
        macd=MACDResult(macd_line=2.5, signal_line=1.2, histogram=1.3),
        bollinger=BollingerBandsResult(
            upper=160.0, middle=148.0, lower=136.0, bandwidth=0.16, percent_b=0.58
        ),
        atr=3.5,
        obv=2500000.0,
        vwap=148.5,
    )


@pytest.fixture
def bearish_indicators() -> TechnicalIndicatorsResult:
    """Fixture providing technical indicators with an overbought/bearish posture."""
    return TechnicalIndicatorsResult(
        symbol="XYZ",
        close=200.0,
        sma={"sma_20": 205.0, "sma_50": 210.0, "sma_200": 220.0},
        ema={"ema_12": 195.0, "ema_26": 202.0},
        rsi=78.5,  # Overbought -> sell indication
        macd=MACDResult(macd_line=-3.0, signal_line=-1.5, histogram=-1.5),
        bollinger=BollingerBandsResult(
            upper=215.0, middle=202.0, lower=189.0, bandwidth=0.13, percent_b=0.42
        ),
        atr=4.0,
        obv=-1500000.0,
        vwap=204.0,
    )


@pytest.fixture
def neutral_indicators() -> TechnicalIndicatorsResult:
    """Fixture providing balanced, neutral technical indicators."""
    return TechnicalIndicatorsResult(
        symbol="SPY",
        close=100.0,
        sma={"sma_50": 100.0},
        ema={"ema_12": 100.0, "ema_26": 100.0},
        rsi=50.0,
        macd=MACDResult(macd_line=0.0, signal_line=0.0, histogram=0.0),
        atr=2.0,
        vwap=100.0,
    )


@pytest.fixture
def strong_fundamentals() -> FundamentalMetrics:
    """Fixture providing strong, healthy corporate fundamentals."""
    return FundamentalMetrics(
        symbol="AAPL",
        pe_ratio=18.0,
        gross_margin=0.45,
        operating_margin=0.28,
        net_margin=0.22,
        roe=0.30,
        debt_to_equity=0.60,
        current_ratio=1.9,
        revenue_growth_yoy=0.15,
    )


@pytest.fixture
def distressed_fundamentals() -> FundamentalMetrics:
    """Fixture providing distressed, leveraged corporate fundamentals."""
    return FundamentalMetrics(
        symbol="XYZ",
        pe_ratio=None,  # Unprofitable
        operating_margin=-0.10,
        net_margin=-0.18,
        debt_to_equity=3.8,
        current_ratio=0.65,
        revenue_growth_yoy=-0.12,
    )


@pytest.mark.issue_13
def test_signal_strategy_config_defaults_and_validation() -> None:
    """Verify SignalStrategyConfig default parameters and dict equality."""
    config = SignalStrategyConfig()
    assert config.technical_weight == 0.50
    assert config.fundamental_weight == 0.35
    assert config.sentiment_weight == 0.15
    assert config.buy_threshold == 0.25
    assert config.sell_threshold == -0.25
    assert config.atr_stop_multiplier == 2.0
    assert config.risk_reward_ratio == 2.0
    assert config == {
        "technical_weight": 0.50,
        "fundamental_weight": 0.35,
        "buy_threshold": 0.25,
    }


@pytest.mark.issue_13
def test_generate_signal_bullish_confluence_produces_buy(
    bullish_indicators: TechnicalIndicatorsResult,
    strong_fundamentals: FundamentalMetrics,
) -> None:
    """Verify that bullish technicals, fundamentals, and sentiment yield a BUY signal."""
    generator = TradingSignalGenerator()
    signal = generator.generate_signal(
        symbol="AAPL",
        indicators=bullish_indicators,
        fundamentals=strong_fundamentals,
        sentiment_score=0.65,
    )

    assert signal.symbol == "AAPL"
    assert signal.action == SignalAction.BUY
    assert signal.confidence >= 0.40
    assert signal.target_price is not None
    assert signal.stop_loss is not None
    assert signal.target_price > bullish_indicators.close
    assert signal.stop_loss < bullish_indicators.close
    assert "RSI oversold" in signal.reasoning
    assert "Bullish MACD" in signal.reasoning
    assert "sentiment positive" in signal.reasoning


@pytest.mark.issue_13
def test_generate_signal_bearish_confluence_produces_sell(
    bearish_indicators: TechnicalIndicatorsResult,
    distressed_fundamentals: FundamentalMetrics,
) -> None:
    """Verify that overbought technicals and distressed fundamentals yield a SELL signal."""
    generator = TradingSignalGenerator()
    signal = generator.generate_signal(
        symbol="XYZ",
        indicators=bearish_indicators,
        fundamentals=distressed_fundamentals,
        sentiment_score=-0.75,
    )

    assert signal.symbol == "XYZ"
    assert signal.action == SignalAction.SELL
    assert signal.confidence >= 0.40
    assert signal.target_price is not None
    assert signal.stop_loss is not None
    assert signal.target_price < bearish_indicators.close
    assert signal.stop_loss > bearish_indicators.close
    assert "RSI overbought" in signal.reasoning
    assert "Bearish MACD" in signal.reasoning


@pytest.mark.issue_13
def test_generate_signal_conflicting_factors_produces_hold(
    bullish_indicators: TechnicalIndicatorsResult,
    distressed_fundamentals: FundamentalMetrics,
) -> None:
    """Verify that conflicting signals (technicals vs fundamentals) default to HOLD."""
    generator = TradingSignalGenerator()
    signal = generator.generate_signal(
        symbol="AAPL",
        indicators=bullish_indicators,
        fundamentals=distressed_fundamentals,
        sentiment_score=0.0,
    )

    assert signal.action == SignalAction.HOLD
    assert "Conflicting" in signal.reasoning
    assert signal.target_price is None
    assert signal.stop_loss is None


@pytest.mark.issue_13
def test_generate_signal_neutral_baseline_produces_hold(
    neutral_indicators: TechnicalIndicatorsResult,
) -> None:
    """Verify that balanced neutral inputs produce a HOLD signal with no stops."""
    generator = TradingSignalGenerator()
    signal = generator.generate_signal(
        symbol="SPY",
        indicators=neutral_indicators,
        fundamentals=None,
        sentiment_score=0.0,
    )

    assert signal.symbol == "SPY"
    assert signal.action == SignalAction.HOLD
    assert signal.target_price is None
    assert signal.stop_loss is None


@pytest.mark.issue_13
def test_risk_levels_atr_pricing_and_reward_ratio() -> None:
    """Verify risk levels calculation when ATR is present."""
    config = SignalStrategyConfig(atr_stop_multiplier=2.0, risk_reward_ratio=2.0)
    generator = TradingSignalGenerator(config=config)

    # 1. BUY scenario: price 100, ATR 2.5
    # stop_dist = 2.0 * 2.5 = 5.0 -> stop_loss = 95.0, target_dist = 10.0 -> target_price = 110.0
    target, stop = generator.calculate_risk_levels(100.0, SignalAction.BUY, atr=2.5)
    assert stop == pytest.approx(95.0)
    assert target == pytest.approx(110.0)

    # 2. SELL scenario: price 100, ATR 2.5
    # stop_loss = 105.0, target_price = 90.0
    target_sell, stop_sell = generator.calculate_risk_levels(100.0, SignalAction.SELL, atr=2.5)
    assert stop_sell == pytest.approx(105.0)
    assert target_sell == pytest.approx(90.0)

    # 3. HOLD scenario
    target_hold, stop_hold = generator.calculate_risk_levels(100.0, SignalAction.HOLD, atr=2.5)
    assert target_hold is None
    assert stop_hold is None


@pytest.mark.issue_13
def test_risk_levels_percentage_fallback_without_atr() -> None:
    """Verify defensive percentage fallback when ATR is missing."""
    config = SignalStrategyConfig(default_stop_loss_pct=0.05, risk_reward_ratio=2.0)
    generator = TradingSignalGenerator(config=config)

    # price 200, 5% stop distance = 10.0 -> stop = 190.0, target = 220.0
    target, stop = generator.calculate_risk_levels(200.0, SignalAction.BUY, atr=None)
    assert stop == pytest.approx(190.0)
    assert target == pytest.approx(220.0)


@pytest.mark.issue_13
def test_strategy_config_custom_thresholds_and_weights(
    bullish_indicators: TechnicalIndicatorsResult,
    strong_fundamentals: FundamentalMetrics,
) -> None:
    """Verify custom strategy configuration threshold adjustments."""
    # Set an unreachable buy threshold (e.g. 0.95)
    strict_config = SignalStrategyConfig(buy_threshold=0.95)
    strict_gen = TradingSignalGenerator(config=strict_config)

    signal = strict_gen.generate_signal(
        symbol="AAPL",
        indicators=bullish_indicators,
        fundamentals=strong_fundamentals,
        sentiment_score=0.50,
    )
    # Even strong bullish posture will not cross 0.95 -> resulting in HOLD
    assert signal.action == SignalAction.HOLD


@pytest.mark.issue_13
def test_graceful_handling_missing_fundamentals_or_sentiment(
    bullish_indicators: TechnicalIndicatorsResult,
) -> None:
    """Verify signal generation functions gracefully with only technical indicators."""
    generator = TradingSignalGenerator()
    signal = generator.generate_signal(
        symbol="AAPL",
        indicators=bullish_indicators,
        fundamentals=None,
        sentiment_score=None,
    )

    assert signal.symbol == "AAPL"
    assert signal.action == SignalAction.BUY
    assert signal.confidence > 0.30
    assert signal.target_price is not None


@pytest.mark.issue_13
def test_generate_signals_batch_execution(
    bullish_indicators: TechnicalIndicatorsResult,
    bearish_indicators: TechnicalIndicatorsResult,
    strong_fundamentals: FundamentalMetrics,
    distressed_fundamentals: FundamentalMetrics,
) -> None:
    """Verify batch signal generation across multiple instruments."""
    generator = TradingSignalGenerator()
    batch_data = [
        {
            "symbol": "AAPL",
            "indicators": bullish_indicators,
            "fundamentals": strong_fundamentals,
            "sentiment_score": 0.5,
        },
        {
            "symbol": "XYZ",
            "indicators": bearish_indicators,
            "fundamentals": distressed_fundamentals,
            "sentiment_score": -0.6,
        },
    ]

    results = generator.generate_signals_batch(batch_data)
    assert len(results) == 2
    assert results[0].symbol == "AAPL"
    assert results[0].action == SignalAction.BUY
    assert results[1].symbol == "XYZ"
    assert results[1].action == SignalAction.SELL


@pytest.mark.issue_13
def test_trading_signal_dictionary_and_state_reducer_compatibility(
    bullish_indicators: TechnicalIndicatorsResult,
) -> None:
    """Verify generated TradingSignal is fully compatible with LangGraph state append reducers."""
    generator = TradingSignalGenerator()
    signal = generator.generate_signal(
        symbol="AAPL",
        indicators=bullish_indicators,
    )

    # Validate attached metrics in indicators dict
    assert "composite_score" in signal.indicators
    assert "technical_score" in signal.indicators

    # Test state reducer integration
    state_signals: list[TradingSignal] = []
    updated = append_signals(state_signals, signal)
    assert len(updated) == 1
    assert updated[0].symbol == "AAPL"

    # Also test appending a second signal as raw dictionary
    second_signal = generator.generate_signal(
        symbol="MSFT",
        indicators={"close": 320.0, "rsi": 30.0},
    )
    updated_dict = append_signals(updated, second_signal.model_dump())
    assert len(updated_dict) == 2
    assert isinstance(updated_dict[1], TradingSignal)
    assert updated_dict[1].symbol == "MSFT"
