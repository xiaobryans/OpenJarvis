// VantaBottomBar — #cb command bar: ⬡ VANTA: prompt, input, status indicators
// (API / CONNECTORS / MODEL / VOICE), mic, SEND. Ports the reference markup.

import React from 'react';

export function VantaBottomBar({ input, onInput, onSend, onMic, micActive, apiOk, connText, model, voiceOn }: {
  input: string; onInput: (v: string) => void; onSend: () => void; onMic: () => void; micActive: boolean;
  apiOk: boolean; connText: string; model: string; voiceOn: boolean;
}): React.ReactElement {
  return (
    <div id="cb">
      <span id="chl">⬡ VANTA:</span>
      <input id="chi" type="text" autoComplete="off" placeholder="Command VANTA..." value={input}
        onChange={(e) => onInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onSend(); }} />
      <div className="sis">
        <span className="si">API <span className={apiOk ? 'sg' : 'sa'}>{apiOk ? 'OK' : 'DOWN'}</span></span>
        <span className="si">CONNECTORS <span className="sc">{connText}</span></span>
        <span className="si">MODEL <span className="sc">{model}</span></span>
        <span className="si">VOICE <span className={voiceOn ? 'sg' : 'sa'}>{voiceOn ? 'ON' : 'OFF'}</span></span>
      </div>
      <button id="micbtn" onClick={onMic} style={micActive ? { color: 'var(--gr)', borderColor: 'var(--gr)' } : undefined}>🎤</button>
      <button id="sndbtn" onClick={onSend}>SEND</button>
    </div>
  );
}
