"""
Intake Agent – receives raw incident data and publishes the initial event.
This is the entry point for all incidents into the AegisOne pipeline.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType

logger = logging.getLogger(__name__)


class IntakeAgent(BaseAgent):
    name = "intake_agent"
    description = "Receives and normalizes raw incident data; triggers the investigation pipeline."
    subscribes_to = [EventType.INCIDENT_CREATED]
    publishes = [
        EventType.VISION_ANALYSIS_COMPLETE,
        EventType.EMAIL_ANALYSIS_COMPLETE,
        EventType.LOG_ANALYSIS_COMPLETE,
    ]
    capabilities = ["email_parsing", "log_parsing", "image_routing", "normalization"]

    async def handle_event(self, event: BandEvent) -> None:
        """
        Normalize the incident source data and fan out to appropriate
        specialist agents via Band events.
        """
        logger.info("IntakeAgent processing incident %s", event.incident_id)
        payload = event.payload
        source_type = payload.get("source_type", "manual")

        # Route to specialist sub-pipelines based on source type
        if source_type == "email":
            await self._route_email(event, payload)
        elif source_type == "log":
            await self._route_log(event, payload)
        elif source_type == "image":
            await self._route_image(event, payload)
        else:
            # Generic threat intelligence lookup for manual/API incidents
            await self._route_generic(event, payload)

        await self._emit_agent_message(event, source_type)

    async def _route_email(self, event: BandEvent, payload: dict[str, Any]) -> None:
        await self.publish(
            event_type=EventType.EMAIL_ANALYSIS_COMPLETE,
            incident_id=event.incident_id,
            payload={
                "email_data": payload.get("source_data", {}),
                "routing": "email_pipeline",
                "status": "pending_analysis",
            },
            correlation_id=event.event_id,
        )

    async def _route_log(self, event: BandEvent, payload: dict[str, Any]) -> None:
        await self.publish(
            event_type=EventType.LOG_ANALYSIS_COMPLETE,
            incident_id=event.incident_id,
            payload={
                "log_data": payload.get("source_data", {}),
                "routing": "log_pipeline",
                "status": "pending_analysis",
            },
            correlation_id=event.event_id,
        )

    async def _route_image(self, event: BandEvent, payload: dict[str, Any]) -> None:
        await self.publish(
            event_type=EventType.VISION_ANALYSIS_COMPLETE,
            incident_id=event.incident_id,
            payload={
                "image_data": payload.get("source_data", {}),
                "routing": "vision_pipeline",
                "status": "pending_analysis",
            },
            correlation_id=event.event_id,
        )

    async def _route_generic(self, event: BandEvent, payload: dict[str, Any]) -> None:
        """For manual/API incidents, trigger threat context lookup directly."""
        await self.publish(
            event_type=EventType.THREAT_CONTEXT_READY,
            incident_id=event.incident_id,
            payload={
                "source_type": "manual",
                "incident_data": payload,
                "iocs": payload.get("ioc_list", []),
                "status": "ready_for_analysis",
            },
            correlation_id=event.event_id,
        )

    async def _emit_agent_message(self, event: BandEvent, source_type: str) -> None:
        """Emit an agent message for the discussion timeline."""
        from db.session import AsyncSessionFactory
        from db.models import AgentMessage

        message = (
            f"Incident received via **{source_type}** channel. "
            f"Normalizing payload and routing to specialist agents. "
            f"Source: `{source_type}`. Pipeline initiated."
        )

        async with AsyncSessionFactory() as session:
            entry = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="routing",
                content=message,
                confidence_score=1.0,
                extra_data={"source_type": source_type},
                band_event_type=EventType.INCIDENT_CREATED,
            )
            session.add(entry)
            await session.commit()
