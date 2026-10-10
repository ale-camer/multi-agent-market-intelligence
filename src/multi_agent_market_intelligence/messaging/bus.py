"""In-memory publish/subscribe message bus for agent coordination."""

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from multi_agent_market_intelligence.messaging.models import AgentMessage

MessageHandler = Callable[[AgentMessage], Any]


class MessageBus:
    """In-memory event bus and dispatcher for inter-agent communication."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._history: list[AgentMessage] = []
        self._dead_letters: list[AgentMessage] = []

    @property
    def history(self) -> list[AgentMessage]:
        """Return the immutable copy of all dispatched messages."""
        return list(self._history)

    @property
    def dead_letters(self) -> list[AgentMessage]:
        """Return messages that had no matching active subscribers."""
        return list(self._dead_letters)

    def subscribe(self, recipient_or_topic: str, handler: MessageHandler) -> None:
        """Register a subscriber callback for a specific recipient, topic, or '*' wildcard."""
        if handler not in self._subscribers[recipient_or_topic]:
            self._subscribers[recipient_or_topic].append(handler)

    def unsubscribe(self, recipient_or_topic: str, handler: MessageHandler) -> bool:
        """Remove a previously registered subscriber callback."""
        if (
            recipient_or_topic in self._subscribers
            and handler in self._subscribers[recipient_or_topic]
        ):
            self._subscribers[recipient_or_topic].remove(handler)
            return True
        return False

    def get_subscribers(self, recipient_or_topic: str) -> list[MessageHandler]:
        """Return registered subscribers for a given topic or recipient."""
        return list(self._subscribers.get(recipient_or_topic, []))

    def _resolve_handlers(self, message: AgentMessage) -> list[MessageHandler]:
        """Resolve all subscriber handlers matching the message recipient or wildcard."""
        handlers: list[MessageHandler] = []
        # Wildcard subscribers receive everything
        handlers.extend(self._subscribers.get("*", []))

        # Recipient specific subscribers
        if message.recipient != "*":
            for h in self._subscribers.get(message.recipient, []):
                if h not in handlers:
                    handlers.append(h)

        # Message type subscribers (e.g. "type:SIGNAL_PROPOSAL")
        type_topic = f"type:{message.message_type}"
        for h in self._subscribers.get(type_topic, []):
            if h not in handlers:
                handlers.append(h)

        return handlers

    def publish(self, message: AgentMessage) -> list[Any]:
        """Deliver message synchronously to all matching subscribers in FIFO order."""
        self._history.append(message)
        handlers = self._resolve_handlers(message)

        if not handlers and message.recipient != "*":
            self._dead_letters.append(message)

        results: list[Any] = []
        for handler in handlers:
            if inspect.iscoroutinefunction(handler):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(handler(message))
                    results.append(None)
                else:
                    res = asyncio.run(handler(message))
                    results.append(res)
            else:
                results.append(handler(message))
        return results

    async def publish_async(self, message: AgentMessage) -> list[Any]:
        """Deliver message asynchronously to all matching subscribers."""
        self._history.append(message)
        handlers = self._resolve_handlers(message)

        if not handlers and message.recipient != "*":
            self._dead_letters.append(message)

        results: list[Any] = []
        for handler in handlers:
            if inspect.iscoroutinefunction(handler):
                res = await handler(message)
            else:
                res = handler(message)
            results.append(res)
        return results

    def get_history(
        self,
        recipient: str | None = None,
        sender: str | None = None,
    ) -> list[AgentMessage]:
        """Filter audit history by recipient and/or sender."""
        return [
            m
            for m in self._history
            if (recipient is None or m.recipient in (recipient, "*"))
            and (sender is None or m.sender == sender)
        ]

    def get_conversation(self, correlation_id: str) -> list[AgentMessage]:
        """Retrieve complete conversation thread sharing a correlation_id."""
        return [m for m in self._history if m.correlation_id == correlation_id]

    def clear(self) -> None:
        """Reset subscribers, message history, and dead letter records."""
        self._subscribers.clear()
        self._history.clear()
        self._dead_letters.clear()
