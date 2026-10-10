"""Unit tests for BaseAgent, agent lifecycle, messaging, and orchestrator integration."""

from typing import Any

import pytest

from multi_agent_market_intelligence import (
    AgentConfig,
    AgentRole,
    AgentStatus,
    BaseAgent,
    MarketIntelligenceOrchestrator,
    MarketIntelligenceState,
    MessageBus,
    MessageType,
    NodeNames,
)
from multi_agent_market_intelligence.state.schema import create_market_state


class MockSuccessAgent(BaseAgent):
    """Test agent returning valid state updates."""

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        return {
            "current_step": self.name,
            "context": {"processed_by": self.name},
        }


class MockFailingAgent(BaseAgent):
    """Test agent that raises an exception during execution."""

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        raise ValueError("Simulated processing failure")


class MockAsyncAgent(BaseAgent):
    """Test agent implementing custom native async processing."""

    async def process_async(self, state: MarketIntelligenceState) -> dict[str, Any]:
        return {
            "current_step": self.name,
            "context": {"async_processed": True},
        }

    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        return {"current_step": self.name}


@pytest.mark.issue_4
def test_base_agent_cannot_be_instantiated_directly() -> None:
    """Ensure BaseAgent is abstract and cannot be directly instantiated."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseAgent()  # type: ignore[abstract]


@pytest.mark.issue_4
def test_agent_config_and_roles() -> None:
    """Verify AgentRole and AgentStatus enums and AgentConfig model."""
    assert AgentRole.RESEARCH == "RESEARCH"
    assert AgentRole.TRADING_ANALYST == "TRADING_ANALYST"
    assert AgentRole.RISK_MANAGER == "RISK_MANAGER"
    assert AgentRole.ORCHESTRATOR == "ORCHESTRATOR"

    assert AgentStatus.IDLE == "IDLE"
    assert AgentStatus.RUNNING == "RUNNING"
    assert AgentStatus.SUCCESS == "SUCCESS"
    assert AgentStatus.ERROR == "ERROR"

    config = AgentConfig(
        name="test_agent",
        role=AgentRole.RESEARCH,
        capabilities=["sentiment_analysis"],
        system_prompt="You are a research bot.",
        timeout_seconds=15.0,
        metadata={"version": "1.0"},
    )
    assert config.name == "test_agent"
    assert config.role == AgentRole.RESEARCH
    assert config.capabilities == ["sentiment_analysis"]
    assert config.timeout_seconds == 15.0


@pytest.mark.issue_4
def test_concrete_agent_execution_lifecycle() -> None:
    """Verify agent execution lifecycle: IDLE -> RUNNING -> SUCCESS and record creation."""
    config = AgentConfig(name="research_bot", role=AgentRole.RESEARCH)
    agent = MockSuccessAgent(config=config)

    assert agent.status == AgentStatus.IDLE

    state = create_market_state(context={"symbol": "AAPL"})
    updates = agent.execute(state)

    assert agent.status == AgentStatus.SUCCESS
    assert updates["current_step"] == "research_bot"
    assert updates["context"] == {"processed_by": "research_bot"}

    # Automatic execution record
    assert "records" in updates
    assert len(updates["records"]) == 1
    record = updates["records"][0]
    assert record.agent_name == "research_bot"
    assert record.status == "SUCCESS"
    assert record.execution_time_ms >= 0.0


@pytest.mark.issue_4
@pytest.mark.anyio
async def test_concrete_agent_async_execution() -> None:
    """Verify asynchronous execution and record generation."""
    config = AgentConfig(name="async_bot", role=AgentRole.TRADING_ANALYST)
    agent = MockAsyncAgent(config=config)

    state = create_market_state()
    updates = await agent.execute_async(state)

    assert agent.status == AgentStatus.SUCCESS
    assert updates["context"] == {"async_processed": True}
    assert len(updates["records"]) == 1
    assert updates["records"][0].status == "SUCCESS"


@pytest.mark.issue_4
def test_agent_step_alias() -> None:
    """Verify step() invokes execute()."""
    agent = MockSuccessAgent()
    state = create_market_state()
    res = agent.step(state)

    assert agent.status == AgentStatus.SUCCESS
    assert len(res["records"]) == 1


@pytest.mark.issue_4
def test_agent_error_handling_isolation() -> None:
    """Verify execution exceptions are captured and do not crash unhandled."""
    agent = MockFailingAgent(config=AgentConfig(name="failing_bot"))
    state = create_market_state()

    updates = agent.execute(state)

    assert agent.status == AgentStatus.ERROR
    assert len(updates["records"]) == 1
    record = updates["records"][0]
    assert record.status == "ERROR"
    assert "Simulated processing failure" in record.logs[0]

    assert "errors" in updates
    assert any("Simulated processing failure" in err for err in updates["errors"])


@pytest.mark.issue_4
@pytest.mark.anyio
async def test_agent_async_error_handling_isolation() -> None:
    """Verify async exceptions are captured gracefully."""
    agent = MockFailingAgent(config=AgentConfig(name="async_failing_bot"))
    state = create_market_state()

    updates = await agent.execute_async(state)

    assert agent.status == AgentStatus.ERROR
    assert updates["records"][0].status == "ERROR"
    assert len(updates["errors"]) == 1


@pytest.mark.issue_4
def test_agent_message_bus_communication() -> None:
    """Verify agent sends and receives messages through injected MessageBus."""
    bus = MessageBus()
    agent_a = MockSuccessAgent(
        config=AgentConfig(name="agent_a", role=AgentRole.RESEARCH),
        message_bus=bus,
    )
    agent_b = MockSuccessAgent(
        config=AgentConfig(name="agent_b", role=AgentRole.TRADING_ANALYST),
        message_bus=bus,
    )

    # Agent A sends message to Agent B
    sent_msg = agent_a.send_message(
        recipient="agent_b",
        message_type=MessageType.RESEARCH_REPORT,
        payload={"headline": "Fed rate cut"},
        correlation_id="corr-123",
    )
    assert sent_msg is not None

    # Agent B must have received it in inbox
    assert len(agent_b.inbox) == 1
    received = agent_b.inbox[0]
    assert received.sender == "agent_a"
    assert received.payload == {"headline": "Fed rate cut"}
    assert received.correlation_id == "corr-123"


@pytest.mark.issue_4
def test_agent_send_message_without_bus_returns_none() -> None:
    """Verify send_message returns None when no MessageBus is attached."""
    agent = MockSuccessAgent()
    msg = agent.send_message("other", MessageType.DATA_REQUEST, {})
    assert msg is None


@pytest.mark.issue_4
def test_agent_as_node_handler_integration_with_orchestrator() -> None:
    """Verify plugging BaseAgent instances into MarketIntelligenceOrchestrator."""
    research_agent = MockSuccessAgent(config=AgentConfig(name=NodeNames.RESEARCH))
    analyst_agent = MockSuccessAgent(config=AgentConfig(name=NodeNames.TRADING_ANALYST))
    risk_agent = MockSuccessAgent(config=AgentConfig(name=NodeNames.RISK_MANAGER))

    orchestrator = MarketIntelligenceOrchestrator()
    orchestrator.register_handler(NodeNames.RESEARCH, research_agent.as_node_handler())
    orchestrator.register_handler(NodeNames.TRADING_ANALYST, analyst_agent.as_node_handler())
    orchestrator.register_handler(NodeNames.RISK_MANAGER, risk_agent.as_node_handler())

    initial_state = create_market_state(context={"ticker": "MSFT"})
    final_state = orchestrator.run(initial_state)

    assert final_state["current_step"] == NodeNames.RISK_MANAGER
    assert len(final_state["records"]) == 3
    assert [r.agent_name for r in final_state["records"]] == [
        NodeNames.RESEARCH,
        NodeNames.TRADING_ANALYST,
        NodeNames.RISK_MANAGER,
    ]
    assert all(r.status == "SUCCESS" for r in final_state["records"])
