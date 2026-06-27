// VantaOrb — Canvas particle-nebula: a glowing 3-D energy sphere, not a flat
// circle. ~2000 particles on a center-dense Fibonacci sphere, depth-shaded,
// each breathing on its own phase, compounded with additive blending. Orbital
// worker/manager nodes ring the outside. Reacts to system state.

import React from 'react';
import { VANTA, type SystemState } from './vanta-kit';

const N = 2000; // particle count
const GOLDEN = Math.PI * (3 - Math.sqrt(5));
const SIZE = 460; // logical canvas px
const CORE_R = 118; // nebula visual radius
const WORKERS = 35;
const MANAGERS = 17;

interface Particle {
  x: number; y: number; z: number; // unit-ish position (center-biased)
  rf: number; // 0 = core, 1 = edge
  phase: number; // independent pulse phase
}

interface StateCfg {
  rot: number; // rotation speed
  expand: number; // radial expansion (processing pushes outward)
  bright: number; // global brightness multiplier
  ripple: boolean;
  edge: [number, number, number]; // outer particle colour
  core: [number, number, number]; // hot core colour
}

function cfgFor(s: SystemState): StateCfg {
  switch (s) {
    case 'processing':
      return { rot: 0.011, expand: 0.16, bright: 1.35, ripple: false, edge: [0, 212, 255], core: [255, 255, 255] };
    case 'speaking':
      return { rot: 0.006, expand: 0.06, bright: 1.2, ripple: true, edge: [0, 255, 150], core: [220, 255, 240] };
    case 'error':
      return { rot: 0.007, expand: 0.05, bright: 1.1, ripple: false, edge: [255, 90, 40], core: [255, 220, 150] };
    default:
      return { rot: 0.0032, expand: 0, bright: 1.0, ripple: false, edge: [30, 130, 230], core: [235, 248, 255] };
  }
}

function buildParticles(): Particle[] {
  const ps: Particle[] = [];
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2; // -1..1
    const rad = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = i * GOLDEN;
    const dx = Math.cos(theta) * rad;
    const dz = Math.sin(theta) * rad;
    // center-dense radius: pow(u, 1.6) clusters particles toward the core.
    const rf = Math.pow(Math.random(), 1.6);
    ps.push({ x: dx * rf, y: y * rf, z: dz * rf, rf, phase: Math.random() * Math.PI * 2 });
  }
  return ps;
}

export function VantaOrb({ systemState }: { systemState: SystemState }): React.ReactElement {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const particles = React.useRef<Particle[]>([]);
  const stateRef = React.useRef<SystemState>(systemState);
  stateRef.current = systemState;

  React.useEffect(() => {
    if (particles.current.length === 0) particles.current = buildParticles();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = SIZE * dpr;
    canvas.height = SIZE * dpr;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const cx = SIZE / 2;
    const cy = SIZE / 2;
    let raf = 0;
    let t0 = 0;
    let angle = 0;

    const draw = (t: number): void => {
      if (!t0) t0 = t;
      const cfg = cfgFor(stateRef.current);
      angle += cfg.rot;
      const cosA = Math.cos(angle);
      const sinA = Math.sin(angle);

      ctx.clearRect(0, 0, SIZE, SIZE);

      // faint radial halo behind the nebula
      const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, CORE_R * 1.7);
      halo.addColorStop(0, `rgba(${cfg.edge[0]},${cfg.edge[1]},${cfg.edge[2]},0.10)`);
      halo.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = halo;
      ctx.fillRect(0, 0, SIZE, SIZE);

      ctx.globalCompositeOperation = 'lighter';

      // ripple wave (speaking): a normalized radius sweeping outward
      const wave = cfg.ripple ? ((t - t0) % 1400) / 1400 : -1;

      const expand = 1 + cfg.expand * (0.6 + 0.4 * Math.sin((t - t0) * 0.004));
      const ps = particles.current;
      for (let i = 0; i < ps.length; i++) {
        const p = ps[i];
        // rotate around Y axis
        const rx = p.x * cosA - p.z * sinA;
        const rz = p.x * sinA + p.z * cosA;
        const depth = (rz + 1) / 2; // 0 far .. 1 near
        const persp = 0.82 + depth * 0.18;
        const sx = cx + rx * CORE_R * expand * persp;
        const sy = cy + p.y * CORE_R * expand * persp;

        const pulse = 0.55 + 0.45 * Math.sin(t * 0.002 + p.phase);
        let bright = (0.12 + depth * 0.55) * pulse * cfg.bright;
        let size = (0.5 + depth * 1.9) * (0.7 + 0.3 * pulse);

        if (wave >= 0) {
          const d = Math.abs(p.rf - wave);
          if (d < 0.12) {
            const boost = 1 - d / 0.12;
            bright += boost * 0.6;
            size += boost * 1.4;
          }
        }

        // colour: hot white core -> state edge colour
        const m = p.rf;
        const r = cfg.core[0] + (cfg.edge[0] - cfg.core[0]) * m;
        const g = cfg.core[1] + (cfg.edge[1] - cfg.core[1]) * m;
        const b = cfg.core[2] + (cfg.edge[2] - cfg.core[2]) * m;
        ctx.fillStyle = `rgba(${r | 0},${g | 0},${b | 0},${Math.min(bright, 0.95)})`;
        ctx.beginPath();
        ctx.arc(sx, sy, size, 0, Math.PI * 2);
        ctx.fill();
      }

      // white-hot core bloom
      const bloom = ctx.createRadialGradient(cx, cy, 0, cx, cy, CORE_R * 0.5);
      bloom.addColorStop(0, `rgba(${cfg.core[0]},${cfg.core[1]},${cfg.core[2]},${0.5 * cfg.bright})`);
      bloom.addColorStop(0.5, `rgba(${cfg.edge[0]},${cfg.edge[1]},${cfg.edge[2]},0.12)`);
      bloom.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = bloom;
      ctx.beginPath();
      ctx.arc(cx, cy, CORE_R * 0.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.globalCompositeOperation = 'source-over';
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  const cfg = cfgFor(systemState);
  const glow = `rgb(${cfg.edge[0]},${cfg.edge[1]},${cfg.edge[2]})`;
  const ready =
    systemState === 'error' ? 'ATTENTION' :
    systemState === 'processing' ? 'PROCESSING' :
    systemState === 'speaking' ? 'SPEAKING' : 'READY';

  return (
    <div style={{ position: 'relative', width: SIZE, height: SIZE, maxWidth: '100%', maxHeight: '100%' }}>
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: SIZE, height: SIZE }} />

      {/* Orbital node rings (orbit outside the nebula) */}
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <g style={{ transformOrigin: `${SIZE / 2}px ${SIZE / 2}px`, animation: 'vantaSpin 44s linear infinite' }}>
          <circle cx={SIZE / 2} cy={SIZE / 2} r={188} fill="none" stroke={glow} strokeOpacity={0.12} />
          {Array.from({ length: WORKERS }).map((_, i) => {
            const a = (i / WORKERS) * 2 * Math.PI;
            return <circle key={i} cx={SIZE / 2 + 188 * Math.cos(a)} cy={SIZE / 2 + 188 * Math.sin(a)} r={1.9} fill={glow} opacity={0.8} />;
          })}
        </g>
        <g style={{ transformOrigin: `${SIZE / 2}px ${SIZE / 2}px`, animation: 'vantaSpinRev 30s linear infinite' }}>
          <circle cx={SIZE / 2} cy={SIZE / 2} r={156} fill="none" stroke={glow} strokeOpacity={0.1} />
          {Array.from({ length: MANAGERS }).map((_, i) => {
            const a = (i / MANAGERS) * 2 * Math.PI;
            return <circle key={i} cx={SIZE / 2 + 156 * Math.cos(a)} cy={SIZE / 2 + 156 * Math.sin(a)} r={2.4} fill={VANTA.cyan} opacity={0.9} />;
          })}
        </g>
      </svg>

      {/* Legend */}
      <div style={{ position: 'absolute', top: 8, left: 8, fontFamily: VANTA.mono, fontSize: 8, color: VANTA.textDim, lineHeight: 1.7 }}>
        <div><span style={{ color: glow }}>●</span> W×{WORKERS} workers</div>
        <div><span style={{ color: VANTA.cyan }}>●</span> M×{MANAGERS} managers</div>
        <div><span style={{ color: '#fff' }}>◆</span> COS / GM core</div>
      </div>

      {/* READY label */}
      <div style={{ position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)', fontFamily: VANTA.mono, fontSize: 12, letterSpacing: '0.34em', color: glow, textShadow: `0 0 14px ${glow}`, fontWeight: 700 }}>
        {ready}
      </div>
    </div>
  );
}
