'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import type { AgentMessage } from '@/lib/api';
import { AGENT_CONFIG, formatDateTime, cn } from '@/lib/utils';

interface AgentTimelineProps {
  messages: AgentMessage[];
  incidentId: string;
}

function MarkdownText({ text }: { text: string }) {
  // Basic markdown: **bold**, `code`, \n\n paragraphs
  const rendered = text
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-aegis-text font-semibold">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-aegis-bg rounded font-mono text-[11px] text-aegis-accent">$1</code>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
  return <div dangerouslySetInnerHTML={{ __html: rendered }} />;
}

const MESSAGE_TYPE_STYLE: Record<string, { border: string; header: string }> = {
  routing:        { border: 'border-blue-500/30',    header: 'text-blue-400' },
  analysis:       { border: 'border-cyan-500/30',    header: 'text-cyan-400' },
  assessment:     { border: 'border-yellow-500/30',  header: 'text-yellow-400' },
  consensus:      { border: 'border-purple-500/30',  header: 'text-purple-400' },
  challenge:      { border: 'border-red-500/30',     header: 'text-red-400' },
  recommendation: { border: 'border-green-500/30',   header: 'text-green-400' },
  execution:      { border: 'border-amber-500/30',   header: 'text-amber-400' },
  verification:   { border: 'border-teal-500/30',    header: 'text-teal-400' },
  report:         { border: 'border-slate-500/30',   header: 'text-slate-400' },
  warning:        { border: 'border-red-600/50',     header: 'text-red-500' },
  default:        { border: 'border-aegis-border',   header: 'text-aegis-muted' },
};

function AgentMessageCard({ msg }: { msg: AgentMessage }) {
  const [expanded, setExpanded] = useState(true);
  const cfg = AGENT_CONFIG[msg.agent_name];
  const style = MESSAGE_TYPE_STYLE[msg.message_type] ?? MESSAGE_TYPE_STYLE.default;
  const isLong = msg.content.length > 400;

  return (
    <div className={cn('relative pl-8 animate-slide-in', 'group')}>
      {/* Timeline line */}
      <div className="absolute left-3.5 top-0 bottom-0 w-px bg-aegis-border/50" />

      {/* Agent avatar dot */}
      <div className={cn(
        'absolute left-1.5 top-4 w-4 h-4 rounded-full border-2 flex items-center justify-center text-[8px]',
        'bg-aegis-surface border-aegis-border group-hover:border-aegis-accent/50 transition-colors'
      )}>
        <span>{cfg?.icon ?? '🤖'}</span>
      </div>

      <div className={cn('ml-2 mb-4 border rounded-lg overflow-hidden', style.border, 'bg-aegis-surface/60')}>
        {/* Message Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-aegis-border/50 bg-aegis-bg/40">
          <div className="flex items-center gap-2.5">
            <span className="text-base">{cfg?.icon ?? '🤖'}</span>
            <div>
              <span className={cn('text-xs font-semibold uppercase tracking-wide', style.header)}>
                {cfg?.role ?? msg.agent_name}
              </span>
              <span className="text-[10px] text-aegis-muted ml-2 font-mono">
                {msg.band_event_type?.replace(/_/g, ' ')}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {msg.confidence_score !== null && msg.confidence_score !== undefined && (
              <div className="flex items-center gap-1.5">
                <div className="text-[10px] text-aegis-muted">confidence</div>
                <div className={cn(
                  'text-xs font-mono font-bold px-1.5 py-0.5 rounded',
                  msg.confidence_score > 0.8 ? 'text-aegis-low bg-green-950/40' :
                  msg.confidence_score > 0.5 ? 'text-aegis-medium bg-yellow-950/40' :
                  'text-aegis-critical bg-red-950/40'
                )}>
                  {(msg.confidence_score * 100).toFixed(0)}%
                </div>
              </div>
            )}
            <div className="text-[10px] text-aegis-muted font-mono">{formatDateTime(msg.timestamp)}</div>
            {isLong && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-aegis-muted hover:text-aegis-text transition-colors"
              >
                {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>
        </div>

        {/* Message Body */}
        {(expanded || !isLong) && (
          <div className="px-4 py-3 text-sm text-aegis-text-dim leading-relaxed">
            <MarkdownText text={msg.content} />
          </div>
        )}

        {!expanded && isLong && (
          <button
            onClick={() => setExpanded(true)}
            className="w-full px-4 py-2 text-xs text-aegis-muted hover:text-aegis-accent transition-colors text-left"
          >
            Click to expand…
          </button>
        )}
      </div>
    </div>
  );
}

export function AgentTimeline({ messages, incidentId }: AgentTimelineProps) {
  if (messages.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-4">🤖</div>
        <h3 className="text-aegis-text font-medium mb-2">Agents Assembling…</h3>
        <p className="text-aegis-muted text-sm">
          Band is orchestrating the investigation pipeline. Agent messages will appear here as they complete their analysis.
        </p>
        <div className="flex items-center justify-center gap-1 mt-4">
          {[0,1,2].map(i => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-aegis-accent animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      {/* Legend */}
      <div className="flex items-center gap-2 mb-6 px-2 py-2 bg-aegis-surface/40 rounded-lg border border-aegis-border text-[10px] text-aegis-muted font-mono">
        <span className="text-aegis-accent">BAND ORCHESTRATION</span>
        <span>·</span>
        <span>{messages.length} agent message{messages.length !== 1 ? 's' : ''}</span>
        <span>·</span>
        <span>Timeline below shows real-time multi-agent reasoning</span>
      </div>

      {/* Messages */}
      <div className="relative">
        {messages.map((msg) => (
          <AgentMessageCard key={msg.id} msg={msg} />
        ))}
      </div>
    </div>
  );
}
