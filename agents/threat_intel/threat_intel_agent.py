"""
Threat Intelligence Agent – enriches IOCs via external threat intelligence feeds.
Uses MCP tool adapters for VirusTotal, AbuseIPDB, and Shodan.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage, ThreatIntelEntry
from db.session import AsyncSessionFactory
from services.featherless_client import featherless

logger = logging.getLogger(__name__)


class ThreatIntelAgent(BaseAgent):
    name = "threat_intel_agent"
    description = "Enriches indicators of compromise using VirusTotal, AbuseIPDB, and Shodan."
    subscribes_to = [
        EventType.THREAT_CONTEXT_READY,
        EventType.EMAIL_ANALYSIS_COMPLETE,
        EventType.LOG_ANALYSIS_COMPLETE,
        EventType.VISION_ANALYSIS_COMPLETE,
    ]
    publishes = [EventType.MITRE_MAPPING_COMPLETE]
    capabilities = ["virustotal", "abuseipdb", "shodan", "ioc_enrichment"]

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("ThreatIntelAgent processing event %s for incident %s",
                    event.event_type, event.incident_id)

        payload = event.payload
        iocs = payload.get("iocs", [])

        # Extract IOCs from various payload shapes
        if not iocs:
            iocs = self._extract_iocs(payload)

        enriched_iocs = []
        for ioc in iocs[:10]:  # Cap at 10 IOCs per incident for rate limiting
            enriched = await self._enrich_ioc(ioc)
            enriched_iocs.append(enriched)
            await self._persist_threat_intel(enriched)

        # Build contextual threat narrative using LLM
        threat_context = await self._build_threat_context(enriched_iocs, payload)

        # Persist agent message
        await self._save_agent_message(event, enriched_iocs, threat_context)

        await self.publish(
            event_type=EventType.MITRE_MAPPING_COMPLETE,
            incident_id=event.incident_id,
            payload={
                "enriched_iocs": enriched_iocs,
                "threat_context": threat_context,
                "ioc_count": len(enriched_iocs),
                "high_confidence_threats": [
                    ioc for ioc in enriched_iocs
                    if ioc.get("threat_score", 0) > 0.7
                ],
            },
            correlation_id=event.event_id,
        )

    def _extract_iocs(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract IOCs from different payload shapes."""
        iocs = []

        # From email
        if "email_data" in payload:
            email = payload["email_data"]
            sender = email.get("sender", "")
            if sender and "@" in sender:
                iocs.append({"type": "email", "value": sender})
            # Extract IPs from headers
            headers = email.get("headers", {})
            for key, val in headers.items():
                if "ip" in key.lower() and val:
                    iocs.append({"type": "ip", "value": val})

        # From log data
        if "log_data" in payload:
            log = payload["log_data"]
            log_lines = log.get("log_lines", [])
            iocs.extend(self._parse_iocs_from_logs(log_lines))

        # From incident data
        if "incident_data" in payload:
            incident = payload["incident_data"]
            raw_iocs = incident.get("ioc_list", [])
            if isinstance(raw_iocs, list):
                iocs.extend(raw_iocs)

        return iocs[:10]

    def _parse_iocs_from_logs(self, log_lines: list[str]) -> list[dict[str, Any]]:
        """Simple regex-based IOC extraction from log lines."""
        import re
        iocs = []
        ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        domain_pattern = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
        hash_pattern = re.compile(r"\b[a-fA-F0-9]{32,64}\b")

        combined = " ".join(log_lines)
        for ip in set(ip_pattern.findall(combined)):
            if not ip.startswith(("127.", "10.", "192.168.", "172.")):
                iocs.append({"type": "ip", "value": ip})
        for domain in set(domain_pattern.findall(combined)):
            if len(domain) > 5 and not domain.endswith(".log"):
                iocs.append({"type": "domain", "value": domain})
        for h in set(hash_pattern.findall(combined)):
            iocs.append({"type": "hash", "value": h})

        return iocs[:5]

    async def _enrich_ioc(self, ioc: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single IOC with threat intelligence data."""
        ioc_type = ioc.get("type", "unknown")
        ioc_value = ioc.get("value", "")

        enriched = {
            "type": ioc_type,
            "value": ioc_value,
            "threat_score": 0.0,
            "sources": [],
            "tags": [],
            "context": {},
        }

        try:
            if ioc_type == "ip":
                enriched = await self._enrich_ip(ioc_value, enriched)
            elif ioc_type in ("domain", "url"):
                enriched = await self._enrich_domain(ioc_value, enriched)
            elif ioc_type == "hash":
                enriched = await self._enrich_hash(ioc_value, enriched)
            elif ioc_type == "email":
                enriched = await self._enrich_email(ioc_value, enriched)
        except Exception as exc:
            logger.warning("IOC enrichment failed for %s: %s", ioc_value, exc)
            enriched["enrichment_error"] = str(exc)

        return enriched

    async def _enrich_ip(self, ip: str, enriched: dict) -> dict:
        """Enrich an IP address via AbuseIPDB and Shodan."""
        from mcp.abuseipdb.adapter import AbuseIPDBAdapter
        from mcp.shodan.adapter import ShodanAdapter

        try:
            abuse_result = await AbuseIPDBAdapter().check_ip(ip)
            enriched["sources"].append("abuseipdb")
            abuse_score = abuse_result.get("abuseConfidenceScore", 0) / 100.0
            enriched["context"]["abuseipdb"] = abuse_result
            enriched["threat_score"] = max(enriched["threat_score"], abuse_score)
            if abuse_result.get("isTor"):
                enriched["tags"].append("tor")
            if abuse_result.get("totalReports", 0) > 0:
                enriched["tags"].append("reported_malicious")
        except Exception as e:
            logger.warning("AbuseIPDB enrichment failed: %s", e)

        try:
            shodan_result = await ShodanAdapter().lookup_ip(ip)
            enriched["sources"].append("shodan")
            enriched["context"]["shodan"] = shodan_result
            ports = shodan_result.get("ports", [])
            if 22 in ports or 3389 in ports:
                enriched["tags"].append("exposed_remote_access")
        except Exception as e:
            logger.warning("Shodan enrichment failed: %s", e)

        return enriched

    async def _enrich_domain(self, domain: str, enriched: dict) -> dict:
        """Enrich a domain via VirusTotal."""
        from mcp.virustotal.adapter import VirusTotalAdapter

        try:
            vt_result = await VirusTotalAdapter().check_domain(domain)
            enriched["sources"].append("virustotal")
            stats = vt_result.get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            total = sum(stats.values()) or 1
            enriched["threat_score"] = max(enriched["threat_score"], malicious / total)
            enriched["context"]["virustotal"] = stats
            if malicious > 0:
                enriched["tags"].append("malicious_domain")
        except Exception as e:
            logger.warning("VirusTotal enrichment failed for domain %s: %s", domain, e)

        return enriched

    async def _enrich_hash(self, hash_value: str, enriched: dict) -> dict:
        """Enrich a file hash via VirusTotal."""
        from mcp.virustotal.adapter import VirusTotalAdapter

        try:
            vt_result = await VirusTotalAdapter().check_hash(hash_value)
            enriched["sources"].append("virustotal")
            stats = vt_result.get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            total = sum(stats.values()) or 1
            enriched["threat_score"] = max(enriched["threat_score"], malicious / total)
            enriched["context"]["virustotal"] = stats
            if malicious > 3:
                enriched["tags"].append("known_malware")
        except Exception as e:
            logger.warning("VirusTotal hash enrichment failed: %s", e)

        return enriched

    async def _enrich_email(self, email: str, enriched: dict) -> dict:
        """Basic email domain enrichment."""
        domain = email.split("@")[-1] if "@" in email else email
        return await self._enrich_domain(domain, enriched)

    async def _build_threat_context(
        self, enriched_iocs: list[dict], original_payload: dict
    ) -> dict[str, Any]:
        """Use LLM to synthesize a threat context narrative."""
        system_prompt = """You are a senior threat intelligence analyst at a cybersecurity SOC.
        Analyze the provided IOC enrichment data and produce a structured threat context.
        Return JSON only with these fields:
        {
          "threat_actor_profile": "string",
          "attack_pattern": "string",
          "severity_assessment": "critical|high|medium|low",
          "confidence": 0.0-1.0,
          "key_findings": ["string"],
          "recommended_actions": ["string"],
          "threat_narrative": "string"
        }"""

        user_prompt = f"""
        Enriched IOCs: {enriched_iocs}
        Original incident context: {str(original_payload)[:1000]}
        
        Provide threat context analysis as JSON.
        """

        try:
            return await featherless.json_completion(system_prompt, user_prompt)
        except Exception as e:
            logger.warning("LLM threat context failed: %s", e)
            high_score_iocs = [i for i in enriched_iocs if i.get("threat_score", 0) > 0.5]
            return {
                "threat_actor_profile": "Unknown",
                "attack_pattern": "Undetermined",
                "severity_assessment": "high" if high_score_iocs else "medium",
                "confidence": 0.5,
                "key_findings": [f"Found {len(enriched_iocs)} IOCs, {len(high_score_iocs)} high-confidence"],
                "recommended_actions": ["Isolate affected systems", "Block malicious IPs"],
                "threat_narrative": f"Analysis identified {len(enriched_iocs)} indicators of compromise requiring investigation.",
            }

    async def _persist_threat_intel(self, enriched: dict) -> None:
        """Persist enriched IOC to the database."""
        async with AsyncSessionFactory() as session:
            entry = ThreatIntelEntry(
                ioc_type=enriched.get("type", "unknown"),
                ioc_value=enriched.get("value", ""),
                threat_score=enriched.get("threat_score", 0.0),
                source=",".join(enriched.get("sources", [])),
                tags=enriched.get("tags", []),
                raw_data=enriched.get("context", {}),
            )
            session.add(entry)
            await session.commit()

    async def _save_agent_message(
        self, event: BandEvent, iocs: list, context: dict
    ) -> None:
        high_threats = [i for i in iocs if i.get("threat_score", 0) > 0.7]
        narrative = context.get("threat_narrative", "Analysis complete.")
        content = (
            f"**Threat Intelligence Analysis Complete**\n\n"
            f"Processed **{len(iocs)} IOCs** across VirusTotal, AbuseIPDB, and Shodan.\n"
            f"High-confidence threats: **{len(high_threats)}**\n\n"
            f"**Threat Narrative:** {narrative}\n\n"
            f"**Key Findings:** {'; '.join(context.get('key_findings', []))}"
        )

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="analysis",
                content=content,
                confidence_score=context.get("confidence", 0.7),
                extra_data={
                    "ioc_count": len(iocs),
                    "high_threat_count": len(high_threats),
                    "severity": context.get("severity_assessment"),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
