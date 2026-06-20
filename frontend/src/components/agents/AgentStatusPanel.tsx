'use client';
import { AGENT_CONFIG, cn } from '@/lib/utils';
import type { AgentInfo } from '@/lib/api';

export function AgentStatusPanel({ agents, loading }: { agents: AgentInfo[]; loading?: boolean }) {
  if (loading) {
    return (
      <div className="aegis-card p-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-3 py-2">
            <div className="w-2 h-2 rounded-full bg-aegis-border animate-pulse" />
            <div className="h-3 bg-aegis-border rounded w-28 animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="aegis-card divide-y divide-aegis-border max-h-80 overflow-y-auto">
      {agents.length === 0 ? (
        <div className="p-4 text-aegis-muted text-sm text-center">No agents registered</div>
      ) : (
        agents.map((agent) => {
          const cfg = AGENT_CONFIG[agent.name];
          const statusColors = {
            idle: 'bg-aegis-muted',
            running: 'bg-aegis-accent animate-pulse',
            error: 'bg-aegis-critical animate-pulse',
          };
          return (
            <div key={agent.name} className="flex items-center gap-3 px-3 py-2 hover:bg-aegis-border/20 transition-colors">
              <span className="text-sm">{cfg?.icon ?? '🤖'}</span>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-aegis-text truncate">{cfg?.role ?? agent.name}</div>
                <div className="text-[10px] text-aegis-muted">{agent.message_count} msgs</div>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={cn('w-1.5 h-1.5 rounded-full', statusColors[agent.status as keyof typeof statusColors] ?? 'bg-aegis-muted')} />
                <span className={cn('text-[10px] font-mono uppercase', 
                  agent.status === 'running' ? 'text-aegis-accent' :
                  agent.status === 'error' ? 'text-aegis-critical' : 'text-aegis-muted'
                )}>
                  {agent.status}
                </span>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
