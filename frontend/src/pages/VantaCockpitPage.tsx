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
import { VantaChatPanel } from './vanta/VantaChatArea';
import { VantaHistoryModal, type HistItem } from './vanta/VantaHistoryModal';
import { VantaBootOverlay } from './vanta/VantaBootOverlay';
import { VantaPermissions, permissionsSeen } from './vanta/VantaPermissions';

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
  const voiceOn = voiceActive && rawState !== 'standby';
  const voiceMode: VoiceMode = !voiceActive ? 'off' : (rawState === 'listening' ? 'listening' : (rawState === 'standby' ? 'parked' : 'active'));

  // Top-bar VOICE pill (FIX 3): state-driven label + colour. The loop reports
  // active+listening while running, so we show "● LISTENING" (not "VOICE OFF").
  const VOICE_PILL: Record<string, { label: string; color: string }> = {
    listening: { label: '● LISTENING', color: '#00ff88' },
    wake_detected: { label: '● WAKE', color: '#ffffff' },
    recording: { label: '● RECORDING', color: '#00d4ff' },
    thinking: { label: '● THINKING', color: '#ff9500' },
    speaking: { label: '● SPEAKING', color: '#00ff88' },
    standby: { label: '● LISTENING', color: '#00ff88' },
  };
  const voiceActiveUi = voiceActive || sending;
  const vp = voiceActiveUi
    ? (VOICE_PILL[effState] ?? { label: '● LISTENING', color: '#00ff88' })
    : { label: '○ VOICE OFF', color: 'rgba(0,212,255,0.4)' };
  const voiceObj = { label: vp.label, color: vp.color, on: voiceActiveUi };

  // Cmd+K unified history + slide-up chat panel state.
  const [historyOpen, setHistoryOpen] = React.useState(false);
  const [typed, setTyped] = React.useState<HistItem[]>([]);
  const [chatOpen, setChatOpen] = React.useState(false);
  const [seenCount, setSeenCount] = React.useState(0);
  const historyOpenRef = React.useRef(false);
  historyOpenRef.current = historyOpen;
  const prevCountRef = React.useRef(0);
  const hideTimerRef = React.useRef<number | null>(null);

  // Auto-show the chat panel on a new message; auto-hide 30s after the last one.
  React.useEffect(() => {
    if (typed.length > prevCountRef.current) {
      prevCountRef.current = typed.length;
      setChatOpen(true);
      if (hideTimerRef.current) window.clearTimeout(hideTimerRef.current);
      hideTimerRef.current = window.setTimeout(() => setChatOpen(false), 30000);
    }
  }, [typed.length]);
  // Mark messages seen while the panel is open; unread drives the input dot.
  React.useEffect(() => { if (chatOpen) setSeenCount(typed.length); }, [chatOpen, typed.length]);
  const unread = !chatOpen && typed.length > seenCount;

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); e.stopImmediatePropagation(); setHistoryOpen((o) => !o);
      } else if (e.key === 'Escape') {
        if (historyOpenRef.current) setHistoryOpen(false);
        else setChatOpen((o) => !o);  // Esc toggles the chat panel
      }
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
      // `model` is REQUIRED by the backend's chat schema — omitting it returns
      // 422 (not 401), which is why the cockpit previously showed no reply.
      const r = await apiFetch('/v1/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: 'gpt-4o', messages, stream: false }) });
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

  // Boot overlay ("VANTA INITIALISING…" / "RECONNECTING…") + first-launch perms.
  const [everHealthy, setEverHealthy] = React.useState(false);
  React.useEffect(() => { if (serverUp) setEverHealthy(true); }, [serverUp]);
  const [showPerms, setShowPerms] = React.useState(() => !permissionsSeen());

  return (
    <div id="vanta-root" className={rootClass}>
      <VantaHudStyles />
      <VantaBackground />
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <VantaTopBar
          time={fmtClock(now)} dateStr={fmtDate(now)} serverUp={serverUp} voice={voiceObj}
        />
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
          <LeftColumn comms={comms} memory={memory} connectors={connectors} />
          <VantaOrb stateLabel={vis.label} stateColor={vis.color} readout={vis.readout} orbLabel={vis.orb} />
          <RightColumn connectors={connectors} voice={voice} health={health} calendar={calendar} voiceMode={voiceMode} />
        </div>
        <VantaBottomBar
          input={input} onInput={setInput} onSend={onSend} onMic={onMic} micActive={micActive}
          apiOk={apiOk} model={model} voiceOn={voiceOn} unread={unread}
        />
      </div>
      {/* Slide-up chat panel — sits just above the command bar, never over the orb. */}
      <VantaChatPanel messages={typed} open={chatOpen} />
      <VantaHistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} typed={typed} />
      <VantaBootOverlay healthy={serverUp} everHealthy={everHealthy} />
      <VantaPermissions open={showPerms} onClose={() => setShowPerms(false)} />
    </div>
  );
}

export default VantaCockpitPage;
