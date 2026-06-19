"""Audit Trail Agent – creates immutable audit records for all Band events."""
from __future__ import annotations
import logging
from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent
from band.events.event_types import EventType
from db.models import AuditEntry
from db.session import AsyncSessionFactory

logger = logging.getLogger(__name__)


class AuditTrailAgent(BaseAgent):
    name = "audit_trail_agent"
    description = "Creates immutable audit records for every significant Band event."
    subscribes_to = ["*"]  # Listens to ALL events
    publishes = []
    capabilities = ["audit_logging", "compliance_recording", "event_archival"]

    # Events to skip to avoid noise
    SKIP_EVENTS = {EventType.AGENT_STARTED, EventType.WS_UPDATE}

    async def handle_event(self, event: BandEvent) -> None:
        if event.event_type in self.SKIP_EVENTS:
            return
        if event.source_agent == self.name:
            return

        action_map = {
            EventType.INCIDENT_CREATED: "Incident created and pipeline triggered",
            EventType.THREAT_CONTEXT_READY: "Threat intelligence enrichment completed",
            EventType.MITRE_MAPPING_COMPLETE: "MITRE ATT&CK mapping performed",
            EventType.RISK_ASSESSED: "Risk assessment triggered",
            EventType.RISK_COMPUTED: "Risk score computed (FAIR methodology)",
            EventType.CONSENSUS_COMPLETE: "Multi-model consensus reached",
            EventType.RED_TEAM_CHALLENGE_COMPLETE: "Red team challenge completed",
            EventType.REMEDIATION_PROPOSED: "Remediation plan proposed",
            EventType.APPROVAL_REQUESTED: "Human approval requested",
            EventType.ACTION_APPROVED: "Remediation action approved by human",
            EventType.ACTION_REJECTED: "Remediation action rejected by human",
            EventType.EXECUTION_COMPLETE: "Remediation actions executed",
            EventType.EXECUTION_FAILED: "Remediation execution failed",
            EventType.VERIFICATION_COMPLETE: "Remediation verification completed",
            EventType.REPORT_GENERATED: "Incident report generated",
            EventType.AUDIT_COMPLETE: "Incident audit trail finalized",
        }

        action = action_map.get(event.event_type, f"Band event: {event.event_type}")

        async with AsyncSessionFactory() as session:
            entry = AuditEntry(
                incident_id=event.incident_id,
                actor=event.source_agent or "system",
                actor_type="agent" if event.source_agent else "system",
                action=action,
                details={
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "metadata": event.metadata,
                },
                outcome="success",
            )
            session.add(entry)
            try:
                await session.commit()
            except Exception as e:
                logger.warning("Audit entry failed: %s", e)
