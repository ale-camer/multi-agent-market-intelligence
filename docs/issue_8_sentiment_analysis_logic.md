# Issue 8: Sentiment Analysis Logic

**Branch**: `feature/issue-8-sentiment-analysis-logic`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #9)
**Milestone**: M2 - Research Agent Implementation

## Objective
Implement specialized financial sentiment analysis logic for the Research Agent. This includes typed domain models (`SentimentLabel`, `SentimentAnalysisResult`), a financial-lexicon-based sentiment engine with domain terminology weighting, negation handling, and confidence scoring, section-aware report analysis, multi-source sentiment aggregation, and seamless enrichment of `NewsArticle`s and `FinancialReport`s into `ResearchArtifact`s.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/research/sentiment.py` defines:
  - `SentimentLabel(str, Enum)`: `BULLISH = "bullish"`, `BEARISH = "bearish"`, `NEUTRAL = "neutral"`.
  - `SentimentAnalysisResult(BaseModel)`: `score: float` in `[-1.0, 1.0]`, `label: SentimentLabel`, `confidence: float` in `[0.0, 1.0]`, `breakdown: dict[str, float]`, `key_drivers: list[str]`, `metadata: dict[str, Any]`.
  - `FinancialSentimentAnalyzer`:
    - `analyze_text(text: str) -> SentimentAnalysisResult`: evaluates text sentiment using financial domain terminology, accounting for negations and intensifiers.
    - `analyze_article(article: NewsArticle) -> SentimentAnalysisResult`: computes sentiment weighted by headline and article content.
    - `analyze_report(report: FinancialReport, target_sections: list[str] | None = None) -> SentimentAnalysisResult`: performs section-targeted analysis (e.g., MD&A, Financial Highlights vs. Risk Factors).
    - `aggregate_sentiment(results: list[SentimentAnalysisResult]) -> SentimentAnalysisResult`: computes confidence-weighted aggregate sentiment across multiple intelligence sources.
- [x] `src/multi_agent_market_intelligence/research/__init__.py` exposes `SentimentLabel`, `SentimentAnalysisResult`, and `FinancialSentimentAnalyzer`.
- [x] `src/multi_agent_market_intelligence/__init__.py` re-exports `SentimentLabel`, `SentimentAnalysisResult`, and `FinancialSentimentAnalyzer`.
- [x] Unit tests in `tests/unit/test_sentiment_analysis.py` marked with `@pytest.mark.issue_8` validating:
  - Directional scoring for bullish, bearish, and neutral text.
  - Negation detection ("not growing", "no profit", "never failed").
  - Intensifier scaling ("substantially increased", "modestly declined").
  - News article sentiment evaluation with headline weighting.
  - Financial report section-selective sentiment evaluation.
  - Multi-result confidence-weighted aggregation.
  - Empty text, punctuation-only, and edge-case handling.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=8` pass cleanly.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=8 NAME=sentiment-analysis-logic
```

### 2. Sentiment Domain Models
- **File**: `src/multi_agent_market_intelligence/research/sentiment.py`
- **Change**: Define `SentimentLabel(str, Enum)` and `SentimentAnalysisResult(BaseModel)`:
  - `score: float` (-1.0 to 1.0)
  - `label: SentimentLabel`
  - `confidence: float` (0.0 to 1.0)
  - `breakdown: dict[str, float]`
  - `key_drivers: list[str]`
  - `metadata: dict[str, Any]`

### 3. Financial Sentiment Analyzer Engine
- **File**: `src/multi_agent_market_intelligence/research/sentiment.py`
- **Change**: Implement `FinancialSentimentAnalyzer`:
  - Financial lexicon dictionary inspired by Loughran-McDonald financial terminology (e.g., revenue growth, beat, margin expansion, headwinds, impairments, litigation, breach).
  - Negation handler checking pre-word contextual window (e.g., "not", "no", "never", "hardly", "failed to").
  - Intensifier modifier (e.g., "significantly", "strongly", "substantially").
  - Methods:
    - `analyze_text(text: str) -> SentimentAnalysisResult`
    - `analyze_article(article: NewsArticle) -> SentimentAnalysisResult`
    - `analyze_report(report: FinancialReport, target_sections: list[str] | None = None) -> SentimentAnalysisResult`
    - `aggregate_sentiment(results: list[SentimentAnalysisResult]) -> SentimentAnalysisResult`

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/research/__init__.py`
- **Change**: Export `SentimentLabel`, `SentimentAnalysisResult`, and `FinancialSentimentAnalyzer`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `SentimentLabel`, `SentimentAnalysisResult`, and `FinancialSentimentAnalyzer`.

### 5. Unit Testing
- **File**: `tests/unit/test_sentiment_analysis.py`
- **Change**: Comprehensive unit tests tagged with `@pytest.mark.issue_8`:
  - Bullish / bearish / neutral lexicon scoring tests.
  - Negation and intensifier resolution tests.
  - News article sentiment with headline weighting.
  - Financial report section-targeted sentiment tests.
  - Confidence-weighted sentiment aggregation.
  - Empty, neutral, and malformed inputs.

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=8
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=8 MSG="feat(research): implement financial sentiment analysis logic and aggregation"
```

## Decisions
- **Domain-Specific Lexicon with Contextual Modifiers**: Financial text uses nuanced phrasing where standard consumer sentiment lexicons misclassify terms (e.g., "liability", "tax loss", "restructuring"). Using a tailored financial lexicon with negation and intensifier windows ensures deterministic, low-latency, and highly accurate scoring without mandatory cloud API tokens.
- **Confidence-Weighted Aggregation**: Individual signals vary in information density and certainty. Weighing scores by both confidence and text length allows multi-source synthesis (e.g., 3 news articles + 1 10-Q filing) to produce a balanced, representative composite score for the Research Agent.
- **Report Section Targeting**: Permitting section-selective analysis (e.g., analyzing MD&A and Guidance while isolating Risk Factors) ensures that boilerplate risk disclosures do not artificially skew an otherwise strongly performing corporate filing.
