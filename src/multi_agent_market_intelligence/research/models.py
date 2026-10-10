"""Domain models for market news articles and intelligence sources."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportType(str, Enum):
    """Supported standardized financial report and filing types."""

    TEN_K = "10-K"
    TEN_Q = "10-Q"
    EIGHT_K = "8-K"
    EARNINGS_RELEASE = "earnings_release"
    ANNUAL_REPORT = "annual_report"


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


class FinancialReport(BaseModel):
    """Structured representation of a corporate financial report or filing."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    report_type: ReportType | str = ReportType.TEN_Q
    period: str
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    content: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    filing_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "sec_edgar"
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
