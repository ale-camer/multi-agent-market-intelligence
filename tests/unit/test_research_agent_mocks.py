"""Mock-based unit and edge-case tests for ResearchAgent intelligence extraction."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from multi_agent_market_intelligence.agents import AgentStatus, ResearchAgent
from multi_agent_market_intelligence.messaging import (
    AgentMessage,
    MessageBus,
    MessageType,
)
from multi_agent_market_intelligence.orchestrator import (
    MarketIntelligenceOrchestrator,
    create_initial_state,
)
from multi_agent_market_intelligence.research import (
    FinancialReport,
    FinancialReportLoader,
    NewsArticle,
    NewsExtractor,
    ReportType,
    SentimentLabel,
    create_research_node_handler,
)
from multi_agent_market_intelligence.state import create_market_state


@pytest.mark.issue_10
def test_research_agent_mock_http_network_errors() -> None:
    """Ensure NewsExtractor URL fetching handles 500, timeout, and connection aborts."""
    extractor = NewsExtractor()

    # 1. Mock HTTP 500 Internal Server Error
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

    with patch.object(requests.Session, "get", return_value=mock_500):
        with pytest.raises(requests.HTTPError, match="500 Server Error"):
            extractor.extract_from_url("https://news.example.com/item-1")

    # 2. Mock network timeout
    with patch.object(
        requests.Session, "get", side_effect=requests.exceptions.Timeout("Request timed out")
    ):
        with pytest.raises(requests.exceptions.Timeout, match="Request timed out"):
            extractor.extract_from_url("https://news.example.com/item-2")

    # 3. Mock connection error
    with patch.object(
        requests.Session,
        "get",
        side_effect=requests.exceptions.ConnectionError("Connection refused"),
    ):
        with pytest.raises(requests.exceptions.ConnectionError, match="Connection refused"):
            extractor.extract_from_url("https://news.example.com/item-3")


@pytest.mark.issue_10
def test_research_agent_mock_malformed_html() -> None:
    """Ensure parser safely handles broken tags, missing headings, and script payloads."""
    malformed_samples = [
        "<html><head><script>eval('evil()')</script></head><body>No content tags</body></html>",
        "<div><p>Unclosed paragraph <b>bold text without finish",
        "   \n\t  ",
        "<!DOCTYPE html><html><body><h1>Header Only</h1></body></html>",
    ]
    extractor = NewsExtractor()

    for raw_html in malformed_samples:
        article = extractor.extract_from_html(raw_html, source="test_source", symbol="AAPL")
        assert isinstance(article, NewsArticle)
        assert article.symbol == "AAPL"
        assert article.source == "test_source"
        assert isinstance(article.headline, str)
        assert len(article.headline) > 0


@pytest.mark.issue_10
def test_research_agent_bullish_consensus_scenario() -> None:
    """Ensure research agent produces high-conviction bullish synthesis on positive data."""
    mock_articles = [
        NewsArticle(
            headline="Quarterly Revenue Growth Surges Beyond Expectations",
            content="Customer adoption accelerated with significant margin expansion.",
            symbol="AAPL",
            source="Reuters",
        ),
        NewsArticle(
            headline="Analysts Upgrade Price Target Following Earnings Beat",
            content="Wall Street raised targets citing operating profit and dividend growth.",
            symbol="AAPL",
            source="Bloomberg",
        ),
    ]

    mock_report = FinancialReport(
        symbol="AAPL",
        report_type=ReportType.TEN_Q,
        period="2026-Q1",
        sections={
            "financial_highlights": (
                "Net revenue increased 18% with solid operating margin expansion."
            ),
            "guidance": "Management raised forward guidance anticipating continued acceleration.",
        },
    )

    mock_news_extractor = MagicMock(spec=NewsExtractor)
    mock_news_extractor.fetch_news_by_symbol.return_value = mock_articles

    mock_report_loader = MagicMock(spec=FinancialReportLoader)
    mock_report_loader.generate_mock_report.return_value = mock_report

    agent = ResearchAgent(
        news_extractor=mock_news_extractor,
        report_loader=mock_report_loader,
    )
    state = create_market_state(context={"symbol": "AAPL", "news_limit": 2})

    updates = agent.process(state)
    artifacts = updates["artifacts"]

    synthesis_list = [a for a in artifacts if a.metadata.get("is_synthesis") is True]
    assert len(synthesis_list) == 1
    synthesis = synthesis_list[0]

    assert synthesis.sentiment_score > 0.3
    assert synthesis.metadata["sentiment_label"] == SentimentLabel.BULLISH.value
    assert synthesis.metadata["confidence"] >= 0.5
    assert (
        "growth" in synthesis.metadata["key_drivers"]
        or "margin expansion" in synthesis.metadata["key_drivers"]
    )


@pytest.mark.issue_10
def test_research_agent_crisis_bearish_scenario() -> None:
    """Ensure research agent synthesizes high-conviction bearish output under crisis data."""
    mock_articles = [
        NewsArticle(
            headline="Severe Guidance Lowered Warning After Disappointing Quarter",
            content="Company reported substantial operating loss amidst rising debt default risks.",
            symbol="INTC",
            source="Financial Times",
        ),
        NewsArticle(
            headline="Agencies Downgrade Credit Rating Citing Litigation Headwinds",
            content="Analyst ratings downgraded following ongoing investigations and revenue drop.",
            symbol="INTC",
            source="WSJ",
        ),
    ]

    mock_report = FinancialReport(
        symbol="INTC",
        report_type=ReportType.TEN_Q,
        period="2026-Q1",
        sections={
            "financial_highlights": (
                "Operating losses widened to record levels with severe impairment."
            ),
            "risk_factors": (
                "Substantial litigation risks, declining demand, and supply bottleneck."
            ),
        },
    )

    mock_news_extractor = MagicMock(spec=NewsExtractor)
    mock_news_extractor.fetch_news_by_symbol.return_value = mock_articles

    mock_report_loader = MagicMock(spec=FinancialReportLoader)
    mock_report_loader.generate_mock_report.return_value = mock_report

    agent = ResearchAgent(
        news_extractor=mock_news_extractor,
        report_loader=mock_report_loader,
    )
    state = create_market_state(context={"symbol": "INTC", "news_limit": 2})

    updates = agent.process(state)
    artifacts = updates["artifacts"]

    synthesis_list = [a for a in artifacts if a.metadata.get("is_synthesis") is True]
    assert len(synthesis_list) == 1
    synthesis = synthesis_list[0]

    assert synthesis.sentiment_score < -0.3
    assert synthesis.metadata["sentiment_label"] == SentimentLabel.BEARISH.value
    assert synthesis.metadata["confidence"] >= 0.5
    assert (
        "guidance lowered" in synthesis.metadata["key_drivers"]
        or "losses" in synthesis.metadata["key_drivers"]
    )


@pytest.mark.issue_10
def test_research_agent_conflicting_signals_scenario() -> None:
    """Ensure agent produces balanced synthesis when news beats but report warns."""
    # Bullish news article
    mock_articles = [
        NewsArticle(
            headline="Strong Quarterly Beat Driven by Cloud Expansion",
            content="Revenue growth and operating momentum remained exceptionally robust.",
            symbol="MSFT",
            source="Bloomberg",
        )
    ]

    # Bearish risk & guidance report
    mock_report = FinancialReport(
        symbol="MSFT",
        report_type=ReportType.TEN_Q,
        period="2026-Q1",
        sections={
            "financial_highlights": (
                "Severe impairment charges recognized amidst regulatory scrutiny."
            ),
            "guidance": "Management warned of declining growth and lowered forward guidance.",
        },
    )

    mock_news_extractor = MagicMock(spec=NewsExtractor)
    mock_news_extractor.fetch_news_by_symbol.return_value = mock_articles

    mock_report_loader = MagicMock(spec=FinancialReportLoader)
    mock_report_loader.generate_mock_report.return_value = mock_report

    agent = ResearchAgent(
        news_extractor=mock_news_extractor,
        report_loader=mock_report_loader,
    )
    state = create_market_state(context={"symbol": "MSFT", "news_limit": 1})

    updates = agent.process(state)
    artifacts = updates["artifacts"]

    synthesis = [a for a in artifacts if a.metadata.get("is_synthesis") is True][0]

    # Conflicting signals should moderate the composite score between extremes
    assert -0.45 <= synthesis.sentiment_score <= 0.45
    drivers = synthesis.metadata["key_drivers"]
    assert len(drivers) >= 2


@pytest.mark.issue_10
def test_research_agent_mock_filings_directory(tmp_path: Path) -> None:
    """Ensure agent correctly parses dynamic directory containing JSON, TXT, and HTML files."""
    # 1. JSON report
    (tmp_path / "AAPL_10-Q_2026-Q1.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "period": "2026-Q1",
                "report_type": "10-Q",
                "content": "JSON filing content",
                "sections": {"financial_highlights": "Highlights from JSON"},
            }
        ),
        encoding="utf-8",
    )

    # 2. TXT report
    txt_content = (
        "Symbol: AAPL\nPeriod: 2025-FY\nReport-Type: 10-K\n\n"
        "## Management Discussion\nDiscussion from text filing."
    )
    (tmp_path / "AAPL_10-K_2025-FY.txt").write_text(txt_content, encoding="utf-8")

    # 3. HTML report
    html_content = """
    <html><body>
        <section data-section="financial_highlights">
            <h2>Highlights</h2><p>HTML filing operational data.</p>
        </section>
    </body></html>
    """
    (tmp_path / "AAPL_8-K_2026-03.html").write_text(html_content, encoding="utf-8")

    agent = ResearchAgent()
    state = create_market_state(
        context={
            "symbol": "AAPL",
            "reports_dir": str(tmp_path),
            "news_limit": 1,
        }
    )

    updates = agent.process(state)
    artifacts = updates["artifacts"]

    # 1 news + 3 directory reports + 1 synthesis = 5 artifacts
    assert len(artifacts) == 5

    report_artifacts = [
        a
        for a in artifacts
        if not a.metadata.get("is_synthesis") and a.source in ["sec_edgar", "local"]
    ]
    assert len(report_artifacts) == 3


@pytest.mark.issue_10
def test_research_agent_message_bus_delivery_with_correlation() -> None:
    """Ensure message bus delivers research report payload with matching correlation ID."""
    bus = MessageBus()
    inbox: list[AgentMessage] = []

    bus.subscribe("trading_analyst", lambda msg: inbox.append(msg))

    agent = ResearchAgent(message_bus=bus)
    state = create_market_state(
        context={
            "symbol": "NVDA",
            "news_limit": 1,
            "correlation_id": "corr-uuid-9999",
        }
    )

    agent.execute(state)

    assert len(inbox) == 1
    msg = inbox[0]
    assert msg.sender == "research_agent"
    assert msg.recipient == "trading_analyst"
    assert msg.message_type == MessageType.RESEARCH_REPORT
    assert msg.payload["symbol"] == "NVDA"
    assert "composite_score" in msg.payload
    assert "sentiment_label" in msg.payload


@pytest.mark.issue_10
def test_research_agent_orchestrator_multi_cycle_dag() -> None:
    """Ensure real ResearchAgent executes in LangGraph DAG across multiple sequential cycles."""
    agent = ResearchAgent()
    handler = create_research_node_handler(agent)

    orchestrator = MarketIntelligenceOrchestrator(research_handler=handler)
    orchestrator.compile()

    # Cycle 1: Analyze AAPL
    state1 = create_initial_state()
    state1["context"] = {"symbol": "AAPL", "news_limit": 1}
    result1 = orchestrator.run(state1)

    assert result1["current_step"] == "risk_manager"
    assert len(result1["artifacts"]) >= 3
    aapl_symbols = {a.metadata.get("symbol") for a in result1["artifacts"]}
    assert "AAPL" in aapl_symbols

    # Cycle 2: Analyze NVDA feeding state from Cycle 1
    state2 = dict(result1)
    state2["context"] = {"symbol": "NVDA", "news_limit": 1}
    result2 = orchestrator.run(state2)

    # State reducer append_artifacts must accumulate both AAPL and NVDA artifacts
    assert len(result2["artifacts"]) > len(result1["artifacts"])
    all_symbols = {a.metadata.get("symbol") for a in result2["artifacts"]}
    assert "AAPL" in all_symbols
    assert "NVDA" in all_symbols

    # Audit records must track both research execution runs
    research_records = [r for r in result2["records"] if r.agent_name == "research_agent"]
    assert len(research_records) == 2
    for r in research_records:
        assert r.status == "SUCCESS"


@pytest.mark.issue_10
@pytest.mark.anyio
async def test_research_agent_execute_async_flow() -> None:
    """Ensure async execution lifecycle operates smoothly and populates records."""
    agent = ResearchAgent()
    state = create_market_state(context={"symbol": "GOOGL", "news_limit": 1})

    result = await agent.execute_async(state)

    assert agent.status == AgentStatus.SUCCESS
    assert result["current_step"] == "research"
    assert len(result["artifacts"]) >= 3
    assert len(result["records"]) == 1
    assert result["records"][0].status == "SUCCESS"


@pytest.mark.issue_10
def test_research_agent_corrupt_and_empty_filings_resilience(tmp_path: Path) -> None:
    """Ensure agent gracefully falls back when directory has corrupt filings or empty paths."""
    # Corrupt JSON file
    (tmp_path / "corrupt.json").write_text("{this is not valid json", encoding="utf-8")
    # Empty non-existent subdirectory
    bad_dir = tmp_path / "non_existent_subdir"

    agent = ResearchAgent()
    state = create_market_state(
        context={
            "symbol": "TSLA",
            "reports_dir": str(bad_dir),
            "news_limit": 1,
        }
    )

    # Should not raise exception, falls back to simulated filing
    updates = agent.process(state)
    assert updates["current_step"] == "research"
    assert len(updates["artifacts"]) >= 3
