// vanta-hud-styles — global CSS + keyframes for the VANTA HUD, a faithful port
// of VANTA-export_dc.html. Scoped under #vanta-root so the styling never leaks
// into the rest of the app. Orb keyframes (radarSpin / statusPulse / fadeUpIn)
// are copied verbatim from the reference so the orb renders identically.

import React from 'react';

export function VantaHudStyles(): React.ReactElement {
  return (
    <style>{`
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Exo+2:wght@300;400;600;700;900&display=swap');

#vanta-root, #vanta-root *, #vanta-root *::before, #vanta-root *::after { margin:0; padding:0; box-sizing:border-box; }
#vanta-root {
  position:fixed; inset:0; width:100%; height:100%; overflow:hidden;
  font-family:'Space Mono','SF Mono',monospace; color:#8ec8e8;
  background:#030912;
  background-image:
    radial-gradient(ellipse at 18% 65%,rgba(0,80,180,0.09) 0%,transparent 55%),
    radial-gradient(ellipse at 82% 18%,rgba(100,40,220,0.07) 0%,transparent 45%),
    radial-gradient(circle,rgba(0,212,255,0.035) 1px,transparent 1px);
  background-size:100% 100%,100% 100%,30px 30px;
}
#vanta-root ::-webkit-scrollbar { width:3px; height:3px; }
#vanta-root ::-webkit-scrollbar-thumb { background:rgba(0,212,255,0.22); border-radius:2px; }
#vanta-root ::-webkit-scrollbar-track { background:transparent; }
#vanta-root input { outline:none; transition:border-color 0.2s,box-shadow 0.2s; }
#vanta-root input::placeholder { color:rgba(0,212,255,0.22); font-family:'Space Mono',monospace; font-size:11px; letter-spacing:0.5px; }
#vanta-root input:focus { border-color:rgba(0,212,255,0.42)!important; box-shadow:0 0 0 1px rgba(0,212,255,0.08),0 0 16px rgba(0,212,255,0.1)!important; }

/* ── Reference keyframes (from VANTA-export_dc.html) ──
   radarSpin is a pure rotation; the rings set transform-box:fill-box +
   transform-origin:center so they orbit concentrically around the sphere.
   (The reference's translate(-50%,-50%) shifts the rotating <g> off-center
   in this SVG context, so it is dropped — the orbit is the intended look.) */
@keyframes radarSpin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
@keyframes statusPulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.2;transform:scale(0.55)} }
@keyframes fadeUpIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
@keyframes vGlitch {
  0%,88%,100%{transform:none;text-shadow:0 0 22px rgba(0,212,255,0.45)}
  90%{transform:translate(-2px,0) skewX(0.6deg);text-shadow:2px 0 rgba(255,60,160,0.55)}
  92%{transform:translate(2px,0) skewX(-0.5deg);text-shadow:-2px 0 rgba(0,255,220,0.5)}
  95%{transform:none;text-shadow:0 0 22px rgba(0,212,255,0.45)}
}
@keyframes vScanlinePan { 0%{transform:translateY(-100%)} 100%{transform:translateY(200vh)} }
@keyframes vWaveBar { 0%,100%{transform:scaleY(0.22)} 50%{transform:scaleY(1)} }

/* ── Per-voice-state orb overrides (idle = pristine reference look) ── */
#vanta-root.v-standby #orb-core { filter:saturate(0.6) brightness(0.72); }
#vanta-root.v-listening #orb-core { animation-duration:3.4s; }
#vanta-root.v-wake #orb-core { animation:none!important; filter:brightness(1.7);
  box-shadow:0 0 60px rgba(255,255,255,0.95),0 0 130px rgba(0,200,255,0.7),inset 0 0 25px rgba(255,255,255,0.5)!important; }
#vanta-root.v-recording #orb-core { animation-duration:1.05s; filter:brightness(1.25) saturate(1.3); }
#vanta-root.v-thinking #orb-core { filter:hue-rotate(150deg) saturate(1.25) brightness(1.05); animation-duration:1.5s; }
#vanta-root.v-speaking #orb-core { animation-duration:1.9s; filter:brightness(1.15); }

/* Orbital rings spin faster while thinking; pulse rings ripple faster while speaking */
#vanta-root.v-thinking .v-ring-fast { animation-duration:5s!important; }
#vanta-root.v-speaking .v-pulse-ring { animation-duration:1.6s!important; }

/* Waveform: animated when active, frozen + dim in standby */
#vanta-root .v-wavebar { animation:vWaveBar 0.9s ease-in-out infinite; transform-origin:center bottom; }
#vanta-root.v-static-wave .v-wavebar { animation:none!important; transform:scaleY(0.16); opacity:0.4; }
    `}</style>
  );
}
