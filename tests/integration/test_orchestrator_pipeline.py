"""End-to-end integration tests for the multi-agent market intelligence pipeline."""

import pytest

from multi_agent_market_intelligence import (
    DecisionStatus,
    MarketIntelligenceOrchestrator,
    MessageBus,
    NodeNames,
    PortfolioSnapshot,
    SignalAction,
)
from multi_agent_market_intelligence.state.schema import create_market_state


@pytest.mark.issue_5
def test_e2e_market_intelligence_pipeline_success(
    configured_orchestrator: MarketIntelligenceOrchestrator,
    shared_bus: MessageBus,
) -> None:
    """Verify complete end-to-end traversal from research to portfolio decision."""
    initial_state = create_market_state(
        context={
            "symbol": "NVDA",
            "sentiment_score": 0.85,
            "correlation_id": "test-corr-nvda-1",
        },
        portfolio=PortfolioSnapshot(cash=50000.0, total_equity=50000.0),
    )

    final_state = configured_orchestrator.run(initial_state)

    # Invariant 1: Step completion
    assert final_state["current_step"] == NodeNames.RISK_MANAGER

    # Invariant 2: Research artifact generation
    assert len(final_state["artifacts"]) == 1
    artifact = final_state["artifacts"][0]
    assert "NVDA" in artifact.headline
    assert artifact.sentiment_score == 0.85

    # Invariant 3: Trading analyst signal generation
    assert len(final_state["signals"]) == 1
    signal = final_state["signals"][0]
    assert signal.symbol == "NVDA"
    assert signal.action == SignalAction.BUY
    assert signal.confidence == 0.85

    # Invariant 4: Risk manager decision and portfolio update
    assert len(final_state["decisions"]) == 1
    decision = final_state["decisions"][0]
    assert decision.status == DecisionStatus.APPROVED
    assert decision.approved_size == 50.0

    portfolio = final_state["portfolio"]
    assert isinstance(portfolio, PortfolioSnapshot)
    assert portfolio.cash == 45000.0  # 50,000 - (50 * 100)
    assert "NVDA" in portfolio.positions
    assert portfolio.positions["NVDA"].quantity == 50.0

    # Invariant 5: Audit execution records
    assert len(final_state["records"]) == 3
    agent_names = [r.agent_name for r in final_state["records"]]
    assert agent_names == [
        NodeNames.RESEARCH,
        NodeNames.TRADING_ANALYST,
        NodeNames.RISK_MANAGER,
    ]
    assert all(r.status == "SUCCESS" for r in final_state["records"])
    assert all(r.execution_time_ms >= 0.0 for r in final_state["records"])


@pytest.mark.issue_5
def test_e2e_message_bus_correlation_tracking(
    configured_orchestrator: MarketIntelligenceOrchestrator,
    shared_bus: MessageBus,
) -> None:
    """Verify that messages dispatched across agents preserve correlation_id."""
    correlation_id = "corr-lifecycle-tracking-42"
    initial_state = create_market_state(
        context={
            "symbol": "AAPL",
            "sentiment_score": 0.70,
            "correlation_id": correlation_id,
        }
    )

    configured_orchestrator.run(initial_state)

    conversation = shared_bus.get_conversation(correlation_id)
    assert len(conversation) == 3

    # Verify message sequence and correlation chain
    assert conversation[0].sender == NodeNames.RESEARCH
    assert conversation[0].recipient == NodeNames.TRADING_ANALYST
    assert conversation[0].correlation_id == correlation_id

    assert conversation[1].sender == NodeNames.TRADING_ANALYST
    assert conversation[1].recipient == NodeNames.RISK_MANAGER
    assert conversation[1].correlation_id == correlation_id

    assert conversation[2].sender == NodeNames.RISK_MANAGER
    assert conversation[2].recipient == "orchestrator"
    assert conversation[2].correlation_id == correlation_id


@pytest.mark.issue_5
def test_e2e_portfolio_state_multi_cycle_evolution(
    configured_orchestrator: MarketIntelligenceOrchestrator,
) -> None:
    """Verify portfolio state compounds sequentially over multiple operational cycles."""
    # Cycle 1: Buy AAPL
    state1 = create_market_state(
        context={"symbol": "AAPL", "sentiment_score": 0.8},
        portfolio=PortfolioSnapshot(cash=50000.0, total_equity=50000.0),
    )
    result1 = configured_orchestrator.run(state1)
    port1 = result1["portfolio"]
    assert isinstance(port1, PortfolioSnapshot)
    assert port1.cash == 45000.0
    assert port1.positions["AAPL"].quantity == 50.0

    # Cycle 2: Buy MSFT (carrying over portfolio)
    state2 = create_market_state(
        context={"symbol": "MSFT", "sentiment_score": 0.9},
        portfolio=port1,
    )
    result2 = configured_orchestrator.run(state2)
    port2 = result2["portfolio"]
    assert isinstance(port2, PortfolioSnapshot)
    assert port2.cash == 40000.0
    assert port2.positions["AAPL"].quantity == 50.0
    assert port2.positions["MSFT"].quantity == 50.0

    # Cycle 3: Sell AAPL (carrying over portfolio)
    state3 = create_market_state(
        context={"symbol": "AAPL", "sentiment_score": -0.8},
        portfolio=port2,
    )
    result3 = configured_orchestrator.run(state3)
    port3 = result3["portfolio"]
    assert isinstance(port3, PortfolioSnapshot)
    assert port3.cash == 45000.0  # 40000 + (50 * 100)
    assert "AAPL" not in port3.positions
    assert port3.positions["MSFT"].quantity == 50.0
