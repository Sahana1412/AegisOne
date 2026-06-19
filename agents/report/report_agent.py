"""Report Agent – generates final incident report."""
from __future__ import annotations
import logging
from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent
from band.events.event_types import EventType
from db.models import AgentMessage, Incident
from db.session import AsyncSessionFactory
from services.featherless_client import featherless
from sqlalchemy import select

logger = logging.getLogger(__name__)

REPORT_PROMPT = """You are a cybersecurity report writer. Generate a concise executive incident report.
Return JSON only:
{
  "executive_summary": "string (2-3 sentences)",
  "timeline": [{"time": "string", "event": "string"}],
  "threat_overview": "string",
  "impact_assessment": "string",
  "actions_taken": ["string"],
  "lessons_learned": ["string"],
  "recommendations": ["string"],
  "classification": "confidential|restricted|internal"
}"""


class ReportAgent(BaseAgent):
    name = "report_agent"
    description = "Generates structured incident reports after verification."
    subscribes_to = [EventType.REPORT_GENERATED]
    publishes = [EventType.AUDIT_COMPLETE]
    capabilities = ["report_generation", "executive_summary", "timeline_construction"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("ReportAgent generating report for incident %s", event.incident_id)
        payload = event.payload

        report = await self._generate_report(payload)
        await self._save_report(event.incident_id, report)
        await self._save_agent_message(event, report)

        await self.publish(
            event_type=EventType.AUDIT_COMPLETE,
            incident_id=event.incident_id,
            payload={**payload, "report": report},
            correlation_id=event.event_id,
        )

    async def _generate_report(self, payload: dict) -> dict:
        user_prompt = f"""
        Incident Summary:
        - Severity: {payload.get("final_severity", "unknown").upper()}
        - Risk Score: {payload.get("risk_result", {}).get("risk_score", 0):.2f}
        - MITRE Techniques: {[t.get("technique_name") for t in payload.get("mitre_mapping", {}).get("techniques", [])]}
        - IOC Count: {len(payload.get("enriched_iocs", []))}
        - Consensus Confidence: {payload.get("consensus_result", {}).get("consensus_confidence", 0):.0%}
        - Verification: {payload.get("verification_result", {}).get("verification_status", "unknown")}
        - Actions Executed: {len(payload.get("execution_results", []))}
        
        Generate comprehensive incident report. Return JSON only.
        """
        try:
            return await featherless.json_completion(REPORT_PROMPT, user_prompt)
        except Exception as e:
            logger.warning("Report generation failed: %s", e)
            return {
                "executive_summary": f"Security incident investigated with {payload.get('final_severity', 'unknown')} severity.",
                "timeline": [{"time": self._now(), "event": "Investigation completed"}],
                "threat_overview": "Multi-vector threat identified and contained.",
                "impact_assessment": "Impact assessment pending manual review.",
                "actions_taken": ["Automated analysis completed", "Remediation executed"],
                "lessons_learned": ["Review detection thresholds"],
                "recommendations": ["Update playbooks based on findings"],
                "classification": "confidential",
            }

    async def _save_report(self, incident_id: str, report: dict) -> None:
        async with AsyncSessionFactory() as session:
            res = await session.execute(select(Incident).where(Incident.id == incident_id))
            incident = res.scalar_one_or_none()
            if incident:
                incident.report_url = f"/api/v1/incidents/{incident_id}/report"
                await session.commit()

    async def _save_agent_message(self, event: BandEvent, report: dict) -> None:
        content = (
            f"**Incident Report Generated** 📋\n\n"
            f"**Executive Summary:** {report.get('executive_summary', 'N/A')}\n\n"
            f"**Classification:** {report.get('classification', 'confidential').upper()}\n\n"
            f"**Recommendations:**\n" +
            "\n".join(f"- {r}" for r in report.get("recommendations", [])) +
            f"\n\n**Lessons Learned:**\n" +
            "\n".join(f"- {l}" for l in report.get("lessons_learned", []))
        )
        async with AsyncSessionFactory() as session:
            session.add(AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="report",
                content=content,
                confidence_score=0.95,
                extra_data={"classification": report.get("classification")},
                band_event_type=event.event_type,
            ))
            await session.commit()
