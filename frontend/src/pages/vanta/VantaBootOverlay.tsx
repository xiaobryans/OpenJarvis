// VantaBootOverlay — full-screen overlay shown while the backend is starting
// ("VANTA INITIALISING…") or after it drops mid-session ("RECONNECTING…").
// Driven by the cockpit's /health poll; never overlaps once the server is up.

import React from 'react';

export function VantaBootOverlay({ healthy, everHealthy }: { healthy: boolean; everHealthy: boolean }): React.ReactElement | null {
  if (healthy) return null;
  const reconnecting = everHealthy;
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 400, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 20,
      background: 'radial-gradient(ellipse at 50% 45%, rgba(2,12,28,0.86), rgba(2,8,18,0.97))',
      backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)',
      fontFamily: "'Space Mono',monospace",
    }}>
      {/* Pulsing core */}
      <div style={{
        width: 70, height: 70, borderRadius: '50%',
        background: 'radial-gradient(circle at 34% 28%,rgba(255,255,255,0.95) 0%,rgba(0,190,255,0.88) 30%,rgba(0,50,140,0.96) 75%,rgba(0,12,45,1) 100%)',
        boxShadow: '0 0 40px rgba(0,190,255,0.7),0 0 90px rgba(0,160,255,0.4)',
        animation: 'statusPulse 1.6s ease-in-out infinite',
      }} />
      <div style={{
        fontFamily: "'Exo 2',sans-serif", fontWeight: 900, fontSize: 16, letterSpacing: '8px',
        color: reconnecting ? '#ff9500' : '#00d4ff', textShadow: `0 0 18px ${reconnecting ? 'rgba(255,149,0,0.5)' : 'rgba(0,212,255,0.5)'}`,
        textTransform: 'uppercase',
      }}>
        {reconnecting ? 'RECONNECTING…' : 'VANTA INITIALISING…'}
      </div>
      <div style={{ fontSize: 9, letterSpacing: '2px', color: 'rgba(0,212,255,0.5)' }}>
        {reconnecting ? '> backend dropped — restarting' : '> starting backend · waiting for /health'}
      </div>
    </div>
  );
}
