"""Technical indicators calculator and market time series analytics engine."""

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

import numpy as np
import pandas as pd

from multi_agent_market_intelligence.trading.models import (
    BollingerBandsResult,
    MACDResult,
    OHLCVBar,
    TechnicalIndicatorsResult,
)


class TechnicalIndicatorsCalculator:
    """Vectorized calculation engine for technical indicators on OHLCV market data."""

    @staticmethod
    def to_dataframe(
        data: pd.DataFrame | Sequence[OHLCVBar] | Sequence[dict[str, Any]],
    ) -> pd.DataFrame:
        """Convert heterogeneous input formats into a normalized pandas DataFrame.

        Args:
            data: Market data as a DataFrame, sequence of OHLCVBar models, or sequence of dicts.

        Returns:
            Normalized pandas DataFrame sorted by timestamp with lowercase float columns.
        """
        if isinstance(data, pd.DataFrame):
            df = data.copy()
            df.columns = [str(col).lower() for col in df.columns]
        else:
            records: list[dict[str, Any]] = []
            for item in data:
                if isinstance(item, OHLCVBar):
                    records.append(item.model_dump())
                elif isinstance(item, dict):
                    records.append(item)
                else:
                    raise TypeError(f"Unsupported data item type: {type(item).__name__}")
            df = pd.DataFrame(records)

        if df.empty:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"]
            )

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values(by="timestamp").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

        return df

    @staticmethod
    def compute_sma(prices: pd.Series | Sequence[float], window: int) -> pd.Series:
        """Calculate Simple Moving Average (SMA).

        Args:
            prices: Series or sequence of price values.
            window: Rolling period length (must be >= 1).

        Returns:
            Series of SMA values with NaN for insufficient history.
        """
        if window < 1:
            raise ValueError(f"SMA window must be >= 1, got {window}")
        series = pd.Series(prices, dtype=float)
        return series.rolling(window=window, min_periods=window).mean()

    @staticmethod
    def compute_ema(prices: pd.Series | Sequence[float], span: int) -> pd.Series:
        """Calculate Exponential Moving Average (EMA).

        Args:
            prices: Series or sequence of price values.
            span: Decay span parameter (must be >= 1).

        Returns:
            Series of EMA values.
        """
        if span < 1:
            raise ValueError(f"EMA span must be >= 1, got {span}")
        series = pd.Series(prices, dtype=float)
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def compute_rsi(prices: pd.Series | Sequence[float], period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index (RSI) using Wilder's exponential smoothing.

        Args:
            prices: Series or sequence of closing prices.
            period: Lookback period (default 14).

        Returns:
            Series bounded within [0.0, 100.0] with NaN for insufficient observations.
        """
        if period < 1:
            raise ValueError(f"RSI period must be >= 1, got {period}")
        series = pd.Series(prices, dtype=float)
        delta = series.diff()

        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)

        # Wilder's smoothing alpha = 1 / period
        alpha = 1.0 / period
        avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # Handle edge cases where loss is zero
        zero_loss = (avg_loss == 0.0) & (~avg_gain.isna())
        rsi.loc[zero_loss & (avg_gain > 0.0)] = 100.0
        rsi.loc[zero_loss & (avg_gain == 0.0)] = 50.0

        return rsi.clip(lower=0.0, upper=100.0)

    @staticmethod
    def compute_macd(
        prices: pd.Series | Sequence[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Moving Average Convergence Divergence (MACD).

        Args:
            prices: Series or sequence of prices.
            fast_period: Short EMA period (default 12).
            slow_period: Long EMA period (default 26).
            signal_period: Signal line EMA period (default 9).

        Returns:
            Tuple of (macd_line, signal_line, histogram).
        """
        series = pd.Series(prices, dtype=float)
        fast_ema = series.ewm(span=fast_period, adjust=False).mean()
        slow_ema = series.ewm(span=slow_period, adjust=False).mean()

        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def compute_bollinger_bands(
        prices: pd.Series | Sequence[float],
        window: int = 20,
        num_std: float = 2.0,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands (upper, middle, lower).

        Args:
            prices: Series or sequence of prices.
            window: Moving average window (default 20).
            num_std: Number of standard deviations (default 2.0).

        Returns:
            Tuple of (upper_band, middle_band, lower_band).
        """
        if window < 1:
            raise ValueError(f"Bollinger window must be >= 1, got {window}")
        series = pd.Series(prices, dtype=float)
        middle = series.rolling(window=window, min_periods=window).mean()
        std = series.rolling(window=window, min_periods=window).std(ddof=0)

        upper = middle + (num_std * std)
        lower = middle - (num_std * std)

        return upper, middle, lower

    @staticmethod
    def compute_atr(
        high: pd.Series | Sequence[float],
        low: pd.Series | Sequence[float],
        close: pd.Series | Sequence[float],
        period: int = 14,
    ) -> pd.Series:
        """Calculate Average True Range (ATR) using Wilder's smoothing.

        Args:
            high: High prices.
            low: Low prices.
            close: Close prices.
            period: Smoothing lookback (default 14).

        Returns:
            Series of ATR values.
        """
        if period < 1:
            raise ValueError(f"ATR period must be >= 1, got {period}")
        high_s = pd.Series(high, dtype=float)
        low_s = pd.Series(low, dtype=float)
        close_s = pd.Series(close, dtype=float)

        prev_close = close_s.shift(1)
        tr1 = high_s - low_s
        tr2 = (high_s - prev_close).abs()
        tr3 = (low_s - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        alpha = 1.0 / period
        return tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    @staticmethod
    def compute_obv(
        close: pd.Series | Sequence[float],
        volume: pd.Series | Sequence[float],
    ) -> pd.Series:
        """Calculate On-Balance Volume (OBV).

        Args:
            close: Series or sequence of closing prices.
            volume: Series or sequence of traded volumes.

        Returns:
            Cumulative OBV series.
        """
        c = pd.Series(close, dtype=float)
        v = pd.Series(volume, dtype=float)

        diff = c.diff().fillna(0.0)
        direction = np.sign(diff)
        return (direction * v).cumsum()

    @staticmethod
    def compute_vwap(
        high: pd.Series | Sequence[float],
        low: pd.Series | Sequence[float],
        close: pd.Series | Sequence[float],
        volume: pd.Series | Sequence[float],
    ) -> pd.Series:
        """Calculate Volume-Weighted Average Price (VWAP).

        Args:
            high: High prices.
            low: Low prices.
            close: Close prices.
            volume: Volume per bar.

        Returns:
            Cumulative VWAP series.
        """
        high_s = pd.Series(high, dtype=float)
        low_s = pd.Series(low, dtype=float)
        close_s = pd.Series(close, dtype=float)
        vol_s = pd.Series(volume, dtype=float)

        typical_price = (high_s + low_s + close_s) / 3.0
        cum_vol_price = (typical_price * vol_s).cumsum()
        cum_volume = vol_s.cumsum().replace(0.0, np.nan)

        return cum_vol_price / cum_volume

    def calculate_all(
        self,
        data: pd.DataFrame | Sequence[OHLCVBar] | Sequence[dict[str, Any]],
    ) -> pd.DataFrame:
        """Compute all supported technical indicators and enrich the DataFrame.

        Appends columns:
        - Moving Averages: sma_20, sma_50, sma_200, ema_12, ema_26, ema_50
        - Momentum: rsi_14
        - Trend: macd_line, macd_signal, macd_hist
        - Volatility: bb_upper, bb_middle, bb_lower, bb_bandwidth, bb_percent_b, atr_14
        - Volume: obv, vwap

        Args:
            data: Market data input.

        Returns:
            Enriched DataFrame with calculated indicators.
        """
        df = self.to_dataframe(data)
        if df.empty or "close" not in df.columns:
            return df

        close = df["close"]
        high = df["high"] if "high" in df.columns else close
        low = df["low"] if "low" in df.columns else close
        volume = df["volume"] if "volume" in df.columns else pd.Series(0.0, index=df.index)

        # Simple Moving Averages
        df["sma_20"] = self.compute_sma(close, window=20)
        df["sma_50"] = self.compute_sma(close, window=50)
        df["sma_200"] = self.compute_sma(close, window=200)

        # Exponential Moving Averages
        df["ema_12"] = self.compute_ema(close, span=12)
        df["ema_26"] = self.compute_ema(close, span=26)
        df["ema_50"] = self.compute_ema(close, span=50)

        # RSI
        df["rsi_14"] = self.compute_rsi(close, period=14)

        # MACD
        m_line, m_sig, m_hist = self.compute_macd(
            close, fast_period=12, slow_period=26, signal_period=9
        )
        df["macd_line"] = m_line
        df["macd_signal"] = m_sig
        df["macd_hist"] = m_hist

        # Bollinger Bands
        bb_u, bb_m, bb_l = self.compute_bollinger_bands(close, window=20, num_std=2.0)
        df["bb_upper"] = bb_u
        df["bb_middle"] = bb_m
        df["bb_lower"] = bb_l
        bb_spread = (bb_u - bb_l).replace(0.0, np.nan)
        df["bb_bandwidth"] = (bb_u - bb_l) / bb_m.replace(0.0, np.nan)
        df["bb_percent_b"] = (close - bb_l) / bb_spread

        # ATR
        df["atr_14"] = self.compute_atr(high, low, close, period=14)

        # Volume Indicators
        df["obv"] = self.compute_obv(close, volume)
        df["vwap"] = self.compute_vwap(high, low, close, volume)

        return df

    def get_latest_indicators(
        self,
        data: pd.DataFrame | Sequence[OHLCVBar] | Sequence[dict[str, Any]],
        symbol: str | None = None,
    ) -> TechnicalIndicatorsResult:
        """Extract a strongly-typed snapshot of the latest computed indicators.

        Args:
            data: Market data input.
            symbol: Optional ticker symbol override.

        Returns:
            TechnicalIndicatorsResult representing the most recent bar.
        """
        df = self.calculate_all(data)
        if df.empty:
            return TechnicalIndicatorsResult(symbol=symbol, close=0.0)

        last = df.iloc[-1]

        def _to_opt_float(val: Any) -> float | None:
            if val is None or pd.isna(val):
                return None
            return float(val)

        # Extract MACD
        m_line = _to_opt_float(last.get("macd_line"))
        m_sig = _to_opt_float(last.get("macd_signal"))
        m_hist = _to_opt_float(last.get("macd_hist"))
        macd_result = (
            MACDResult(macd_line=m_line, signal_line=m_sig, histogram=m_hist)
            if m_line is not None and m_sig is not None and m_hist is not None
            else None
        )

        # Extract Bollinger Bands
        bb_u = _to_opt_float(last.get("bb_upper"))
        bb_m = _to_opt_float(last.get("bb_middle"))
        bb_l = _to_opt_float(last.get("bb_lower"))
        bb_bw = _to_opt_float(last.get("bb_bandwidth")) or 0.0
        bb_pb = _to_opt_float(last.get("bb_percent_b")) or 0.0
        bb_result = (
            BollingerBandsResult(
                upper=bb_u, middle=bb_m, lower=bb_l, bandwidth=bb_bw, percent_b=bb_pb
            )
            if bb_u is not None and bb_m is not None and bb_l is not None
            else None
        )

        raw_sym = last.get("symbol")
        resolved_symbol = symbol or (
            str(raw_sym) if raw_sym is not None and not pd.isna(raw_sym) else None
        )
        ts_val = last.get("timestamp")
        timestamp = (
            ts_val.to_pydatetime()
            if isinstance(ts_val, pd.Timestamp)
            else (ts_val if isinstance(ts_val, datetime) else datetime.now(timezone.utc))
        )

        return TechnicalIndicatorsResult(
            symbol=resolved_symbol,
            timestamp=timestamp,
            close=float(last.get("close", 0.0)),
            sma={
                "sma_20": _to_opt_float(last.get("sma_20")),
                "sma_50": _to_opt_float(last.get("sma_50")),
                "sma_200": _to_opt_float(last.get("sma_200")),
            },
            ema={
                "ema_12": _to_opt_float(last.get("ema_12")),
                "ema_26": _to_opt_float(last.get("ema_26")),
                "ema_50": _to_opt_float(last.get("ema_50")),
            },
            rsi=_to_opt_float(last.get("rsi_14")),
            macd=macd_result,
            bollinger=bb_result,
            atr=_to_opt_float(last.get("atr_14")),
            obv=_to_opt_float(last.get("obv")),
            vwap=_to_opt_float(last.get("vwap")),
            metadata={
                "total_bars": len(df),
            },
        )

    @staticmethod
    def generate_mock_ohlcv(
        symbol: str = "AAPL",
        num_bars: int = 100,
        base_price: float = 150.0,
        trend: str = "neutral",
        seed: int | None = 42,
    ) -> list[OHLCVBar]:
        """Generate deterministic synthetic OHLCV time series data for offline testing.

        Args:
            symbol: Ticker symbol.
            num_bars: Number of daily bars to produce.
            base_price: Starting price.
            trend: Drift direction ('up', 'down', 'neutral', 'volatile').
            seed: Random seed for repeatability.

        Returns:
            List of valid OHLCVBar objects.
        """
        rng = np.random.default_rng(seed)

        drift = 0.0
        volatility = 0.015
        if trend == "up":
            drift = 0.003
            volatility = 0.012
        elif trend == "down":
            drift = -0.003
            volatility = 0.015
        elif trend == "volatile":
            drift = 0.0
            volatility = 0.035

        start_date = datetime.now(timezone.utc) - timedelta(days=num_bars)
        bars: list[OHLCVBar] = []
        current_close = base_price

        for i in range(num_bars):
            bar_date = start_date + timedelta(days=i)
            pct_change = drift + rng.normal(0, volatility)
            new_close = max(1.0, current_close * (1.0 + pct_change))

            # Realistic intra-day high/low spread
            open_price = current_close
            candle_min = min(open_price, new_close)
            candle_max = max(open_price, new_close)

            spread_high = abs(rng.normal(0, volatility * 0.5)) * open_price
            spread_low = abs(rng.normal(0, volatility * 0.5)) * open_price

            high_price = candle_max + spread_high
            low_price = max(0.5, candle_min - spread_low)
            volume = float(rng.integers(500_000, 5_000_000))

            bars.append(
                OHLCVBar(
                    timestamp=bar_date,
                    open=round(float(open_price), 2),
                    high=round(float(high_price), 2),
                    low=round(float(low_price), 2),
                    close=round(float(new_close), 2),
                    volume=volume,
                    symbol=symbol,
                )
            )
            current_close = new_close

        return bars
