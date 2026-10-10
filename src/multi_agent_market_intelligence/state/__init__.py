"""State management package defining domain models, reducers, and protocols."""

from multi_agent_market_intelligence.state.models import (
    AgentExecutionRecord,
    DecisionStatus,
    PortfolioSnapshot,
    Position,
    ResearchArtifact,
    RiskDecision,
    SignalAction,
    TradingSignal,
)
from multi_agent_market_intelligence.state.protocol import (
    StateContainer,
    StateProtocol,
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
from multi_agent_market_intelligence.state.schema import (
    MarketIntelligenceState,
    create_market_state,
)

__all__ = [
    "AgentExecutionRecord",
    "DecisionStatus",
    "MarketIntelligenceState",
    "PortfolioSnapshot",
    "Position",
    "ResearchArtifact",
    "RiskDecision",
    "SignalAction",
    "StateContainer",
    "StateProtocol",
    "TradingSignal",
    "append_artifacts",
    "append_decisions",
    "append_errors",
    "append_messages",
    "append_records",
    "append_signals",
    "create_market_state",
    "merge_dict",
]
