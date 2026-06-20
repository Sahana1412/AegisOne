'use client';
import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: ReactNode;
  color: string;
  subtext?: string;
  loading?: boolean;
  urgent?: boolean;
}

export function MetricCard({ label, value, icon, color, subtext, loading, urgent }: MetricCardProps) {
  return (
    <div className={cn(
      'aegis-card p-4 transition-all',
      urgent && 'border-orange-700/60 shadow-[0_0_12px_rgba(255,140,0,0.1)]'
    )}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-aegis-muted uppercase tracking-wider font-medium">{label}</span>
        <span className={cn('opacity-70', color)}>{icon}</span>
      </div>
      {loading ? (
        <div className="h-8 w-20 bg-aegis-border/50 rounded animate-pulse" />
      ) : (
        <div className={cn('text-2xl font-bold font-mono', color)}>{value}</div>
      )}
      {subtext && (
        <div className="text-xs text-aegis-muted mt-1">{subtext}</div>
      )}
    </div>
  );
}
