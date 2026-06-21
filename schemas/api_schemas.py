"""
AegisOne XDR – Pydantic schemas for API layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Incident ──────────────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    title: str
    description: str | None = None
    severity: str = "medium"
    source_type: str = "manual"
    source_data: dict[str, Any] | None = None
    affected_assets: list[str] | None = None
    ioc_list: list[dict[str, Any]] | None = None
    tags: list[str] | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    status: str | None = None
    assigned_to: str | None = None
    tags: list[str] | None = None


class IncidentResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    severity: str
    status: str
    source_type: str | None
    affected_assets: list[str] | None
    ioc_list: list[dict[str, Any]] | None
    mitre_techniques: list[dict[str, Any]] | None
    risk_score: float
    confidence_score: float
    consensus_result: dict[str, Any] | None
    remediation_plan: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    verification_result: dict[str, Any] | None
    report_url: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    assigned_to: str | None
    tags: list[str] | None

    class Config:
        from_attributes = True


# ── Approval ──────────────────────────────────────────────────────────────────

class ApprovalDecision(BaseModel):
    decision: str  # approved | rejected | modified
    reviewer_notes: str | None = None
    modified_actions: list[dict[str, Any]] | None = None
    reviewed_by: str = "security_analyst"


class ApprovalResponse(BaseModel):
    id: UUID
    incident_id: UUID
    proposed_actions: list[dict[str, Any]]
    risk_summary: str | None
    confidence_score: float | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    reviewer_notes: str | None
    modified_actions: list[dict[str, Any]] | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Agent Messages ────────────────────────────────────────────────────────────

class AgentMessageResponse(BaseModel):
    id: UUID
    incident_id: UUID
    agent_name: str
    message_type: str | None
    content: str
    confidence_score: float | None
    extra_data: dict[str, Any] | None
    band_event_type: str | None
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditEntryResponse(BaseModel):
    id: UUID
    incident_id: UUID
    actor: str
    actor_type: str
    action: str
    details: dict[str, Any] | None
    outcome: str | None
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Ingest ────────────────────────────────────────────────────────────────────

class EmailIngest(BaseModel):
    subject: str
    sender: str
    recipient: str
    body: str
    attachments: list[dict[str, Any]] | None = None
    headers: dict[str, str] | None = None
    received_at: datetime | None = None


class LogIngest(BaseModel):
    source: str  # syslog | aws | azure | gcp | endpoint
    log_lines: list[str]
    asset_id: str | None = None
    time_range: dict[str, str] | None = None


class ImageIngest(BaseModel):
    filename: str
    base64_data: str
    media_type: str = "image/png"
    context: str | None = None


# ── Dashboard Stats ───────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_incidents: int
    open_incidents: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    pending_approvals: int
    avg_risk_score: float
    top_mitre_techniques: list[dict[str, Any]]
    recent_iocs: list[dict[str, Any]]
    agent_activity: list[dict[str, Any]]


# ── WebSocket ─────────────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str
    incident_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None
