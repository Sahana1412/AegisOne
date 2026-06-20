'use client';

import { useEffect, useState, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { CheckCircle, XCircle, Edit3, AlertTriangle, Shield } from 'lucide-react';
import { approvals } from '@/lib/api';
import type { ApprovalRequest } from '@/lib/api';
import { Sidebar } from '@/components/shared/Sidebar';
import { formatTimeAgo, cn } from '@/lib/utils';

export default function ApprovalsPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen overflow-hidden bg-aegis-bg">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-aegis-muted animate-pulse">Loading approval center…</div>
        </main>
      </div>
    }>
      <ApprovalsPageContent />
    </Suspense>
  );
}

function ApprovalsPageContent() {
  const searchParams = useSearchParams();
  const focusId = searchParams.get('id');

  const [list, setList] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ApprovalRequest | null>(null);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [filter, setFilter] = useState<'pending' | 'approved' | 'rejected' | 'all'>('pending');

  const fetchData = useCallback(async () => {
    try {
      const data = await approvals.list(filter === 'all' ? undefined : filter);
      setList(data);
      if (focusId) {
        const match = data.find(a => a.id === focusId);
        if (match) setSelected(match);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [filter, focusId]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => {
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleDecision = async (decision: 'approved' | 'rejected') => {
    if (!selected) return;
    setSubmitting(true);
    try {
      await approvals.decide(selected.id, {
        decision,
        reviewer_notes: notes || undefined,
        reviewed_by: 'security_analyst',
      });
      setSelected(null);
      setNotes('');
      fetchData();
    } catch (e) { console.error(e); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-aegis-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="sticky top-0 z-10 bg-aegis-bg/90 backdrop-blur-sm border-b border-aegis-border px-6 py-4">
          <h1 className="text-xl font-semibold text-aegis-text">Approval Center</h1>
          <p className="text-xs text-aegis-muted mt-0.5">
            Human-in-the-loop review · No remediation executes without explicit approval
          </p>
          <div className="flex gap-1 mt-3">
            {(['pending', 'approved', 'rejected', 'all'] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={cn('px-2.5 py-1 rounded text-xs capitalize transition-colors',
                  filter === f ? 'bg-aegis-accent/20 text-aegis-accent border border-aegis-accent/30' :
                  'text-aegis-muted hover:text-aegis-text border border-transparent'
                )}>
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* List */}
          <div className="space-y-3">
            {loading ? (
              <div className="text-aegis-muted text-sm animate-pulse">Loading approval requests…</div>
            ) : list.length === 0 ? (
              <div className="aegis-card p-8 text-center">
                <Shield className="w-8 h-8 text-aegis-low mx-auto mb-2" />
                <p className="text-aegis-muted text-sm">No {filter !== 'all' ? filter : ''} approval requests.</p>
              </div>
            ) : (
              list.map(ap => (
                <button
                  key={ap.id}
                  onClick={() => setSelected(ap)}
                  className={cn(
                    'w-full text-left aegis-card p-4 transition-all hover:border-aegis-accent/40',
                    selected?.id === ap.id && 'border-aegis-accent shadow-aegis'
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className={cn('text-xs font-semibold uppercase px-2 py-0.5 rounded',
                      ap.status === 'pending' ? 'text-aegis-high bg-orange-950/40' :
                      ap.status === 'approved' ? 'text-aegis-low bg-green-950/40' :
                      'text-aegis-critical bg-red-950/40'
                    )}>
                      {ap.status}
                    </span>
                    <span className="text-[10px] text-aegis-muted">{formatTimeAgo(ap.created_at)}</span>
                  </div>
                  <p className="text-sm text-aegis-text-dim line-clamp-2">{ap.risk_summary}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-aegis-muted">
                    <span>{ap.proposed_actions?.length ?? 0} actions</span>
                    {ap.confidence_score !== null && <span>· {(ap.confidence_score * 100).toFixed(0)}% confidence</span>}
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Detail Panel */}
          <div>
            {!selected ? (
              <div className="aegis-card p-12 text-center h-full flex flex-col items-center justify-center">
                <AlertTriangle className="w-8 h-8 text-aegis-muted mb-3 opacity-50" />
                <p className="text-aegis-muted text-sm">Select an approval request to review</p>
              </div>
            ) : (
              <div className="aegis-card p-5 sticky top-24">
                <h3 className="text-sm font-semibold text-aegis-text mb-1">Risk Summary</h3>
                <p className="text-sm text-aegis-text-dim mb-4">{selected.risk_summary}</p>

                <h3 className="text-sm font-semibold text-aegis-text mb-2">Proposed Actions</h3>
                <div className="space-y-2 mb-4 max-h-64 overflow-y-auto">
                  {selected.proposed_actions.map((action, i) => (
                    <div key={i} className="p-3 bg-aegis-bg rounded border border-aegis-border">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono text-aegis-muted">{action.action_id}</span>
                        <span className="text-xs px-1.5 py-0.5 bg-aegis-border rounded font-mono text-aegis-accent">{action.action_type}</span>
                        {action.reversible && <span className="text-[10px] text-aegis-low">reversible</span>}
                      </div>
                      <div className="text-sm font-medium text-aegis-text">{action.title}</div>
                      <div className="text-xs text-aegis-text-dim mt-1">{action.description}</div>
                      <div className="text-[10px] text-aegis-muted mt-1.5">via MCP tool: <code className="text-aegis-accent">{action.mcp_tool}</code></div>
                    </div>
                  ))}
                </div>

                {selected.status === 'pending' ? (
                  <>
                    <textarea
                      value={notes}
                      onChange={e => setNotes(e.target.value)}
                      placeholder="Reviewer notes (optional)…"
                      rows={2}
                      className="w-full px-3 py-2 bg-aegis-bg border border-aegis-border rounded text-sm text-aegis-text placeholder-aegis-muted focus:outline-none focus:border-aegis-accent/50 resize-none mb-3"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleDecision('approved')}
                        disabled={submitting}
                        className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-green-950/40 border border-green-700/50 rounded text-aegis-low text-sm font-medium hover:bg-green-950/60 transition-colors disabled:opacity-50"
                      >
                        <CheckCircle className="w-4 h-4" /> Approve
                      </button>
                      <button
                        onClick={() => handleDecision('rejected')}
                        disabled={submitting}
                        className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-red-950/40 border border-red-700/50 rounded text-aegis-critical text-sm font-medium hover:bg-red-950/60 transition-colors disabled:opacity-50"
                      >
                        <XCircle className="w-4 h-4" /> Reject
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="p-3 bg-aegis-bg rounded border border-aegis-border text-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn('font-medium uppercase text-xs',
                        selected.status === 'approved' ? 'text-aegis-low' : 'text-aegis-critical'
                      )}>{selected.status}</span>
                      <span className="text-aegis-muted text-xs">by {selected.reviewed_by}</span>
                    </div>
                    {selected.reviewer_notes && <p className="text-aegis-text-dim text-xs">{selected.reviewer_notes}</p>}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
