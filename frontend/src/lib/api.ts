const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_V1 = `${API_BASE}/api/v1`;

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Incident {
  id: string;
  title: string;
  description: string | null;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  status: string;
  source_type: string | null;
  affected_assets: string[] | null;
  ioc_list: Record<string, string>[] | null;
  mitre_techniques: Record<string, unknown>[] | null;
  risk_score: number;
  confidence_score: number;
  consensus_result: Record<string, unknown> | null;
  remediation_plan: Record<string, unknown> | null;
  execution_result: Record<string, unknown> | null;
  verification_result: Record<string, unknown> | null;
  report_url: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  assigned_to: string | null;
  tags: string[] | null;
}

export interface AgentMessage {
  id: string;
  incident_id: string;
  agent_name: string;
  message_type: string;
  content: string;
  confidence_score: number | null;
  extra_data: Record<string, unknown> | null;
  band_event_type: string | null;
  timestamp: string;
}

export interface ApprovalRequest {
  id: string;
  incident_id: string;
  proposed_actions: RemediationAction[];
  risk_summary: string | null;
  confidence_score: number | null;
  status: 'pending' | 'approved' | 'rejected' | 'modified';
  reviewed_by: string | null;
  reviewed_at: string | null;
  reviewer_notes: string | null;
  modified_actions: RemediationAction[] | null;
  created_at: string;
}

export interface RemediationAction {
  action_id: string;
  action_type: string;
  priority: number;
  title: string;
  description: string;
  parameters: Record<string, unknown>;
  mcp_tool: string;
  reversible: boolean;
  estimated_impact: string;
  requires_downtime: boolean;
}

export interface AuditEntry {
  id: string;
  incident_id: string;
  actor: string;
  actor_type: string;
  action: string;
  details: Record<string, unknown> | null;
  outcome: string | null;
  timestamp: string;
}

export interface AgentInfo {
  name: string;
  description: string;
  subscribes_to: string[];
  publishes: string[];
  status: 'idle' | 'running' | 'error';
  last_active: string | null;
  message_count: number;
  error_count: number;
  capabilities: string[];
}

export interface DashboardStats {
  total_incidents: number;
  open_incidents: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  pending_approvals: number;
  avg_risk_score: number;
  top_mitre_techniques: { technique_id: string; count: number }[];
  recent_iocs: { ioc_type: string; ioc_value: string; threat_score: number; tags: string[] }[];
  agent_activity: unknown[];
}

// ── Incidents ──────────────────────────────────────────────────────────────

export const incidents = {
  list: (params?: { severity?: string; status?: string }) => {
    const qs = params ? '?' + new URLSearchParams(params as Record<string, string>).toString() : '';
    return apiFetch<Incident[]>(`/incidents/${qs}`);
  },
  get: (id: string) => apiFetch<Incident>(`/incidents/${id}`),
  create: (body: {
    title: string;
    description?: string;
    severity?: string;
    source_type?: string;
    source_data?: Record<string, unknown>;
    ioc_list?: Record<string, string>[];
    tags?: string[];
  }) => apiFetch<Incident>('/incidents/', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: Partial<Incident>) =>
    apiFetch<Incident>(`/incidents/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  messages: (id: string) => apiFetch<AgentMessage[]>(`/incidents/${id}/messages`),
  events: (id: string) => apiFetch<unknown[]>(`/incidents/${id}/events`),
  rerun: (id: string) => apiFetch<{ message: string }>(`/incidents/${id}/rerun`, { method: 'POST' }),
};

// ── Approvals ──────────────────────────────────────────────────────────────

export const approvals = {
  list: (status?: string) => {
    const qs = status ? `?status=${status}` : '';
    return apiFetch<ApprovalRequest[]>(`/approvals/${qs}`);
  },
  get: (id: string) => apiFetch<ApprovalRequest>(`/approvals/${id}`),
  decide: (id: string, body: {
    decision: 'approved' | 'rejected' | 'modified';
    reviewer_notes?: string;
    modified_actions?: RemediationAction[];
    reviewed_by?: string;
  }) => apiFetch<ApprovalRequest>(`/approvals/${id}/decide`, { method: 'POST', body: JSON.stringify(body) }),
};

// ── Agents ─────────────────────────────────────────────────────────────────

export const agentsApi = {
  list: () => apiFetch<AgentInfo[]>('/agents/'),
  events: () => apiFetch<unknown[]>('/agents/events'),
};

// ── Dashboard ──────────────────────────────────────────────────────────────

export const dashboard = {
  stats: () => apiFetch<DashboardStats>('/dashboard/stats'),
};

// ── Audit ──────────────────────────────────────────────────────────────────

export const audit = {
  list: (incident_id?: string) => {
    const qs = incident_id ? `?incident_id=${incident_id}` : '';
    return apiFetch<AuditEntry[]>(`/audit/${qs}`);
  },
};

// ── Ingest ─────────────────────────────────────────────────────────────────

export const ingest = {
  email: (body: {
    subject: string; sender: string; recipient: string; body: string;
  }) => apiFetch<{ incident_id: string }>('/ingest/email', { method: 'POST', body: JSON.stringify(body) }),
  log: (body: { source: string; log_lines: string[] }) =>
    apiFetch<{ incident_id: string }>('/ingest/log', { method: 'POST', body: JSON.stringify(body) }),
};

// ── WebSocket ──────────────────────────────────────────────────────────────

export const WS_BASE = (process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000').replace(/^http/, 'ws');

export function createIncidentWebSocket(
  incidentId: string,
  onMessage: (data: unknown) => void,
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/incidents/${incidentId}`);
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)); } catch { /* ignore */ }
  };
  return ws;
}
