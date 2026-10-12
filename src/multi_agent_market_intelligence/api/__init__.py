"""FastAPI REST API package for Multi-Agent Market Intelligence platform."""

from multi_agent_market_intelligence.api.app import app, create_app
from multi_agent_market_intelligence.api.config import APISettings
from multi_agent_market_intelligence.api.dependencies import (
    get_orchestrator,
    get_portfolio_tracker,
    get_settings,
    reset_portfolio_tracker,
)
from multi_agent_market_intelligence.api.routers import (
    analysis_router,
    api_v1_router,
    health_router,
    portfolio_router,
)
from multi_agent_market_intelligence.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    CashTransactionRequest,
    CashTransactionResponse,
    ErrorResponse,
    HealthResponse,
    PortfolioResetRequest,
    PortfolioStateResponse,
    PositionsListResponse,
    TradeExecutionRequest,
    TradeExecutionResponse,
    TradeHistoryResponse,
)

__all__ = [
    "APISettings",
    "AnalysisRequest",
    "AnalysisResponse",
    "CashTransactionRequest",
    "CashTransactionResponse",
    "ErrorResponse",
    "HealthResponse",
    "PortfolioResetRequest",
    "PortfolioStateResponse",
    "PositionsListResponse",
    "TradeExecutionRequest",
    "TradeExecutionResponse",
    "TradeHistoryResponse",
    "analysis_router",
    "api_v1_router",
    "app",
    "create_app",
    "get_orchestrator",
    "get_portfolio_tracker",
    "get_settings",
    "health_router",
    "portfolio_router",
    "reset_portfolio_tracker",
]
