'use client';

import { useEffect, useState, useCallback } from 'react';
import { Zap, ArrowRight } from 'lucide-react';
import { agentsApi } from '@/lib/api';
import type { AgentInfo } from '@/lib/api';
import { Sidebar } from '@/components/shared/Sidebar';
import { AGENT_CONFIG, formatTimeAgo, cn } from '@/lib/utils';

const PIPELINE_ORDER = [
  'intake_agent', 'threat_intel_agent', 'mitre_mapping_agent', 'risk_assessment_agent',
  'consensus_agent', 'red_team_agent', 'remediation_agent', 'execution_agent',
  'verification_agent', 'report_agent', 'audit_trail_agent',
];

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const data = await agentsApi.list();
      setAgents(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const ordered = PIPELINE_ORDER
    .map(name => agents.find(a => a.name === name))
    .filter((a): a is AgentInfo => Boolean(a));

  return (
    <div className="flex h-screen overflow-hidden bg-aegis-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="sticky top-0 z-10 bg-aegis-bg/90 backdrop-blur-sm border-b border-aegis-border px-6 py-4">
          <h1 className="text-xl font-semibold text-aegis-text flex items-center gap-2">
            <Zap className="w-5 h-5 text-aegis-accent" /> Band Agent Fleet
          </h1>
          <p className="text-xs text-aegis-muted mt-0.5">
            {agents.length} agents registered · All communication flows through the Band event bus
          </p>
        </div>

        <div className="p-6">
          {/* Pipeline Flow Visualization */}
          <div className="aegis-card p-5 mb-6 overflow-x-auto">
            <h2 className="text-sm font-semibold text-aegis-text mb-4">Investigation Pipeline Flow</h2>
            <div className="flex items-center gap-1 min-w-max pb-2">
              {ordered.map((agent, i) => {
                const cfg = AGENT_CONFIG[agent.name];
                return (
                  <div key={agent.name} className="flex items-center">
                    <div className={cn(
                      'flex flex-col items-center gap-1 px-3 py-2 rounded-lg border min-w-[90px]',
                      agent.status === 'running' ? 'border-aegis-accent bg-aegis-accent/10 animate-glow' :
                      agent.status === 'error' ? 'border-aegis-critical bg-red-950/20' :
                      'border-aegis-border bg-aegis-bg/40'
                    )}>
                      <span className="text-lg">{cfg?.icon ?? '🤖'}</span>
                      <span className="text-[10px] text-aegis-text-dim text-center leading-tight">{cfg?.role ?? agent.name}</span>
                    </div>
                    {i < ordered.length - 1 && (
                      <ArrowRight className="w-4 h-4 text-aegis-muted/40 mx-1 shrink-0" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Agent Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {loading ? (
              [...Array(6)].map((_, i) => (
                <div key={i} className="aegis-card p-4 h-40 animate-pulse" />
              ))
            ) : (
              agents.map(agent => {
                const cfg = AGENT_CONFIG[agent.name];
                return (
                  <div key={agent.name} className="aegis-card p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{cfg?.icon ?? '🤖'}</span>
                        <div>
                          <div className="text-sm font-medium text-aegis-text">{cfg?.role ?? agent.name}</div>
                          <div className="text-[10px] text-aegis-muted font-mono">{agent.name}</div>
                        </div>
                      </div>
                      <div className={cn('status-dot', agent.status)} />
                    </div>
                    <p className="text-xs text-aegis-text-dim mb-3 leading-relaxed">{agent.description}</p>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-aegis-muted">{agent.message_count} messages</span>
                      {agent.error_count > 0 && (
                        <span className="text-aegis-critical">{agent.error_count} errors</span>
                      )}
                    </div>
                    {agent.last_active && (
                      <div className="text-[10px] text-aegis-muted mt-1">
                        Last active: {formatTimeAgo(agent.last_active)}
                      </div>
                    )}
                    <div className="flex flex-wrap gap-1 mt-3">
                      {agent.capabilities.slice(0, 3).map(cap => (
                        <span key={cap} className="text-[9px] px-1.5 py-0.5 bg-aegis-border/50 rounded text-aegis-muted font-mono">
                          {cap}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
