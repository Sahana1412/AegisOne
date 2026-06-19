"""
Verification Agent – confirms that remediation actions succeeded and the threat is contained.
If verification fails, it triggers alternative remediation.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage, Incident
from db.session import AsyncSessionFactory
from services.featherless_client import featherless
from sqlalchemy import select

logger = logging.getLogger(__name__)

VERIFICATION_SYSTEM_PROMPT = """You are a cybersecurity verification specialist.
Assess whether the executed remediation actions were successful based on the execution results.
Return ONLY valid JSON:
{
  "verification_status": "success|partial|failed",
  "containment_achieved": true|false,
  "verified_actions": ["action_id"],
  "failed_verifications": ["action_id"],
  "residual_risk": "none|low|medium|high",
  "follow_up_required": true|false,
  "follow_up_actions": ["string"],
  "explanation": "string",
  "incident_status": "closed|investigating|remediating"
}"""


class VerificationAgent(BaseAgent):
    name = "verification_agent"
    description = "Verifies remediation success and triggers alternative response if needed."
    subscribes_to = [EventType.EXECUTION_COMPLETE, EventType.EXECUTION_FAILED]
    publishes = [EventType.VERIFICATION_COMPLETE, EventType.REPORT_GENERATED]
    capabilities = ["remediation_verification", "threat_containment_check", "risk_reassessment"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("VerificationAgent checking remediation for incident %s", event.incident_id)
        payload = event.payload

        execution_results = payload.get("execution_results", [])
        failed_actions = payload.get("failed_actions", [])

        verification = await self._verify_remediation(execution_results, failed_actions, payload)

        await self._update_incident_verification(event.incident_id, verification)
        await self._save_agent_message(event, verification)

        await self.publish(
            event_type=EventType.VERIFICATION_COMPLETE,
            incident_id=event.incident_id,
            payload={
                **payload,
                "verification_result": verification,
                "containment_achieved": verification.get("containment_achieved", False),
                "incident_status": verification.get("incident_status", "investigating"),
            },
            correlation_id=event.event_id,
        )

        # Always trigger report generation
        await self.publish(
            event_type=EventType.REPORT_GENERATED,
            incident_id=event.incident_id,
            payload={**payload, "verification_result": verification},
            correlation_id=event.event_id,
        )

    async def _verify_remediation(
        self,
        execution_results: list[dict],
        failed_actions: list[dict],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        user_prompt = f"""
        Execution Results:
        - Successful actions: {len(execution_results)}
        - Failed actions: {len(failed_actions)}
        
        Successful action types: {[r.get("action_type") for r in execution_results]}
        Failed action types: {[r.get("action_type") for r in failed_actions]}
        Failed reasons: {[r.get("error") for r in failed_actions]}
        
        Original threat context:
        - Severity: {payload.get("final_severity", "unknown")}
        - Risk Score: {payload.get("risk_result", {}).get("risk_score", 0.5):.2f}
        - IOC Count: {len(payload.get("enriched_iocs", []))}
        
        Verify whether the executed actions successfully contained the threat.
        Return JSON only.
        """

        try:
            return await featherless.json_completion(VERIFICATION_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning("Verification LLM call failed: %s", e)
            all_success = len(failed_actions) == 0
            return {
                "verification_status": "success" if all_success else "partial",
                "containment_achieved": all_success,
                "verified_actions": [r.get("action_id") for r in execution_results],
                "failed_verifications": [r.get("action_id") for r in failed_actions],
                "residual_risk": "none" if all_success else "medium",
                "follow_up_required": not all_success,
                "follow_up_actions": (
                    [] if all_success
                    else ["Manual verification of failed actions required"]
                ),
                "explanation": (
                    f"Verification {'complete' if all_success else 'partial'}: "
                    f"{len(execution_results)} actions succeeded, "
                    f"{len(failed_actions)} failed."
                ),
                "incident_status": "closed" if all_success else "investigating",
            }

    async def _update_incident_verification(
        self, incident_id: str, verification: dict
    ) -> None:
        async with AsyncSessionFactory() as session:
            res = await session.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = res.scalar_one_or_none()
            if incident:
                incident.verification_result = verification
                status_map = {
                    "closed": "closed",
                    "investigating": "investigating",
                    "remediating": "remediating",
                }
                incident.status = status_map.get(
                    verification.get("incident_status", "investigating"), "investigating"
                )
                await session.commit()

    async def _save_agent_message(self, event: BandEvent, verification: dict) -> None:
        status = verification.get("verification_status", "unknown")
        status_emoji = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(status, "❓")
        containment = verification.get("containment_achieved", False)

        content = (
            f"**Verification Report** {status_emoji}\n\n"
            f"**Status:** {status.upper()}\n"
            f"**Containment Achieved:** {'Yes' if containment else 'No'}\n"
            f"**Residual Risk:** {verification.get('residual_risk', 'unknown').upper()}\n\n"
            f"**Explanation:** {verification.get('explanation', 'N/A')}\n\n"
        )
        if verification.get("follow_up_required"):
            follow_ups = verification.get("follow_up_actions", [])
            content += f"**Follow-up Required:**\n" + "\n".join(f"- {f}" for f in follow_ups)

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="verification",
                content=content,
                confidence_score=0.9 if status == "success" else 0.5,
                extra_data={
                    "verification_status": status,
                    "containment_achieved": containment,
                    "residual_risk": verification.get("residual_risk"),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
