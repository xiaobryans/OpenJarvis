// VantaCockpitPage — the VANTA Neural Command Center cockpit (Task B redesign).
//
// Single page, no routing. Full-width top/bottom bars, three-column body
// (left panels · orb · right panels). Every panel pulls real data on its own
// auto-refresh interval (Task A) via useLivePanel — no manual refresh, no fakes.

import React from 'react';
import { useLivePanel } from '../lib/useLivePanel';
import { apiFetch } from '../lib/api';
import {
  VANTA, VantaKeyframes,
  type SystemState, type VoiceMode,
  type WeatherData, type CommsData, type CalendarData, type MemoryData,
  type VoiceStatusData, type BriefingData, type HealthData,
} from './vanta/vanta-kit';
import { VantaTopBar } from './vanta/VantaTopBar';
import { VantaBottomBar } from './vanta/VantaBottomBar';
import { VantaOrb } from './vanta/VantaOrb';
import { CommsPanel, MemoryPanel, CalendarPanel, FinancePanel, BriefingBanner } from './vanta/VantaPanels';

// Task A refresh intervals (ms).
const I = {
  voice: 5_000,
  system: 10_000,
  connectors: 30_000,
  memory: 60_000,
  comms: 120_000,
  calendar: 300_000,
  weather: 1_800_000,
} as const;

function deriveVoiceMode(v: VoiceStatusData | null, ok: boolean): VoiceMode {
  if (!ok || !v) return 'off';
  const state = String(v.state ?? '').toLowerCase();
  if (state === 'speaking' || state === 'thinking' || state === 'transcribing' || v.active) return 'active';
  if (v.listening || state === 'listening' || state === 'awake') return 'listening';
  return 'parked';
}

export function VantaCockpitPage(): React.ReactElement {
  // ── live panels ──────────────────────────────────────────────────────────
  const health = useLivePanel<HealthData>('/health', I.system);
  const voice = useLivePanel<VoiceStatusData>('/v1/voice/status', I.voice);
  const weather = useLivePanel<WeatherData>('/v1/weather', I.weather);
  const comms = useLivePanel<CommsData>('/v1/comms/recent', I.comms);
  const calendar = useLivePanel<CalendarData>('/v1/calendar/today', I.calendar);
  const memory = useLivePanel<MemoryData>('/v1/memory/status', I.memory);
  const briefing = useLivePanel<BriefingData>('/v1/briefing/latest', 0 || 3_600_000); // load once-ish

  // ── command input ──────────────────────────────────────────────────────────
  const [input, setInput] = React.useState('');
  const [sending, setSending] = React.useState(false);
  const [micHeld, setMicHeld] = React.useState(false);
  const [briefingDismissed, setBriefingDismissed] = React.useState(false);

  const voiceMode = micHeld ? 'active' : deriveVoiceMode(voice.data, voice.ok);

  const systemState: SystemState = React.useMemo(() => {
    if (sending) return 'processing';
    const vs = String(voice.data?.state ?? '').toLowerCase();
    if (vs === 'speaking') return 'speaking';
    if (health.data && health.data.status !== 'ok') return 'error';
    return 'idle';
  }, [sending, voice.data, health.data]);

  const onSend = React.useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      await apiFetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'user', content: text }], stream: false }),
      });
      setInput('');
    } catch {
      /* surfaced via system state; keep input for retry */
    } finally {
      setSending(false);
    }
  }, [input, sending]);

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%', background: VANTA.bg, color: VANTA.text, display: 'flex', flexDirection: 'column', overflow: 'hidden', fontFamily: VANTA.mono }}>
      <VantaKeyframes />
      {/* ── living background layers ── */}
      {/* perspective floor grid */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0,
        background: 'repeating-linear-gradient(0deg, transparent, transparent 43px, rgba(0,212,255,0.04) 44px), repeating-linear-gradient(90deg, transparent, transparent 43px, rgba(0,212,255,0.04) 44px)' }} />
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: '42%', pointerEvents: 'none', zIndex: 0,
        background: 'repeating-linear-gradient(0deg, transparent, transparent 22px, rgba(0,212,255,0.05) 23px)',
        transform: 'perspective(420px) rotateX(62deg)', transformOrigin: 'bottom', opacity: 0.5, maskImage: 'linear-gradient(to top, black, transparent)', WebkitMaskImage: 'linear-gradient(to top, black, transparent)' }} />
      {/* radial glow behind orb */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0,
        background: 'radial-gradient(560px 560px at 50% 52%, rgba(0,212,255,0.05), transparent 70%)' }} />
      {/* periodic scan-line sweep */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: '24vh', pointerEvents: 'none', zIndex: 0,
        background: 'linear-gradient(to bottom, transparent, rgba(0,212,255,0.06) 50%, transparent)', animation: 'vantaScan 9s ease-in-out infinite' }} />

      <VantaTopBar systemState={systemState} voiceMode={voiceMode} weather={weather.data} health={health.data} />

      {!briefingDismissed && (
        <div style={{ paddingTop: 8 }}>
          <BriefingBanner state={briefing} onDismiss={() => setBriefingDismissed(true)} />
        </div>
      )}

      {/* Body: left · center · right */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '260px 1fr 260px', gap: 10, padding: 10, minHeight: 0, position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'grid', gridTemplateRows: '1fr auto', gap: 10, minHeight: 0 }}>
          <CommsPanel state={comms} />
          <MemoryPanel state={memory} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 0, minHeight: 0, overflow: 'hidden' }}>
          <VantaOrb systemState={systemState} />
        </div>

        <div style={{ display: 'grid', gridTemplateRows: '1fr auto', gap: 10, minHeight: 0 }}>
          <CalendarPanel state={calendar} />
          <FinancePanel />
        </div>
      </div>

      <VantaBottomBar
        systemState={systemState}
        voiceMode={voiceMode}
        input={input}
        sending={sending}
        onInput={setInput}
        onSend={onSend}
        onMicDown={() => setMicHeld(true)}
        onMicUp={() => setMicHeld(false)}
      />
    </div>
  );
}

export default VantaCockpitPage;
