"""
AegisOne XDR – Background Worker

This worker process hosts the same Band agent fleet as the API service,
but is intended to handle long-running and asynchronous work:
- Periodic incident health checks (stuck investigations)
- Verification retry loops (alternative remediation on failure)
- Scheduled threat-intel re-enrichment
- RAG knowledge base refresh jobs

In this hackathon architecture the FastAPI backend process also runs the
Band bus and agents in-process for simplicity (single Postgres-backed system,
no Redis/Kafka). The worker is kept as a separate Render service so that:
  1) Long-running loops never block the web service's event loop, and
  2) The architecture maps cleanly to "API service" + "Background worker"
     as required by the hackathon brief, while staying lightweight.

The worker polls the database directly (no message broker) which keeps the
footprint small and avoids extra infrastructure for a hackathon deployment.

ARCHITECTURE NOTE: The Band event bus is in-memory and per-process (by
design — no Redis/Kafka). The worker's bus instance is therefore independent
of the API service's bus instance. All incident pipeline execution
(Intake → … → Audit) happens synchronously inside the API service process,
triggered by POST /api/v1/incidents and the approvals endpoint, so the full
agent fleet reliably sees every event for a given incident within that one
process. This worker registers the same agent fleet so it CAN host pipeline
execution too, but today it is used for periodic maintenance jobs against
the shared Postgres database rather than live event handling — satisfying
the "web service + worker" Render architecture requirement while keeping
the deployment to a single Postgres instance and no broker.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from band.core.event_bus import BandEvent, band_bus
from band.events.event_types import EventType
from db.models import ApprovalRequest, Incident
from db.session import AsyncSessionFactory, create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] worker.%(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30
STUCK_INVESTIGATION_THRESHOLD = timedelta(minutes=15)


def register_agents() -> list:
    """Register the full Band agent fleet on this process's event bus."""
    from agents.intake.intake_agent import IntakeAgent
    from agents.vision.vision_agent import VisionAgent
    from agents.email.email_agent import EmailAgent
    from agents.log_analysis.log_analysis_agent import LogAnalysisAgent
    from agents.threat_intel.threat_intel_agent import ThreatIntelAgent
    from agents.malware.malware_agent import MalwareAgent
    from agents.rag_knowledge.rag_knowledge_agent import RAGKnowledgeAgent
    from agents.mitre_mapping.mitre_mapping_agent import MITREMappingAgent
    from agents.risk_assessment.risk_assessment_agent import RiskAssessmentAgent
    from agents.consensus.consensus_agent import ConsensusAgent
    from agents.red_team.red_team_agent import RedTeamSkepticAgent
    from agents.remediation.remediation_agent import RemediationAgent
    from agents.approval.approval_agent import ApprovalAgent
    from agents.execution.execution_agent import ExecutionAgent
    from agents.verification.verification_agent import VerificationAgent
    from agents.report.report_agent import ReportAgent
    from agents.audit_trail.audit_trail_agent import AuditTrailAgent

    return [
        IntakeAgent(band_bus),
        VisionAgent(band_bus),
        EmailAgent(band_bus),
        LogAnalysisAgent(band_bus),
        ThreatIntelAgent(band_bus),
        MalwareAgent(band_bus),
        RAGKnowledgeAgent(band_bus),
        MITREMappingAgent(band_bus),
        RiskAssessmentAgent(band_bus),
        ConsensusAgent(band_bus),
        RedTeamSkepticAgent(band_bus),
        RemediationAgent(band_bus),
        ApprovalAgent(band_bus),
        ExecutionAgent(band_bus),
        VerificationAgent(band_bus),
        ReportAgent(band_bus),
        AuditTrailAgent(band_bus),
    ]


async def check_stuck_investigations() -> None:
    """Find incidents stuck in 'investigating' for too long and flag them."""
    cutoff = datetime.now(timezone.utc) - STUCK_INVESTIGATION_THRESHOLD
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Incident).where(
                Incident.status == "investigating",
                Incident.updated_at < cutoff,
            )
        )
        stuck = result.scalars().all()
        for incident in stuck:
            logger.warning(
                "Incident %s has been investigating since %s — flagging for review",
                incident.id,
                incident.updated_at,
            )
            tags = list(incident.tags or [])
            if "needs_manual_review" not in tags:
                tags.append("needs_manual_review")
                incident.tags = tags
        if stuck:
            await session.commit()


async def check_pending_approval_age() -> None:
    """Surface approval requests that have been waiting too long (for alerting)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.status == "pending",
                ApprovalRequest.created_at < cutoff,
            )
        )
        aging = result.scalars().all()
        if aging:
            logger.warning(
                "%d approval request(s) pending for over 1 hour — consider escalation",
                len(aging),
            )


async def poll_loop() -> None:
    """Main worker polling loop."""
    logger.info("AegisOne worker starting poll loop (interval=%ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await check_stuck_investigations()
            await check_pending_approval_age()
        except Exception:
            logger.exception("Worker poll cycle failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    logger.info("AegisOne XDR worker booting…")
    await create_tables()

    agents = register_agents()
    logger.info("Worker registered %d Band agents", len(agents))

    await poll_loop()


if __name__ == "__main__":
    asyncio.run(main())
