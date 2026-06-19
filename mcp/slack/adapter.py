"""
MCP Slack Adapter – sends security alerts to Slack channels.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_BASE = "https://slack.com/api"

SEVERITY_COLORS = {
    "critical": "#FF0000",
    "high": "#FF8C00",
    "medium": "#FFD700",
    "low": "#00CED1",
    "info": "#808080",
}


class SlackAdapter:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or SLACK_BOT_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def send_security_alert(
        self,
        channel: str,
        incident_id: str,
        message: str,
        severity: str = "high",
    ) -> dict[str, Any]:
        if not self.token:
            logger.warning("Slack not configured; returning mock response")
            return {"ok": True, "channel": channel, "mock": True}

        color = SEVERITY_COLORS.get(severity, "#808080")
        payload = {
            "channel": channel,
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"🚨 AegisOne XDR Security Alert [{severity.upper()}]",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Incident ID:*\n{incident_id}"},
                                {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                            ],
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": message},
                        },
                    ],
                }
            ],
        }

        logger.info("Sending Slack alert to %s for incident %s", channel, incident_id)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SLACK_BASE}/chat.postMessage",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
