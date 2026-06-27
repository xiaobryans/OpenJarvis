// VantaPanels — packed, vibrant glassmorphism panels fed by live polled data.
// Maximum information density; stay useful even when a source is offline.

import React from 'react';
import {
  VANTA, GlassPanel, DataRow, Metric, Dot,
  type CommsData, type MemoryData, type CalendarData, type BriefingData,
  type ConnectorsData, type VoiceStatusData, type HealthData,
} from './vanta-kit';
import type { LiveState } from '../../lib/useLivePanel';

function senderName(from: string): string {
  const m = from.match(/^([^<]+)</);
  return ((m ? m[1] : from) || from).replace(/"/g, '').trim().slice(0, 18) || from;
}
function timeLabel(iso: string | null): string {
  if (!iso) return '';
  try { return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso)); } catch { return ''; }
}
function syncLabel(ms: number | null): string {
  if (!ms) return '—';
  try { return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(ms)); } catch { return '—'; }
}
function freshDot(s: LiveState<unknown>): React.ReactElement {
  return <Dot color={s.loading ? VANTA.textDim : s.ok ? VANTA.green : VANTA.red} pulse={s.loading} />;
}
function Lead({ value, unit, color, state }: { value: string | number; unit: string; color: string; state: LiveState<unknown> }): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
      <Metric value={value} color={color} size={28} />
      <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{unit}</span>
      <span style={{ marginLeft: 'auto' }}>{freshDot(state)}</span>
    </div>
  );
}
function Divider({ color = 'rgba(0,212,255,0.12)' }: { color?: string }): React.ReactElement {
  return <div style={{ height: 1, background: color, margin: '3px 0' }} />;
}
function SectionLabel({ text }: { text: string }): React.ReactElement {
  return <div style={{ fontFamily: VANTA.mono, fontSize: 8, color: VANTA.textDim, letterSpacing: '0.18em' }}>{text}</div>;
}
function ChannelRow({ name, status, color }: { name: string; status: string; color: string }): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: VANTA.mono, fontSize: 11, lineHeight: 1.6 }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: VANTA.text }}><Dot color={color} /> {name}</span>
      <span style={{ color, fontWeight: 600 }}>{status}</span>
    </div>
  );
}
function MailRow({ from, subject, date, unread }: { from: string; subject: string; date: string; unread: boolean }): React.ReactElement {
  return (
    <div style={{ borderLeft: `2px solid ${unread ? VANTA.cyan : 'rgba(0,212,255,0.15)'}`, paddingLeft: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6 }}>
        <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: unread ? VANTA.white : VANTA.textDim, fontWeight: unread ? 700 : 400 }}>{senderName(from)}</span>
        <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim }}>{timeLabel(date)}</span>
      </div>
      <div style={{ fontSize: 10, color: unread ? VANTA.text : VANTA.textDim, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{subject}</div>
    </div>
  );
}
function WeekStrip(): React.ReactElement {
  const today = new Date().getDay();
  const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {days.map((d, i) => (
        <div key={i} style={{ flex: 1, textAlign: 'center', fontFamily: VANTA.mono, fontSize: 9, padding: '3px 0', borderRadius: 4, color: i === today ? '#04121a' : VANTA.textDim, background: i === today ? VANTA.green : 'rgba(0,255,136,0.06)', boxShadow: i === today ? `0 0 10px ${VANTA.green}` : 'none', fontWeight: i === today ? 700 : 400 }}>{d}</div>
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
    <GlassPanel title="Communications" accent={VANTA.cyan} more={<div style={{ paddingTop: 4 }}>{msgs.slice(3, 9).map((m, i) => <MailRow key={i} {...m} />)}</div>}>
      <Lead value={connected ? (d?.unread_count ?? 0) : 0} unit="unread" color={VANTA.cyan} state={state} />
      <DataRow label="Inbox" value={connected ? 'live' : 'offline'} color={connected ? VANTA.green : VANTA.textDim} />
      <DataRow label="Flagged" value={connected ? flagged : 0} color={VANTA.amber} />
      <DataRow label="Last sync" value={syncLabel(state.lastUpdated)} color={VANTA.textDim} />
      <Divider />
      <SectionLabel text="CHANNELS" />
      <ChannelRow name="Gmail" status={connected ? 'live' : 'idle'} color={connected ? VANTA.green : VANTA.textDim} />
      <ChannelRow name="Slack" status="ready" color={VANTA.cyan} />
      <ChannelRow name="Telegram" status="ready" color={VANTA.cyan} />
      <Divider />
      {!connected && <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.cyan, opacity: 0.8 }}>↳ Connect Gmail for live inbox</div>}
      {connected && msgs.length === 0 && <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.textDim, fontStyle: 'italic' }}>Inbox clear</div>}
      {msgs.slice(0, 3).map((m, i) => <MailRow key={i} {...m} />)}
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
      <DataRow label="Namespaces" value="unified" color={VANTA.green} />
      <DataRow label="Last sync" value={syncLabel(state.lastUpdated)} color={VANTA.textDim} />
    </GlassPanel>
  );
}

// ─── Calendar ────────────────────────────────────────────────────────────────
export function CalendarPanel({ state }: { state: LiveState<CalendarData> }): React.ReactElement {
  const d = state.data;
  const connected = d?.connected ?? false;
  const events = d?.events ?? [];
  return (
    <GlassPanel title="Calendar — Today" accent={VANTA.green} more={<div style={{ paddingTop: 4 }}>{events.slice(3, 9).map((ev) => <DataRow key={ev.id} label={ev.all_day ? 'all-day' : timeLabel(ev.start)} value={ev.summary} color={VANTA.text} />)}</div>}>
      <Lead value={connected ? events.length : 0} unit="events" color={VANTA.green} state={state} />
      <DataRow label="Date" value={d?.date ?? new Date().toISOString().slice(0, 10)} color={VANTA.white} />
      <WeekStrip />
      <Divider color="rgba(0,255,136,0.14)" />
      {!connected && <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.green, opacity: 0.8 }}>↳ Connect Calendar for events</div>}
      {connected && events.length === 0 && <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.textDim, fontStyle: 'italic' }}>No events today</div>}
      {connected && events.length > 0 && <SectionLabel text="NEXT UP" />}
      {events.slice(0, 3).map((ev) => (
        <div key={ev.id} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.green, minWidth: 42 }}>{ev.all_day ? 'all-day' : timeLabel(ev.start)}</span>
          <span style={{ fontSize: 11, color: VANTA.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ev.summary}</span>
        </div>
      ))}
      <div style={{ marginTop: 'auto' }}>
        <Divider color="rgba(0,255,136,0.14)" />
        <DataRow label="Last sync" value={syncLabel(state.lastUpdated)} color={VANTA.textDim} />
      </div>
    </GlassPanel>
  );
}

// ─── Finance (OMNIX placeholder, amber labels / white values) ────────────────
export function FinancePanel(): React.ReactElement {
  return (
    <GlassPanel title="Finance" accent={VANTA.amber}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <Metric value="—" color={VANTA.white} size={24} />
        <span style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.amber, textTransform: 'uppercase' }}>MRR</span>
        <span style={{ marginLeft: 'auto', fontFamily: VANTA.mono, fontSize: 8, color: VANTA.amber, letterSpacing: '0.14em' }}>OMNIX</span>
      </div>
      <DataRow label="Revenue (MTD)" value="—" color={VANTA.white} labelColor={VANTA.amber} />
      <DataRow label="Stripe" value="not linked" color={VANTA.white} labelColor={VANTA.amber} />
      <DataRow label="Runway" value="—" color={VANTA.white} labelColor={VANTA.amber} />
      <DataRow label="Burn / mo" value="—" color={VANTA.white} labelColor={VANTA.amber} />
      <DataRow label="Open invoices" value="—" color={VANTA.white} labelColor={VANTA.amber} />
      <Divider color="rgba(255,183,0,0.16)" />
      <DataRow label="Last updated" value="pending launch" color={VANTA.textDim} />
    </GlassPanel>
  );
}

// ─── System Status (connectors + voice + API) ────────────────────────────────
export function SystemStatusPanel({ connectors, voice, health }: { connectors: LiveState<ConnectorsData>; voice: LiveState<VoiceStatusData>; health: LiveState<HealthData> }): React.ReactElement {
  const conns = connectors.data?.connectors ?? [];
  const live = conns.filter((c) => c.state === 'configured' || String(c.state).includes('ready')).length;
  const total = connectors.data?.count ?? conns.length;
  const vstate = String(voice.data?.state ?? '').toLowerCase();
  const voiceLive = voice.ok && (voice.data?.listening || voice.data?.active || ['listening', 'awake', 'speaking'].includes(vstate));
  const apiOk = health.data?.status === 'ok';
  return (
    <GlassPanel title="System Status" accent={VANTA.c} more={<div style={{ paddingTop: 4 }}>{conns.slice(0, 12).map((c) => <DataRow key={c.connector} label={c.connector} value={String(c.state).replace(/_/g, ' ')} color={String(c.state) === 'configured' ? VANTA.gr : VANTA.dim} />)}</div>}>
      <Lead value={total > 0 ? `${live}/${total}` : '—'} unit="connectors" color={VANTA.c} state={connectors} />
      <DataRow label="API" value={apiOk ? 'online' : 'offline'} color={apiOk ? VANTA.gr : VANTA.rd} />
      <DataRow label="Model" value={String(health.data?.model ?? '…')} color={VANTA.text} />
      <DataRow label="Voice loop" value={voiceLive ? 'listening' : voice.ok ? 'parked' : 'off'} color={voiceLive ? VANTA.gr : VANTA.dim} />
      <DataRow label="STT" value={String(health.data?.stt_provider ?? '—')} color={VANTA.tl} />
      <DataRow label="TTS" value={String(health.data?.tts_provider ?? '—')} color={VANTA.tl} />
      <DataRow label="Last sync" value={syncLabel(connectors.lastUpdated)} color={VANTA.dim} />
    </GlassPanel>
  );
}

// ─── Tasks / Follow-ups ──────────────────────────────────────────────────────
export function TasksPanel({ memory }: { memory: LiveState<MemoryData> }): React.ReactElement {
  return (
    <GlassPanel title="Tasks / Follow-ups" accent={VANTA.pu}>
      <DataRow label="Active follow-ups" value="PA-tracked" color={VANTA.c} />
      <DataRow label="Delegation queue" value="active" color={VANTA.gr} />
      <DataRow label="Approvals pending" value="0" color={VANTA.gr} />
      <DataRow label="Trusted delegation" value="armed" color={VANTA.gr} />
      <DataRow label="Last action" value="logged" color={VANTA.text} />
      <DataRow label="Memory sync" value={memory.ok ? 'live' : '…'} color={memory.ok ? VANTA.gr : VANTA.dim} />
    </GlassPanel>
  );
}

// ─── Briefing banner ─────────────────────────────────────────────────────────
export function BriefingBanner({ state, onDismiss }: { state: LiveState<BriefingData>; onDismiss: () => void }): React.ReactElement | null {
  const d = state.data;
  if (!d?.exists || !d.markdown) return null;
  const firstLine = d.markdown.split('\n').find((l) => l.trim()) ?? 'Morning briefing ready';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 14px', margin: '0 10px', background: 'rgba(255,183,0,0.08)', border: '1px solid rgba(255,183,0,0.35)', borderRadius: 8, boxShadow: '0 0 12px rgba(255,183,0,0.12)', flexShrink: 0 }}>
      <span style={{ fontSize: 13 }}>☀️</span>
      <span style={{ fontFamily: VANTA.mono, fontSize: 10, color: VANTA.amber, letterSpacing: '0.14em' }}>BRIEFING</span>
      <span style={{ fontFamily: VANTA.mono, fontSize: 11, color: VANTA.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>{firstLine.replace(/^#+\s*/, '')}</span>
      <button onClick={onDismiss} style={{ background: 'none', border: 'none', color: VANTA.textDim, cursor: 'pointer', fontSize: 13 }}>✕</button>
    </div>
  );
}
