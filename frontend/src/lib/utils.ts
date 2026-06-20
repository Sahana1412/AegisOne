import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

export function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export const SEVERITY_CONFIG = {
  critical: { color: 'text-aegis-critical', bg: 'bg-red-950/40', border: 'border-red-800/50', dot: 'bg-aegis-critical', label: 'CRITICAL' },
  high:     { color: 'text-aegis-high',     bg: 'bg-orange-950/40', border: 'border-orange-800/50', dot: 'bg-aegis-high', label: 'HIGH' },
  medium:   { color: 'text-aegis-medium',   bg: 'bg-yellow-950/40', border: 'border-yellow-800/50', dot: 'bg-aegis-medium', label: 'MEDIUM' },
  low:      { color: 'text-aegis-low',      bg: 'bg-green-950/40', border: 'border-green-800/50', dot: 'bg-aegis-low', label: 'LOW' },
  info:     { color: 'text-aegis-info',     bg: 'bg-blue-950/40', border: 'border-blue-800/50', dot: 'bg-aegis-info', label: 'INFO' },
} as const;

export const AGENT_CONFIG: Record<string, { icon: string; color: string; role: string }> = {
  intake_agent:          { icon: '📥', color: 'text-blue-400',   role: 'Intake' },
  threat_intel_agent:    { icon: '🕵️', color: 'text-orange-400', role: 'Threat Intel' },
  mitre_mapping_agent:   { icon: '🗺️', color: 'text-purple-400', role: 'MITRE Mapping' },
  risk_assessment_agent: { icon: '⚖️', color: 'text-yellow-400', role: 'Risk Assessment' },
  consensus_agent:       { icon: '🧠', color: 'text-cyan-400',   role: 'Consensus' },
  red_team_agent:        { icon: '🔴', color: 'text-red-400',    role: 'Red Team' },
  remediation_agent:     { icon: '🛠️', color: 'text-green-400',  role: 'Remediation' },
  approval_agent:        { icon: '✅', color: 'text-emerald-400', role: 'Approval' },
  execution_agent:       { icon: '⚡', color: 'text-amber-400',  role: 'Execution' },
  verification_agent:    { icon: '🔍', color: 'text-teal-400',   role: 'Verification' },
  report_agent:          { icon: '📋', color: 'text-slate-400',  role: 'Report' },
  audit_trail_agent:     { icon: '📜', color: 'text-gray-400',   role: 'Audit Trail' },
};
