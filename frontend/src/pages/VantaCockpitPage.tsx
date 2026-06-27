// VantaCockpitPage — VANTA Voice Intelligence System cockpit. A faithful port of
// the VANTA-export_dc.html reference design, with every panel wired to live
// backend data (poll intervals match the spec). Scoped under #vanta-root so the
// HUD styling never leaks into the rest of the app.

import React from 'react';
import { useLivePanel } from '../lib/useLivePanel';
import { apiFetch } from '../lib/api';
import type {
  WeatherData, CommsData, CalendarData, MemoryData,
  VoiceStatusData, HealthData, ConnectorsData, VoiceMode,
} from './vanta/vanta-kit';
import { VantaHudStyles } from './vanta/vanta-hud-styles';
import { VantaBackground } from './vanta/VantaBackground';
import { VantaTopBar } from './vanta/VantaTopBar';
import { VantaBottomBar } from './vanta/VantaBottomBar';
import { VantaOrb } from './vanta/VantaOrb';
import { LeftColumn, RightColumn } from './vanta/VantaPanels';
import { VantaHistoryModal, type HistItem } from './vanta/VantaHistoryModal';

// Poll intervals (ms) — match the task spec.
const I = {
  health: 30_000, voiceState: 2_000, voiceStatus: 5_000, connectors: 30_000,
  comms: 120_000, memory: 60_000, calendar: 300_000, weather: 1_800_000,
} as const;

interface Vis { cls: string; label: string; color: string; readout: string; orb: string; wave: boolean }
const VIS: Record<string, Vis> = {
  idle: { cls: '', label: 'READY', color: '#00ff88', readout: '> SYSTEM NOMINAL', orb: 'READY', wave: false },
  standby: { cls: 'v-standby', label: 'STANDBY', color: '#4a6080', readout: '> VOICE STANDBY', orb: 'STANDBY', wave: false },
  listening: { cls: 'v-listening', label: 'LISTENING', color: '#00d4ff', readout: '> LISTENING FOR "HEY VANTA"', orb: 'LISTENING', wave: true },
  wake_detected: { cls: 'v-wake', label: 'WAKE DETECTED', color: '#ffffff', readout: '> WAKE DETECTED', orb: 'WAKE', wave: true },
  recording: { cls: 'v-recording', label: 'RECORDING', color: '#00ff88', readout: '> RECORDING…', orb: 'RECORDING', wave: true },
  thinking: { cls: 'v-thinking', label: 'THINKING', color: '#ff9500', readout: '> THINKING…', orb: 'THINKING', wave: true },
  speaking: { cls: 'v-speaking', label: 'SPEAKING', color: '#00ff88', readout: '> SPEAKING', orb: 'SPEAKING', wave: true },
};

interface VoiceUx { active: boolean; state: string }

function fmtClock(d: Date): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(d);
}
function fmtDate(d: Date): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }).format(d).toUpperCase().replace(/,/g, '');
}

export function VantaCockpitPage(): React.ReactElement {
  const health = useLivePanel<HealthData>('/health', I.health);
  const voice = useLivePanel<VoiceStatusData>('/v1/voice/status', I.voiceStatus);
  const voiceUx = useLivePanel<VoiceUx>('/v1/voice/state', I.voiceState);
  const comms = useLivePanel<CommsData>('/v1/comms/recent', I.comms);
  const calendar = useLivePanel<CalendarData>('/v1/calendar/today', I.calendar);
  const memory = useLivePanel<MemoryData>('/v1/memory/status', I.memory);
  const connectors = useLivePanel<ConnectorsData>('/v1/connectors/status', I.connectors);
  useLivePanel<WeatherData>('/v1/weather', I.weather); // kept warm for parity; not shown in this layout

  // Live SGT clock + date (ticks every second).
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 1000); return () => window.clearInterval(t); }, []);

  // Orb / indicator state driven by real voice state; a typed send overrides to thinking.
  const [sending, setSending] = React.useState(false);
  const voiceActive = voiceUx.ok && !!voiceUx.data?.active;
  const rawState = voiceActive ? String(voiceUx.data?.state ?? 'standby') : 'idle';
  const effState = sending ? 'thinking' : rawState;
  const vis = VIS[effState] ?? VIS.idle;
  const rootClass = `${vis.cls}${vis.wave ? '' : ' v-static-wave'}`;

  // Derived status.
  const serverUp = health.ok;
  const apiOk = serverUp && (health.data?.status === 'ok' || health.data?.status === undefined ? true : false);
  const model = String(health.data?.model ?? '—');
  const voiceStateText = (sending ? 'THINKING' : rawState).toUpperCase().replace(/_/g, ' ');
  const voiceOn = voiceActive && rawState !== 'standby';
  const voiceMode: VoiceMode = !voiceActive ? 'off' : (rawState === 'listening' ? 'listening' : (rawState === 'standby' ? 'parked' : 'active'));

  // Cmd+K unified history (capture phase so the cockpit's modal wins over the global viewer).
  const [historyOpen, setHistoryOpen] = React.useState(false);
  const [typed, setTyped] = React.useState<HistItem[]>([]);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); e.stopImmediatePropagation(); setHistoryOpen((o) => !o);
      } else if (e.key === 'Escape') { setHistoryOpen(false); }
    };
    window.addEventListener('keydown', onKey, { capture: true });
    return () => window.removeEventListener('keydown', onKey, { capture: true });
  }, []);

  // Command input → same chat endpoint, with last-20-turn context.
  const [input, setInput] = React.useState('');
  const onSend = React.useCallback(async () => {
    const text = input.trim(); if (!text) return;
    setInput(''); setSending(true);
    setTyped((h) => [...h, { ts: Date.now() / 1000, speaker: 'you', text, mode: 'typed' }]);
    const history = typed.slice(-40).map((t) => ({ role: t.speaker === 'you' ? 'user' : 'assistant', content: t.text }));
    const messages = [...history, { role: 'user', content: text }];
    try {
      const r = await apiFetch('/v1/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages, stream: false }) });
      if (r.ok) {
        const j = await r.json();
        const reply = (((j.choices || [])[0] || {}).message || {}).content;
        if (reply) setTyped((h) => [...h, { ts: Date.now() / 1000, speaker: 'vanta', text: String(reply), mode: 'typed' }]);
      }
    } catch { /* surfaced via state */ }
    finally { window.setTimeout(() => setSending(false), 2500); }
  }, [input, typed]);

  // Mic = push-to-talk: start one manual voice turn.
  const [micActive, setMicActive] = React.useState(false);
  const onMic = React.useCallback(() => {
    setMicActive(true);
    void apiFetch('/v1/voice/turn/start', { method: 'POST' }).catch(() => {});
    window.setTimeout(() => setMicActive(false), 3000);
  }, []);

  return (
    <div id="vanta-root" className={rootClass}>
      <VantaHudStyles />
      <VantaBackground />
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <VantaTopBar
          time={fmtClock(now)} dateStr={fmtDate(now)} serverUp={serverUp}
          voiceActive={voiceActive || sending} voiceStateText={voiceStateText}
        />
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
          <LeftColumn comms={comms} memory={memory} connectors={connectors} />
          <VantaOrb stateLabel={vis.label} stateColor={vis.color} readout={vis.readout} orbLabel={vis.orb} />
          <RightColumn connectors={connectors} voice={voice} health={health} calendar={calendar} voiceMode={voiceMode} />
        </div>
        <VantaBottomBar
          input={input} onInput={setInput} onSend={onSend} onMic={onMic} micActive={micActive}
          apiOk={apiOk} model={model} voiceOn={voiceOn}
        />
      </div>
      <VantaHistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} typed={typed} />
    </div>
  );
}

export default VantaCockpitPage;
