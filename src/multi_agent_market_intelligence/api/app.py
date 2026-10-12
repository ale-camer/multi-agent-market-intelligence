"""FastAPI application factory, middleware, and ASGI entrypoint."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from multi_agent_market_intelligence.api.config import APISettings
from multi_agent_market_intelligence.api.dependencies import get_settings
from multi_agent_market_intelligence.api.routers import api_v1_router, health_router
from multi_agent_market_intelligence.api.schemas import ErrorResponse


def create_app(settings: APISettings | None = None) -> FastAPI:
    """Create and configure FastAPI application instance.

    Args:
        settings: Optional APISettings overrides. Defaults to get_settings().

    Returns:
        Configured FastAPI application ready for ASGI deployment.
    """
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.title,
        version=cfg.version,
        description=cfg.description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=cfg.debug,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error_resp = ErrorResponse(
            error="ValidationError",
            detail=list(exc.errors()),
        )
        status_code = getattr(
            status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        return JSONResponse(
            status_code=status_code,
            content=error_resp.model_dump(mode="json"),
        )

    # Root metadata endpoint
    @app.get(
        "/",
        tags=["System"],
        summary="Service root metadata",
        description="Returns API service name, version, and documentation links.",
    )
    def root() -> dict[str, Any]:
        return {
            "service": cfg.title,
            "version": cfg.version,
            "description": cfg.description,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "api_v1": cfg.api_v1_prefix,
            "health": "/health",
        }

    # Mount routers
    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=cfg.api_v1_prefix)

    return app


app: FastAPI = create_app()
