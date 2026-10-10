"""Schema definitions, roles, and configuration for autonomous agents."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentRole(StrEnum):
    """Functional roles for agents in the market intelligence architecture."""

    RESEARCH = "RESEARCH"
    TRADING_ANALYST = "TRADING_ANALYST"
    RISK_MANAGER = "RISK_MANAGER"
    ORCHESTRATOR = "ORCHESTRATOR"
    GENERAL = "GENERAL"


class AgentStatus(StrEnum):
    """Lifecycle status states for an autonomous agent."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    PAUSED = "PAUSED"


class AgentConfig(BaseModel):
    """Configuration specification for instantiating an agent."""

    model_config = ConfigDict(extra="allow")

    name: str
    role: AgentRole = AgentRole.GENERAL
    capabilities: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    timeout_seconds: float = 30.0
    metadata: dict[str, Any] = Field(default_factory=dict)
