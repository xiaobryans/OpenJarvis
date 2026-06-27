// VantaPanels — left column (Mission Control / Communications / Memory OS) and
// right column (System Status / Calendar / Connectors / Finance). Faithful port
// of VANTA-export_dc.html, fed by live polled backend data.

import React from 'react';
import type { LiveState } from '../../lib/useLivePanel';
import type { CommsData, MemoryData, CalendarData, VoiceStatusData, HealthData, ConnectorsData, VoiceMode } from './vanta-kit';

// ─── Shared primitives ───────────────────────────────────────────────────────
function Panel({ title, titleColor, borderColor, corner, children }: {
  title: string; titleColor: string; borderColor: string; corner?: 'tl' | 'tr'; children: React.ReactNode;
}): React.ReactElement {
  return (
    <div style={{ background: 'rgba(2,12,28,0.9)', border: `1px solid ${borderColor}`, borderRadius: 6, padding: 12, flexShrink: 0, position: 'relative', overflow: 'hidden' }}>
      {corner === 'tr' && <div style={{ position: 'absolute', top: 0, right: 0, width: 18, height: 18, borderBottom: '1px solid rgba(0,212,255,0.12)', borderLeft: '1px solid rgba(0,212,255,0.12)', borderBottomLeftRadius: 4 }} />}
      {corner === 'tl' && <div style={{ position: 'absolute', top: 0, left: 0, width: 18, height: 18, borderBottom: '1px solid rgba(0,212,255,0.12)', borderRight: '1px solid rgba(0,212,255,0.12)', borderBottomRightRadius: 4 }} />}
      <div style={{ fontSize: 8, letterSpacing: '2px', color: titleColor, textTransform: 'uppercase', marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function Row({ k, v, vColor = '#8ec8e8' }: { k: string; v: React.ReactNode; vColor?: string }): React.ReactElement {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: 9, lineHeight: 1.9, gap: 6 }}>
      <span style={{ color: 'rgba(142,200,232,0.45)', whiteSpace: 'nowrap' }}>{k}</span>
      <span style={{ color: vColor, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'right' }}>{v}</span>
    </div>
  );
}

function evTime(iso: string | null): string {
  if (!iso) return '—';
  try { return new Intl.DateTimeFormat('en-SG', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso)); } catch { return '—'; }
}

// ─── Mission Control (static VANTA sprint roadmap) ───────────────────────────
interface Mission { name: string; pct: number; status: string; color: string }
const MISSIONS: Mission[] = [
  { name: 'S1 · Voice Pipeline', pct: 95, status: 'active', color: '#00FF88' },
  { name: 'S2 · Daily Impact', pct: 80, status: 'active', color: '#00FF88' },
  { name: 'S3 · Business Ops', pct: 80, status: 'active', color: '#00FF88' },
  { name: 'S4 · Stage 4 Intel', pct: 60, status: 'in progress', color: '#00d4ff' },
  { name: 'S5 · iOS & Mobile', pct: 0, status: 'pending', color: '#00d4ff' },
];

function MissionRow({ m }: { m: Mission }): React.ReactElement {
  const active = m.pct > 0;
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
        <span style={{ fontSize: 8.5, color: 'rgba(142,200,232,0.72)', letterSpacing: '0.5px' }}>{m.name}</span>
        <span style={{ fontSize: 8, color: active ? m.color : 'rgba(0,212,255,0.4)', letterSpacing: '1px', textTransform: 'uppercase' }}>{m.pct}% {m.status}</span>
      </div>
      <div style={{ height: 3, background: 'rgba(0,180,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${m.pct}%`, height: '100%', background: `linear-gradient(90deg,${m.color},${m.color}99)`, boxShadow: active ? `0 0 6px ${m.color}` : 'none', borderRadius: 2, transition: 'width 1.2s ease' }} />
      </div>
    </div>
  );
}

// ─── Left column ─────────────────────────────────────────────────────────────
export function LeftColumn({ comms, memory, connectors }: {
  comms: LiveState<CommsData>; memory: LiveState<MemoryData>; connectors: LiveState<ConnectorsData>;
}): React.ReactElement {
  const cd = comms.data;
  const connected = cd?.connected ?? false;
  const unread = connected ? (cd?.unread_count ?? 0) : '—';

  const conns = connectors.data?.connectors ?? [];
  const isConn = (name: string): boolean => conns.some((c) => c.connector.toLowerCase().includes(name) && (c.state === 'configured' || String(c.state).includes('ready')));
  const slackOn = isConn('slack');
  const tgOn = isConn('telegram');

  const md = memory.data;
  const entries = typeof md?.total_entries === 'number' ? md.total_entries : '—';
  const synced = md?.cloud_sync?.synced;
  const followUps = typeof (md?.follow_ups as number | undefined) === 'number' ? (md?.follow_ups as number) : 'PA-tracked';

  return (
    <div style={{ width: 248, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 6, padding: 8, overflowY: 'auto', borderRight: '1px solid rgba(0,212,255,0.07)', background: 'rgba(0,4,14,0.28)' }}>
      {/* Mission Control */}
      <div style={{ background: 'rgba(2,12,28,0.9)', border: '1px solid rgba(0,212,255,0.13)', borderRadius: 6, padding: 12, flexShrink: 0, position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, right: 0, width: 18, height: 18, borderBottom: '1px solid rgba(0,212,255,0.12)', borderLeft: '1px solid rgba(0,212,255,0.12)', borderBottomLeftRadius: 4 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid rgba(0,212,255,0.07)' }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#00d4ff', boxShadow: '0 0 6px #00d4ff', flexShrink: 0, animation: 'vStatusPulse 2s ease-in-out infinite' }} />
          <span style={{ fontSize: 8, letterSpacing: '2px', color: 'rgba(0,212,255,0.6)', textTransform: 'uppercase' }}>Mission Control</span>
        </div>
        {MISSIONS.map((m) => <MissionRow key={m.name} m={m} />)}
      </div>

      {/* Communications */}
      <Panel title="Communications" titleColor="rgba(0,212,255,0.6)" borderColor="rgba(0,212,255,0.13)" corner="tl">
        <Row k="UNREAD" v={unread} vColor="#00d4ff" />
        <Row k="GMAIL" v={connected ? 'connected' : 'offline'} vColor={connected ? '#00FF88' : '#FF3355'} />
        <Row k="SLACK" v={slackOn ? 'connected' : 'ready'} vColor={slackOn ? '#00FF88' : 'rgba(0,212,255,0.6)'} />
        <Row k="TELEGRAM" v={tgOn ? 'connected' : 'ready'} vColor={tgOn ? '#00FF88' : 'rgba(0,212,255,0.6)'} />
      </Panel>

      {/* Memory OS */}
      <Panel title="Memory OS" titleColor="rgba(124,58,237,0.7)" borderColor="rgba(124,58,237,0.2)">
        <div style={{ fontFamily: "'Exo 2',sans-serif", fontSize: 24, fontWeight: 700, color: '#bd60ff', lineHeight: 1, marginTop: 2, textShadow: '0 0 18px rgba(124,58,237,0.5)' }}>{entries}</div>
        <div style={{ fontSize: 7, letterSpacing: '3px', color: 'rgba(124,58,237,0.45)', marginBottom: 8, textTransform: 'uppercase' }}>Entries</div>
        <Row k="STORE" v={memory.ok ? 'active' : 'offline'} vColor={memory.ok ? '#00FF88' : '#FF3355'} />
        <Row k="FOLLOW-UPS" v={followUps} />
        <Row k="CLOUD SYNC" v={synced === undefined ? '…' : synced ? 'live' : 'pending'} vColor={synced ? '#00FF88' : 'rgba(255,149,0,0.8)'} />
      </Panel>
    </div>
  );
}

// ─── Right column ────────────────────────────────────────────────────────────
export function RightColumn({ connectors, voice, health, calendar, voiceMode }: {
  connectors: LiveState<ConnectorsData>; voice: LiveState<VoiceStatusData>; health: LiveState<HealthData>;
  calendar: LiveState<CalendarData>; voiceMode: VoiceMode;
}): React.ReactElement {
  const conns = connectors.data?.connectors ?? [];
  const live = conns.filter((c) => c.state === 'configured' || String(c.state).includes('ready')).length;
  const total = connectors.data?.count ?? conns.length;
  const apiOk = health.data?.status === 'ok';
  const model = String(health.data?.model ?? '—');
  const cal = calendar.data;
  const calConnected = cal?.connected ?? false;
  const events = cal?.events ?? [];
  const today = new Intl.DateTimeFormat('en-SG', { timeZone: 'Asia/Singapore', weekday: 'short', day: 'numeric', month: 'short' }).format(new Date());

  return (
    <div style={{ width: 248, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 6, padding: 8, overflowY: 'auto', borderLeft: '1px solid rgba(0,212,255,0.07)', background: 'rgba(0,4,14,0.28)' }}>
      {/* System Status */}
      <Panel title="System Status" titleColor="rgba(0,212,255,0.6)" borderColor="rgba(0,212,255,0.13)" corner="tr">
        <Row k="API" v={apiOk ? 'OK' : 'DOWN'} vColor={apiOk ? '#00FF88' : '#FF3355'} />
        <Row k="MODEL" v={model} vColor="#00d4ff" />
        <Row k="CONNECTORS" v={total > 0 ? `${live}/${total} live` : '—'} />
        <Row k="VOICE" v={voiceMode} vColor={voiceMode === 'listening' || voiceMode === 'active' ? '#00FF88' : 'rgba(142,200,232,0.6)'} />
        <Row k="STT / TTS" v={`${health.data?.stt_provider ?? '—'} / ${health.data?.tts_provider ?? '—'}`} vColor="#00d4ff" />
      </Panel>

      {/* Calendar */}
      <Panel title="Calendar — Today" titleColor="rgba(16,185,129,0.6)" borderColor="rgba(16,185,129,0.2)">
        <Row k="DATE" v={today} vColor="#00d4ff" />
        <Row k="EVENTS" v={calConnected ? `${events.length}` : 'offline'} vColor={calConnected ? '#10b981' : '#FF3355'} />
        <div style={{ height: 1, background: 'rgba(16,185,129,0.12)', margin: '6px 0' }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {!calConnected && <span style={{ fontSize: 9, color: 'rgba(16,185,129,0.45)' }}>↳ Connect Calendar</span>}
          {calConnected && events.length === 0 && <span style={{ fontSize: 9, color: 'rgba(16,185,129,0.45)' }}>No events today</span>}
          {events.slice(0, 4).map((e) => (
            <div key={e.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 6, fontSize: 9 }}>
              <span style={{ color: 'rgba(16,185,129,0.7)', whiteSpace: 'nowrap' }}>{e.all_day ? 'all-day' : evTime(e.start)}</span>
              <span style={{ color: '#8ec8e8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 140, textAlign: 'right' }}>{e.summary}</span>
            </div>
          ))}
        </div>
      </Panel>

      {/* Connectors */}
      <Panel title="Connectors" titleColor="rgba(0,212,255,0.6)" borderColor="rgba(0,212,255,0.13)">
        <Row k="LIVE" v={total > 0 ? `${live}/${total}` : '—'} vColor="#00d4ff" />
        <div style={{ height: 1, background: 'rgba(0,180,255,0.1)', margin: '6px 0' }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 120, overflowY: 'auto' }}>
          {conns.length === 0 && <span style={{ fontSize: 9, color: 'rgba(0,212,255,0.35)' }}>No connectors</span>}
          {/* FIX 4: show connected connectors first so Gmail/Calendar/Slack/Weather
              are visible instead of being buried below not_configured entries. */}
          {[...conns]
            .map((c) => ({ c, on: c.state === 'configured' || String(c.state).includes('ready') }))
            .sort((a, b) => Number(b.on) - Number(a.on))
            .slice(0, 10)
            .map(({ c, on }) => (
              <Row key={c.connector} k={c.connector.toUpperCase()} v={on ? 'connected' : String(c.state)} vColor={on ? '#00FF88' : 'rgba(255,149,0,0.8)'} />
            ))}
        </div>
      </Panel>

      {/* Finance (static placeholder) */}
      <div style={{ background: 'rgba(2,12,28,0.9)', border: '1px solid rgba(255,149,0,0.15)', borderRadius: 6, padding: 12, flexShrink: 0 }}>
        <div style={{ fontSize: 8, letterSpacing: '2px', color: 'rgba(255,149,0,0.5)', textTransform: 'uppercase', marginBottom: 8 }}>Finance</div>
        <div style={{ fontSize: 9, color: 'rgba(255,149,0,0.35)', lineHeight: 1.8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>MRR</span><span>—</span></div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>STRIPE</span><span style={{ color: 'rgba(255,149,0,0.5)' }}>not linked</span></div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>RUNWAY</span><span>—</span></div>
        </div>
        <div style={{ marginTop: 8, fontSize: 8, color: 'rgba(255,149,0,0.3)', fontStyle: 'italic' }}>Stripe connects when OMNIX launches.</div>
      </div>
    </div>
  );
}
