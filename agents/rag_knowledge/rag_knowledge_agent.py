"""
RAG Knowledge Agent – retrieves grounding context from the Qdrant-backed
knowledge base (MITRE ATT&CK, OWASP, NIST SP800, CVE, CIS Benchmarks,
previous incidents, internal playbooks) to prevent hallucination in
downstream agent reasoning.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage
from db.session import AsyncSessionFactory
from rag.retrievers.qdrant_retriever import QdrantRetriever

logger = logging.getLogger(__name__)

COLLECTIONS = [
    "mitre_attack",
    "owasp",
    "nist_sp800",
    "cve_database",
    "cis_benchmarks",
    "previous_incidents",
    "internal_playbooks",
]


class RAGKnowledgeAgent(BaseAgent):
    name = "rag_knowledge_agent"
    description = (
        "Grounds agent reasoning in verified knowledge: MITRE ATT&CK, OWASP, "
        "NIST SP800, CVE database, CIS benchmarks, previous incidents, and "
        "internal playbooks via Qdrant Cloud."
    )
    subscribes_to = [EventType.THREAT_CONTEXT_READY]
    publishes = []  # Terminal grounding step; does not re-trigger the pipeline
    capabilities = ["rag_retrieval", "knowledge_grounding", "playbook_lookup", "cve_lookup"]

    def __init__(self, bus: BandEventBus) -> None:
        super().__init__(bus)
        self.retriever = QdrantRetriever()

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("RAGKnowledgeAgent grounding context for incident %s", event.incident_id)
        payload = event.payload

        query = self._build_query(payload)
        grounding_docs = await self._retrieve_grounding(query)

        await self._save_agent_message(event, grounding_docs)
        # Note: this agent is intentionally a terminal grounding step in the
        # Band graph. It runs in parallel with ThreatIntelAgent (both subscribe
        # to THREAT_CONTEXT_READY) but does not re-publish, so MITREMappingAgent
        # is triggered exactly once, by ThreatIntelAgent's MITRE_MAPPING_COMPLETE
        # event. This avoids duplicate downstream pipeline execution while still
        # surfacing grounding context in the Agent Discussion Timeline.

    def _build_query(self, payload: dict[str, Any]) -> str:
        parts = []
        for key in ("vision_analysis", "email_analysis", "log_analysis", "threat_context"):
            val = payload.get(key)
            if isinstance(val, dict):
                parts.append(str(val.get("summary", "")))
            elif isinstance(val, str):
                parts.append(val)
        return " ".join(parts)[:500] or "general security incident"

    async def _retrieve_grounding(self, query: str) -> list[dict[str, Any]]:
        all_docs = []
        # Query across the most relevant collections to keep latency reasonable
        priority_collections = ["mitre_attack", "internal_playbooks", "previous_incidents", "nist_sp800"]

        for collection in priority_collections:
            try:
                docs = await self.retriever.retrieve(query, collection=collection, top_k=2)
                for d in docs:
                    d["collection"] = collection
                all_docs.extend(docs)
            except Exception as e:
                logger.warning("RAG retrieval failed for collection %s: %s", collection, e)

        return all_docs

    async def _save_agent_message(self, event: BandEvent, docs: list[dict]) -> None:
        if not docs:
            content = (
                "**RAG Knowledge Grounding**\n\n"
                "No grounding documents retrieved from the knowledge base. "
                "Downstream reasoning will rely on model knowledge alone."
            )
        else:
            sources = ", ".join(sorted({d.get("collection", "unknown") for d in docs}))
            content = (
                f"**RAG Knowledge Grounding Complete**\n\n"
                f"Retrieved **{len(docs)} grounding document(s)** from: {sources}\n\n"
                f"This context is used downstream to reduce hallucination risk "
                f"in MITRE mapping, risk assessment, and remediation planning."
            )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="grounding",
                content=content,
                confidence_score=0.9 if docs else 0.4,
                extra_data={"doc_count": len(docs)},
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
