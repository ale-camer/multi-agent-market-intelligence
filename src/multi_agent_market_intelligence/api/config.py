"""API configuration settings and environment variable bindings."""

import os

from pydantic import BaseModel, Field


class APISettings(BaseModel):
    """Global web service configuration parameters and runtime settings."""

    title: str = Field(
        default="Multi-Agent Market Intelligence API",
        description="FastAPI service title displayed in OpenAPI specification.",
    )
    version: str = Field(
        default="0.1.0",
        description="Semantic application API version.",
    )
    description: str = Field(
        default=(
            "Autonomous Multi-Agent Orchestration platform for financial research, "
            "quantitative trading, and portfolio risk management."
        ),
        description="OpenAPI service documentation summary.",
    )
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="URL prefix routing path for version 1 endpoints.",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origin hosts.",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode and verbose tracebacks.",
    )
    default_cash: float = Field(
        default=100_000.0,
        gt=0.0,
        description="Default portfolio liquid cash balance initialized when unprovided.",
    )

    @classmethod
    def from_env(cls) -> "APISettings":
        """Instantiate APISettings overriding defaults with active environment variables."""
        origins_str = os.getenv("API_CORS_ORIGINS")
        origins = [o.strip() for o in origins_str.split(",") if o.strip()] if origins_str else ["*"]
        return cls(
            title=os.getenv("API_TITLE", "Multi-Agent Market Intelligence API"),
            version=os.getenv("API_VERSION", "0.1.0"),
            description=os.getenv(
                "API_DESCRIPTION",
                (
                    "Autonomous Multi-Agent Orchestration platform for financial research, "
                    "quantitative trading, and portfolio risk management."
                ),
            ),
            api_v1_prefix=os.getenv("API_V1_PREFIX", "/api/v1"),
            cors_origins=origins,
            debug=os.getenv("API_DEBUG", "false").lower() in ("true", "1", "yes"),
            default_cash=float(os.getenv("API_DEFAULT_CASH", "100000.0")),
        )
