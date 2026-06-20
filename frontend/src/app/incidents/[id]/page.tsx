'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, RefreshCw, AlertTriangle, Clock, Shield,
  ChevronDown, ChevronUp, Play, ExternalLink
} from 'lucide-react';
import Link from 'next/link';
import { incidents } from '@/lib/api';
import type { Incident as IncidentType, AgentMessage } from '@/lib/api';
import { Sidebar } from '@/components/shared/Sidebar';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { AgentTimeline } from '@/components/incidents/AgentTimeline';
import { formatDateTime, formatTimeAgo, cn } from '@/lib/utils';

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [incident, setIncident] = useState<IncidentType | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'timeline' | 'details' | 'mitre' | 'remediation'>('timeline');
  const [rerunning, setRerunning] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [inc, msgs] = await Promise.all([
        incidents.get(id),
        incidents.messages(id),
      ]);
      setIncident(inc);
      setMessages(msgs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRerun = async () => {
    setRerunning(true);
    try {
      await incidents.rerun(id);
      setTimeout(fetchData, 2000);
    } finally {
      setRerunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen overflow-hidden bg-aegis-bg">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-aegis-muted animate-pulse">Loading incident…</div>
        </main>
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="flex h-screen overflow-hidden bg-aegis-bg">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <AlertTriangle className="w-10 h-10 text-aegis-critical mx-auto mb-3" />
            <p className="text-aegis-text">Incident not found</p>
            <Link href="/incidents" className="text-aegis-accent text-sm mt-2 block">← Back to incidents</Link>
          </div>
        </main>
      </div>
    );
  }

  const consensus = incident.consensus_result as any;
  const mitreData = incident.mitre_techniques as any[] ?? [];

  return (
    <div className="flex h-screen overflow-hidden bg-aegis-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-aegis-bg/90 backdrop-blur-sm border-b border-aegis-border px-6 py-4">
          <div className="flex items-center gap-4">
            <button onClick={() => router.back()} className="text-aegis-muted hover:text-aegis-text transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3">
                <SeverityBadge severity={incident.severity} />
                <h1 className="text-base font-semibold text-aegis-text truncate">{incident.title}</h1>
              </div>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-xs text-aegis-muted font-mono">{id.slice(0, 8)}…</span>
                <span className="text-xs text-aegis-muted">·</span>
                <span className="text-xs text-aegis-muted">{formatTimeAgo(incident.created_at)}</span>
                <span className="text-xs text-aegis-muted">·</span>
                <span className={cn('text-xs font-mono uppercase px-1.5 py-0.5 rounded',
                  incident.status === 'closed' ? 'text-aegis-low bg-green-950/30' :
                  incident.status === 'investigating' ? 'text-aegis-accent bg-cyan-950/30' :
                  incident.status === 'awaiting_approval' ? 'text-aegis-medium bg-yellow-950/30' :
                  'text-aegis-muted bg-aegis-border/30'
                )}>
                  {incident.status.replace(/_/g, ' ')}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleRerun}
                disabled={rerunning}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-aegis-border/50 hover:bg-aegis-border rounded border border-aegis-border hover:border-aegis-accent/50 text-aegis-text-dim hover:text-aegis-accent transition-all"
              >
                <Play className={cn('w-3 h-3', rerunning && 'animate-spin')} />
                {rerunning ? 'Running…' : 'Re-run Analysis'}
              </button>
              <button onClick={fetchData} className="p-1.5 text-aegis-muted hover:text-aegis-accent transition-colors rounded">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="p-6">
          {/* Quick Stats */}
          <div className="grid grid-cols-4 gap-3 mb-6">
            {[
              { label: 'Risk Score', value: incident.risk_score > 0 ? `${(incident.risk_score * 100).toFixed(0)}%` : 'Pending', color: incident.risk_score > 0.7 ? 'text-aegis-critical' : 'text-aegis-medium' },
              { label: 'Confidence', value: consensus?.consensus_confidence ? `${(consensus.consensus_confidence * 100).toFixed(0)}%` : 'Pending', color: 'text-aegis-accent' },
              { label: 'IOCs Found', value: incident.ioc_list?.length ?? 0, color: 'text-orange-400' },
              { label: 'Agent Messages', value: messages.length, color: 'text-purple-400' },
            ].map((stat) => (
              <div key={stat.label} className="aegis-card p-3">
                <div className="text-[10px] text-aegis-muted uppercase">{stat.label}</div>
                <div className={cn('text-xl font-bold font-mono mt-1', stat.color)}>{stat.value}</div>
              </div>
            ))}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mb-4 border-b border-aegis-border">
            {(['timeline', 'details', 'mitre', 'remediation'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={cn(
                  'px-4 py-2 text-sm capitalize transition-all border-b-2 -mb-px',
                  activeTab === tab
                    ? 'text-aegis-accent border-aegis-accent'
                    : 'text-aegis-muted border-transparent hover:text-aegis-text'
                )}
              >
                {tab === 'timeline' ? '🤖 Agent Discussion' :
                 tab === 'details' ? '📋 Details' :
                 tab === 'mitre' ? '🗺️ MITRE ATT&CK' :
                 '🛠️ Remediation'}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === 'timeline' && (
            <AgentTimeline messages={messages} incidentId={id} />
          )}

          {activeTab === 'details' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="aegis-card p-4 space-y-3">
                <h3 className="text-sm font-semibold text-aegis-text">Incident Details</h3>
                {incident.description && (
                  <div>
                    <div className="text-xs text-aegis-muted mb-1">Description</div>
                    <p className="text-sm text-aegis-text-dim">{incident.description}</p>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-aegis-muted mb-1">Source</div>
                    <div className="text-sm font-mono text-aegis-text">{incident.source_type ?? 'manual'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-aegis-muted mb-1">Created</div>
                    <div className="text-sm font-mono text-aegis-text">{formatDateTime(incident.created_at)}</div>
                  </div>
                </div>
              </div>
              <div className="aegis-card p-4 space-y-3">
                <h3 className="text-sm font-semibold text-aegis-text">IOC List</h3>
                {(incident.ioc_list ?? []).length === 0 ? (
                  <p className="text-sm text-aegis-muted">No IOCs recorded yet.</p>
                ) : (
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {(incident.ioc_list ?? []).map((ioc: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="px-1.5 py-0.5 bg-aegis-border rounded font-mono text-aegis-muted uppercase">{ioc.type}</span>
                        <span className="font-mono text-aegis-text truncate">{ioc.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {consensus && (
                <div className="aegis-card p-4 col-span-2">
                  <h3 className="text-sm font-semibold text-aegis-text mb-3">Consensus Result</h3>
                  <div className="grid grid-cols-4 gap-3">
                    <div>
                      <div className="text-xs text-aegis-muted">Verdict</div>
                      <div className="text-sm font-bold text-aegis-accent uppercase">{consensus.final_severity}</div>
                    </div>
                    <div>
                      <div className="text-xs text-aegis-muted">Confidence</div>
                      <div className="text-sm font-mono text-aegis-text">{(consensus.consensus_confidence * 100).toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-xs text-aegis-muted">Agreement</div>
                      <div className="text-sm font-mono text-aegis-text">{((consensus.agreement_score ?? 0) * 100).toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-xs text-aegis-muted">True Positive</div>
                      <div className={cn('text-sm font-mono', consensus.is_true_positive ? 'text-aegis-critical' : 'text-aegis-low')}>
                        {consensus.is_true_positive ? 'Likely YES' : 'Likely NO'}
                      </div>
                    </div>
                  </div>
                  {consensus.reasoning && (
                    <p className="text-xs text-aegis-muted mt-3 p-2 bg-aegis-bg rounded border border-aegis-border">{consensus.reasoning}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'mitre' && (
            <div className="space-y-3">
              {mitreData.length === 0 ? (
                <div className="aegis-card p-8 text-center text-aegis-muted">
                  No MITRE techniques mapped yet. Analysis may still be running.
                </div>
              ) : (
                mitreData.map((t: any, i: number) => (
                  <div key={i} className="aegis-card p-4 flex items-start gap-4">
                    <div className="shrink-0">
                      <span className="font-mono text-sm text-aegis-accent font-bold">{t.technique_id}</span>
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-aegis-text text-sm">{t.technique_name}</div>
                      <div className="text-xs text-aegis-muted mt-0.5">{t.tactic} · {t.tactic_id}</div>
                      {t.evidence && <div className="text-xs text-aegis-text-dim mt-2 italic">{t.evidence}</div>}
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-xs text-aegis-muted">Confidence</div>
                      <div className={cn('text-sm font-mono font-bold',
                        t.confidence > 0.7 ? 'text-aegis-critical' : t.confidence > 0.4 ? 'text-aegis-medium' : 'text-aegis-muted'
                      )}>
                        {((t.confidence ?? 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'remediation' && (
            <div className="space-y-3">
              {!incident.remediation_plan ? (
                <div className="aegis-card p-8 text-center text-aegis-muted">
                  No remediation plan generated yet. Analysis may still be in progress.
                </div>
              ) : (
                <>
                  <div className="aegis-card p-4">
                    <h3 className="text-sm font-semibold text-aegis-text mb-2">Plan Objective</h3>
                    <p className="text-sm text-aegis-text-dim">
                      {(incident.remediation_plan as any)?.remediation_plan?.objective ?? 'N/A'}
                    </p>
                  </div>
                  {((incident.remediation_plan as any)?.remediation_plan?.actions ?? []).map((action: any, i: number) => (
                    <div key={i} className="aegis-card p-4">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-xs font-mono text-aegis-muted">{action.action_id}</span>
                        <span className="text-xs px-1.5 py-0.5 bg-aegis-border rounded font-mono text-aegis-accent">{action.action_type}</span>
                        <span className="text-xs text-aegis-muted">via `{action.mcp_tool}`</span>
                        {action.reversible && <span className="text-xs text-aegis-low">reversible</span>}
                      </div>
                      <div className="font-medium text-sm text-aegis-text">{action.title}</div>
                      <div className="text-xs text-aegis-text-dim mt-1">{action.description}</div>
                    </div>
                  ))}
                  <Link
                    href="/approvals"
                    className="flex items-center justify-center gap-2 w-full py-3 bg-aegis-accent/10 border border-aegis-accent/30 rounded-lg text-aegis-accent text-sm font-medium hover:bg-aegis-accent/20 transition-colors"
                  >
                    Go to Approval Center <ExternalLink className="w-4 h-4" />
                  </Link>
                </>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
