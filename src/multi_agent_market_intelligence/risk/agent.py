"""Autonomous Risk & Portfolio Manager Agent validating trading signals and managing capital."""

from collections.abc import Callable
from typing import Any

from multi_agent_market_intelligence.agents.base import BaseAgent
from multi_agent_market_intelligence.agents.schema import AgentConfig, AgentRole
from multi_agent_market_intelligence.messaging.bus import MessageBus
from multi_agent_market_intelligence.messaging.models import MessageType
from multi_agent_market_intelligence.orchestrator.schema import NodeNames, OrchestratorState
from multi_agent_market_intelligence.risk.portfolio import PortfolioTracker
from multi_agent_market_intelligence.risk.validation import SignalRiskValidator
from multi_agent_market_intelligence.state.models import (
    DecisionStatus,
    PortfolioSnapshot,
    RiskDecision,
    TradingSignal,
)
from multi_agent_market_intelligence.state.schema import MarketIntelligenceState


class RiskPortfolioManagerAgent(BaseAgent):
    """Autonomous Risk & Portfolio Manager Agent responsible for signal validation and capital."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        message_bus: MessageBus | None = None,
        validator: SignalRiskValidator | None = None,
        tracker: PortfolioTracker | None = None,
        auto_execute_trades: bool = True,
        sector_mappings: dict[str, str] | None = None,
    ) -> None:
        """Initialize the Risk & Portfolio Manager Agent.

        Args:
            config: Agent configuration parameters.
            message_bus: Central message bus for inter-agent pub/sub communication.
            validator: Quantitative signal validation engine.
            tracker: Real-time portfolio accounting engine.
            auto_execute_trades: If True, mutates tracker positions and cash upon approval.
            sector_mappings: Optional mapping from ticker symbols to market sector names.
        """
        cfg = config or AgentConfig(
            name="RiskPortfolioManager",
            role=AgentRole.RISK_MANAGER,
            capabilities=[
                "risk_limits_validation",
                "portfolio_state_tracking",
                "position_sizing",
                "decision_dispatch",
            ],
        )
        super().__init__(config=cfg, message_bus=message_bus)

        if self.message_bus is not None and self.name != "risk_manager":
            self.message_bus.subscribe("risk_manager", self.receive_message)

        self.validator: SignalRiskValidator = validator or SignalRiskValidator()
        self.sector_mappings: dict[str, str] = dict(sector_mappings or {})
        self.tracker: PortfolioTracker = tracker or PortfolioTracker(
            initial_cash=100_000.0,
            sector_mappings=self.sector_mappings,
        )
        if self.sector_mappings:
            self.tracker.set_sector_mappings(self.sector_mappings)

        self.auto_execute_trades: bool = auto_execute_trades

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Execute risk evaluation and portfolio update flow over candidate signals.

        Args:
            state: Current market intelligence workflow state.

        Returns:
            Dictionary with state updates: decisions, portfolio, messages, current_step, context.
        """
        context = dict(state.get("context", {}))
        signals = list(state.get("signals", []))
        if not signals and "signals" in context:
            ctx_signals = context["signals"]
            if isinstance(ctx_signals, list):
                signals = list(ctx_signals)

        # Synchronize portfolio state from incoming state if present
        state_portfolio = state.get("portfolio")
        if not state_portfolio and "portfolio" in context:
            state_portfolio = context["portfolio"]

        eval_portfolio: PortfolioTracker | PortfolioSnapshot | dict[str, Any] = self.tracker
        if state_portfolio:
            eval_portfolio = state_portfolio
            if isinstance(state_portfolio, PortfolioSnapshot):
                self.tracker = PortfolioTracker(
                    initial_cash=state_portfolio.cash,
                    positions=state_portfolio.positions,
                    sector_mappings=self.sector_mappings,
                )
            elif isinstance(state_portfolio, dict) and state_portfolio:
                self.tracker = PortfolioTracker(
                    initial_cash=float(state_portfolio.get("cash", 0.0)),
                    positions=state_portfolio.get("positions", {}),
                    sector_mappings=self.sector_mappings,
                )

        correlation_id = str(context.get("correlation_id", "")) or None
        prices: dict[str, float] = {}
        if isinstance(context.get("prices"), dict):
            for k, v in context["prices"].items():
                prices[str(k)] = float(v)

        sectors = dict(self.sector_mappings)
        if isinstance(context.get("sectors"), dict):
            for k, v in context["sectors"].items():
                sectors[str(k)] = str(v)

        proposed_sizes: dict[str, float] = {}
        if isinstance(context.get("proposed_sizes"), dict):
            for k, v in context["proposed_sizes"].items():
                proposed_sizes[str(k)] = float(v)

        # Handle empty signals scenario gracefully
        if not signals:
            snapshot = self.tracker.create_snapshot()
            messages = list(state.get("messages", []))
            messages.append(
                {
                    "role": NodeNames.RISK_MANAGER,
                    "content": "No trading signals available to evaluate.",
                }
            )
            return {
                "decisions": [],
                "portfolio": snapshot,
                "current_step": NodeNames.RISK_MANAGER,
                "messages": messages,
                "context": {
                    "decisions_count": 0,
                    "approved_count": 0,
                    "modified_count": 0,
                    "rejected_count": 0,
                },
            }

        # Validate signals batch with cumulative capacity tracking
        decisions: list[RiskDecision] = self.validator.validate_signals_batch(
            signals=signals,
            portfolio=eval_portfolio,
            prices=prices,
            proposed_sizes=proposed_sizes,
            sectors=sectors,
            track_cumulative_capacity=True,
        )

        # Auto-execute approved or modified orders on portfolio tracker
        if self.auto_execute_trades:
            for decision in decisions:
                if decision.status in (DecisionStatus.APPROVED, DecisionStatus.MODIFIED):
                    if decision.approved_size > 0.0:
                        sig = decision.original_signal
                        if isinstance(sig, TradingSignal):
                            fill_price = prices.get(sig.symbol)
                            if fill_price is None or fill_price <= 0.0:
                                if isinstance(sig.indicators, dict) and "close" in sig.indicators:
                                    fill_price = float(sig.indicators["close"])
                                else:
                                    fill_price = 100.0

                            try:
                                self.tracker.apply_trade(
                                    symbol=sig.symbol,
                                    action=sig.action,
                                    quantity=decision.approved_size,
                                    price=fill_price,
                                )
                            except ValueError:
                                # Safe pass-through if edge condition restricts trade
                                pass

        updated_snapshot = self.tracker.create_snapshot()

        app_count = sum(1 for d in decisions if d.status == DecisionStatus.APPROVED)
        mod_count = sum(1 for d in decisions if d.status == DecisionStatus.MODIFIED)
        rej_count = sum(1 for d in decisions if d.status == DecisionStatus.REJECTED)

        # Broadcast evaluation results on message bus
        if self.message_bus is not None:
            self.send_message(
                recipient="orchestrator",
                message_type=MessageType.RISK_EVALUATION,
                payload={
                    "decisions_count": len(decisions),
                    "approved_count": app_count,
                    "modified_count": mod_count,
                    "rejected_count": rej_count,
                    "decisions": [d.model_dump() for d in decisions],
                    "total_equity": updated_snapshot.total_equity,
                    "cash": updated_snapshot.cash,
                },
                correlation_id=correlation_id,
            )

        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": NodeNames.RISK_MANAGER,
                "content": (
                    f"Risk evaluation complete for {len(decisions)} signals: "
                    f"{app_count} approved, {mod_count} modified, {rej_count} rejected."
                ),
            }
        )

        return {
            "decisions": decisions,
            "portfolio": updated_snapshot,
            "current_step": NodeNames.RISK_MANAGER,
            "messages": messages,
            "context": {
                "decisions_count": len(decisions),
                "approved_count": app_count,
                "modified_count": mod_count,
                "rejected_count": rej_count,
            },
        }

    async def process_async(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Asynchronously execute risk and portfolio management evaluation.

        Args:
            state: Current market intelligence workflow state.

        Returns:
            Dictionary with state updates: decisions, portfolio, messages, current_step, context.
        """
        return self.process(state)


# Public alias
RiskManagerAgent = RiskPortfolioManagerAgent


def create_risk_manager_node_handler(
    agent: RiskPortfolioManagerAgent | None = None,
) -> Callable[[OrchestratorState], dict[str, Any]]:
    """Create an orchestrator-compatible node handler powered by a RiskPortfolioManagerAgent.

    Args:
        agent: Optional custom RiskPortfolioManagerAgent instance.

    Returns:
        Callable compatible with LangGraph Orchestrator node contracts.
    """
    risk_agent = agent or RiskPortfolioManagerAgent()

    def risk_manager_node_handler(state: OrchestratorState) -> dict[str, Any]:
        market_state: MarketIntelligenceState = {
            "messages": list(state.get("messages", [])),
            "context": dict(state.get("context", {})),
            "artifacts": list(state.get("artifacts", [])),
            "signals": list(state.get("signals", [])),
            "decisions": list(state.get("decisions", [])),
            "records": list(state.get("records", [])),
            "portfolio": state.get("portfolio", {}),
            "current_step": str(state.get("current_step", "init")),
            "errors": list(state.get("errors", [])),
        }
        return risk_agent.execute(market_state)

    return risk_manager_node_handler
