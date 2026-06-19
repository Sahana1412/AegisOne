"""
MCP Email Adapter – sends notification emails (e.g. to affected users or
the security team) as part of a remediation action. Uses SMTP directly so
it works with any provider (SES, SendGrid SMTP relay, Gmail SMTP, etc.)
without an extra SDK dependency.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", "aegisone-xdr@example.com")


class EmailAdapter:
    """Sends outbound notification emails. Falls back to a mock send (logged
    only) when SMTP credentials are not configured, so the pipeline never
    breaks during a hackathon demo without mail infrastructure."""

    def __init__(self) -> None:
        self.host = SMTP_HOST
        self.port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_address = SMTP_FROM_ADDRESS

    async def send_notification(
        self,
        to_address: str,
        subject: str,
        body: str,
        incident_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.host or not self.username:
            logger.warning(
                "SMTP not configured; mock-sending email to %s: %s", to_address, subject
            )
            return {
                "to": to_address,
                "subject": subject,
                "sent": True,
                "mock": True,
                "incident_id": incident_id,
            }

        msg = MIMEMultipart()
        msg["From"] = self.from_address
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            # smtplib is synchronous; run it off the event loop via asyncio's
            # default executor to avoid blocking other agents.
            import asyncio

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_sync, to_address, msg)
            logger.info("Sent notification email to %s (incident: %s)", to_address, incident_id)
            return {"to": to_address, "subject": subject, "sent": True, "mock": False}
        except Exception as e:
            logger.exception("Failed to send email to %s: %s", to_address, e)
            return {"to": to_address, "subject": subject, "sent": False, "error": str(e)}

    def _send_sync(self, to_address: str, msg: MIMEMultipart) -> None:
        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.from_address, [to_address], msg.as_string())
