"""Domain models for market time series and technical indicator data."""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from multi_agent_market_intelligence.state.models import DomainStateModel


class OHLCVBar(DomainStateModel):
    """Single open, high, low, close, volume market candle."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    symbol: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MACDResult(DomainStateModel):
    """Calculated Moving Average Convergence Divergence values."""

    macd_line: float
    signal_line: float
    histogram: float


class BollingerBandsResult(DomainStateModel):
    """Calculated Bollinger Bands values."""

    upper: float
    middle: float
    lower: float
    bandwidth: float
    percent_b: float


class TechnicalIndicatorsResult(DomainStateModel):
    """Consolidated technical indicators calculated for a market asset."""

    symbol: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    close: float = 0.0
    sma: dict[str, float | None] = Field(default_factory=dict)
    ema: dict[str, float | None] = Field(default_factory=dict)
    rsi: float | None = None
    macd: MACDResult | None = None
    bollinger: BollingerBandsResult | None = None
    atr: float | None = None
    obv: float | None = None
    vwap: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert indicator values to a nested dictionary for state integration."""
        return self.model_dump()


class FundamentalMetrics(DomainStateModel):
    """Corporate valuation, profitability, health, and growth metrics."""

    symbol: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Valuation
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None

    # Profitability
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    roa: float | None = None

    # Balance Sheet & Solvency
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    interest_coverage: float | None = None
    free_cash_flow: float | None = None

    # Growth & Dividends
    revenue_growth_yoy: float | None = None
    net_income_growth_yoy: float | None = None
    eps_growth_yoy: float | None = None
    dividend_yield: float | None = None

    # Metadata
    fiscal_period: str | None = None
    source: str = "mock"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_undervalued(self, benchmark_pe: float = 25.0) -> bool:
        """Evaluate if the asset is undervalued relative to a benchmark P/E."""
        if self.pe_ratio is None or self.pe_ratio <= 0.0:
            return False
        return self.pe_ratio <= benchmark_pe

    def is_profitable(self) -> bool:
        """Check if the business operates profitably based on margins or returns."""
        if self.net_margin is not None:
            return self.net_margin > 0.0
        if self.operating_margin is not None:
            return self.operating_margin > 0.0
        if self.roe is not None:
            return self.roe > 0.0
        return False

    def has_healthy_balance_sheet(
        self,
        max_debt_to_equity: float = 2.0,
        min_current_ratio: float = 1.0,
    ) -> bool:
        """Evaluate whether balance sheet liquidity and leverage meet safety thresholds."""
        healthy = True
        if self.debt_to_equity is not None and self.debt_to_equity > max_debt_to_equity:
            healthy = False
        if self.current_ratio is not None and self.current_ratio < min_current_ratio:
            healthy = False
        return healthy

    def fundamental_score(self) -> float:
        """Calculate a composite fundamental score normalized between 0.0 and 1.0."""
        score = 0.5  # neutral baseline

        # Valuation component (+/- 0.15)
        if self.pe_ratio is not None:
            if 0.0 < self.pe_ratio <= 15.0:
                score += 0.15
            elif 15.0 < self.pe_ratio <= 25.0:
                score += 0.08
            elif self.pe_ratio > 35.0 or self.pe_ratio <= 0.0:
                score -= 0.10

        # Profitability component (+/- 0.15)
        if self.net_margin is not None:
            if self.net_margin >= 0.20:
                score += 0.15
            elif self.net_margin >= 0.10:
                score += 0.08
            elif self.net_margin < 0.0:
                score -= 0.15

        # Solvency component (+/- 0.10)
        if self.debt_to_equity is not None:
            if self.debt_to_equity <= 0.8:
                score += 0.05
            elif self.debt_to_equity > 2.0:
                score -= 0.08
        if self.current_ratio is not None:
            if self.current_ratio >= 1.5:
                score += 0.05
            elif self.current_ratio < 1.0:
                score -= 0.08

        # Growth component (+/- 0.10)
        if self.revenue_growth_yoy is not None:
            if self.revenue_growth_yoy >= 0.15:
                score += 0.10
            elif self.revenue_growth_yoy >= 0.05:
                score += 0.05
            elif self.revenue_growth_yoy < 0.0:
                score -= 0.10

        return max(0.0, min(1.0, round(score, 4)))

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to a nested dictionary for state integration."""
        return self.model_dump()
