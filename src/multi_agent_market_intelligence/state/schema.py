"""Typed state schema with LangGraph reducer annotations."""

from typing import Annotated, Any, TypedDict

from multi_agent_market_intelligence.state.models import (
    AgentExecutionRecord,
    PortfolioSnapshot,
    ResearchArtifact,
    RiskDecision,
    TradingSignal,
)
from multi_agent_market_intelligence.state.reducers import (
    append_artifacts,
    append_decisions,
    append_errors,
    append_messages,
    append_records,
    append_signals,
    merge_dict,
)


class MarketIntelligenceState(TypedDict, total=False):
    """Strongly-typed multi-agent workflow state with LangGraph reducer channels.

    Each list-based channel uses an append reducer to prevent overwriting during
    concurrent or sequential node execution.
    """

    messages: Annotated[list[dict[str, Any]], append_messages]
    context: Annotated[dict[str, Any], merge_dict]
    artifacts: Annotated[list[ResearchArtifact], append_artifacts]
    signals: Annotated[list[TradingSignal], append_signals]
    decisions: Annotated[list[RiskDecision], append_decisions]
    records: Annotated[list[AgentExecutionRecord], append_records]
    portfolio: PortfolioSnapshot | dict[str, Any]
    current_step: str
    errors: Annotated[list[str], append_errors]


def create_market_state(
    messages: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    artifacts: list[ResearchArtifact] | None = None,
    signals: list[TradingSignal] | None = None,
    decisions: list[RiskDecision] | None = None,
    records: list[AgentExecutionRecord] | None = None,
    portfolio: PortfolioSnapshot | dict[str, Any] | None = None,
    current_step: str = "init",
    errors: list[str] | None = None,
) -> MarketIntelligenceState:
    """Factory creating a cleanly initialized MarketIntelligenceState dictionary."""
    return {
        "messages": messages if messages is not None else [],
        "context": context if context is not None else {},
        "artifacts": artifacts if artifacts is not None else [],
        "signals": signals if signals is not None else [],
        "decisions": decisions if decisions is not None else [],
        "records": records if records is not None else [],
        "portfolio": portfolio if portfolio is not None else {},
        "current_step": current_step,
        "errors": errors if errors is not None else [],
    }
