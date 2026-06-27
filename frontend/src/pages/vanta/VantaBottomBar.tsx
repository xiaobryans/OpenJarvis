// VantaBottomBar — command bar: "⬡ VANTA:" prompt, free-text input (Enter to
// send), live API / MODEL / VOICE status, mic (push-to-talk) and SEND buttons.
// Faithful port of VANTA-export_dc.html, wired to the cockpit chat + voice.

import React from 'react';

export function VantaBottomBar({ input, onInput, onSend, onMic, micActive, apiOk, model, voiceOn }: {
  input: string; onInput: (v: string) => void; onSend: () => void; onMic: () => void; micActive: boolean;
  apiOk: boolean; model: string; voiceOn: boolean;
}): React.ReactElement {
  return (
    <div style={{
      height: 52, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 10,
      borderTop: '1px solid rgba(0,212,255,0.1)', background: 'rgba(2,10,24,0.94)',
    }}>
      <span style={{ color: '#00d4ff', fontSize: 10, letterSpacing: '2px', whiteSpace: 'nowrap', animation: 'vStatusPulse 2.5s ease-in-out infinite' }}>⬡ VANTA:</span>
      <input
        type="text" autoComplete="off" placeholder="Command VANTA..." value={input}
        onChange={(e) => onInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onSend(); }}
        style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: '1px solid rgba(0,212,255,0.2)', color: '#8ec8e8', fontFamily: "'Space Mono',monospace", fontSize: 11, padding: '4px 0' }}
      />
      <div style={{ display: 'flex', gap: 6, borderLeft: '1px solid rgba(0,212,255,0.1)', paddingLeft: 10, fontSize: 8, color: 'rgba(0,212,255,0.4)' }}>
        <span>API <span style={{ color: apiOk ? '#00ff88' : '#FF3355' }}>{apiOk ? 'OK' : 'ERROR'}</span></span>
        <span>MODEL <span style={{ color: '#00d4ff' }}>{model}</span></span>
        <span>VOICE <span style={{ color: voiceOn ? '#00ff88' : 'rgba(0,212,255,0.4)' }}>{voiceOn ? 'ON' : 'OFF'}</span></span>
      </div>
      <button onClick={onMic} style={{ padding: '6px 10px', border: `1px solid ${micActive ? '#00ff88' : 'rgba(0,212,255,0.3)'}`, background: 'transparent', color: micActive ? '#00ff88' : 'rgba(0,212,255,0.5)', fontSize: 14, cursor: 'pointer', borderRadius: 2 }}>🎤</button>
      <button onClick={onSend} style={{ padding: '6px 16px', border: '1px solid #00d4ff', background: 'rgba(0,212,255,0.08)', color: '#00d4ff', fontFamily: "'Exo 2',sans-serif", fontSize: 9, letterSpacing: '3px', cursor: 'pointer', borderRadius: 2 }}>SEND</button>
    </div>
  );
}
