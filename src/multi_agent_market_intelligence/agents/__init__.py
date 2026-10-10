"""Agents package providing BaseAgent and agent configuration schemas."""

from multi_agent_market_intelligence.agents.base import BaseAgent
from multi_agent_market_intelligence.agents.schema import (
    AgentConfig,
    AgentRole,
    AgentStatus,
)

__all__ = [
    "AgentConfig",
    "AgentRole",
    "AgentStatus",
    "BaseAgent",
]
