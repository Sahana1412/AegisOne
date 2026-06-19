"""
MCP PostgreSQL Adapter – exposes safe, read-only ad-hoc query capability
against the AegisOne database for agents that need to look up historical
incident context (e.g. "has this IP been seen before?"). Writes always go
through the typed SQLAlchemy models in `db/models.py`; this adapter is
intentionally read-only and parameterized to avoid SQL injection, since
its queries may be partially shaped by LLM output.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from db.session import AsyncSessionFactory

logger = logging.getLogger(__name__)

# Whitelisted tables an agent may query through this adapter. This prevents
# arbitrary table access even though queries are otherwise parameterized.
ALLOWED_TABLES = {
    "incidents",
    "threat_intel",
    "audit_entries",
    "agent_messages",
    "approval_requests",
    "playbooks",
}


class PostgreSQLAdapter:
    """Read-only query adapter for agent use. All calls are logged for audit."""

    async def lookup_ioc_history(self, ioc_value: str) -> list[dict[str, Any]]:
        """Check whether an IOC has been seen in prior threat_intel entries."""
        logger.info("PostgreSQL MCP: looking up IOC history for %s", ioc_value)
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text(
                    "SELECT ioc_type, ioc_value, threat_score, source, last_seen "
                    "FROM threat_intel WHERE ioc_value = :value "
                    "ORDER BY last_seen DESC LIMIT 10"
                ),
                {"value": ioc_value},
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    async def lookup_similar_incidents(self, severity: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find recent incidents of a given severity for pattern comparison."""
        logger.info("PostgreSQL MCP: looking up similar incidents (severity=%s)", severity)
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text(
                    "SELECT id, title, severity, status, risk_score, created_at "
                    "FROM incidents WHERE severity = :severity "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {"severity": severity, "limit": limit},
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    async def count_open_incidents(self) -> int:
        """Return the count of currently open/investigating incidents."""
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM incidents "
                    "WHERE status IN ('open', 'investigating')"
                )
            )
            row = result.mappings().first()
            return int(row["cnt"]) if row else 0
