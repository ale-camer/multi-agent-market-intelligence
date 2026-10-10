"""Domain models for market news articles and intelligence sources."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NewsArticle(BaseModel):
    """Structured representation of an extracted news article."""

    model_config = ConfigDict(extra="allow")

    headline: str
    content: str
    source: str = "web"
    url: str | None = None
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __eq__(self, other: Any) -> bool:
        """Allow comparison against raw dicts for testing and adapter compatibility."""
        if isinstance(other, dict):
            for k, v in other.items():
                val = getattr(self, k, None)
                if val is None and self.__pydantic_extra__:
                    val = self.__pydantic_extra__.get(k)
                if val != v:
                    return False
            return True
        return super().__eq__(other)
