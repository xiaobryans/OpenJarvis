// VantaPanels — the six reference .hud panels (Comms / Memory OS / Tasks left;
// System Status / Calendar / Finance right), fed by live polled data.

import React from 'react';
import type { LiveState } from '../../lib/useLivePanel';
import type { CommsData, MemoryData, CalendarData, VoiceStatusData, HealthData, ConnectorsData, VoiceMode } from './vanta-kit';

function Row({ k, v, cls }: { k: string; v: React.ReactNode; cls?: string }): React.ReactElement {
  return <div className="hr"><span className="k">{k}</span><span className={`v ${cls ?? ''}`}>{v}</span></div>;
}
function evTime(iso: string | null): string {
  if (!iso) return '—';
  try { return new Intl.DateTimeFormat('en-SG', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso)); } catch { return '—'; }
}

export function LeftColumn({ comms, memory }: { comms: LiveState<CommsData>; memory: LiveState<MemoryData> }): React.ReactElement {
  const cd = comms.data;
  const connected = cd?.connected ?? false;
  const unread = connected ? (cd?.unread_count ?? 0) : '—';
  const flagged = connected ? (cd?.messages.filter((m) => m.unread).length ?? 0) : '—';
  const md = memory.data;
  const entries = typeof md?.total_entries === 'number' ? md.total_entries : '—';
  const synced = md?.cloud_sync?.synced;

  return (
    <div className="col">
      <div className="hud" style={{ flex: 2 }}>
        <div className="htop"><span className="ht">COMMUNICATIONS</span><span className="dot dg" /></div>
        <Row k="UNREAD" v={unread} cls="vc" />
        <Row k="INBOX" v={connected ? 'active' : 'offline'} cls={connected ? 'vg' : ''} />
        <Row k="FLAGGED" v={flagged} />
        <div className="hdv" />
        <Row k="GMAIL" v={connected ? 'connected' : 'offline'} cls={connected ? 'vg' : 'vr'} />
        <Row k="SLACK" v="ready" cls="vg" />
        <Row k="TELEGRAM" v="ready" cls="vg" />
      </div>

      <div className="hud" style={{ flex: 1.5 }}>
        <div className="htop"><span className="ht">MEMORY OS</span><span className="dot da" /></div>
        <div className="bv">{entries}</div>
        <div className="bl">ENTRIES</div>
        <div className="mw">
          <div className="ml"><span>CLOUD SYNC</span><span className="va">{synced === undefined ? '…' : synced ? 'live' : 'pending'}</span></div>
          <div className="mb"><div className="mf mfa" style={{ width: synced ? '100%' : '60%' }} /></div>
        </div>
        <Row k="STORE" v="active" cls="vg" />
        <Row k="FOLLOW-UPS" v="PA-tracked" />
      </div>

      <div className="hud" style={{ flex: 2 }}>
        <div className="htop"><span className="ht">TASKS / FOLLOW-UPS</span><span className="dot dg" /></div>
        <Row k="CENTER" v="PA-tracked" />
        <Row k="ACTIVE" v="tracked" cls="vg" />
        <Row k="DELEGATION" v="LIVE" cls="vg" />
        <Row k="QUEUE" v="0" cls="vc" />
        <div className="hdv" />
        <Row k="CONFIDENCE" v="nominal" cls="vg" />
        <Row k="NAMESPACES" v="unified" cls="vc" />
      </div>
    </div>
  );
}

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
    <div className="col">
      <div className="hud" style={{ flex: 1.5 }}>
        <div className="htop"><span className="ht">SYSTEM STATUS</span><span className={`dot ${apiOk ? 'dg' : 'dr'}`} /></div>
        <Row k="API" v={apiOk ? 'OK' : 'DOWN'} cls={apiOk ? 'vg' : 'vr'} />
        <Row k="MODEL" v={model} cls="vc" />
        <Row k="CONNECTORS" v={total > 0 ? `${live}/${total} live` : '—'} />
        <Row k="VOICE" v={voiceMode} cls={voiceMode === 'listening' || voiceMode === 'active' ? 'vg' : ''} />
        <Row k="STT / TTS" v={`${health.data?.stt_provider ?? '—'} / ${health.data?.tts_provider ?? '—'}`} cls="vc" />
      </div>

      <div className="hud" style={{ flex: 2 }}>
        <div className="htop"><span className="ht">CALENDAR — TODAY</span><span className="dot dg" /></div>
        <Row k="DATE" v={today} cls="vc" />
        <Row k="EVENTS" v={calConnected ? `${events.length} events` : 'offline'} />
        <div className="hdv" />
        <div id="evlist" className="sn">
          {!calConnected && <span style={{ color: 'var(--dim)' }}>↳ Connect Calendar</span>}
          {calConnected && events.length === 0 && <span style={{ color: 'var(--dim)' }}>No events today</span>}
          {events.slice(0, 4).map((e) => (
            <div className="hr" key={e.id}><span className="k">{e.all_day ? 'all-day' : evTime(e.start)}</span><span className="v" style={{ fontSize: 9, maxWidth: 130 }}>{e.summary}</span></div>
          ))}
        </div>
      </div>

      <div className="hud" style={{ flex: 2 }}>
        <div className="htop"><span className="ht">FINANCE</span><span className="dot da" /></div>
        <Row k="MRR" v="—" cls="va" />
        <Row k="REVENUE MTD" v="—" />
        <Row k="STRIPE" v="not linked" cls="va" />
        <Row k="RUNWAY" v="—" />
        <div className="hdv" />
        <div className="sn">Stripe connects when OMNIX launches.</div>
        <div className="al" style={{ marginTop: 6 }}>Awaiting Stripe integration</div>
      </div>
    </div>
  );
}
