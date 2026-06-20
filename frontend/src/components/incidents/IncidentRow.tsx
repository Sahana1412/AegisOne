'use client';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { formatTimeAgo, cn } from '@/lib/utils';
import type { Incident } from '@/lib/api';

const STATUS_STYLES: Record<string, string> = {
  open: 'text-aegis-high bg-orange-950/30',
  investigating: 'text-aegis-accent bg-cyan-950/30',
  awaiting_approval: 'text-aegis-medium bg-yellow-950/30',
  remediating: 'text-purple-400 bg-purple-950/30',
  verifying: 'text-blue-400 bg-blue-950/30',
  closed: 'text-aegis-low bg-green-950/30',
  false_positive: 'text-aegis-muted bg-aegis-border/30',
};

export function IncidentRow({ incident }: { incident: Incident }) {
  return (
    <Link
      href={`/incidents/${incident.id}`}
      className="flex items-center gap-4 px-4 py-3 hover:bg-aegis-border/20 transition-colors group"
    >
      <SeverityBadge severity={incident.severity} />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-aegis-text truncate group-hover:text-aegis-accent transition-colors">
          {incident.title}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-mono uppercase', STATUS_STYLES[incident.status] ?? STATUS_STYLES.open)}>
            {incident.status.replace(/_/g, ' ')}
          </span>
          {incident.source_type && (
            <span className="text-[10px] text-aegis-muted font-mono">{incident.source_type}</span>
          )}
          {incident.risk_score > 0 && (
            <span className={cn(
              'text-[10px] font-mono',
              incident.risk_score > 0.7 ? 'text-aegis-critical' :
              incident.risk_score > 0.4 ? 'text-aegis-high' : 'text-aegis-muted'
            )}>
              risk: {(incident.risk_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>
      <div className="text-[10px] text-aegis-muted shrink-0">
        {formatTimeAgo(incident.created_at)}
      </div>
      <ChevronRight className="w-4 h-4 text-aegis-muted/50 group-hover:text-aegis-accent transition-colors shrink-0" />
    </Link>
  );
}
