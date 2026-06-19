"""
Remediation Agent – proposes specific remediation actions based on threat analysis.
All proposed actions must pass through human approval before execution.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage, ApprovalRequest, Incident
from db.session import AsyncSessionFactory
from services.featherless_client import featherless
from sqlalchemy import select

logger = logging.getLogger(__name__)

REMEDIATION_SYSTEM_PROMPT = """You are a cybersecurity incident response expert.
Propose specific, actionable remediation steps for the identified threat.
Order by priority. All actions will require human approval before execution.
Return ONLY valid JSON:
{
  "remediation_plan": {
    "objective": "string",
    "estimated_duration": "string",
    "risk_of_action": "low|medium|high",
    "actions": [
      {
        "action_id": "ACT-001",
        "action_type": "block_ip|disable_account|kill_process|revoke_session|create_github_issue|send_slack_alert|quarantine_file|isolate_host",
        "priority": 1,
        "title": "string",
        "description": "string",
        "parameters": {"key": "value"},
        "mcp_tool": "abuseipdb|github|slack|filesystem",
        "reversible": true|false,
        "estimated_impact": "string",
        "requires_downtime": false
      }
    ],
    "rollback_plan": "string",
    "success_criteria": ["string"]
  }
}"""


class RemediationAgent(BaseAgent):
    name = "remediation_agent"
    description = "Proposes structured remediation actions requiring human approval before execution."
    subscribes_to = [EventType.REMEDIATION_PROPOSED]
    publishes = [EventType.APPROVAL_REQUESTED]
    capabilities = [
        "remediation_planning",
        "action_sequencing",
        "impact_assessment",
        "playbook_retrieval",
    ]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("RemediationAgent building plan for incident %s", event.incident_id)
        payload = event.payload

        # Check if red team said to halt
        if not payload.get("should_proceed_to_remediation", True):
            logger.warning(
                "Red team halted remediation for incident %s", event.incident_id
            )
            await self._save_halted_message(event)
            return

        remediation = await self._build_remediation_plan(payload)

        # Persist remediation plan to incident
        await self._update_incident_remediation(event.incident_id, remediation)

        # Create approval request
        approval_id = await self._create_approval_request(event.incident_id, remediation, payload)

        await self._save_agent_message(event, remediation)

        await self.publish(
            event_type=EventType.APPROVAL_REQUESTED,
            incident_id=event.incident_id,
            payload={
                **payload,
                "remediation_plan": remediation,
                "approval_request_id": str(approval_id),
                "action_count": len(remediation.get("remediation_plan", {}).get("actions", [])),
            },
            correlation_id=event.event_id,
        )

    async def _build_remediation_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        mitre_mapping = payload.get("mitre_mapping", {})
        enriched_iocs = payload.get("enriched_iocs", [])
        consensus = payload.get("consensus_result", {})
        risk_result = payload.get("risk_result", {})

        # Get IPs and domains to block
        malicious_ips = [
            i["value"] for i in enriched_iocs
            if i.get("type") == "ip" and i.get("threat_score", 0) > 0.5
        ]
        malicious_domains = [
            i["value"] for i in enriched_iocs
            if i.get("type") in ("domain", "url") and i.get("threat_score", 0) > 0.5
        ]

        user_prompt = f"""
        Threat Profile:
        - Final Severity: {payload.get("final_severity", "medium").upper()}
        - Risk Score: {risk_result.get("risk_score", 0.5):.2f}
        - MITRE Techniques: {[t.get("technique_name") for t in mitre_mapping.get("techniques", [])]}
        - Kill Chain Phase: {mitre_mapping.get("kill_chain_phase", "unknown")}
        
        Malicious IPs to Block: {malicious_ips[:5]}
        Malicious Domains to Block: {malicious_domains[:5]}
        
        Systems at Risk: {risk_result.get("systems_at_risk", ["Unknown"])}
        Data at Risk: {risk_result.get("data_at_risk", ["Unknown"])}
        
        Red Team Notes: {payload.get("red_team_challenge", {}).get("red_team_verdict", "None")}
        
        Build a prioritized remediation plan. Return JSON only.
        """

        try:
            result = await featherless.json_completion(REMEDIATION_SYSTEM_PROMPT, user_prompt)
            return result
        except Exception as e:
            logger.warning("Remediation LLM call failed: %s", e)
            # Fallback plan based on IOCs
            actions = []
            for i, ip in enumerate(malicious_ips[:3], 1):
                actions.append({
                    "action_id": f"ACT-{i:03d}",
                    "action_type": "block_ip",
                    "priority": i,
                    "title": f"Block malicious IP: {ip}",
                    "description": f"Add {ip} to firewall blocklist",
                    "parameters": {"ip": ip, "duration": "permanent"},
                    "mcp_tool": "abuseipdb",
                    "reversible": True,
                    "estimated_impact": "Blocks C2 communication",
                    "requires_downtime": False,
                })
            actions.append({
                "action_id": f"ACT-{len(actions)+1:03d}",
                "action_type": "send_slack_alert",
                "priority": len(actions) + 1,
                "title": "Notify security team via Slack",
                "description": "Send incident alert to #security-incidents channel",
                "parameters": {"channel": "#security-incidents"},
                "mcp_tool": "slack",
                "reversible": True,
                "estimated_impact": "Team notification",
                "requires_downtime": False,
            })
            return {
                "remediation_plan": {
                    "objective": "Contain threat and prevent further compromise",
                    "estimated_duration": "30-60 minutes",
                    "risk_of_action": "low",
                    "actions": actions,
                    "rollback_plan": "Unblock IPs if confirmed false positive",
                    "success_criteria": [
                        "All malicious IPs blocked",
                        "Security team notified",
                        "No further C2 communication observed",
                    ],
                }
            }

    async def _update_incident_remediation(
        self, incident_id: str, remediation: dict
    ) -> None:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one_or_none()
            if incident:
                incident.remediation_plan = remediation
                incident.status = "awaiting_approval"
                await session.commit()

    async def _create_approval_request(
        self, incident_id: str, remediation: dict, payload: dict
    ) -> str:
        plan = remediation.get("remediation_plan", {})
        actions = plan.get("actions", [])

        async with AsyncSessionFactory() as session:
            approval = ApprovalRequest(
                incident_id=incident_id,
                proposed_actions=actions,
                risk_summary=(
                    f"Severity: {payload.get('final_severity', 'unknown').upper()} | "
                    f"Risk: {payload.get('risk_result', {}).get('risk_score', 0):.2f} | "
                    f"{plan.get('objective', '')}"
                ),
                confidence_score=payload.get("adjusted_confidence",
                                             payload.get("consensus_result", {}).get("consensus_confidence", 0.5)),
                status="pending",
            )
            session.add(approval)
            await session.commit()
            await session.refresh(approval)
            return str(approval.id)

    async def _save_agent_message(self, event: BandEvent, remediation: dict) -> None:
        plan = remediation.get("remediation_plan", {})
        actions = plan.get("actions", [])
        action_list = "\n".join([
            f"{i+1}. **[{a.get('action_type', '?')}]** {a.get('title', '')} "
            f"(tool: `{a.get('mcp_tool', 'unknown')}`)"
            for i, a in enumerate(actions[:5])
        ])

        content = (
            f"**Remediation Plan Proposed** ⚠️ Awaiting Human Approval\n\n"
            f"**Objective:** {plan.get('objective', 'N/A')}\n"
            f"**Estimated Duration:** {plan.get('estimated_duration', 'Unknown')}\n"
            f"**Action Risk:** {plan.get('risk_of_action', 'unknown').upper()}\n"
            f"**Total Actions:** {len(actions)}\n\n"
            f"**Proposed Actions:**\n{action_list}\n\n"
            f"**Success Criteria:** {'; '.join(plan.get('success_criteria', []))}\n\n"
            f"⏳ **Waiting for analyst approval before execution.**"
        )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="recommendation",
                content=content,
                confidence_score=0.85,
                extra_data={
                    "action_count": len(actions),
                    "risk_of_action": plan.get("risk_of_action"),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()

    async def _save_halted_message(self, event: BandEvent) -> None:
        content = (
            "🛑 **Remediation Halted by Red Team**\n\n"
            "The Red Team Skeptic Agent flagged significant concerns that prevent "
            "automated remediation planning. Manual investigation required.\n\n"
            "Please review the red team challenge findings and re-initiate the "
            "investigation pipeline after manual analysis."
        )
        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="warning",
                content=content,
                confidence_score=0.0,
                extra_data={"halted": True},
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
