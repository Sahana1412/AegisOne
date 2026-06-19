"""
Band Event Bus - Core nervous system for agent communication.
All agents communicate exclusively through Band events.
No direct agent-to-agent invocation is allowed.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class BandEvent:
    """Immutable event envelope passed through Band."""
    event_type: str
    incident_id: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_agent: str = ""
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


HandlerFn = Callable[[BandEvent], Coroutine[Any, Any, None]]


class BandEventBus:
    """
    Async publish/subscribe event bus.
    Agents subscribe to event types and publish events.
    The bus fans out to all registered handlers concurrently.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerFn]] = defaultdict(list)
        self._wildcard_handlers: list[HandlerFn] = []
        self._event_log: list[BandEvent] = []
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, handler: HandlerFn) -> None:
        """Register a handler for a specific event type."""
        if event_type == "*":
            self._wildcard_handlers.append(handler)
        else:
            self._handlers[event_type].append(handler)
        logger.debug("Subscribed handler %s to event '%s'", handler.__qualname__, event_type)

    def unsubscribe(self, event_type: str, handler: HandlerFn) -> None:
        """Remove a handler."""
        if event_type == "*":
            self._wildcard_handlers = [h for h in self._wildcard_handlers if h != handler]
        else:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    async def publish(self, event: BandEvent) -> None:
        """
        Publish an event to all registered handlers.
        Runs all handlers concurrently; logs but does not re-raise errors.
        """
        async with self._lock:
            self._event_log.append(event)

        logger.info(
            "BAND EVENT | type=%s | incident=%s | source=%s | event_id=%s",
            event.event_type,
            event.incident_id,
            event.source_agent,
            event.event_id,
        )

        handlers = list(self._handlers.get(event.event_type, []))
        handlers += list(self._wildcard_handlers)

        if not handlers:
            logger.warning("No handlers registered for event type '%s'", event.event_type)
            return

        tasks = [asyncio.create_task(self._safe_call(h, event)) for h in handlers]
        await asyncio.gather(*tasks)

    async def _safe_call(self, handler: HandlerFn, event: BandEvent) -> None:
        try:
            await handler(event)
        except Exception as exc:
            logger.exception(
                "Handler %s raised an exception for event %s: %s",
                handler.__qualname__,
                event.event_type,
                exc,
            )

    def get_event_log(self, incident_id: str | None = None) -> list[dict[str, Any]]:
        """Return the in-memory event log, optionally filtered by incident."""
        events = self._event_log
        if incident_id:
            events = [e for e in events if e.incident_id == incident_id]
        return [e.to_dict() for e in events]

    def clear_log(self) -> None:
        self._event_log.clear()


# Singleton instance shared across the application
band_bus = BandEventBus()
