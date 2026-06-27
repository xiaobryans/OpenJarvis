// VantaPanels — compact, dense glassmorphism panels fed by live polled data.
// Maximum information, minimum space. No giant empty boxes.

import React from 'react';
import {
  VANTA, GlassPanel, DataRow, Metric, Dot,
  type CommsData, type MemoryData, type CalendarData, type BriefingData,
} from './vanta-kit';
import type { LiveState } from '../../lib/useLivePanel';

function senderName(from: string): string {
  const m = from.match(/^([^<]+)</);
  return ((m ? m[1] : from) || from).replace(/"/g, '').trim().slice(0, 18) || from;
}
function timeLabel(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso));
  } catch { return ''; }
}
function freshDot(s: LiveState<unknown>): React.ReactElement {
  return <Dot color={s.loading ? VANTA.textDim : s.ok ? VANTA.green : VANTA.red} pulse={s.loading} />;
}
function Lead({ value, unit, color, state }: { value: string | number; unit: string; color: string; state: LiveState<unknown> }): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
      <Metric value={value} color={color} size={26} />
      <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{unit}</span>
      <span style={{ marginLeft: 'auto' }}>{freshDot(state)}</span>
    </div>
  );
}
function MailRow({ from, subject, date, unread }: { from: string; subject: string; date: string; unread: boolean }): React.ReactElement {
  return (
    <div style={{ borderLeft: `2px solid ${unread ? VANTA.cyan : 'rgba(0,212,255,0.12)'}`, paddingLeft: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6 }}>
        <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: unread ? VANTA.text : VANTA.textDim, fontWeight: unread ? 700 : 400 }}>{senderName(from)}</span>
        <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim }}>{timeLabel(date)}</span>
      </div>
      <div style={{ fontSize: 10, color: VANTA.textDim, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{subject}</div>
    </div>
  );
}
function NotConnected({ what, color }: { what: string; color: string }): React.ReactElement {
  return <div style={{ fontFamily: VANTA.mono, fontSize: 10, color, opacity: 0.8, cursor: 'pointer' }}>↳ Connect {what}</div>;
}
// 7-day week-ahead strip (today highlighted) — fills the calendar panel footer.
function WeekStrip(): React.ReactElement {
  const today = new Date().getDay();
  const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  return (
    <div style={{ display: 'flex', gap: 4, justifyContent: 'space-between' }}>
      {days.map((d, i) => (
        <div key={i} style={{
          flex: 1, textAlign: 'center', fontFamily: VANTA.mono, fontSize: 9, padding: '3px 0', borderRadius: 4,
          color: i === today ? '#001018' : VANTA.textDim,
          background: i === today ? VANTA.green : 'rgba(0,255,136,0.05)',
          fontWeight: i === today ? 700 : 400,
        }}>{d}</div>
      ))}
    </div>
  );
}

// ─── Communications ──────────────────────────────────────────────────────────
export function CommsPanel({ state }: { state: LiveState<CommsData> }): React.ReactElement {
  const d = state.data;
  const connected = d?.connected ?? false;
  const msgs = d?.messages ?? [];
  const flagged = msgs.filter((m) => m.unread).length;
  return (
    <GlassPanel title="Communications" accent={VANTA.cyan} more={
      <div style={{ paddingTop: 4 }}>{msgs.slice(3, 8).map((m, i) => <MailRow key={i} {...m} />)}</div>
    }>
      <Lead value={connected ? (d?.unread_count ?? 0) : '—'} unit="unread" color={VANTA.cyan} state={state} />
      <DataRow label="Inbox" value={connected ? 'live' : 'offline'} color={connected ? VANTA.green : VANTA.textDim} />
      <DataRow label="Flagged / unseen" value={connected ? flagged : '—'} color={VANTA.amber} />
      <div style={{ height: 1, background: 'rgba(0,212,255,0.08)', margin: '3px 0' }} />
      {!connected && <NotConnected what="Gmail" color={VANTA.cyan} />}
      {connected && msgs.length === 0 && <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.textDim, fontStyle: 'italic' }}>Inbox clear</div>}
      {msgs.slice(0, 3).map((m, i) => <MailRow key={i} {...m} />)}
      <div style={{ marginTop: 'auto', paddingTop: 6, borderTop: '1px solid rgba(0,212,255,0.08)' }}>
        <div style={{ fontFamily: VANTA.mono, fontSize: 8, color: VANTA.textDim, letterSpacing: '0.16em', marginBottom: 4 }}>CHANNELS</div>
        <DataRow label="Gmail" value={connected ? 'live' : 'idle'} color={connected ? VANTA.green : VANTA.textDim} />
        <DataRow label="Slack" value="ready" color={VANTA.cyan} />
        <DataRow label="Telegram" value="ready" color={VANTA.cyan} />
      </div>
    </GlassPanel>
  );
}

// ─── Memory / Tasks ──────────────────────────────────────────────────────────
export function MemoryPanel({ state }: { state: LiveState<MemoryData> }): React.ReactElement {
  const d = state.data;
  const synced = d?.cloud_sync?.synced;
  const entries = typeof d?.total_entries === 'number' ? d.total_entries : '—';
  return (
    <GlassPanel title="Memory / Tasks" accent={VANTA.purple}>
      <Lead value={entries} unit="memories" color={VANTA.purple} state={state} />
      <DataRow label="Store" value="active" color={VANTA.green} />
      <DataRow label="Cloud sync" value={synced === undefined ? '…' : synced ? 'live' : 'pending'} color={synced ? VANTA.green : VANTA.amber} />
      <DataRow label="Follow-ups" value="PA-tracked" color={VANTA.cyan} />
      <DataRow label="Delegation" value="active" color={VANTA.green} />
      <DataRow label="Namespaces" value={typeof d?.namespaces === 'number' ? (d.namespaces as number) : 'unified'} color={VANTA.text} />
    </GlassPanel>
  );
}

// ─── Calendar ────────────────────────────────────────────────────────────────
export function CalendarPanel({ state }: { state: LiveState<CalendarData> }): React.ReactElement {
  const d = state.data;
  const connected = d?.connected ?? false;
  const events = d?.events ?? [];
  return (
    <GlassPanel title="Calendar — Today" accent={VANTA.green} more={
      <div style={{ paddingTop: 4 }}>{events.slice(4, 10).map((ev) => (
        <DataRow key={ev.id} label={ev.all_day ? 'all-day' : timeLabel(ev.start)} value={ev.summary} color={VANTA.text} />
      ))}</div>
    }>
      <Lead value={connected ? events.length : '—'} unit="events" color={VANTA.green} state={state} />
      <DataRow label="Date" value={d?.date ?? '—'} color={VANTA.text} />
      <div style={{ height: 1, background: 'rgba(0,255,136,0.08)', margin: '3px 0' }} />
      {!connected && <NotConnected what="Calendar" color={VANTA.green} />}
      {connected && events.length === 0 && <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.textDim, fontStyle: 'italic' }}>No events today</div>}
      {events.slice(0, 4).map((ev) => (
        <div key={ev.id} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.green, minWidth: 40 }}>{ev.all_day ? 'all-day' : timeLabel(ev.start)}</span>
          <span style={{ fontSize: 11, color: VANTA.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ev.summary}</span>
        </div>
      ))}
      <div style={{ marginTop: 'auto', paddingTop: 6, borderTop: '1px solid rgba(0,255,136,0.12)' }}>
        {d?.next_upcoming && (
          <div style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim, marginBottom: 5 }}>
            NEXT → <span style={{ color: VANTA.green }}>{d.next_upcoming.summary}</span>
          </div>
        )}
        <WeekStrip />
      </div>
    </GlassPanel>
  );
}

// ─── Finance (OMNIX placeholder, but filled meaningfully) ────────────────────
export function FinancePanel(): React.ReactElement {
  return (
    <GlassPanel title="Finance" accent={VANTA.amber}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <Metric value="—" color={VANTA.amber} size={22} />
        <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim, textTransform: 'uppercase' }}>MRR</span>
        <span style={{ marginLeft: 'auto', fontFamily: VANTA.mono, fontSize: 8, color: VANTA.amber, letterSpacing: '0.14em' }}>OMNIX</span>
      </div>
      <DataRow label="Revenue (MTD)" value="—" color={VANTA.textDim} />
      <DataRow label="Stripe" value="not linked" color={VANTA.textDim} />
      <DataRow label="Runway" value="—" color={VANTA.textDim} />
      <DataRow label="Burn / mo" value="—" color={VANTA.textDim} />
      <div style={{ height: 1, background: 'rgba(255,183,0,0.1)', margin: '3px 0' }} />
      <div style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim, lineHeight: 1.5 }}>
        Stripe connects here<br />when OMNIX launches.
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 14px', margin: '0 10px', background: 'rgba(255,183,0,0.08)', border: '1px solid rgba(255,183,0,0.3)', borderRadius: 8, flexShrink: 0 }}>
      <span style={{ fontSize: 13 }}>☀️</span>
      <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.amber, letterSpacing: '0.14em' }}>BRIEFING</span>
      <span style={{ fontFamily: VANTA.mono, fontSize: 11, color: VANTA.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>{firstLine.replace(/^#+\s*/, '')}</span>
      <button onClick={onDismiss} style={{ background: 'none', border: 'none', color: VANTA.textDim, cursor: 'pointer', fontSize: 13 }}>✕</button>
    </div>
  );
}
