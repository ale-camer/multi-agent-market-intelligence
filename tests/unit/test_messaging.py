"""Unit tests for inter-agent messaging models, message bus, and adapters."""

import pytest

from multi_agent_market_intelligence import (
    AgentMessage,
    MessageBus,
    MessagePriority,
    MessageType,
)
from multi_agent_market_intelligence.messaging.adapters import (
    agent_messages_to_state,
    from_state_dict,
    messages_to_agent_messages,
    to_state_dict,
)


@pytest.mark.issue_3
def test_message_type_and_priority_enums() -> None:
    """Verify enum members and values."""
    assert MessageType.DATA_REQUEST == "DATA_REQUEST"
    assert MessageType.RESEARCH_REPORT == "RESEARCH_REPORT"
    assert MessageType.SIGNAL_PROPOSAL == "SIGNAL_PROPOSAL"
    assert MessageType.RISK_EVALUATION == "RISK_EVALUATION"
    assert MessageType.SYSTEM_ALERT == "SYSTEM_ALERT"

    assert MessagePriority.LOW == "LOW"
    assert MessagePriority.NORMAL == "NORMAL"
    assert MessagePriority.HIGH == "HIGH"
    assert MessagePriority.URGENT == "URGENT"


@pytest.mark.issue_3
def test_agent_message_defaults_and_fields() -> None:
    """Verify default UUID generation and field initialization."""
    msg = AgentMessage(sender="research_agent")

    assert msg.sender == "research_agent"
    assert msg.recipient == "*"
    assert msg.message_type == MessageType.DATA_REQUEST
    assert msg.priority == MessagePriority.NORMAL
    assert len(msg.message_id) == 36
    assert len(msg.correlation_id) == 36
    assert msg.payload == {}


@pytest.mark.issue_3
def test_agent_message_create_reply() -> None:
    """Verify create_reply swaps sender/recipient and maintains correlation_id."""
    initial = AgentMessage(
        sender="research_agent",
        recipient="trading_analyst",
        message_type=MessageType.RESEARCH_REPORT,
        payload={"sentiment": 0.8},
    )

    reply = initial.create_reply(
        sender="trading_analyst",
        message_type=MessageType.SIGNAL_PROPOSAL,
        payload={"signal": "BUY"},
    )

    assert reply.sender == "trading_analyst"
    assert reply.recipient == "research_agent"
    assert reply.correlation_id == initial.correlation_id
    assert reply.message_id != initial.message_id
    assert reply.message_type == MessageType.SIGNAL_PROPOSAL
    assert reply.payload == {"signal": "BUY"}


@pytest.mark.issue_3
def test_agent_message_equality_with_dict() -> None:
    """Verify AgentMessage supports equality comparison with dictionaries."""
    msg = AgentMessage(
        sender="risk_manager",
        recipient="orchestrator",
        message_type=MessageType.RISK_EVALUATION,
    )
    assert msg == {"sender": "risk_manager", "recipient": "orchestrator"}
    assert msg != {"sender": "other_agent"}


@pytest.mark.issue_3
def test_message_bus_subscribe_and_unsubscribe() -> None:
    """Verify subscription management."""
    bus = MessageBus()
    received: list[AgentMessage] = []

    def handler(msg: AgentMessage) -> None:
        received.append(msg)

    bus.subscribe("trading_analyst", handler)
    assert handler in bus.get_subscribers("trading_analyst")

    # Duplicate subscription is ignored
    bus.subscribe("trading_analyst", handler)
    assert len(bus.get_subscribers("trading_analyst")) == 1

    # Unsubscribe
    assert bus.unsubscribe("trading_analyst", handler) is True
    assert handler not in bus.get_subscribers("trading_analyst")
    assert bus.unsubscribe("unknown", handler) is False


@pytest.mark.issue_3
def test_message_bus_direct_routing() -> None:
    """Verify messages are routed to explicit recipient subscribers."""
    bus = MessageBus()
    analyst_inbox: list[AgentMessage] = []
    risk_inbox: list[AgentMessage] = []

    bus.subscribe("trading_analyst", lambda m: analyst_inbox.append(m))
    bus.subscribe("risk_manager", lambda m: risk_inbox.append(m))

    msg1 = AgentMessage(sender="research", recipient="trading_analyst", payload={"data": 1})
    bus.publish(msg1)

    assert len(analyst_inbox) == 1
    assert len(risk_inbox) == 0
    assert analyst_inbox[0].payload == {"data": 1}

    msg2 = AgentMessage(sender="analyst", recipient="risk_manager", payload={"data": 2})
    bus.publish(msg2)

    assert len(analyst_inbox) == 1
    assert len(risk_inbox) == 1


@pytest.mark.issue_3
def test_message_bus_wildcard_routing() -> None:
    """Verify wildcard subscribers receive all messages."""
    bus = MessageBus()
    wildcard_inbox: list[AgentMessage] = []

    bus.subscribe("*", lambda m: wildcard_inbox.append(m))

    bus.publish(AgentMessage(sender="a", recipient="b"))
    bus.publish(AgentMessage(sender="c", recipient="*"))

    assert len(wildcard_inbox) == 2


@pytest.mark.issue_3
def test_message_bus_type_routing() -> None:
    """Verify subscribers can filter messages by message type."""
    bus = MessageBus()
    alerts: list[AgentMessage] = []

    bus.subscribe("type:SYSTEM_ALERT", lambda m: alerts.append(m))

    bus.publish(AgentMessage(sender="monitor", message_type=MessageType.DATA_REQUEST))
    bus.publish(AgentMessage(sender="monitor", message_type=MessageType.SYSTEM_ALERT))

    assert len(alerts) == 1
    assert alerts[0].message_type == MessageType.SYSTEM_ALERT


@pytest.mark.issue_3
def test_message_bus_dead_letter() -> None:
    """Verify messages with unhandled recipients are logged as dead letters."""
    bus = MessageBus()
    msg = AgentMessage(sender="research", recipient="unregistered_agent")

    bus.publish(msg)

    assert len(bus.dead_letters) == 1
    assert bus.dead_letters[0] == msg


@pytest.mark.issue_3
def test_message_bus_history_and_filters() -> None:
    """Verify history audit tracking and filtering."""
    bus = MessageBus()

    m1 = AgentMessage(sender="research", recipient="trading_analyst")
    m2 = AgentMessage(sender="trading_analyst", recipient="risk_manager")
    m3 = AgentMessage(sender="research", recipient="risk_manager")

    bus.publish(m1)
    bus.publish(m2)
    bus.publish(m3)

    assert len(bus.history) == 3
    assert len(bus.get_history(sender="research")) == 2
    assert len(bus.get_history(recipient="risk_manager")) == 2
    assert len(bus.get_history(sender="research", recipient="trading_analyst")) == 1


@pytest.mark.issue_3
def test_message_bus_conversation_correlation() -> None:
    """Verify complete multi-step conversation thread tracking by correlation_id."""
    bus = MessageBus()

    msg1 = AgentMessage(
        sender="research",
        recipient="trading_analyst",
        message_type=MessageType.RESEARCH_REPORT,
    )
    reply1 = msg1.create_reply(
        sender="trading_analyst",
        message_type=MessageType.SIGNAL_PROPOSAL,
        payload={"action": "BUY"},
    )
    reply2 = reply1.create_reply(
        sender="risk_manager",
        message_type=MessageType.RISK_EVALUATION,
        payload={"status": "APPROVED"},
    )

    unrelated = AgentMessage(sender="heartbeat", recipient="*")

    bus.publish(msg1)
    bus.publish(unrelated)
    bus.publish(reply1)
    bus.publish(reply2)

    conversation = bus.get_conversation(msg1.correlation_id)
    assert len(conversation) == 3
    assert [m.sender for m in conversation] == ["research", "trading_analyst", "risk_manager"]


@pytest.mark.issue_3
@pytest.mark.anyio
async def test_message_bus_async_publish() -> None:
    """Verify async message publishing and handler execution."""
    bus = MessageBus()
    received: list[str] = []

    async def async_handler(msg: AgentMessage) -> None:
        received.append(msg.sender)

    bus.subscribe("target", async_handler)
    await bus.publish_async(AgentMessage(sender="async_sender", recipient="target"))

    assert received == ["async_sender"]


@pytest.mark.issue_3
def test_message_bus_clear() -> None:
    """Verify clear() resets subscribers, history, and dead letters."""
    bus = MessageBus()
    bus.subscribe("target", lambda m: None)
    bus.publish(AgentMessage(sender="s", recipient="nowhere"))

    assert len(bus.history) == 1
    assert len(bus.dead_letters) == 1
    assert len(bus.get_subscribers("target")) == 1

    bus.clear()

    assert len(bus.history) == 0
    assert len(bus.dead_letters) == 0
    assert len(bus.get_subscribers("target")) == 0


@pytest.mark.issue_3
def test_state_adapters_roundtrip() -> None:
    """Verify bidirectional conversion between AgentMessage and LangGraph state dictionaries."""
    msg = AgentMessage(
        sender="trading_analyst",
        recipient="risk_manager",
        message_type=MessageType.SIGNAL_PROPOSAL,
        payload={"symbol": "AAPL", "action": "BUY"},
        priority=MessagePriority.HIGH,
        metadata={"cycle": 1},
    )

    state_dict = to_state_dict(msg)
    assert state_dict["role"] == "trading_analyst"
    assert state_dict["recipient"] == "risk_manager"
    assert state_dict["message_type"] == "SIGNAL_PROPOSAL"
    assert state_dict["priority"] == "HIGH"
    assert state_dict["payload"] == {"symbol": "AAPL", "action": "BUY"}

    restored = from_state_dict(state_dict)
    assert restored.sender == msg.sender
    assert restored.recipient == msg.recipient
    assert restored.message_id == msg.message_id
    assert restored.correlation_id == msg.correlation_id
    assert restored.message_type == msg.message_type
    assert restored.priority == msg.priority
    assert restored.payload == msg.payload

    # Batch helpers
    batch_dicts = agent_messages_to_state([msg])
    assert len(batch_dicts) == 1
    batch_models = messages_to_agent_messages(batch_dicts)
    assert len(batch_models) == 1
    assert batch_models[0].message_id == msg.message_id
