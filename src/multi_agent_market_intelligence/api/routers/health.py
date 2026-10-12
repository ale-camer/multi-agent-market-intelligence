"""Health check and readiness probe endpoints."""

from fastapi import APIRouter, Depends

from multi_agent_market_intelligence.api.config import APISettings
from multi_agent_market_intelligence.api.dependencies import get_settings
from multi_agent_market_intelligence.api.schemas import HealthResponse

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check probe",
    description="Returns operational status and service metadata for liveness/readiness probes.",
)
def get_health(settings: APISettings = Depends(get_settings)) -> HealthResponse:
    """Return operational health status and version telemetry."""
    return HealthResponse(
        status="healthy",
        service=settings.title,
        version=settings.version,
    )
