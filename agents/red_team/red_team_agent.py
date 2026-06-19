"""
Red Team Skeptic Agent – adversarially challenges the consensus finding
to surface false positives and missed attack vectors.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage
from db.session import AsyncSessionFactory
from services.featherless_client import featherless

logger = logging.getLogger(__name__)

RED_TEAM_SYSTEM_PROMPT = """You are an adversarial red team analyst. Your job is to challenge
security assessments for logical flaws, false positives, and missed attack vectors.
Be skeptical and rigorous. Look for alternative explanations.
Return ONLY valid JSON:
{
  "challenges": [
    {
      "claim": "the claim being challenged",
      "challenge": "the adversarial counter-argument",
      "severity": "fatal|major|minor",
      "alternative_explanation": "benign explanation if applicable"
    }
  ],
  "false_positive_indicators": ["string"],
  "missed_attack_vectors": ["string"],
  "confidence_adjustment": -0.3 to 0.1,
  "override_recommendation": null or "lower_severity|escalate|false_positive|investigate_further",
  "red_team_verdict": "string",
  "should_proceed": true|false
}"""


class RedTeamSkepticAgent(BaseAgent):
    name = "red_team_agent"
    description = (
        "Adversarially challenges the consensus finding to surface "
        "false positives and alternative explanations."
    )
    subscribes_to = [EventType.CONSENSUS_COMPLETE]
    publishes = [EventType.REMEDIATION_PROPOSED]
    capabilities = [
        "adversarial_analysis",
        "false_positive_detection",
        "attack_vector_identification",
    ]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("RedTeamAgent challenging consensus for incident %s", event.incident_id)
        payload = event.payload

        consensus = payload.get("consensus_result", {})
        mitre_mapping = payload.get("mitre_mapping", {})
        enriched_iocs = payload.get("enriched_iocs", [])

        challenge_result = await self._challenge_consensus(
            consensus, mitre_mapping, enriched_iocs
        )

        await self._save_agent_message(event, challenge_result, consensus)

        # Apply confidence adjustment
        original_confidence = consensus.get("consensus_confidence", 0.5)
        adjusted_confidence = max(
            0.1,
            min(1.0, original_confidence + challenge_result.get("confidence_adjustment", 0.0)),
        )

        should_proceed = challenge_result.get("should_proceed", True)

        await self.publish(
            event_type=EventType.REMEDIATION_PROPOSED,
            incident_id=event.incident_id,
            payload={
                **payload,
                "red_team_challenge": challenge_result,
                "adjusted_confidence": adjusted_confidence,
                "should_proceed_to_remediation": should_proceed,
                "final_severity": (
                    payload.get("final_severity")
                    if not challenge_result.get("override_recommendation")
                    else self._apply_override(
                        payload.get("final_severity", "medium"),
                        challenge_result.get("override_recommendation"),
                    )
                ),
            },
            correlation_id=event.event_id,
        )

    def _apply_override(self, current_severity: str, override: str | None) -> str:
        severity_order = ["info", "low", "medium", "high", "critical"]
        idx = severity_order.index(current_severity) if current_severity in severity_order else 2

        if override == "lower_severity":
            return severity_order[max(0, idx - 1)]
        elif override == "escalate":
            return severity_order[min(4, idx + 1)]
        elif override == "false_positive":
            return "info"
        return current_severity

    async def _challenge_consensus(
        self,
        consensus: dict[str, Any],
        mitre_mapping: dict[str, Any],
        enriched_iocs: list[dict],
    ) -> dict[str, Any]:
        user_prompt = f"""
        Consensus Result to Challenge:
        - Final Severity: {consensus.get("final_severity", "unknown")}
        - Confidence: {consensus.get("consensus_confidence", 0.5):.0%}
        - Reasoning: {consensus.get("reasoning", "No reasoning provided")}
        - Model Agreement: {consensus.get("agreement_score", 0.0):.0%}
        - Dissenting Models: {consensus.get("dissenting_models", [])}
        
        MITRE Techniques:
        {[f"{t.get('technique_id')}: {t.get('technique_name')}" 
          for t in mitre_mapping.get("techniques", [])]}
        
        IOC Summary:
        - Count: {len(enriched_iocs)}
        - High-threat: {len([i for i in enriched_iocs if i.get("threat_score", 0) > 0.7])}
        
        Challenge this assessment adversarially. What might we be getting wrong?
        Return JSON only.
        """

        try:
            return await featherless.json_completion(RED_TEAM_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning("Red team LLM call failed: %s", e)
            # Default: mild skepticism
            return {
                "challenges": [
                    {
                        "claim": f"Severity assessed as {consensus.get('final_severity', 'unknown')}",
                        "challenge": "Consider whether environmental context reduces actual risk",
                        "severity": "minor",
                        "alternative_explanation": "Could be authorized activity or misconfiguration",
                    }
                ],
                "false_positive_indicators": ["Insufficient historical baseline for comparison"],
                "missed_attack_vectors": ["Lateral movement potential not fully assessed"],
                "confidence_adjustment": -0.05,
                "override_recommendation": None,
                "red_team_verdict": "Consensus assessment appears reasonable but warrants human review",
                "should_proceed": True,
            }

    async def _save_agent_message(
        self, event: BandEvent, challenge: dict, consensus: dict
    ) -> None:
        challenges_text = "\n".join([
            f"- [{c.get('severity', '?').upper()}] {c.get('challenge', '')}"
            for c in challenge.get("challenges", [])
        ])

        override = challenge.get("override_recommendation")
        override_text = f"\n\n⚡ **Override:** {override.upper()}" if override else ""
        proceed_emoji = "✅" if challenge.get("should_proceed", True) else "🛑"

        content = (
            f"**Red Team Challenge Analysis**\n\n"
            f"{proceed_emoji} **Recommendation:** "
            f"{'Proceed to remediation' if challenge.get('should_proceed', True) else 'HALT - requires further investigation'}\n"
            f"**Confidence Adjustment:** {challenge.get('confidence_adjustment', 0):+.0%}\n\n"
            f"**Challenges Raised:**\n{challenges_text or 'No major challenges identified'}\n\n"
            f"**False Positive Indicators:** {', '.join(challenge.get('false_positive_indicators', ['None']))}\n"
            f"**Missed Vectors:** {', '.join(challenge.get('missed_attack_vectors', ['None']))}\n\n"
            f"**Red Team Verdict:** {challenge.get('red_team_verdict', 'N/A')}"
            f"{override_text}"
        )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="challenge",
                content=content,
                confidence_score=max(0.1, consensus.get("consensus_confidence", 0.5)
                                     + challenge.get("confidence_adjustment", 0)),
                extra_data={
                    "challenge_count": len(challenge.get("challenges", [])),
                    "should_proceed": challenge.get("should_proceed", True),
                    "override": override,
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
