// VantaCockpitPage — VANTA Neural Command Center, a faithful port of the
// jarvis_hud reference. Scoped under #vanta-root. All panel data is polled live
// from the backend (intervals match the reference).

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

const I = { voice: 5_000, system: 30_000, memory: 60_000, comms: 120_000, calendar: 300_000, weather: 1_800_000 } as const;

const STATES = [
  { cls: '', lbl: 'READY', lc: '#00FF88', rd: '> SYSTEM NOMINAL · ALL GATES CLEAR' },
  { cls: 'sp', lbl: 'PROCESSING', lc: '#00D4FF', rd: '> ROUTING QUERY → COS/GM · DISPATCHING' },
  { cls: 'sa', lbl: 'ANALYZING', lc: '#FF9500', rd: '> ANALYZING INPUTS · CONFIDENCE NOMINAL' },
] as const;

function deriveVoiceMode(v: VoiceStatusData | null, ok: boolean): VoiceMode {
  if (!ok || !v) return 'off';
  const ready = String(v.voice_readiness ?? '').toUpperCase();
  const s = String(v.state ?? '').toLowerCase();
  if (ready === 'RUNTIME_STARTED' || ready === 'READY' || s === 'speaking' || s === 'thinking' || v.active) return 'active';
  if (v.listening || s === 'listening' || s === 'awake') return 'listening';
  return 'parked';
}
function parseTemp(text: string | undefined): string {
  const m = (text ?? '').match(/([+-]?\d+°C)/);
  return m ? m[1] : '';
}

export function VantaCockpitPage(): React.ReactElement {
  const health = useLivePanel<HealthData>('/health', I.system);
  const voice = useLivePanel<VoiceStatusData>('/v1/voice/status', I.voice);
  const weather = useLivePanel<WeatherData>('/v1/weather', I.weather);
  const comms = useLivePanel<CommsData>('/v1/comms/recent', I.comms);
  const calendar = useLivePanel<CalendarData>('/v1/calendar/today', I.calendar);
  const memory = useLivePanel<MemoryData>('/v1/memory/status', I.memory);
  const connectors = useLivePanel<ConnectorsData>('/v1/connectors/status', I.system);

  // clock
  const [time, setTime] = React.useState(() => new Date().toTimeString().slice(0, 8));
  React.useEffect(() => { const t = window.setInterval(() => setTime(new Date().toTimeString().slice(0, 8)), 1000); return () => window.clearInterval(t); }, []);

  // state cycle (real send overrides)
  const [si, setSi] = React.useState(0);
  const [sending, setSending] = React.useState(false);
  React.useEffect(() => { const t = window.setInterval(() => setSi((s) => (s + 1) % STATES.length), 9000); return () => window.clearInterval(t); }, []);
  const st = sending ? STATES[1] : STATES[si];

  // ambient hum + click cue (armed on first click)
  React.useEffect(() => {
    let ctx: AudioContext | null = null;
    const onClick = () => {
      if (!ctx) {
        try {
          const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          ctx = new AC();
          const o = ctx.createOscillator(), g = ctx.createGain();
          o.frequency.value = 55; o.type = 'sine'; g.gain.value = 0.022; o.connect(g).connect(ctx.destination); o.start();
        } catch { return; }
      }
      try {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = 1100; o.type = 'square'; g.gain.setValueAtTime(0.06, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.09); o.connect(g).connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.09);
      } catch { /* ignore */ }
    };
    window.addEventListener('click', onClick, { passive: true });
    return () => window.removeEventListener('click', onClick);
  }, []);

  // derived
  const voiceMode = deriveVoiceMode(voice.data, voice.ok);
  const voiceOn = voiceMode === 'listening' || voiceMode === 'active';
  const apiOk = health.data?.status === 'ok';
  const model = String(health.data?.model ?? '—');
  const conns = connectors.data?.connectors ?? [];
  const liveC = conns.filter((c) => c.state === 'configured' || String(c.state).includes('ready')).length;
  const totalC = connectors.data?.count ?? conns.length;
  const connText = totalC > 0 ? `${liveC}/${totalC}` : '—';
  const temp = parseTemp(weather.data?.text);
  const weatherText = weather.ok && temp ? `${temp} · SGT` : 'SGT';
  const voiceText = voiceOn ? '● LISTENING' : '○ VOICE OFF';
  const voiceColor = voiceOn ? 'var(--gr)' : 'var(--dim)';

  // unified history: Cmd+K modal + cockpit session's typed turns
  const [historyOpen, setHistoryOpen] = React.useState(false);
  const [typed, setTyped] = React.useState<HistItem[]>([]);
  React.useEffect(() => {
    // Capture phase + stopImmediatePropagation so the cockpit's unified history
    // modal opens on Cmd+K instead of the app-wide text-fallback viewer. The
    // global Cmd+K still works on every other page (this listener is scoped to
    // the cockpit's lifetime).
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        e.stopImmediatePropagation();
        setHistoryOpen((o) => !o);
      } else if (e.key === 'Escape') {
        setHistoryOpen(false);
      }
    };
    window.addEventListener('keydown', onKey, { capture: true });
    return () => window.removeEventListener('keydown', onKey, { capture: true });
  }, []);

  const [input, setInput] = React.useState('');
  const onSend = React.useCallback(async () => {
    const text = input.trim(); if (!text) return;
    setInput(''); setSending(true);
    setTyped((h) => [...h, { ts: Date.now() / 1000, speaker: 'you', text, mode: 'typed' }]);
    try {
      const r = await apiFetch('/v1/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: [{ role: 'user', content: text }], stream: false }) });
      if (r.ok) {
        const j = await r.json();
        const reply = (((j.choices || [])[0] || {}).message || {}).content;
        if (reply) setTyped((h) => [...h, { ts: Date.now() / 1000, speaker: 'vanta', text: String(reply), mode: 'typed' }]);
      }
    } catch { /* surfaced via state */ }
    finally { window.setTimeout(() => setSending(false), 2500); }
  }, [input]);

  const [micActive, setMicActive] = React.useState(false);
  const onMic = React.useCallback(() => { setMicActive(true); window.setTimeout(() => setMicActive(false), 3000); }, []);

  return (
    <div id="vanta-root" className={st.cls}>
      <VantaHudStyles />
      <VantaBackground />
      <VantaTopBar time={time} weatherText={weatherText} voiceText={voiceText} voiceColor={voiceColor} />
      <div id="app">
        <LeftColumn comms={comms} memory={memory} />
        <VantaOrb stateLabel={st.lbl} stateColor={st.lc} readout={st.rd} />
        <RightColumn connectors={connectors} voice={voice} health={health} calendar={calendar} voiceMode={voiceMode} />
      </div>
      <VantaBottomBar input={input} onInput={setInput} onSend={onSend} onMic={onMic} micActive={micActive} apiOk={!!apiOk} connText={connText} model={model} voiceOn={voiceOn} />
      <VantaHistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} typed={typed} />
    </div>
  );
}

export default VantaCockpitPage;
