// VantaBottomBar — pipeline chain (with a travelling dot) + ⬡ VANTA: command
// input + mic push-to-talk + SEND.

import React from 'react';
import { VANTA, type SystemState, type VoiceMode } from './vanta-kit';

const PIPELINE = ['CLASSIFY', 'ROUTE', 'MANAGER', 'WORKER', 'QUALITY', 'COS/GM', 'RESPOND'];

function stageColor(idx: number, activeIdx: number): string {
  if (activeIdx < 0) return VANTA.dim;
  if (idx < activeIdx) return VANTA.gr;
  if (idx === activeIdx) return VANTA.c;
  return VANTA.dim;
}

export function VantaBottomBar({ systemState, voiceMode, input, sending, onInput, onSend, onMicDown, onMicUp }: {
  systemState: SystemState; voiceMode: VoiceMode; input: string; sending: boolean;
  onInput: (v: string) => void; onSend: () => void; onMicDown: () => void; onMicUp: () => void;
}): React.ReactElement {
  const activeIdx = systemState === 'processing' ? 3 : systemState === 'speaking' ? 6 : -1;
  const micActive = voiceMode === 'listening' || voiceMode === 'active';
  const [focused, setFocused] = React.useState(false);

  return (
    <div style={{ position: 'relative', zIndex: 2, display: 'flex', flexDirection: 'column', gap: 5, padding: '5px 16px 7px', background: 'rgba(2,8,22,0.98)', borderTop: `1px solid ${VANTA.border}`, flexShrink: 0 }}>
      {/* pipeline with travelling dot */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 5, fontFamily: VANTA.orb, fontSize: 8.5, letterSpacing: '1px' }}>
        <div style={{ position: 'absolute', top: -3, left: 0, right: 80, height: 3, pointerEvents: 'none' }}>
          <span style={{ position: 'absolute', top: 0, width: 30, height: 3, marginLeft: -30, borderRadius: 2, background: 'linear-gradient(90deg, transparent, rgba(0,212,255,0.6), #00d4ff)', boxShadow: '0 0 10px #00d4ff', animation: 'vFlow 3.2s linear infinite' }} />
        </div>
        {PIPELINE.map((s, i) => (
          <React.Fragment key={s}>
            <span style={{ color: stageColor(i, activeIdx), textShadow: i === activeIdx ? `0 0 8px ${VANTA.c}` : 'none' }}>{s}</span>
            {i < PIPELINE.length - 1 && <span style={{ color: 'rgba(0,212,255,0.3)' }}>→</span>}
          </React.Fragment>
        ))}
        <span style={{ marginLeft: 'auto', fontFamily: VANTA.mono, color: micActive ? VANTA.gr : VANTA.dim, fontWeight: 600 }}>{micActive ? '● LISTENING' : '○ MIC IDLE'}</span>
      </div>

      {/* command input */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', flex: 1, gap: 8, background: 'rgba(2,10,24,0.85)', border: `1px solid ${focused ? VANTA.c : VANTA.border}`, borderRadius: 4, padding: '0 12px', boxShadow: focused ? '0 0 14px rgba(0,212,255,0.35), inset 0 0 8px rgba(0,212,255,0.08)' : 'none', transition: 'box-shadow 0.2s, border-color 0.2s' }}>
          <span style={{ fontFamily: VANTA.orb, fontSize: 11, color: VANTA.c, textShadow: `0 0 8px ${VANTA.c}`, whiteSpace: 'nowrap' }}>⬡ VANTA:</span>
          <input
            value={input}
            onChange={(e) => onInput(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
            placeholder="Command VANTA…  (Enter to send · hold 🎤 to talk)"
            style={{ flex: 1, background: 'transparent', border: 'none', color: VANTA.text, fontFamily: VANTA.mono, fontSize: 12.5, padding: '9px 0', outline: 'none' }}
          />
        </div>
        <button onMouseDown={onMicDown} onMouseUp={onMicUp} onMouseLeave={() => micActive && onMicUp()} title="Hold to talk"
          style={{ width: 40, height: 40, borderRadius: 4, border: `1px solid ${micActive ? VANTA.gr : VANTA.border}`, background: micActive ? 'rgba(0,255,136,0.16)' : 'rgba(2,10,24,0.85)', color: micActive ? VANTA.gr : VANTA.text, fontSize: 16, cursor: 'pointer', boxShadow: micActive ? `0 0 14px ${VANTA.gr}66` : 'none' }}>🎤</button>
        <button onClick={onSend} disabled={sending || !input.trim()}
          style={{ height: 40, padding: '0 20px', borderRadius: 4, border: 'none', background: sending || !input.trim() ? 'rgba(0,212,255,0.25)' : VANTA.c, color: '#021018', fontFamily: VANTA.orb, fontWeight: 700, fontSize: 12, letterSpacing: '2px', cursor: sending || !input.trim() ? 'default' : 'pointer', boxShadow: sending || !input.trim() ? 'none' : `0 0 14px ${VANTA.c}66` }}>{sending ? '…' : 'SEND'}</button>
      </div>
    </div>
  );
}
