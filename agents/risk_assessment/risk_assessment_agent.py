"""
Risk Assessment Agent – computes a quantitative risk score from threat data.
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

RISK_SYSTEM_PROMPT = """You are a cybersecurity risk quantification expert using FAIR methodology.
Analyze the threat data and provide a comprehensive risk assessment.
Return ONLY valid JSON:
{
  "risk_score": 0.0-1.0,
  "impact_score": 0.0-1.0,
  "likelihood_score": 0.0-1.0,
  "business_impact": "critical|high|medium|low",
  "data_at_risk": ["string"],
  "systems_at_risk": ["string"],
  "financial_impact_estimate": "string",
  "regulatory_implications": ["string"],
  "risk_factors": [{"factor": "string", "weight": 0.0-1.0}],
  "executive_summary": "string"
}"""


class RiskAssessmentAgent(BaseAgent):
    name = "risk_assessment_agent"
    description = "Quantifies risk using FAIR methodology across impact and likelihood dimensions."
    subscribes_to = [EventType.RISK_ASSESSED]
    publishes = [EventType.RISK_COMPUTED]
    capabilities = ["fair_risk_model", "impact_analysis", "business_risk_quantification"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("RiskAssessmentAgent processing incident %s", event.incident_id)
        payload = event.payload

        risk_result = await self._compute_risk(payload)

        # Update incident in database
        await self._update_incident_risk(event.incident_id, risk_result)

        await self._save_agent_message(event, risk_result)

        enriched_payload = {
            **payload,
            "risk_score": risk_result["risk_score"],
            "risk_result": risk_result,
        }

        # Re-publish as RISK_COMPUTED — a distinct event type so that
        # ConsensusAgent (which subscribes to RISK_ASSESSED) fires exactly
        # once, only after the risk score has actually been computed.
        await self.publish(
            event_type=EventType.RISK_COMPUTED,
            incident_id=event.incident_id,
            payload=enriched_payload,
            correlation_id=event.event_id,
        )

    async def _compute_risk(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Compute quantitative risk score."""
        mitre_mapping = payload.get("mitre_mapping", {})
        enriched_iocs = payload.get("enriched_iocs", [])
        threat_context = payload.get("threat_context", {})

        # Quick heuristic score
        base_score = 0.0
        techniques = mitre_mapping.get("techniques", [])
        high_confidence_techniques = [t for t in techniques if t.get("confidence", 0) > 0.7]
        base_score += min(0.3, len(high_confidence_techniques) * 0.05)

        high_iocs = [i for i in enriched_iocs if i.get("threat_score", 0) > 0.7]
        base_score += min(0.3, len(high_iocs) * 0.06)

        severity_map = {"critical": 0.4, "high": 0.3, "medium": 0.2, "low": 0.1, "info": 0.0}
        severity = threat_context.get("severity_assessment", "medium")
        base_score += severity_map.get(severity, 0.2)

        base_score = min(1.0, base_score)

        # LLM-enhanced risk assessment
        user_prompt = f"""
        MITRE Techniques: {[t.get("technique_name") for t in techniques]}
        Kill Chain Phase: {mitre_mapping.get("kill_chain_phase", "unknown")}
        IOC Count: {len(enriched_iocs)}, High-threat IOCs: {len(high_iocs)}
        Threat Actor Profile: {threat_context.get("threat_actor_profile", "Unknown")}
        Initial Risk Estimate: {base_score:.2f}
        
        Provide comprehensive risk assessment. Return JSON only.
        """

        try:
            result = await featherless.json_completion(RISK_SYSTEM_PROMPT, user_prompt)
            # Ensure risk_score is within bounds
            result["risk_score"] = max(0.0, min(1.0, float(result.get("risk_score", base_score))))
            return result
        except Exception as e:
            logger.warning("Risk LLM call failed: %s", e)
            return {
                "risk_score": base_score,
                "impact_score": base_score * 0.7,
                "likelihood_score": base_score * 0.8,
                "business_impact": severity,
                "data_at_risk": ["User data", "System integrity"],
                "systems_at_risk": ["Unknown"],
                "financial_impact_estimate": "Undetermined",
                "regulatory_implications": ["Potential GDPR notification required"],
                "risk_factors": [{"factor": "IOC presence", "weight": 0.6}],
                "executive_summary": f"Risk score {base_score:.2f} based on {len(techniques)} MITRE techniques and {len(enriched_iocs)} IOCs.",
            }

    async def _update_incident_risk(self, incident_id: str, risk_result: dict) -> None:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one_or_none()
            if incident:
                incident.risk_score = risk_result.get("risk_score", 0.0)
                severity_map = {
                    "critical": "critical", "high": "high",
                    "medium": "medium", "low": "low", "info": "low",
                }
                incident.severity = severity_map.get(
                    risk_result.get("business_impact", "medium"), "medium"
                )
                await session.commit()

    async def _save_agent_message(self, event: BandEvent, risk: dict) -> None:
        content = (
            f"**Risk Assessment Complete (FAIR Methodology)**\n\n"
            f"**Overall Risk Score:** {risk['risk_score']:.2f}/1.0\n"
            f"**Impact Score:** {risk.get('impact_score', 0):.2f}\n"
            f"**Likelihood Score:** {risk.get('likelihood_score', 0):.2f}\n"
            f"**Business Impact:** {risk.get('business_impact', 'Unknown').upper()}\n\n"
            f"**Executive Summary:** {risk.get('executive_summary', 'N/A')}\n\n"
            f"**Data at Risk:** {', '.join(risk.get('data_at_risk', []))}\n"
            f"**Regulatory Implications:** {', '.join(risk.get('regulatory_implications', []))}"
        )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="assessment",
                content=content,
                confidence_score=risk.get("likelihood_score", 0.5),
                extra_data={
                    "risk_score": risk.get("risk_score"),
                    "business_impact": risk.get("business_impact"),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
