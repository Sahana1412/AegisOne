'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Shield, Activity, Users, CheckSquare, FileText,
  Settings, AlertTriangle, Zap, Terminal, ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: Activity },
  { href: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { href: '/agents', label: 'Agent Fleet', icon: Zap },
  { href: '/approvals', label: 'Approvals', icon: CheckSquare },
  { href: '/audit', label: 'Audit Trail', icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 flex flex-col bg-aegis-surface border-r border-aegis-border">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-aegis-border">
        <div className="relative">
          <Shield className="w-7 h-7 text-aegis-accent" />
          <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-aegis-low animate-pulse" />
        </div>
        <div>
          <div className="text-sm font-bold text-aegis-text tracking-tight">AegisOne</div>
          <div className="text-[10px] text-aegis-muted font-mono uppercase tracking-widest">XDR Platform</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-2 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all group',
                active
                  ? 'bg-aegis-accent/10 text-aegis-accent border border-aegis-accent/20'
                  : 'text-aegis-text-dim hover:text-aegis-text hover:bg-aegis-border/50'
              )}
            >
              <Icon className={cn('w-4 h-4 shrink-0', active ? 'text-aegis-accent' : 'text-aegis-muted group-hover:text-aegis-text-dim')} />
              <span className="flex-1">{label}</span>
              {active && <ChevronRight className="w-3 h-3 text-aegis-accent/60" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-aegis-border px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-aegis-low animate-pulse" />
          <span className="text-[10px] text-aegis-muted font-mono">BAND ONLINE</span>
        </div>
        <div className="text-[10px] text-aegis-muted/60 font-mono mt-0.5">17 agents active</div>
      </div>
    </aside>
  );
}
