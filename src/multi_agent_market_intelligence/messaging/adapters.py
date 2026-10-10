"""Adapters converting between AgentMessage and LangGraph state channels."""

from typing import Any

from multi_agent_market_intelligence.messaging.models import (
    AgentMessage,
    MessagePriority,
    MessageType,
)


def to_state_dict(message: AgentMessage) -> dict[str, Any]:
    """Convert an AgentMessage into a dictionary compatible with LangGraph state channels.

    Formats role as the message sender and serializes payload and routing metadata.
    """
    return {
        "role": message.sender,
        "content": str(message.payload.get("content", message.payload.get("summary", ""))),
        "message_id": message.message_id,
        "recipient": message.recipient,
        "message_type": str(message.message_type),
        "correlation_id": message.correlation_id,
        "priority": str(message.priority),
        "payload": message.payload,
        "timestamp": message.timestamp.isoformat(),
        "metadata": message.metadata,
    }


def from_state_dict(data: dict[str, Any]) -> AgentMessage:
    """Reconstruct an AgentMessage from a LangGraph state dictionary."""
    sender = str(data.get("role", data.get("sender", "unknown")))
    recipient = str(data.get("recipient", "*"))

    raw_type = data.get("message_type", MessageType.DATA_REQUEST)
    try:
        msg_type = MessageType(raw_type)
    except ValueError:
        msg_type = MessageType.DATA_REQUEST

    raw_priority = data.get("priority", MessagePriority.NORMAL)
    try:
        priority = MessagePriority(raw_priority)
    except ValueError:
        priority = MessagePriority.NORMAL

    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = {"content": data.get("content", "")}

    kwargs: dict[str, Any] = {
        "sender": sender,
        "recipient": recipient,
        "message_type": msg_type,
        "priority": priority,
        "payload": payload,
        "metadata": data.get("metadata", {}),
    }

    if "message_id" in data:
        kwargs["message_id"] = str(data["message_id"])
    if "correlation_id" in data:
        kwargs["correlation_id"] = str(data["correlation_id"])

    return AgentMessage(**kwargs)


def messages_to_agent_messages(messages: list[dict[str, Any]]) -> list[AgentMessage]:
    """Convert a sequence of raw state dictionaries into AgentMessage instances."""
    return [from_state_dict(m) for m in messages]


def agent_messages_to_state(messages: list[AgentMessage]) -> list[dict[str, Any]]:
    """Convert a sequence of AgentMessage instances into LangGraph state dictionaries."""
    return [to_state_dict(m) for m in messages]
