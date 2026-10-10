"""Unit tests for state management models, reducers, and protocols."""

from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from multi_agent_market_intelligence import (
    AgentExecutionRecord,
    DecisionStatus,
    MarketIntelligenceOrchestrator,
    MarketIntelligenceState,
    NodeNames,
    PortfolioSnapshot,
    Position,
    ResearchArtifact,
    RiskDecision,
    SignalAction,
    StateContainer,
    StateProtocol,
    TradingSignal,
)
from multi_agent_market_intelligence.state.reducers import (
    append_artifacts,
    append_decisions,
    append_errors,
    append_messages,
    append_records,
    append_signals,
    merge_dict,
)
from multi_agent_market_intelligence.state.schema import create_market_state


@pytest.mark.issue_2
def test_signal_action_and_decision_status_enums() -> None:
    """Verify enum members and values."""
    assert SignalAction.BUY == "BUY"
    assert SignalAction.SELL == "SELL"
    assert SignalAction.HOLD == "HOLD"

    assert DecisionStatus.APPROVED == "APPROVED"
    assert DecisionStatus.REJECTED == "REJECTED"
    assert DecisionStatus.MODIFIED == "MODIFIED"


@pytest.mark.issue_2
def test_research_artifact_valid_and_bounds() -> None:
    """Verify ResearchArtifact validation and boundary checks."""
    artifact = ResearchArtifact(
        headline="Tech Rally",
        summary="Positive sentiment in tech sector",
        sentiment_score=0.75,
        source="Bloomberg",
    )
    assert artifact.headline == "Tech Rally"
    assert artifact.sentiment_score == 0.75
    assert artifact.source == "Bloomberg"
    assert isinstance(artifact.timestamp, datetime)

    # Valid boundaries
    assert (
        ResearchArtifact(headline="Max", summary="Max", sentiment_score=1.0).sentiment_score == 1.0
    )
    assert (
        ResearchArtifact(headline="Min", summary="Min", sentiment_score=-1.0).sentiment_score
        == -1.0
    )

    # Invalid boundary values
    with pytest.raises(ValidationError):
        ResearchArtifact(headline="High", summary="High", sentiment_score=1.1)

    with pytest.raises(ValidationError):
        ResearchArtifact(headline="Low", summary="Low", sentiment_score=-1.1)


@pytest.mark.issue_2
def test_trading_signal_valid_and_bounds() -> None:
    """Verify TradingSignal validation, defaults, and boundary checks."""
    signal = TradingSignal(
        symbol="AAPL",
        action=SignalAction.BUY,
        confidence=0.9,
        target_price=220.0,
        stop_loss=195.0,
        reasoning="Golden cross detected",
    )
    assert signal.symbol == "AAPL"
    assert signal.action == SignalAction.BUY
    assert signal.confidence == 0.9

    # Valid boundaries
    assert TradingSignal(confidence=0.0).confidence == 0.0
    assert TradingSignal(confidence=1.0).confidence == 1.0

    # Invalid boundaries
    with pytest.raises(ValidationError):
        TradingSignal(confidence=-0.1)

    with pytest.raises(ValidationError):
        TradingSignal(confidence=1.1)


@pytest.mark.issue_2
def test_risk_decision_validation() -> None:
    """Verify RiskDecision validation and negative size check."""
    decision = RiskDecision(
        status=DecisionStatus.APPROVED,
        approved_size=150.0,
        max_loss_limit=500.0,
        reason="Within VAR limits",
    )
    assert decision.status == DecisionStatus.APPROVED
    assert decision.approved_size == 150.0

    with pytest.raises(ValidationError):
        RiskDecision(approved_size=-10.0)


@pytest.mark.issue_2
def test_position_and_portfolio_snapshot() -> None:
    """Verify Position and PortfolioSnapshot models."""
    pos = Position(
        symbol="MSFT",
        quantity=50.0,
        entry_price=400.0,
        current_price=410.0,
        unrealized_pnl=500.0,
    )
    snapshot = PortfolioSnapshot(
        cash=10000.0,
        positions={"MSFT": pos},
        total_equity=30500.0,
    )
    assert snapshot.cash == 10000.0
    assert snapshot.positions["MSFT"].unrealized_pnl == 500.0
    assert snapshot.total_equity == 30500.0


@pytest.mark.issue_2
def test_agent_execution_record() -> None:
    """Verify AgentExecutionRecord fields."""
    rec = AgentExecutionRecord(
        agent_name="research_agent",
        step="news_parse",
        status="SUCCESS",
        execution_time_ms=120.5,
        logs=["Extracted 5 articles"],
    )
    assert rec.agent_name == "research_agent"
    assert rec.execution_time_ms == 120.5
    assert len(rec.logs) == 1


@pytest.mark.issue_2
def test_reducer_append_signals() -> None:
    """Verify append_signals reducer behavior and conversions."""
    assert append_signals(None, None) == []

    sig1 = TradingSignal(symbol="NVDA", action=SignalAction.BUY, confidence=0.85)
    res = append_signals(None, sig1)
    assert len(res) == 1
    assert res[0].symbol == "NVDA"

    # Append from dict
    dict_sig = {"symbol": "TSLA", "action": "SELL", "confidence": 0.7}
    res2 = append_signals(res, dict_sig)
    assert len(res2) == 2
    assert res2[1].symbol == "TSLA"
    assert res2[1].action == SignalAction.SELL

    # Cumulative deduplication
    cumulative = [res2[0], res2[1], TradingSignal(symbol="AMD", confidence=0.6)]
    res3 = append_signals(res2, cumulative)
    assert len(res3) == 3
    assert res3[2].symbol == "AMD"

    with pytest.raises(TypeError):
        append_signals(res3, 12345)  # type: ignore[arg-type]


@pytest.mark.issue_2
def test_reducer_append_artifacts() -> None:
    """Verify append_artifacts reducer behavior."""
    assert append_artifacts(None, None) == []

    art = ResearchArtifact(headline="CPI Report", summary="Inflation steady", sentiment_score=0.1)
    res = append_artifacts([], [art])
    assert len(res) == 1

    # Append from dict
    res2 = append_artifacts(
        res, {"headline": "Earnings", "summary": "Beats", "sentiment_score": 0.5}
    )
    assert len(res2) == 2
    assert res2[1].headline == "Earnings"

    with pytest.raises(TypeError):
        append_artifacts(res2, "invalid")  # type: ignore[arg-type]


@pytest.mark.issue_2
def test_reducer_append_decisions() -> None:
    """Verify append_decisions reducer behavior."""
    assert append_decisions(None, None) == []

    dec = RiskDecision(status=DecisionStatus.REJECTED, reason="Over exposure")
    res = append_decisions(None, dec)
    assert len(res) == 1
    assert res[0].status == DecisionStatus.REJECTED

    # Append from dict
    res2 = append_decisions(res, {"status": "APPROVED", "approved_size": 25.0})
    assert len(res2) == 2
    assert res2[1].status == DecisionStatus.APPROVED

    with pytest.raises(TypeError):
        append_decisions(res2, 999)  # type: ignore[arg-type]


@pytest.mark.issue_2
def test_reducer_append_records_messages_errors() -> None:
    """Verify reducers for records, messages, and errors."""
    assert append_records(None, None) == []
    rec = AgentExecutionRecord(agent_name="analyst", step="eval")
    assert len(append_records(None, rec)) == 1

    assert append_messages(None, None) == []
    assert len(append_messages([{"role": "user"}], [{"role": "agent"}])) == 2

    assert append_errors(None, None) == []
    assert append_errors(["err1"], "err2") == ["err1", "err2"]


@pytest.mark.issue_2
def test_reducer_merge_dict() -> None:
    """Verify merge_dict reducer preserves existing keys while applying updates."""
    base = {"a": 1, "b": 2}
    merged = merge_dict(base, {"b": 20, "c": 30})
    assert merged == {"a": 1, "b": 20, "c": 30}
    assert merge_dict(None, {"x": 10}) == {"x": 10}


@pytest.mark.issue_2
def test_state_container_protocol_conformance() -> None:
    """Verify StateContainer conforms to StateProtocol."""
    raw_state = {
        "current_step": "trading_analyst",
        "artifacts": [{"headline": "Macro", "summary": "Neutral", "sentiment_score": 0.0}],
        "signals": [{"symbol": "GOOG", "action": "BUY", "confidence": 0.95}],
        "decisions": [{"status": "APPROVED", "approved_size": 10.0}],
    }
    container = StateContainer(raw_state)

    # Runtime Protocol check
    assert isinstance(container, StateProtocol)

    artifacts = container.get_artifacts()
    assert len(artifacts) == 1
    assert artifacts[0].headline == "Macro"

    signals = container.get_signals()
    assert len(signals) == 1
    assert signals[0].symbol == "GOOG"

    decisions = container.get_decisions()
    assert len(decisions) == 1
    assert decisions[0].status == DecisionStatus.APPROVED

    # Snapshot deepcopy test
    snap = container.snapshot()
    assert snap["current_step"] == "trading_analyst"
    snap["current_step"] = "mutated"
    assert container.current_step == "trading_analyst"


@pytest.mark.issue_2
def test_state_container_transitions() -> None:
    """Verify state transition validation logic."""
    container = StateContainer({"current_step": "init"})
    assert container.validate_transition("research") is True
    assert container.validate_transition("risk_manager") is False

    container = StateContainer({"current_step": "research"})
    assert container.validate_transition("trading_analyst") is True
    assert container.validate_transition("complete") is False


@pytest.mark.issue_2
def test_create_market_state_factory() -> None:
    """Verify create_market_state factory initializes all channels."""
    state = create_market_state()
    assert state["messages"] == []
    assert state["context"] == {}
    assert state["artifacts"] == []
    assert state["signals"] == []
    assert state["decisions"] == []
    assert state["records"] == []
    assert state["portfolio"] == {}
    assert state["current_step"] == "init"
    assert state["errors"] == []


@pytest.mark.issue_2
def test_orchestrator_execution_with_typed_state() -> None:
    """Verify full DAG execution with MarketIntelligenceOrchestrator producing typed state."""

    def custom_research(state: MarketIntelligenceState) -> dict[str, Any]:
        artifact = ResearchArtifact(
            headline="Earnings surprise",
            summary="Strong Q3 beat",
            sentiment_score=0.8,
            source="SEC",
        )
        return {
            "current_step": NodeNames.RESEARCH,
            "artifacts": [artifact],
        }

    def custom_analyst(state: MarketIntelligenceState) -> dict[str, Any]:
        artifacts = state.get("artifacts", [])
        assert len(artifacts) == 1
        signal = TradingSignal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.88,
            target_price=230.0,
            stop_loss=205.0,
            reasoning=f"High sentiment: {artifacts[0].headline}",
        )
        return {
            "current_step": NodeNames.TRADING_ANALYST,
            "signals": [signal],
        }

    def custom_risk(state: MarketIntelligenceState) -> dict[str, Any]:
        signals = state.get("signals", [])
        assert len(signals) == 1
        decision = RiskDecision(
            status=DecisionStatus.APPROVED,
            original_signal=signals[0],
            approved_size=100.0,
            reason="Risk approved within 2% threshold",
        )
        return {
            "current_step": NodeNames.RISK_MANAGER,
            "decisions": [decision],
        }

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=custom_research,
        trading_analyst_handler=custom_analyst,
        risk_manager_handler=custom_risk,
    )

    initial_state = create_market_state(context={"ticker": "AAPL"})
    final_state = orchestrator.run(initial_state)

    assert final_state["current_step"] == NodeNames.RISK_MANAGER
    assert len(final_state["artifacts"]) == 1
    assert final_state["artifacts"][0].headline == "Earnings surprise"
    assert len(final_state["signals"]) == 1
    assert final_state["signals"][0].symbol == "AAPL"
    assert len(final_state["decisions"]) == 1
    assert final_state["decisions"][0].status == DecisionStatus.APPROVED
    assert final_state["decisions"][0].approved_size == 100.0
