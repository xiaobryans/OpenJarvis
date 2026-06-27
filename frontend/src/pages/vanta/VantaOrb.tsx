// VantaOrb — center cluster: state label + readout, the glowing core orb with
// three spinning orbital rings and three pulse rings, the live transcript
// overlay, a 30-bar waveform, and the processing pipeline chain. Faithful port
// of VANTA-export_dc.html. Orb/waveform visuals are driven by the voice-state
// class on #vanta-root (see vanta-hud-styles).

import React from 'react';
import { VantaTranscript } from './VantaTranscript';

const PIPELINE: { label: string; tone: 'green' | 'cyan' | 'dim' | 'faint' }[] = [
  { label: 'CLASSIFY', tone: 'green' },
  { label: 'ROUTE', tone: 'green' },
  { label: 'MANAGER', tone: 'cyan' },
  { label: 'WORKER', tone: 'dim' },
  { label: 'QUALITY', tone: 'dim' },
  { label: 'COS/GM', tone: 'dim' },
  { label: 'RESPOND', tone: 'faint' },
];
const TONE: Record<string, { color: string; border: string }> = {
  green: { color: 'rgba(0,255,136,0.7)', border: 'rgba(0,255,136,0.3)' },
  cyan: { color: 'rgba(0,212,255,0.7)', border: 'rgba(0,212,255,0.4)' },
  dim: { color: 'rgba(0,212,255,0.4)', border: 'rgba(0,212,255,0.15)' },
  faint: { color: 'rgba(0,212,255,0.25)', border: 'rgba(0,212,255,0.08)' },
};

// 30 waveform bars, cyan/purple alternating, deterministic heights + delays.
const BARS = Array.from({ length: 30 }, (_, i) => {
  const base = 6 + Math.round(18 * Math.abs(Math.sin(i * 0.7)));
  return { h: base, delay: (i % 10) * 0.09, color: i % 2 === 0 ? '#00d4ff' : '#7c3aed' };
});

export function VantaOrb({ stateLabel, stateColor, readout, orbLabel }: {
  stateLabel: string; stateColor: string; readout: string; orbLabel: string;
}): React.ReactElement {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
      {/* State label + readout */}
      <div style={{ position: 'absolute', top: 16, fontFamily: "'Exo 2',sans-serif", fontSize: 9, letterSpacing: '10px', color: stateColor, textShadow: `0 0 15px ${stateColor}`, zIndex: 30, textTransform: 'uppercase', transition: 'color .4s,text-shadow .4s' }}>{stateLabel}</div>
      <div style={{ position: 'absolute', top: 36, fontSize: 7, letterSpacing: '2px', color: 'rgba(0,212,255,0.4)', zIndex: 30 }}>{readout}</div>

      {/* ORB — ported verbatim from VANTA-export_dc.html */}
      <div style={{ position: 'relative', width: 260, height: 260, flexShrink: 0 }}>
        {/* Outer breathing glow halo */}
        <div style={{ position: 'absolute', inset: -60, borderRadius: '50%', background: 'radial-gradient(circle,rgba(0,160,255,0.12) 0%,rgba(0,80,200,0.05) 45%,transparent 70%)', animation: 'statusPulse 4s ease-in-out infinite' }} />
        {/* Orbital rings */}
        <svg style={{ position: 'absolute', inset: -40, width: 'calc(100% + 80px)', height: 'calc(100% + 80px)' }} viewBox="0 0 340 340" xmlns="http://www.w3.org/2000/svg">
          <g className="v-ring-fast" style={{ transformBox: 'fill-box', transformOrigin: 'center', animation: 'radarSpin 12s linear infinite' }}>
            <ellipse cx="170" cy="170" rx="155" ry="50" fill="none" stroke="rgba(0,212,255,0.38)" strokeWidth="1.3" />
            <circle cx="325" cy="170" r="5" fill="#00d4ff" opacity="0.95" />
          </g>
          <g className="v-ring-fast" style={{ transformBox: 'fill-box', transformOrigin: 'center', animation: 'radarSpin 20s linear infinite reverse' }}>
            <ellipse cx="170" cy="170" rx="138" ry="44" fill="none" stroke="rgba(124,58,237,0.35)" strokeWidth="1" transform="rotate(55,170,170)" />
            <circle cx="308" cy="170" r="3.5" fill="rgba(124,58,237,0.85)" />
          </g>
          <g className="v-ring-fast" style={{ transformBox: 'fill-box', transformOrigin: 'center', animation: 'radarSpin 34s linear infinite' }}>
            <ellipse cx="170" cy="170" rx="122" ry="38" fill="none" stroke="rgba(0,212,255,0.18)" strokeWidth="0.8" transform="rotate(-38,170,170)" />
            <circle cx="292" cy="170" r="3" fill="rgba(0,245,212,0.8)" />
          </g>
        </svg>
        {/* Core orb: white-hot center → cyan → deep blue → near-black edge */}
        <div id="orb-core" style={{
          position: 'absolute', inset: 30, borderRadius: '50%',
          background: 'radial-gradient(circle at 34% 28%,rgba(255,255,255,0.95) 0%,rgba(160,235,255,0.9) 6%,rgba(0,190,255,0.88) 22%,rgba(0,120,220,0.92) 48%,rgba(0,50,140,0.96) 72%,rgba(0,12,45,1) 100%)',
          boxShadow: '0 0 35px rgba(0,190,255,0.8),0 0 70px rgba(0,160,255,0.55),0 0 140px rgba(0,120,220,0.3),inset 0 0 25px rgba(0,80,180,0.4)',
          animation: 'statusPulse 3.5s ease-in-out infinite',
        }} />
        {/* Pulse rings */}
        <div className="v-pulse-ring" style={{ position: 'absolute', inset: 20, borderRadius: '50%', border: '1px solid rgba(0,212,255,0.45)', animation: 'fadeUpIn 4s ease-out infinite' }} />
        <div className="v-pulse-ring" style={{ position: 'absolute', inset: 10, borderRadius: '50%', border: '1px solid rgba(0,212,255,0.25)', animation: 'fadeUpIn 4s ease-out infinite 1.33s' }} />
        <div className="v-pulse-ring" style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '1px solid rgba(0,212,255,0.12)', animation: 'fadeUpIn 4s ease-out infinite 2.66s' }} />
      </div>

      {/* Orb label */}
      <div style={{ marginTop: 16, fontFamily: "'Exo 2',sans-serif", fontSize: 8, letterSpacing: '8px', color: 'rgba(0,212,255,0.5)', textTransform: 'uppercase' }}>{orbLabel}</div>

      {/* Live transcript overlay */}
      <VantaTranscript />

      {/* Pipeline chain */}
      <div style={{ position: 'absolute', bottom: 48, left: '50%', transform: 'translateX(-50%)', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap', gap: 4 }}>
        {PIPELINE.map((p, i) => (
          <React.Fragment key={p.label}>
            <span style={{ fontSize: 7, letterSpacing: '1px', color: TONE[p.tone].color, padding: '2px 6px', border: `1px solid ${TONE[p.tone].border}`, fontFamily: "'Space Mono',monospace" }}>{p.label}</span>
            {i < PIPELINE.length - 1 && <span style={{ color: 'rgba(0,212,255,0.3)', fontSize: 10 }}>→</span>}
          </React.Fragment>
        ))}
      </div>

      {/* Waveform */}
      <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', display: 'flex', alignItems: 'center', gap: 2, height: 26 }}>
        {BARS.map((b, i) => (
          <div key={i} className="v-wavebar" style={{ width: 2, height: b.h, background: b.color, boxShadow: `0 0 4px ${b.color}`, borderRadius: 1, animationDelay: `${b.delay}s` }} />
        ))}
      </div>
    </div>
  );
}
