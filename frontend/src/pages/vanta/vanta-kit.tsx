// vanta-kit — design tokens, shared types, and glassmorphism primitives for the
// VANTA Neural Command Center cockpit. Single-page, deep navy, glass panels.

import React from 'react';

// ─── Design tokens ───────────────────────────────────────────────────────────
export const VANTA = {
  bg: '#050a14',
  cyan: '#00d4ff',
  green: '#00ff88',
  amber: '#ffb700',
  purple: '#9945ff',
  red: '#ff4444',
  white: '#ffffff',
  text: '#e6f2ff',
  textDim: '#4a6080',
  mono: "'JetBrains Mono', 'SF Mono', 'Consolas', monospace",
  panelBorder: 'rgba(0,212,255,0.28)',
  panelBg: 'rgba(10,20,40,0.45)',
} as const;

export type SystemState = 'idle' | 'processing' | 'speaking' | 'error';
export type VoiceMode = 'listening' | 'active' | 'parked' | 'off';

// ─── Backend payload shapes (subset we render) ───────────────────────────────
export interface WeatherData { ok: boolean; location: string; text: string; source: string | null }
export interface CommsData {
  ok: boolean; connected: boolean; unread_count: number;
  messages: { from: string; subject: string; date: string; unread: boolean; snippet: string }[];
}
export interface CalendarData {
  ok: boolean; connected: boolean; date: string | null;
  events: { id: string; summary: string; start: string | null; end: string | null; all_day: boolean; location: string | null }[];
  next_upcoming: { summary: string; start: string | null } | null;
}
export interface MemoryData { total_entries?: number; cloud_sync?: { synced?: boolean }; [k: string]: unknown }
export interface VoiceStatusData { listening?: boolean; active?: boolean; state?: string; wake_word?: string; [k: string]: unknown }
export interface ConnectorsData { connectors: { connector: string; state: string }[]; count: number }
export interface BriefingData { exists: boolean; markdown: string; generated_at: string | null; id: number | null }
export interface HealthData { status?: string; model?: string; version?: string; stt_provider?: string; tts_provider?: string; [k: string]: unknown }

// ─── Primitives ──────────────────────────────────────────────────────────────
export function Dot({ color, pulse }: { color: string; pulse?: boolean }): React.ReactElement {
  return (
    <span
      style={{
        display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
        background: color, boxShadow: `0 0 8px ${color}, 0 0 3px ${color}`, flexShrink: 0,
        animation: pulse ? 'vantaPulse 1.8s ease-in-out infinite' : undefined,
      }}
    />
  );
}

// Compact one-line data row: label left, value right.
export function DataRow({ label, value, color = VANTA.text, labelColor = VANTA.textDim }: { label: string; value: React.ReactNode; color?: string; labelColor?: string }): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8, fontFamily: VANTA.mono, fontSize: 11, lineHeight: 1.55 }}>
      <span style={{ color: labelColor, whiteSpace: 'nowrap' }}>{label}</span>
      <span style={{ color, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'right' }}>{value}</span>
    </div>
  );
}

// Glassmorphism panel with accent left-border header and expand-on-click.
export function GlassPanel({
  title, accent = VANTA.cyan, children, more, headerRight,
}: {
  title: string;
  accent?: string;
  children: React.ReactNode;
  more?: React.ReactNode;
  headerRight?: React.ReactNode;
}): React.ReactElement {
  const [open, setOpen] = React.useState(false);
  return (
    <div
      style={{
        background: 'rgba(10,20,40,0.45)',
        backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(0,212,255,0.22)',
        boxShadow: `0 0 12px rgba(0,212,255,0.15), 0 0 1px rgba(0,212,255,0.4), inset 0 1px 0 rgba(255,255,255,0.06)`,
        borderRadius: 8,
        display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0,
      }}
    >
      <div
        onClick={more ? () => setOpen((o) => !o) : undefined}
        style={{
          display: 'flex', alignItems: 'center', gap: 7, padding: '6px 9px',
          borderLeft: `2px solid ${accent}`, cursor: more ? 'pointer' : 'default',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase', color: accent, fontFamily: VANTA.mono, fontWeight: 600 }}>{title}</span>
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          {headerRight}
          {more && <span style={{ color: VANTA.textDim, fontSize: 9 }}>{open ? '▾' : '▸'}</span>}
        </span>
      </div>
      <div className="vanta-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '4px 9px 9px', overflow: 'hidden', flex: 1, minHeight: 0 }}>
        {children}
        {open && more}
      </div>
    </div>
  );
}

// Monospace metric that flashes when its value changes.
export function Metric({ value, color = VANTA.green, size = 13 }: { value: string | number; color?: string; size?: number }): React.ReactElement {
  const [flash, setFlash] = React.useState(false);
  const prev = React.useRef(value);
  React.useEffect(() => {
    if (prev.current !== value) {
      setFlash(true);
      prev.current = value;
      const t = setTimeout(() => setFlash(false), 500);
      return () => clearTimeout(t);
    }
  }, [value]);
  return (
    <span style={{ fontFamily: VANTA.mono, fontSize: size, color, fontWeight: 700, transition: 'text-shadow 0.5s, color 0.5s', textShadow: flash ? `0 0 12px ${color}` : `0 0 4px ${color}55` }}>{value}</span>
  );
}

export function VantaKeyframes(): React.ReactElement {
  return (
    <style>{`
      @keyframes vantaPulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
      @keyframes vantaSpin { from{transform:rotate(0)} to{transform:rotate(360deg)} }
      @keyframes vantaSpinRev { from{transform:rotate(0)} to{transform:rotate(-360deg)} }
      @keyframes vantaScan { 0%{transform:translateY(-30vh);opacity:0} 8%{opacity:1} 92%{opacity:1} 100%{transform:translateY(130vh);opacity:0} }
      @keyframes vantaFlow { 0%{left:0%;opacity:0} 8%{opacity:1} 92%{opacity:1} 100%{left:100%;opacity:0} }
      @keyframes vantaBreathe { 0%,100%{opacity:0.6;box-shadow:0 0 6px currentColor} 50%{opacity:1;box-shadow:0 0 12px currentColor} }
      .vanta-scroll::-webkit-scrollbar{width:4px}
      .vanta-scroll::-webkit-scrollbar-thumb{background:rgba(0,212,255,0.25);border-radius:3px}
    `}</style>
  );
}
