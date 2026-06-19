"""
Email Agent – analyzes email headers, body, and attachments for phishing,
business email compromise (BEC), and malicious links.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage
from db.session import AsyncSessionFactory
from services.featherless_client import featherless

logger = logging.getLogger(__name__)

EMAIL_SYSTEM_PROMPT = """You are an email security analyst specializing in phishing
and business email compromise (BEC) detection.
Analyze the email for social engineering tactics, spoofing indicators, urgency/pressure
language, suspicious links, and impersonation attempts.
Return ONLY valid JSON:
{
  "is_phishing": true|false,
  "is_bec": true|false,
  "confidence": 0.0-1.0,
  "red_flags": ["string"],
  "sender_legitimacy": "legitimate|suspicious|spoofed|unknown",
  "urgency_tactics_detected": true|false,
  "suspicious_links": ["string"],
  "recommended_action": "string",
  "summary": "string"
}"""


class EmailAgent(BaseAgent):
    name = "email_agent"
    description = "Analyzes emails for phishing, BEC, and social engineering indicators."
    subscribes_to = [EventType.EMAIL_ANALYSIS_COMPLETE]
    publishes = [EventType.THREAT_CONTEXT_READY]
    capabilities = ["phishing_detection", "bec_detection", "header_analysis", "url_extraction"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("EmailAgent analyzing email for incident %s", event.incident_id)
        payload = event.payload
        email_data = payload.get("email_data", {})

        analysis = await self._analyze_email(email_data)
        iocs = self._extract_iocs(email_data, analysis)

        await self._save_agent_message(event, analysis, iocs)

        await self.publish(
            event_type=EventType.THREAT_CONTEXT_READY,
            incident_id=event.incident_id,
            payload={
                "source_type": "email",
                "email_analysis": analysis,
                "iocs": iocs,
                "status": "ready_for_analysis",
            },
            correlation_id=event.event_id,
        )

    async def _analyze_email(self, email_data: dict[str, Any]) -> dict[str, Any]:
        user_prompt = f"""
        Subject: {email_data.get("subject", "")}
        Sender: {email_data.get("sender", "")}
        Recipient: {email_data.get("recipient", "")}
        Body: {email_data.get("body", "")[:2000]}
        Headers: {email_data.get("headers", {})}
        
        Analyze for phishing/BEC indicators. Return JSON only.
        """
        try:
            return await featherless.json_completion(EMAIL_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning("Email analysis LLM call failed: %s", e)
            body = email_data.get("body", "")
            urgency_words = ["urgent", "immediately", "action required", "verify now", "suspended"]
            has_urgency = any(w in body.lower() for w in urgency_words)
            return {
                "is_phishing": has_urgency,
                "is_bec": False,
                "confidence": 0.5,
                "red_flags": ["Urgency language detected"] if has_urgency else [],
                "sender_legitimacy": "unknown",
                "urgency_tactics_detected": has_urgency,
                "suspicious_links": [],
                "recommended_action": "Manual review recommended",
                "summary": "Heuristic analysis applied due to LLM unavailability.",
            }

    def _extract_iocs(self, email_data: dict, analysis: dict) -> list[dict[str, Any]]:
        iocs = []
        sender = email_data.get("sender", "")
        if sender:
            iocs.append({"type": "email", "value": sender})

        body = email_data.get("body", "")
        url_pattern = re.compile(r"https?://[^\s\)\]\"]+")
        for url in list(set(url_pattern.findall(body)))[:5]:
            iocs.append({"type": "url", "value": url})

        for link in analysis.get("suspicious_links", [])[:5]:
            if not any(i["value"] == link for i in iocs):
                iocs.append({"type": "url", "value": link})

        return iocs

    async def _save_agent_message(
        self, event: BandEvent, analysis: dict, iocs: list[dict]
    ) -> None:
        flags = ", ".join(analysis.get("red_flags", [])) or "None"
        verdict = "🎯 PHISHING DETECTED" if analysis.get("is_phishing") else (
            "⚠️ BEC SUSPECTED" if analysis.get("is_bec") else "✅ No clear threat indicators"
        )

        content = (
            f"**Email Security Analysis**\n\n"
            f"**Verdict:** {verdict}\n"
            f"**Sender Legitimacy:** {analysis.get('sender_legitimacy', 'unknown').upper()}\n"
            f"**Confidence:** {analysis.get('confidence', 0.5):.0%}\n\n"
            f"**Red Flags:** {flags}\n"
            f"**Suspicious Links:** {len(analysis.get('suspicious_links', []))}\n\n"
            f"**Summary:** {analysis.get('summary', 'N/A')}"
        )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="analysis",
                content=content,
                confidence_score=analysis.get("confidence", 0.5),
                extra_data={
                    "is_phishing": analysis.get("is_phishing"),
                    "is_bec": analysis.get("is_bec"),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
