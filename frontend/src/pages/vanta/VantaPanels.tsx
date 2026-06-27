// VantaPanels — glassmorphism side panels (Communications, Memory/Tasks,
// Calendar, Finance) + briefing banner. All fed by live polled data.

import React from 'react';
import {
  VANTA, GlassPanel, Metric, Dot,
  type CommsData, type MemoryData, type CalendarData, type BriefingData,
} from './vanta-kit';
import type { LiveState } from '../../lib/useLivePanel';

function senderName(from: string): string {
  const m = from.match(/^([^<]+)</);
  return (m ? m[1] : from).replace(/"/g, '').trim() || from;
}

function timeLabel(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso));
  } catch {
    return '';
  }
}

function freshness(s: LiveState<unknown>): React.ReactElement {
  const color = s.loading ? VANTA.textDim : s.ok ? VANTA.green : VANTA.red;
  return <Dot color={color} pulse={s.loading} />;
}

// ─── Communications (Gmail) ──────────────────────────────────────────────────
export function CommsPanel({ state }: { state: LiveState<CommsData> }): React.ReactElement {
  const d = state.data;
  const connected = d?.connected ?? false;
  return (
    <GlassPanel title="Communications" accent={VANTA.cyan}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <Metric value={d?.unread_count ?? '—'} color={VANTA.cyan} size={22} />
        <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim }}>unread</span>
        <span style={{ marginLeft: 'auto' }}>{freshness(state)}</span>
      </div>
      <div className="vanta-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 5, overflowY: 'auto', flex: 1, minHeight: 0 }}>
        {!connected && <Empty text="Gmail not connected" />}
        {connected && (d?.messages ?? []).length === 0 && <Empty text="Inbox clear" />}
        {(d?.messages ?? []).map((m, i) => (
          <div key={i} style={{ borderLeft: `2px solid ${m.unread ? VANTA.cyan : 'rgba(0,212,255,0.15)'}`, paddingLeft: 7 }}>
            <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: m.unread ? VANTA.text : VANTA.textDim, fontWeight: m.unread ? 700 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {senderName(m.from)}
            </div>
            <div style={{ fontSize: 10, color: VANTA.textDim, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.subject}</div>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}

// ─── Memory / Tasks ──────────────────────────────────────────────────────────
export function MemoryPanel({ state }: { state: LiveState<MemoryData> }): React.ReactElement {
  const d = state.data;
  const synced = d?.cloud_sync?.synced;
  return (
    <GlassPanel title="Memory / Tasks" accent={VANTA.purple}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <Metric value={d?.total_entries ?? '—'} color={VANTA.purple} size={22} />
        <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim }}>memories</span>
        <span style={{ marginLeft: 'auto' }}>{freshness(state)}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <Row label="Store" value="active" color={VANTA.green} />
        <Row label="Cloud sync" value={synced === undefined ? '…' : synced ? 'live' : 'pending'} color={synced ? VANTA.green : VANTA.amber} />
        <Row label="Follow-ups" value="PA-tracked" color={VANTA.cyan} />
      </div>
    </GlassPanel>
  );
}

// ─── Calendar ────────────────────────────────────────────────────────────────
export function CalendarPanel({ state }: { state: LiveState<CalendarData> }): React.ReactElement {
  const d = state.data;
  const connected = d?.connected ?? false;
  const events = d?.events ?? [];
  return (
    <GlassPanel title="Calendar — Today" accent={VANTA.green}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <Metric value={connected ? events.length : '—'} color={VANTA.green} size={22} />
        <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim }}>events</span>
        <span style={{ marginLeft: 'auto' }}>{freshness(state)}</span>
      </div>
      <div className="vanta-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 5, overflowY: 'auto', flex: 1, minHeight: 0 }}>
        {!connected && <Empty text="Calendar not connected" />}
        {connected && events.length === 0 && <Empty text="No events today" />}
        {events.map((ev) => (
          <div key={ev.id} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
            <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.green, minWidth: 38 }}>{ev.all_day ? 'all-day' : timeLabel(ev.start)}</span>
            <span style={{ fontSize: 11, color: VANTA.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ev.summary}</span>
          </div>
        ))}
      </div>
      {d?.next_upcoming && (
        <div style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim, borderTop: `1px solid ${VANTA.panelBorder}`, paddingTop: 5 }}>
          NEXT → <span style={{ color: VANTA.green }}>{d.next_upcoming.summary}</span>
        </div>
      )}
    </GlassPanel>
  );
}

// ─── Finance (placeholder for OMNIX / Stripe) ────────────────────────────────
export function FinancePanel(): React.ReactElement {
  return (
    <GlassPanel title="Finance" accent={VANTA.amber}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 6, opacity: 0.75 }}>
        <div style={{ fontSize: 24 }}>💳</div>
        <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.textDim, textAlign: 'center' }}>
          Stripe connects here<br />when OMNIX launches
        </div>
        <div style={{ fontFamily: VANTA.mono, fontSize: 8, color: VANTA.amber, letterSpacing: '0.16em' }}>PLACEHOLDER</div>
      </div>
    </GlassPanel>
  );
}

// ─── Briefing banner ─────────────────────────────────────────────────────────
export function BriefingBanner({ state, onDismiss }: { state: LiveState<BriefingData>; onDismiss: () => void }): React.ReactElement | null {
  const d = state.data;
  if (!d?.exists || !d.markdown) return null;
  const firstLine = d.markdown.split('\n').find((l) => l.trim()) ?? 'Morning briefing ready';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 14px', margin: '0 10px', background: 'rgba(255,183,0,0.08)', border: `1px solid rgba(255,183,0,0.3)`, borderRadius: 8, flexShrink: 0 }}>
      <span style={{ fontSize: 14 }}>☀️</span>
      <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.amber, letterSpacing: '0.14em' }}>BRIEFING</span>
      <span style={{ fontFamily: VANTA.mono, fontSize: 11, color: VANTA.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>
        {firstLine.replace(/^#+\s*/, '')}
      </span>
      <button onClick={onDismiss} style={{ background: 'none', border: 'none', color: VANTA.textDim, cursor: 'pointer', fontSize: 14 }}>✕</button>
    </div>
  );
}

// ─── small helpers ───────────────────────────────────────────────────────────
function Empty({ text }: { text: string }): React.ReactElement {
  return <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.textDim, padding: '6px 2px', fontStyle: 'italic' }}>{text}</div>;
}
function Row({ label, value, color }: { label: string; value: string; color: string }): React.ReactElement {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: VANTA.mono, fontSize: 10 }}>
      <span style={{ color: VANTA.textDim }}>{label}</span>
      <span style={{ color }}>{value}</span>
    </div>
  );
}
