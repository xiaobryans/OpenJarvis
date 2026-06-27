// vanta-kit — design tokens, shared types, and glassmorphism primitives for the
// VANTA Neural Command Center cockpit. Single-page, dark navy, glass panels.

import React from 'react';

// ─── Design tokens ───────────────────────────────────────────────────────────
export const VANTA = {
  bg: '#0a0e1a',
  cyan: '#00d4ff',
  green: '#00ff88',
  amber: '#ffb700',
  purple: '#9945ff',
  red: '#ff4d5e',
  text: '#cfe3f2',
  textDim: 'rgba(207,227,242,0.55)',
  mono: "'JetBrains Mono', 'SF Mono', 'Consolas', monospace",
  panelBg: 'rgba(14,22,40,0.55)',
  panelBorder: 'rgba(0,212,255,0.18)',
} as const;

export type SystemState = 'idle' | 'processing' | 'speaking' | 'error';
export type VoiceMode = 'listening' | 'active' | 'parked' | 'off';

// ─── Backend payload shapes (subset we render) ───────────────────────────────
export interface WeatherData {
  ok: boolean;
  location: string;
  text: string;
  source: string | null;
}
export interface CommsData {
  ok: boolean;
  connected: boolean;
  unread_count: number;
  messages: { from: string; subject: string; date: string; unread: boolean; snippet: string }[];
}
export interface CalendarData {
  ok: boolean;
  connected: boolean;
  date: string | null;
  events: { id: string; summary: string; start: string | null; end: string | null; all_day: boolean; location: string | null }[];
  next_upcoming: { summary: string; start: string | null } | null;
}
export interface MemoryData {
  total_entries?: number;
  cloud_sync?: { synced?: boolean };
  [k: string]: unknown;
}
export interface VoiceStatusData {
  listening?: boolean;
  active?: boolean;
  state?: string;
  wake_word?: string;
  [k: string]: unknown;
}
export interface ConnectorsData {
  connectors: { connector: string; state: string }[];
  count: number;
}
export interface BriefingData {
  exists: boolean;
  markdown: string;
  generated_at: string | null;
  id: number | null;
}
export interface HealthData {
  status?: string;
  model?: string;
  version?: string;
  stt_provider?: string;
  tts_provider?: string;
  [k: string]: unknown;
}

// ─── Primitives ──────────────────────────────────────────────────────────────
export function Dot({ color, pulse }: { color: string; pulse?: boolean }): React.ReactElement {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 7,
        height: 7,
        borderRadius: '50%',
        background: color,
        boxShadow: `0 0 8px ${color}`,
        animation: pulse ? 'vantaPulse 1.6s ease-in-out infinite' : undefined,
      }}
    />
  );
}

export function GlassPanel({
  title,
  accent = VANTA.cyan,
  children,
  flush = false,
}: {
  title?: string;
  accent?: string;
  children: React.ReactNode;
  flush?: boolean;
}): React.ReactElement {
  return (
    <div
      style={{
        background: VANTA.panelBg,
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        border: `1px solid ${VANTA.panelBorder}`,
        borderRadius: 10,
        boxShadow: `0 0 0 1px rgba(0,0,0,0.2), 0 8px 28px rgba(0,0,0,0.35), inset 0 0 24px ${accent}10`,
        padding: flush ? 0 : '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        overflow: 'hidden',
        minHeight: 0,
      }}
    >
      {title && (
        <div
          style={{
            fontSize: 9,
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
            color: accent,
            fontFamily: VANTA.mono,
            opacity: 0.85,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span style={{ width: 14, height: 1, background: accent, opacity: 0.5 }} />
          {title}
        </div>
      )}
      {children}
    </div>
  );
}

// Monospace metric that flashes when its value changes (ticking numbers).
export function Metric({
  value,
  color = VANTA.green,
  size = 13,
}: {
  value: string | number;
  color?: string;
  size?: number;
}): React.ReactElement {
  const [flash, setFlash] = React.useState(false);
  const prev = React.useRef(value);
  React.useEffect(() => {
    if (prev.current !== value) {
      setFlash(true);
      prev.current = value;
      const t = setTimeout(() => setFlash(false), 450);
      return () => clearTimeout(t);
    }
  }, [value]);
  return (
    <span
      style={{
        fontFamily: VANTA.mono,
        fontSize: size,
        color,
        fontWeight: 600,
        transition: 'text-shadow 0.45s, color 0.45s',
        textShadow: flash ? `0 0 10px ${color}` : 'none',
      }}
    >
      {value}
    </span>
  );
}

// Shared keyframes — injected once.
export function VantaKeyframes(): React.ReactElement {
  return (
    <style>{`
      @keyframes vantaPulse { 0%,100%{opacity:1} 50%{opacity:0.35} }
      @keyframes vantaSpin { from{transform:rotate(0)} to{transform:rotate(360deg)} }
      @keyframes vantaSpinRev { from{transform:rotate(0)} to{transform:rotate(-360deg)} }
      @keyframes vantaRipple { 0%{transform:scale(1);opacity:0.6} 100%{transform:scale(1.8);opacity:0} }
      @keyframes vantaDrift { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
      .vanta-scroll::-webkit-scrollbar{width:5px}
      .vanta-scroll::-webkit-scrollbar-thumb{background:rgba(0,212,255,0.25);border-radius:3px}
    `}</style>
  );
}
