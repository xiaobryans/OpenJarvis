// VantaTopBar — #tb header: ⬡ VANTA · NEURAL COMMAND · MISSION CONTROL · clock ·
// weather · voice status. Ports the reference markup.

import React from 'react';

export function VantaTopBar({ time, weatherText, voiceText, voiceColor }: { time: string; weatherText: string; voiceText: string; voiceColor: string }): React.ReactElement {
  return (
    <nav id="tb">
      <div className="tbl"><span className="tbi">⬡</span>VANTA</div>
      <span className="tbv">NEURAL COMMAND</span>
      <div className="tbc">MISSION CONTROL</div>
      <div className="tbs" />
      <span id="clk">{time}</span>
      <span className="tbi2">{weatherText}</span>
      <span className="tbi2" style={{ color: voiceColor }}>{voiceText}</span>
    </nav>
  );
}
