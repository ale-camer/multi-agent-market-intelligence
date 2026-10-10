"""Unit tests for financial report domain models, loader, and parser tools."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from multi_agent_market_intelligence.research import (
    FinancialReport,
    FinancialReportLoader,
    ReportType,
    report_to_research_artifact,
)
from multi_agent_market_intelligence.state.models import ResearchArtifact


@pytest.mark.issue_7
def test_financial_report_defaults_and_fields() -> None:
    """Ensure FinancialReport sets sensible defaults including UTC filing date."""
    report = FinancialReport(
        symbol="AAPL",
        period="2026-Q1",
        content="Quarterly performance overview...",
    )

    assert report.symbol == "AAPL"
    assert report.report_type == ReportType.TEN_Q
    assert report.period == "2026-Q1"
    assert report.content == "Quarterly performance overview..."
    assert report.sections == {}
    assert report.source == "sec_edgar"
    assert report.metadata == {}
    assert isinstance(report.filing_date, datetime)
    assert report.filing_date.tzinfo is not None


@pytest.mark.issue_7
def test_financial_report_custom_fields_and_extras() -> None:
    """Ensure FinancialReport supports custom attributes and extra fields."""
    filing_date = datetime(2026, 4, 15, 18, 30, tzinfo=timezone.utc)
    report = FinancialReport(
        symbol="MSFT",
        report_type=ReportType.TEN_K,
        period="2025-FY",
        fiscal_year=2025,
        fiscal_quarter=None,
        content="Annual report content...",
        sections={"mda": "Discussion", "risks": "Risk statements"},
        filing_date=filing_date,
        source="investor_relations",
        metadata={"auditor": "Deloitte"},
        accession_number="0001234567-26-000001",  # type: ignore[call-arg]
    )

    assert report.symbol == "MSFT"
    assert report.report_type == ReportType.TEN_K
    assert report.fiscal_year == 2025
    assert report.sections["mda"] == "Discussion"
    assert report.metadata["auditor"] == "Deloitte"
    assert getattr(report, "accession_number", None) == "0001234567-26-000001"


@pytest.mark.issue_7
def test_financial_report_dict_equality() -> None:
    """Ensure FinancialReport compares seamlessly with dictionary representations."""
    report = FinancialReport(
        symbol="GOOGL",
        period="2026-Q2",
        source="sec_edgar",
    )

    assert report == {
        "symbol": "GOOGL",
        "period": "2026-Q2",
        "source": "sec_edgar",
    }
    assert report != {"symbol": "OTHER"}
    assert report != "not-a-report"


@pytest.mark.issue_7
def test_financial_report_loader_load_from_dict() -> None:
    """Ensure load_from_dict parses in-memory dictionaries with ISO dates."""
    loader = FinancialReportLoader()
    raw = {
        "symbol": "NVDA",
        "report_type": "10-Q",
        "period": "2026-Q1",
        "content": "Data center acceleration drove record revenues.",
        "filing_date": "2026-05-20T21:00:00+00:00",
        "sections": {"mda": "High growth observed."},
    }

    report = loader.load_from_dict(raw)

    assert isinstance(report, FinancialReport)
    assert report.symbol == "NVDA"
    assert report.period == "2026-Q1"
    assert report.filing_date.year == 2026
    assert report.sections["mda"] == "High growth observed."


@pytest.mark.issue_7
def test_financial_report_loader_load_json_file(tmp_path: Path) -> None:
    """Ensure loader parses structured JSON files and extracts sections."""
    file_path = tmp_path / "AAPL_10-Q_2026-Q1.json"
    payload = {
        "symbol": "AAPL",
        "report_type": "10-Q",
        "period": "2026-Q1",
        "fiscal_year": 2026,
        "fiscal_quarter": 1,
        "content": "iPhone and Services growth...",
        "sections": {
            "financial_highlights": "Net sales rose 8%.",
            "risk_factors": "Currency fluctuations and supply chains.",
        },
        "metadata": {"form": "10-Q"},
    }
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    loader = FinancialReportLoader()
    report = loader.load_from_file(file_path)

    assert report.symbol == "AAPL"
    assert report.fiscal_year == 2026
    assert report.sections["financial_highlights"] == "Net sales rose 8%."
    assert report.metadata["form"] == "10-Q"


@pytest.mark.issue_7
def test_financial_report_loader_load_text_file_with_headers(tmp_path: Path) -> None:
    """Ensure loader parses text files with metadata headers and markdown sections."""
    file_path = tmp_path / "TSLA_2026-Q1.txt"
    text_content = """Symbol: TSLA
Period: 2026-Q1
Report-Type: 10-Q
Fiscal-Year: 2026
Fiscal-Quarter: 1

## Management Discussion
Automotive deliveries and energy storage deployments increased strongly.

## Risk Factors
Supply chain bottlenecks and raw material battery costs.
"""
    file_path.write_text(text_content, encoding="utf-8")

    loader = FinancialReportLoader()
    report = loader.load_from_file(file_path)

    assert report.symbol == "TSLA"
    assert report.period == "2026-Q1"
    assert report.fiscal_year == 2026
    assert report.fiscal_quarter == 1
    assert "management_discussion" in report.sections
    assert "Automotive deliveries" in report.sections["management_discussion"]
    assert "risk_factors" in report.sections
    assert "battery costs" in report.sections["risk_factors"]


@pytest.mark.issue_7
def test_financial_report_loader_load_markdown_file(tmp_path: Path) -> None:
    """Ensure loader parses markdown (.md) reports."""
    file_path = tmp_path / "AMZN_10-K_2025-FY.md"
    md_content = """# AWS Cloud Infrastructure Review

### Overview
Enterprise cloud migration accelerated across global accounts.

### Financial Performance
AWS operating margins rose due to custom chip efficiencies.
"""
    file_path.write_text(md_content, encoding="utf-8")

    loader = FinancialReportLoader()
    report = loader.load_from_file(file_path)

    assert report.symbol == "AMZN"
    assert report.period == "2025-FY"
    assert "overview" in report.sections or "financial_performance" in report.sections
    assert "Enterprise cloud migration" in report.content


@pytest.mark.issue_7
def test_financial_report_loader_load_html_file(tmp_path: Path) -> None:
    """Ensure loader parses HTML filing, strips boilerplate, and captures sections."""
    file_path = tmp_path / "META_10-Q_2026-Q2.html"
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>META Form 10-Q Filing</title>
        <style>body { font-family: sans-serif; }</style>
        <script>console.log("SEC EDGAR tracker");</script>
    </head>
    <body>
        <nav><a href="#toc">Table of Contents</a></nav>
        <header><h1>Quarterly Report For The Period Ended June 30, 2026</h1></header>
        <section data-section="management_discussion">
            <h2>Item 2. Management's Discussion and Analysis</h2>
            <p>Ad impressions increased 18% year-over-year while average price per ad rose 6%.</p>
        </section>
        <section data-section="risk_factors">
            <h2>Item 1A. Risk Factors</h2>
            <p>Our advertising business is influenced by macroeconomic condition volatility.</p>
        </section>
        <footer><p>End of filing document</p></footer>
    </body>
    </html>
    """
    file_path.write_text(html_content, encoding="utf-8")

    loader = FinancialReportLoader()
    report = loader.load_from_file(file_path)

    assert report.symbol == "META"
    assert report.period == "2026-Q2"
    assert "SEC EDGAR tracker" not in report.content
    assert "Table of Contents" not in report.content
    assert "management_discussion" in report.sections
    assert "Ad impressions increased 18%" in report.sections["management_discussion"]
    assert "risk_factors" in report.sections


@pytest.mark.issue_7
def test_financial_report_loader_load_from_directory(tmp_path: Path) -> None:
    """Ensure load_from_directory scans files and supports symbol filtering."""
    sub_dir = tmp_path / "filings"
    sub_dir.mkdir()

    (sub_dir / "AAPL_10-Q_2026-Q1.json").write_text(
        json.dumps({"symbol": "AAPL", "period": "2026-Q1", "content": "Apple report"}),
        encoding="utf-8",
    )
    (sub_dir / "AAPL_10-K_2025-FY.txt").write_text(
        "Symbol: AAPL\nPeriod: 2025-FY\n\nContent here.",
        encoding="utf-8",
    )
    (sub_dir / "MSFT_10-Q_2026-Q1.json").write_text(
        json.dumps({"symbol": "MSFT", "period": "2026-Q1", "content": "Microsoft report"}),
        encoding="utf-8",
    )
    (sub_dir / "unsupported.pdf").write_text("PDF dummy", encoding="utf-8")

    loader = FinancialReportLoader()

    # Load all supported reports
    all_reports = loader.load_from_directory(sub_dir)
    assert len(all_reports) == 3

    # Filter by symbol
    aapl_reports = loader.load_from_directory(sub_dir, symbol="AAPL")
    assert len(aapl_reports) == 2
    for r in aapnl_reports if (aapnl_reports := aapl_reports) else []:
        assert r.symbol == "AAPL"

    msft_reports = loader.load_from_directory(sub_dir, symbol="msft")
    assert len(msft_reports) == 1
    assert msft_reports[0].symbol == "MSFT"


@pytest.mark.issue_7
def test_financial_report_loader_errors(tmp_path: Path) -> None:
    """Ensure proper exceptions are raised for invalid inputs."""
    loader = FinancialReportLoader()

    # Nonexistent file
    with pytest.raises(FileNotFoundError, match="Financial report file not found"):
        loader.load_from_file(tmp_path / "does_not_exist.json")

    # Nonexistent directory
    with pytest.raises(NotADirectoryError, match="Directory not found"):
        loader.load_from_directory(tmp_path / "nonexistent_dir")

    # Unsupported file extension
    unsupported_file = tmp_path / "report.xyz"
    unsupported_file.write_text("dummy", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file format"):
        loader.load_from_file(unsupported_file)

    # Malformed JSON root
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text('["not", "a", "dict"]', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON report must contain a root object"):
        loader.load_from_file(invalid_json)


@pytest.mark.issue_7
def test_financial_report_loader_generate_mock_report() -> None:
    """Ensure generate_mock_report produces realistic structured report offline."""
    loader = FinancialReportLoader()
    report = loader.generate_mock_report("NVDA", report_type="10-Q", period="2026-Q1")

    assert report.symbol == "NVDA"
    assert report.report_type == "10-Q"
    assert report.period == "2026-Q1"
    assert report.fiscal_year == 2026
    assert report.fiscal_quarter == 1
    assert "management_discussion" in report.sections
    assert "risk_factors" in report.sections
    assert "financial_highlights" in report.sections
    assert "guidance" in report.sections
    assert report.metadata.get("simulated") is True
    assert "Net Revenue" in report.content


@pytest.mark.issue_7
def test_report_to_research_artifact_conversion() -> None:
    """Ensure FinancialReport converts into a standardized ResearchArtifact."""
    loader = FinancialReportLoader()
    report = loader.generate_mock_report("AAPL", report_type="10-Q", period="2026-Q1")

    artifact = report_to_research_artifact(report, sentiment_score=0.65)

    assert isinstance(artifact, ResearchArtifact)
    assert artifact.headline == "AAPL 10-Q Financial Report (2026-Q1)"
    assert len(artifact.summary) <= 303
    assert artifact.sentiment_score == 0.65
    assert artifact.source == "sec_edgar"
    assert artifact.metadata["symbol"] == "AAPL"
    assert artifact.metadata["period"] == "2026-Q1"
    assert artifact.metadata["report_type"] == "10-Q"
    assert "financial_highlights" in artifact.metadata["available_sections"]


@pytest.mark.issue_7
def test_report_to_research_artifact_fallback_summary() -> None:
    """Ensure reports without standard sections use fallback content summary."""
    report = FinancialReport(
        symbol="ORCL",
        report_type="8-K",
        period="2026-Q1",
        content="Short 8-K disclosure announcement.",
    )

    artifact = report_to_research_artifact(report, sentiment_score=0.1)

    assert artifact.headline == "ORCL 8-K Financial Report (2026-Q1)"
    assert artifact.summary == "Short 8-K disclosure announcement."
    assert artifact.sentiment_score == 0.1
