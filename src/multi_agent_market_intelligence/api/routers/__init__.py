"""API routers aggregation and versioning."""

from fastapi import APIRouter

from multi_agent_market_intelligence.api.routers.analysis import router as analysis_router
from multi_agent_market_intelligence.api.routers.health import router as health_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(analysis_router)

__all__ = ["analysis_router", "api_v1_router", "health_router"]
