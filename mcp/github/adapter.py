"""
MCP GitHub Adapter – creates security issues and manages security workflows.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_SECURITY_REPO", "")  # format: owner/repo
GITHUB_BASE = "https://api.github.com"


class GitHubAdapter:
    def __init__(self, token: str | None = None, repo: str | None = None) -> None:
        self.token = token or GITHUB_TOKEN
        self.repo = repo or GITHUB_REPO
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_security_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.token or not self.repo:
            logger.warning("GitHub not configured; returning mock issue")
            return {
                "number": 0,
                "html_url": f"https://github.com/{self.repo or 'org/repo'}/issues/0",
                "title": title,
                "mock": True,
            }

        logger.info("Creating GitHub security issue: %s", title)
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{GITHUB_BASE}/repos/{self.repo}/issues",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "number": data["number"],
                "html_url": data["html_url"],
                "title": data["title"],
            }
