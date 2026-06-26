"""
AegisOne XDR – SQLAlchemy async database models.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(512), nullable=False)
    description = Column(Text)
    severity = Column(
        Enum("critical", "high", "medium", "low", "info", name="severity_enum"),
        default="medium",
        nullable=False,
    )
    status = Column(
        Enum(
            "open", "investigating", "awaiting_approval", "remediating",
            "verifying", "closed", "false_positive",
            name="incident_status_enum",
        ),
        default="open",
        nullable=False,
    )
    source_type = Column(String(64))  # email | log | image | api | manual
    source_data = Column(JSON)  # raw ingest payload
    affected_assets = Column(JSON)
    ioc_list = Column(JSON)  # indicators of compromise
    mitre_techniques = Column(JSON)
    risk_score = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.0)
    consensus_result = Column(JSON)
    remediation_plan = Column(JSON)
    execution_result = Column(JSON)
    verification_result = Column(JSON)
    report_url = Column(String(512))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    closed_at = Column(DateTime(timezone=True))
    assigned_to = Column(String(128))
    tags = Column(JSON, default=list)

    # Relationships
    events = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")
    approvals = relationship("ApprovalRequest", back_populates="incident", cascade="all, delete-orphan")
    audit_entries = relationship("AuditEntry", back_populates="incident", cascade="all, delete-orphan")
    agent_messages = relationship("AgentMessage", back_populates="incident", cascade="all, delete-orphan")


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    event_type = Column(String(128), nullable=False)
    source_agent = Column(String(64))
    payload = Column(JSON)
    correlation_id = Column(String(128))
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    incident = relationship("Incident", back_populates="events")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    proposed_actions = Column(JSON, nullable=False)
    risk_summary = Column(Text)
    confidence_score = Column(Float)
    status = Column(
        Enum("pending", "approved", "rejected", "modified", name="approval_status_enum"),
        default="pending",
        nullable=False,
    )
    reviewed_by = Column(String(128))
    reviewed_at = Column(DateTime(timezone=True))
    reviewer_notes = Column(Text)
    modified_actions = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    incident = relationship("Incident", back_populates="approvals")


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    actor = Column(String(128), nullable=False)  # agent name or human user
    actor_type = Column(Enum("agent", "human", "system", name="actor_type_enum"), nullable=False)
    action = Column(String(256), nullable=False)
    details = Column(JSON)
    outcome = Column(String(64))  # success | failure | pending
    ip_address = Column(String(64))
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    incident = relationship("Incident", back_populates="audit_entries")


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    agent_name = Column(String(64), nullable=False)
    message_type = Column(String(64))  # analysis | finding | recommendation | challenge | approval
    content = Column(Text, nullable=False)
    confidence_score = Column(Float)
    extra_data = Column(JSON)
    band_event_type = Column(String(128))
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    incident = relationship("Incident", back_populates="agent_messages")


class ThreatIntelEntry(Base):
    __tablename__ = "threat_intel"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ioc_type = Column(String(32), nullable=False)  # ip | domain | hash | url | email
    ioc_value = Column(String(512), nullable=False, index=True)
    threat_score = Column(Float, default=0.0)
    source = Column(String(64))  # virustotal | abuseipdb | shodan | internal
    tags = Column(JSON)
    raw_data = Column(JSON)
    last_seen = Column(DateTime(timezone=True), default=utcnow)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class PlaybookEntry(Base):
    __tablename__ = "playbooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(256), nullable=False)
    trigger_conditions = Column(JSON)
    steps = Column(JSON, nullable=False)
    mitre_techniques = Column(JSON)
    severity_threshold = Column(String(16))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
