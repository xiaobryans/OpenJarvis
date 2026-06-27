// VantaTranscript — live transcript overlay above the pipeline chain. Polls
// /v1/voice/transcript every 500ms. Hidden entirely when voice is off; clears a
// few seconds after the last word. YOU = cyan, VANTA = green.

import React from 'react';
import { apiFetch } from '../../lib/api';

interface TEvent { ts: number; speaker: string; text: string; final: boolean }

export function VantaTranscript(): React.ReactElement | null {
  const [active, setActive] = React.useState(false);
  const [events, setEvents] = React.useState<TEvent[]>([]);

  React.useEffect(() => {
    let alive = true;
    const tick = async (): Promise<void> => {
      try {
        const r = await apiFetch('/v1/voice/transcript?limit=6');
        if (!r.ok) return;
        const j = (await r.json()) as { active: boolean; events: TEvent[] };
        if (!alive) return;
        setActive(!!j.active);
        setEvents(Array.isArray(j.events) ? j.events : []);
      } catch { /* keep last state */ }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 500);
    return () => { alive = false; window.clearInterval(id); };
  }, []);

  if (!active) return null;

  // Show only the last 3 lines, and only while fresh (clears ~4s after the turn).
  const nowSec = Date.now() / 1000;
  const fresh = events.filter((e) => nowSec - (e.ts || 0) < 4.5).slice(-3);
  if (fresh.length === 0) return null;

  return (
    <div style={{
      position: 'absolute', bottom: 48, left: '50%', transform: 'translateX(-50%)',
      width: 'min(92%, 460px)', maxHeight: 54, overflow: 'hidden', zIndex: 26,
      background: 'rgba(0,0,0,0.3)', borderRadius: 4, padding: '5px 10px',
      display: 'flex', flexDirection: 'column', gap: 1, pointerEvents: 'none',
    }}>
      {fresh.map((e, i) => {
        const you = e.speaker === 'bryan';
        return (
          <div key={`${e.ts}-${i}`} style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 10, lineHeight: 1.4,
            color: you ? 'rgba(0,212,255,0.7)' : 'rgba(0,255,136,0.7)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            opacity: e.final ? 1 : 0.7,
          }}>
            <span style={{ opacity: 0.7 }}>{you ? 'YOU: ' : 'VANTA: '}</span>{e.text}
          </div>
        );
      })}
    </div>
  );
}
