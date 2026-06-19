"""
Base Agent – abstract base for all AegisOne XDR agents.
All agents communicate exclusively through Band events.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from band.registry.agent_registry import AgentInfo, agent_registry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Agents register themselves with the Band bus and react to events.
    They never invoke other agents directly.
    """

    name: str = "base_agent"
    description: str = "Base agent"
    subscribes_to: list[str] = []
    publishes: list[str] = []
    capabilities: list[str] = []

    def __init__(self, bus: BandEventBus) -> None:
        self.bus = bus
        self._register()
        self._subscribe()

    def _register(self) -> None:
        agent_registry.register(
            AgentInfo(
                name=self.name,
                description=self.description,
                subscribes_to=self.subscribes_to,
                publishes=self.publishes,
                capabilities=self.capabilities,
            )
        )

    def _subscribe(self) -> None:
        for event_type in self.subscribes_to:
            self.bus.subscribe(event_type, self._handle_event_wrapper)

    async def _handle_event_wrapper(self, event: BandEvent) -> None:
        agent_registry.mark_active(self.name, "running")
        try:
            await self.handle_event(event)
            agent_registry.mark_idle(self.name)
        except Exception as exc:
            agent_registry.mark_error(self.name)
            logger.exception("Agent %s failed on event %s: %s", self.name, event.event_type, exc)
            await self._publish_agent_failed(event, str(exc))

    @abstractmethod
    async def handle_event(self, event: BandEvent) -> None:
        """Process an incoming Band event."""

    async def publish(
        self,
        event_type: str,
        incident_id: str,
        payload: dict,
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> None:
        """Publish an event to the Band bus."""
        event = BandEvent(
            event_type=event_type,
            incident_id=incident_id,
            payload=payload,
            source_agent=self.name,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )
        await self.bus.publish(event)

    async def _publish_agent_failed(self, original_event: BandEvent, error: str) -> None:
        await self.publish(
            event_type=EventType.AGENT_FAILED,
            incident_id=original_event.incident_id,
            payload={
                "agent": self.name,
                "original_event_type": original_event.event_type,
                "error": error,
            },
            correlation_id=original_event.event_id,
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
