"""End-to-end integration tests for the Risk & Portfolio Manager and multi-agent pipeline."""

import pytest

from multi_agent_market_intelligence import (
    DecisionStatus,
    MarketIntelligenceOrchestrator,
    MessageBus,
    MessageType,
    NodeNames,
    PortfolioSnapshot,
    PortfolioTracker,
    Position,
    ResearchAgent,
    RiskDecision,
    RiskLimitsConfig,
    RiskPortfolioManagerAgent,
    RiskViolationType,
    SignalAction,
    SignalRiskValidator,
    TradingAnalystAgent,
    TradingSignal,
    create_market_state,
    create_research_node_handler,
    create_risk_manager_node_handler,
    create_trading_analyst_node_handler,
)


@pytest.mark.issue_20
def test_risk_manager_e2e_three_agent_pipeline_success() -> None:
    """Verify complete 3-agent DAG traversal: research -> trading_analyst -> risk_manager."""
    research_handler = create_research_node_handler()
    trading_handler = create_trading_analyst_node_handler()
    risk_handler = create_risk_manager_node_handler()

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=research_handler,
        trading_analyst_handler=trading_handler,
        risk_manager_handler=risk_handler,
    )

    initial_state = create_market_state(
        context={
            "target_symbols": ["AAPL"],
            "correlation_id": "e2e-risk-int-001",
        },
        portfolio=PortfolioSnapshot(cash=100_000.0, total_equity=100_000.0),
    )

    final_state = orchestrator.run(initial_state)

    # 1. Pipeline step completed
    assert final_state["current_step"] == NodeNames.RISK_MANAGER

    # 2. Research artifacts generated
    assert len(final_state["artifacts"]) > 0

    # 3. Trading signals generated
    assert len(final_state["signals"]) > 0
    signal = final_state["signals"][0]
    assert signal.symbol == "AAPL"

    # 4. Risk decisions evaluated
    assert len(final_state["decisions"]) > 0
    decision = final_state["decisions"][0]
    assert isinstance(decision, RiskDecision)
    assert decision.status in (DecisionStatus.APPROVED, DecisionStatus.MODIFIED)

    # 5. Portfolio snapshot updated
    portfolio = final_state["portfolio"]
    assert isinstance(portfolio, PortfolioSnapshot)
    assert portfolio.total_equity > 0.0

    # 6. Audit records logged for all 3 agents
    agent_names = {r.agent_name.lower() for r in final_state["records"]}
    assert any("research" in n for n in agent_names)
    assert any("trading" in n for n in agent_names)
    assert any("risk" in n for n in agent_names)


@pytest.mark.issue_20
def test_risk_manager_multi_cycle_trading_portfolio_evolution() -> None:
    """Verify portfolio balance sheet evolution across sequential multi-cycle sessions."""
    limits = RiskLimitsConfig(max_position_size_pct=0.30)
    agent = RiskPortfolioManagerAgent(
        validator=SignalRiskValidator(limits=limits),
        tracker=PortfolioTracker(initial_cash=100_000.0),
        auto_execute_trades=True,
    )

    # Cycle 1: BUY 100 AAPL @ $100 ($10,000 value)
    sig1 = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state1 = create_market_state(
        signals=[sig1],
        context={"prices": {"AAPL": 100.0}, "proposed_sizes": {"AAPL": 100.0}},
    )
    res1 = agent.process(state1)

    assert res1["decisions"][0].status == DecisionStatus.APPROVED
    snap1 = res1["portfolio"]
    assert snap1.cash == 90_000.0
    assert snap1.positions["AAPL"].quantity == 100.0
    assert snap1.positions["AAPL"].entry_price == 100.0

    # Cycle 2: Scale BUY 100 AAPL @ $120 ($12,000 value) -> Average cost basis = $110.0
    sig2 = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=170.0,
        stop_loss=90.0,
        indicators={"close": 120.0},
    )
    state2 = create_market_state(
        signals=[sig2],
        portfolio=snap1,
        context={"prices": {"AAPL": 120.0}, "proposed_sizes": {"AAPL": 100.0}},
    )
    res2 = agent.process(state2)

    assert res2["decisions"][0].status == DecisionStatus.APPROVED
    snap2 = res2["portfolio"]
    assert snap2.cash == 78_000.0
    assert snap2.positions["AAPL"].quantity == 200.0
    assert snap2.positions["AAPL"].entry_price == pytest.approx(110.0)

    # Cycle 3: Take-profit SELL 100 AAPL @ $140
    # Realized PnL = (140 - 110) * 100 = $3,000. Proceeds = $14,000. New cash = $92,000.
    sig3 = TradingSignal(
        symbol="AAPL",
        action=SignalAction.SELL,
        indicators={"close": 140.0},
    )
    state3 = create_market_state(
        signals=[sig3],
        portfolio=snap2,
        context={"prices": {"AAPL": 140.0}, "proposed_sizes": {"AAPL": 100.0}},
    )
    res3 = agent.process(state3)

    assert res3["decisions"][0].status == DecisionStatus.APPROVED
    snap3 = res3["portfolio"]
    assert snap3.cash == 92_000.0
    assert snap3.positions["AAPL"].quantity == 100.0
    assert agent.tracker.realized_pnl == pytest.approx(3_000.0)


@pytest.mark.issue_20
def test_risk_manager_circuit_breaker_pipeline_rejection() -> None:
    """Verify active circuit breaker immediately halts orders and rejects signals."""
    limits = RiskLimitsConfig(circuit_breaker_active=True)
    validator = SignalRiskValidator(limits=limits)
    agent = RiskPortfolioManagerAgent(validator=validator)

    handler = create_risk_manager_node_handler(agent)
    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=150.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    state = create_market_state(signals=[sig])

    result = handler(state)

    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]
    assert decision.status == DecisionStatus.REJECTED
    assert decision.approved_size == 0.0
    assert RiskViolationType.CIRCUIT_BREAKER_ACTIVE.value in decision.metrics["violations"]


@pytest.mark.issue_20
def test_risk_manager_drawdown_limit_pipeline_veto() -> None:
    """Verify drawdown breach restricts BUY orders but permits liquidation SELL orders."""
    limits = RiskLimitsConfig(max_portfolio_drawdown_pct=0.15)
    validator = SignalRiskValidator(limits=limits)
    agent = RiskPortfolioManagerAgent(validator=validator)

    # State with 25% drawdown (> 15% limit) holding 100 AAPL
    pos = Position(symbol="AAPL", quantity=100.0, entry_price=100.0, current_price=75.0)
    distressed_portfolio = {
        "cash": 50_000.0,
        "total_equity": 57_500.0,
        "current_drawdown_pct": 0.25,
        "positions": {"AAPL": pos},
    }

    # 1. BUY signal is vetoed
    buy_sig = TradingSignal(
        symbol="MSFT",
        action=SignalAction.BUY,
        target_price=260.0,
        stop_loss=170.0,
        indicators={"close": 200.0},
    )
    state_buy = create_market_state(signals=[buy_sig], portfolio=distressed_portfolio)
    res_buy = agent.process(state_buy)
    assert res_buy["decisions"][0].status == DecisionStatus.REJECTED
    assert (
        RiskViolationType.MAX_PORTFOLIO_DRAWDOWN_EXCEEDED.value
        in res_buy["decisions"][0].metrics["violations"]
    )

    # 2. SELL liquidation signal is approved
    sell_sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.SELL,
        indicators={"close": 75.0},
    )
    state_sell = create_market_state(signals=[sell_sig], portfolio=distressed_portfolio)
    res_sell = agent.process(state_sell)
    assert res_sell["decisions"][0].status == DecisionStatus.APPROVED
    assert res_sell["decisions"][0].approved_size == 100.0


@pytest.mark.issue_20
def test_risk_manager_daily_loss_limit_pipeline_veto() -> None:
    """Verify session daily loss breach halts BUY orders."""
    limits = RiskLimitsConfig(max_daily_loss_pct=0.05)
    validator = SignalRiskValidator(limits=limits)
    agent = RiskPortfolioManagerAgent(validator=validator)

    # State down 8% on the session
    loss_portfolio = {
        "cash": 92_000.0,
        "total_equity": 92_000.0,
        "daily_pnl_pct": -0.08,
        "positions": {},
    }

    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    state = create_market_state(signals=[sig], portfolio=loss_portfolio)
    res = agent.process(state)

    assert res["decisions"][0].status == DecisionStatus.REJECTED
    assert (
        RiskViolationType.MAX_DAILY_LOSS_EXCEEDED.value in res["decisions"][0].metrics["violations"]
    )


@pytest.mark.issue_20
def test_risk_manager_sector_concentration_limit_scaling() -> None:
    """Verify aggregate sector exposure caps scale down incoming trades."""
    limits = RiskLimitsConfig(max_sector_exposure_pct=0.30)  # Max $30,000 in Tech
    validator = SignalRiskValidator(limits=limits)
    agent = RiskPortfolioManagerAgent(
        validator=validator,
        sector_mappings={"AAPL": "Technology", "MSFT": "Technology"},
    )

    # Holds $20,000 in AAPL (Technology)
    pos_aapl = Position(symbol="AAPL", quantity=200.0, entry_price=100.0, current_price=100.0)
    portfolio = {
        "cash": 80_000.0,
        "total_equity": 100_000.0,
        "positions": {"AAPL": pos_aapl},
        "sector_mappings": {"AAPL": "Technology", "MSFT": "Technology"},
    }

    # BUY MSFT @ $200, requesting 100 units ($20,000). Remaining Tech room = $10,000 (50 units).
    sig_msft = TradingSignal(
        symbol="MSFT",
        action=SignalAction.BUY,
        target_price=260.0,
        stop_loss=170.0,
        indicators={"close": 200.0},
    )
    state = create_market_state(
        signals=[sig_msft],
        portfolio=portfolio,
        context={"prices": {"MSFT": 200.0}, "proposed_sizes": {"MSFT": 100.0}},
    )

    res = agent.process(state)

    decision = res["decisions"][0]
    assert decision.status == DecisionStatus.MODIFIED
    assert decision.approved_size == 50.0
    assert RiskViolationType.MAX_SECTOR_EXPOSURE_EXCEEDED.value in decision.metrics["violations"]


@pytest.mark.issue_20
def test_risk_manager_cash_buffer_reserve_protection() -> None:
    """Verify trade scaling preserves minimum cash buffer requirement."""
    # Equity $100,000, must keep 10% ($10,000) cash
    limits = RiskLimitsConfig(min_cash_buffer_pct=0.10, max_position_size_pct=0.50)
    validator = SignalRiskValidator(limits=limits)
    agent = RiskPortfolioManagerAgent(validator=validator)

    # Cash = $25,000. Free cash for trades = $15,000.
    portfolio = {
        "cash": 25_000.0,
        "total_equity": 100_000.0,
        "positions": {
            "SPY": Position(symbol="SPY", quantity=750.0, entry_price=100.0, current_price=100.0)
        },
    }

    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    # Requested 200 units ($20,000). Free cash allows max 150 units ($15,000).
    state = create_market_state(
        signals=[sig],
        portfolio=portfolio,
        context={"prices": {"AAPL": 100.0}, "proposed_sizes": {"AAPL": 200.0}},
    )

    res = agent.process(state)

    decision = res["decisions"][0]
    assert decision.status == DecisionStatus.MODIFIED
    assert decision.approved_size == 150.0
    assert RiskViolationType.INSUFFICIENT_CASH_BUFFER.value in decision.metrics["violations"]
    # Post-trade cash is exactly $10,000
    assert res["portfolio"].cash == 10_000.0


@pytest.mark.issue_20
def test_risk_manager_gross_leverage_cap_protection() -> None:
    """Verify trade scaling respects gross leverage ceiling."""
    # Equity $100,000, max leverage = 1.2x (Max gross exposure = $120,000)
    limits = RiskLimitsConfig(max_leverage=1.2, max_position_size_pct=0.50)
    validator = SignalRiskValidator(limits=limits)
    agent = RiskPortfolioManagerAgent(validator=validator)

    # Gross exposure = $110,000. Remaining leverage capacity = $10,000.
    portfolio = {
        "cash": 50_000.0,
        "total_equity": 100_000.0,
        "positions": {
            "SPY": Position(symbol="SPY", quantity=1100.0, entry_price=100.0, current_price=100.0)
        },
    }

    sig = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=70.0,
        stop_loss=40.0,
        indicators={"close": 50.0},
    )
    # Requested 300 units @ $50 = $15,000. Cap allows max 200 units ($10,000).
    state = create_market_state(
        signals=[sig],
        portfolio=portfolio,
        context={"prices": {"AAPL": 50.0}, "proposed_sizes": {"AAPL": 300.0}},
    )

    res = agent.process(state)

    decision = res["decisions"][0]
    assert decision.status == DecisionStatus.MODIFIED
    assert decision.approved_size == 200.0
    assert RiskViolationType.EXCESSIVE_LEVERAGE.value in decision.metrics["violations"]


@pytest.mark.issue_20
def test_risk_manager_concurrent_positions_cap_rejection() -> None:
    """Verify max open positions limit rejects new symbols while permitting existing ones."""
    limits = RiskLimitsConfig(max_open_positions=2)
    validator = SignalRiskValidator(limits=limits)
    agent = RiskPortfolioManagerAgent(validator=validator)

    # Holds 2 positions (AAPL and MSFT)
    portfolio = {
        "cash": 70_000.0,
        "total_equity": 100_000.0,
        "positions": {
            "AAPL": Position(symbol="AAPL", quantity=100.0, entry_price=100.0, current_price=100.0),
            "MSFT": Position(symbol="MSFT", quantity=100.0, entry_price=200.0, current_price=200.0),
        },
    }

    # 1. 3rd symbol GOOGL is rejected
    sig_googl = TradingSignal(
        symbol="GOOGL",
        action=SignalAction.BUY,
        target_price=150.0,
        stop_loss=90.0,
        indicators={"close": 100.0},
    )
    res_googl = agent.process(create_market_state(signals=[sig_googl], portfolio=portfolio))
    assert res_googl["decisions"][0].status == DecisionStatus.REJECTED
    assert (
        RiskViolationType.MAX_CONCURRENT_POSITIONS_EXCEEDED.value
        in res_googl["decisions"][0].metrics["violations"]
    )

    # 2. Existing symbol AAPL is permitted to scale
    sig_aapl = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=80.0,
        indicators={"close": 100.0},
    )
    res_aapl = agent.process(
        create_market_state(
            signals=[sig_aapl],
            portfolio=portfolio,
            context={"proposed_sizes": {"AAPL": 20.0}},
        )
    )
    assert res_aapl["decisions"][0].status in (
        DecisionStatus.APPROVED,
        DecisionStatus.MODIFIED,
    )


@pytest.mark.issue_20
def test_risk_manager_message_bus_inter_agent_event_flow() -> None:
    """Verify inter-agent event communication and correlation ID flow over MessageBus."""
    bus = MessageBus()
    received_evals = []

    bus.subscribe("orchestrator", lambda msg: received_evals.append(msg))

    research_agent = ResearchAgent(message_bus=bus)
    trading_agent = TradingAnalystAgent(message_bus=bus)
    risk_agent = RiskPortfolioManagerAgent(message_bus=bus)

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=create_research_node_handler(research_agent),
        trading_analyst_handler=create_trading_analyst_node_handler(trading_agent),
        risk_manager_handler=create_risk_manager_node_handler(risk_agent),
    )

    corr_id = "test-event-bus-flow-101"
    initial_state = create_market_state(
        context={"target_symbols": ["AAPL"], "correlation_id": corr_id}
    )

    orchestrator.run(initial_state)

    # Assert Risk Manager broadcasted RISK_EVALUATION
    assert len(received_evals) >= 1
    eval_msg = received_evals[-1]
    assert eval_msg.message_type == MessageType.RISK_EVALUATION
    assert eval_msg.correlation_id == corr_id
    assert eval_msg.payload["decisions_count"] >= 1


@pytest.mark.issue_20
def test_risk_manager_corrupted_signal_resilience() -> None:
    """Verify pipeline gracefully handles corrupted signal geometry without crashing."""
    agent = RiskPortfolioManagerAgent()

    # Corrupted signal: stop loss is higher than entry price for a BUY
    corrupted_signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        target_price=140.0,
        stop_loss=120.0,  # Inverted! Entry price is 100
        indicators={"close": 100.0},
    )

    state = create_market_state(signals=[corrupted_signal])
    result = agent.process(state)

    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]
    assert decision.status == DecisionStatus.REJECTED
    assert RiskViolationType.MISSING_STOP_LOSS.value in decision.metrics["violations"]


@pytest.mark.issue_20
@pytest.mark.anyio
async def test_risk_manager_pipeline_async_execution() -> None:
    """Verify asynchronous pipeline execution parity."""
    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=create_research_node_handler(),
        trading_analyst_handler=create_trading_analyst_node_handler(),
        risk_manager_handler=create_risk_manager_node_handler(),
    )

    state = create_market_state(
        context={"target_symbols": ["AAPL"], "correlation_id": "async-e2e-002"}
    )

    final_state = await orchestrator.arun(state)

    assert final_state["current_step"] == NodeNames.RISK_MANAGER
    assert len(final_state["decisions"]) > 0
    assert isinstance(final_state["portfolio"], PortfolioSnapshot)
