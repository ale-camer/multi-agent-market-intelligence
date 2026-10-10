"""Unit tests for financial sentiment analysis models, lexicon rules, and aggregation."""

import pytest

from multi_agent_market_intelligence.research import (
    FinancialReport,
    FinancialSentimentAnalyzer,
    NewsArticle,
    SentimentAnalysisResult,
    SentimentLabel,
)


@pytest.mark.issue_8
def test_sentiment_models_defaults_and_fields() -> None:
    """Ensure SentimentAnalysisResult validates ranges and allows dict comparison."""
    result = SentimentAnalysisResult(
        score=0.45,
        label=SentimentLabel.BULLISH,
        confidence=0.82,
        breakdown={"positive": 0.8, "negative": 0.1, "neutral": 0.1},
        key_drivers=["revenue growth", "beat"],
        metadata={"ticker": "NVDA"},
    )

    assert result.score == 0.45
    assert result.label == SentimentLabel.BULLISH
    assert result.confidence == 0.82
    assert "revenue growth" in result.key_drivers
    assert result == {
        "score": 0.45,
        "label": SentimentLabel.BULLISH,
        "confidence": 0.82,
    }
    assert result != {"score": -0.5}
    assert result != "invalid-type"


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_bullish_text() -> None:
    """Ensure analyzer identifies strongly bullish corporate performance statements."""
    text = (
        "The company reported record quarterly growth and beat Wall Street expectations. "
        "Operating momentum remained robust with solid margin expansion and dividend increases."
    )
    analyzer = FinancialSentimentAnalyzer()
    result = analyzer.analyze_text(text)

    assert result.score > 0.15
    assert result.label == SentimentLabel.BULLISH
    assert result.confidence > 0.5
    assert "growth" in result.key_drivers or "margin expansion" in result.key_drivers
    assert result.breakdown["positive"] > result.breakdown["negative"]


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_bearish_text() -> None:
    """Ensure analyzer identifies bearish indicators such as warnings, losses, and litigation."""
    text = (
        "Executive leadership issued a severe guidance lowered warning due to rising headwinds. "
        "The operating loss widened alongside active litigation and debt default risks."
    )
    analyzer = FinancialSentimentAnalyzer()
    result = analyzer.analyze_text(text)

    assert result.score < -0.15
    assert result.label == SentimentLabel.BEARISH
    assert result.confidence > 0.5
    assert "guidance lowered" in result.key_drivers or "headwinds" in result.key_drivers
    assert result.breakdown["negative"] > result.breakdown["positive"]


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_neutral_text() -> None:
    """Ensure non-financial descriptive text evaluates to neutral with low confidence."""
    text = "The committee held its scheduled quarterly administrative session on Tuesday morning."
    analyzer = FinancialSentimentAnalyzer()
    result = analyzer.analyze_text(text)

    assert result.label == SentimentLabel.NEUTRAL
    assert -0.15 <= result.score <= 0.15
    assert result.confidence == 0.0
    assert result.key_drivers == []


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_negation_inversion() -> None:
    """Ensure negation words invert positive sentiment into negative impact."""
    positive_text = "The division demonstrated revenue growth and strong operational expansion."
    negated_text = (
        "The division showed no revenue growth and failed to achieve operational expansion."
    )

    analyzer = FinancialSentimentAnalyzer()
    pos_res = analyzer.analyze_text(positive_text)
    neg_res = analyzer.analyze_text(negated_text)

    assert pos_res.score > 0.2
    assert pos_res.label == SentimentLabel.BULLISH
    assert neg_res.score < 0.0
    assert "not_expansion" in neg_res.key_drivers or neg_res.score < pos_res.score


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_intensifiers() -> None:
    """Ensure intensifiers amplify scores while dampeners moderate them."""
    base_text = "The company reported strong gains and profit."
    boosted_text = "The company reported exceptionally strong gains and profit."
    dampened_text = "The company reported marginally strong gains and profit."

    analyzer = FinancialSentimentAnalyzer()
    base_res = analyzer.analyze_text(base_text)
    boosted_res = analyzer.analyze_text(boosted_text)
    dampened_res = analyzer.analyze_text(dampened_text)

    assert boosted_res.score >= base_res.score
    assert dampened_res.score <= boosted_res.score


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_multiword_phrases() -> None:
    """Ensure multi-word financial phrases receive specific precedence and scoring."""
    phrase_text = (
        "Analysts observed price target raised after substantial operating margin expansion."
    )
    analyzer = FinancialSentimentAnalyzer()
    result = analyzer.analyze_text(phrase_text)

    assert result.score > 0.25
    assert (
        "operating margin expansion" in result.key_drivers
        or "margin expansion" in result.key_drivers
    )


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_empty_and_whitespace() -> None:
    """Ensure empty or whitespace strings return neutral results without errors."""
    analyzer = FinancialSentimentAnalyzer()

    res_empty = analyzer.analyze_text("")
    assert res_empty.score == 0.0
    assert res_empty.label == SentimentLabel.NEUTRAL
    assert res_empty.confidence == 0.0

    res_spaces = analyzer.analyze_text("     ")
    assert res_spaces.score == 0.0
    assert res_spaces.label == SentimentLabel.NEUTRAL


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_analyze_article() -> None:
    """Ensure analyze_article weights headline alongside article body."""
    article = NewsArticle(
        headline="Apple Beats Expectations with Record Cloud Revenue",
        content="Customer adoption increased strongly, delivering accelerated profit growth.",
        symbol="AAPL",
        source="Bloomberg",
    )
    analyzer = FinancialSentimentAnalyzer()
    result = analyzer.analyze_article(article)

    assert result.score > 0.2
    assert result.label == SentimentLabel.BULLISH
    assert result.metadata["symbol"] == "AAPL"
    assert result.metadata["source"] == "Bloomberg"
    assert "headline_score" in result.breakdown
    assert "content_score" in result.breakdown


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_analyze_report_sections() -> None:
    """Ensure analyze_report allows targeting specific sections like highlights vs risk factors."""
    report = FinancialReport(
        symbol="MSFT",
        period="2026-Q1",
        sections={
            "financial_highlights": "Net income rose 22% with record operating margin expansion.",
            "risk_factors": (
                "Litigation risks, cross-border regulatory scrutiny, and supply chain bottleneck "
                "adversely impact financial performance."
            ),
        },
    )
    analyzer = FinancialSentimentAnalyzer()

    # Target financial highlights: should be bullish
    high_res = analyzer.analyze_report(report, target_sections=["financial_highlights"])
    assert high_res.score > 0.15
    assert high_res.label == SentimentLabel.BULLISH

    # Target risk factors: should be bearish
    risk_res = analyzer.analyze_report(report, target_sections=["risk_factors"])
    assert risk_res.score < -0.15
    assert risk_res.label == SentimentLabel.BEARISH


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_aggregate_sentiment() -> None:
    """Ensure aggregate_sentiment combines multiple signals with confidence weighting."""
    res1 = SentimentAnalysisResult(
        score=0.6,
        label=SentimentLabel.BULLISH,
        confidence=0.8,
        key_drivers=["growth", "beat"],
    )
    res2 = SentimentAnalysisResult(
        score=0.4,
        label=SentimentLabel.BULLISH,
        confidence=0.7,
        key_drivers=["margin expansion"],
    )
    res3 = SentimentAnalysisResult(
        score=-0.1,
        label=SentimentLabel.NEUTRAL,
        confidence=0.2,
        key_drivers=["inflation"],
    )

    analyzer = FinancialSentimentAnalyzer()
    aggregated = analyzer.aggregate_sentiment([res1, res2, res3])

    assert aggregated.score > 0.3
    assert aggregated.label == SentimentLabel.BULLISH
    assert aggregated.confidence >= 0.5
    assert "growth" in aggregated.key_drivers
    assert aggregated.metadata["total_items"] == 3


@pytest.mark.issue_8
def test_financial_sentiment_analyzer_aggregate_empty() -> None:
    """Ensure aggregate_sentiment handles empty list cleanly."""
    analyzer = FinancialSentimentAnalyzer()
    empty_agg = analyzer.aggregate_sentiment([])

    assert empty_agg.score == 0.0
    assert empty_agg.label == SentimentLabel.NEUTRAL
    assert empty_agg.confidence == 0.0
    assert empty_agg.metadata["total_items"] == 0
