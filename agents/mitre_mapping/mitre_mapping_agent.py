"""
MITRE Mapping Agent – maps threats to ATT&CK techniques using RAG + LLM.
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

MITRE_SYSTEM_PROMPT = """You are a MITRE ATT&CK expert at a top-tier cybersecurity firm.
Map the provided threat intelligence to specific ATT&CK techniques and tactics.
Return ONLY valid JSON with this structure:
{
  "techniques": [
    {
      "technique_id": "T1234",
      "technique_name": "Technique Name",
      "tactic": "Tactic Name",
      "tactic_id": "TA0001",
      "confidence": 0.0-1.0,
      "evidence": "why this technique was identified"
    }
  ],
  "kill_chain_phase": "reconnaissance|weaponization|delivery|exploitation|installation|c2|actions",
  "attack_pattern_summary": "brief summary",
  "detection_opportunities": ["string"],
  "data_sources_needed": ["string"]
}"""


class MITREMappingAgent(BaseAgent):
    name = "mitre_mapping_agent"
    description = "Maps threat indicators to MITRE ATT&CK techniques and tactics."
    subscribes_to = [EventType.MITRE_MAPPING_COMPLETE]
    publishes = [EventType.RISK_ASSESSED]
    capabilities = ["mitre_attack", "rag_retrieval", "technique_mapping"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("MITREMappingAgent processing incident %s", event.incident_id)
        payload = event.payload

        enriched_iocs = payload.get("enriched_iocs", [])
        threat_context = payload.get("threat_context", {})

        # Retrieve relevant MITRE context from RAG
        rag_context = await self._retrieve_mitre_context(threat_context)

        # Map to ATT&CK techniques
        mapping_result = await self._map_to_attack(enriched_iocs, threat_context, rag_context)

        await self._save_agent_message(event, mapping_result)

        await self.publish(
            event_type=EventType.RISK_ASSESSED,
            incident_id=event.incident_id,
            payload={
                **payload,
                "mitre_mapping": mapping_result,
                "technique_count": len(mapping_result.get("techniques", [])),
                "kill_chain_phase": mapping_result.get("kill_chain_phase", "unknown"),
            },
            correlation_id=event.event_id,
        )

    async def _retrieve_mitre_context(self, threat_context: dict) -> str:
        """Retrieve relevant MITRE ATT&CK context from the RAG system."""
        try:
            from rag.retrievers.qdrant_retriever import QdrantRetriever
            query = threat_context.get("attack_pattern", "") + " " + threat_context.get("threat_narrative", "")
            retriever = QdrantRetriever()
            docs = await retriever.retrieve(query, collection="mitre_attack", top_k=5)
            return "\n\n".join([d.get("text", "") for d in docs])
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)
            return ""

    async def _map_to_attack(
        self,
        enriched_iocs: list[dict],
        threat_context: dict,
        rag_context: str,
    ) -> dict[str, Any]:
        """Use LLM to map threats to MITRE ATT&CK."""
        user_prompt = f"""
        Threat Context:
        {threat_context}
        
        Enriched IOCs:
        {enriched_iocs[:5]}
        
        Relevant MITRE ATT&CK Context from Knowledge Base:
        {rag_context[:2000] if rag_context else "Not available"}
        
        Map these threats to specific ATT&CK techniques. Return JSON only.
        """

        try:
            return await featherless.json_completion(MITRE_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning("MITRE mapping LLM call failed: %s", e)
            # Fallback heuristic mapping based on IOC types
            techniques = []
            ioc_types = {i.get("type") for i in enriched_iocs}

            if "ip" in ioc_types:
                techniques.append({
                    "technique_id": "T1071",
                    "technique_name": "Application Layer Protocol",
                    "tactic": "Command and Control",
                    "tactic_id": "TA0011",
                    "confidence": 0.6,
                    "evidence": "External IP communication detected",
                })
            if "email" in ioc_types:
                techniques.append({
                    "technique_id": "T1566",
                    "technique_name": "Phishing",
                    "tactic": "Initial Access",
                    "tactic_id": "TA0001",
                    "confidence": 0.7,
                    "evidence": "Suspicious email sender identified",
                })

            return {
                "techniques": techniques,
                "kill_chain_phase": "delivery",
                "attack_pattern_summary": "Potential multi-stage attack identified",
                "detection_opportunities": ["Monitor outbound connections", "Email filtering"],
                "data_sources_needed": ["Network logs", "Email logs"],
            }

    async def _save_agent_message(self, event: BandEvent, mapping: dict) -> None:
        techniques = mapping.get("techniques", [])
        technique_list = "\n".join([
            f"- **{t['technique_id']}** {t['technique_name']} (confidence: {t['confidence']:.0%})"
            for t in techniques[:5]
        ])

        content = (
            f"**MITRE ATT&CK Mapping Complete**\n\n"
            f"Identified **{len(techniques)} techniques** across the kill chain.\n"
            f"**Kill Chain Phase:** {mapping.get('kill_chain_phase', 'Unknown')}\n\n"
            f"**Top Techniques:**\n{technique_list or 'None identified'}\n\n"
            f"**Summary:** {mapping.get('attack_pattern_summary', 'N/A')}"
        )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="analysis",
                content=content,
                confidence_score=max(
                    [t.get("confidence", 0) for t in techniques], default=0.5
                ),
                extra_data={
                    "technique_count": len(techniques),
                    "kill_chain_phase": mapping.get("kill_chain_phase"),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
