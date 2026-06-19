"""
MCP AbuseIPDB Adapter – wraps AbuseIPDB API v2 for IP reputation checks.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ABUSEIPDB_BASE = "https://api.abuseipdb.com/api/v2"
ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY", "")


class AbuseIPDBAdapter:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or ABUSEIPDB_API_KEY
        self.headers = {
            "Key": self.api_key,
            "Accept": "application/json",
        }

    async def check_ip(self, ip: str, max_age_days: int = 90) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("AbuseIPDB API key not configured; returning mock data")
            return self._mock_check(ip)

        logger.info("AbuseIPDB check: %s", ip)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{ABUSEIPDB_BASE}/check",
                headers=self.headers,
                params={"ipAddress": ip, "maxAgeInDays": max_age_days, "verbose": True},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})

    async def report_ip(self, ip: str, categories: list[int], comment: str) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("AbuseIPDB API key not configured; returning mock report")
            return {"ipAddress": ip, "abuseConfidenceScore": 0, "mock": True}

        logger.info("AbuseIPDB report: %s (categories: %s)", ip, categories)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ABUSEIPDB_BASE}/report",
                headers=self.headers,
                data={
                    "ip": ip,
                    "categories": ",".join(map(str, categories)),
                    "comment": comment,
                },
            )
            resp.raise_for_status()
            return resp.json().get("data", {})

    def _mock_check(self, ip: str) -> dict[str, Any]:
        return {
            "ipAddress": ip,
            "isPublic": True,
            "abuseConfidenceScore": 0,
            "countryCode": "US",
            "totalReports": 0,
            "isTor": False,
            "mock": True,
        }
