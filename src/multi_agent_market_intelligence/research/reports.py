"""Financial report loading, parsing, and state integration tools."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from multi_agent_market_intelligence.research.models import (
    FinancialReport,
    ReportType,
)
from multi_agent_market_intelligence.state.models import ResearchArtifact


class FinancialReportLoader:
    """Loader and parser for structured financial disclosures and SEC filings."""

    SUPPORTED_EXTENSIONS: set[str] = {".json", ".txt", ".md", ".html", ".htm"}

    def load_from_dict(self, data: dict[str, Any]) -> FinancialReport:
        """Parse and validate an in-memory dictionary into a FinancialReport.

        Args:
            data: Dictionary containing report attributes.

        Returns:
            Validated FinancialReport instance.
        """
        payload = dict(data)
        if "filing_date" in payload and isinstance(payload["filing_date"], str):
            payload["filing_date"] = datetime.fromisoformat(payload["filing_date"])
        return FinancialReport(**payload)

    def load_from_file(self, file_path: str | Path) -> FinancialReport:
        """Load and parse a financial report file based on its extension.

        Args:
            file_path: Path to the financial report file.

        Returns:
            Parsed FinancialReport instance.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file format is unsupported or invalid.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Financial report file not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format '{ext}' for financial report: {file_path}")

        inferred = self._infer_meta_from_filename(path)

        if ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"JSON report must contain a root object: {file_path}")
            for k, v in inferred.items():
                data.setdefault(k, v)
            return self.load_from_dict(data)

        if ext in {".txt", ".md"}:
            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            sections, header_meta, body_text = self._parse_text_report(raw_text)
            merged = {**inferred, **header_meta}
            fiscal_year = int(merged["fiscal_year"]) if "fiscal_year" in merged else None
            fiscal_quarter = int(merged["fiscal_quarter"]) if "fiscal_quarter" in merged else None
            return FinancialReport(
                symbol=merged.get("symbol", "UNKNOWN"),
                report_type=merged.get("report_type", ReportType.TEN_Q),
                period=merged.get("period", "UNKNOWN"),
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                content=body_text,
                sections=sections,
                source=merged.get("source", "local"),
                metadata=merged,
            )

        # ext in {".html", ".htm"}
        with open(path, "r", encoding="utf-8") as f:
            raw_html = f.read()
        parsed = self._parse_html_report(raw_html)
        return FinancialReport(
            symbol=inferred.get("symbol", "UNKNOWN"),
            report_type=inferred.get("report_type", ReportType.TEN_Q),
            period=inferred.get("period", "UNKNOWN"),
            content=parsed["content"],
            sections=parsed["sections"],
            source=inferred.get("source", "sec_edgar"),
            metadata=inferred,
        )

    def load_from_directory(
        self,
        directory_path: str | Path,
        symbol: str | None = None,
    ) -> list[FinancialReport]:
        """Scan directory and load all matching financial reports.

        Args:
            directory_path: Directory path containing report files.
            symbol: Optional ticker symbol filter.

        Returns:
            List of parsed FinancialReport instances.

        Raises:
            NotADirectoryError: If directory_path is not a valid directory.
        """
        dir_path = Path(directory_path)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Directory not found: {directory_path}")

        reports: list[FinancialReport] = []
        for file_path in sorted(dir_path.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                try:
                    report = self.load_from_file(file_path)
                    if symbol is None or report.symbol.upper() == symbol.upper():
                        reports.append(report)
                except Exception:
                    continue

        return reports

    def generate_mock_report(
        self,
        symbol: str,
        report_type: str = "10-Q",
        period: str = "2026-Q1",
    ) -> FinancialReport:
        """Generate a realistic mock financial filing offline for development and testing.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'MSFT').
            report_type: Report or filing type identifier.
            period: Reporting period identifier (e.g., '2026-Q1').

        Returns:
            Structured FinancialReport with populated MD&A and financial metrics.
        """
        sym = symbol.upper()
        fiscal_year: int | None = None
        fiscal_quarter: int | None = None
        if "-" in period:
            parts = period.split("-")
            if parts[0].isdigit():
                fiscal_year = int(parts[0])
            if len(parts) > 1 and parts[1].upper().startswith("Q") and parts[1][1:].isdigit():
                fiscal_quarter = int(parts[1][1:])

        sections = {
            "management_discussion": (
                f"Management's Discussion and Analysis of Financial Condition for {sym}. "
                "Total operating revenue increased by 14.2% year-over-year, driven by expanding "
                "enterprise customer adoption of high-performance cloud intelligence solutions. "
                "Operating margins expanded by 180 basis points as production efficiencies "
                "materialized across scalable platform deployments."
            ),
            "risk_factors": (
                f"Risk disclosures for {sym} encompass macroeconomic interest rate sensitivity, "
                "global supply chain fluctuations, potential cross-border regulatory changes, "
                "and heightened market competition across enterprise hardware and software "
                "segments."
            ),
            "financial_highlights": (
                f"Consolidated Operational Highlights for {sym} ({period}):\n"
                "- Net Revenue: $28,450 million (up 14.2% YoY)\n"
                "- Operating Income: $8,920 million (operating margin 31.3%)\n"
                "- Diluted EPS: $1.42 (compared to $1.22 in the prior period)\n"
                "- Free Cash Flow: $7,110 million (operating cash conversion 79.7%)"
            ),
            "guidance": (
                f"Forward guidance for {sym}: Management anticipates next quarter revenue "
                "growth in the range of 12% to 15%, with disciplined capital expenditure "
                "prioritizing core datacenter expansion and sustained cash returns."
            ),
        }

        content = "\n\n".join(f"=== {k.upper()} ===\n{v}" for k, v in sections.items())

        return FinancialReport(
            symbol=sym,
            report_type=report_type,
            period=period,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            content=content,
            sections=sections,
            filing_date=datetime.now(timezone.utc),
            source="sec_edgar",
            metadata={"simulated": True, "filing_format": "structured"},
        )

    @staticmethod
    def _infer_meta_from_filename(path: Path) -> dict[str, Any]:
        """Infer ticker symbol, report type, and period from standard filename patterns."""
        meta: dict[str, Any] = {}
        parts = path.stem.split("_")
        if len(parts) >= 1 and parts[0].isalpha():
            meta["symbol"] = parts[0].upper()
        if len(parts) >= 3:
            meta["report_type"] = parts[1]
            meta["period"] = parts[2]
        elif len(parts) == 2:
            meta["period"] = parts[1]
        return meta

    @staticmethod
    def _parse_text_report(content: str) -> tuple[dict[str, str], dict[str, Any], str]:
        """Parse plain text or markdown report into sections and metadata headers."""
        lines = content.splitlines()
        header_meta: dict[str, Any] = {}
        body_lines: list[str] = []
        in_header = True

        for line in lines:
            stripped = line.strip()
            if in_header and ":" in stripped and not stripped.startswith("#"):
                k, v = stripped.split(":", 1)
                key = k.strip().lower().replace("-", "_")
                if key in {
                    "symbol",
                    "period",
                    "report_type",
                    "fiscal_year",
                    "fiscal_quarter",
                    "source",
                }:
                    header_meta[key] = v.strip()
                    continue
            in_header = False
            body_lines.append(line)

        body_text = "\n".join(body_lines).strip()
        sections: dict[str, str] = {}
        current_sec = "overview"
        sec_lines: list[str] = []

        for line in body_lines:
            header_match = re.match(r"^(?:#{1,3}\s+|===+\s*)(.+?)(?:\s*===+)?$", line.strip())
            if header_match:
                if sec_lines and current_sec:
                    sections[current_sec] = "\n".join(sec_lines).strip()
                    sec_lines = []
                sec_title = header_match.group(1).strip()
                current_sec = re.sub(r"[^a-zA-Z0-9_]+", "_", sec_title.lower()).strip("_")
            else:
                sec_lines.append(line)

        if sec_lines and current_sec:
            sections[current_sec] = "\n".join(sec_lines).strip()

        return sections, header_meta, body_text

    @staticmethod
    def _parse_html_report(content: str) -> dict[str, Any]:
        """Extract content and sections from HTML filing, decomposing boilerplate."""
        soup = BeautifulSoup(content, "html.parser")
        for tag in ["script", "style", "nav", "header", "footer", "noscript"]:
            for el in soup.find_all(tag):
                el.decompose()

        sections: dict[str, str] = {}
        for sec_tag in soup.find_all(["section", "div"], attrs={"data-section": True}):
            sec_name = sec_tag.get("data-section")
            if sec_name:
                text = sec_tag.get_text(separator="\n", strip=True)
                if text:
                    sections[str(sec_name).lower()] = text

        if not sections:
            current_heading = "overview"
            accumulated: list[str] = []
            for child in (soup.body or soup).find_all(["h1", "h2", "h3", "p"]):
                if child.name in ["h1", "h2", "h3"]:
                    if accumulated and current_heading:
                        sections[current_heading] = "\n\n".join(accumulated)
                        accumulated = []
                    heading_text = child.get_text(strip=True).lower()
                    current_heading = re.sub(r"[^a-zA-Z0-9_]+", "_", heading_text).strip("_")
                elif child.name == "p":
                    p_text = child.get_text(strip=True)
                    if p_text:
                        accumulated.append(p_text)
            if accumulated and current_heading:
                sections[current_heading] = "\n\n".join(accumulated)

        full_text = (soup.body or soup).get_text(separator="\n\n", strip=True)
        return {"content": full_text, "sections": sections}


def report_to_research_artifact(
    report: FinancialReport,
    sentiment_score: float = 0.0,
) -> ResearchArtifact:
    """Convert an extracted FinancialReport into a standardized ResearchArtifact.

    Args:
        report: The parsed FinancialReport instance.
        sentiment_score: Numerical sentiment evaluation score.

    Returns:
        Structured ResearchArtifact adhering to the state protocol.
    """
    report_type_str = (
        report.report_type.value
        if isinstance(report.report_type, ReportType)
        else str(report.report_type)
    )
    headline = f"{report.symbol} {report_type_str} Financial Report ({report.period})"

    if "financial_highlights" in report.sections:
        summary_raw = report.sections["financial_highlights"]
    elif "management_discussion" in report.sections:
        summary_raw = report.sections["management_discussion"]
    else:
        summary_raw = report.content

    summary = summary_raw[:300] + "..." if len(summary_raw) > 300 else summary_raw

    metadata: dict[str, Any] = dict(report.metadata)
    metadata["symbol"] = report.symbol
    metadata["period"] = report.period
    metadata["report_type"] = report_type_str
    if report.fiscal_year is not None:
        metadata["fiscal_year"] = report.fiscal_year
    if report.fiscal_quarter is not None:
        metadata["fiscal_quarter"] = report.fiscal_quarter
    if report.sections:
        metadata["available_sections"] = list(report.sections.keys())

    return ResearchArtifact(
        headline=headline,
        summary=summary,
        sentiment_score=sentiment_score,
        source=report.source,
        timestamp=report.filing_date,
        metadata=metadata,
    )
