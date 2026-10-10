# Issue 6: News Extraction Tools

**Branch**: `feature/issue-6-news-extraction-tools`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #7)
**Milestone**: M2 - Research Agent Implementation

## Objective
Develop structured news extraction and parsing tools for the Research Agent. This includes a typed `NewsArticle` model, a BeautifulSoup-based HTML article content extractor with boilerplate removal, a configurable `NewsExtractor` client supporting web URLs, raw HTML, and simulated symbol-based feeds, and adapter functions to convert extracted news into `ResearchArtifact`s.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/research/models.py` defines `NewsArticle` Pydantic model with `headline`, `content`, `source`, `url`, `published_at`, `symbol`, and `metadata`.
- [x] `src/multi_agent_market_intelligence/research/parser.py` implements `NewsHTMLParser` leveraging BeautifulSoup to clean HTML boilerplate (scripts, styles, navigation), extract title/headline (`h1`, `title`, `og:title`), main text body, and publishing metadata.
- [x] `src/multi_agent_market_intelligence/research/news.py` implements `NewsExtractor`:
  - `extract_from_html(html: str, source: str = "web", symbol: str | None = None) -> NewsArticle`.
  - `extract_from_url(url: str, symbol: str | None = None, timeout: float = 10.0) -> NewsArticle` with proper User-Agent headers, timeout handling, and network error isolation.
  - `fetch_news_by_symbol(symbol: str, limit: int = 5) -> list[NewsArticle]` supporting offline simulated data and custom news providers.
  - `to_research_artifact(article: NewsArticle, sentiment_score: float = 0.0) -> ResearchArtifact`.
- [x] `src/multi_agent_market_intelligence/research/__init__.py` exposes all public news extraction models and tools.
- [x] Unit tests in `tests/unit/test_news_extractor.py` marked with `@pytest.mark.issue_6` validating model fields, HTML parsing, boilerplate stripping, HTTP error handling, mock feed generation, and artifact conversion.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=6` pass cleanly.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=6 NAME=news-extraction-tools
```

### 2. News Article Domain Model
- **File**: `src/multi_agent_market_intelligence/research/models.py`
- **Change**: Define `NewsArticle(BaseModel)` with attributes:
  - `headline: str`
  - `content: str`
  - `source: str = "web"`
  - `url: str | None = None`
  - `published_at: datetime` (timezone-aware default UTC)
  - `symbol: str | None = None`
  - `metadata: dict[str, Any]`

### 3. HTML Cleaning & Article Parser
- **File**: `src/multi_agent_market_intelligence/research/parser.py`
- **Change**: Implement `NewsHTMLParser`:
  - Strips non-content tags (`<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, `<aside>`).
  - Resolves headlines from `og:title`, `meta[name="title"]`, `<h1>`, or `<title>`.
  - Extracts clean text body from `<article>` or `<p>` paragraphs.
  - Resolves author or publisher metadata from OpenGraph / meta tags.

### 4. News Extractor Tool
- **File**: `src/multi_agent_market_intelligence/research/news.py`
- **Change**: Implement `NewsExtractor`:
  - `extract_from_html(html, source, symbol) -> NewsArticle`.
  - `extract_from_url(url, symbol, timeout) -> NewsArticle` (uses `requests.Session` with custom headers, catching connection/HTTP errors and returning a fallback record or raising informative exceptions).
  - `fetch_news_by_symbol(symbol, limit) -> list[NewsArticle]` with built-in realistic mock news generator for offline tests.
  - Helper `to_research_artifact(article, sentiment_score) -> ResearchArtifact`.

### 5. Package Exports
- **File**: `src/multi_agent_market_intelligence/research/__init__.py`
- **Change**: Export `NewsArticle`, `NewsHTMLParser`, `NewsExtractor`, and `to_research_artifact`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `NewsArticle` and `NewsExtractor`.

### 6. Unit Testing
- **File**: `tests/unit/test_news_extractor.py`
- **Change**: Implement comprehensive unit tests tagged with `@pytest.mark.issue_6`:
  - Model validation and default timestamp creation.
  - HTML parser extracting headline, clean body, and removing scripts/styles.
  - OpenGraph metadata parsing (`og:title`, `og:site_name`).
  - Malformed HTML handling.
  - URL fetching with mocked HTTP responses (200 OK, 404 Not Found, Timeout).
  - Symbol-based news generation with limit constraints.
  - Conversion from `NewsArticle` to `ResearchArtifact`.

### 7. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=6
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=6 MSG="feat(research): implement news extraction models and parser tools"
```

## Decisions
- **BeautifulSoup with HTML Boilerplate Stripping**: Use `BeautifulSoup(html, "html.parser")` and actively decompose non-content tags (`script`, `style`, `nav`, `footer`) to provide clean, concise article text for downstream sentiment analysis without hallucination-inducing HTML noise.
- **Offline Mock Provider Built-in**: Provide deterministic, offline symbol-based news generation inside `NewsExtractor` so that testing and development workflows never depend on external paid news API rate limits.
- **Direct Bridge to ResearchArtifact**: Implement `to_research_artifact()` to ensure news articles seamlessly convert into the established Milestone 1 state protocol (`ResearchArtifact`).
