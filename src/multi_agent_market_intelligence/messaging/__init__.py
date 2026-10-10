"""Messaging package providing inter-agent communication models and bus."""

from multi_agent_market_intelligence.messaging.adapters import (
    agent_messages_to_state,
    from_state_dict,
    messages_to_agent_messages,
    to_state_dict,
)
from multi_agent_market_intelligence.messaging.bus import (
    MessageBus,
    MessageHandler,
)
from multi_agent_market_intelligence.messaging.models import (
    AgentMessage,
    MessagePriority,
    MessageType,
)

__all__ = [
    "AgentMessage",
    "MessageBus",
    "MessageHandler",
    "MessagePriority",
    "MessageType",
    "agent_messages_to_state",
    "from_state_dict",
    "messages_to_agent_messages",
    "to_state_dict",
]
