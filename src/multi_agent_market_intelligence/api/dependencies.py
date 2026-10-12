"""FastAPI dependency providers for orchestrator, configuration, and shared resources."""

from functools import lru_cache

from multi_agent_market_intelligence.api.config import APISettings
from multi_agent_market_intelligence.orchestrator.graph import MarketIntelligenceOrchestrator
from multi_agent_market_intelligence.research.agent import create_research_node_handler
from multi_agent_market_intelligence.risk.agent import create_risk_manager_node_handler
from multi_agent_market_intelligence.risk.portfolio import PortfolioTracker
from multi_agent_market_intelligence.trading.agent import create_trading_analyst_node_handler

_portfolio_tracker: PortfolioTracker | None = None


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


def get_portfolio_tracker() -> PortfolioTracker:
    """Provide stateful PortfolioTracker instance for portfolio management operations."""
    global _portfolio_tracker
    if _portfolio_tracker is None:
        _portfolio_tracker = PortfolioTracker(initial_cash=100_000.0)
    return _portfolio_tracker


def reset_portfolio_tracker(initial_cash: float = 100_000.0) -> PortfolioTracker:
    """Reset the global portfolio tracker instance with fresh cash balance."""
    global _portfolio_tracker
    _portfolio_tracker = PortfolioTracker(initial_cash=initial_cash)
    return _portfolio_tracker
