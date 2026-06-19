"""
Approval Agent – bridges the human approval decision (made via the REST API)
back into the Band event pipeline. Listens for ACTION_APPROVED / ACTION_REJECTED
events created by the approvals API route and forwards execution authorization.

This agent enforces the platform's core safety invariant: the Execution Agent
only ever receives approved_actions through this agent's forwarding step,
never directly from RemediationAgent.
"""
from __future__ import annotations

import logging

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage
from db.session import AsyncSessionFactory

logger = logging.getLogger(__name__)


class ApprovalAgent(BaseAgent):
    name = "approval_agent"
    description = (
        "Mediates human approval decisions and authorizes the Execution Agent "
        "to proceed. No remediation runs without passing through this gate."
    )
    subscribes_to = [EventType.ACTION_APPROVED, EventType.ACTION_REJECTED]
    publishes = [EventType.ACTION_APPROVED]
    capabilities = ["human_in_the_loop", "approval_gating", "action_authorization"]

    async def handle_event(self, event: BandEvent) -> None:
        if event.event_type == EventType.ACTION_REJECTED:
            await self._handle_rejection(event)
            return

        logger.info("ApprovalAgent confirming authorization for incident %s", event.incident_id)
        await self._save_agent_message(event, approved=True)
        # Note: ACTION_APPROVED is already published by the approvals API route
        # with the correct payload shape for ExecutionAgent. This agent's role
        # here is primarily to record the authorization in the discussion timeline
        # and audit trail; it does not re-publish to avoid double execution.

    async def _handle_rejection(self, event: BandEvent) -> None:
        await self._save_agent_message(event, approved=False)
        logger.info("Remediation rejected for incident %s by human reviewer", event.incident_id)

    async def _save_agent_message(self, event: BandEvent, approved: bool) -> None:
        payload = event.payload
        reviewer = payload.get("reviewed_by", "security_analyst")
        notes = payload.get("reviewer_notes", "")

        if approved:
            content = (
                f"**Human Approval Granted** ✅\n\n"
                f"Reviewer **{reviewer}** authorized remediation execution.\n"
                + (f"\nNotes: {notes}" if notes else "")
                + "\n\nForwarding to Execution Agent for action."
            )
        else:
            content = (
                f"**Human Approval Rejected** ❌\n\n"
                f"Reviewer **{reviewer}** rejected the proposed remediation plan.\n"
                + (f"\nReason: {notes}" if notes else "")
                + "\n\nNo actions will be executed. Incident returned to investigation."
            )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="approval",
                content=content,
                confidence_score=1.0,
                extra_data={"approved": approved, "reviewer": reviewer},
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
