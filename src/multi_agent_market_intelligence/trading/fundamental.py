"""Fundamental data loading, parsing, and financial metrics extraction engine."""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from multi_agent_market_intelligence.research.models import FinancialReport
from multi_agent_market_intelligence.trading.models import FundamentalMetrics


class FundamentalDataLoader:
    """Configurable loader and parser for corporate fundamental metrics."""

    def __init__(self, data_directory: str | Path | None = None) -> None:
        """Initialize the loader with an optional base data directory.

        Args:
            data_directory: Base filesystem path for metrics files.
        """
        self.data_directory = Path(data_directory) if data_directory is not None else None
        self._cache: dict[str, FundamentalMetrics] = {}

    def load_from_dict(self, data: dict[str, Any]) -> FundamentalMetrics:
        """Parse and validate an in-memory dictionary of fundamental indicators.

        Args:
            data: Raw dictionary containing corporate metrics.

        Returns:
            Validated FundamentalMetrics instance.

        Raises:
            ValueError: If symbol is missing or empty.
        """
        symbol = data.get("symbol")
        if not symbol or not str(symbol).strip():
            raise ValueError("Fundamental metrics record must contain a non-empty 'symbol'")

        normalized = {str(k).lower(): v for k, v in data.items()}
        normalized["symbol"] = str(symbol).upper().strip()

        # Clean numeric fields if strings were provided
        for key, val in list(normalized.items()):
            if key not in {"symbol", "source", "fiscal_period", "timestamp", "metadata"}:
                if val is not None and isinstance(val, (int, float, str)):
                    try:
                        normalized[key] = float(val)
                    except (ValueError, TypeError):
                        normalized[key] = None

        return FundamentalMetrics.model_validate(normalized)

    def load_from_file(self, file_path: str | Path) -> FundamentalMetrics:
        """Load fundamental metrics from a JSON or CSV file.

        Args:
            file_path: Filesystem path to the metrics file.

        Returns:
            Validated FundamentalMetrics instance.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file extension or content is unsupported.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Fundamental metrics file not found: {path}")

        ext = path.suffix.lower()
        if ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                content = json.load(f)
            if not isinstance(content, dict):
                raise ValueError(f"JSON metrics file must contain an object, got {type(content)}")
            return self.load_from_dict(content)

        elif ext == ".csv":
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [row for row in reader if row and any(cell.strip() for cell in row)]

            if not rows:
                raise ValueError(f"CSV file is empty: {path}")

            # Check if key-value vertical layout (2 columns) or row-based table layout
            first_row = [c.strip() for c in rows[0]]
            if len(first_row) == 2 and first_row[0].lower() in {"metric", "key", "field"}:
                data_dict: dict[str, Any] = {}
                for row in rows[1:]:
                    if len(row) >= 2:
                        k, v = row[0].strip().lower(), row[1].strip()
                        data_dict[k] = v
                return self.load_from_dict(data_dict)
            else:
                # Row-based CSV
                header = [c.strip().lower() for c in first_row]
                if len(rows) < 2:
                    raise ValueError(f"CSV table contains headers but no data row: {path}")
                data_row = [c.strip() for c in rows[1]]
                data_dict = dict(zip(header, data_row, strict=False))
                return self.load_from_dict(data_dict)

        else:
            raise ValueError(f"Unsupported fundamental metrics file format: {ext}")

    def load_from_directory(
        self,
        directory_path: str | Path,
        symbol: str | None = None,
    ) -> list[FundamentalMetrics]:
        """Batch load all fundamental metric files (.json, .csv) from a directory.

        Args:
            directory_path: Directory path to scan.
            symbol: Optional ticker symbol to filter records.

        Returns:
            List of parsed FundamentalMetrics objects.
        """
        dir_path = Path(directory_path)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        metrics_list: list[FundamentalMetrics] = []
        for file in sorted(dir_path.iterdir()):
            if file.suffix.lower() in {".json", ".csv"}:
                try:
                    metrics = self.load_from_file(file)
                    if symbol is None or metrics.symbol.upper() == symbol.upper().strip():
                        metrics_list.append(metrics)
                except Exception:
                    continue

        return metrics_list

    def load_from_financial_report(self, report: FinancialReport) -> FundamentalMetrics:
        """Extract fundamental metrics directly from a structured FinancialReport.

        Args:
            report: Domain FinancialReport instance.

        Returns:
            FundamentalMetrics enriched with filing highlights and operational metrics.
        """
        sym = report.symbol.upper().strip()
        data: dict[str, Any] = {
            "symbol": sym,
            "timestamp": report.filing_date,
            "fiscal_period": report.period,
            "source": f"financial_report:{report.report_type}",
            "metadata": {"report_source": report.source},
        }

        # Check existing metadata for explicit metrics
        if "fundamentals" in report.metadata and isinstance(report.metadata["fundamentals"], dict):
            data.update(report.metadata["fundamentals"])
        elif "metrics" in report.metadata and isinstance(report.metadata["metrics"], dict):
            data.update(report.metadata["metrics"])

        # Extract operational highlights from sections if present
        highlights = report.sections.get("financial_highlights", "") or report.content
        if highlights:
            # Regex extraction for standard patterns
            margin_match = re.search(
                r"operating margin[^\d\n\r]{0,20}?([0-9.]+)%", highlights, re.IGNORECASE
            )
            if margin_match and "operating_margin" not in data:
                data["operating_margin"] = float(margin_match.group(1)) / 100.0

            rev_growth = re.search(
                r"(?:up|increased by|growth of)\s+([0-9.]+)%\s*(?:yoy|year-over-year)?",
                highlights,
                re.IGNORECASE,
            )
            if rev_growth and "revenue_growth_yoy" not in data:
                data["revenue_growth_yoy"] = float(rev_growth.group(1)) / 100.0

            eps_match = re.search(
                r"(?:diluted\s+)?eps[^\d\n\r]{0,20}?\$\s*([0-9.]+)", highlights, re.IGNORECASE
            )
            if eps_match:
                data["metadata"]["eps"] = float(eps_match.group(1))

            fcf_match = re.search(
                r"free cash flow[^\d\n\r]{0,20}?\$\s*([0-9,]+)", highlights, re.IGNORECASE
            )
            if fcf_match:
                raw_fcf = fcf_match.group(1).replace(",", "")
                data["free_cash_flow"] = float(raw_fcf)

        return self.load_from_dict(data)

    def fetch_fundamentals(self, symbol: str) -> FundamentalMetrics:
        """Resolve fundamental metrics for a symbol from local storage, cache, or mock data.

        Args:
            symbol: Ticker symbol.

        Returns:
            FundamentalMetrics record.
        """
        sym = symbol.upper().strip()
        if sym in self._cache:
            return self._cache[sym]

        if self.data_directory and self.data_directory.is_dir():
            matches = self.load_from_directory(self.data_directory, symbol=sym)
            if matches:
                self._cache[sym] = matches[0]
                return matches[0]

        mock_data = self.generate_mock_fundamentals(symbol=sym, profile="neutral")
        self._cache[sym] = mock_data
        return mock_data

    @staticmethod
    def generate_mock_fundamentals(
        symbol: str = "AAPL",
        profile: str = "strong",
        seed: int | None = 42,
    ) -> FundamentalMetrics:
        """Produce deterministic mock fundamental metrics for offline testing.

        Profiles:
            - 'strong': High margins, low debt, consistent growth (undervalued/compounder).
            - 'growth': Rapid revenue growth, higher P/E, moderate margins.
            - 'distressed': High debt/equity, negative margins, declining revenues.
            - 'neutral': Market average baseline metrics.

        Args:
            symbol: Ticker symbol.
            profile: Archetype name ('strong', 'growth', 'distressed', 'neutral').
            seed: Random seed for small deterministic variance.

        Returns:
            Populated FundamentalMetrics object.
        """
        rng = np.random.default_rng(seed)
        noise = float(rng.normal(0, 0.02))
        sym = symbol.upper().strip()

        if profile == "strong":
            return FundamentalMetrics(
                symbol=sym,
                timestamp=datetime.now(timezone.utc),
                pe_ratio=round(18.5 + noise * 10, 2),
                pb_ratio=round(3.8 + noise, 2),
                ps_ratio=4.5,
                ev_ebitda=12.0,
                gross_margin=round(0.45 + noise, 3),
                operating_margin=round(0.28 + noise, 3),
                net_margin=round(0.22 + noise, 3),
                roe=round(0.32 + noise, 3),
                roa=round(0.14 + noise, 3),
                debt_to_equity=round(0.55 + abs(noise), 2),
                current_ratio=round(1.85 + noise, 2),
                quick_ratio=round(1.50 + noise, 2),
                interest_coverage=18.5,
                free_cash_flow=25_000_000_000.0,
                revenue_growth_yoy=round(0.14 + noise, 3),
                net_income_growth_yoy=round(0.16 + noise, 3),
                eps_growth_yoy=round(0.18 + noise, 3),
                dividend_yield=0.015,
                fiscal_period="2026-FY",
                source="mock:strong",
                metadata={"profile": "strong"},
            )

        elif profile == "growth":
            return FundamentalMetrics(
                symbol=sym,
                timestamp=datetime.now(timezone.utc),
                pe_ratio=round(42.0 + noise * 20, 2),
                pb_ratio=round(8.5 + noise, 2),
                ps_ratio=9.2,
                ev_ebitda=26.0,
                gross_margin=round(0.62 + noise, 3),
                operating_margin=round(0.18 + noise, 3),
                net_margin=round(0.14 + noise, 3),
                roe=round(0.19 + noise, 3),
                roa=round(0.09 + noise, 3),
                debt_to_equity=round(0.35 + abs(noise), 2),
                current_ratio=round(2.40 + noise, 2),
                quick_ratio=round(2.10 + noise, 2),
                interest_coverage=12.0,
                free_cash_flow=8_500_000_000.0,
                revenue_growth_yoy=round(0.28 + noise, 3),
                net_income_growth_yoy=round(0.32 + noise, 3),
                eps_growth_yoy=round(0.35 + noise, 3),
                dividend_yield=0.0,
                fiscal_period="2026-FY",
                source="mock:growth",
                metadata={"profile": "growth"},
            )

        elif profile == "distressed":
            return FundamentalMetrics(
                symbol=sym,
                timestamp=datetime.now(timezone.utc),
                pe_ratio=None,  # Unprofitable
                pb_ratio=round(0.75 + noise, 2),
                ps_ratio=0.6,
                ev_ebitda=None,
                gross_margin=round(0.15 + noise, 3),
                operating_margin=round(-0.08 + noise, 3),
                net_margin=round(-0.16 + noise, 3),
                roe=round(-0.25 + noise, 3),
                roa=round(-0.11 + noise, 3),
                debt_to_equity=round(3.80 + abs(noise), 2),
                current_ratio=round(0.72 + noise, 2),
                quick_ratio=round(0.48 + noise, 2),
                interest_coverage=0.8,
                free_cash_flow=-2_500_000_000.0,
                revenue_growth_yoy=round(-0.11 + noise, 3),
                net_income_growth_yoy=round(-0.24 + noise, 3),
                eps_growth_yoy=round(-0.30 + noise, 3),
                dividend_yield=0.0,
                fiscal_period="2026-FY",
                source="mock:distressed",
                metadata={"profile": "distressed"},
            )

        else:  # neutral
            return FundamentalMetrics(
                symbol=sym,
                timestamp=datetime.now(timezone.utc),
                pe_ratio=round(22.0 + noise * 5, 2),
                pb_ratio=round(2.6 + noise, 2),
                ps_ratio=2.2,
                ev_ebitda=11.5,
                gross_margin=round(0.32 + noise, 3),
                operating_margin=round(0.12 + noise, 3),
                net_margin=round(0.08 + noise, 3),
                roe=round(0.12 + noise, 3),
                roa=round(0.06 + noise, 3),
                debt_to_equity=round(1.15 + abs(noise), 2),
                current_ratio=round(1.35 + noise, 2),
                quick_ratio=round(1.05 + noise, 2),
                interest_coverage=6.5,
                free_cash_flow=4_200_000_000.0,
                revenue_growth_yoy=round(0.04 + noise, 3),
                net_income_growth_yoy=round(0.05 + noise, 3),
                eps_growth_yoy=round(0.05 + noise, 3),
                dividend_yield=0.022,
                fiscal_period="2026-FY",
                source="mock:neutral",
                metadata={"profile": "neutral"},
            )
