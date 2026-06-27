// vanta-kit — design tokens, types, and HUD primitives for the VANTA Neural
// Command Center, matching the jarvis_hud reference aesthetic.

import React from 'react';

// ─── Exact reference palette ─────────────────────────────────────────────────
export const VANTA = {
  c: '#00D4FF', // cyan primary
  am: '#FF9500', // amber
  gr: '#00FF88', // green
  rd: '#FF3355', // red
  pu: '#BD60FF', // purple
  tl: '#00F5D4', // teal
  bg: '#020810', // background
  panel: 'rgba(4,16,40,0.18)',
  border: 'rgba(0,200,255,0.28)',
  text: '#8EC8E8',
  dim: 'rgba(142,200,232,0.38)',
  white: '#ffffff',
  // aliases kept for older callers
  cyan: '#00D4FF',
  green: '#00FF88',
  amber: '#FF9500',
  purple: '#BD60FF',
  red: '#FF3355',
  textDim: 'rgba(142,200,232,0.38)',
  panelBorder: 'rgba(0,200,255,0.28)',
  orb: "'Orbitron', 'JetBrains Mono', monospace",
  mono: "'JetBrains Mono', 'SF Mono', monospace",
} as const;

export type SystemState = 'idle' | 'processing' | 'speaking' | 'error';
export type VoiceMode = 'listening' | 'active' | 'parked' | 'off';

// ─── Backend payload shapes ──────────────────────────────────────────────────
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
    <span style={{
      display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: color,
      boxShadow: `0 0 8px ${color}`, flexShrink: 0,
      animation: pulse ? 'vDotPulse 1.6s ease-in-out infinite' : undefined,
    }} />
  );
}

export function DataRow({ label, value, color = VANTA.text, labelColor = VANTA.dim }: { label: string; value: React.ReactNode; color?: string; labelColor?: string }): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8, fontFamily: VANTA.mono, fontSize: 10.5, lineHeight: 1.6 }}>
      <span style={{ color: labelColor, whiteSpace: 'nowrap' }}>{label}</span>
      <span style={{ color, fontWeight: 500, fontSize: 11, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'right' }}>{value}</span>
    </div>
  );
}

// Glassmorphism panel with cyan L-shaped corner brackets (top-left + bottom-right).
export function GlassPanel({ title, accent = VANTA.c, children, more }: { title: string; accent?: string; children: React.ReactNode; more?: React.ReactNode }): React.ReactElement {
  const [open, setOpen] = React.useState(false);
  const bracket = (corner: 'tl' | 'br'): React.CSSProperties => ({
    position: 'absolute', width: 14, height: 14, pointerEvents: 'none',
    borderColor: VANTA.c,
    ...(corner === 'tl'
      ? { top: -1, left: -1, borderTop: `1px solid ${VANTA.c}`, borderLeft: `1px solid ${VANTA.c}` }
      : { bottom: -1, right: -1, borderBottom: `1px solid ${VANTA.c}`, borderRight: `1px solid ${VANTA.c}` }),
  });
  return (
    <div style={{
      position: 'relative',
      background: 'linear-gradient(135deg, rgba(4,16,40,0.22), rgba(4,16,40,0.12))',
      backdropFilter: 'blur(22px) saturate(180%)', WebkitBackdropFilter: 'blur(22px) saturate(180%)',
      border: `1px solid ${VANTA.border}`, borderRadius: 4,
      boxShadow: '0 0 18px rgba(0,200,255,0.06), inset 0 0 24px rgba(0,160,255,0.03)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0,
    }}>
      <span style={bracket('tl')} />
      <span style={bracket('br')} />
      <div onClick={more ? () => setOpen((o) => !o) : undefined}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 10px 4px', cursor: more ? 'pointer' : 'default', flexShrink: 0 }}>
        <span style={{ fontFamily: VANTA.orb, fontSize: 9, fontWeight: 600, letterSpacing: '3px', textTransform: 'uppercase', color: accent }}>{title}</span>
        {more && <span style={{ marginLeft: 'auto', color: VANTA.dim, fontSize: 9 }}>{open ? '▾' : '▸'}</span>}
      </div>
      <div className="vanta-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 3, padding: '2px 10px 9px', overflow: 'hidden', flex: 1, minHeight: 0 }}>
        {children}
        {open && more}
      </div>
    </div>
  );
}

// Orbitron metric that flashes on change.
export function Metric({ value, color = VANTA.gr, size = 24 }: { value: string | number; color?: string; size?: number }): React.ReactElement {
  const [flash, setFlash] = React.useState(false);
  const prev = React.useRef(value);
  React.useEffect(() => {
    if (prev.current !== value) { setFlash(true); prev.current = value; const t = setTimeout(() => setFlash(false), 500); return () => clearTimeout(t); }
  }, [value]);
  return <span style={{ fontFamily: VANTA.orb, fontSize: size, color, fontWeight: 700, transition: 'text-shadow 0.5s', textShadow: flash ? `0 0 14px ${color}` : `0 0 6px ${color}55` }}>{value}</span>;
}

export function VantaKeyframes(): React.ReactElement {
  return (
    <style>{`
      @keyframes vDotPulse { 0%,100%{opacity:1} 50%{opacity:0.35} }
      @keyframes vRing { 0%{transform:scale(0.6);opacity:0.7} 100%{transform:scale(1.9);opacity:0} }
      @keyframes vBreathe { 0%,100%{opacity:0.5;transform:scale(0.96)} 50%{opacity:0.95;transform:scale(1.06)} }
      @keyframes vSpin { from{transform:rotate(0)} to{transform:rotate(360deg)} }
      @keyframes vSpinRev { from{transform:rotate(0)} to{transform:rotate(-360deg)} }
      @keyframes vScan { 0%{transform:translateY(-30vh);opacity:0} 8%{opacity:1} 92%{opacity:1} 100%{transform:translateY(130vh);opacity:0} }
      @keyframes vFlow { 0%{left:0%;opacity:0} 8%{opacity:1} 92%{opacity:1} 100%{left:100%;opacity:0} }
      @keyframes vCorePulse { 0%,100%{opacity:0.85} 50%{opacity:1} }
      .vanta-scroll::-webkit-scrollbar{width:4px}
      .vanta-scroll::-webkit-scrollbar-thumb{background:rgba(0,200,255,0.25);border-radius:3px}
    `}</style>
  );
}
