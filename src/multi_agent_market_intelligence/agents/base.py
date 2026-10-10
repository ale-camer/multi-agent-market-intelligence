"""Base agent abstract class establishing execution and communication contracts."""

import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from multi_agent_market_intelligence.agents.schema import (
    AgentConfig,
    AgentRole,
    AgentStatus,
)
from multi_agent_market_intelligence.messaging.bus import MessageBus
from multi_agent_market_intelligence.messaging.models import (
    AgentMessage,
    MessagePriority,
    MessageType,
)
from multi_agent_market_intelligence.state.models import AgentExecutionRecord
from multi_agent_market_intelligence.state.schema import MarketIntelligenceState


class BaseAgent(ABC):
    """Abstract base class for all specialized domain agents.

    Subclasses implement domain decision-making in `process()` and/or `process_async()`,
    while `execute()` provides template lifecycle management, duration recording,
    error isolation, and audit logging.
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self.config: AgentConfig = config or AgentConfig(name="base_agent")
        self.name: str = self.config.name
        self.role: AgentRole = self.config.role
        self.message_bus: MessageBus | None = message_bus
        self._status: AgentStatus = AgentStatus.IDLE
        self._inbox: list[AgentMessage] = []

        if self.message_bus is not None:
            self.message_bus.subscribe(self.name, self.receive_message)

    @property
    def status(self) -> AgentStatus:
        """Return the current agent execution status."""
        return self._status

    @property
    def inbox(self) -> list[AgentMessage]:
        """Return a copy of messages delivered to this agent."""
        return list(self._inbox)

    @abstractmethod
    def process(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Execute core agent logic synchronously and return partial state updates."""
        raise NotImplementedError

    async def process_async(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Execute core agent logic asynchronously.

        Subclasses can override with native coroutines. Defaults to delegating to `process()`.
        """
        return self.process(state)

    def execute(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Template execution method managing timing, status, and audit records."""
        self._status = AgentStatus.RUNNING
        start_time = time.perf_counter()

        try:
            updates = self.process(state)
            self._status = AgentStatus.SUCCESS
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            step_name = str(updates.get("current_step", self.name))
            record = AgentExecutionRecord(
                agent_name=self.name,
                step=step_name,
                status="SUCCESS",
                execution_time_ms=duration_ms,
            )

            result = dict(updates)
            records = list(result.get("records", []))
            records.append(record)
            result["records"] = records
            return result

        except Exception as exc:
            self._status = AgentStatus.ERROR
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            error_msg = f"[{self.name}] Error during execution: {exc}"
            record = AgentExecutionRecord(
                agent_name=self.name,
                step=self.name,
                status="ERROR",
                execution_time_ms=duration_ms,
                logs=[str(exc)],
            )
            return {
                "records": [record],
                "errors": [error_msg],
            }

    async def execute_async(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Asynchronous template execution method managing timing, status, and audit records."""
        self._status = AgentStatus.RUNNING
        start_time = time.perf_counter()

        try:
            updates = await self.process_async(state)
            self._status = AgentStatus.SUCCESS
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            step_name = str(updates.get("current_step", self.name))
            record = AgentExecutionRecord(
                agent_name=self.name,
                step=step_name,
                status="SUCCESS",
                execution_time_ms=duration_ms,
            )

            result = dict(updates)
            records = list(result.get("records", []))
            records.append(record)
            result["records"] = records
            return result

        except Exception as exc:
            self._status = AgentStatus.ERROR
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            error_msg = f"[{self.name}] Error during async execution: {exc}"
            record = AgentExecutionRecord(
                agent_name=self.name,
                step=self.name,
                status="ERROR",
                execution_time_ms=duration_ms,
                logs=[str(exc)],
            )
            return {
                "records": [record],
                "errors": [error_msg],
            }

    def step(self, state: MarketIntelligenceState) -> dict[str, Any]:
        """Convenience alias invoking execute()."""
        return self.execute(state)

    def send_message(
        self,
        recipient: str,
        message_type: MessageType,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage | None:
        """Publish a message from this agent via the connected MessageBus."""
        if self.message_bus is None:
            return None

        message = AgentMessage(
            sender=self.name,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id or str(uuid.uuid4()),
            priority=priority,
        )
        self.message_bus.publish(message)
        return message

    def receive_message(self, message: AgentMessage) -> None:
        """Receive and store an incoming message addressed to this agent."""
        self._inbox.append(message)

    def as_node_handler(self) -> Callable[[MarketIntelligenceState], dict[str, Any]]:
        """Return a callable handler compatible with LangGraph StateGraph nodes."""

        def _handler(state: MarketIntelligenceState) -> dict[str, Any]:
            return self.execute(state)

        return _handler
