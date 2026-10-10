"""Unit tests for news extraction models, parser, and tools."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from multi_agent_market_intelligence.research import (
    NewsArticle,
    NewsExtractor,
    NewsHTMLParser,
    to_research_artifact,
)
from multi_agent_market_intelligence.state.models import ResearchArtifact


@pytest.mark.issue_6
def test_news_article_creation_defaults() -> None:
    """Ensure NewsArticle sets sensible defaults including UTC timestamp."""
    article = NewsArticle(
        headline="Apple Reports Record Earnings",
        content="Apple Inc. announced financial results for its fiscal quarter...",
    )

    assert article.headline == "Apple Reports Record Earnings"
    assert "Apple Inc." in article.content
    assert article.source == "web"
    assert article.url is None
    assert article.symbol is None
    assert article.metadata == {}
    assert isinstance(article.published_at, datetime)
    assert article.published_at.tzinfo is not None


@pytest.mark.issue_6
def test_news_article_custom_fields_and_extras() -> None:
    """Ensure NewsArticle supports custom fields and extra attributes."""
    pub_time = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    article = NewsArticle(
        headline="Tech Rally Continues",
        content="Semiconductor stocks led the market rally today.",
        source="Bloomberg",
        url="https://bloomberg.com/news/tech-rally",
        published_at=pub_time,
        symbol="NVDA",
        metadata={"author": "Jane Doe", "tickers": ["NVDA", "AMD"]},
        custom_tag="tech",  # type: ignore[call-arg]
    )

    assert article.headline == "Tech Rally Continues"
    assert article.source == "Bloomberg"
    assert article.url == "https://bloomberg.com/news/tech-rally"
    assert article.published_at == pub_time
    assert article.symbol == "NVDA"
    assert article.metadata["author"] == "Jane Doe"
    assert getattr(article, "custom_tag", None) == "tech"


@pytest.mark.issue_6
def test_news_article_dict_equality() -> None:
    """Ensure NewsArticle compares correctly with dictionaries and other instances."""
    article = NewsArticle(
        headline="Market Closes Higher",
        content="The S&P 500 rose 1.2% today.",
        source="Reuters",
        symbol="SPY",
    )

    assert article == {
        "headline": "Market Closes Higher",
        "content": "The S&P 500 rose 1.2% today.",
        "source": "Reuters",
        "symbol": "SPY",
    }
    assert article != {"headline": "Different Headline"}
    assert article != "invalid-type"


@pytest.mark.issue_6
def test_news_html_parser_strip_boilerplate_tags() -> None:
    """Ensure parser removes scripts, styles, navigation, footer, and boilerplate tags."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tech Innovation in Cloud</title>
        <style>body { background-color: #000; }</style>
        <script>console.log("analytics tracking");</script>
    </head>
    <body>
        <nav><a href="/home">Home</a><a href="/market">Markets</a></nav>
        <header><h1>Market Morning Digest</h1></header>
        <main>
            <p>Cloud service providers reported notable revenue acceleration this quarter.</p>
            <aside>Related stories: 10 other stocks to watch.</aside>
            <p>Enterprise migration to distributed cloud architectures remains robust.</p>
        </main>
        <form><button>Subscribe Now</button></form>
        <footer><p>Copyright 2026 Financial News Inc.</p></footer>
    </body>
    </html>
    """

    parsed = NewsHTMLParser.parse(html)

    assert parsed["headline"] == "Market Morning Digest"
    assert "Cloud service providers reported notable revenue acceleration" in parsed["content"]
    assert "Enterprise migration to distributed cloud architectures" in parsed["content"]
    assert "analytics tracking" not in parsed["content"]
    assert "Home" not in parsed["content"]
    assert "Subscribe Now" not in parsed["content"]
    assert "Copyright 2026" not in parsed["content"]
    assert "Related stories" not in parsed["content"]


@pytest.mark.issue_6
def test_news_html_parser_headline_resolution_hierarchy() -> None:
    """Ensure headline precedence respects og:title -> twitter -> meta -> h1 -> title."""
    # 1. OpenGraph title precedence
    html_og = """
    <html>
        <head>
            <meta property="og:title" content="OpenGraph Headline" />
            <meta name="twitter:title" content="Twitter Headline" />
            <title>Page Title</title>
        </head>
        <body><h1>H1 Headline</h1><p>Article body paragraph text goes here.</p></body>
    </html>
    """
    assert NewsHTMLParser.parse(html_og)["headline"] == "OpenGraph Headline"

    # 2. Twitter title fallback
    html_twitter = """
    <html>
        <head>
            <meta name="twitter:title" content="Twitter Headline" />
            <title>Page Title</title>
        </head>
        <body><h1>H1 Headline</h1><p>Article body paragraph text goes here.</p></body>
    </html>
    """
    assert NewsHTMLParser.parse(html_twitter)["headline"] == "Twitter Headline"

    # 3. Meta title fallback
    html_meta = """
    <html>
        <head>
            <meta name="title" content="Meta Name Headline" />
            <title>Page Title</title>
        </head>
        <body><h1>H1 Headline</h1><p>Article body paragraph text goes here.</p></body>
    </html>
    """
    assert NewsHTMLParser.parse(html_meta)["headline"] == "Meta Name Headline"

    # 4. H1 tag fallback
    html_h1 = """
    <html>
        <head><title>Page Title</title></head>
        <body><h1>Primary H1 Headline</h1><p>Article body paragraph text goes here.</p></body>
    </html>
    """
    assert NewsHTMLParser.parse(html_h1)["headline"] == "Primary H1 Headline"

    # 5. Title tag fallback
    html_title = """
    <html>
        <head><title>Page Title Headline</title></head>
        <body><p>Article body paragraph text goes here without heading.</p></body>
    </html>
    """
    assert NewsHTMLParser.parse(html_title)["headline"] == "Page Title Headline"

    # 6. Fallback when none available
    html_empty = "<html><body><p>Article body paragraph text goes here.</p></body></html>"
    assert NewsHTMLParser.parse(html_empty)["headline"] == "Untitled Article"


@pytest.mark.issue_6
def test_news_html_parser_metadata_and_site_name() -> None:
    """Ensure OpenGraph and metadata fields are properly extracted."""
    html = """
    <html>
        <head>
            <meta property="og:title" content="Fed Holds Interest Rates Steady" />
            <meta property="og:site_name" content="Wall Street Journal" />
            <meta property="og:description" content="Central bank maintains target range." />
            <meta name="author" content="Jerome Powell Watch" />
            <meta property="article:published_time" content="2026-10-10T14:00:00Z" />
        </head>
        <body>
            <article>
                <p>The Federal Reserve decided today to maintain benchmark interest rates.</p>
                <p>Officials signaled confidence in economic indicators and price stability.</p>
            </article>
        </body>
    </html>
    """

    parsed = NewsHTMLParser.parse(html)

    assert parsed["headline"] == "Fed Holds Interest Rates Steady"
    assert parsed["source"] == "Wall Street Journal"
    assert parsed["metadata"]["site_name"] == "Wall Street Journal"
    assert parsed["metadata"]["description"] == "Central bank maintains target range."
    assert parsed["metadata"]["author"] == "Jerome Powell Watch"
    assert parsed["metadata"]["published_time"] == "2026-10-10T14:00:00Z"


@pytest.mark.issue_6
def test_news_html_parser_empty_and_fallback_content() -> None:
    """Ensure parser gracefully handles empty inputs and fallback text."""
    empty_result = NewsHTMLParser.parse("")
    assert empty_result["headline"] == "Untitled Article"
    assert empty_result["content"] == ""
    assert empty_result["source"] == "web"

    # HTML without <p> tags should extract direct text
    no_p_html = (
        "<html><body><div>General market commentary line 1. Line 2 follows.</div></body></html>"
    )
    result = NewsHTMLParser.parse(no_p_html)
    assert "General market commentary line 1" in result["content"]


@pytest.mark.issue_6
def test_news_extractor_custom_session() -> None:
    """Ensure NewsExtractor accepts custom session and user agent."""
    custom_session = requests.Session()
    extractor = NewsExtractor(session=custom_session, user_agent="CustomAgent/2.0")

    assert extractor.session is custom_session
    assert extractor.session.headers["User-Agent"] == "CustomAgent/2.0"


@pytest.mark.issue_6
def test_news_extractor_extract_from_html() -> None:
    """Ensure extract_from_html returns typed NewsArticle."""
    html = """
    <html>
        <head>
            <title>Semiconductor Output Surges</title>
        </head>
        <body>
            <article>
                <p>Global chip manufacturers ramped up manufacturing output.</p>
            </article>
        </body>
    </html>
    """
    extractor = NewsExtractor()
    article = extractor.extract_from_html(
        html=html,
        source="TechNews",
        symbol="TSMC",
        url="https://technews.example/semis",
    )

    assert isinstance(article, NewsArticle)
    assert article.headline == "Semiconductor Output Surges"
    assert "Global chip manufacturers" in article.content
    assert article.source == "TechNews"
    assert article.symbol == "TSMC"
    assert article.url == "https://technews.example/semis"


@pytest.mark.issue_6
def test_news_extractor_extract_from_url_success() -> None:
    """Ensure extract_from_url sends GET request and extracts article."""
    fake_html = """
    <html>
        <head>
            <meta property="og:title" content="EV Market Expands Globally" />
            <meta property="og:site_name" content="CleanEnergy Times" />
        </head>
        <body>
            <p>Electric vehicle adoption surged across European and Asian markets.</p>
        </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = fake_html

    with patch.object(requests.Session, "get", return_value=mock_response) as mock_get:
        extractor = NewsExtractor()
        article = extractor.extract_from_url(
            url="https://cleanenergytimes.com/articles/ev-surge",
            symbol="TSLA",
            timeout=5.0,
        )

        mock_get.assert_called_once_with(
            "https://cleanenergytimes.com/articles/ev-surge",
            timeout=5.0,
        )
        assert article.headline == "EV Market Expands Globally"
        assert article.source == "CleanEnergy Times"
        assert article.symbol == "TSLA"
        assert article.url == "https://cleanenergytimes.com/articles/ev-surge"


@pytest.mark.issue_6
def test_news_extractor_extract_from_url_http_error() -> None:
    """Ensure extract_from_url raises HTTPError when response is not 200."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Client Error")

    with patch.object(requests.Session, "get", return_value=mock_response):
        extractor = NewsExtractor()
        with pytest.raises(requests.HTTPError, match="404 Client Error"):
            extractor.extract_from_url("https://example.com/not-found")


@pytest.mark.issue_6
def test_news_extractor_extract_from_url_timeout() -> None:
    """Ensure extract_from_url propagates timeout errors."""
    with patch.object(
        requests.Session, "get", side_effect=requests.exceptions.Timeout("Timed out")
    ):
        extractor = NewsExtractor()
        with pytest.raises(requests.exceptions.Timeout, match="Timed out"):
            extractor.extract_from_url("https://example.com/slow-endpoint")


@pytest.mark.issue_6
def test_news_extractor_fetch_news_by_symbol() -> None:
    """Ensure fetch_news_by_symbol generates simulated articles adhering to limit."""
    extractor = NewsExtractor()

    # Limit = 3
    articles = extractor.fetch_news_by_symbol("MSFT", limit=3)
    assert len(articles) == 3
    for idx, art in enumerate(articles):
        assert isinstance(art, NewsArticle)
        assert art.symbol == "MSFT"
        assert "MSFT" in art.headline
        assert art.metadata.get("simulated") is True
        assert art.metadata.get("index") == idx
        assert art.url is not None

    # Limit larger than templates (caps at 5)
    all_articles = extractor.fetch_news_by_symbol("aapl", limit=10)
    assert len(all_articles) == 5
    assert all_articles[0].symbol == "AAPL"


@pytest.mark.issue_6
def test_to_research_artifact_conversion() -> None:
    """Ensure NewsArticle converts accurately to ResearchArtifact."""
    long_content = "Word " * 100  # 500 characters
    article = NewsArticle(
        headline="Major AI Acquisition Announced",
        content=long_content,
        source="TechCrunch",
        url="https://techcrunch.com/article/ai-acquisition",
        symbol="GOOGL",
        metadata={"category": "mergers"},
    )

    artifact = to_research_artifact(article, sentiment_score=0.85)

    assert isinstance(artifact, ResearchArtifact)
    assert artifact.headline == "Major AI Acquisition Announced"
    assert len(artifact.summary) <= 303  # 300 chars + "..."
    assert artifact.summary.endswith("...")
    assert artifact.sentiment_score == 0.85
    assert artifact.source == "TechCrunch"
    assert artifact.timestamp == article.published_at
    assert artifact.metadata["category"] == "mergers"
    assert artifact.metadata["url"] == "https://techcrunch.com/article/ai-acquisition"
    assert artifact.metadata["symbol"] == "GOOGL"


@pytest.mark.issue_6
def test_to_research_artifact_short_content() -> None:
    """Ensure short content is preserved without trailing ellipsis."""
    short_content = "Short news update."
    article = NewsArticle(
        headline="Brief Update",
        content=short_content,
        source="Reuters",
    )

    artifact = to_research_artifact(article, sentiment_score=-0.2)

    assert artifact.summary == "Short news update."
    assert artifact.sentiment_score == -0.2
    assert "url" not in artifact.metadata
    assert "symbol" not in artifact.metadata
