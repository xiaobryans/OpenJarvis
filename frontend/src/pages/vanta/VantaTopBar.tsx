// VantaTopBar — full-width header: VANTA branding, live ticking SGT clock,
// date + weekday, live Singapore weather, system status, voice status.

import React from 'react';
import { VANTA, Dot, Metric, type SystemState, type VoiceMode, type WeatherData, type HealthData } from './vanta-kit';

const SGT_TZ = 'Asia/Singapore';

function useClock(): Date {
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return now;
}

function voiceLabel(mode: VoiceMode): { text: string; color: string } {
  switch (mode) {
    case 'listening':
      return { text: '● LISTENING', color: VANTA.green };
    case 'active':
      return { text: '● ACTIVE', color: VANTA.cyan };
    case 'parked':
      return { text: '◌ PARKED', color: VANTA.amber };
    default:
      return { text: '○ VOICE OFF', color: VANTA.textDim };
  }
}

function parseTemp(text: string): string {
  const m = text.match(/([+-]?\d+°C)/);
  return m ? m[1] : '—';
}

export function VantaTopBar({
  systemState,
  voiceMode,
  weather,
  health,
}: {
  systemState: SystemState;
  voiceMode: VoiceMode;
  weather: WeatherData | null;
  health: HealthData | null;
}): React.ReactElement {
  const now = useClock();
  const time = new Intl.DateTimeFormat('en-GB', { timeZone: SGT_TZ, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(now);
  const date = new Intl.DateTimeFormat('en-GB', { timeZone: SGT_TZ, weekday: 'long', day: '2-digit', month: 'short', year: 'numeric' }).format(now);

  const v = voiceLabel(voiceMode);
  const sysColor = systemState === 'error' ? VANTA.red : systemState === 'idle' ? VANTA.green : VANTA.cyan;
  const sysOk = health?.status === 'ok';
  const weatherText = weather?.ok ? weather.text.replace(/^Singapore:\s*/, '') : 'weather unavailable';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        height: 52,
        background: 'rgba(8,13,26,0.7)',
        backdropFilter: 'blur(14px)',
        borderBottom: `1px solid ${VANTA.panelBorder}`,
        flexShrink: 0,
      }}
    >
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ fontFamily: VANTA.mono, fontWeight: 800, fontSize: 20, letterSpacing: '0.34em', color: VANTA.cyan, textShadow: `0 0 16px ${VANTA.cyan}88` }}>VANTA</div>
        <div style={{ fontFamily: VANTA.mono, fontSize: 8, color: VANTA.textDim, letterSpacing: '0.2em', lineHeight: 1.3 }}>
          NEURAL<br />COMMAND
        </div>
      </div>

      {/* Clock + date */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
        <Metric value={time} color={VANTA.text} size={22} />
        <div style={{ fontFamily: VANTA.mono, fontSize: 9, color: VANTA.textDim, letterSpacing: '0.14em' }}>{date} · SGT</div>
      </div>

      {/* Weather + status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
          <Metric value={parseTemp(weather?.text ?? '')} color={VANTA.amber} size={15} />
          <div style={{ fontFamily: VANTA.mono, fontSize: 8, color: VANTA.textDim, maxWidth: 220, textAlign: 'right', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            🇸🇬 {weatherText}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: VANTA.mono, fontSize: 9, color: sysColor }}>
            <Dot color={sysColor} pulse={systemState !== 'idle'} /> {sysOk ? 'SYSTEM OK' : 'SYSTEM…'}
          </div>
          <div style={{ fontFamily: VANTA.mono, fontSize: 10, color: v.color, fontWeight: 700, letterSpacing: '0.08em' }}>{v.text}</div>
        </div>
      </div>
    </div>
  );
}
