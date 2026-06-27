// VantaChatArea — typed chat conversation, shown in the center column below the
// orb and above the pipeline chain (FIX 2). Last 10 exchanges, Bryan right/cyan,
// VANTA left/green, Space Mono, subtle separators, new lines animate in, and the
// view auto-scrolls to the latest message.

import React from 'react';
import type { HistItem } from './VantaHistoryModal';

export function VantaChatArea({ messages }: { messages: HistItem[] }): React.ReactElement | null {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const recent = messages.slice(-10);

  React.useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight; // auto-scroll to latest
  }, [messages.length]);

  if (recent.length === 0) return null;

  return (
    <div
      ref={ref}
      style={{
        position: 'absolute', bottom: 78, left: '50%', transform: 'translateX(-50%)',
        width: 'min(86%, 560px)', maxHeight: 200, overflowY: 'auto', zIndex: 24,
        display: 'flex', flexDirection: 'column', gap: 0,
        fontFamily: "'Space Mono',monospace", fontSize: 11, lineHeight: 1.5,
        padding: '4px 2px',
      }}
    >
      {recent.map((m, i) => {
        const you = m.speaker === 'you' || m.speaker === 'bryan';
        return (
          <div
            key={`${m.ts}-${i}`}
            style={{
              display: 'flex', justifyContent: you ? 'flex-end' : 'flex-start',
              borderTop: i === 0 ? 'none' : '1px solid rgba(0,212,255,0.06)',
              padding: '5px 2px', animation: 'fadeUpIn 0.35s ease-out',
            }}
          >
            <div style={{
              maxWidth: '82%', textAlign: you ? 'right' : 'left',
              color: you ? 'rgba(0,212,255,0.92)' : 'rgba(0,255,136,0.92)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              <span style={{ opacity: 0.55, fontSize: 8, letterSpacing: '1px' }}>
                {you ? 'YOU' : 'VANTA'}
              </span>
              <div>{m.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
