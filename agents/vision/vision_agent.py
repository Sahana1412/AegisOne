"""
Vision Agent – analyzes screenshots, network diagrams, and visual artifacts
using Qwen2.5-VL multimodal model via Featherless.
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

VISION_ANALYSIS_PROMPT = """You are a cybersecurity analyst examining a visual artifact
(screenshot, dashboard, alert, network diagram, or phishing page).
Identify any signs of compromise, suspicious UI elements, phishing indicators,
malicious URLs/domains visible in the image, error messages, or anomalies.
Respond with a structured analysis covering:
1. What the image depicts
2. Suspicious elements identified (be specific about text/URLs/UI visible)
3. Potential threat indicators
4. Recommended next steps
Be concise and factual."""


class VisionAgent(BaseAgent):
    name = "vision_agent"
    description = "Analyzes screenshots and visual artifacts using Qwen2.5-VL multimodal AI."
    subscribes_to = [EventType.VISION_ANALYSIS_COMPLETE]
    publishes = [EventType.THREAT_CONTEXT_READY]
    capabilities = ["multimodal_analysis", "screenshot_triage", "phishing_page_detection", "qwen2.5-vl"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("VisionAgent analyzing image for incident %s", event.incident_id)
        payload = event.payload
        image_data = payload.get("image_data", {})

        base64_data = image_data.get("base64_data", "")
        media_type = image_data.get("media_type", "image/png")
        context = image_data.get("context", "")

        if not base64_data:
            await self._handle_missing_image(event)
            return

        analysis_text = await self._analyze_image(base64_data, media_type, context)
        extracted_iocs = self._extract_iocs_from_text(analysis_text)

        await self._save_agent_message(event, analysis_text, extracted_iocs)

        await self.publish(
            event_type=EventType.THREAT_CONTEXT_READY,
            incident_id=event.incident_id,
            payload={
                "source_type": "image",
                "vision_analysis": analysis_text,
                "iocs": extracted_iocs,
                "status": "ready_for_analysis",
            },
            correlation_id=event.event_id,
        )

    async def _analyze_image(self, base64_data: str, media_type: str, context: str) -> str:
        prompt = VISION_ANALYSIS_PROMPT
        if context:
            prompt += f"\n\nAdditional context provided by the reporting user: {context}"

        try:
            return await featherless.vision_completion(
                prompt=prompt,
                image_base64=base64_data,
                media_type=media_type,
            )
        except Exception as e:
            logger.warning("Vision LLM call failed: %s", e)
            return (
                "Vision analysis unavailable (model call failed). "
                "Manual review of the submitted image is recommended. "
                f"Context provided: {context or 'none'}"
            )

    def _extract_iocs_from_text(self, text: str) -> list[dict[str, Any]]:
        """Extract URLs/domains/IPs mentioned in the vision model's analysis."""
        import re
        iocs = []
        url_pattern = re.compile(r"https?://[^\s\)\]\"]+")
        domain_pattern = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
        ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

        for url in list(set(url_pattern.findall(text)))[:5]:
            iocs.append({"type": "url", "value": url})
        for domain in set(domain_pattern.findall(text)):
            if len(domain) > 5:
                iocs.append({"type": "domain", "value": domain})
        for ip in set(ip_pattern.findall(text)):
            iocs.append({"type": "ip", "value": ip})

        return iocs[:8]

    async def _handle_missing_image(self, event: BandEvent) -> None:
        await self.publish(
            event_type=EventType.THREAT_CONTEXT_READY,
            incident_id=event.incident_id,
            payload={
                "source_type": "image",
                "vision_analysis": "No image data provided.",
                "iocs": [],
                "status": "skipped_no_image",
            },
            correlation_id=event.event_id,
        )

    async def _save_agent_message(
        self, event: BandEvent, analysis: str, iocs: list[dict[str, Any]]
    ) -> None:
        ioc_summary = ", ".join([f"{i['type']}:{i['value']}" for i in iocs[:5]]) or "None identified"
        content = (
            f"**Visual Analysis Complete (Qwen2.5-VL)**\n\n"
            f"{analysis[:800]}{'...' if len(analysis) > 800 else ''}\n\n"
            f"**Extracted Indicators:** {ioc_summary}"
        )
        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="analysis",
                content=content,
                confidence_score=0.75,
                extra_data={"ioc_count": len(iocs)},
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
