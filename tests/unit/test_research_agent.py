"""Unit tests for ResearchAgent execution flow, state integration, and orchestrator adapter."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from multi_agent_market_intelligence.agents import (
    AgentConfig,
    AgentRole,
    AgentStatus,
    ResearchAgent,
)
from multi_agent_market_intelligence.messaging import MessageBus
from multi_agent_market_intelligence.orchestrator import (
    MarketIntelligenceOrchestrator,
    create_initial_state,
)
from multi_agent_market_intelligence.research import (
    create_research_node_handler,
)
from multi_agent_market_intelligence.state import (
    create_market_state,
)


@pytest.mark.issue_9
def test_research_agent_initialization_defaults() -> None:
    """Ensure ResearchAgent initializes with standard defaults."""
    agent = ResearchAgent()

    assert agent.name == "research_agent"
    assert agent.role == AgentRole.RESEARCH
    assert agent.status == AgentStatus.IDLE
    assert agent.symbols == ["AAPL"]
    assert agent.news_extractor is not None
    assert agent.report_loader is not None
    assert agent.sentiment_analyzer is not None


@pytest.mark.issue_9
def test_research_agent_initialization_custom() -> None:
    """Ensure ResearchAgent respects custom configuration and dependencies."""
    bus = MessageBus()
    config = AgentConfig(
        name="custom_analyst",
        role=AgentRole.RESEARCH,
        capabilities=["custom_signals"],
    )
    agent = ResearchAgent(
        config=config,
        message_bus=bus,
        symbols=["NVDA", "MSFT"],
    )

    assert agent.name == "custom_analyst"
    assert agent.role == AgentRole.RESEARCH
    assert agent.symbols == ["NVDA", "MSFT"]
    assert agent.message_bus is bus


@pytest.mark.issue_9
def test_research_agent_process_single_symbol() -> None:
    """Ensure process extracts news, reports, and generates synthesis for a single symbol."""
    agent = ResearchAgent()
    state = create_market_state(context={"symbol": "TSLA", "news_limit": 2})

    updates = agent.process(state)

    assert updates["current_step"] == "research"
    assert updates["context"]["research_completed"] is True
    assert updates["context"]["target_symbols"] == ["TSLA"]

    artifacts = updates["artifacts"]
    # 2 news articles + 1 report + 1 synthesis = 4 artifacts
    assert len(artifacts) == 4

    # Verify news artifacts
    news_artifacts = [
        a for a in artifacts if not a.metadata.get("is_synthesis") and "10-" not in a.headline
    ]
    assert len(news_artifacts) == 2
    for na in news_artifacts:
        assert na.metadata["symbol"] == "TSLA"
        assert "sentiment_label" in na.metadata

    # Verify synthesis artifact
    synthesis = [a for a in artifacts if a.metadata.get("is_synthesis") is True]
    assert len(synthesis) == 1
    syn = synthesis[0]
    assert syn.headline == "Market Intelligence Synthesis for TSLA"
    assert syn.metadata["symbol"] == "TSLA"
    assert syn.metadata["news_count"] == 2
    assert syn.metadata["reports_count"] == 1


@pytest.mark.issue_9
def test_research_agent_process_multiple_symbols() -> None:
    """Ensure process correctly iterates over multiple target tickers."""
    agent = ResearchAgent()
    state = create_market_state(context={"symbols": ["AAPL", "GOOGL"], "news_limit": 1})

    updates = agent.process(state)

    target_symbols = updates["context"]["target_symbols"]
    assert target_symbols == ["AAPL", "GOOGL"]

    artifacts = updates["artifacts"]
    # Per symbol: 1 news + 1 report + 1 synthesis = 3 * 2 = 6 artifacts
    assert len(artifacts) == 6

    syntheses = [a for a in artifacts if a.metadata.get("is_synthesis") is True]
    assert len(syntheses) == 2
    syn_symbols = {s.metadata["symbol"] for s in syntheses}
    assert syn_symbols == {"AAPL", "GOOGL"}


@pytest.mark.issue_9
def test_research_agent_process_fallback_symbols() -> None:
    """Ensure process defaults to agent.symbols when context lacks symbol info."""
    agent = ResearchAgent(symbols=["NVDA"])
    state = create_market_state(context={})

    updates = agent.process(state)

    assert updates["context"]["target_symbols"] == ["NVDA"]
    assert any(a.metadata.get("symbol") == "NVDA" for a in updates["artifacts"])


@pytest.mark.issue_9
def test_research_agent_message_bus_broadcast() -> None:
    """Ensure agent publishes notifications to the MessageBus during execution."""
    bus = MessageBus()
    received_messages: list[dict[str, object]] = []

    def subscriber(msg: object) -> None:
        received_messages.append({"received": True})

    bus.subscribe("trading_analyst", subscriber)

    agent = ResearchAgent(message_bus=bus)
    state = create_market_state(context={"symbol": "MSFT", "news_limit": 1})

    agent.process(state)

    assert len(received_messages) > 0


@pytest.mark.issue_9
def test_research_agent_execute_template_lifecycle() -> None:
    """Ensure BaseAgent.execute tracks status transitions and records audit logs."""
    agent = ResearchAgent()
    state = create_market_state(context={"symbol": "AAPL", "news_limit": 1})

    assert agent.status == AgentStatus.IDLE
    result = agent.execute(state)

    assert agent.status == AgentStatus.SUCCESS
    assert "records" in result
    assert len(result["records"]) == 1

    rec = result["records"][0]
    assert rec.agent_name == "research_agent"
    assert rec.status == "SUCCESS"
    assert rec.execution_time_ms > 0.0


@pytest.mark.issue_9
def test_research_agent_with_custom_reports_dir(tmp_path: Path) -> None:
    """Ensure process utilizes financial reports loaded from a custom directory."""
    report_file = tmp_path / "AAPL_10-Q_2026-Q1.txt"
    report_content = (
        "Symbol: AAPL\nPeriod: 2026-Q1\n\n"
        "## Management Discussion\nCustom file loaded successfully."
    )
    report_file.write_text(report_content, encoding="utf-8")

    agent = ResearchAgent()
    state = create_market_state(
        context={
            "symbol": "AAPL",
            "reports_dir": str(tmp_path),
            "news_limit": 1,
        }
    )

    updates = agent.process(state)
    artifacts = updates["artifacts"]

    report_artifacts = [
        a for a in artifacts if "10-Q" in a.headline and not a.metadata.get("is_synthesis")
    ]
    assert len(report_artifacts) >= 1


@pytest.mark.issue_9
def test_create_research_node_handler_standalone() -> None:
    """Ensure create_research_node_handler returns a callable compatible with OrchestratorState."""
    agent = ResearchAgent()
    handler = create_research_node_handler(agent)

    state = create_initial_state()
    state["context"] = {"symbol": "AAPL", "news_limit": 1}

    result = handler(state)

    assert result["current_step"] == "research"
    assert len(result["artifacts"]) >= 3
    assert len(result["records"]) == 1


@pytest.mark.issue_9
def test_research_node_handler_integrated_with_orchestrator() -> None:
    """Ensure ResearchAgent node handler integrates smoothly with MarketIntelligenceOrchestrator."""
    agent = ResearchAgent()
    handler = create_research_node_handler(agent)

    orchestrator = MarketIntelligenceOrchestrator(research_handler=handler)
    orchestrator.compile()

    state = create_initial_state()
    state["context"] = {"symbol": "AAPL", "news_limit": 1}

    final_state = orchestrator.run(state)

    assert final_state["current_step"] == "risk_manager"
    assert len(final_state["artifacts"]) >= 3
    # Ensure research execution record is present
    research_records = [r for r in final_state["records"] if r.agent_name == "research_agent"]
    assert len(research_records) == 1
    assert research_records[0].status == "SUCCESS"


@pytest.mark.issue_9
def test_research_agent_error_handling_in_execute() -> None:
    """Ensure BaseAgent.execute isolates exceptions, sets ERROR status, and adds audit record."""
    agent = ResearchAgent()
    agent.process = MagicMock(side_effect=RuntimeError("Data provider crashed"))  # type: ignore[method-assign]

    state = create_market_state(context={"symbol": "AAPL"})
    result = agent.execute(state)

    assert agent.status == AgentStatus.ERROR
    assert len(result["records"]) == 1
    assert result["records"][0].status == "ERROR"
    assert "errors" in result
    assert any("Data provider crashed" in err for err in result["errors"])
