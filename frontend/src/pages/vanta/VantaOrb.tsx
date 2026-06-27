// VantaOrb — HUD core matching the jarvis_hud reference: radial-gradient sphere
// (white-hot center → cyan → deep blue edge), 3 expanding ring halos, a breathing
// outer glow, rotating orbital ellipses with travelling dots, and node badges
// (COS/GM, W×35, M×17, REV, PA) tethered to the core by dashed connectors.

import React from 'react';
import { VANTA, type SystemState } from './vanta-kit';

const V = 440; // viewBox units
const CX = V / 2;

interface Cfg { label: string; core: string; ring: string; spin: string }
function cfgFor(s: SystemState): Cfg {
  switch (s) {
    case 'processing': return { label: 'PROCESSING', core: '#00D4FF', ring: '#00D4FF', spin: '0.85' };
    case 'speaking': return { label: 'SPEAKING', core: '#00F5D4', ring: '#00F5D4', spin: '0.95' };
    case 'error': return { label: 'ANALYZING', core: '#FF9500', ring: '#FF9500', spin: '1.1' };
    default: return { label: 'READY', core: '#00D4FF', ring: '#3aa8ff', spin: '1' };
  }
}

const NODES: { id: string; x: number; y: number }[] = [
  { id: 'COS/GM', x: 220, y: 50 },
  { id: 'W×35', x: 372, y: 134 },
  { id: 'M×17', x: 360, y: 316 },
  { id: 'REV', x: 96, y: 330 },
  { id: 'PA', x: 74, y: 140 },
];

function centerStyle(sizePct: number): React.CSSProperties {
  return { position: 'absolute', top: '50%', left: '50%', width: `${sizePct}%`, height: `${sizePct}%`, transform: 'translate(-50%,-50%)', borderRadius: '50%' };
}

export function VantaOrb({ systemState }: { systemState: SystemState }): React.ReactElement {
  const cfg = cfgFor(systemState);
  const sd = (base: number) => `${(base * Number(cfg.spin)).toFixed(1)}s`;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', maxWidth: V, maxHeight: V, aspectRatio: '1 / 1', margin: 'auto' }}>
      {/* SVG: orbital ellipses + travelling dots + connectors + node dots */}
      <svg viewBox={`0 0 ${V} ${V}`} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
        {/* dashed connectors from core to each node + midpoint dot */}
        {NODES.map((n) => {
          const mx = (CX + n.x) / 2, my = (CX + n.y) / 2;
          return (
            <g key={n.id}>
              <line x1={CX} y1={CX} x2={n.x} y2={n.y} stroke={VANTA.c} strokeOpacity={0.22} strokeWidth={1} strokeDasharray="3 5" />
              <circle cx={mx} cy={my} r={1.7} fill={VANTA.c} opacity={0.7} />
            </g>
          );
        })}
        {/* orbital ellipse 1 */}
        <g style={{ transformOrigin: `${CX}px ${CX}px`, animation: `vSpin ${sd(24)} linear infinite` }}>
          <ellipse cx={CX} cy={CX} rx={205} ry={78} fill="none" stroke={cfg.ring} strokeOpacity={0.16} />
          <circle cx={CX + 205} cy={CX} r={3} fill={cfg.ring}><animate attributeName="opacity" values="0.4;1;0.4" dur="2s" repeatCount="indefinite" /></circle>
        </g>
        {/* orbital ellipse 2 */}
        <g style={{ transformOrigin: `${CX}px ${CX}px`, animation: `vSpinRev ${sd(32)} linear infinite` }}>
          <ellipse cx={CX} cy={CX} rx={86} ry={200} fill="none" stroke={cfg.ring} strokeOpacity={0.13} />
          <circle cx={CX} cy={CX - 200} r={2.6} fill={VANTA.tl} />
        </g>
        {/* orbital ellipse 3 (tilted) */}
        <g style={{ transformOrigin: `${CX}px ${CX}px`, animation: `vSpin ${sd(40)} linear infinite` }}>
          <ellipse cx={CX} cy={CX} rx={200} ry={150} fill="none" stroke={cfg.ring} strokeOpacity={0.1} transform={`rotate(34 ${CX} ${CX})`} />
        </g>
        {/* node anchor dots */}
        {NODES.map((n) => <circle key={n.id} cx={n.x} cy={n.y} r={2.4} fill={VANTA.c} />)}
      </svg>

      {/* breathing outer glow */}
      <div style={{ ...centerStyle(58), background: `radial-gradient(circle, ${cfg.core}55, transparent 68%)`, filter: 'blur(8px)', animation: 'vBreathe 4.5s ease-in-out infinite' }} />

      {/* 3 expanding ring halos */}
      {[0, 1.3, 2.6].map((delay, i) => (
        <div key={i} style={{ ...centerStyle(34), border: `1px solid ${cfg.ring}`, animation: `vRing 4s ease-out ${delay}s infinite` }} />
      ))}

      {/* core sphere */}
      <div style={{
        ...centerStyle(34),
        background: `radial-gradient(circle at 38% 32%, #ffffff 0%, ${cfg.core} 32%, #0a4a8a 64%, #041830 100%)`,
        boxShadow: `0 0 40px ${cfg.core}, 0 0 90px ${cfg.core}66, inset 0 0 30px rgba(255,255,255,0.25)`,
        animation: `vCorePulse ${systemState === 'processing' ? '1.1s' : '3s'} ease-in-out infinite`,
      }} />

      {/* node badge pills */}
      {NODES.map((n) => (
        <div key={n.id} style={{
          position: 'absolute', left: `${(n.x / V) * 100}%`, top: `${(n.y / V) * 100}%`, transform: 'translate(-50%,-50%)',
          fontFamily: VANTA.orb, fontSize: 8.5, fontWeight: 600, letterSpacing: '1.5px', color: VANTA.c,
          padding: '2px 7px', borderRadius: 3, whiteSpace: 'nowrap',
          background: 'rgba(2,12,28,0.75)', border: `1px solid ${VANTA.border}`,
          boxShadow: `0 0 10px ${VANTA.c}33`,
        }}>{n.id}</div>
      ))}

      {/* READY / state label */}
      <div style={{ position: 'absolute', bottom: '2%', left: '50%', transform: 'translateX(-50%)', fontFamily: VANTA.orb, fontSize: 13, fontWeight: 700, letterSpacing: '6px', color: cfg.core, textShadow: `0 0 16px ${cfg.core}` }}>
        {cfg.label}
      </div>
    </div>
  );
}
