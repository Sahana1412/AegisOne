'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  Shield, AlertTriangle, Activity, Clock, CheckCircle, XCircle,
  Eye, Zap, TrendingUp, Server, Globe, ChevronRight, RefreshCw
} from 'lucide-react';
import { dashboard, incidents, agentsApi, approvals } from '@/lib/api';
import type { DashboardStats, Incident, AgentInfo, ApprovalRequest } from '@/lib/api';
import { SEVERITY_CONFIG, formatTimeAgo, cn } from '@/lib/utils';
import { Sidebar } from '@/components/shared/Sidebar';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { MitreHeatmap } from '@/components/dashboard/MitreHeatmap';
import { AgentStatusPanel } from '@/components/agents/AgentStatusPanel';
import { IncidentRow } from '@/components/incidents/IncidentRow';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentIncidents, setRecentIncidents] = useState<Incident[]>([]);
  const [agentList, setAgentList] = useState<AgentInfo[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchData = useCallback(async () => {
    try {
      const [s, inc, ags, apprs] = await Promise.all([
        dashboard.stats(),
        incidents.list(),
        agentsApi.list(),
        approvals.list('pending'),
      ]);
      setStats(s);
      setRecentIncidents(inc.slice(0, 8));
      setAgentList(ags);
      setPendingApprovals(apprs.slice(0, 5));
      setLastRefresh(new Date());
    } catch (e) {
      console.error('Dashboard fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="flex h-screen overflow-hidden bg-aegis-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-aegis-bg/90 backdrop-blur-sm border-b border-aegis-border px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-aegis-text">Security Operations Center</h1>
              <p className="text-xs text-aegis-muted font-mono mt-0.5">
                Last updated: {formatTimeAgo(lastRefresh.toISOString())}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {pendingApprovals.length > 0 && (
                <Link href="/approvals" className="flex items-center gap-2 px-3 py-1.5 bg-orange-950/60 border border-orange-700/50 rounded-md text-aegis-high text-sm font-medium animate-pulse-slow">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {pendingApprovals.length} Pending Approval{pendingApprovals.length > 1 ? 's' : ''}
                </Link>
              )}
              <button
                onClick={fetchData}
                className="p-2 rounded-md border border-aegis-border hover:border-aegis-accent/50 text-aegis-muted hover:text-aegis-accent transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Threat Status Banner */}
          {stats && stats.critical_count > 0 && (
            <div className="flex items-center gap-3 px-4 py-3 bg-red-950/30 border border-red-800/50 rounded-lg animate-fade-in">
              <div className="w-2 h-2 rounded-full bg-aegis-critical animate-pulse" />
              <span className="text-aegis-critical font-semibold text-sm">CRITICAL THREAT ACTIVE</span>
              <span className="text-red-400/70 text-sm">—</span>
              <span className="text-red-400/70 text-sm">{stats.critical_count} critical incident{stats.critical_count > 1 ? 's' : ''} requiring immediate attention</span>
              <Link href="/incidents?severity=critical" className="ml-auto text-aegis-critical text-xs underline">
                View Now →
              </Link>
            </div>
          )}

          {/* Metric Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Total Incidents"
              value={stats?.total_incidents ?? 0}
              icon={<Shield className="w-5 h-5" />}
              color="text-aegis-accent"
              subtext={`${stats?.open_incidents ?? 0} open`}
              loading={loading}
            />
            <MetricCard
              label="Critical / High"
              value={`${stats?.critical_count ?? 0} / ${stats?.high_count ?? 0}`}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="text-aegis-critical"
              subtext="active threats"
              loading={loading}
              urgent={Boolean(stats && stats.critical_count > 0)}
            />
            <MetricCard
              label="Avg Risk Score"
              value={stats ? `${(stats.avg_risk_score * 100).toFixed(0)}%` : '—'}
              icon={<TrendingUp className="w-5 h-5" />}
              color={stats && stats.avg_risk_score > 0.7 ? 'text-aegis-critical' : 'text-aegis-medium'}
              subtext="FAIR methodology"
              loading={loading}
            />
            <MetricCard
              label="Pending Approvals"
              value={stats?.pending_approvals ?? 0}
              icon={<CheckCircle className="w-5 h-5" />}
              color="text-aegis-high"
              subtext="human review needed"
              loading={loading}
              urgent={Boolean(stats && stats.pending_approvals > 0)}
            />
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Incident Feed - 2/3 width */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-aegis-text uppercase tracking-wider flex items-center gap-2">
                  <Activity className="w-4 h-4 text-aegis-accent" />
                  Live Incident Feed
                </h2>
                <Link href="/incidents" className="text-xs text-aegis-accent hover:underline flex items-center gap-1">
                  View all <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
              <div className="aegis-card overflow-hidden">
                {loading ? (
                  <div className="p-8 text-center text-aegis-muted text-sm">Loading incidents…</div>
                ) : recentIncidents.length === 0 ? (
                  <div className="p-8 text-center">
                    <Shield className="w-10 h-10 text-aegis-muted mx-auto mb-3 opacity-50" />
                    <p className="text-aegis-muted text-sm">No incidents detected. All systems nominal.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-aegis-border">
                    {recentIncidents.map((inc) => (
                      <IncidentRow key={inc.id} incident={inc} />
                    ))}
                  </div>
                )}
              </div>

              {/* MITRE Heatmap */}
              <div>
                <h2 className="text-sm font-semibold text-aegis-text uppercase tracking-wider flex items-center gap-2 mb-3">
                  <Globe className="w-4 h-4 text-aegis-accent" />
                  MITRE ATT&CK Coverage
                </h2>
                <MitreHeatmap techniques={stats?.top_mitre_techniques ?? []} loading={loading} />
              </div>
            </div>

            {/* Right Panel */}
            <div className="space-y-4">
              {/* Agent Status */}
              <div>
                <h2 className="text-sm font-semibold text-aegis-text uppercase tracking-wider flex items-center gap-2 mb-3">
                  <Zap className="w-4 h-4 text-aegis-accent" />
                  Band Agent Fleet
                </h2>
                <AgentStatusPanel agents={agentList} loading={loading} />
              </div>

              {/* Recent IOCs */}
              <div>
                <h2 className="text-sm font-semibold text-aegis-text uppercase tracking-wider flex items-center gap-2 mb-3">
                  <Eye className="w-4 h-4 text-aegis-accent" />
                  Recent IOCs
                </h2>
                <div className="aegis-card divide-y divide-aegis-border">
                  {loading ? (
                    <div className="p-4 text-aegis-muted text-sm text-center">Loading…</div>
                  ) : (stats?.recent_iocs ?? []).length === 0 ? (
                    <div className="p-4 text-aegis-muted text-sm text-center">No IOCs recorded</div>
                  ) : (
                    (stats?.recent_iocs ?? []).slice(0, 6).map((ioc, i) => (
                      <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                        <span className="text-xs px-1.5 py-0.5 bg-aegis-border rounded text-aegis-muted uppercase font-mono">
                          {ioc.ioc_type}
                        </span>
                        <span className="text-xs font-mono text-aegis-text truncate flex-1">
                          {ioc.ioc_value}
                        </span>
                        <span className={cn(
                          'text-xs font-mono',
                          ioc.threat_score > 0.7 ? 'text-aegis-critical' :
                          ioc.threat_score > 0.4 ? 'text-aegis-high' : 'text-aegis-muted'
                        )}>
                          {(ioc.threat_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Pending Approvals */}
              {pendingApprovals.length > 0 && (
                <div>
                  <h2 className="text-sm font-semibold text-aegis-text uppercase tracking-wider flex items-center gap-2 mb-3">
                    <CheckCircle className="w-4 h-4 text-aegis-high" />
                    Awaiting Approval
                  </h2>
                  <div className="space-y-2">
                    {pendingApprovals.map((ap) => (
                      <Link
                        key={ap.id}
                        href={`/approvals?id=${ap.id}`}
                        className="block aegis-card p-3 hover:border-aegis-accent/40 transition-colors group"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-aegis-high font-semibold">PENDING APPROVAL</span>
                          <ChevronRight className="w-3 h-3 text-aegis-muted group-hover:text-aegis-accent" />
                        </div>
                        <p className="text-xs text-aegis-text-dim truncate">{ap.risk_summary}</p>
                        <p className="text-xs text-aegis-muted mt-1">{ap.proposed_actions?.length ?? 0} actions proposed</p>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
