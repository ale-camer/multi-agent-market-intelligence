"""FastAPI dependency providers for orchestrator, configuration, and shared resources."""

from functools import lru_cache

from multi_agent_market_intelligence.api.config import APISettings
from multi_agent_market_intelligence.orchestrator.graph import MarketIntelligenceOrchestrator
from multi_agent_market_intelligence.research.agent import create_research_node_handler
from multi_agent_market_intelligence.risk.agent import create_risk_manager_node_handler
from multi_agent_market_intelligence.trading.agent import create_trading_analyst_node_handler


@lru_cache
def get_settings() -> APISettings:
    """Provide cached application configuration settings."""
    return APISettings.from_env()


def get_orchestrator() -> MarketIntelligenceOrchestrator:
    """Provide configured MarketIntelligenceOrchestrator instance for DAG execution."""
    return MarketIntelligenceOrchestrator(
        research_handler=create_research_node_handler(),
        trading_analyst_handler=create_trading_analyst_node_handler(),
        risk_manager_handler=create_risk_manager_node_handler(),
    )
