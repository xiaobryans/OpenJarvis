// VantaBackground — full-screen scanline overlay + a horizontal scan light that
// pans down the viewport. Faithful port of VANTA-export_dc.html. Both layers are
// pointer-events:none so they never intercept clicks.

import React from 'react';

export function VantaBackground(): React.ReactElement {
  return (
    <>
      {/* Full-screen scanlines */}
      <div style={{
        position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 200,
        background: 'repeating-linear-gradient(0deg,transparent 0px,transparent 3px,rgba(0,0,0,0.022) 3px,rgba(0,0,0,0.022) 4px)',
      }} />
      {/* Horizontal scan light */}
      <div style={{
        position: 'fixed', left: 0, right: 0, height: 1,
        background: 'linear-gradient(to right,transparent,rgba(0,212,255,0.11),transparent)',
        pointerEvents: 'none', zIndex: 201, animation: 'vScanlinePan 10s linear infinite',
      }} />
    </>
  );
}
