# Issue 12: Fundamental Data Loader

**Branch**: `feature/issue-12-fundamental-data-loader`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #13)
**Milestone**: M3 - Trading Analyst Implementation

## Objective
Implement structured fundamental data loading, parsing, and domain modeling for the Trading Analyst module. In conjunction with technical indicators (Issue 11), fundamental metrics—such as valuation ratios (P/E, P/B, P/S, EV/EBITDA), profitability margins (gross, operating, net, ROE, ROA), financial health/solvency (debt-to-equity, current ratio, interest coverage), and growth rates—provide the qualitative and structural backing required by the Trading Signal Generator (Issue 13). This module provides strongly-typed models (`FundamentalMetrics`), directory/file loaders (JSON, CSV), an adapter for SEC `FinancialReport` filings, deterministic mock profile generators, and composite health scoring.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/trading/models.py` defines `FundamentalMetrics(DomainStateModel)`:
  - `symbol: str`
  - `timestamp: datetime`
  - Valuation metrics: `pe_ratio: float | None`, `pb_ratio: float | None`, `ps_ratio: float | None`, `ev_ebitda: float | None`, `market_cap: float | None`, `enterprise_value: float | None`
  - Profitability metrics: `gross_margin: float | None`, `operating_margin: float | None`, `net_margin: float | None`, `roe: float | None`, `roa: float | None`
  - Balance sheet & Solvency: `debt_to_equity: float | None`, `current_ratio: float | None`, `quick_ratio: float | None`, `interest_coverage: float | None`, `free_cash_flow: float | None`
  - Growth & Dividends: `revenue_growth_yoy: float | None`, `net_income_growth_yoy: float | None`, `eps_growth_yoy: float | None`, `dividend_yield: float | None`
  - Metadata: `fiscal_period: str | None`, `source: str = "mock"`, `metadata: dict[str, Any]`
  - Methods:
    - `is_undervalued(benchmark_pe: float = 25.0) -> bool`
    - `is_profitable() -> bool`
    - `has_healthy_balance_sheet(max_debt_to_equity: float = 2.0, min_current_ratio: float = 1.0) -> bool`
    - `fundamental_score() -> float` (composite score in range $[0.0, 1.0]$)
    - `to_dict() -> dict[str, Any]`
- [x] `src/multi_agent_market_intelligence/trading/fundamental.py` implements `FundamentalDataLoader`:
  - `load_from_dict(data: dict[str, Any]) -> FundamentalMetrics`: validates and normalizes in-memory dictionary.
  - `load_from_file(file_path: str | Path) -> FundamentalMetrics`: loads from JSON or CSV file.
  - `load_from_directory(directory_path: str | Path, symbol: str | None = None) -> list[FundamentalMetrics]`: batch loads files from a directory, optionally filtered by symbol.
  - `load_from_financial_report(report: FinancialReport) -> FundamentalMetrics`: extracts fundamental metrics from an SEC financial filing.
  - `fetch_fundamentals(symbol: str) -> FundamentalMetrics`: resolves metrics for a symbol, with fallback to mock data.
  - `generate_mock_fundamentals(symbol: str = "AAPL", profile: str = "strong", seed: int | None = 42) -> FundamentalMetrics`: produces deterministic fundamental profiles (`"strong"`, `"growth"`, `"distressed"`, `"neutral"`).
- [x] `src/multi_agent_market_intelligence/trading/__init__.py` and `src/multi_agent_market_intelligence/__init__.py` export `FundamentalMetrics` and `FundamentalDataLoader`.
- [x] Unit tests in `tests/unit/test_fundamental_loader.py` tagged with `@pytest.mark.issue_12` covering:
  - Model attributes, dict equality, default field handling.
  - JSON and CSV file ingestion and parsing.
  - Directory traversal with ticker filtering.
  - `FinancialReport` adapter integration.
  - Deterministic mock generation across all archetypes (`strong`, `growth`, `distressed`, `neutral`).
  - Helper methods (`is_undervalued`, `is_profitable`, `has_healthy_balance_sheet`, `fundamental_score`).
  - Error isolation: missing files, invalid file extensions, corrupt payloads.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=12` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=12 NAME=fundamental-data-loader
```

### 2. Fundamental Domain Models
- **File**: `src/multi_agent_market_intelligence/trading/models.py`
- **Change**: Define `FundamentalMetrics(DomainStateModel)`:
  - Valuation, profitability, liquidity/solvency, and growth attributes.
  - Evaluation helper methods (`is_undervalued`, `is_profitable`, `has_healthy_balance_sheet`, `fundamental_score`).
  - Pydantic serialization and dict comparison methods.

### 3. Fundamental Data Loader Engine
- **File**: `src/multi_agent_market_intelligence/trading/fundamental.py`
- **Change**: Implement `FundamentalDataLoader`:
  - `load_from_dict(data) -> FundamentalMetrics`
  - `load_from_file(file_path) -> FundamentalMetrics` (auto-detects `.json` and `.csv`)
  - `load_from_directory(directory_path, symbol) -> list[FundamentalMetrics]`
  - `load_from_financial_report(report: FinancialReport) -> FundamentalMetrics`
  - `fetch_fundamentals(symbol) -> FundamentalMetrics`
  - `generate_mock_fundamentals(symbol, profile, seed) -> FundamentalMetrics` supporting standard profiles.

### 4. Package Exports
- **File**: `src/multi_agent_market_intelligence/trading/__init__.py`
- **Change**: Export `FundamentalMetrics`, `FundamentalDataLoader`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `FundamentalMetrics` and `FundamentalDataLoader`.

### 5. Unit Testing
- **File**: `tests/unit/test_fundamental_loader.py`
- **Change**: Implement comprehensive test suite tagged with `@pytest.mark.issue_12`:
  - `test_fundamental_metrics_model_validation_and_dict_equality`
  - `test_load_from_dict_normalization`
  - `test_load_from_json_file`
  - `test_load_from_csv_file`
  - `test_load_from_directory_with_symbol_filter`
  - `test_load_from_financial_report_integration`
  - `test_generate_mock_fundamentals_archetypes`
  - `test_fundamental_ratios_helper_methods`
  - `test_fundamental_score_bounds_and_ranking`
  - `test_error_handling_invalid_files_and_missing_keys`

### 6. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=12
make test
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=12 MSG="feat(trading): implement fundamental data loader and metrics models"
```

## Decisions
- **Nullable Metric Fields for Non-Standard Companies**: All ratio and margin fields default to `None` rather than `0.0`. This properly represents early-stage startups without revenue, unprofitable companies without meaningful P/E ratios, or financial firms with non-standard debt-to-equity structures without biasing calculations.
- **Composite Fundamental Score**: Implement a normalized scoring helper (`fundamental_score() -> float` in $[0.0, 1.0]$) weighting valuation, profitability, balance sheet stability, and growth. This provides an easily interpretable composite metric for the Trading Signal Generator (Issue 13).
- **Direct FinancialReport Ingestion**: Provide a dedicated adapter method `load_from_financial_report()` to directly extract financial highlights and operational numbers produced during Research Agent filing ingestion, seamlessly coupling Milestone 2 research intelligence into Milestone 3 analysis.
- **Deterministic Archetypes**: The mock generator implements distinct financial archetypes (`"strong"`, `"growth"`, `"distressed"`, `"neutral"`) to guarantee reproducible, realistic testing of trading strategies without external financial data API dependencies.
