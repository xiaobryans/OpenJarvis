// VantaOrb — central particle-nebula orb with orbital worker/manager nodes.
// Reacts to system state: idle (slow cool-blue pulse), processing (faster,
// brighter), speaking (ripple outward), error (amber/red shift).

import React from 'react';
import { VANTA, type SystemState } from './vanta-kit';

const WORKERS = 35; // outer ring — W×35
const MANAGERS = 17; // middle ring — M×17

function stateColor(s: SystemState): { core: string; ring: string; glow: string } {
  switch (s) {
    case 'processing':
      return { core: VANTA.cyan, ring: VANTA.cyan, glow: VANTA.cyan };
    case 'speaking':
      return { core: VANTA.green, ring: VANTA.green, glow: VANTA.green };
    case 'error':
      return { core: VANTA.amber, ring: VANTA.red, glow: VANTA.amber };
    default:
      return { core: '#3aa0ff', ring: '#2d6fb0', glow: '#1e6fd0' };
  }
}

function ringNodes(count: number, radius: number, color: string, dur: number, reverse: boolean) {
  const nodes = [];
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * 2 * Math.PI;
    const cx = 150 + radius * Math.cos(angle);
    const cy = 150 + radius * Math.sin(angle);
    nodes.push(<circle key={i} cx={cx} cy={cy} r={2.1} fill={color} opacity={0.85} />);
  }
  return (
    <g style={{ transformOrigin: '150px 150px', animation: `${reverse ? 'vantaSpinRev' : 'vantaSpin'} ${dur}s linear infinite` }}>
      <circle cx={150} cy={150} r={radius} fill="none" stroke={color} strokeOpacity={0.14} strokeWidth={1} />
      {nodes}
    </g>
  );
}

export function VantaOrb({ systemState }: { systemState: SystemState }): React.ReactElement {
  const c = stateColor(systemState);
  const pulseDur = systemState === 'processing' ? '1.1s' : systemState === 'idle' ? '3.4s' : '2s';

  return (
    <div style={{ position: 'relative', width: 300, height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg viewBox="0 0 300 300" width={300} height={300} style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <radialGradient id="vantaCore" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={c.core} stopOpacity={0.95} />
            <stop offset="45%" stopColor={c.core} stopOpacity={0.5} />
            <stop offset="100%" stopColor={c.core} stopOpacity={0} />
          </radialGradient>
          <filter id="vantaBlur"><feGaussianBlur stdDeviation="3" /></filter>
        </defs>

        {/* Orbital rings: managers (inner) + workers (outer) */}
        {ringNodes(MANAGERS, 88, c.ring, 26, true)}
        {ringNodes(WORKERS, 128, c.ring, 40, false)}

        {/* Speaking ripple */}
        {systemState === 'speaking' && (
          <circle cx={150} cy={150} r={60} fill="none" stroke={c.glow} strokeWidth={2}
            style={{ transformOrigin: '150px 150px', animation: 'vantaRipple 1.4s ease-out infinite' }} />
        )}

        {/* Core nebula */}
        <circle cx={150} cy={150} r={58} fill="url(#vantaCore)" filter="url(#vantaBlur)"
          style={{ transformOrigin: '150px 150px', animation: `vantaPulse ${pulseDur} ease-in-out infinite` }} />
        <circle cx={150} cy={150} r={30} fill={c.core} fillOpacity={0.9}
          style={{ transformOrigin: '150px 150px', animation: `vantaPulse ${pulseDur} ease-in-out infinite` }} />

        {/* COS / GM labels near core */}
        <text x={150} y={146} textAnchor="middle" fontFamily={VANTA.mono} fontSize={11} fill="#001018" fontWeight={700}>VANTA</text>
        <text x={150} y={160} textAnchor="middle" fontFamily={VANTA.mono} fontSize={7} fill="#00202c" letterSpacing="1.5">COS · GM</text>
      </svg>

      {/* Ring legend */}
      <div style={{ position: 'absolute', top: 6, left: 6, fontFamily: VANTA.mono, fontSize: 8, color: VANTA.textDim, lineHeight: 1.6 }}>
        <div><span style={{ color: c.ring }}>●</span> W×{WORKERS} workers</div>
        <div><span style={{ color: c.ring }}>●</span> M×{MANAGERS} managers</div>
        <div><span style={{ color: VANTA.cyan }}>◆</span> COS / GM</div>
      </div>

      {/* READY label */}
      <div style={{ position: 'absolute', bottom: -4, left: '50%', transform: 'translateX(-50%)', fontFamily: VANTA.mono, fontSize: 11, letterSpacing: '0.32em', color: c.glow, textShadow: `0 0 12px ${c.glow}`, fontWeight: 700 }}>
        {systemState === 'error' ? 'ATTENTION' : systemState === 'processing' ? 'PROCESSING' : systemState === 'speaking' ? 'SPEAKING' : 'READY'}
      </div>
    </div>
  );
}
