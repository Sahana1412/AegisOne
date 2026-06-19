# AegisOne XDR — Complete File Manifest

134 files total. Organized by concern below; exact paths match the zip.

## Root / Deployment
.env.example
.gitignore
.dockerignore
README.md
requirements.txt
docker-compose.yml
docker/Dockerfile.backend
render.yaml
docs/ARCHITECTURE.md

## Band (event bus — the nervous system)
band/core/event_bus.py
band/events/event_types.py
band/registry/agent_registry.py
events/__init__.py            (spec-compliant re-export shim -> band.events)

## Database
db/models.py                  (SQLAlchemy: Incident, AgentMessage, ApprovalRequest, AuditEntry, ThreatIntelEntry, PlaybookEntry)
db/session.py                 (async engine + session factory + create_tables)
models/__init__.py            (spec-compliant re-export shim -> db.models)

## Schemas
schemas/api_schemas.py         (Pydantic request/response models)

## Shared Services
services/featherless_client.py (Featherless LLM client: chat/vision/json/consensus completions)

## Agents (17 total)
agents/base_agent.py           (abstract base — all comms via Band only)
agents/intake/intake_agent.py
agents/vision/vision_agent.py
agents/email/email_agent.py
agents/log_analysis/log_analysis_agent.py
agents/threat_intel/threat_intel_agent.py
agents/malware/malware_agent.py
agents/rag_knowledge/rag_knowledge_agent.py
agents/mitre_mapping/mitre_mapping_agent.py
agents/risk_assessment/risk_assessment_agent.py
agents/consensus/consensus_agent.py
agents/red_team/red_team_agent.py
agents/remediation/remediation_agent.py
agents/approval/approval_agent.py
agents/execution/execution_agent.py
agents/verification/verification_agent.py
agents/report/report_agent.py
agents/audit_trail/audit_trail_agent.py
(+ __init__.py in each agent folder)

## MCP Tool Adapters
mcp/virustotal/adapter.py
mcp/abuseipdb/adapter.py
mcp/shodan/adapter.py
mcp/github/adapter.py
mcp/slack/adapter.py
mcp/filesystem/adapter.py
mcp/email/adapter.py
mcp/postgresql/adapter.py
(+ __init__.py in each mcp folder)

## RAG
rag/retrievers/qdrant_retriever.py
rag/indexers/seed_knowledge_base.py
(+ __init__.py)

## Backend (FastAPI app)
backend/main.py                (app entrypoint, lifespan, registers all 17 agents)
api/routes/incidents.py
api/routes/approvals.py
api/routes/agents.py
api/routes/audit.py
api/routes/dashboard.py
api/routes/ingest.py
api/routes/websocket.py
(+ __init__.py files; backend/api, backend/core, backend/models, backend/services, backend/utils are reserved expansion slots, currently empty)

## Worker
worker/main.py                 (Render background worker: stuck-incident sweep, approval-aging check)

## Frontend (Next.js 15 + TypeScript + Tailwind)
frontend/package.json
frontend/package-lock.json
frontend/tsconfig.json
frontend/next.config.js
frontend/next-env.d.ts
frontend/tailwind.config.js
frontend/postcss.config.js
frontend/.eslintrc.json
frontend/.dockerignore
frontend/.env.local.example
frontend/Dockerfile

frontend/src/app/layout.tsx
frontend/src/app/globals.css
frontend/src/app/page.tsx                      (dashboard / SOC home)
frontend/src/app/incidents/page.tsx            (incident list + create modal)
frontend/src/app/incidents/[id]/page.tsx       (incident detail + Agent Discussion Timeline)
frontend/src/app/approvals/page.tsx            (human-in-the-loop approval center)
frontend/src/app/agents/page.tsx               (Band agent fleet + pipeline visualization)
frontend/src/app/audit/page.tsx                (immutable audit trail)

frontend/src/components/shared/Sidebar.tsx
frontend/src/components/shared/SeverityBadge.tsx
frontend/src/components/dashboard/MetricCard.tsx
frontend/src/components/dashboard/MitreHeatmap.tsx
frontend/src/components/incidents/IncidentRow.tsx
frontend/src/components/incidents/AgentTimeline.tsx   (the "wow factor" component)
frontend/src/components/agents/AgentStatusPanel.tsx
frontend/src/components/ui/button.tsx
frontend/src/components/ui/badge.tsx

frontend/src/lib/api.ts        (typed API client + WebSocket helper)
frontend/src/lib/utils.ts      (cn, formatters, severity/agent config maps)
