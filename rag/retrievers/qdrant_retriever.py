"""
Qdrant RAG Retriever – retrieves relevant documents from Qdrant Cloud.
Used by agents to ground LLM responses in verified knowledge.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


class QdrantRetriever:
    """Retrieves relevant documents from Qdrant Cloud collections."""

    def __init__(self) -> None:
        self._client = None
        self._embedder = None

    def _get_client(self):
        if self._client is None:
            from qdrant_client import AsyncQdrantClient
            if QDRANT_URL and QDRANT_API_KEY:
                self._client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            else:
                logger.warning("Qdrant not configured; RAG will return empty results")
                self._client = None
        return self._client

    async def retrieve(
        self,
        query: str,
        collection: str = "mitre_attack",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve the top-k most relevant documents for a query."""
        client = self._get_client()
        if client is None:
            return self._fallback_docs(query, collection)

        try:
            embedding = await self._embed(query)
            from qdrant_client.models import ScoredPoint
            results: list[ScoredPoint] = await client.search(
                collection_name=collection,
                query_vector=embedding,
                limit=top_k,
                with_payload=True,
            )
            return [
                {
                    "text": r.payload.get("text", ""),
                    "source": r.payload.get("source", collection),
                    "score": r.score,
                    "metadata": {k: v for k, v in r.payload.items() if k != "text"},
                }
                for r in results
            ]
        except Exception as e:
            logger.warning("Qdrant retrieval failed: %s", e)
            return self._fallback_docs(query, collection)

    async def _embed(self, text: str) -> list[float]:
        """Generate embedding vector for a text."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(EMBEDDING_MODEL)
        embedding = self._embedder.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def _fallback_docs(self, query: str, collection: str) -> list[dict[str, Any]]:
        """Return curated fallback documents when Qdrant is unavailable."""
        fallbacks = {
            "mitre_attack": [
                {
                    "text": "T1566 - Phishing: Adversaries may send phishing messages to gain access to victim systems.",
                    "source": "mitre_attack",
                    "score": 0.7,
                    "metadata": {"technique_id": "T1566"},
                },
                {
                    "text": "T1071 - Application Layer Protocol: Adversaries may communicate using application layer protocols.",
                    "source": "mitre_attack",
                    "score": 0.65,
                    "metadata": {"technique_id": "T1071"},
                },
            ],
            "nist": [
                {
                    "text": "NIST SP800-61: Incident response lifecycle includes Preparation, Detection, Containment, Eradication, and Recovery.",
                    "source": "nist",
                    "score": 0.8,
                    "metadata": {"framework": "NIST SP800-61"},
                }
            ],
        }
        return fallbacks.get(collection, [])
