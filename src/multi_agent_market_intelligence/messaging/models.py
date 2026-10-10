"""Message models and enumerations for inter-agent communication."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageType(StrEnum):
    """Allowed message categorization types for inter-agent messaging."""

    DATA_REQUEST = "DATA_REQUEST"
    RESEARCH_REPORT = "RESEARCH_REPORT"
    SIGNAL_PROPOSAL = "SIGNAL_PROPOSAL"
    RISK_EVALUATION = "RISK_EVALUATION"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    COMMAND = "COMMAND"
    HEARTBEAT = "HEARTBEAT"


class MessagePriority(StrEnum):
    """Priority levels for message routing and queuing."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class AgentMessage(BaseModel):
    """Structured envelope for inter-agent communication."""

    model_config = ConfigDict(extra="allow")

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    recipient: str = "*"
    message_type: MessageType = MessageType.DATA_REQUEST
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def create_reply(
        self,
        sender: str,
        message_type: MessageType,
        payload: dict[str, Any],
        priority: MessagePriority | None = None,
    ) -> "AgentMessage":
        """Create a correlated response message addressing the original sender."""
        return AgentMessage(
            sender=sender,
            recipient=self.sender,
            message_type=message_type,
            payload=payload,
            correlation_id=self.correlation_id,
            priority=priority or self.priority,
        )

    def __eq__(self, other: Any) -> bool:
        """Allow comparison against raw dicts for testing and adapter compatibility."""
        if isinstance(other, dict):
            for k, v in other.items():
                val = getattr(self, k, None)
                if val is None and self.__pydantic_extra__:
                    val = self.__pydantic_extra__.get(k)
                if val != v:
                    return False
            return True
        return super().__eq__(other)
