# 🛡️ AegisOne XDR

**AI-Powered Autonomous Detection, Investigation & Response Platform**

Built for the Band of Agents Hackathon. AegisOne XDR is a full-stack, multi-agent
cybersecurity platform where 17 specialized AI agents — orchestrated entirely
through **Band** — investigate incidents end-to-end: ingest → enrich → map to
MITRE ATT&CK → assess risk → reach multi-model consensus → red-team the
findings → propose remediation → wait for human approval → execute → verify
→ report → audit.

---

## Architecture at a Glance

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  Next.js 15  │◄────►│   FastAPI + WS    │◄────►│   Render PostgreSQL  │
│  Frontend    │ HTTP │   Backend API     │      │   (incidents, audit, │
│  (Tailwind,  │  WS  │   + Band Bus      │      │    approvals, etc.)  │
│   shadcn/ui) │      │   + 17 Agents     │      └─────────────────────┘
└─────────────┘      └─────────┬─────────┘
                                │
                ┌───────────────┼────────────────┐
                │               │                │
        ┌───────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
        │  Featherless  │ │ Qdrant Cloud │ │  MCP Tools    │
        │  (DeepSeek-R1,│ │  (RAG: MITRE,│ │ VirusTotal,   │
        │  Qwen3, Llama │ │  OWASP, NIST,│ │ AbuseIPDB,    │
        │  3.3, Mistral,│ │  CVE, CIS,   │ │ Shodan, GitHub│
        │  Qwen2.5-VL)  │ │  playbooks)  │ │ Slack, FS, PG │
        └───────────────┘ └──────────────┘ └───────────────┘

        ┌─────────────────────────────────────────────────┐
        │  Background Worker (Render worker service)       │
        │  Periodic maintenance: stuck-investigation sweep, │
        │  approval-aging checks. Shares Postgres with API. │
        └─────────────────────────────────────────────────┘
```

**No Redis. No Kafka.** Band's in-process async event bus is the entire
nervous system — agents never call each other directly, only through
`band.core.event_bus.BandEventBus`.

---

## The 17 Agents

| # | Agent | Role |
|---|-------|------|
| 1 | `intake_agent` | Normalizes raw incident data, routes to specialist pipelines |
| 2 | `vision_agent` | Multimodal screenshot/diagram analysis via Qwen2.5-VL |
| 3 | `email_agent` | Phishing & BEC detection |
| 4 | `log_analysis_agent` | SIEM-style log threat hunting |
| 5 | `threat_intel_agent` | VirusTotal / AbuseIPDB / Shodan enrichment |
| 6 | `malware_agent` | Static hash analysis & malware family triage |
| 7 | `rag_knowledge_agent` | Grounds reasoning in Qdrant-backed knowledge base |
| 8 | `mitre_mapping_agent` | Maps findings to MITRE ATT&CK techniques |
| 9 | `risk_assessment_agent` | FAIR-methodology quantitative risk scoring |
| 10 | `consensus_agent` | Aggregates DeepSeek-R1, Qwen3, Llama 3.3, Mistral votes |
| 11 | `red_team_agent` | Adversarially challenges the consensus verdict |
| 12 | `remediation_agent` | Proposes prioritized, reversible remediation actions |
| 13 | `approval_agent` | Bridges human approval decisions back into Band |
| 14 | `execution_agent` | Executes approved actions via MCP tools only |
| 15 | `verification_agent` | Confirms containment succeeded |
| 16 | `report_agent` | Generates executive incident reports |
| 17 | `audit_trail_agent` | Immutably logs every Band event (`subscribes_to = ["*"]`) |

Full event flow (each arrow is a Band event, not a direct call):

```
INCIDENT_CREATED
  -> (email|log|image)_ANALYSIS_COMPLETE -> THREAT_CONTEXT_READY
  -> [ThreatIntelAgent enriches]          -> MITRE_MAPPING_COMPLETE
  -> [MITREMappingAgent maps ATT&CK]      -> RISK_ASSESSED
  -> [RiskAssessmentAgent scores FAIR]    -> RISK_COMPUTED
  -> [ConsensusAgent: 4-model vote]       -> CONSENSUS_COMPLETE
  -> [RedTeamAgent challenges]            -> REMEDIATION_PROPOSED
  -> [RemediationAgent plans actions]     -> APPROVAL_REQUESTED
  -> PAUSE: HUMAN APPROVES / REJECTS via UI -> ACTION_APPROVED
  -> [ExecutionAgent runs MCP tools]      -> EXECUTION_COMPLETE
  -> [VerificationAgent confirms]         -> VERIFICATION_COMPLETE + REPORT_GENERATED
  -> [ReportAgent writes summary]         -> AUDIT_COMPLETE
```

`rag_knowledge_agent` and `audit_trail_agent` run in parallel off
`THREAT_CONTEXT_READY` / `"*"` respectively as grounding & logging
side-effects — they don't gate the main pipeline.

---

## Repository Layout

```
aegisone-xdr/
├── frontend/              Next.js 15 + TypeScript + Tailwind + shadcn/ui
├── backend/main.py        FastAPI app entrypoint (registers all agents)
├── worker/main.py         Background worker (Render worker service)
├── agents/                17 agent implementations, one folder each
├── band/                  Event bus, event type constants, agent registry
├── mcp/                   Tool adapters: virustotal, abuseipdb, shodan,
│                          github, slack, filesystem, email, postgresql
├── rag/                   Qdrant retriever + knowledge base seeder
├── db/                    SQLAlchemy async models + session factory
├── schemas/               Pydantic request/response schemas
├── api/routes/            incidents, approvals, agents, audit, dashboard,
│                          ingest, websocket
├── services/              Shared Featherless LLM client
├── docker/Dockerfile.backend
├── docker-compose.yml     Local dev: postgres + backend + frontend
├── render.yaml            One-click Render Blueprint deployment
├── requirements.txt
└── .env.example
```

---

## Running Locally

### Prerequisites
- Docker & Docker Compose
- A Featherless AI API key (required — this is the LLM provider for all agent reasoning)
- Optional: Qdrant Cloud cluster, VirusTotal/AbuseIPDB/Shodan/GitHub/Slack API keys (the platform runs with safe mock data if these are omitted)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env and set at minimum:
#   FEATHERLESS_API_KEY=...
```

### 2. Start everything with Docker Compose

```bash
docker compose up --build
```

This starts:
- `postgres` on `:5432`
- `backend` (FastAPI + Band agents) on `:8000`
- `frontend` (Next.js) on `:3000`

Open **http://localhost:3000** — you'll land on the Security Operations
Center dashboard.

### 3. Seed the RAG knowledge base (optional but recommended)

If you've configured `QDRANT_URL` / `QDRANT_API_KEY`:

```bash
docker compose exec backend python -m rag.indexers.seed_knowledge_base
```

Without Qdrant configured, the RAG agent gracefully falls back to a small
curated set of in-code MITRE/NIST snippets so the pipeline still runs end to
end.

### 4. Create your first incident

In the UI: **Incidents → New Incident**. Fill in a title, severity, and a
couple of comma-separated IOCs (e.g. `1.2.3.4, evil-domain.com`), then watch
the **Agent Discussion Timeline** populate in real time as Band orchestrates
the full pipeline — threat intel enrichment, MITRE mapping, FAIR risk
scoring, 4-model consensus, red-team challenge, and a remediation plan that
lands in the **Approval Center** for your sign-off.

Or via the API directly:

```bash
curl -X POST http://localhost:8000/api/v1/incidents/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Suspicious outbound connection to known C2 IP",
    "severity": "high",
    "source_type": "manual",
    "ioc_list": [{"type": "ip", "value": "185.220.101.1"}]
  }'
```

### 5. Approve or reject remediation

Go to **Approval Center**, review the proposed actions (block IP, disable
account, Slack alert, etc.), and click **Approve** or **Reject**. Only after
approval does `execution_agent` invoke any MCP tool — nothing is ever
auto-executed.

---

## Running Without Docker (manual)

**Backend:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://aegisone:aegisone@localhost:5432/aegisone
export FEATHERLESS_API_KEY=your_key
export PYTHONPATH=.
uvicorn backend.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_WS_URL=ws://localhost:8000" >> .env.local
npm run dev
```

**Worker (optional locally):**
```bash
python -m worker.main
```

You'll need a local Postgres instance — easiest via:
```bash
docker run -d --name aegis-pg -e POSTGRES_USER=aegisone -e POSTGRES_PASSWORD=aegisone -e POSTGRES_DB=aegisone -p 5432:5432 postgres:16-alpine
```

---

## Deploying to Render

This repo includes a ready-to-use **`render.yaml` Blueprint** that provisions:

1. **`aegisone-xdr-frontend`** — web service, Docker runtime, builds `frontend/Dockerfile`
2. **`aegisone-xdr-backend`** — web service, Docker runtime, builds `docker/Dockerfile.backend`, exposes REST + WebSocket
3. **`aegisone-xdr-worker`** — background worker, same Docker image, runs `python -m worker.main`
4. **`aegisone-xdr-db`** — managed Render PostgreSQL

### Steps

1. Push this repository to GitHub.
2. In the Render Dashboard: **New → Blueprint**, point it at your repo. Render will read `render.yaml` and propose all four services.
3. Before deploying, set the secret environment variables flagged `sync: false` in `render.yaml`:
   - `FEATHERLESS_API_KEY` (required)
   - `QDRANT_URL`, `QDRANT_API_KEY` (recommended)
   - `VIRUSTOTAL_API_KEY`, `ABUSEIPDB_API_KEY`, `SHODAN_API_KEY` (optional — mocked if absent)
   - `GITHUB_TOKEN`, `GITHUB_SECURITY_REPO`, `SLACK_BOT_TOKEN` (optional — mocked if absent)
4. Click **Apply**. Render builds and deploys all services; the database connection string is wired automatically via `fromDatabase`.
5. Once the backend is healthy (`/health` returns `200`), the frontend's `NEXT_PUBLIC_API_URL` (wired via `fromService`) will resolve correctly.
6. Visit your frontend's Render URL — you're live.

### Notes on the Render setup

- **Health checks**: backend uses `GET /health`; frontend uses `GET /`. Both Dockerfiles include `HEALTHCHECK` directives too.
- **Persistent storage**: this hackathon build keeps quarantined files under a local path (`/tmp/aegisone_quarantine` by default, override via `QUARANTINE_DIR`). For production durability, attach a Render Disk to the backend service and point `QUARANTINE_DIR` at the mount path, or switch `mcp/filesystem/adapter.py` to a Cloudinary-backed adapter.
- **Database migrations**: tables are created automatically on startup via SQLAlchemy `create_all()` (see `db/session.py: create_tables()`), which is sufficient for a hackathon deployment. For ongoing schema evolution, wire in Alembic.
- **Scaling**: the backend Dockerfile runs Uvicorn with 2 workers; bump `--workers` or the Render plan size as needed. The worker service runs a single lightweight polling loop and can stay on the smallest plan.

---

## Key Design Decisions

- **Band is the only nervous system.** Every agent extends `agents.base_agent.BaseAgent`, which forces all communication through `self.publish(...)` and `BandEventBus.subscribe(...)`. No agent imports or calls another agent's class directly.
- **Human-in-the-loop is structurally enforced.** `execution_agent` only subscribes to `ACTION_APPROVED` — there is no code path from `remediation_agent`'s proposal straight to execution.
- **Consensus fires exactly once per incident.** `risk_assessment_agent` re-publishes a distinct `RISK_COMPUTED` event (rather than re-using `RISK_ASSESSED`) specifically so `consensus_agent` doesn't double-fire — a subtle but important correctness detail in a pub/sub graph with re-publishing agents.
- **Graceful degradation everywhere.** Every MCP adapter and the Qdrant retriever return safe, clearly-labeled mock data (`"mock": true`) when API keys aren't configured, so the full pipeline — and the demo — never breaks because a third-party key is missing.
- **The Agent Discussion Timeline is the wow factor.** Every agent writes a human-readable Markdown message to `agent_messages` with a confidence score and the Band event that triggered it, rendered as a live, color-coded conversation thread on each incident's detail page.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, TailwindCSS, shadcn/ui primitives, lucide-react |
| Backend | FastAPI, Python 3.12, async SQLAlchemy 2.0, Pydantic v2 |
| Agent orchestration | Band (custom async pub/sub event bus) |
| LLM provider | Featherless AI — DeepSeek-R1, Qwen3, Llama 3.3, Mistral, Qwen2.5-VL |
| Vector DB / RAG | Qdrant Cloud + LangChain-style retrieval + sentence-transformers embeddings |
| Database | Render PostgreSQL (asyncpg) |
| Tool integrations | VirusTotal, AbuseIPDB, Shodan, GitHub, Slack, Filesystem — all via MCP-style adapters in `mcp/` |
| Deployment | Docker, Render Blueprint (`render.yaml`) |

---

## License

Built for the Band of Agents Hackathon. Use freely for demonstration and
educational purposes.
