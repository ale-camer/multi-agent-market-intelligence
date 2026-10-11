"""Multi-factor quantitative trading signal generator and risk level calculator."""

from datetime import datetime, timezone
from typing import Any

from multi_agent_market_intelligence.state.models import SignalAction, TradingSignal
from multi_agent_market_intelligence.trading.models import (
    FundamentalMetrics,
    SignalStrategyConfig,
    TechnicalIndicatorsResult,
)


class TradingSignalGenerator:
    """Quantitative multi-factor trading signal generator and risk level calculator."""

    def __init__(self, config: SignalStrategyConfig | None = None) -> None:
        """Initialize the signal generator with strategy weights and thresholds.

        Args:
            config: Strategy parameters and risk thresholds.
        """
        self.config = config or SignalStrategyConfig()

    def evaluate_technical_score(
        self,
        indicators: TechnicalIndicatorsResult | dict[str, Any],
    ) -> tuple[float, list[str]]:
        """Evaluate technical indicators into a normalized directional score [-1.0, 1.0].

        Args:
            indicators: Computed technical indicators.

        Returns:
            Tuple of (technical_score, itemized_reasons).
        """
        reasons: list[str] = []
        if isinstance(indicators, TechnicalIndicatorsResult):
            ind_dict = indicators.to_dict()
        else:
            ind_dict = dict(indicators)

        sub_scores: list[tuple[float, float]] = []  # (score, weight)

        # 1. RSI (Momentum / Mean-Reversion)
        rsi = ind_dict.get("rsi")
        if rsi is not None:
            if rsi < self.config.rsi_oversold:
                sub_scores.append((1.0, self.config.rsi_weight))
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > self.config.rsi_overbought:
                sub_scores.append((-1.0, self.config.rsi_weight))
                reasons.append(f"RSI overbought ({rsi:.1f})")
            else:
                # Moderate momentum: 50-70 mildly positive, 30-50 mildly negative
                norm_rsi = (rsi - 50.0) / 20.0
                sub_scores.append((max(-0.6, min(0.6, norm_rsi)), self.config.rsi_weight))
                if abs(norm_rsi) > 0.3:
                    reasons.append(f"RSI momentum neutral-to-trend ({rsi:.1f})")

        # 2. MACD (Trend & Convergence)
        macd = ind_dict.get("macd")
        if macd and isinstance(macd, dict):
            hist = macd.get("histogram")
            m_line = macd.get("macd_line")
            s_line = macd.get("signal_line")
            if hist is not None:
                if hist > 0:
                    is_crossover = m_line is not None and s_line is not None and m_line > s_line
                    score = 1.0 if is_crossover else 0.5
                    sub_scores.append((score, self.config.macd_weight))
                    reasons.append(f"Bullish MACD histogram (+{hist:.2f})")
                elif hist < 0:
                    is_under = m_line is not None and s_line is not None and m_line < s_line
                    score = -1.0 if is_under else -0.5
                    sub_scores.append((score, self.config.macd_weight))
                    reasons.append(f"Bearish MACD histogram ({hist:.2f})")
                else:
                    sub_scores.append((0.0, self.config.macd_weight))

        # 3. Moving Average Trend (SMA & EMA)
        close = ind_dict.get("close", 0.0)
        sma = ind_dict.get("sma", {}) or {}
        ema = ind_dict.get("ema", {}) or {}

        trend_score = 0.0
        trend_count = 0

        sma_50 = sma.get("sma_50")
        if sma_50 is not None and close:
            if close > sma_50:
                trend_score += 0.5
                reasons.append("Price above SMA 50")
            else:
                trend_score -= 0.5
                reasons.append("Price below SMA 50")
            trend_count += 1

        ema_12 = ema.get("ema_12")
        ema_26 = ema.get("ema_26")
        if ema_12 is not None and ema_26 is not None:
            if ema_12 > ema_26:
                trend_score += 0.5
                reasons.append("EMA 12 > EMA 26 bullish alignment")
            else:
                trend_score -= 0.5
                reasons.append("EMA 12 < EMA 26 bearish alignment")
            trend_count += 1

        if trend_count > 0:
            sub_scores.append((max(-1.0, min(1.0, trend_score)), self.config.trend_weight))

        # 4. VWAP & Bollinger Confirmations
        vwap = ind_dict.get("vwap")
        if vwap is not None and close:
            if close > vwap:
                sub_scores.append((0.25, 0.10))
                reasons.append("Price above VWAP support")
            else:
                sub_scores.append((-0.25, 0.10))
                reasons.append("Price below VWAP resistance")

        if not sub_scores:
            return 0.0, ["Insufficient technical indicators"]

        total_weight = sum(w for _, w in sub_scores)
        weighted_sum = sum(s * w for s, w in sub_scores)
        final_tech_score = round(weighted_sum / total_weight, 4)

        return max(-1.0, min(1.0, final_tech_score)), reasons

    def evaluate_fundamental_score(
        self,
        fundamentals: FundamentalMetrics | dict[str, Any] | None,
    ) -> tuple[float, list[str]]:
        """Evaluate corporate fundamental metrics into a directional score [-1.0, 1.0].

        Args:
            fundamentals: Corporate fundamentals record.

        Returns:
            Tuple of (fundamental_score, itemized_reasons).
        """
        if fundamentals is None:
            return 0.0, ["No fundamental data available"]

        if isinstance(fundamentals, dict):
            fund = FundamentalMetrics.model_validate(fundamentals)
        else:
            fund = fundamentals

        reasons: list[str] = []

        # Convert composite score [0.0, 1.0] to directional [-1.0, 1.0]
        base_score = round((fund.fundamental_score() - 0.5) * 2.0, 4)

        # Reasons itemization
        if fund.is_undervalued(benchmark_pe=25.0):
            reasons.append(f"Attractive valuation P/E ({fund.pe_ratio:.1f})")
        elif fund.pe_ratio and fund.pe_ratio > 40.0:
            reasons.append(f"Elevated valuation multiple P/E ({fund.pe_ratio:.1f})")

        if fund.is_profitable():
            margin_val = fund.net_margin
            margin_text = f"{margin_val * 100:.1f}%" if margin_val is not None else "positive"
            reasons.append(f"Profitable operations (Net margin: {margin_text})")
        elif fund.net_margin is not None and fund.net_margin < 0:
            reasons.append(f"Negative net margin ({fund.net_margin * 100:.1f}%)")

        if fund.has_healthy_balance_sheet():
            reasons.append("Healthy balance sheet leverage and solvency")
        else:
            reasons.append("Elevated debt leverage or constrained liquidity")

        if fund.revenue_growth_yoy is not None and fund.revenue_growth_yoy > 0.10:
            reasons.append(f"Robust revenue expansion (+{fund.revenue_growth_yoy * 100:.1f}% YoY)")

        return max(-1.0, min(1.0, base_score)), reasons

    def calculate_risk_levels(
        self,
        current_price: float,
        action: SignalAction,
        atr: float | None = None,
    ) -> tuple[float | None, float | None]:
        """Calculate volatility-adjusted target price and stop loss.

        Args:
            current_price: Current market price of the asset.
            action: Trading signal action (BUY, SELL, HOLD).
            atr: Average True Range volatility measure.

        Returns:
            Tuple of (target_price, stop_loss). Both None if action is HOLD.
        """
        if action == SignalAction.HOLD or current_price <= 0.0:
            return None, None

        if atr is not None and atr > 0.0:
            stop_dist = self.config.atr_stop_multiplier * atr
        else:
            stop_dist = current_price * self.config.default_stop_loss_pct

        target_dist = stop_dist * self.config.risk_reward_ratio

        if action == SignalAction.BUY:
            stop_loss = max(0.01, round(current_price - stop_dist, 2))
            target_price = round(current_price + target_dist, 2)
        else:  # SELL
            stop_loss = round(current_price + stop_dist, 2)
            target_price = max(0.01, round(current_price - target_dist, 2))

        return target_price, stop_loss

    def generate_signal(
        self,
        symbol: str,
        indicators: TechnicalIndicatorsResult | dict[str, Any],
        fundamentals: FundamentalMetrics | dict[str, Any] | None = None,
        sentiment_score: float | None = None,
        current_price: float | None = None,
    ) -> TradingSignal:
        """Generate a strongly-typed TradingSignal combining quantitative and qualitative factors.

        Args:
            symbol: Ticker symbol.
            indicators: Technical indicators snapshot.
            fundamentals: Corporate fundamentals record.
            sentiment_score: Research sentiment score in [-1.0, 1.0].
            current_price: Optional market price override.

        Returns:
            Structured TradingSignal adhering to state management protocol.
        """
        sym = symbol.upper().strip()
        all_reasons: list[str] = []

        # 1. Technical Evaluation
        tech_score, tech_reasons = self.evaluate_technical_score(indicators)
        all_reasons.extend(tech_reasons)

        # 2. Fundamental Evaluation
        fund_score, fund_reasons = self.evaluate_fundamental_score(fundamentals)
        if fundamentals is not None:
            all_reasons.extend(fund_reasons)

        # 3. Sentiment Evaluation
        active_weights: list[tuple[float, float]] = [(tech_score, self.config.technical_weight)]
        if fundamentals is not None:
            active_weights.append((fund_score, self.config.fundamental_weight))

        clamped_sentiment = 0.0
        if sentiment_score is not None:
            clamped_sentiment = max(-1.0, min(1.0, sentiment_score))
            active_weights.append((clamped_sentiment, self.config.sentiment_weight))
            if abs(clamped_sentiment) > 0.15:
                s_lbl = "positive" if clamped_sentiment > 0 else "negative"
                all_reasons.append(f"Research sentiment {s_lbl} ({clamped_sentiment:+.2f})")

        # 4. Composite Scoring
        total_w = sum(w for _, w in active_weights)
        composite_score = round(sum(s * w for s, w in active_weights) / total_w, 4)

        # 5. Signal Action Determination
        # Conflict detection: If technical and fundamental strongly disagree, default to HOLD
        conflicting = (
            fundamentals is not None
            and (tech_score > 0.35 and fund_score < -0.35)
            or (tech_score < -0.35 and fund_score > 0.35)
        )

        if conflicting:
            action = SignalAction.HOLD
            all_reasons.append("Conflicting directional factors (technicals vs fundamentals)")
        elif composite_score >= self.config.buy_threshold:
            action = SignalAction.BUY
        elif composite_score <= self.config.sell_threshold:
            action = SignalAction.SELL
        else:
            action = SignalAction.HOLD

        # 6. Confidence Scoring [0.0, 1.0]
        if action == SignalAction.HOLD:
            confidence = round(max(self.config.min_confidence, 1.0 - abs(composite_score) * 0.8), 2)
        else:
            confidence = round(min(1.0, max(self.config.min_confidence, abs(composite_score))), 2)

        if conflicting:
            confidence = round(confidence * 0.7, 2)

        # 7. Price and Risk Level Calculation
        if current_price is not None and current_price > 0.0:
            price = current_price
        elif isinstance(indicators, TechnicalIndicatorsResult):
            price = indicators.close
        else:
            price = float(indicators.get("close", 100.0))

        atr_val = (
            indicators.atr
            if isinstance(indicators, TechnicalIndicatorsResult)
            else indicators.get("atr")
        )
        target_price, stop_loss = self.calculate_risk_levels(price, action, atr=atr_val)

        # 8. Indicator and Audit Payload
        if isinstance(indicators, TechnicalIndicatorsResult):
            ind_dict = indicators.to_dict()
        else:
            ind_dict = dict(indicators)
        ind_dict["composite_score"] = composite_score
        ind_dict["technical_score"] = tech_score
        ind_dict["fundamental_score"] = fund_score
        if sentiment_score is not None:
            ind_dict["sentiment_score"] = clamped_sentiment

        return TradingSignal(
            symbol=sym,
            action=action,
            confidence=confidence,
            target_price=target_price,
            stop_loss=stop_loss,
            reasoning="; ".join(all_reasons) if all_reasons else "Neutral multi-factor evaluation",
            indicators=ind_dict,
            timestamp=datetime.now(timezone.utc),
        )

    def generate_signals_batch(self, data_items: list[dict[str, Any]]) -> list[TradingSignal]:
        """Generate signals across multiple market instruments.

        Args:
            data_items: List of dictionaries matching generate_signal keyword arguments.

        Returns:
            List of generated TradingSignal objects.
        """
        signals: list[TradingSignal] = []
        for item in data_items:
            signals.append(
                self.generate_signal(
                    symbol=item["symbol"],
                    indicators=item["indicators"],
                    fundamentals=item.get("fundamentals"),
                    sentiment_score=item.get("sentiment_score"),
                    current_price=item.get("current_price"),
                )
            )
        return signals
