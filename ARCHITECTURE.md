# AegisOne XDR — Architecture Reference

This document is a focused technical reference for the Band event graph and
the safety invariants enforced in code. For setup and deployment
instructions, see the top-level `README.md`.

## Band Event Graph

Every arrow below is a `BandEvent` published on `band.core.event_bus.band_bus`
and consumed by a subscriber's `handle_event`. No agent ever imports or calls
another agent's class directly — this is enforced structurally because
`BaseAgent` only exposes `self.publish(...)` as its outbound communication
method.

```
INCIDENT_CREATED
   |
   v
IntakeAgent  -- routes by source_type --
   |--(email)--> EMAIL_ANALYSIS_COMPLETE  -> EmailAgent       -> THREAT_CONTEXT_READY
   |--(log)----> LOG_ANALYSIS_COMPLETE    -> LogAnalysisAgent -> THREAT_CONTEXT_READY
   |--(image)--> VISION_ANALYSIS_COMPLETE -> VisionAgent      -> THREAT_CONTEXT_READY
   '--(manual)-------------------------------------------------> THREAT_CONTEXT_READY
                                                                       |
                              +----------------------------------------+
                              |                                        |
                              v                                        v
                    ThreatIntelAgent                         RAGKnowledgeAgent
                 (VirusTotal/AbuseIPDB/Shodan)              (Qdrant grounding —
                              |                              terminal, writes to
                              v                               timeline only,
                   MITRE_MAPPING_COMPLETE                     publishes nothing)
                              |
                              v
                     MITREMappingAgent
                              |
                              v
                        RISK_ASSESSED
                              |
                              v
                   RiskAssessmentAgent (FAIR)
                              |
                              v
                       RISK_COMPUTED  *** distinct from RISK_ASSESSED,
                              |            see "Why RISK_COMPUTED" below
                              v
                       ConsensusAgent
              (DeepSeek-R1, Qwen3, Llama 3.3, Mistral
               — weighted vote, run in parallel)
                              |
                              v
                     CONSENSUS_COMPLETE
                              |
                              v
                    RedTeamSkepticAgent
              (adversarial challenge, may override severity)
                              |
                              v
                   REMEDIATION_PROPOSED
                              |
                              v
                     RemediationAgent
              (builds prioritized action plan, creates
               ApprovalRequest row, status=pending)
                              |
                              v
                   APPROVAL_REQUESTED  ---->  [Approval Center UI]
                                                       |
                                          human clicks Approve / Reject
                                                       |
                                                       v
                                     POST /api/v1/approvals/{id}/decide
                                                       |
                              +------------------------+------------------------+
                              v                                                 v
                       ACTION_APPROVED                                  ACTION_REJECTED
                              |                                                 |
                              v                                                 v
                       ApprovalAgent                                    ApprovalAgent
                  (records authorization                          (records rejection,
                   in timeline)                                    incident returns to
                              |                                     "investigating")
                              v
                       ExecutionAgent
              (dispatches each action to its MCP tool:
               AbuseIPDB report, GitHub issue, Slack alert,
               filesystem quarantine, or simulated action)
                              |
                              v
              EXECUTION_COMPLETE / EXECUTION_FAILED
                              |
                              v
                     VerificationAgent
              (LLM-assessed containment check)
                              |
                  +-----------+-----------+
                  v                       v
        VERIFICATION_COMPLETE      REPORT_GENERATED
                                            |
                                            v
                                      ReportAgent
                                            |
                                            v
                                     AUDIT_COMPLETE
```

`AuditTrailAgent` subscribes to `"*"` (every event type) throughout the
entire graph and writes an immutable `AuditEntry` row for each one,
independent of the main flow.

## Why `RISK_COMPUTED` is a distinct event from `RISK_ASSESSED`

`MITREMappingAgent` publishes `RISK_ASSESSED` as a "please assess risk"
trigger. `RiskAssessmentAgent` subscribes to it, computes a FAIR score, and
needs to hand off to `ConsensusAgent`. The naive approach — re-publishing
`RISK_ASSESSED` with the score attached — would cause `ConsensusAgent` (if
it also subscribed to `RISK_ASSESSED`) to fire twice for the same incident:
once on the original trigger and once on the re-publish. `RiskAssessmentAgent`
instead publishes a new, distinct event type, `RISK_COMPUTED`, and
`ConsensusAgent` subscribes only to that. This guarantees exactly one
consensus run per incident and is the kind of subtlety that matters in any
pub/sub graph where an agent both consumes and re-publishes under a related
name.

## Safety Invariants

1. **No direct agent calls.** `BaseAgent.__init__` only wires `subscribe()`
   calls; there is no mechanism for one agent to hold a reference to
   another's instance.
2. **Execution requires human approval.** `ExecutionAgent.subscribes_to =
   [EventType.ACTION_APPROVED]` — there is no other event type that reaches
   it. `ACTION_APPROVED` is only ever published by the approvals API route
   after a human POSTs a decision; no agent publishes it autonomously.
3. **All tool invocations are auditable.** Every MCP adapter call inside
   `ExecutionAgent._execute_*` is wrapped in `_audit_action`, which writes an
   `AuditEntry` row with the action parameters and result before the event
   loop continues.
4. **Graceful degradation.** Every MCP adapter (`mcp/*/adapter.py`) and the
   Qdrant retriever check for a configured API key/URL before making a
   network call; if absent, they return a clearly-flagged mock response
   (`"mock": true`) rather than raising, so the full pipeline always
   completes even with zero third-party credentials configured.
