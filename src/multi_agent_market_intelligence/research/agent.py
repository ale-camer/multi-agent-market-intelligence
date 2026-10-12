"""Autonomous Research Agent executing news extraction, report loading, and sentiment analysis."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from multi_agent_market_intelligence.agents.base import BaseAgent
from multi_agent_market_intelligence.agents.schema import AgentConfig, AgentRole
from multi_agent_market_intelligence.messaging.bus import MessageBus
from multi_agent_market_intelligence.messaging.models import MessagePriority, MessageType
from multi_agent_market_intelligence.orchestrator.schema import OrchestratorState
from multi_agent_market_intelligence.research.news import (
    NewsExtractor,
    to_research_artifact,
)
from multi_agent_market_intelligence.research.reports import (
    FinancialReportLoader,
    report_to_research_artifact,
)
from multi_agent_market_intelligence.research.sentiment import (
    FinancialSentimentAnalyzer,
    SentimentAnalysisResult,
)
from multi_agent_market_intelligence.state.models import ResearchArtifact
from multi_agent_market_intelligence.state.schema import MarketIntelligenceState


class ResearchAgent(BaseAgent):
    """Autonomous Research Agent responsible for ingesting market disclosures and sentiment."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        message_bus: MessageBus | None = None,
        news_extractor: NewsExtractor | None = None,
        report_loader: FinancialReportLoader | None = None,
        sentiment_analyzer: FinancialSentimentAnalyzer | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        cfg = config or AgentConfig(
            name="research_agent",
            role=AgentRole.RESEARCH,
            capabilities=["news_extraction", "report_loading", "sentiment_analysis"],
        )
        super().__init__(config=cfg, message_bus=message_bus)
        self.news_extractor = news_extractor or NewsExtractor()
        self.report_loader = report_loader or FinancialReportLoader()
        self.sentiment_analyzer = sentiment_analyzer or FinancialSentimentAnalyzer()
        self.symbols = list(symbols) if symbols is not None else ["AAPL"]

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Execute synchronous multi-source research workflow over target symbols.

        Args:
            state: Current market intelligence state.

        Returns:
            Dictionary with state updates: artifacts, messages, context, and current_step.
        """
        context = state.get("context", {})
        target_symbols = self._resolve_target_symbols(context)

        news_limit = int(context.get("news_limit", 3))
        reports_dir = context.get("reports_dir")
        target_sections = context.get("target_sections")

        artifacts_collector: list[ResearchArtifact] = []

        for symbol in target_symbols:
            symbol_sentiments: list[SentimentAnalysisResult] = []

            # 1. Fetch news articles and score sentiment
            articles = self.news_extractor.fetch_news_by_symbol(symbol, limit=news_limit)
            for article in articles:
                sentiment = self.sentiment_analyzer.analyze_article(article)
                symbol_sentiments.append(sentiment)
                artifact = to_research_artifact(article, sentiment_score=sentiment.score)
                artifact.metadata["sentiment_label"] = sentiment.label.value
                artifact.metadata["confidence"] = sentiment.confidence
                artifact.metadata["key_drivers"] = sentiment.key_drivers
                artifact.metadata["breakdown"] = sentiment.breakdown
                artifacts_collector.append(artifact)

            # 2. Ingest or generate financial report and score sentiment
            if reports_dir:
                try:
                    reports = self.report_loader.load_from_directory(reports_dir, symbol=symbol)
                except Exception:
                    reports = []
                if not reports:
                    reports = [self.report_loader.generate_mock_report(symbol)]
            else:
                reports = [self.report_loader.generate_mock_report(symbol)]

            for report in reports:
                rep_sentiment = self.sentiment_analyzer.analyze_report(
                    report,
                    target_sections=target_sections,
                )
                symbol_sentiments.append(rep_sentiment)
                rep_artifact = report_to_research_artifact(
                    report,
                    sentiment_score=rep_sentiment.score,
                )
                rep_artifact.metadata["sentiment_label"] = rep_sentiment.label.value
                rep_artifact.metadata["confidence"] = rep_sentiment.confidence
                rep_artifact.metadata["key_drivers"] = rep_sentiment.key_drivers
                rep_artifact.metadata["breakdown"] = rep_sentiment.breakdown
                artifacts_collector.append(rep_artifact)

            # 3. Compute composite sentiment across news and reports
            composite_sentiment = self.sentiment_analyzer.aggregate_sentiment(symbol_sentiments)

            # 4. Synthesize consolidated market intelligence artifact
            drivers_str = ", ".join(composite_sentiment.key_drivers) or "None"
            summary_text = (
                f"Consolidated intelligence for {symbol}: Overall sentiment is "
                f"{composite_sentiment.label.value} (score: {composite_sentiment.score:+.2f}, "
                f"confidence: {composite_sentiment.confidence:.2f}). "
                f"Key drivers: {drivers_str}. "
                f"Synthesized from {len(articles)} news items and {len(reports)} reports."
            )
            synthesis_artifact = ResearchArtifact(
                headline=f"Market Intelligence Synthesis for {symbol}",
                summary=summary_text,
                sentiment_score=composite_sentiment.score,
                source="research_agent_synthesis",
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "symbol": symbol,
                    "composite_score": composite_sentiment.score,
                    "sentiment_label": composite_sentiment.label.value,
                    "confidence": composite_sentiment.confidence,
                    "key_drivers": composite_sentiment.key_drivers,
                    "news_count": len(articles),
                    "reports_count": len(reports),
                    "is_synthesis": True,
                },
            )
            artifacts_collector.append(synthesis_artifact)

            # 5. Broadcast notification via MessageBus if available
            if self.message_bus is not None:
                self.send_message(
                    recipient="trading_analyst",
                    message_type=MessageType.RESEARCH_REPORT,
                    payload={
                        "symbol": symbol,
                        "composite_score": composite_sentiment.score,
                        "sentiment_label": composite_sentiment.label.value,
                        "confidence": composite_sentiment.confidence,
                        "artifacts_count": len(articles) + len(reports) + 1,
                    },
                    priority=MessagePriority.NORMAL,
                )

        symbols_str = ", ".join(target_symbols)
        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": self.name,
                "content": f"Research analysis completed for {symbols_str}.",
            }
        )

        return {
            "current_step": "research",
            "artifacts": artifacts_collector,
            "messages": messages,
            "context": {
                "target_symbols": target_symbols,
                "research_completed": True,
            },
        }

    async def process_async(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Execute asynchronous multi-source research workflow."""
        return self.process(state)

    def _resolve_target_symbols(self, context: dict[str, Any]) -> list[str]:
        """Resolve ticker symbols from state context or defaults."""
        single_sym = context.get("symbol")
        if single_sym and str(single_sym).strip():
            return [str(single_sym).upper().strip()]

        raw_symbols = context.get("symbols") or context.get("target_symbols")
        if raw_symbols and isinstance(raw_symbols, list):
            resolved = [str(s).upper().strip() for s in raw_symbols if str(s).strip()]
            if resolved:
                return resolved

        return list(self.symbols)


def create_research_node_handler(
    agent: ResearchAgent | None = None,
) -> Callable[[OrchestratorState], dict[str, Any]]:
    """Create an orchestrator-compatible node handler powered by a ResearchAgent instance.

    Args:
        agent: Optional custom ResearchAgent instance.

    Returns:
        Callable compatible with LangGraph Orchestrator node contracts.
    """
    research_agent = agent or ResearchAgent()

    def research_node_handler(state: OrchestratorState) -> dict[str, Any]:
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
        return research_agent.execute(market_state)

    return research_node_handler
