// VantaCockpitPage — VANTA Neural Command Center, matching the jarvis_hud
// reference. Single page, no scroll. Background field + orb + 6 live panels +
// HUD top/bottom bars. All panel data is polled live (Task A intervals).

import React from 'react';
import { useLivePanel } from '../lib/useLivePanel';
import { apiFetch } from '../lib/api';
import {
  VANTA, VantaKeyframes,
  type SystemState, type VoiceMode,
  type WeatherData, type CommsData, type CalendarData, type MemoryData,
  type VoiceStatusData, type BriefingData, type HealthData, type ConnectorsData,
} from './vanta/vanta-kit';
import { VantaBackground } from './vanta/VantaBackground';
import { VantaTopBar } from './vanta/VantaTopBar';
import { VantaBottomBar } from './vanta/VantaBottomBar';
import { VantaOrb } from './vanta/VantaOrb';
import { CommsPanel, MemoryPanel, TasksPanel, SystemStatusPanel, CalendarPanel, FinancePanel, BriefingBanner } from './vanta/VantaPanels';

const I = { voice: 5_000, system: 10_000, connectors: 30_000, memory: 60_000, comms: 120_000, calendar: 300_000, weather: 1_800_000, briefing: 3_600_000 } as const;

function deriveVoiceMode(v: VoiceStatusData | null, ok: boolean): VoiceMode {
  if (!ok || !v) return 'off';
  const s = String(v.state ?? '').toLowerCase();
  if (s === 'speaking' || s === 'thinking' || s === 'transcribing' || v.active) return 'active';
  if (v.listening || s === 'listening' || s === 'awake') return 'listening';
  return 'parked';
}

// Lightweight ambient hum + click cue (WebAudio), armed on first user gesture.
function useHudAudio(): { arm: () => void; click: () => void } {
  const ctxRef = React.useRef<AudioContext | null>(null);
  const arm = React.useCallback(() => {
    if (ctxRef.current) return;
    try {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AC();
      ctxRef.current = ctx;
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.type = 'sine'; osc.frequency.value = 56; gain.gain.value = 0.015;
      const osc2 = ctx.createOscillator(); osc2.type = 'sine'; osc2.frequency.value = 84;
      const gain2 = ctx.createGain(); gain2.gain.value = 0.008;
      osc.connect(gain).connect(ctx.destination); osc2.connect(gain2).connect(ctx.destination);
      osc.start(); osc2.start();
    } catch { /* audio unavailable — silent */ }
  }, []);
  const click = React.useCallback(() => {
    const ctx = ctxRef.current; if (!ctx) return;
    try {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'triangle'; o.frequency.value = 660; g.gain.value = 0.05;
      o.connect(g).connect(ctx.destination); o.start();
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.09); o.stop(ctx.currentTime + 0.1);
    } catch { /* ignore */ }
  }, []);
  return { arm, click };
}

export function VantaCockpitPage(): React.ReactElement {
  const health = useLivePanel<HealthData>('/health', I.system);
  const voice = useLivePanel<VoiceStatusData>('/v1/voice/status', I.voice);
  const weather = useLivePanel<WeatherData>('/v1/weather', I.weather);
  const comms = useLivePanel<CommsData>('/v1/comms/recent', I.comms);
  const calendar = useLivePanel<CalendarData>('/v1/calendar/today', I.calendar);
  const memory = useLivePanel<MemoryData>('/v1/memory/status', I.memory);
  const connectors = useLivePanel<ConnectorsData>('/v1/connectors/status', I.connectors);
  const briefing = useLivePanel<BriefingData>('/v1/briefing/latest', I.briefing);

  const [input, setInput] = React.useState('');
  const [sending, setSending] = React.useState(false);
  const [micHeld, setMicHeld] = React.useState(false);
  const [briefingDismissed, setBriefingDismissed] = React.useState(false);
  const audio = useHudAudio();

  const voiceMode = micHeld ? 'active' : deriveVoiceMode(voice.data, voice.ok);
  const systemState: SystemState = React.useMemo(() => {
    if (sending) return 'processing';
    if (String(voice.data?.state ?? '').toLowerCase() === 'speaking') return 'speaking';
    if (health.data && health.data.status !== 'ok') return 'error';
    return 'idle';
  }, [sending, voice.data, health.data]);

  const onSend = React.useCallback(async () => {
    const text = input.trim(); if (!text || sending) return;
    audio.click(); setSending(true);
    try {
      await apiFetch('/v1/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: [{ role: 'user', content: text }], stream: false }) });
      setInput('');
    } catch { /* surfaced via system state */ } finally { setSending(false); }
  }, [input, sending, audio]);

  return (
    <div onPointerDown={audio.arm} style={{ position: 'relative', height: '100%', width: '100%', background: VANTA.bg, color: VANTA.text, display: 'flex', flexDirection: 'column', overflow: 'hidden', fontFamily: VANTA.mono }}>
      <VantaKeyframes />
      <VantaBackground />

      <VantaTopBar systemState={systemState} voiceMode={voiceMode} weather={weather.data} health={health.data} />

      {!briefingDismissed && <div style={{ position: 'relative', zIndex: 2, paddingTop: 8 }}><BriefingBanner state={briefing} onDismiss={() => { audio.click(); setBriefingDismissed(true); }} /></div>}

      {/* body: left · orb · right */}
      <div style={{ position: 'relative', zIndex: 1, flex: 1, display: 'grid', gridTemplateColumns: '248px 1fr 248px', gap: 10, padding: 10, minHeight: 0 }}>
        <div style={{ display: 'grid', gridTemplateRows: '1.15fr 1fr 0.9fr', gap: 10, minHeight: 0 }}>
          <CommsPanel state={comms} />
          <MemoryPanel state={memory} />
          <TasksPanel memory={memory} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 0, minHeight: 0, overflow: 'hidden' }}>
          <VantaOrb systemState={systemState} />
        </div>

        <div style={{ display: 'grid', gridTemplateRows: '1fr 1.15fr 0.9fr', gap: 10, minHeight: 0 }}>
          <SystemStatusPanel connectors={connectors} voice={voice} health={health} />
          <CalendarPanel state={calendar} />
          <FinancePanel />
        </div>
      </div>

      <VantaBottomBar systemState={systemState} voiceMode={voiceMode} input={input} sending={sending} onInput={setInput} onSend={onSend} onMicDown={() => { audio.click(); setMicHeld(true); }} onMicUp={() => setMicHeld(false)} />
    </div>
  );
}

export default VantaCockpitPage;
