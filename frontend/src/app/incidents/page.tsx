'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Plus, Search, Filter, RefreshCw } from 'lucide-react';
import { incidents, ingest } from '@/lib/api';
import type { Incident } from '@/lib/api';
import { Sidebar } from '@/components/shared/Sidebar';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { IncidentRow } from '@/components/incidents/IncidentRow';
import { cn } from '@/lib/utils';

const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low'];
const STATUSES = ['all', 'open', 'investigating', 'awaiting_approval', 'remediating', 'closed'];

export default function IncidentsPage() {
  const [allIncidents, setAllIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: '', severity: 'medium', description: '', source_type: 'manual',
    iocs: '', tags: ''
  });

  const fetchIncidents = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (severityFilter !== 'all') params.severity = severityFilter;
      if (statusFilter !== 'all') params.status = statusFilter;
      const data = await incidents.list(params);
      setAllIncidents(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [severityFilter, statusFilter]);

  useEffect(() => { fetchIncidents(); }, [fetchIncidents]);

  const filtered = allIncidents.filter(inc =>
    search === '' ||
    inc.title.toLowerCase().includes(search.toLowerCase()) ||
    inc.id.includes(search)
  );

  const handleCreate = async () => {
    setCreating(true);
    try {
      const iocList = form.iocs.split(',').filter(Boolean).map(v => {
        const val = v.trim();
        const type = /^\d+\.\d+\.\d+\.\d+$/.test(val) ? 'ip' :
                     /@/.test(val) ? 'email' : 'domain';
        return { type, value: val };
      });
      await incidents.create({
        title: form.title,
        description: form.description || undefined,
        severity: form.severity,
        source_type: form.source_type,
        ioc_list: iocList.length > 0 ? iocList : undefined,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      });
      setShowCreate(false);
      setForm({ title: '', severity: 'medium', description: '', source_type: 'manual', iocs: '', tags: '' });
      fetchIncidents();
    } catch (e) { console.error(e); }
    finally { setCreating(false); }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-aegis-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-aegis-bg/90 backdrop-blur-sm border-b border-aegis-border px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-aegis-text">Incidents</h1>
              <p className="text-xs text-aegis-muted mt-0.5">{allIncidents.length} total · {allIncidents.filter(i => i.status === 'open' || i.status === 'investigating').length} active</p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={fetchIncidents} className="p-2 text-aegis-muted hover:text-aegis-accent transition-colors rounded border border-aegis-border">
                <RefreshCw className="w-4 h-4" />
              </button>
              <button
                onClick={() => setShowCreate(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-aegis-accent/10 border border-aegis-accent/30 rounded text-aegis-accent text-sm hover:bg-aegis-accent/20 transition-colors"
              >
                <Plus className="w-4 h-4" /> New Incident
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-3 mt-3">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-aegis-muted" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search incidents…"
                className="w-full pl-8 pr-3 py-1.5 bg-aegis-surface border border-aegis-border rounded text-sm text-aegis-text placeholder-aegis-muted focus:outline-none focus:border-aegis-accent/50"
              />
            </div>
            <div className="flex gap-1">
              {SEVERITIES.map(s => (
                <button key={s} onClick={() => setSeverityFilter(s)}
                  className={cn('px-2.5 py-1 rounded text-xs capitalize transition-colors',
                    severityFilter === s ? 'bg-aegis-accent/20 text-aegis-accent border border-aegis-accent/30' :
                    'text-aegis-muted hover:text-aegis-text border border-transparent'
                  )}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Incident Table */}
        <div className="p-6">
          <div className="aegis-card overflow-hidden">
            <div className="grid grid-cols-[1fr,120px,120px,100px,100px] gap-0 px-4 py-2 border-b border-aegis-border text-[10px] text-aegis-muted uppercase font-medium tracking-wider">
              <div>Title</div><div>Severity</div><div>Status</div><div>Risk</div><div>Created</div>
            </div>
            {loading ? (
              <div className="p-8 text-center text-aegis-muted animate-pulse">Loading incidents…</div>
            ) : filtered.length === 0 ? (
              <div className="p-12 text-center">
                <div className="text-2xl mb-2">🛡️</div>
                <p className="text-aegis-muted text-sm">No incidents found.</p>
              </div>
            ) : (
              <div className="divide-y divide-aegis-border">
                {filtered.map(inc => (
                  <Link key={inc.id} href={`/incidents/${inc.id}`}
                    className="grid grid-cols-[1fr,120px,120px,100px,100px] gap-0 px-4 py-3 hover:bg-aegis-border/20 transition-colors items-center group"
                  >
                    <div className="text-sm text-aegis-text group-hover:text-aegis-accent transition-colors truncate pr-4">{inc.title}</div>
                    <div><SeverityBadge severity={inc.severity} /></div>
                    <div className="text-xs text-aegis-muted font-mono">{inc.status.replace(/_/g,' ')}</div>
                    <div className={cn('text-sm font-mono', inc.risk_score > 0.7 ? 'text-aegis-critical' : inc.risk_score > 0.4 ? 'text-aegis-medium' : 'text-aegis-muted')}>
                      {inc.risk_score > 0 ? `${(inc.risk_score*100).toFixed(0)}%` : '—'}
                    </div>
                    <div className="text-xs text-aegis-muted">{new Date(inc.created_at).toLocaleDateString()}</div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Create Modal */}
        {showCreate && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-aegis-surface border border-aegis-border rounded-xl p-6 w-full max-w-lg shadow-aegis-lg">
              <h2 className="text-lg font-semibold text-aegis-text mb-4">Create New Incident</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-aegis-muted block mb-1">Title *</label>
                  <input value={form.title} onChange={e => setForm({...form, title: e.target.value})}
                    placeholder="Suspicious activity detected…"
                    className="w-full px-3 py-2 bg-aegis-bg border border-aegis-border rounded text-sm text-aegis-text placeholder-aegis-muted focus:outline-none focus:border-aegis-accent/50"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-aegis-muted block mb-1">Severity</label>
                    <select value={form.severity} onChange={e => setForm({...form, severity: e.target.value})}
                      className="w-full px-3 py-2 bg-aegis-bg border border-aegis-border rounded text-sm text-aegis-text focus:outline-none focus:border-aegis-accent/50">
                      {['critical','high','medium','low','info'].map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-aegis-muted block mb-1">Source Type</label>
                    <select value={form.source_type} onChange={e => setForm({...form, source_type: e.target.value})}
                      className="w-full px-3 py-2 bg-aegis-bg border border-aegis-border rounded text-sm text-aegis-text focus:outline-none focus:border-aegis-accent/50">
                      {['manual','email','log','image','api'].map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-aegis-muted block mb-1">Description</label>
                  <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                    rows={2} placeholder="Describe the threat…"
                    className="w-full px-3 py-2 bg-aegis-bg border border-aegis-border rounded text-sm text-aegis-text placeholder-aegis-muted focus:outline-none focus:border-aegis-accent/50 resize-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-aegis-muted block mb-1">IOCs (comma-separated IPs/domains/emails)</label>
                  <input value={form.iocs} onChange={e => setForm({...form, iocs: e.target.value})}
                    placeholder="1.2.3.4, evil.com, user@phish.net"
                    className="w-full px-3 py-2 bg-aegis-bg border border-aegis-border rounded text-sm text-aegis-text placeholder-aegis-muted focus:outline-none focus:border-aegis-accent/50"
                  />
                </div>
              </div>
              <div className="flex gap-3 mt-5">
                <button onClick={() => setShowCreate(false)}
                  className="flex-1 py-2 border border-aegis-border rounded text-sm text-aegis-muted hover:text-aegis-text transition-colors">
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!form.title || creating}
                  className="flex-1 py-2 bg-aegis-accent/20 border border-aegis-accent/40 rounded text-sm text-aegis-accent hover:bg-aegis-accent/30 disabled:opacity-50 transition-colors font-medium"
                >
                  {creating ? 'Creating…' : 'Create & Investigate'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
