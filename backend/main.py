"""
AegisOne XDR – FastAPI Application Entry Point
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.routes import incidents, agents, approvals, audit, dashboard, ingest, websocket
from db.session import create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://aegisone-xdr.onrender.com",
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    logger.info("AegisOne XDR starting up…")

    # Create database tables
    await create_tables()
    logger.info("Database tables ready")

    # Initialize and register all Band agents
    from band.core.event_bus import band_bus
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

    agents = [
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

    # Register WebSocket broadcaster for real-time frontend updates
    from api.routes.websocket import register_ws_listener
    register_ws_listener(band_bus)

    # Store agents on app state for access in routes
    app.state.band_bus = band_bus
    app.state.agents = agents
    logger.info("Registered %d Band agents", len(agents))

    yield

    logger.info("AegisOne XDR shutting down…")


app = FastAPI(
    title="AegisOne XDR",
    description="AI-Powered Autonomous Detection, Investigation and Response Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routes
app.include_router(incidents.router, prefix="/api/v1/incidents", tags=["incidents"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["approvals"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "aegisone-xdr-backend"}


@app.get("/")
async def root():
    return {
        "name": "AegisOne XDR API",
        "version": "1.0.0",
        "docs": "/api/docs",
    }
