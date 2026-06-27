// VantaOrb — dark energy sphere with cyan plasma streams flowing across its
// surface (aurora / liquid-lightning), a soft diffuse halo, and sparks. The
// core is dark — the energy lives ON the surface. Streams wrap the sphere at
// different angles and depths; the sphere rotates slowly. Reacts to state.

import React from 'react';
import { VANTA, type SystemState } from './vanta-kit';

const SIZE = 500; // logical canvas px
const R = 200; // sphere radius (diameter 400)
const VIEW_TILT = 0.42; // tip the sphere toward the viewer
const SAMPLES = 230; // points per stream (dense enough to read as fluid ribbons)
const WORKERS = 35;
const MANAGERS = 17;

// Each plasma stream: a band wrapping the sphere with an undulating latitude,
// oriented by a fixed tilt so the streams cross at different angles.
interface Stream { tilt: [number, number, number]; phase: number; amp: number; k: number; dir: number }
const STREAMS: Stream[] = [
  { tilt: [0.25, 0.0, 0.15], phase: 0.0, amp: 0.34, k: 2, dir: 1 },
  { tilt: [1.15, 0.5, -0.1], phase: 2.1, amp: 0.27, k: 3, dir: -1 },
  { tilt: [0.55, 1.25, 0.35], phase: 4.0, amp: 0.31, k: 2, dir: 1 },
  { tilt: [1.55, 0.8, 0.7], phase: 1.2, amp: 0.22, k: 4, dir: -1 },
];

function rotX(p: number[], a: number): number[] { const c = Math.cos(a), s = Math.sin(a); return [p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c]; }
function rotY(p: number[], a: number): number[] { const c = Math.cos(a), s = Math.sin(a); return [p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c]; }
function rotZ(p: number[], a: number): number[] { const c = Math.cos(a), s = Math.sin(a); return [p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2]]; }

interface Cfg { primary: [number, number, number]; rot: number; flow: number; bright: number; ripple: boolean }
function cfgFor(s: SystemState): Cfg {
  switch (s) {
    case 'processing': return { primary: [0, 212, 255], rot: 0.010, flow: 1.8, bright: 1.35, ripple: false };
    case 'speaking': return { primary: [0, 255, 150], rot: 0.006, flow: 1.2, bright: 1.25, ripple: true };
    case 'error': return { primary: [255, 120, 40], rot: 0.007, flow: 1.0, bright: 1.15, ripple: false };
    default: return { primary: [0, 212, 255], rot: 0.0034, flow: 1.0, bright: 1.0, ripple: false };
  }
}

export function VantaOrb({ systemState }: { systemState: SystemState }): React.ReactElement {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const stateRef = React.useRef<SystemState>(systemState);
  stateRef.current = systemState;

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = SIZE * dpr;
    canvas.height = SIZE * dpr;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    const cx = SIZE / 2, cy = SIZE / 2;
    let raf = 0, t0 = 0, angle = 0;

    const draw = (t: number): void => {
      if (!t0) t0 = t;
      const tm = t - t0;
      const cfg = cfgFor(stateRef.current);
      const [pr, pg, pb] = cfg.primary;
      angle += cfg.rot;
      ctx.clearRect(0, 0, SIZE, SIZE);

      // ── soft diffuse halo around the whole sphere ──
      ctx.globalCompositeOperation = 'lighter';
      const halo = ctx.createRadialGradient(cx, cy, R * 0.55, cx, cy, R * 1.5);
      halo.addColorStop(0, `rgba(${pr},${pg},${pb},0.16)`);
      halo.addColorStop(0.5, `rgba(${pr},${pg},${pb},0.06)`);
      halo.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = halo;
      ctx.fillRect(0, 0, SIZE, SIZE);

      // ── dark sphere core (energy lives on the surface) ──
      ctx.globalCompositeOperation = 'source-over';
      const core = ctx.createRadialGradient(cx - R * 0.25, cy - R * 0.3, R * 0.1, cx, cy, R);
      core.addColorStop(0, '#0a1622');
      core.addColorStop(0.7, '#050d16');
      core.addColorStop(1, '#02060c');
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fillStyle = core; ctx.fill();

      // ── plasma streams (dense additive blobs = glowing fluid) ──
      ctx.globalCompositeOperation = 'lighter';
      for (let si = 0; si < STREAMS.length; si++) {
        const st = STREAMS[si];
        for (let i = 0; i < SAMPLES; i++) {
          const u = (i / SAMPLES) * Math.PI * 2;
          const lat = st.amp * Math.sin(st.k * u + st.phase + tm * 0.0006 * st.dir * cfg.flow);
          let p: number[] = [Math.cos(lat) * Math.cos(u), Math.sin(lat), Math.cos(lat) * Math.sin(u)];
          p = rotZ(rotY(rotX(p, st.tilt[0]), st.tilt[1]), st.tilt[2]);
          p = rotX(rotY(p, angle), VIEW_TILT);
          const depth = p[2]; // -1 back .. 1 front
          const sx = cx + p[0] * R;
          const sy = cy - p[1] * R;
          // travelling flow brightness along the path
          const flow = Math.pow(0.5 + 0.5 * Math.sin(u * 3 - tm * 0.0032 * st.dir * cfg.flow + st.phase), 1.6);
          const df = depth > 0 ? 0.4 + 0.6 * depth : 0.08 * (1 + depth); // front bright, back faint
          const a = Math.min(0.95, (0.22 + 0.8 * flow) * df * cfg.bright);
          if (a < 0.015) continue;
          const size = (2.0 + 3.6 * df) * (0.65 + 0.6 * flow);
          // hotter (whiter) where brightest
          const hot = Math.min(1, flow * df * 1.3);
          const r = pr + (255 - pr) * hot, g = pg + (255 - pg) * hot, b = pb + (255 - pb) * hot;
          ctx.beginPath(); ctx.arc(sx, sy, size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${r | 0},${g | 0},${b | 0},${a})`;
          ctx.fill();
          // sparks: occasional bright pinpoint riding the stream
          if ((i + Math.floor(tm * 0.05 * (si + 1))) % 17 === 0 && depth > 0.1) {
            ctx.beginPath(); ctx.arc(sx, sy, size * 0.5 + 0.6, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255,255,255,${Math.min(0.9, a + 0.3)})`;
            ctx.fill();
          }
        }
      }

      // ── speaking ripple ──
      if (cfg.ripple) {
        const wr = R * (0.6 + 0.7 * ((tm % 1500) / 1500));
        ctx.beginPath(); ctx.arc(cx, cy, wr, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${pr},${pg},${pb},${0.4 * (1 - (tm % 1500) / 1500)})`;
        ctx.lineWidth = 2; ctx.stroke();
      }

      // ── rim light on the sphere edge ──
      const rim = ctx.createRadialGradient(cx, cy, R * 0.86, cx, cy, R * 1.02);
      rim.addColorStop(0, 'rgba(0,0,0,0)');
      rim.addColorStop(0.85, `rgba(${pr},${pg},${pb},0.0)`);
      rim.addColorStop(1, `rgba(${pr},${pg},${pb},0.5)`);
      ctx.beginPath(); ctx.arc(cx, cy, R * 1.02, 0, Math.PI * 2); ctx.fillStyle = rim; ctx.fill();

      ctx.globalCompositeOperation = 'source-over';
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  const cfg = cfgFor(systemState);
  const glow = `rgb(${cfg.primary[0]},${cfg.primary[1]},${cfg.primary[2]})`;
  const ready = systemState === 'error' ? 'ATTENTION' : systemState === 'processing' ? 'PROCESSING' : systemState === 'speaking' ? 'SPEAKING' : 'READY';

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', maxWidth: SIZE, maxHeight: SIZE, aspectRatio: '1 / 1', margin: 'auto' }}>
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />

      {/* Orbital node rings outside the sphere */}
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
        <g style={{ transformOrigin: `${SIZE / 2}px ${SIZE / 2}px`, animation: 'vantaSpin 48s linear infinite' }}>
          <circle cx={SIZE / 2} cy={SIZE / 2} r={238} fill="none" stroke={glow} strokeOpacity={0.14} />
          {Array.from({ length: WORKERS }).map((_, i) => { const a = (i / WORKERS) * 2 * Math.PI; return <circle key={i} cx={SIZE / 2 + 238 * Math.cos(a)} cy={SIZE / 2 + 238 * Math.sin(a)} r={2} fill={glow} opacity={0.85} />; })}
        </g>
        <g style={{ transformOrigin: `${SIZE / 2}px ${SIZE / 2}px`, animation: 'vantaSpinRev 34s linear infinite' }}>
          <circle cx={SIZE / 2} cy={SIZE / 2} r={222} fill="none" stroke={glow} strokeOpacity={0.1} />
          {Array.from({ length: MANAGERS }).map((_, i) => { const a = (i / MANAGERS) * 2 * Math.PI; return <circle key={i} cx={SIZE / 2 + 222 * Math.cos(a)} cy={SIZE / 2 + 222 * Math.sin(a)} r={2.6} fill={VANTA.cyan} opacity={0.9} />; })}
        </g>
      </svg>

      {/* Legend */}
      <div style={{ position: 'absolute', top: 10, left: 10, fontFamily: VANTA.mono, fontSize: 8, color: VANTA.textDim, lineHeight: 1.7 }}>
        <div><span style={{ color: glow }}>●</span> W×{WORKERS} workers</div>
        <div><span style={{ color: VANTA.cyan }}>●</span> M×{MANAGERS} managers</div>
        <div><span style={{ color: '#fff' }}>◆</span> COS / GM core</div>
      </div>

      {/* READY label */}
      <div style={{ position: 'absolute', bottom: 6, left: '50%', transform: 'translateX(-50%)', fontFamily: VANTA.mono, fontSize: 13, letterSpacing: '0.36em', color: glow, textShadow: `0 0 16px ${glow}`, fontWeight: 700 }}>
        {ready}
      </div>
    </div>
  );
}
