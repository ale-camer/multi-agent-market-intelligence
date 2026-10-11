"""Unit tests for corporate fundamental metrics domain models and loader tools."""

import json
from pathlib import Path

import pytest

from multi_agent_market_intelligence.research.models import FinancialReport, ReportType
from multi_agent_market_intelligence.trading import (
    FundamentalDataLoader,
    FundamentalMetrics,
)


@pytest.mark.issue_12
def test_fundamental_metrics_model_validation_and_dict_equality() -> None:
    """Validate FundamentalMetrics field defaults, serialization, and dict equality."""
    metrics = FundamentalMetrics(
        symbol="AAPL",
        pe_ratio=28.5,
        pb_ratio=6.2,
        net_margin=0.25,
        debt_to_equity=1.1,
        current_ratio=1.4,
        revenue_growth_yoy=0.08,
        source="sec_edgar",
    )
    assert metrics.symbol == "AAPL"
    assert metrics.pe_ratio == 28.5
    assert metrics.timestamp is not None
    assert metrics == {
        "symbol": "AAPL",
        "pe_ratio": 28.5,
        "pb_ratio": 6.2,
        "net_margin": 0.25,
    }

    dumped = metrics.to_dict()
    assert dumped["symbol"] == "AAPL"
    assert dumped["pe_ratio"] == 28.5
    assert dumped["debt_to_equity"] == 1.1


@pytest.mark.issue_12
def test_load_from_dict_normalization() -> None:
    """Verify dictionary parsing with case normalization and string-to-float conversions."""
    loader = FundamentalDataLoader()
    raw = {
        "symbol": "msft",
        "PE_RATIO": "32.4",
        "NET_MARGIN": "0.34",
        "Debt_To_Equity": "0.45",
        "FISCAL_PERIOD": "2026-Q2",
    }
    metrics = loader.load_from_dict(raw)
    assert metrics.symbol == "MSFT"
    assert metrics.pe_ratio == pytest.approx(32.4)
    assert metrics.net_margin == pytest.approx(0.34)
    assert metrics.debt_to_equity == pytest.approx(0.45)
    assert metrics.fiscal_period == "2026-Q2"

    # Missing or empty symbol raises ValueError
    with pytest.raises(ValueError, match="non-empty 'symbol'"):
        loader.load_from_dict({"pe_ratio": 20.0})

    with pytest.raises(ValueError, match="non-empty 'symbol'"):
        loader.load_from_dict({"symbol": "   ", "pe_ratio": 20.0})


@pytest.mark.issue_12
def test_load_from_json_file(tmp_path: Path) -> None:
    """Verify loading fundamental metrics from a JSON file."""
    loader = FundamentalDataLoader()
    json_file = tmp_path / "aapl_fundamentals.json"
    data = {
        "symbol": "AAPL",
        "pe_ratio": 29.1,
        "gross_margin": 0.44,
        "operating_margin": 0.30,
        "current_ratio": 1.25,
        "source": "json_feed",
    }
    json_file.write_text(json.dumps(data), encoding="utf-8")

    metrics = loader.load_from_file(json_file)
    assert metrics.symbol == "AAPL"
    assert metrics.pe_ratio == pytest.approx(29.1)
    assert metrics.gross_margin == pytest.approx(0.44)
    assert metrics.source == "json_feed"

    # Invalid JSON structure (list instead of dict)
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")
    with pytest.raises(ValueError, match="must contain an object"):
        loader.load_from_file(invalid_json)


@pytest.mark.issue_12
def test_load_from_csv_file(tmp_path: Path) -> None:
    """Verify loading from row-based and key-value CSV formats."""
    loader = FundamentalDataLoader()

    # 1. Row-based CSV (table header + data row)
    row_csv = tmp_path / "nvda_row.csv"
    row_csv.write_text(
        "symbol,pe_ratio,net_margin,revenue_growth_yoy\nNVDA,55.0,0.52,1.20\n",
        encoding="utf-8",
    )
    metrics_row = loader.load_from_file(row_csv)
    assert metrics_row.symbol == "NVDA"
    assert metrics_row.pe_ratio == pytest.approx(55.0)
    assert metrics_row.net_margin == pytest.approx(0.52)
    assert metrics_row.revenue_growth_yoy == pytest.approx(1.20)

    # 2. Key-value vertical layout CSV
    kv_csv = tmp_path / "nvda_kv.csv"
    kv_csv.write_text(
        "metric,value\nsymbol,NVDA\npe_ratio,55.0\nnet_margin,0.52\nroe,0.65\n",
        encoding="utf-8",
    )
    metrics_kv = loader.load_from_file(kv_csv)
    assert metrics_kv.symbol == "NVDA"
    assert metrics_kv.roe == pytest.approx(0.65)

    # Empty CSV raises ValueError
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV file is empty"):
        loader.load_from_file(empty_csv)


@pytest.mark.issue_12
def test_load_from_directory_with_symbol_filter(tmp_path: Path) -> None:
    """Verify batch loading metrics across a directory with optional ticker filtering."""
    loader = FundamentalDataLoader()

    (tmp_path / "aapl.json").write_text(
        json.dumps({"symbol": "AAPL", "pe_ratio": 28.0}), encoding="utf-8"
    )
    (tmp_path / "msft.json").write_text(
        json.dumps({"symbol": "MSFT", "pe_ratio": 32.0}), encoding="utf-8"
    )
    (tmp_path / "googl.csv").write_text("symbol,pe_ratio\nGOOGL,23.5\n", encoding="utf-8")
    # Non-supported extension should be ignored gracefully
    (tmp_path / "notes.txt").write_text("irrelevant notes", encoding="utf-8")

    all_metrics = loader.load_from_directory(tmp_path)
    assert len(all_metrics) == 3
    symbols = {m.symbol for m in all_metrics}
    assert symbols == {"AAPL", "MSFT", "GOOGL"}

    # Filter by specific ticker
    filtered = loader.load_from_directory(tmp_path, symbol="msft")
    assert len(filtered) == 1
    assert filtered[0].symbol == "MSFT"

    with pytest.raises(FileNotFoundError):
        loader.load_from_directory(tmp_path / "non_existent_subdir")


@pytest.mark.issue_12
def test_load_from_financial_report_integration() -> None:
    """Verify extracting fundamental metrics from a research FinancialReport."""
    loader = FundamentalDataLoader()

    report = FinancialReport(
        symbol="TSLA",
        report_type=ReportType.TEN_Q,
        period="2026-Q1",
        content="",
        sections={
            "financial_highlights": (
                "Operational metrics for TSLA: Net Revenue up 18.5% YoY. "
                "Operating margin was 14.2% across automations. "
                "Diluted EPS: $1.25, with free cash flow: $2,450 million."
            ),
        },
        metadata={"fundamentals": {"debt_to_equity": 0.25, "current_ratio": 1.75}},
    )

    metrics = loader.load_from_financial_report(report)
    assert metrics.symbol == "TSLA"
    assert metrics.operating_margin == pytest.approx(0.142)
    assert metrics.revenue_growth_yoy == pytest.approx(0.185)
    assert metrics.free_cash_flow == pytest.approx(2450.0)
    assert metrics.debt_to_equity == pytest.approx(0.25)
    assert metrics.current_ratio == pytest.approx(1.75)
    assert metrics.metadata["eps"] == pytest.approx(1.25)


@pytest.mark.issue_12
def test_generate_mock_fundamentals_archetypes() -> None:
    """Verify mock generator produces realistic archetypes with determinism."""
    strong = FundamentalDataLoader.generate_mock_fundamentals(
        symbol="AAPL", profile="strong", seed=42
    )
    assert strong.symbol == "AAPL"
    assert strong.pe_ratio is not None and strong.pe_ratio < 25.0
    assert strong.net_margin is not None and strong.net_margin > 0.15
    assert strong.debt_to_equity is not None and strong.debt_to_equity < 1.0

    growth = FundamentalDataLoader.generate_mock_fundamentals(
        symbol="NVDA", profile="growth", seed=42
    )
    assert growth.symbol == "NVDA"
    assert growth.pe_ratio is not None and growth.pe_ratio > 30.0
    assert growth.revenue_growth_yoy is not None and growth.revenue_growth_yoy > 0.20

    distressed = FundamentalDataLoader.generate_mock_fundamentals(
        symbol="WEAK", profile="distressed", seed=42
    )
    assert distressed.symbol == "WEAK"
    assert distressed.pe_ratio is None  # Unprofitable
    assert distressed.net_margin is not None and distressed.net_margin < 0.0
    assert distressed.debt_to_equity is not None and distressed.debt_to_equity > 2.0

    neutral = FundamentalDataLoader.generate_mock_fundamentals(
        symbol="SPY", profile="neutral", seed=42
    )
    assert neutral.symbol == "SPY"
    assert neutral.pe_ratio is not None

    # Determinism check
    strong_again = FundamentalDataLoader.generate_mock_fundamentals(
        symbol="AAPL", profile="strong", seed=42
    )
    assert strong.pe_ratio == strong_again.pe_ratio
    assert strong.net_margin == strong_again.net_margin


@pytest.mark.issue_12
def test_fundamental_ratios_helper_methods() -> None:
    """Verify helper evaluation methods on FundamentalMetrics."""
    # is_undervalued
    val_cheap = FundamentalMetrics(symbol="TEST", pe_ratio=18.0)
    assert val_cheap.is_undervalued(benchmark_pe=25.0) is True

    val_expensive = FundamentalMetrics(symbol="TEST", pe_ratio=35.0)
    assert val_expensive.is_undervalued(benchmark_pe=25.0) is False

    val_none = FundamentalMetrics(symbol="TEST", pe_ratio=None)
    assert val_none.is_undervalued() is False

    # is_profitable
    prof = FundamentalMetrics(symbol="TEST", net_margin=0.15)
    assert prof.is_profitable() is True

    unprof = FundamentalMetrics(symbol="TEST", net_margin=-0.05)
    assert unprof.is_profitable() is False

    # has_healthy_balance_sheet
    healthy = FundamentalMetrics(symbol="TEST", debt_to_equity=0.5, current_ratio=2.0)
    assert healthy.has_healthy_balance_sheet() is True

    unhealthy_debt = FundamentalMetrics(symbol="TEST", debt_to_equity=3.0, current_ratio=1.5)
    assert unhealthy_debt.has_healthy_balance_sheet() is False

    unhealthy_liq = FundamentalMetrics(symbol="TEST", debt_to_equity=0.8, current_ratio=0.7)
    assert unhealthy_liq.has_healthy_balance_sheet() is False


@pytest.mark.issue_12
def test_fundamental_score_bounds_and_ranking() -> None:
    """Verify composite fundamental score bounds and archetype ordering."""
    strong = FundamentalDataLoader.generate_mock_fundamentals(profile="strong", seed=10)
    distressed = FundamentalDataLoader.generate_mock_fundamentals(profile="distressed", seed=10)

    score_strong = strong.fundamental_score()
    score_distressed = distressed.fundamental_score()

    assert 0.0 <= score_strong <= 1.0
    assert 0.0 <= score_distressed <= 1.0
    assert score_strong > score_distressed
    assert score_strong >= 0.70
    assert score_distressed <= 0.35


@pytest.mark.issue_12
def test_error_handling_invalid_files_and_missing_keys(tmp_path: Path) -> None:
    """Verify error isolation for missing files, bad extensions, and corrupted rows."""
    loader = FundamentalDataLoader()

    with pytest.raises(FileNotFoundError):
        loader.load_from_file(tmp_path / "does_not_exist.json")

    bad_ext = tmp_path / "metrics.xml"
    bad_ext.write_text("<root></root>", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported fundamental metrics file format"):
        loader.load_from_file(bad_ext)


@pytest.mark.issue_12
def test_fetch_fundamentals_caching(tmp_path: Path) -> None:
    """Verify fetch_fundamentals retrieves from directory, caches result, and falls back."""
    (tmp_path / "meta.json").write_text(
        json.dumps({"symbol": "META", "pe_ratio": 24.0, "net_margin": 0.28}),
        encoding="utf-8",
    )
    loader = FundamentalDataLoader(data_directory=tmp_path)

    # 1. Fetches from directory
    meta = loader.fetch_fundamentals("META")
    assert meta.symbol == "META"
    assert meta.pe_ratio == 24.0
    assert meta.net_margin == 0.28

    # 2. Subsequent call uses cache
    meta_cached = loader.fetch_fundamentals("META")
    assert meta_cached is meta

    # 3. Fallback to mock for unknown symbol
    unknown = loader.fetch_fundamentals("UNKNOWN")
    assert unknown.symbol == "UNKNOWN"
    assert unknown.source.startswith("mock")
