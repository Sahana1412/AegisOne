"""
MCP VirusTotal Adapter – wraps VirusTotal API v3 for IOC enrichment.
All invocations are logged for auditability.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

VT_BASE = "https://www.virustotal.com/api/v3"
VT_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")


class VirusTotalAdapter:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or VT_API_KEY
        self.headers = {"x-apikey": self.api_key}

    async def check_domain(self, domain: str) -> dict[str, Any]:
        return await self._get(f"/domains/{domain}")

    async def check_hash(self, file_hash: str) -> dict[str, Any]:
        return await self._get(f"/files/{file_hash}")

    async def check_url(self, url: str) -> dict[str, Any]:
        import base64
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        return await self._get(f"/urls/{url_id}")

    async def check_ip(self, ip: str) -> dict[str, Any]:
        return await self._get(f"/ip_addresses/{ip}")

    async def _get(self, path: str) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("VirusTotal API key not configured; returning mock data")
            return self._mock_response(path)

        url = f"{VT_BASE}{path}"
        logger.info("VirusTotal API call: GET %s", path)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 404:
                return {"error": "not_found", "data": {"attributes": {"last_analysis_stats": {}}}}
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("attributes", {})

    def _mock_response(self, path: str) -> dict[str, Any]:
        """Return safe mock data when API key is not configured."""
        return {
            "last_analysis_stats": {
                "malicious": 0,
                "suspicious": 0,
                "undetected": 50,
                "harmless": 10,
            },
            "reputation": 0,
            "mock": True,
        }
