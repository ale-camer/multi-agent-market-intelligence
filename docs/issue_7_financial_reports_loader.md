# Issue 7: Financial Reports Loader

**Branch**: `feature/issue-7-financial-reports-loader`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #8)
**Milestone**: M2 - Research Agent Implementation

## Objective
Develop structured financial reports loading and parsing tools for the Research Agent. This includes a typed `FinancialReport` domain model with support for standardized filing types (10-K, 10-Q, 8-K, earnings releases), section-based extraction (e.g. Management Discussion & Analysis, Risk Factors, Financial Statements), a configurable `FinancialReportLoader` capable of loading local files (JSON, TXT, HTML/EDGAR) and scanning directories, an offline mock report generator, and adapter functions to convert financial reports into `ResearchArtifact`s.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/research/models.py` defines `ReportType` enum and `FinancialReport` Pydantic model with `symbol`, `report_type`, `period`, `fiscal_year`, `fiscal_quarter`, `content`, `sections`, `filing_date`, `source`, `metadata`, and dict comparison support.
- [x] `src/multi_agent_market_intelligence/research/reports.py` implements `FinancialReportLoader`:
  - `load_from_dict(data: dict[str, Any]) -> FinancialReport`: parses and validates in-memory dictionary.
  - `load_from_file(file_path: str | Path) -> FinancialReport`: auto-detects format (JSON, TXT, HTML/HTM, MD) and extracts content, sections, and metadata.
  - `load_from_directory(directory_path: str | Path, symbol: str | None = None) -> list[FinancialReport]`: scans directory for supported report files, optionally filtered by symbol.
  - `generate_mock_report(symbol: str, report_type: str = "10-Q", period: str = "2026-Q1") -> FinancialReport`: produces realistic structured filings offline with Management Discussion & Analysis, Risk Factors, and Financial Highlights sections.
  - `report_to_research_artifact(report: FinancialReport, sentiment_score: float = 0.0) -> ResearchArtifact`: adapter creating standard state protocol research artifact.
- [x] `src/multi_agent_market_intelligence/research/__init__.py` exposes `FinancialReport`, `ReportType`, `FinancialReportLoader`, and `report_to_research_artifact`.
- [x] `src/multi_agent_market_intelligence/__init__.py` re-exports `FinancialReport`, `ReportType`, and `FinancialReportLoader`.
- [x] Unit tests in `tests/unit/test_financial_reports.py` marked with `@pytest.mark.issue_7` validating model fields, JSON/TXT/HTML file ingestion, section extraction, directory batch loading, symbol filtering, mock generation, and `ResearchArtifact` conversion.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=7` pass cleanly.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=7 NAME=financial-reports-loader
```

### 2. Financial Report Domain Model
- **File**: `src/multi_agent_market_intelligence/research/models.py`
- **Change**: Define `ReportType(str, Enum)`:
  - `TEN_K = "10-K"`
  - `TEN_Q = "10-Q"`
  - `EIGHT_K = "8-K"`
  - `EARNINGS_RELEASE = "earnings_release"`
  - `ANNUAL_REPORT = "annual_report"`
- **Change**: Define `FinancialReport(BaseModel)` with attributes:
  - `symbol: str`
  - `report_type: ReportType | str = ReportType.TEN_Q`
  - `period: str`
  - `fiscal_year: int | None = None`
  - `fiscal_quarter: int | None = None`
  - `content: str = ""`
  - `sections: dict[str, str] = Field(default_factory=dict)`
  - `filing_date: datetime` (timezone-aware default UTC)
  - `source: str = "sec_edgar"`
  - `metadata: dict[str, Any] = Field(default_factory=dict)`
  - `__eq__` allowing direct comparison against dictionaries.

### 3. Financial Report Loader & Parser
- **File**: `src/multi_agent_market_intelligence/research/reports.py`
- **Change**: Implement `FinancialReportLoader`:
  - `load_from_dict(data: dict[str, Any]) -> FinancialReport`: parses and validates in-memory dictionary.
  - `load_from_file(file_path: str | Path) -> FinancialReport`: detects format by extension (`.json`, `.txt`, `.html`, `.htm`, `.md`) and parses structured fields and sections.
  - `load_from_directory(directory_path: str | Path, symbol: str | None = None) -> list[FinancialReport]`: recursively traverses directory, parses supported files, and filters by ticker symbol if specified.
  - `generate_mock_report(symbol: str, report_type: str = "10-Q", period: str = "2026-Q1") -> FinancialReport`: returns deterministic, realistic mock report with MD&A, Risk Factors, and Financial Highlights sections.
  - Helper `report_to_research_artifact(report: FinancialReport, sentiment_score: float = 0.0) -> ResearchArtifact`.

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/research/__init__.py`
- **Change**: Export `FinancialReport`, `ReportType`, `FinancialReportLoader`, and `report_to_research_artifact`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `FinancialReport`, `ReportType`, and `FinancialReportLoader`.

### 5. Unit Testing
- **File**: `tests/unit/test_financial_reports.py`
- **Change**: Implement comprehensive unit tests tagged with `@pytest.mark.issue_7`:
  - Model field validation, enum support, defaults, and dict comparison.
  - Loading from JSON files with sections.
  - Loading from plain text files with section headers.
  - Loading from HTML/SEC filings with boilerplate decomposition.
  - Directory scanning and symbol filtering.
  - Error handling for nonexistent files and unsupported extensions.
  - Mock report generation across multiple symbols and periods.
  - Conversion from `FinancialReport` to `ResearchArtifact`.

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=7
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=7 MSG="feat(research): implement financial reports loader and parser tools"
```

## Decisions
- **Multi-Format Ingestion**: Financial reports in practice exist in varied formats (SEC EDGAR HTML, structured JSON vendor feeds, markdown/text analyst notes). Supporting JSON, TXT, and HTML locally ensures high versatility without adding heavy PDF dependencies.
- **Section-Aware Parsing**: Storing extracted report sections in `sections: dict[str, str]` (such as MD&A and Risk Factors) enables downstream sentiment and LLM agents in Issue 8 and 9 to analyze critical sections selectively rather than processing entire massive disclosures.
- **Offline Mock Generator**: Providing deterministic mock filings inside `FinancialReportLoader` guarantees tests and local simulations run reliably without network dependencies or SEC rate limiting.
