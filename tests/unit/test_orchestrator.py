"""Unit tests for BaseOrchestrator and MarketIntelligenceOrchestrator."""

from typing import Any

import pytest

from multi_agent_market_intelligence import (
    BaseOrchestrator,
    MarketIntelligenceOrchestrator,
    NodeNames,
    OrchestratorState,
)
from multi_agent_market_intelligence.orchestrator import (
    create_initial_state,
    default_research_handler,
    default_risk_manager_handler,
    default_trading_analyst_handler,
)


@pytest.mark.issue_1
def test_base_orchestrator_cannot_be_instantiated_directly() -> None:
    """Ensure BaseOrchestrator is abstract and cannot be instantiated."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseOrchestrator()  # type: ignore[abstract]


@pytest.mark.issue_1
def test_subclass_without_build_graph_fails() -> None:
    """Ensure subclass lacking build_graph implementation cannot be instantiated."""

    class IncompleteOrchestrator(BaseOrchestrator[OrchestratorState]):
        pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteOrchestrator()  # type: ignore[abstract]


@pytest.mark.issue_1
def test_compiled_graph_access_before_compilation() -> None:
    """Ensure accessing compiled_graph before compile() raises RuntimeError."""
    orchestrator = MarketIntelligenceOrchestrator()
    assert orchestrator.is_compiled is False
    with pytest.raises(RuntimeError, match="has not been compiled yet"):
        _ = orchestrator.compiled_graph


@pytest.mark.issue_1
def test_is_compiled_flag_lifecycle() -> None:
    """Ensure is_compiled accurately reflects the compilation state."""
    orchestrator = MarketIntelligenceOrchestrator()
    assert orchestrator.is_compiled is False
    compiled = orchestrator.compile()
    assert orchestrator.is_compiled is True
    assert orchestrator.compiled_graph is compiled


@pytest.mark.issue_1
def test_graph_builder_and_compiled_structure() -> None:
    """Verify that build_graph defines the expected nodes and connectivity."""
    orchestrator = MarketIntelligenceOrchestrator()
    builder = orchestrator.build_graph()

    expected_nodes = {
        NodeNames.RESEARCH,
        NodeNames.TRADING_ANALYST,
        NodeNames.RISK_MANAGER,
    }
    assert set(builder.nodes.keys()) == expected_nodes

    compiled = orchestrator.compile()
    compiled_nodes = set(compiled.nodes.keys())
    assert expected_nodes.issubset(compiled_nodes)


@pytest.mark.issue_1
def test_default_execution_flow() -> None:
    """Verify default sequential execution: research -> trading_analyst -> risk_manager."""
    orchestrator = MarketIntelligenceOrchestrator()
    initial_state = create_initial_state(context={"symbol": "AAPL"})

    result = orchestrator.run(initial_state)

    assert result["current_step"] == NodeNames.RISK_MANAGER
    assert result["context"] == {"symbol": "AAPL"}
    assert len(result["messages"]) == 3
    assert result["messages"][0]["role"] == NodeNames.RESEARCH
    assert result["messages"][1]["role"] == NodeNames.TRADING_ANALYST
    assert result["messages"][2]["role"] == NodeNames.RISK_MANAGER


@pytest.mark.issue_1
def test_invoke_alias_execution() -> None:
    """Ensure invoke() behaves identically to run()."""
    orchestrator = MarketIntelligenceOrchestrator()
    initial_state = create_initial_state()

    result = orchestrator.invoke(initial_state)

    assert result["current_step"] == NodeNames.RISK_MANAGER
    assert len(result["messages"]) == 3


@pytest.mark.issue_1
def test_custom_handlers_via_constructor() -> None:
    """Verify injecting custom handlers at initialization time."""

    def custom_research(state: OrchestratorState) -> dict[str, Any]:
        return {"current_step": "custom_research", "signals": [{"source": "news", "score": 0.85}]}

    def custom_analyst(state: OrchestratorState) -> dict[str, Any]:
        signals = list(state.get("signals", []))
        signals.append({"source": "technical", "action": "BUY"})
        return {"current_step": "custom_analyst", "signals": signals}

    def custom_risk(state: OrchestratorState) -> dict[str, Any]:
        return {
            "current_step": "custom_risk",
            "decisions": [{"approved": True, "size": 100}],
        }

    orchestrator = MarketIntelligenceOrchestrator(
        research_handler=custom_research,
        trading_analyst_handler=custom_analyst,
        risk_manager_handler=custom_risk,
    )
    result = orchestrator.run(create_initial_state())

    assert result["current_step"] == "custom_risk"
    assert len(result["signals"]) == 2
    assert result["decisions"] == [{"approved": True, "size": 100}]


@pytest.mark.issue_1
def test_register_handler_overrides_and_invalidates_cache() -> None:
    """Verify handler replacement and compilation cache invalidation."""
    orchestrator = MarketIntelligenceOrchestrator()
    orchestrator.compile()
    assert orchestrator.is_compiled is True

    def override_analyst(state: OrchestratorState) -> dict[str, Any]:
        return {"current_step": "overridden_analyst"}

    orchestrator.register_handler(NodeNames.TRADING_ANALYST, override_analyst)
    # Registration must invalidate existing compiled graph
    assert orchestrator.is_compiled is False

    assert orchestrator.get_handler(NodeNames.TRADING_ANALYST) is override_analyst

    result = orchestrator.run(create_initial_state())
    assert result["current_step"] == NodeNames.RISK_MANAGER


@pytest.mark.issue_1
def test_register_handler_unknown_node_raises_value_error() -> None:
    """Verify registering a handler for an invalid node identifier raises ValueError."""
    orchestrator = MarketIntelligenceOrchestrator()

    with pytest.raises(ValueError, match="Unknown node 'unknown_agent'"):
        orchestrator.register_handler("unknown_agent", lambda s: {})


@pytest.mark.issue_1
def test_get_handler_invalid_node_raises_key_error() -> None:
    """Verify get_handler raises KeyError for unmanaged nodes."""
    orchestrator = MarketIntelligenceOrchestrator()

    with pytest.raises(KeyError, match="Node 'unknown_agent' is not registered"):
        orchestrator.get_handler("unknown_agent")


@pytest.mark.issue_1
def test_invalid_initial_state_type_raises_type_error() -> None:
    """Verify TypeError is raised when initial_state is not a dictionary."""
    orchestrator = MarketIntelligenceOrchestrator()

    with pytest.raises(TypeError, match="initial_state must be a dictionary"):
        orchestrator.run("not a dict")  # type: ignore[arg-type]


@pytest.mark.issue_1
@pytest.mark.anyio
async def test_async_arun_and_ainvoke_execution() -> None:
    """Verify asynchronous execution methods arun and ainvoke."""
    orchestrator = MarketIntelligenceOrchestrator()
    initial_state = create_initial_state(context={"mode": "async"})

    res_arun = await orchestrator.arun(initial_state)
    assert res_arun["current_step"] == NodeNames.RISK_MANAGER
    assert res_arun["context"] == {"mode": "async"}

    res_ainvoke = await orchestrator.ainvoke(initial_state)
    assert res_ainvoke["current_step"] == NodeNames.RISK_MANAGER


@pytest.mark.issue_1
def test_create_initial_state_defaults() -> None:
    """Verify factory initializes default collections cleanly."""
    state = create_initial_state()
    assert state["messages"] == []
    assert state["context"] == {}
    assert state["signals"] == []
    assert state["decisions"] == []
    assert state["current_step"] == "init"
    assert state["errors"] == []


@pytest.mark.issue_1
def test_default_handlers_isolated_execution() -> None:
    """Verify isolated execution of individual default handlers."""
    base_state = create_initial_state()

    res_r = default_research_handler(base_state)
    assert res_r["current_step"] == NodeNames.RESEARCH
    assert len(res_r["messages"]) == 1

    res_t = default_trading_analyst_handler(base_state)
    assert res_t["current_step"] == NodeNames.TRADING_ANALYST
    assert len(res_t["messages"]) == 1

    res_rm = default_risk_manager_handler(base_state)
    assert res_rm["current_step"] == NodeNames.RISK_MANAGER
    assert len(res_rm["messages"]) == 1
