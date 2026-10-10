"""Research agent domain models, parsers, and extraction tools."""

from multi_agent_market_intelligence.research.models import NewsArticle
from multi_agent_market_intelligence.research.news import (
    NewsExtractor,
    to_research_artifact,
)
from multi_agent_market_intelligence.research.parser import NewsHTMLParser

__all__ = [
    "NewsArticle",
    "NewsExtractor",
    "NewsHTMLParser",
    "to_research_artifact",
]
