"""Autonomous Trading Analyst Agent executing quantitative indicators, fundamentals, and signals."""

from collections.abc import Callable, Sequence
from typing import Any, cast

from multi_agent_market_intelligence.agents.base import BaseAgent
from multi_agent_market_intelligence.agents.schema import AgentConfig, AgentRole
from multi_agent_market_intelligence.messaging.bus import MessageBus
from multi_agent_market_intelligence.messaging.models import MessagePriority, MessageType
from multi_agent_market_intelligence.orchestrator.schema import OrchestratorState
from multi_agent_market_intelligence.state.models import TradingSignal
from multi_agent_market_intelligence.state.schema import MarketIntelligenceState
from multi_agent_market_intelligence.trading.fundamental import (
    FundamentalDataLoader,
)
from multi_agent_market_intelligence.trading.indicators import (
    TechnicalIndicatorsCalculator,
)
from multi_agent_market_intelligence.trading.models import (
    FundamentalMetrics,
    TechnicalIndicatorsResult,
)
from multi_agent_market_intelligence.trading.signals import (
    TradingSignalGenerator,
)


def _extract_symbol_sentiment(
    artifacts: Sequence[Any],
    symbol: str,
) -> float | None:
    """Extract sentiment score for a given ticker symbol from research artifacts.

    Prefers synthesis artifacts produced by ResearchAgent. Falls back to averaging
    granular news and report artifact sentiment scores. Returns None if no match.

    Args:
        artifacts: List of research artifacts or dictionaries from state.
        symbol: Ticker symbol to extract sentiment for.

    Returns:
        Directional sentiment score in [-1.0, 1.0] or None.
    """
    sym = symbol.upper().strip()
    scores: list[float] = []

    for item in artifacts:
        metadata: dict[str, Any] = (
            item.metadata
            if hasattr(item, "metadata") and isinstance(item.metadata, dict)
            else (item.get("metadata", {}) if isinstance(item, dict) else {})
        )
        headline = (
            getattr(item, "headline", "")
            if hasattr(item, "headline")
            else (item.get("headline", "") if isinstance(item, dict) else "")
        )
        item_symbol = str(metadata.get("symbol", "")).upper().strip()
        matches_symbol = (item_symbol == sym) or (sym in headline.upper())

        if not matches_symbol:
            continue

        raw_score = (
            getattr(item, "sentiment_score", None)
            if hasattr(item, "sentiment_score")
            else (item.get("sentiment_score") if isinstance(item, dict) else None)
        )
        if raw_score is None:
            raw_score = metadata.get("composite_score")

        if raw_score is not None:
            try:
                score_val = float(raw_score)
                # Prioritize high-level synthesis artifact immediately
                if metadata.get("is_synthesis") is True:
                    return score_val
                scores.append(score_val)
            except (ValueError, TypeError):
                continue

    if scores:
        return round(sum(scores) / len(scores), 4)
    return None


class TradingAnalystAgent(BaseAgent):
    """Autonomous Trading Analyst Agent responsible for quantitative evaluation and signals."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        message_bus: MessageBus | None = None,
        indicators_calculator: TechnicalIndicatorsCalculator | None = None,
        fundamental_loader: FundamentalDataLoader | None = None,
        signal_generator: TradingSignalGenerator | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        cfg = config or AgentConfig(
            name="TradingAnalyst",
            role=AgentRole.TRADING_ANALYST,
            capabilities=[
                "technical_analysis",
                "fundamental_analysis",
                "signal_generation",
            ],
        )
        super().__init__(config=cfg, message_bus=message_bus)
        # Register alias subscription for lower-case role matching
        if self.message_bus is not None and self.name != "trading_analyst":
            self.message_bus.subscribe("trading_analyst", self.receive_message)

        self.indicators_calculator = indicators_calculator or TechnicalIndicatorsCalculator()
        self.fundamental_loader = fundamental_loader or FundamentalDataLoader()
        self.signal_generator = signal_generator or TradingSignalGenerator()
        self.symbols = [s.upper().strip() for s in symbols] if symbols is not None else ["AAPL"]

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Execute synchronous multi-factor trading analysis workflow over target symbols.

        Args:
            state: Current market intelligence state.

        Returns:
            Dictionary with state updates: signals, messages, context, and current_step.
        """
        context = state.get("context", {})
        artifacts = state.get("artifacts", [])
        target_symbols = self._resolve_target_symbols(context)

        signals_collector: list[TradingSignal] = []
        correlation_id = str(context.get("correlation_id", "")) or None

        for symbol in target_symbols:
            # 1. Ingest sentiment from state research artifacts or context fallback
            sentiment_score = _extract_symbol_sentiment(artifacts, symbol)
            if sentiment_score is None:
                sentiment_ctx = context.get("sentiment_scores") or context.get("sentiment")
                if isinstance(sentiment_ctx, dict) and symbol in sentiment_ctx:
                    try:
                        sentiment_score = float(sentiment_ctx[symbol])
                    except (ValueError, TypeError):
                        pass

            # 2. Retrieve or compute technical indicators
            indicators = self._resolve_indicators(symbol, context)

            # 3. Retrieve or load corporate fundamentals
            fundamentals = self._resolve_fundamentals(symbol, context)

            # 4. Resolve current market price override if provided
            current_price = self._resolve_current_price(symbol, context)

            # 5. Generate structured multi-factor trading signal
            signal = self.signal_generator.generate_signal(
                symbol=symbol,
                indicators=indicators,
                fundamentals=fundamentals,
                sentiment_score=sentiment_score,
                current_price=current_price,
            )
            signals_collector.append(signal)

            # 6. Publish SIGNAL_PROPOSAL notification via MessageBus if available
            if self.message_bus is not None:
                self.send_message(
                    recipient="risk_manager",
                    message_type=MessageType.SIGNAL_PROPOSAL,
                    payload={
                        "symbol": signal.symbol,
                        "action": signal.action.value,
                        "confidence": signal.confidence,
                        "target_price": signal.target_price,
                        "stop_loss": signal.stop_loss,
                        "reasoning": signal.reasoning,
                        "signal": signal.model_dump(),
                    },
                    correlation_id=correlation_id,
                    priority=MessagePriority.NORMAL,
                )

        symbols_str = ", ".join(target_symbols)
        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": self.name,
                "content": (
                    f"Trading analysis completed for {symbols_str}. "
                    f"Generated {len(signals_collector)} signals."
                ),
            }
        )

        return {
            "current_step": "trading_analyst",
            "signals": signals_collector,
            "messages": messages,
            "context": {
                "target_symbols": target_symbols,
                "signals_generated_count": len(signals_collector),
                "trading_analysis_completed": True,
            },
        }

    async def process_async(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Execute asynchronous quantitative trading analysis workflow."""
        return self.process(state)

    def _resolve_target_symbols(self, context: dict[str, Any]) -> list[str]:
        """Resolve ticker symbols from state context or defaults."""
        raw_symbols = context.get("target_symbols") or context.get("symbols")
        if raw_symbols and isinstance(raw_symbols, list):
            resolved = [str(s).upper().strip() for s in raw_symbols if str(s).strip()]
            if resolved:
                return resolved

        single_sym = context.get("symbol")
        if single_sym and str(single_sym).strip():
            return [str(single_sym).upper().strip()]

        return list(self.symbols) if self.symbols else ["AAPL"]

    def _resolve_indicators(
        self,
        symbol: str,
        context: dict[str, Any],
    ) -> TechnicalIndicatorsResult | dict[str, Any]:
        """Retrieve precomputed indicators or compute via indicators calculator."""
        ctx_indicators = context.get("indicators", {})
        if isinstance(ctx_indicators, dict) and symbol in ctx_indicators:
            val = ctx_indicators[symbol]
            if isinstance(val, (TechnicalIndicatorsResult, dict)):
                return val
            return cast(dict[str, Any], val)

        ctx_bars = (
            context.get("ohlcv_bars", {}).get(symbol)
            if isinstance(context.get("ohlcv_bars"), dict)
            else None
        ) or (
            context.get("bars", {}).get(symbol) if isinstance(context.get("bars"), dict) else None
        )
        if ctx_bars and isinstance(ctx_bars, list):
            return self.indicators_calculator.get_latest_indicators(ctx_bars, symbol=symbol)

        # Autonomous fallback: generate mock bars and compute
        bars = self.indicators_calculator.generate_mock_ohlcv(symbol=symbol)
        return self.indicators_calculator.get_latest_indicators(bars, symbol=symbol)

    def _resolve_fundamentals(
        self,
        symbol: str,
        context: dict[str, Any],
    ) -> FundamentalMetrics | None:
        """Retrieve corporate fundamentals from context or fetch via loader."""
        ctx_fundamentals = context.get("fundamentals", {})
        if isinstance(ctx_fundamentals, dict) and symbol in ctx_fundamentals:
            val = ctx_fundamentals[symbol]
            if isinstance(val, FundamentalMetrics):
                return val
            if isinstance(val, dict):
                return FundamentalMetrics.model_validate(val)

        try:
            return self.fundamental_loader.fetch_fundamentals(symbol)
        except Exception:
            return None

    def _resolve_current_price(
        self,
        symbol: str,
        context: dict[str, Any],
    ) -> float | None:
        """Resolve current market price override from context if provided."""
        prices = context.get("prices") or context.get("current_prices") or {}
        if isinstance(prices, dict) and symbol in prices:
            try:
                return float(prices[symbol])
            except (ValueError, TypeError):
                pass
        return None


def create_trading_analyst_node_handler(
    agent: TradingAnalystAgent | None = None,
) -> Callable[[OrchestratorState], dict[str, Any]]:
    """Create an orchestrator-compatible node handler powered by a TradingAnalystAgent instance.

    Args:
        agent: Optional custom TradingAnalystAgent instance.

    Returns:
        Callable compatible with LangGraph Orchestrator node contracts.
    """
    trading_agent = agent or TradingAnalystAgent()

    def trading_analyst_node_handler(state: OrchestratorState) -> dict[str, Any]:
        market_state: MarketIntelligenceState = {
            "messages": list(state.get("messages", [])),
            "context": dict(state.get("context", {})),
            "artifacts": list(state.get("artifacts", [])),
            "signals": list(state.get("signals", [])),
            "decisions": list(state.get("decisions", [])),
            "records": list(state.get("records", [])),
            "portfolio": dict(state.get("portfolio", {})),
            "current_step": str(state.get("current_step", "init")),
            "errors": list(state.get("errors", [])),
        }
        return trading_agent.execute(market_state)

    return trading_analyst_node_handler
