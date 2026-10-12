"""Comprehensive signal tests and edge-case validation for TradingAnalystAgent."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import anyio
import pytest

from multi_agent_market_intelligence.messaging import MessageBus, MessageType
from multi_agent_market_intelligence.orchestrator import (
    MarketIntelligenceOrchestrator,
    create_initial_state,
)
from multi_agent_market_intelligence.research import (
    create_research_node_handler,
)
from multi_agent_market_intelligence.state import (
    ResearchArtifact,
    SignalAction,
    create_market_state,
)
from multi_agent_market_intelligence.trading import (
    FundamentalDataLoader,
    FundamentalMetrics,
    MACDResult,
    OHLCVBar,
    TechnicalIndicatorsResult,
    TradingAnalystAgent,
    create_trading_analyst_node_handler,
)


@pytest.mark.issue_15
def test_trading_analyst_bullish_breakout_regime() -> None:
    """Validate strong BUY signal under aligned bullish technicals, fundamentals, and sentiment."""
    agent = TradingAnalystAgent()
    bullish_tech = TechnicalIndicatorsResult(
        symbol="BULL",
        close=150.0,
        sma={"sma_20": 145.0, "sma_50": 140.0, "sma_200": 130.0},
        ema={"ema_12": 152.0, "ema_26": 146.0},
        rsi=25.0,  # Oversold rebound / momentum
        macd=MACDResult(macd_line=3.0, signal_line=1.5, histogram=1.5),
        atr=4.0,
        vwap=148.0,
    )
    strong_fund = FundamentalMetrics(
        symbol="BULL",
        pe_ratio=16.0,
        gross_margin=0.50,
        operating_margin=0.30,
        net_margin=0.25,
        roe=0.35,
        debt_to_equity=0.45,
        current_ratio=2.2,
        revenue_growth_yoy=0.25,
    )
    synthesis_artifact = ResearchArtifact(
        headline="Market Intelligence Synthesis for BULL",
        summary="Consolidated intelligence: Strong bullish outlook.",
        sentiment_score=0.85,
        source="research_agent_synthesis",
        timestamp=datetime.now(timezone.utc),
        metadata={"symbol": "BULL", "is_synthesis": True, "composite_score": 0.85},
    )
    state = create_market_state(
        artifacts=[synthesis_artifact],
        context={
            "symbol": "BULL",
            "indicators": {"BULL": bullish_tech},
            "fundamentals": {"BULL": strong_fund},
        },
    )
    updates = agent.process(state)
    assert updates["current_step"] == "trading_analyst"
    signals = updates["signals"]
    assert len(signals) == 1
    sig = signals[0]
    assert sig.symbol == "BULL"
    assert sig.action == SignalAction.BUY
    assert sig.confidence >= 0.60
    assert sig.target_price is not None and sig.stop_loss is not None
    assert sig.target_price > 150.0
    assert sig.stop_loss < 150.0
    assert "positive" in sig.reasoning.lower() or "rsi oversold" in sig.reasoning.lower()


@pytest.mark.issue_15
def test_trading_analyst_bearish_breakdown_regime() -> None:
    """Validate SELL signal under aligned bearish technical breakdown and weak fundamentals."""
    agent = TradingAnalystAgent()
    bearish_tech = TechnicalIndicatorsResult(
        symbol="BEAR",
        close=80.0,
        sma={"sma_20": 85.0, "sma_50": 90.0, "sma_200": 95.0},
        ema={"ema_12": 78.0, "ema_26": 84.0},
        rsi=82.0,  # Overbought or breakdown
        macd=MACDResult(macd_line=-2.5, signal_line=-1.0, histogram=-1.5),
        atr=3.0,
        vwap=85.0,
    )
    weak_fund = FundamentalMetrics(
        symbol="BEAR",
        pe_ratio=55.0,
        gross_margin=0.15,
        operating_margin=-0.05,
        net_margin=-0.12,
        roe=-0.10,
        debt_to_equity=3.5,
        current_ratio=0.7,
        revenue_growth_yoy=-0.15,
    )
    synthesis_artifact = ResearchArtifact(
        headline="Market Intelligence Synthesis for BEAR",
        summary="Consolidated intelligence: Severe operational headwinds.",
        sentiment_score=-0.80,
        source="research_agent_synthesis",
        timestamp=datetime.now(timezone.utc),
        metadata={"symbol": "BEAR", "is_synthesis": True, "composite_score": -0.80},
    )
    state = create_market_state(
        artifacts=[synthesis_artifact],
        context={
            "symbol": "BEAR",
            "indicators": {"BEAR": bearish_tech},
            "fundamentals": {"BEAR": weak_fund},
        },
    )
    updates = agent.process(state)
    signals = updates["signals"]
    assert len(signals) == 1
    sig = signals[0]
    assert sig.symbol == "BEAR"
    assert sig.action == SignalAction.SELL
    assert sig.confidence >= 0.50
    assert sig.target_price is not None and sig.stop_loss is not None
    assert sig.target_price < 80.0
    assert sig.stop_loss > 80.0


@pytest.mark.issue_15
def test_trading_analyst_neutral_choppy_regime() -> None:
    """Validate HOLD signal with null risk levels under sideways market consolidation."""
    agent = TradingAnalystAgent()
    neutral_tech = TechnicalIndicatorsResult(
        symbol="CHOP",
        close=100.0,
        sma={"sma_50": 100.0},
        ema={"ema_12": 100.0, "ema_26": 100.0},
        rsi=50.0,
        macd=MACDResult(macd_line=0.0, signal_line=0.0, histogram=0.0),
        atr=2.0,
        vwap=100.0,
    )
    neutral_fund = FundamentalMetrics(
        symbol="CHOP",
        pe_ratio=25.0,
        gross_margin=0.30,
        operating_margin=0.12,
        net_margin=0.08,
        roe=0.12,
        debt_to_equity=1.0,
        current_ratio=1.2,
        revenue_growth_yoy=0.03,
    )
    state = create_market_state(
        context={
            "symbol": "CHOP",
            "indicators": {"CHOP": neutral_tech},
            "fundamentals": {"CHOP": neutral_fund},
        },
    )
    updates = agent.process(state)
    signals = updates["signals"]
    assert len(signals) == 1
    sig = signals[0]
    assert sig.symbol == "CHOP"
    assert sig.action == SignalAction.HOLD
    assert sig.target_price is None
    assert sig.stop_loss is None


@pytest.mark.issue_15
def test_trading_analyst_factor_conflict_dampening() -> None:
    """Validate that conflicting factors trigger confidence dampening and default to HOLD."""
    agent = TradingAnalystAgent()
    bullish_tech = TechnicalIndicatorsResult(
        symbol="CONFLICT",
        close=120.0,
        sma={"sma_50": 100.0},
        ema={"ema_12": 125.0, "ema_26": 115.0},
        rsi=25.0,
        macd=MACDResult(macd_line=4.0, signal_line=2.0, histogram=2.0),
        atr=3.0,
    )
    distressed_fund = FundamentalMetrics(
        symbol="CONFLICT",
        pe_ratio=80.0,
        gross_margin=0.05,
        operating_margin=-0.20,
        net_margin=-0.25,
        roe=-0.30,
        debt_to_equity=5.0,
        current_ratio=0.5,
        revenue_growth_yoy=-0.20,
    )
    state = create_market_state(
        context={
            "symbol": "CONFLICT",
            "indicators": {"CONFLICT": bullish_tech},
            "fundamentals": {"CONFLICT": distressed_fund},
        },
    )
    updates = agent.process(state)
    sig = updates["signals"][0]
    assert sig.symbol == "CONFLICT"
    assert sig.action == SignalAction.HOLD
    assert "conflicting directional factors" in sig.reasoning.lower()


@pytest.mark.issue_15
def test_trading_analyst_missing_fundamentals_fallback() -> None:
    """Validate signal generation relying on technicals and sentiment when fundamentals absent."""
    loader_mock = MagicMock(spec=FundamentalDataLoader)
    loader_mock.fetch_fundamentals.return_value = None
    agent = TradingAnalystAgent(fundamental_loader=loader_mock)

    bullish_tech = TechnicalIndicatorsResult(
        symbol="NOFUND",
        close=200.0,
        sma={"sma_50": 180.0},
        ema={"ema_12": 205.0, "ema_26": 190.0},
        rsi=28.0,
        macd=MACDResult(macd_line=3.0, signal_line=1.0, histogram=2.0),
        atr=5.0,
    )
    state = create_market_state(
        artifacts=[
            ResearchArtifact(
                headline="NOFUND Sentiment",
                summary="Bullish outlook.",
                sentiment_score=0.60,
                metadata={"symbol": "NOFUND", "is_synthesis": True},
            )
        ],
        context={
            "symbol": "NOFUND",
            "indicators": {"NOFUND": bullish_tech},
            "fundamentals": {"NOFUND": None},
        },
    )
    updates = agent.process(state)
    sig = updates["signals"][0]
    assert sig.symbol == "NOFUND"
    assert sig.action == SignalAction.BUY
    assert sig.indicators.get("fundamental_score") == 0.0


@pytest.mark.issue_15
def test_trading_analyst_missing_atr_percentage_stop_loss() -> None:
    """Validate fallback to percentage-based stop loss and target price when ATR is None."""
    agent = TradingAnalystAgent()
    bullish_no_atr = TechnicalIndicatorsResult(
        symbol="NO_ATR",
        close=100.0,
        sma={"sma_50": 90.0},
        ema={"ema_12": 105.0, "ema_26": 95.0},
        rsi=25.0,
        macd=MACDResult(macd_line=2.0, signal_line=1.0, histogram=1.0),
        atr=None,
    )
    state = create_market_state(
        context={
            "symbol": "NO_ATR",
            "indicators": {"NO_ATR": bullish_no_atr},
        },
    )
    updates = agent.process(state)
    sig = updates["signals"][0]
    assert sig.symbol == "NO_ATR"
    assert sig.action == SignalAction.BUY
    # With close=100.0 and default 5% stop, 2:1 RR: stop_loss = 95.0, target_price = 110.0
    assert sig.stop_loss == 95.0
    assert sig.target_price == 110.0


@pytest.mark.issue_15
def test_trading_analyst_flat_price_series_zero_division_safety() -> None:
    """Validate numerical stability against constant flat price time series."""
    agent = TradingAnalystAgent()
    flat_bars = [
        OHLCVBar(
            timestamp=datetime.now(timezone.utc),
            open=50.0,
            high=50.0,
            low=50.0,
            close=50.0,
            volume=1000.0,
            symbol="FLAT",
        )
        for _ in range(35)
    ]
    state = create_market_state(
        context={
            "symbol": "FLAT",
            "ohlcv_bars": {"FLAT": flat_bars},
        },
    )
    # Must complete without ZeroDivisionError or uncaught exceptions
    updates = agent.process(state)
    sig = updates["signals"][0]
    assert sig.symbol == "FLAT"
    assert isinstance(sig.action, SignalAction)


@pytest.mark.issue_15
def test_trading_analyst_insufficient_bars_graceful_handling() -> None:
    """Validate graceful handling of bar series shorter than standard indicator windows."""
    agent = TradingAnalystAgent()
    short_bars = [
        OHLCVBar(
            timestamp=datetime.now(timezone.utc),
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=500.0,
            symbol="SPARSE",
        ),
        OHLCVBar(
            timestamp=datetime.now(timezone.utc),
            open=101.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=600.0,
            symbol="SPARSE",
        ),
    ]
    state = create_market_state(
        context={
            "symbol": "SPARSE",
            "ohlcv_bars": {"SPARSE": short_bars},
        },
    )
    updates = agent.process(state)
    sig = updates["signals"][0]
    assert sig.symbol == "SPARSE"
    assert isinstance(sig.action, SignalAction)
    assert 0.0 <= sig.confidence <= 1.0


@pytest.mark.issue_15
def test_trading_analyst_batch_multi_symbol_evaluation() -> None:
    """Validate batch multi-symbol evaluation with distinct risk levels and actions."""
    agent = TradingAnalystAgent()
    tech_bull = TechnicalIndicatorsResult(
        symbol="T_BULL",
        close=200.0,
        sma={"sma_50": 180.0},
        ema={"ema_12": 210.0, "ema_26": 195.0},
        rsi=25.0,
        macd=MACDResult(macd_line=3.0, signal_line=1.0, histogram=2.0),
        atr=4.0,
    )
    tech_bear = TechnicalIndicatorsResult(
        symbol="T_BEAR",
        close=50.0,
        sma={"sma_50": 60.0},
        ema={"ema_12": 48.0, "ema_26": 55.0},
        rsi=85.0,
        macd=MACDResult(macd_line=-2.0, signal_line=-1.0, histogram=-1.0),
        atr=2.0,
    )
    tech_chop = TechnicalIndicatorsResult(
        symbol="T_CHOP",
        close=100.0,
        sma={"sma_50": 100.0},
        ema={"ema_12": 100.0, "ema_26": 100.0},
        rsi=50.0,
        macd=MACDResult(macd_line=0.0, signal_line=0.0, histogram=0.0),
        atr=1.5,
    )
    state = create_market_state(
        context={
            "symbols": ["T_BULL", "T_BEAR", "T_CHOP"],
            "indicators": {
                "T_BULL": tech_bull,
                "T_BEAR": tech_bear,
                "T_CHOP": tech_chop,
            },
        },
    )
    updates = agent.process(state)
    signals = updates["signals"]
    assert len(signals) == 3
    sig_map = {s.symbol: s for s in signals}
    assert sig_map["T_BULL"].action == SignalAction.BUY
    assert sig_map["T_BEAR"].action == SignalAction.SELL
    assert sig_map["T_CHOP"].action == SignalAction.HOLD


@pytest.mark.issue_15
def test_trading_analyst_message_bus_proposal_contract() -> None:
    """Validate structured payload and correlation ID preservation on MessageBus dispatch."""
    bus = MessageBus()
    inbox: list[object] = []
    bus.subscribe("risk_manager", lambda msg: inbox.append(msg))

    agent = TradingAnalystAgent(message_bus=bus)
    state = create_market_state(
        context={
            "symbol": "BUS_TEST",
            "correlation_id": "corr-spec-uuid-777",
        }
    )
    agent.process(state)

    assert len(inbox) == 1
    msg = inbox[0]
    assert getattr(msg, "sender") == "TradingAnalyst"
    assert getattr(msg, "recipient") == "risk_manager"
    assert getattr(msg, "message_type") == MessageType.SIGNAL_PROPOSAL
    assert getattr(msg, "correlation_id") == "corr-spec-uuid-777"
    payload = getattr(msg, "payload")
    assert payload["symbol"] == "BUS_TEST"
    assert "action" in payload
    assert "confidence" in payload
    assert "signal" in payload
    assert isinstance(payload["signal"], dict)
    assert payload["signal"]["symbol"] == "BUS_TEST"


@pytest.mark.issue_15
def test_trading_analyst_orchestrator_multi_cycle_dag_execution() -> None:
    """Validate multi-cycle LangGraph DAG execution with state reducer accumulation."""
    research_handler = create_research_node_handler()
    trading_handler = create_trading_analyst_node_handler()

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=research_handler,
        trading_analyst_handler=trading_handler,
    )
    orchestrator.compile()

    # Cycle 1
    state1 = create_initial_state()
    state1["context"] = {"symbol": "AAPL", "news_limit": 1}
    result1 = orchestrator.run(state1)

    assert len(result1["artifacts"]) >= 3
    assert len(result1["signals"]) >= 1
    assert any(s.symbol == "AAPL" for s in result1["signals"])

    # Cycle 2 continuing from previous state with another symbol
    result1["context"]["symbol"] = "MSFT"
    result2 = orchestrator.run(result1)

    # State accumulation via reducers
    assert len(result2["artifacts"]) > len(result1["artifacts"])
    assert len(result2["signals"]) > len(result1["signals"])
    symbols_in_signals = {s.symbol for s in result2["signals"]}
    assert "AAPL" in symbols_in_signals
    assert "MSFT" in symbols_in_signals
    assert len(result2["records"]) >= 4


@pytest.mark.issue_15
@pytest.mark.anyio
async def test_trading_analyst_async_execution_stress() -> None:
    """Validate async lifecycle and execution under concurrent asynchronous tasks."""
    agent = TradingAnalystAgent()
    tickers = ["ASYNC_1", "ASYNC_2", "ASYNC_3", "ASYNC_4"]
    results: list[dict[str, Any]] = [{} for _ in tickers]

    async def run_agent(idx: int, sym: str) -> None:
        state = create_market_state(context={"symbol": sym})
        res = await agent.execute_async(state)
        results[idx] = res

    async with anyio.create_task_group() as tg:
        for i, sym in enumerate(tickers):
            tg.start_soon(run_agent, i, sym)

    for i, sym in enumerate(tickers):
        assert results[i]["current_step"] == "trading_analyst"
        assert len(results[i]["signals"]) == 1
        assert results[i]["signals"][0].symbol == sym
        assert results[i]["records"][0].status == "SUCCESS"
