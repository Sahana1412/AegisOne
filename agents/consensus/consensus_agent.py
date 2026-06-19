"""
Consensus Agent – runs the incident payload through multiple LLMs and
aggregates their confidence scores using weighted voting.
Models: DeepSeek-R1, Qwen3, Llama 3.3, Mistral
"""
from __future__ import annotations

import logging
import statistics
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage
from db.session import AsyncSessionFactory
from services.featherless_client import CONSENSUS_MODELS, featherless

logger = logging.getLogger(__name__)

CONSENSUS_SYSTEM_PROMPT = """You are a senior cybersecurity analyst providing independent threat assessment.
Analyze the incident data and provide your assessment.
Return ONLY valid JSON with this exact structure:
{
  "threat_level": "critical|high|medium|low|info",
  "confidence": 0.0-1.0,
  "is_true_positive": true|false,
  "false_positive_probability": 0.0-1.0,
  "key_risk_factors": ["string"],
  "recommended_severity": "critical|high|medium|low|info",
  "reasoning": "brief explanation of your assessment"
}"""


class ConsensusAgent(BaseAgent):
    name = "consensus_agent"
    description = (
        "Aggregates independent assessments from DeepSeek-R1, Qwen3, Llama 3.3, "
        "and Mistral to produce a consensus threat verdict."
    )
    subscribes_to = [EventType.RISK_COMPUTED]
    publishes = [EventType.CONSENSUS_COMPLETE]
    capabilities = ["multi_model_consensus", "confidence_aggregation", "threat_classification"]

    # Model weights (higher = more trusted for security tasks)
    MODEL_WEIGHTS = {
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B": 0.30,
        "Qwen/Qwen3-8B": 0.25,
        "meta-llama/Llama-3.3-70B-Instruct": 0.30,
        "mistralai/Mistral-7B-Instruct-v0.3": 0.15,
    }

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("ConsensusAgent running multi-model analysis for incident %s",
                    event.incident_id)
        payload = event.payload

        user_prompt = self._build_analysis_prompt(payload)

        # Run all models in parallel
        model_responses = await featherless.consensus_completions(
            system_prompt=CONSENSUS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            models=CONSENSUS_MODELS,
        )

        # Aggregate responses
        consensus = self._aggregate_responses(model_responses)

        await self._save_agent_message(event, model_responses, consensus)

        await self.publish(
            event_type=EventType.CONSENSUS_COMPLETE,
            incident_id=event.incident_id,
            payload={
                **payload,
                "consensus_result": consensus,
                "model_responses": model_responses,
                "final_severity": consensus["final_severity"],
                "consensus_confidence": consensus["consensus_confidence"],
                "is_true_positive": consensus["is_true_positive"],
            },
            correlation_id=event.event_id,
        )

    def _build_analysis_prompt(self, payload: dict[str, Any]) -> str:
        mitre_mapping = payload.get("mitre_mapping", {})
        risk_score = payload.get("risk_score", 0.0)
        threat_context = payload.get("threat_context", {})
        enriched_iocs = payload.get("enriched_iocs", [])

        return f"""
        Incident Risk Score: {risk_score:.2f}/1.0
        
        Threat Context:
        - Actor Profile: {threat_context.get("threat_actor_profile", "Unknown")}
        - Attack Pattern: {threat_context.get("attack_pattern", "Unknown")}
        - Key Findings: {threat_context.get("key_findings", [])}
        
        MITRE ATT&CK Techniques Identified:
        {[t.get("technique_name", "") for t in mitre_mapping.get("techniques", [])]}
        
        Kill Chain Phase: {mitre_mapping.get("kill_chain_phase", "Unknown")}
        
        IOC Summary:
        - Total IOCs: {len(enriched_iocs)}
        - High-confidence threats: {len([i for i in enriched_iocs if i.get("threat_score", 0) > 0.7])}
        - IOC types: {list({i.get("type") for i in enriched_iocs})}
        
        Provide your independent assessment as a security expert.
        """

    def _aggregate_responses(
        self, model_responses: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Weighted voting across all model responses."""
        valid_responses = [
            r for r in model_responses
            if r.get("response") and not r.get("error")
        ]

        if not valid_responses:
            return {
                "final_severity": "medium",
                "consensus_confidence": 0.3,
                "is_true_positive": True,
                "false_positive_probability": 0.3,
                "agreement_score": 0.0,
                "dissenting_models": [],
                "reasoning": "Insufficient model responses for consensus",
                "model_breakdown": [],
            }

        # Collect weighted votes
        severity_votes: dict[str, float] = {}
        confidence_scores = []
        tp_votes = []
        fp_probs = []
        model_breakdown = []

        severity_order = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}

        for resp in valid_responses:
            model = resp["model"]
            response = resp["response"]
            weight = self.MODEL_WEIGHTS.get(model, 0.25)

            severity = response.get("recommended_severity", "medium").lower()
            confidence = float(response.get("confidence", 0.5))
            is_tp = bool(response.get("is_true_positive", True))
            fp_prob = float(response.get("false_positive_probability", 0.3))

            severity_votes[severity] = severity_votes.get(severity, 0) + weight
            confidence_scores.append(confidence * weight)
            tp_votes.append((is_tp, weight))
            fp_probs.append(fp_prob * weight)

            model_breakdown.append({
                "model": model.split("/")[-1],
                "severity": severity,
                "confidence": confidence,
                "is_true_positive": is_tp,
                "weight": weight,
                "reasoning": response.get("reasoning", ""),
            })

        # Determine winning severity
        final_severity = max(severity_votes, key=severity_votes.get)
        consensus_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        weighted_tp = sum(w for tp, w in tp_votes if tp) / sum(w for _, w in tp_votes)
        is_true_positive = weighted_tp > 0.5
        avg_fp_prob = sum(fp_probs) / len(fp_probs) if fp_probs else 0.3

        # Calculate agreement score
        total_weight = sum(severity_votes.values())
        winning_weight = severity_votes.get(final_severity, 0)
        agreement_score = winning_weight / total_weight if total_weight > 0 else 0.0

        # Find dissenting models
        dissenting = [
            b["model"] for b in model_breakdown
            if b["severity"] != final_severity
        ]

        return {
            "final_severity": final_severity,
            "consensus_confidence": round(consensus_confidence, 3),
            "is_true_positive": is_true_positive,
            "false_positive_probability": round(avg_fp_prob, 3),
            "agreement_score": round(agreement_score, 3),
            "dissenting_models": dissenting,
            "severity_vote_distribution": severity_votes,
            "model_breakdown": model_breakdown,
            "reasoning": (
                f"Consensus reached with {agreement_score:.0%} agreement. "
                f"Severity: {final_severity.upper()} with "
                f"{consensus_confidence:.0%} confidence across "
                f"{len(valid_responses)}/{len(model_responses)} models."
            ),
        }

    async def _save_agent_message(
        self,
        event: BandEvent,
        model_responses: list[dict],
        consensus: dict,
    ) -> None:
        breakdown_lines = "\n".join([
            f"- **{b['model']}**: {b['severity'].upper()} ({b['confidence']:.0%} confidence)"
            for b in consensus.get("model_breakdown", [])
        ])

        content = (
            f"**Multi-Model Consensus Analysis**\n\n"
            f"**Final Verdict:** {consensus['final_severity'].upper()}\n"
            f"**Consensus Confidence:** {consensus['consensus_confidence']:.0%}\n"
            f"**Agreement Score:** {consensus['agreement_score']:.0%}\n"
            f"**True Positive Probability:** {1 - consensus['false_positive_probability']:.0%}\n\n"
            f"**Model Breakdown:**\n{breakdown_lines}\n\n"
            f"**Reasoning:** {consensus['reasoning']}"
        )
        if consensus.get("dissenting_models"):
            content += f"\n\n⚠️ **Dissenting models:** {', '.join(consensus['dissenting_models'])}"

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="consensus",
                content=content,
                confidence_score=consensus["consensus_confidence"],
                extra_data={
                    "final_severity": consensus["final_severity"],
                    "agreement_score": consensus["agreement_score"],
                    "model_count": len(model_responses),
                    "valid_responses": len([r for r in model_responses if not r.get("error")]),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
