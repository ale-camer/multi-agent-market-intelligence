"""News extraction client and tools for research agents."""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from multi_agent_market_intelligence.research.models import NewsArticle
from multi_agent_market_intelligence.research.parser import NewsHTMLParser
from multi_agent_market_intelligence.state.models import ResearchArtifact


class NewsExtractor:
    """News extraction client supporting HTML parsing, URL fetching, and mock feeds."""

    DEFAULT_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; MultiAgentMarketIntelligence/1.0; +https://example.com/bot)"
    )

    def __init__(
        self,
        session: requests.Session | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.session.headers.update({"User-Agent": self.user_agent})

    def extract_from_html(
        self,
        html: str,
        source: str = "web",
        symbol: str | None = None,
        url: str | None = None,
    ) -> NewsArticle:
        """Parse raw HTML and construct a typed NewsArticle."""
        parsed = NewsHTMLParser.parse(html, fallback_source=source)
        return NewsArticle(
            headline=parsed["headline"],
            content=parsed["content"],
            source=parsed["source"],
            url=url,
            symbol=symbol,
            metadata=parsed["metadata"],
        )

    def extract_from_url(
        self,
        url: str,
        symbol: str | None = None,
        timeout: float = 10.0,
    ) -> NewsArticle:
        """Fetch article from URL via HTTP GET and parse into a typed NewsArticle."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc or "web"

        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()

        return self.extract_from_html(
            html=response.text,
            source=domain,
            symbol=symbol,
            url=url,
        )

    def fetch_news_by_symbol(
        self,
        symbol: str,
        limit: int = 5,
    ) -> list[NewsArticle]:
        """Fetch news articles for a specific stock ticker.

        Generates realistic structured news items offline for paper trading and test execution.
        """
        symbol_upper = symbol.upper()
        mock_templates = [
            (
                f"{symbol_upper} Announces Strategic Expansion in Enterprise AI",
                (
                    f"{symbol_upper} revealed a comprehensive multi-year roadmap today aimed at "
                    f"accelerating cloud enterprise workflows. Executive leadership highlighted "
                    f"strong enterprise customer adoption and recurring margin growth."
                ),
                "Reuters",
            ),
            (
                f"Analysts Upgrade {symbol_upper} Following Robust Quarterly Metrics",
                (
                    f"Wall Street investment analysts raised their price target for {symbol_upper} "
                    f"citing outperforming operational metrics, solid supply chain resilience, and "
                    f"accelerating operating cash flow."
                ),
                "Bloomberg",
            ),
            (
                f"Macroeconomic Factors and Sector Rotation Impact {symbol_upper} Trading",
                (
                    "Broader equity indexes experienced sector rotation amidst treasury yield "
                    "adjustments. "
                    f"Trading volume for {symbol_upper} remained active as institutional "
                    "participants rebalanced equity portfolios."
                ),
                "Financial Times",
            ),
            (
                f"{symbol_upper} Unveils Next-Generation Product Suite at Industry Summit",
                (
                    f"At the global technology expo, {symbol_upper} showcased its next-generation "
                    "platform featuring high energy efficiency and enhanced security benchmarks."
                ),
                "MarketWatch",
            ),
            (
                f"Regulatory and Compliance Updates in {symbol_upper}'s Core Market",
                (
                    "Industry watchdogs published new compliance standards applicable to "
                    f"companies in the sector. {symbol_upper} stated its operational framework "
                    "fully complies with revised guidelines."
                ),
                "Wall Street Journal",
            ),
        ]

        count = min(limit, len(mock_templates))
        articles: list[NewsArticle] = []

        for i in range(count):
            headline, content, source = mock_templates[i]
            source_slug = source.lower().replace(" ", "")
            news_url = f"https://{source_slug}.com/news/{symbol_upper.lower()}-{i + 1}"
            articles.append(
                NewsArticle(
                    headline=headline,
                    content=content,
                    source=source,
                    url=news_url,
                    symbol=symbol_upper,
                    published_at=datetime.now(timezone.utc),
                    metadata={"index": i, "simulated": True},
                )
            )

        return articles


def to_research_artifact(
    article: NewsArticle,
    sentiment_score: float = 0.0,
) -> ResearchArtifact:
    """Convert an extracted NewsArticle into a standardized ResearchArtifact."""
    summary = article.content[:300] + "..." if len(article.content) > 300 else article.content
    metadata: dict[str, Any] = dict(article.metadata)
    if article.url:
        metadata["url"] = article.url
    if article.symbol:
        metadata["symbol"] = article.symbol

    return ResearchArtifact(
        headline=article.headline,
        summary=summary,
        sentiment_score=sentiment_score,
        source=article.source,
        timestamp=article.published_at,
        metadata=metadata,
    )
