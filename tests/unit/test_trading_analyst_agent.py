"""Unit tests for TradingAnalystAgent execution flow and orchestrator adapter."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from multi_agent_market_intelligence.agents import (
    AgentConfig,
    AgentRole,
    AgentStatus,
)
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
    create_market_state,
)
from multi_agent_market_intelligence.trading import (
    FundamentalDataLoader,
    TechnicalIndicatorsCalculator,
    TradingAnalystAgent,
    TradingSignalGenerator,
    create_trading_analyst_node_handler,
)


@pytest.mark.issue_14
def test_trading_analyst_initialization_defaults_and_custom() -> None:
    """Ensure TradingAnalystAgent initializes with defaults and respects custom config."""
    # 1. Defaults verification
    agent = TradingAnalystAgent()
    assert agent.name == "TradingAnalyst"
    assert agent.role == AgentRole.TRADING_ANALYST
    assert agent.status == AgentStatus.IDLE
    assert agent.symbols == ["AAPL"]
    assert agent.indicators_calculator is not None
    assert agent.fundamental_loader is not None
    assert agent.signal_generator is not None

    # 2. Custom configuration verification
    bus = MessageBus()
    custom_cfg = AgentConfig(
        name="custom_analyst",
        role=AgentRole.TRADING_ANALYST,
        capabilities=["custom_quant"],
    )
    custom_calc = TechnicalIndicatorsCalculator()
    custom_loader = FundamentalDataLoader()
    custom_gen = TradingSignalGenerator()

    custom_agent = TradingAnalystAgent(
        config=custom_cfg,
        message_bus=bus,
        indicators_calculator=custom_calc,
        fundamental_loader=custom_loader,
        signal_generator=custom_gen,
        symbols=["MSFT", "GOOGL"],
    )

    assert custom_agent.name == "custom_analyst"
    assert custom_agent.role == AgentRole.TRADING_ANALYST
    assert custom_agent.symbols == ["MSFT", "GOOGL"]
    assert custom_agent.indicators_calculator is custom_calc
    assert custom_agent.fundamental_loader is custom_loader
    assert custom_agent.signal_generator is custom_gen
    assert custom_agent.message_bus is bus


@pytest.mark.issue_14
def test_trading_analyst_process_single_symbol() -> None:
    """Ensure process computes indicators, loads fundamentals, and generates signal for a symbol."""
    agent = TradingAnalystAgent()
    state = create_market_state(context={"symbol": "TSLA"})

    updates = agent.process(state)

    assert updates["current_step"] == "trading_analyst"
    assert updates["context"]["target_symbols"] == ["TSLA"]
    assert updates["context"]["signals_generated_count"] == 1
    assert updates["context"]["trading_analysis_completed"] is True

    signals = updates["signals"]
    assert len(signals) == 1
    signal = signals[0]
    assert signal.symbol == "TSLA"
    assert signal.action is not None
    assert 0.0 <= signal.confidence <= 1.0
    assert signal.indicators.get("composite_score") is not None
    assert "TSLA" in updates["messages"][-1]["content"]


@pytest.mark.issue_14
def test_trading_analyst_process_multiple_symbols() -> None:
    """Ensure process correctly iterates across multiple tickers from context."""
    agent = TradingAnalystAgent()
    state = create_market_state(context={"symbols": ["AAPL", "NVDA", "AMZN"]})

    updates = agent.process(state)

    assert updates["context"]["target_symbols"] == ["AAPL", "NVDA", "AMZN"]
    signals = updates["signals"]
    assert len(signals) == 3

    symbols_in_signals = [s.symbol for s in signals]
    assert symbols_in_signals == ["AAPL", "NVDA", "AMZN"]


@pytest.mark.issue_14
def test_trading_analyst_ingests_research_sentiment_artifacts() -> None:
    """Ensure TradingAnalystAgent ingests synthesis artifacts and factors sentiment into signal."""
    agent = TradingAnalystAgent()

    # Create research artifacts including a positive synthesis artifact for NVDA
    granular_artifact = ResearchArtifact(
        headline="NVDA Reports Revenue Growth",
        summary="Strong quarterly earnings beat expectations.",
        sentiment_score=0.60,
        source="Reuters",
        timestamp=datetime.now(timezone.utc),
        metadata={"symbol": "NVDA"},
    )
    synthesis_artifact = ResearchArtifact(
        headline="Market Intelligence Synthesis for NVDA",
        summary="Consolidated intelligence: Strong bullish consensus.",
        sentiment_score=0.88,
        source="research_agent_synthesis",
        timestamp=datetime.now(timezone.utc),
        metadata={
            "symbol": "NVDA",
            "composite_score": 0.88,
            "is_synthesis": True,
        },
    )

    state = create_market_state(
        artifacts=[granular_artifact, synthesis_artifact],
        context={"symbol": "NVDA"},
    )

    updates = agent.process(state)
    signal = updates["signals"][0]

    # Verify synthesis score was ingested into the indicator payload and reasoning
    assert signal.indicators.get("sentiment_score") == 0.88
    assert "Research sentiment positive" in signal.reasoning


@pytest.mark.issue_14
def test_trading_analyst_message_bus_signal_proposal_broadcast() -> None:
    """Ensure agent publishes SIGNAL_PROPOSAL notifications with correlation ID over MessageBus."""
    bus = MessageBus()
    received_proposals: list[dict[str, object]] = []

    def subscriber(msg: object) -> None:
        received_proposals.append({"message": msg})

    bus.subscribe("risk_manager", subscriber)

    agent = TradingAnalystAgent(message_bus=bus)
    state = create_market_state(
        context={
            "symbol": "AMD",
            "correlation_id": "test-corr-456",
        }
    )

    agent.process(state)

    assert len(received_proposals) == 1
    raw_msg = received_proposals[0]["message"]
    # Verify AgentMessage fields
    assert getattr(raw_msg, "sender") == "TradingAnalyst"
    assert getattr(raw_msg, "recipient") == "risk_manager"
    assert getattr(raw_msg, "message_type") == MessageType.SIGNAL_PROPOSAL
    assert getattr(raw_msg, "correlation_id") == "test-corr-456"

    payload = getattr(raw_msg, "payload", {})
    assert payload.get("symbol") == "AMD"
    assert "signal" in payload


@pytest.mark.issue_14
def test_trading_analyst_audit_execution_record_tracking() -> None:
    """Ensure BaseAgent.execute records timing, updates status, and appends audit record."""
    agent = TradingAnalystAgent()
    state = create_market_state(context={"symbol": "MSFT"})

    assert agent.status == AgentStatus.IDLE
    result = agent.execute(state)

    assert agent.status == AgentStatus.SUCCESS
    assert "records" in result
    assert len(result["records"]) == 1

    rec = result["records"][0]
    assert rec.agent_name == "TradingAnalyst"
    assert rec.step == "trading_analyst"
    assert rec.status == "SUCCESS"
    assert rec.execution_time_ms > 0.0


@pytest.mark.issue_14
def test_trading_analyst_node_handler_adapter_execution() -> None:
    """Ensure create_trading_analyst_node_handler executes smoothly against OrchestratorState."""
    agent = TradingAnalystAgent()
    handler = create_trading_analyst_node_handler(agent)

    state = create_initial_state()
    state["context"] = {"symbol": "AAPL"}

    result = handler(state)

    assert result["current_step"] == "trading_analyst"
    assert len(result["signals"]) == 1
    assert len(result["records"]) == 1
    assert result["records"][0].status == "SUCCESS"


@pytest.mark.issue_14
def test_trading_analyst_orchestrator_multi_node_dag_pipeline() -> None:
    """Ensure Research and Trading Analyst execute sequentially in compiled Orchestrator DAG."""
    research_handler = create_research_node_handler()
    trading_handler = create_trading_analyst_node_handler()

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=research_handler,
        trading_analyst_handler=trading_handler,
    )
    orchestrator.compile()

    state = create_initial_state()
    state["context"] = {"symbol": "AAPL", "news_limit": 1}

    final_state = orchestrator.run(state)

    # 1. Traversal completed to end node (risk_manager)
    assert final_state["current_step"] == "risk_manager"

    # 2. Research artifacts created
    assert len(final_state["artifacts"]) >= 3

    # 3. Trading signals generated and appended via reducer
    assert len(final_state["signals"]) >= 1
    sig = final_state["signals"][0]
    assert sig.symbol == "AAPL"

    # 4. Audit execution records from both agents preserved
    record_agents = [r.agent_name for r in final_state["records"]]
    assert "research_agent" in record_agents
    assert "TradingAnalyst" in record_agents


@pytest.mark.issue_14
def test_trading_analyst_defensive_error_handling_empty_context() -> None:
    """Ensure agent defaults gracefully on empty context and isolates unhandled exceptions."""
    agent = TradingAnalystAgent()

    # Empty context: should fall back to default agent.symbols
    empty_state = create_market_state(context={})
    updates = agent.process(empty_state)
    assert updates["context"]["target_symbols"] == ["AAPL"]
    assert len(updates["signals"]) == 1

    # Exception isolation in BaseAgent.execute
    agent.process = MagicMock(side_effect=RuntimeError("Indicator calculation timeout"))  # type: ignore[method-assign]
    error_result = agent.execute(empty_state)

    assert agent.status == AgentStatus.ERROR
    assert len(error_result["records"]) == 1
    assert error_result["records"][0].status == "ERROR"
    assert "errors" in error_result
    assert any("Indicator calculation timeout" in e for e in error_result["errors"])


@pytest.mark.issue_14
@pytest.mark.anyio
async def test_trading_analyst_async_execution() -> None:
    """Ensure process_async and execute_async function correctly in async runtime."""
    agent = TradingAnalystAgent()
    state = create_market_state(context={"symbol": "GOOGL"})

    # Async process
    async_updates = await agent.process_async(state)
    assert async_updates["current_step"] == "trading_analyst"
    assert len(async_updates["signals"]) == 1
    assert async_updates["signals"][0].symbol == "GOOGL"

    # Async execute template
    async_result = await agent.execute_async(state)
    assert agent.status == AgentStatus.SUCCESS
    assert len(async_result["records"]) == 1
    assert async_result["records"][0].status == "SUCCESS"
