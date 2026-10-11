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
