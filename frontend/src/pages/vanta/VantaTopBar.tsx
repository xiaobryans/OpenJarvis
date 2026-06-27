// VantaTopBar — top header: hexagon VANTA logo, four live status pills
// (CORTEX ONLINE / VOICE state / SECURE CHANNEL / NET STABLE), and a live SGT
// clock + date. Faithful port of VANTA-export_dc.html, wired to backend health +
// voice state. The VOICE pill is state-driven (FIX 3).

import React from 'react';

function hexToRgba(c: string, a: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(c.trim());
  if (m) {
    const n = parseInt(m[1], 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  // Already rgba()/named — return a low-opacity cyan-ish fallback for fills.
  return c;
}

function StatusPill({ label, color, on, delay }: { label: string; color: string; on: boolean; delay: number }): React.ReactElement {
  const c = on ? color : 'rgba(0,212,255,0.4)';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 5, padding: '3px 8px',
      border: `1px solid ${hexToRgba(c, 0.25)}`, borderRadius: 2, background: hexToRgba(c, 0.06),
    }}>
      <div style={{
        width: 5, height: 5, borderRadius: '50%', background: c,
        boxShadow: on ? `0 0 6px ${c}` : 'none', flexShrink: 0,
        animation: on ? `vStatusPulse 2.2s ease-in-out infinite ${delay}s` : undefined,
      }} />
      <span style={{ fontSize: 7, letterSpacing: '1.5px', color: hexToRgba(c, on ? 0.85 : 0.6), textTransform: 'uppercase' }}>{label}</span>
    </div>
  );
}

export function VantaTopBar({ time, dateStr, serverUp, voice }: {
  time: string; dateStr: string; serverUp: boolean;
  voice: { label: string; color: string; on: boolean };
}): React.ReactElement {
  return (
    <div style={{
      height: 52, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 14,
      borderBottom: '1px solid rgba(0,212,255,0.1)', background: 'rgba(2,10,24,0.94)', position: 'relative', overflow: 'hidden',
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <div style={{
          width: 34, height: 34, border: '1.5px solid rgba(0,212,255,0.45)', borderRadius: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,212,255,0.06)',
          boxShadow: '0 0 14px rgba(0,212,255,0.14)', position: 'relative', flexShrink: 0,
        }}>
          <div style={{
            width: 14, height: 14, background: 'rgba(0,212,255,0.88)',
            clipPath: 'polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%)',
            boxShadow: '0 0 10px rgba(0,212,255,0.9)',
          }} />
          <div style={{ position: 'absolute', top: 2, left: 2, width: 5, height: 5, borderTop: '1px solid rgba(0,212,255,0.55)', borderLeft: '1px solid rgba(0,212,255,0.55)' }} />
          <div style={{ position: 'absolute', bottom: 2, right: 2, width: 5, height: 5, borderBottom: '1px solid rgba(0,212,255,0.55)', borderRight: '1px solid rgba(0,212,255,0.55)' }} />
        </div>
        <div>
          <div style={{
            fontFamily: "'Exo 2',sans-serif", fontWeight: 900, fontSize: 20, letterSpacing: '6px', color: '#e8f8ff',
            textShadow: '0 0 22px rgba(0,212,255,0.45)', animation: 'vGlitch 11s ease-in-out infinite',
          }}>VANTA</div>
          <div style={{ fontSize: 7, letterSpacing: '3px', color: 'rgba(0,212,255,0.38)', marginTop: -3, textTransform: 'uppercase' }}>Voice Intelligence System</div>
        </div>
      </div>

      {/* Status pills */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <StatusPill label={serverUp ? 'CORTEX ONLINE' : 'CORTEX OFFLINE'} color="#10b981" on={serverUp} delay={0} />
        <StatusPill label={voice.label} color={voice.color} on={voice.on} delay={0.6} />
        <StatusPill label="SECURE CHANNEL" color="#00d4ff" on={serverUp} delay={1.1} />
        <StatusPill label={serverUp ? 'NET STABLE' : 'NET DOWN'} color="#10b981" on={serverUp} delay={0.9} />
      </div>

      <div style={{ flex: 1 }} />

      {/* Clock + date */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: 29, fontWeight: 700, color: '#e2f4ff', letterSpacing: '3px', lineHeight: 1, textShadow: '0 0 20px rgba(0,212,255,0.3)' }}>{time}</div>
        <div style={{ fontSize: 7, letterSpacing: '2px', color: 'rgba(0,212,255,0.42)', marginTop: 1, textTransform: 'uppercase' }}>{dateStr}</div>
      </div>

      <div style={{ position: 'absolute', left: 0, bottom: 0, right: 0, height: 1, background: 'linear-gradient(to right,transparent,rgba(0,212,255,0.22),transparent)' }} />
    </div>
  );
}
