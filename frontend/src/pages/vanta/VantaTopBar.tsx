// VantaTopBar — 48px HUD header: VANTA (Orbitron), centred live SGT clock,
// live weather, system + prominent voice status.

import React from 'react';
import { VANTA, Dot, type SystemState, type VoiceMode, type WeatherData, type HealthData } from './vanta-kit';

const SGT = 'Asia/Singapore';

function useClock(): Date {
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 1000); return () => window.clearInterval(t); }, []);
  return now;
}
function voiceLabel(m: VoiceMode): { text: string; color: string } {
  switch (m) {
    case 'listening': return { text: '● LISTENING', color: VANTA.gr };
    case 'active': return { text: '● ACTIVE', color: VANTA.c };
    case 'parked': return { text: '◌ PARKED', color: VANTA.am };
    default: return { text: '○ VOICE OFF', color: VANTA.dim };
  }
}
function parseTemp(text: string): string { const m = text.match(/([+-]?\d+°C)/); return m ? m[1] : '—'; }

export function VantaTopBar({ systemState, voiceMode, weather, health }: { systemState: SystemState; voiceMode: VoiceMode; weather: WeatherData | null; health: HealthData | null }): React.ReactElement {
  const now = useClock();
  const time = new Intl.DateTimeFormat('en-GB', { timeZone: SGT, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(now);
  const date = new Intl.DateTimeFormat('en-GB', { timeZone: SGT, weekday: 'short', day: '2-digit', month: 'short' }).format(now);
  const v = voiceLabel(voiceMode);
  const sysColor = systemState === 'error' ? VANTA.rd : systemState === 'idle' ? VANTA.gr : VANTA.c;
  const sysOk = health?.status === 'ok';
  const weatherText = weather?.ok ? weather.text.replace(/^Singapore:\s*/, '') : 'weather offline';

  return (
    <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 48, padding: '0 16px', background: 'rgba(2,8,22,0.98)', borderBottom: `1px solid ${VANTA.border}`, flexShrink: 0 }}>
      {/* brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 230 }}>
        <div style={{ fontFamily: VANTA.orb, fontWeight: 900, fontSize: 22, letterSpacing: '7px', color: VANTA.c, textShadow: '0 0 20px #00d4ff, 0 0 40px rgba(0,212,255,0.5)' }}>VANTA</div>
        <div style={{ fontFamily: VANTA.orb, fontSize: 7.5, color: VANTA.c, opacity: 0.6, letterSpacing: '3px', lineHeight: 1.3 }}>NEURAL<br />COMMAND</div>
      </div>

      {/* clock */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0 }}>
        <span style={{ fontFamily: VANTA.orb, fontSize: 21, fontWeight: 700, color: '#fff', letterSpacing: '2px', textShadow: '0 0 14px rgba(255,255,255,0.3)' }}>{time}</span>
        <span style={{ fontFamily: VANTA.mono, fontSize: 8.5, color: VANTA.dim, letterSpacing: '2px' }}>{date} · SGT</span>
      </div>

      {/* weather + status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, minWidth: 230, justifyContent: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
          <span style={{ fontFamily: VANTA.orb, fontSize: 14, fontWeight: 600, color: VANTA.am, textShadow: `0 0 10px ${VANTA.am}66` }}>{parseTemp(weather?.text ?? '')}</span>
          <span style={{ fontFamily: VANTA.mono, fontSize: 8, color: VANTA.dim, maxWidth: 180, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>🇸🇬 {weatherText}</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: VANTA.mono, fontSize: 9, color: sysColor }}><Dot color={sysColor} pulse /> {sysOk ? 'SYSTEM OK' : 'SYSTEM…'}</span>
          <span style={{ fontFamily: VANTA.orb, fontSize: 10, fontWeight: 600, letterSpacing: '1px', color: v.color, textShadow: voiceMode === 'off' ? 'none' : `0 0 10px ${v.color}` }}>{v.text}</span>
        </div>
      </div>
    </div>
  );
}
