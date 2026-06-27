// VantaHistoryModal — Cmd+K unified history viewer. Glassmorphism HUD modal with
// corner brackets, search (cyan focus), 🎤 voice + ⌨ typed entries newest-first,
// click-to-expand, Esc/Cmd+K to close. Merges backend voice history (/v1/history)
// with the cockpit session's typed turns.

import React from 'react';
import { apiFetch } from '../../lib/api';

export interface HistItem { ts: number; speaker: string; text: string; mode: string }

function fmtTime(ts: number): string {
  try { return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' }).format(new Date(ts * 1000)); }
  catch { return ''; }
}
function Bracket({ corner }: { corner: 'tl' | 'br' }): React.ReactElement {
  const base: React.CSSProperties = { position: 'absolute', width: 16, height: 16, pointerEvents: 'none' };
  return <span style={corner === 'tl'
    ? { ...base, top: -1, left: -1, borderTop: '2px solid #00D4FF', borderLeft: '2px solid #00D4FF' }
    : { ...base, bottom: -1, right: -1, borderBottom: '2px solid #00D4FF', borderRight: '2px solid #00D4FF' }} />;
}

export function VantaHistoryModal({ open, onClose, typed }: { open: boolean; onClose: () => void; typed: HistItem[] }): React.ReactElement | null {
  const [voice, setVoice] = React.useState<HistItem[]>([]);
  const [query, setQuery] = React.useState('');
  const [expanded, setExpanded] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      try {
        const r = await apiFetch('/v1/history?limit=100');
        if (!r.ok) return;
        const j = (await r.json()) as { entries: HistItem[] };
        if (alive) setVoice(Array.isArray(j.entries) ? j.entries : []);
      } catch { /* show typed only */ }
    })();
    setTimeout(() => inputRef.current?.focus(), 30);
    return () => { alive = false; };
  }, [open]);

  if (!open) return null;

  const merged = [...voice, ...typed].sort((a, b) => (b.ts || 0) - (a.ts || 0));
  const q = query.trim().toLowerCase();
  const items = q ? merged.filter((m) => (m.text || '').toLowerCase().includes(q)) : merged;

  return (
    <div onClick={onClose} style={{ position: 'absolute', inset: 0, zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(1,5,12,0.55)', backdropFilter: 'blur(2px)' }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        position: 'relative', width: 640, maxWidth: '92vw', maxHeight: '70vh', display: 'flex', flexDirection: 'column',
        background: 'rgba(4,16,40,0.92)', backdropFilter: 'blur(22px) saturate(180%)', WebkitBackdropFilter: 'blur(22px) saturate(180%)',
        border: '1px solid rgba(0,200,255,0.22)', borderRadius: 4,
        boxShadow: '0 0 30px rgba(0,200,255,0.12), 0 20px 60px rgba(0,0,0,0.5)',
      }}>
        <Bracket corner="tl" /><Bracket corner="br" />

        {/* header + search */}
        <div style={{ padding: '12px 14px 8px', borderBottom: '1px solid rgba(0,180,255,0.12)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 9, fontWeight: 600, letterSpacing: '3px', color: '#00D4FF' }}>HISTORY — UNIFIED</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(142,200,232,0.38)' }}>{items.length} entries · Esc to close</span>
          </div>
          <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search history…"
            style={{ width: '100%', background: 'rgba(2,10,24,0.85)', border: '1px solid rgba(0,200,255,0.28)', borderRadius: 4, color: '#e6f2ff', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, padding: '8px 12px', outline: 'none' }}
            onFocus={(e) => { e.currentTarget.style.borderColor = '#00D4FF'; e.currentTarget.style.boxShadow = '0 0 12px rgba(0,212,255,0.3)'; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = 'rgba(0,200,255,0.28)'; e.currentTarget.style.boxShadow = 'none'; }} />
        </div>

        {/* list */}
        <div className="vanta-scroll" style={{ overflowY: 'auto', padding: '6px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {items.length === 0 && <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(142,200,232,0.38)', padding: 12, fontStyle: 'italic' }}>No history yet.</div>}
          {items.map((m, i) => {
            const voiceEntry = m.mode === 'voice';
            const you = m.speaker === 'bryan' || m.speaker === 'you';
            const key = `${m.ts}-${i}`;
            const isOpen = expanded === key;
            return (
              <div key={key} onClick={() => setExpanded(isOpen ? null : key)} style={{ display: 'flex', gap: 8, padding: '6px 8px', borderLeft: `2px solid ${you ? 'rgba(0,212,255,0.4)' : 'rgba(0,255,136,0.4)'}`, cursor: 'pointer', background: isOpen ? 'rgba(0,212,255,0.05)' : 'transparent' }}>
                <span style={{ fontSize: 11, flexShrink: 0 }}>{voiceEntry ? '🎤' : '⌨'}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 8, letterSpacing: '1.5px', color: you ? '#00D4FF' : '#00FF88' }}>{you ? 'YOU' : 'VANTA'}</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: 'rgba(142,200,232,0.38)' }}>{fmtTime(m.ts)}</span>
                  </div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#8EC8E8', whiteSpace: isOpen ? 'normal' : 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', wordBreak: isOpen ? 'break-word' : 'normal' }}>{m.text}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
