"""
MCP Shodan Adapter – wraps Shodan API for host intelligence.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SHODAN_API_KEY = os.getenv("SHODAN_API_KEY", "")
SHODAN_BASE = "https://api.shodan.io"


class ShodanAdapter:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or SHODAN_API_KEY

    async def lookup_ip(self, ip: str) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("Shodan API key not configured; returning mock data")
            return self._mock_host(ip)

        logger.info("Shodan lookup: %s", ip)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{SHODAN_BASE}/shodan/host/{ip}",
                params={"key": self.api_key},
            )
            if resp.status_code == 404:
                return {"ip_str": ip, "ports": [], "hostnames": [], "not_found": True}
            resp.raise_for_status()
            data = resp.json()
            return {
                "ip_str": ip,
                "ports": data.get("ports", []),
                "hostnames": data.get("hostnames", []),
                "country_name": data.get("country_name"),
                "org": data.get("org"),
                "isp": data.get("isp"),
                "vulns": list(data.get("vulns", {}).keys()),
                "tags": data.get("tags", []),
            }

    def _mock_host(self, ip: str) -> dict[str, Any]:
        return {
            "ip_str": ip,
            "ports": [80, 443],
            "hostnames": [],
            "country_name": "Unknown",
            "org": "Unknown",
            "isp": "Unknown",
            "vulns": [],
            "tags": [],
            "mock": True,
        }
