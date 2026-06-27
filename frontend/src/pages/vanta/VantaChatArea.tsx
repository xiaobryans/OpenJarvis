// VantaChatPanel — slide-up chat conversation that sits just above the command
// input bar (not in the center column, so it never overlaps the orb). Controlled
// by `open`; the page handles auto-show/auto-hide/Esc + the unread indicator.
// Glassmorphism, Bryan right/cyan, VANTA left/green, Space Mono 10px.

import React from 'react';
import type { HistItem } from './VantaHistoryModal';

export function VantaChatPanel({ messages, open }: { messages: HistItem[]; open: boolean }): React.ReactElement {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const recent = messages.slice(-30);

  React.useEffect(() => {
    if (open && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [messages.length, open]);

  return (
    <div
      ref={ref}
      style={{
        position: 'absolute', left: '50%', bottom: 60, zIndex: 120,
        width: 'min(620px, 78%)', maxHeight: 180, overflowY: 'auto',
        transform: `translateX(-50%) translateY(${open ? '0' : '115%'})`,
        opacity: open ? 1 : 0, pointerEvents: open ? 'auto' : 'none',
        transition: 'transform 0.35s cubic-bezier(0.2,0.8,0.2,1), opacity 0.3s ease',
        background: 'linear-gradient(135deg, rgba(4,16,40,0.55), rgba(4,16,40,0.32))',
        backdropFilter: 'blur(22px) saturate(160%)', WebkitBackdropFilter: 'blur(22px) saturate(160%)',
        border: '1px solid rgba(0,212,255,0.2)', borderRadius: 8,
        boxShadow: '0 0 24px rgba(0,200,255,0.08), 0 12px 32px rgba(0,0,0,0.4)',
        fontFamily: "'Space Mono',monospace", fontSize: 10, lineHeight: 1.5,
        display: 'flex', flexDirection: 'column', padding: '6px 10px',
      }}
    >
      {recent.length === 0 && (
        <div style={{ color: 'rgba(0,212,255,0.35)', textAlign: 'center', padding: '6px 0' }}>No messages yet.</div>
      )}
      {recent.map((m, i) => {
        const you = m.speaker === 'you' || m.speaker === 'bryan';
        return (
          <div
            key={`${m.ts}-${i}`}
            style={{
              display: 'flex', justifyContent: you ? 'flex-end' : 'flex-start',
              borderTop: i === 0 ? 'none' : '1px solid rgba(0,212,255,0.06)',
              padding: '4px 2px', animation: 'fadeUpIn 0.3s ease-out',
            }}
          >
            <div style={{
              maxWidth: '82%', textAlign: you ? 'right' : 'left',
              color: you ? 'rgba(0,212,255,0.92)' : 'rgba(0,255,136,0.92)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              <span style={{ opacity: 0.5, fontSize: 8, letterSpacing: '1px' }}>{you ? 'YOU' : 'VANTA'}</span>
              <div>{m.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
