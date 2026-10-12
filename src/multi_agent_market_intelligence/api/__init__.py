"""FastAPI REST API package for Multi-Agent Market Intelligence platform."""

from multi_agent_market_intelligence.api.app import app, create_app
from multi_agent_market_intelligence.api.config import APISettings
from multi_agent_market_intelligence.api.dependencies import get_orchestrator, get_settings
from multi_agent_market_intelligence.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ErrorResponse,
    HealthResponse,
)

__all__ = [
    "APISettings",
    "AnalysisRequest",
    "AnalysisResponse",
    "ErrorResponse",
    "HealthResponse",
    "app",
    "create_app",
    "get_orchestrator",
    "get_settings",
]
