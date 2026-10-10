"""Schema definitions and type contracts for the orchestrator."""

from collections.abc import Callable
from typing import Any

from multi_agent_market_intelligence.state.schema import (
    MarketIntelligenceState,
    create_market_state,
)

# Alias OrchestratorState to MarketIntelligenceState for backward compatibility
OrchestratorState = MarketIntelligenceState
create_initial_state = create_market_state

# Node handler contract: receives state, returns partial state updates
NodeHandler = Callable[[MarketIntelligenceState], dict[str, Any]]


class NodeNames:
    """Standard node identifiers for the market intelligence DAG."""

    RESEARCH: str = "research"
    TRADING_ANALYST: str = "trading_analyst"
    RISK_MANAGER: str = "risk_manager"
