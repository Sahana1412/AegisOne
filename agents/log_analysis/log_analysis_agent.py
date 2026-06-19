"""
Log Analysis Agent – performs threat hunting across raw log lines
(syslog, cloud audit logs, endpoint telemetry) to surface anomalies.
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

LOG_SYSTEM_PROMPT = """You are a SOC analyst performing log-based threat hunting.
Analyze the provided log lines for signs of compromise: brute force attempts,
privilege escalation, lateral movement, unusual access patterns, data exfiltration,
or known attack signatures.
Return ONLY valid JSON:
{
  "anomalies_detected": true|false,
  "anomaly_types": ["string"],
  "confidence": 0.0-1.0,
  "affected_accounts": ["string"],
  "affected_hosts": ["string"],
  "suspicious_ips": ["string"],
  "timeline_summary": "string",
  "severity_indicator": "critical|high|medium|low",
  "summary": "string"
}"""


class LogAnalysisAgent(BaseAgent):
    name = "log_analysis_agent"
    description = "Threat hunts across raw logs for anomalies, brute force, and lateral movement."
    subscribes_to = [EventType.LOG_ANALYSIS_COMPLETE]
    publishes = [EventType.THREAT_CONTEXT_READY]
    capabilities = ["log_parsing", "anomaly_detection", "brute_force_detection", "siem_analysis"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("LogAnalysisAgent analyzing logs for incident %s", event.incident_id)
        payload = event.payload
        log_data = payload.get("log_data", {})
        log_lines = log_data.get("log_lines", [])

        analysis = await self._analyze_logs(log_lines, log_data)
        iocs = self._extract_iocs(log_lines, analysis)

        await self._save_agent_message(event, analysis, iocs, len(log_lines))

        await self.publish(
            event_type=EventType.THREAT_CONTEXT_READY,
            incident_id=event.incident_id,
            payload={
                "source_type": "log",
                "log_analysis": analysis,
                "iocs": iocs,
                "status": "ready_for_analysis",
            },
            correlation_id=event.event_id,
        )

    async def _analyze_logs(self, log_lines: list[str], log_data: dict) -> dict[str, Any]:
        sample = "\n".join(log_lines[:200])  # Cap context size
        user_prompt = f"""
        Log source: {log_data.get("source", "unknown")}
        Asset: {log_data.get("asset_id", "unknown")}
        Total lines: {len(log_lines)}
        
        Log sample:
        {sample[:4000]}
        
        Identify threats in these logs. Return JSON only.
        """
        try:
            return await featherless.json_completion(LOG_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning("Log analysis LLM call failed: %s", e)
            failed_logins = sum(1 for line in log_lines if re.search(r"fail(ed)?\s*login|authentication\s*fail", line, re.I))
            has_anomaly = failed_logins > 5
            return {
                "anomalies_detected": has_anomaly,
                "anomaly_types": ["Potential brute force"] if has_anomaly else [],
                "confidence": 0.5,
                "affected_accounts": [],
                "affected_hosts": [],
                "suspicious_ips": [],
                "timeline_summary": f"Found {failed_logins} failed login indicators across {len(log_lines)} lines.",
                "severity_indicator": "high" if has_anomaly else "low",
                "summary": "Heuristic regex analysis applied due to LLM unavailability.",
            }

    def _extract_iocs(self, log_lines: list[str], analysis: dict) -> list[dict[str, Any]]:
        iocs = []
        ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        combined = " ".join(log_lines[:500])

        for ip in set(ip_pattern.findall(combined)):
            if not ip.startswith(("127.", "10.", "192.168.", "172.")):
                iocs.append({"type": "ip", "value": ip})

        for ip in analysis.get("suspicious_ips", []):
            if not any(i["value"] == ip for i in iocs):
                iocs.append({"type": "ip", "value": ip})

        return iocs[:10]

    async def _save_agent_message(
        self, event: BandEvent, analysis: dict, iocs: list, line_count: int
    ) -> None:
        verdict = "🚨 ANOMALIES DETECTED" if analysis.get("anomalies_detected") else "✅ No significant anomalies"
        content = (
            f"**Log Analysis Complete**\n\n"
            f"**Verdict:** {verdict}\n"
            f"**Lines Analyzed:** {line_count}\n"
            f"**Severity Indicator:** {analysis.get('severity_indicator', 'low').upper()}\n\n"
            f"**Anomaly Types:** {', '.join(analysis.get('anomaly_types', [])) or 'None'}\n"
            f"**Affected Hosts:** {', '.join(analysis.get('affected_hosts', [])) or 'None'}\n"
            f"**Suspicious IPs:** {len(iocs)}\n\n"
            f"**Timeline:** {analysis.get('timeline_summary', 'N/A')}"
        )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="analysis",
                content=content,
                confidence_score=analysis.get("confidence", 0.5),
                extra_data={
                    "anomalies_detected": analysis.get("anomalies_detected"),
                    "line_count": line_count,
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
