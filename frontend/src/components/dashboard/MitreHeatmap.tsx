'use client';

interface MitreHeatmapProps {
  techniques: { technique_id: string; count: number }[];
  loading?: boolean;
}

const TACTIC_MAP: Record<string, { tactic: string; color: string }> = {
  'T1566': { tactic: 'Initial Access', color: '#ff3b3b' },
  'T1071': { tactic: 'C2', color: '#ff8c00' },
  'T1059': { tactic: 'Execution', color: '#f5c518' },
  'T1053': { tactic: 'Persistence', color: '#00c851' },
  'T1078': { tactic: 'Priv Esc', color: '#4a9eff' },
  'T1055': { tactic: 'Def Evasion', color: '#9b59b6' },
  'T1003': { tactic: 'Cred Access', color: '#e74c3c' },
  'T1082': { tactic: 'Discovery', color: '#1abc9c' },
  'T1021': { tactic: 'Lateral Mov', color: '#f39c12' },
  'T1041': { tactic: 'Exfiltration', color: '#e74c3c' },
};

export function MitreHeatmap({ techniques, loading }: MitreHeatmapProps) {
  if (loading) {
    return (
      <div className="aegis-card p-4 h-32 flex items-center justify-center">
        <div className="text-aegis-muted text-sm">Loading MITRE data…</div>
      </div>
    );
  }

  if (techniques.length === 0) {
    return (
      <div className="aegis-card p-6 text-center">
        <div className="text-aegis-muted text-sm">No MITRE techniques mapped yet.</div>
        <div className="text-aegis-muted/50 text-xs mt-1">Techniques appear after incident analysis.</div>
      </div>
    );
  }

  const maxCount = Math.max(...techniques.map(t => t.count), 1);

  return (
    <div className="aegis-card p-4">
      <div className="grid grid-cols-5 gap-2">
        {techniques.map((t) => {
          const info = TACTIC_MAP[t.technique_id];
          const intensity = t.count / maxCount;
          return (
            <div
              key={t.technique_id}
              className="relative group cursor-pointer"
              title={`${t.technique_id}: ${t.count} incident${t.count !== 1 ? 's' : ''}`}
            >
              <div
                className="rounded p-2 text-center border border-aegis-border/50 transition-all group-hover:border-aegis-accent/50"
                style={{
                  backgroundColor: `${info?.color ?? '#4a9eff'}${Math.round(intensity * 40 + 10).toString(16).padStart(2, '0')}`,
                }}
              >
                <div className="text-[10px] font-mono text-white/80 truncate">{t.technique_id}</div>
                <div className="text-xs font-bold text-white mt-0.5">{t.count}</div>
                {info && (
                  <div className="text-[9px] text-white/60 truncate">{info.tactic}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-aegis-border">
        <span className="text-[10px] text-aegis-muted">Frequency:</span>
        <div className="flex gap-1 items-center">
          {[0.15, 0.35, 0.6, 0.85, 1.0].map((v, i) => (
            <div key={i} className="w-4 h-3 rounded-sm" style={{ backgroundColor: `rgba(255,59,59,${v})` }} />
          ))}
          <span className="text-[10px] text-aegis-muted ml-1">High</span>
        </div>
      </div>
    </div>
  );
}
