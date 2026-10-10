"""Market Intelligence DAG workflow orchestrator using LangGraph."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from multi_agent_market_intelligence.orchestrator.base import BaseOrchestrator
from multi_agent_market_intelligence.orchestrator.schema import (
    NodeHandler,
    NodeNames,
    OrchestratorState,
)


def default_research_handler(state: OrchestratorState) -> dict[str, Any]:
    """Default handler for the Research Agent node."""
    messages = list(state.get("messages", []))
    messages.append({"role": NodeNames.RESEARCH, "content": "Research analysis completed."})
    return {
        "current_step": NodeNames.RESEARCH,
        "messages": messages,
    }


def default_trading_analyst_handler(state: OrchestratorState) -> dict[str, Any]:
    """Default handler for the Trading Analyst node."""
    messages = list(state.get("messages", []))
    messages.append({"role": NodeNames.TRADING_ANALYST, "content": "Trading analysis completed."})
    return {
        "current_step": NodeNames.TRADING_ANALYST,
        "messages": messages,
    }


def default_risk_manager_handler(state: OrchestratorState) -> dict[str, Any]:
    """Default handler for the Risk & Portfolio Manager node."""
    messages = list(state.get("messages", []))
    messages.append({"role": NodeNames.RISK_MANAGER, "content": "Risk evaluation completed."})
    return {
        "current_step": NodeNames.RISK_MANAGER,
        "messages": messages,
    }


class MarketIntelligenceOrchestrator(BaseOrchestrator[OrchestratorState]):
    """Central orchestrator managing the Market Intelligence multi-agent workflow DAG.

    Sequences execution across three specialized nodes:
    1. Research Agent: News extraction and sentiment analysis.
    2. Trading Analyst: Technical indicators and signal generation.
    3. Risk & Portfolio Manager: Limits validation and position sizing.
    """

    VALID_NODES: set[str] = {
        NodeNames.RESEARCH,
        NodeNames.TRADING_ANALYST,
        NodeNames.RISK_MANAGER,
    }

    def __init__(
        self,
        research_handler: NodeHandler | None = None,
        trading_analyst_handler: NodeHandler | None = None,
        risk_manager_handler: NodeHandler | None = None,
    ) -> None:
        super().__init__()
        self._handlers: dict[str, NodeHandler] = {
            NodeNames.RESEARCH: research_handler or default_research_handler,
            NodeNames.TRADING_ANALYST: trading_analyst_handler or default_trading_analyst_handler,
            NodeNames.RISK_MANAGER: risk_manager_handler or default_risk_manager_handler,
        }

    def register_handler(self, node_name: str, handler: NodeHandler) -> None:
        """Register or override a handler for a specific node in the DAG.

        Args:
            node_name: The identifier of the node to override.
            handler: Callable taking state and returning partial state updates.

        Raises:
            ValueError: If node_name is not recognized.
        """
        if node_name not in self.VALID_NODES:
            raise ValueError(
                f"Unknown node '{node_name}'. Valid nodes are: {sorted(self.VALID_NODES)}"
            )
        self._handlers[node_name] = handler
        # Invalidate compiled graph to require recompilation with new handler
        self._compiled_graph = None

    def get_handler(self, node_name: str) -> NodeHandler:
        """Retrieve the handler currently registered for a specific node.

        Args:
            node_name: The node identifier.

        Returns:
            The registered NodeHandler callable.

        Raises:
            KeyError: If the node is not found in registered handlers.
        """
        if node_name not in self._handlers:
            raise KeyError(f"Node '{node_name}' is not registered.")
        return self._handlers[node_name]

    def build_graph(self) -> StateGraph[OrchestratorState, Any, Any, Any]:
        """Construct the market intelligence DAG with sequential agent nodes.

        Topology:
            START -> research -> trading_analyst -> risk_manager -> END

        Returns:
            The uncompiled StateGraph builder.
        """
        builder: StateGraph[OrchestratorState, Any, Any, Any] = StateGraph(OrchestratorState)

        # Dispatch node calls dynamically to current handlers
        def _research_node(state: OrchestratorState) -> dict[str, Any]:
            return self._handlers[NodeNames.RESEARCH](state)

        def _trading_analyst_node(state: OrchestratorState) -> dict[str, Any]:
            return self._handlers[NodeNames.TRADING_ANALYST](state)

        def _risk_manager_node(state: OrchestratorState) -> dict[str, Any]:
            return self._handlers[NodeNames.RISK_MANAGER](state)

        builder.add_node(NodeNames.RESEARCH, _research_node)
        builder.add_node(NodeNames.TRADING_ANALYST, _trading_analyst_node)
        builder.add_node(NodeNames.RISK_MANAGER, _risk_manager_node)

        builder.add_edge(START, NodeNames.RESEARCH)
        builder.add_edge(NodeNames.RESEARCH, NodeNames.TRADING_ANALYST)
        builder.add_edge(NodeNames.TRADING_ANALYST, NodeNames.RISK_MANAGER)
        builder.add_edge(NodeNames.RISK_MANAGER, END)

        return builder
