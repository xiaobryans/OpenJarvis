// VantaBottomBar — full-width footer: live pipeline status chain + command
// input (text, send, mic push-to-talk, voice indicator).

import React from 'react';
import { VANTA, type SystemState, type VoiceMode } from './vanta-kit';

const PIPELINE = ['CLASSIFY', 'ROUTE', 'MANAGER', 'WORKER', 'QUALITY', 'COS/GM', 'RESPOND'];

function stageColor(idx: number, activeIdx: number): string {
  if (activeIdx < 0) return VANTA.textDim;
  if (idx < activeIdx) return VANTA.green;
  if (idx === activeIdx) return VANTA.cyan;
  return VANTA.textDim;
}

export function VantaBottomBar({
  systemState,
  voiceMode,
  input,
  sending,
  onInput,
  onSend,
  onMicDown,
  onMicUp,
}: {
  systemState: SystemState;
  voiceMode: VoiceMode;
  input: string;
  sending: boolean;
  onInput: (v: string) => void;
  onSend: () => void;
  onMicDown: () => void;
  onMicUp: () => void;
}): React.ReactElement {
  // Map system state to a pipeline highlight position (illustrative live chain).
  const activeIdx = systemState === 'processing' ? 3 : systemState === 'speaking' ? 6 : systemState === 'error' ? -1 : -1;
  const micActive = voiceMode === 'listening' || voiceMode === 'active';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '8px 16px 10px',
        background: 'rgba(8,13,26,0.7)',
        backdropFilter: 'blur(14px)',
        borderTop: `1px solid ${VANTA.panelBorder}`,
        flexShrink: 0,
      }}
    >
      {/* Pipeline chain */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: VANTA.mono, fontSize: 9 }}>
        {PIPELINE.map((stage, i) => (
          <React.Fragment key={stage}>
            <span style={{ color: stageColor(i, activeIdx), letterSpacing: '0.08em', textShadow: i === activeIdx ? `0 0 8px ${VANTA.cyan}` : 'none' }}>{stage}</span>
            {i < PIPELINE.length - 1 && <span style={{ color: 'rgba(0,212,255,0.25)' }}>→</span>}
          </React.Fragment>
        ))}
        <span style={{ marginLeft: 'auto', color: micActive ? VANTA.green : VANTA.textDim, fontWeight: 700 }}>
          {micActive ? '● LISTENING' : '○ MIC IDLE'}
        </span>
      </div>

      {/* Command input */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          value={input}
          onChange={(e) => onInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          placeholder="Command VANTA…  (Enter to send · hold 🎤 to talk)"
          style={{
            flex: 1,
            background: 'rgba(4,8,18,0.8)',
            border: `1px solid ${VANTA.panelBorder}`,
            borderRadius: 8,
            color: VANTA.text,
            fontFamily: VANTA.mono,
            fontSize: 13,
            padding: '10px 14px',
            outline: 'none',
          }}
        />
        <button
          onMouseDown={onMicDown}
          onMouseUp={onMicUp}
          onMouseLeave={() => micActive && onMicUp()}
          title="Hold to talk (push-to-talk)"
          style={{
            width: 42,
            height: 42,
            borderRadius: 8,
            border: `1px solid ${micActive ? VANTA.green : VANTA.panelBorder}`,
            background: micActive ? 'rgba(0,255,136,0.16)' : 'rgba(4,8,18,0.8)',
            color: micActive ? VANTA.green : VANTA.text,
            fontSize: 17,
            cursor: 'pointer',
            boxShadow: micActive ? `0 0 14px ${VANTA.green}66` : 'none',
          }}
        >🎤</button>
        <button
          onClick={onSend}
          disabled={sending || !input.trim()}
          style={{
            height: 42,
            padding: '0 20px',
            borderRadius: 8,
            border: 'none',
            background: sending || !input.trim() ? 'rgba(0,212,255,0.25)' : VANTA.cyan,
            color: '#001018',
            fontFamily: VANTA.mono,
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: '0.1em',
            cursor: sending || !input.trim() ? 'default' : 'pointer',
          }}
        >{sending ? '…' : 'SEND'}</button>
      </div>
    </div>
  );
}
