"""
AegisOne XDR – Band Event Type Constants
All event types that flow through the Band event bus.
"""


class EventType:
    # Incident lifecycle
    INCIDENT_CREATED = "incident_created"
    INCIDENT_UPDATED = "incident_updated"
    INCIDENT_CLOSED = "incident_closed"

    # Analysis events
    VISION_ANALYSIS_COMPLETE = "vision_analysis_complete"
    EMAIL_ANALYSIS_COMPLETE = "email_analysis_complete"
    LOG_ANALYSIS_COMPLETE = "log_analysis_complete"

    # Intelligence events
    THREAT_CONTEXT_READY = "threat_context_ready"
    MALWARE_ANALYSIS_COMPLETE = "malware_analysis_complete"
    RAG_CONTEXT_READY = "rag_context_ready"

    # Mapping and assessment
    MITRE_MAPPING_COMPLETE = "mitre_mapping_complete"
    RISK_ASSESSED = "risk_assessed"
    RISK_COMPUTED = "risk_computed"

    # Consensus
    CONSENSUS_COMPLETE = "consensus_complete"

    # Red team
    RED_TEAM_CHALLENGE_COMPLETE = "red_team_challenge_complete"

    # Remediation
    REMEDIATION_PROPOSED = "remediation_proposed"
    APPROVAL_REQUESTED = "approval_requested"
    ACTION_APPROVED = "action_approved"
    ACTION_REJECTED = "action_rejected"
    ACTION_MODIFIED = "action_modified"

    # Execution
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAILED = "execution_failed"

    # Verification
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETE = "verification_complete"
    VERIFICATION_FAILED = "verification_failed"

    # Reporting
    REPORT_GENERATED = "report_generated"

    # Audit
    AUDIT_COMPLETE = "audit_complete"
    AUDIT_ENTRY_CREATED = "audit_entry_created"

    # Agent status
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    # WebSocket broadcast
    WS_UPDATE = "ws_update"
