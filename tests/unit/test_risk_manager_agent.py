"""Unit tests for RiskPortfolioManagerAgent execution flow, adapter, and DAG integration."""

import pytest

from multi_agent_market_intelligence.agents import AgentRole
from multi_agent_market_intelligence.messaging import MessageBus, MessageType
from multi_agent_market_intelligence.orchestrator import (
    MarketIntelligenceOrchestrator,
    NodeNames,
)
from multi_agent_market_intelligence.research import create_research_node_handler
from multi_agent_market_intelligence.risk import (
    PortfolioTracker,
    RiskLimitsConfig,
    RiskManagerAgent,
    RiskPortfolioManagerAgent,
    SignalRiskValidator,
    create_risk_manager_node_handler,
)
from multi_agent_market_intelligence.state import (
    AgentExecutionRecord,
    DecisionStatus,
    PortfolioSnapshot,
    Position,
    SignalAction,
    TradingSignal,
    create_market_state,
)
from multi_agent_market_intelligence.trading import create_trading_analyst_node_handler


@pytest.mark.issue_19
def test_risk_manager_agent_initialization_defaults_and_custom() -> None:
    """Verify default and customized initialization of RiskPortfolioManagerAgent."""
    agent = RiskPortfolioManagerAgent()

    assert agent.name == "RiskPortfolioManager"
    assert agent.role == AgentRole.RISK_MANAGER
    assert "risk_limits_validation" in agent.config.capabilities
    assert agent.auto_execute_trades is True
    assert isinstance(agent.validator, SignalRiskValidator)
    assert isinstance(agent.tracker, PortfolioTracker)

    # Alias check
    alias_agent = RiskManagerAgent()
    assert isinstance(alias_agent, RiskPortfolioManagerAgent)

    # Custom components
    bus = MessageBus()
    custom_limits = RiskLimitsConfig(max_position_size_pct=0.10)
    custom_val = SignalRiskValidator(limits=custom_limits)
    custom_tracker = PortfolioTracker(initial_cash=50_000.0)
    custom_agent = RiskPortfolioManagerAgent(
        message_bus=bus,
        validator=custom_val,
        tracker=custom_tracker,
        auto_execute_trades=False,
        sector_mappings={"AAPL": "Technology"},
    )
    assert custom_agent.message_bus is bus
    assert custom_agent.validator is custom_val
    assert custom_agent.tracker.cash == 50_000.0
    assert custom_agent.auto_execute_trades is False


@pytest.mark.issue_19
def test_risk_manager_agent_process_single_signal() -> None:
    """Verify processing single BUY signal produces RiskDecision and updates portfolio."""
    agent = RiskPortfolioManagerAgent()

    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state = create_market_state(signals=[signal])

    result = agent.process(state)

    assert result["current_step"] == NodeNames.RISK_MANAGER
    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]
    assert decision.status in (DecisionStatus.APPROVED, DecisionStatus.MODIFIED)
    assert decision.approved_size > 0.0

    # Auto-execution updated portfolio
    snapshot = result["portfolio"]
    assert isinstance(snapshot, PortfolioSnapshot)
    assert snapshot.cash < 100_000.0
    assert "AAPL" in snapshot.positions
    assert result["context"]["decisions_count"] == 1


@pytest.mark.issue_19
def test_risk_manager_agent_process_batch_signals() -> None:
    """Verify batch signal evaluation respects cumulative capacity across sequential orders."""
    agent = RiskPortfolioManagerAgent(
        tracker=PortfolioTracker(initial_cash=50_000.0),
        sector_mappings={"AAPL": "Tech", "MSFT": "Tech"},
    )

    sig1 = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    sig2 = TradingSignal(
        symbol="MSFT",
        action=SignalAction.BUY,
        target_price=260.0,
        stop_loss=170.0,
        indicators={"close": 200.0},
    )

    state = create_market_state(
        signals=[sig1, sig2],
        context={
            "prices": {"AAPL": 100.0, "MSFT": 200.0},
            "proposed_sizes": {"AAPL": 100.0, "MSFT": 50.0},
        },
    )

    result = agent.process(state)

    assert len(result["decisions"]) == 2
    assert result["context"]["decisions_count"] == 2
    assert (result["context"]["approved_count"] + result["context"]["modified_count"]) == 2


@pytest.mark.issue_19
def test_risk_manager_agent_portfolio_hydration_from_state() -> None:
    """Verify agent dynamically hydrates balance sheet from incoming state snapshot."""
    agent = RiskPortfolioManagerAgent()

    # Pre-existing state holding 100 shares of AAPL
    initial_pos = Position(symbol="AAPL", quantity=100.0, entry_price=100.0, current_price=100.0)
    snapshot = PortfolioSnapshot(
        cash=50_000.0,
        positions={"AAPL": initial_pos},
        total_equity=60_000.0,
    )

    # SELL signal for held AAPL
    sell_sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.SELL,
        indicators={"close": 120.0},
    )

    state = create_market_state(
        signals=[sell_sig],
        portfolio=snapshot,
        context={"prices": {"AAPL": 120.0}, "proposed_sizes": {"AAPL": 50.0}},
    )

    result = agent.process(state)

    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]
    assert decision.status == DecisionStatus.APPROVED
    assert decision.approved_size == 50.0

    # Auto-execution credited proceeds to cash and reduced held shares
    updated_snap = result["portfolio"]
    assert updated_snap.cash == 50_000.0 + (50.0 * 120.0)
    assert updated_snap.positions["AAPL"].quantity == 50.0


@pytest.mark.issue_19
def test_risk_manager_agent_auto_execute_trades_updates_tracker() -> None:
    """Verify auto_execute_trades toggle controls mutation of PortfolioTracker balance sheet."""
    # 1. auto_execute_trades = True
    active_agent = RiskPortfolioManagerAgent(auto_execute_trades=True)
    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state1 = create_market_state(signals=[sig], context={"proposed_sizes": {"AAPL": 100.0}})
    res1 = active_agent.process(state1)
    assert res1["portfolio"].cash == 90_000.0
    assert active_agent.tracker.cash == 90_000.0
    assert "AAPL" in active_agent.tracker.positions

    # 2. auto_execute_trades = False
    passive_agent = RiskPortfolioManagerAgent(auto_execute_trades=False)
    state2 = create_market_state(signals=[sig], context={"proposed_sizes": {"AAPL": 100.0}})
    res2 = passive_agent.process(state2)
    assert res2["decisions"][0].status in (
        DecisionStatus.APPROVED,
        DecisionStatus.MODIFIED,
    )
    # Cash remains untouched at $100,000
    assert res2["portfolio"].cash == 100_000.0
    assert passive_agent.tracker.cash == 100_000.0
    assert "AAPL" not in passive_agent.tracker.positions


@pytest.mark.issue_19
def test_risk_manager_agent_message_bus_evaluation_broadcast() -> None:
    """Verify RISK_EVALUATION notification broadcast over MessageBus with correlation ID."""
    bus = MessageBus()
    received_messages = []

    def handle_eval(msg):
        received_messages.append(msg)

    bus.subscribe("orchestrator", handle_eval)

    agent = RiskPortfolioManagerAgent(message_bus=bus)
    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state = create_market_state(
        signals=[sig],
        context={"correlation_id": "corr-risk-test-999"},
    )

    agent.process(state)

    assert len(received_messages) == 1
    eval_msg = received_messages[0]
    assert eval_msg.message_type == MessageType.RISK_EVALUATION
    assert eval_msg.sender == "RiskPortfolioManager"
    assert eval_msg.recipient == "orchestrator"
    assert eval_msg.correlation_id == "corr-risk-test-999"
    assert eval_msg.payload["decisions_count"] == 1


@pytest.mark.issue_19
def test_risk_manager_agent_audit_execution_record_tracking() -> None:
    """Verify execute template records execution duration and AgentExecutionRecord."""
    agent = RiskPortfolioManagerAgent()
    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state = create_market_state(signals=[sig])

    result = agent.execute(state)

    assert "records" in result
    records = result["records"]
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, AgentExecutionRecord)
    assert record.agent_name == "RiskPortfolioManager"
    assert record.status == "SUCCESS"
    assert record.execution_time_ms >= 0.0


@pytest.mark.issue_19
def test_risk_manager_agent_node_handler_adapter_execution() -> None:
    """Verify node handler adapter executes as callable taking and returning OrchestratorState."""
    agent = RiskPortfolioManagerAgent()
    handler = create_risk_manager_node_handler(agent)

    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state = create_market_state(signals=[sig])

    result = handler(state)

    assert "decisions" in result
    assert "portfolio" in result
    assert "records" in result
    assert result["current_step"] == NodeNames.RISK_MANAGER


@pytest.mark.issue_19
def test_risk_manager_agent_full_three_node_dag_pipeline() -> None:
    """Verify complete 3-agent DAG execution: research -> trading_analyst -> risk_manager."""
    research_handler = create_research_node_handler()
    trading_handler = create_trading_analyst_node_handler()
    risk_handler = create_risk_manager_node_handler()

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=research_handler,
        trading_analyst_handler=trading_handler,
        risk_manager_handler=risk_handler,
    )

    initial_state = create_market_state(
        context={"target_symbols": ["AAPL"], "correlation_id": "dag-run-001"}
    )

    final_state = orchestrator.run(initial_state)

    # 1. Research Agent produced artifacts
    assert len(final_state["artifacts"]) > 0

    # 2. Trading Analyst produced signals
    assert len(final_state["signals"]) > 0

    # 3. Risk & Portfolio Manager produced decisions
    assert len(final_state["decisions"]) > 0
    assert final_state["current_step"] == NodeNames.RISK_MANAGER

    # 4. Records logged for all 3 agents
    agent_names_lower = {r.agent_name.lower() for r in final_state["records"]}
    assert any("research" in n for n in agent_names_lower)
    assert any("trading" in n for n in agent_names_lower)
    assert any("risk" in n for n in agent_names_lower)


@pytest.mark.issue_19
def test_risk_manager_agent_defensive_handling_empty_signals() -> None:
    """Verify agent handles empty signals without errors and returns valid empty decisions."""
    agent = RiskPortfolioManagerAgent()
    empty_state = create_market_state(signals=[])

    result = agent.process(empty_state)

    assert result["decisions"] == []
    assert result["context"]["decisions_count"] == 0
    assert result["current_step"] == NodeNames.RISK_MANAGER
    assert isinstance(result["portfolio"], PortfolioSnapshot)


@pytest.mark.issue_19
@pytest.mark.anyio
async def test_risk_manager_agent_async_execution() -> None:
    """Verify process_async parity for asynchronous workflows."""
    agent = RiskPortfolioManagerAgent()
    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state = create_market_state(signals=[sig])

    result = await agent.process_async(state)

    assert len(result["decisions"]) == 1
    assert result["current_step"] == NodeNames.RISK_MANAGER
    assert isinstance(result["portfolio"], PortfolioSnapshot)
