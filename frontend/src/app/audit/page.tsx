'use client';

import { useEffect, useState, useCallback } from 'react';
import { FileText, User, Bot, Cog } from 'lucide-react';
import { audit } from '@/lib/api';
import type { AuditEntry } from '@/lib/api';
import { Sidebar } from '@/components/shared/Sidebar';
import { formatDateTime, cn } from '@/lib/utils';

const ACTOR_ICONS: Record<string, any> = { agent: Bot, human: User, system: Cog };

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const data = await audit.list();
      setEntries(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="flex h-screen overflow-hidden bg-aegis-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="sticky top-0 z-10 bg-aegis-bg/90 backdrop-blur-sm border-b border-aegis-border px-6 py-4">
          <h1 className="text-xl font-semibold text-aegis-text flex items-center gap-2">
            <FileText className="w-5 h-5 text-aegis-accent" /> Audit Trail
          </h1>
          <p className="text-xs text-aegis-muted mt-0.5">
            Immutable record of every action taken by agents, humans, and the system
          </p>
        </div>

        <div className="p-6">
          <div className="aegis-card overflow-hidden">
            {loading ? (
              <div className="p-8 text-center text-aegis-muted animate-pulse">Loading audit log…</div>
            ) : entries.length === 0 ? (
              <div className="p-8 text-center text-aegis-muted">No audit entries yet.</div>
            ) : (
              <div className="divide-y divide-aegis-border">
                {entries.map(entry => {
                  const Icon = ACTOR_ICONS[entry.actor_type] ?? Cog;
                  return (
                    <div key={entry.id} className="flex items-start gap-3 px-4 py-3 hover:bg-aegis-border/10 transition-colors">
                      <div className={cn(
                        'shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5',
                        entry.actor_type === 'human' ? 'bg-purple-950/40 text-purple-400' :
                        entry.actor_type === 'agent' ? 'bg-cyan-950/40 text-cyan-400' :
                        'bg-aegis-border/40 text-aegis-muted'
                      )}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-aegis-text font-medium">{entry.actor}</span>
                          <span className={cn('text-[10px] px-1.5 py-0.5 rounded uppercase font-mono',
                            entry.outcome === 'success' ? 'text-aegis-low bg-green-950/30' : 'text-aegis-critical bg-red-950/30'
                          )}>
                            {entry.outcome}
                          </span>
                        </div>
                        <p className="text-xs text-aegis-text-dim mt-0.5">{entry.action}</p>
                        <p className="text-[10px] text-aegis-muted mt-1 font-mono">
                          incident: {entry.incident_id.slice(0, 8)}… · {formatDateTime(entry.timestamp)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
