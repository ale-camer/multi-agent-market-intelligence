"""Integration tests verifying resilience, fault recovery, and concurrency in the pipeline."""

import asyncio
from typing import Any

import pytest

from multi_agent_market_intelligence import (
    BaseAgent,
    DecisionStatus,
    MarketIntelligenceOrchestrator,
    MarketIntelligenceState,
    NodeNames,
    PortfolioSnapshot,
    SignalAction,
)
from multi_agent_market_intelligence.state.schema import create_market_state


class FailingResearchAgent(BaseAgent):
    """Simulates a network or data-source outage in the Research agent."""

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        raise ConnectionError("Upstream financial wire API unavailable")


@pytest.mark.issue_5
def test_pipeline_recovers_from_research_failure(
    simulated_analyst_agent: BaseAgent,
    simulated_risk_agent: BaseAgent,
) -> None:
    """Verify downstream agents handle upstream failure gracefully without graph crash."""
    failing_research = FailingResearchAgent()

    orchestrator = MarketIntelligenceOrchestrator()
    orchestrator.register_handler(NodeNames.RESEARCH, failing_research.as_node_handler())
    orchestrator.register_handler(
        NodeNames.TRADING_ANALYST, simulated_analyst_agent.as_node_handler()
    )
    orchestrator.register_handler(NodeNames.RISK_MANAGER, simulated_risk_agent.as_node_handler())

    initial_state = create_market_state(context={"symbol": "AAPL"})
    final_state = orchestrator.run(initial_state)

    # Graph must complete through risk manager
    assert final_state["current_step"] == NodeNames.RISK_MANAGER

    # Research failed and logged error
    assert any("Upstream financial wire API unavailable" in err for err in final_state["errors"])
    assert final_state["records"][0].status == "ERROR"

    # Analyst defaulted to HOLD due to lack of intelligence
    assert len(final_state["signals"]) == 1
    assert final_state["signals"][0].action == SignalAction.HOLD

    # Risk manager safely rejected HOLD
    assert len(final_state["decisions"]) == 1
    assert final_state["decisions"][0].status == DecisionStatus.REJECTED


@pytest.mark.issue_5
@pytest.mark.anyio
async def test_concurrent_orchestrator_runs(
    simulated_research_agent: BaseAgent,
    simulated_analyst_agent: BaseAgent,
    simulated_risk_agent: BaseAgent,
) -> None:
    """Verify multiple concurrent pipeline runs maintain isolated state without cross-talk."""
    orchestrator = MarketIntelligenceOrchestrator()
    orchestrator.register_handler(NodeNames.RESEARCH, simulated_research_agent.as_node_handler())
    orchestrator.register_handler(
        NodeNames.TRADING_ANALYST, simulated_analyst_agent.as_node_handler()
    )
    orchestrator.register_handler(NodeNames.RISK_MANAGER, simulated_risk_agent.as_node_handler())

    symbols = ["AAPL", "GOOG", "TSLA", "AMZN", "MSFT"]

    async def run_single(symbol: str) -> MarketIntelligenceState:
        state = create_market_state(
            context={"symbol": symbol, "sentiment_score": 0.8},
            portfolio=PortfolioSnapshot(cash=50000.0, total_equity=50000.0),
        )
        return await orchestrator.arun(state)

    results = await asyncio.gather(*[run_single(s) for s in symbols])

    assert len(results) == 5
    for idx, sym in enumerate(symbols):
        res = results[idx]
        assert res["artifacts"][0].headline == f"Market Intelligence Report for {sym}"
        assert res["signals"][0].symbol == sym
        assert sym in res["portfolio"].positions


@pytest.mark.issue_5
def test_risk_manager_veto_insufficient_cash(
    configured_orchestrator: MarketIntelligenceOrchestrator,
) -> None:
    """Verify that the risk manager vetoes buy orders when portfolio cash is insufficient."""
    initial_state = create_market_state(
        context={"symbol": "TSLA", "sentiment_score": 0.9},
        portfolio=PortfolioSnapshot(cash=100.0, total_equity=100.0),  # Not enough for 50 * $100
    )

    final_state = configured_orchestrator.run(initial_state)

    assert final_state["current_step"] == NodeNames.RISK_MANAGER
    assert len(final_state["decisions"]) == 1

    decision = final_state["decisions"][0]
    assert decision.status == DecisionStatus.REJECTED
    assert "Insufficient cash" in decision.reason

    # Portfolio cash and positions unchanged
    portfolio = final_state["portfolio"]
    assert isinstance(portfolio, PortfolioSnapshot)
    assert portfolio.cash == 100.0
    assert "TSLA" not in portfolio.positions
