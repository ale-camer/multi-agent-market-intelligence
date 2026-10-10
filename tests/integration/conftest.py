"""Shared integration test fixtures and simulated agents for pipeline testing."""

from typing import Any

import pytest

from multi_agent_market_intelligence import (
    AgentConfig,
    AgentRole,
    BaseAgent,
    DecisionStatus,
    MarketIntelligenceOrchestrator,
    MarketIntelligenceState,
    MessageBus,
    MessageType,
    NodeNames,
    PortfolioSnapshot,
    Position,
    ResearchArtifact,
    RiskDecision,
    SignalAction,
    TradingSignal,
)


class SimulatedResearchAgent(BaseAgent):
    """Simulates research intelligence extraction and publication."""

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        context = state.get("context", {})
        symbol = str(context.get("symbol", "AAPL"))
        sentiment = float(context.get("sentiment_score", 0.75))
        correlation_id = context.get("correlation_id")

        artifact = ResearchArtifact(
            headline=f"Market Intelligence Report for {symbol}",
            summary=f"Automated research analysis indicating sentiment score {sentiment}",
            sentiment_score=sentiment,
            source="simulated_wire",
        )

        self.send_message(
            recipient=NodeNames.TRADING_ANALYST,
            message_type=MessageType.RESEARCH_REPORT,
            payload={"symbol": symbol, "sentiment": sentiment},
            correlation_id=correlation_id,
        )

        return {
            "current_step": NodeNames.RESEARCH,
            "artifacts": [artifact],
        }


class SimulatedAnalystAgent(BaseAgent):
    """Simulates trading signal generation based on research artifacts."""

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        context = state.get("context", {})
        symbol = str(context.get("symbol", "AAPL"))
        correlation_id = context.get("correlation_id")

        artifacts = state.get("artifacts", [])
        if artifacts and artifacts[-1].sentiment_score > 0.2:
            action = SignalAction.BUY
            confidence = 0.85
            target_price = 200.0
            stop_loss = 180.0
        elif artifacts and artifacts[-1].sentiment_score < -0.2:
            action = SignalAction.SELL
            confidence = 0.80
            target_price = 150.0
            stop_loss = 190.0
        else:
            action = SignalAction.HOLD
            confidence = 0.50
            target_price = None
            stop_loss = None

        signal = TradingSignal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            target_price=target_price,
            stop_loss=stop_loss,
            reasoning=f"Signal derived from {len(artifacts)} research artifacts.",
        )

        self.send_message(
            recipient=NodeNames.RISK_MANAGER,
            message_type=MessageType.SIGNAL_PROPOSAL,
            payload={"symbol": symbol, "action": str(action), "confidence": confidence},
            correlation_id=correlation_id,
        )

        return {
            "current_step": NodeNames.TRADING_ANALYST,
            "signals": [signal],
        }


class SimulatedRiskAgent(BaseAgent):
    """Simulates portfolio risk checking, signal approval/veto, and position sizing."""

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        context = state.get("context", {})
        correlation_id = context.get("correlation_id")
        signals = state.get("signals", [])
        raw_portfolio = state.get("portfolio", {})

        if isinstance(raw_portfolio, PortfolioSnapshot):
            portfolio = raw_portfolio
        elif isinstance(raw_portfolio, dict) and raw_portfolio:
            portfolio = PortfolioSnapshot.model_validate(raw_portfolio)
        else:
            portfolio = PortfolioSnapshot(cash=50000.0, total_equity=50000.0)

        if not signals:
            decision = RiskDecision(
                status=DecisionStatus.REJECTED,
                reason="No signals provided for risk evaluation.",
            )
            return {"current_step": NodeNames.RISK_MANAGER, "decisions": [decision]}

        latest_signal = signals[-1]
        symbol = latest_signal.symbol
        price = 100.0  # Simulated price

        if latest_signal.action == SignalAction.HOLD:
            decision = RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=latest_signal,
                reason="HOLD signals do not initiate new positions.",
            )
        elif latest_signal.action == SignalAction.BUY:
            required_cash = 50.0 * price
            if portfolio.cash < required_cash:
                decision = RiskDecision(
                    status=DecisionStatus.REJECTED,
                    original_signal=latest_signal,
                    reason=(
                        f"Insufficient cash: required {required_cash}, available {portfolio.cash}"
                    ),
                )
            else:
                decision = RiskDecision(
                    status=DecisionStatus.APPROVED,
                    original_signal=latest_signal,
                    approved_size=50.0,
                    reason="Order within risk limits.",
                )
                new_cash = portfolio.cash - required_cash
                existing_pos = portfolio.positions.get(symbol)
                new_qty = (existing_pos.quantity if existing_pos else 0.0) + 50.0
                new_positions = dict(portfolio.positions)
                new_positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_qty,
                    entry_price=price,
                    current_price=price,
                )
                portfolio = PortfolioSnapshot(
                    cash=new_cash,
                    positions=new_positions,
                    total_equity=new_cash
                    + sum(p.quantity * p.current_price for p in new_positions.values()),
                )
        elif latest_signal.action == SignalAction.SELL:
            existing_pos = portfolio.positions.get(symbol)
            if not existing_pos or existing_pos.quantity < 50.0:
                decision = RiskDecision(
                    status=DecisionStatus.REJECTED,
                    original_signal=latest_signal,
                    reason="Insufficient position quantity to sell.",
                )
            else:
                decision = RiskDecision(
                    status=DecisionStatus.APPROVED,
                    original_signal=latest_signal,
                    approved_size=50.0,
                    reason="Sell order approved.",
                )
                new_cash = portfolio.cash + (50.0 * price)
                new_positions = dict(portfolio.positions)
                if existing_pos.quantity == 50.0:
                    del new_positions[symbol]
                else:
                    new_positions[symbol] = Position(
                        symbol=symbol,
                        quantity=existing_pos.quantity - 50.0,
                        entry_price=existing_pos.entry_price,
                        current_price=price,
                    )
                portfolio = PortfolioSnapshot(
                    cash=new_cash,
                    positions=new_positions,
                    total_equity=new_cash
                    + sum(p.quantity * p.current_price for p in new_positions.values()),
                )
        else:
            decision = RiskDecision(status=DecisionStatus.REJECTED, reason="Unknown action.")

        self.send_message(
            recipient="orchestrator",
            message_type=MessageType.RISK_EVALUATION,
            payload={"status": str(decision.status), "approved_size": decision.approved_size},
            correlation_id=correlation_id,
        )

        return {
            "current_step": NodeNames.RISK_MANAGER,
            "decisions": [decision],
            "portfolio": portfolio,
        }


@pytest.fixture
def shared_bus() -> MessageBus:
    """Provide a clean MessageBus instance."""
    return MessageBus()


@pytest.fixture
def simulated_research_agent(shared_bus: MessageBus) -> SimulatedResearchAgent:
    """Provide an initialized research agent connected to shared_bus."""
    return SimulatedResearchAgent(
        config=AgentConfig(name=NodeNames.RESEARCH, role=AgentRole.RESEARCH),
        message_bus=shared_bus,
    )


@pytest.fixture
def simulated_analyst_agent(shared_bus: MessageBus) -> SimulatedAnalystAgent:
    """Provide an initialized trading analyst agent connected to shared_bus."""
    return SimulatedAnalystAgent(
        config=AgentConfig(name=NodeNames.TRADING_ANALYST, role=AgentRole.TRADING_ANALYST),
        message_bus=shared_bus,
    )


@pytest.fixture
def simulated_risk_agent(shared_bus: MessageBus) -> SimulatedRiskAgent:
    """Provide an initialized risk manager agent connected to shared_bus."""
    return SimulatedRiskAgent(
        config=AgentConfig(name=NodeNames.RISK_MANAGER, role=AgentRole.RISK_MANAGER),
        message_bus=shared_bus,
    )


@pytest.fixture
def configured_orchestrator(
    simulated_research_agent: SimulatedResearchAgent,
    simulated_analyst_agent: SimulatedAnalystAgent,
    simulated_risk_agent: SimulatedRiskAgent,
) -> MarketIntelligenceOrchestrator:
    """Provide an orchestrator pre-wired with simulated domain agents."""
    orchestrator = MarketIntelligenceOrchestrator()
    orchestrator.register_handler(NodeNames.RESEARCH, simulated_research_agent.as_node_handler())
    orchestrator.register_handler(
        NodeNames.TRADING_ANALYST, simulated_analyst_agent.as_node_handler()
    )
    orchestrator.register_handler(NodeNames.RISK_MANAGER, simulated_risk_agent.as_node_handler())
    return orchestrator
