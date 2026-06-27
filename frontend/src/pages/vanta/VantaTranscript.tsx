// VantaTranscript — live transcript overlay above the waveform. Polls
// /v1/voice/transcript (the backend serves a JSON snapshot, not SSE) and shows
// the most recent turns: YOU in cyan, VANTA in green. Fades out ~3s after the
// last word of a turn. Faithful port of VANTA-export_dc.html's transcript layer.

import React from 'react';
import { apiFetch } from '../../lib/api';

interface TEvent { ts: number; speaker: string; text: string; final: boolean }

export function VantaTranscript(): React.ReactElement {
  const [events, setEvents] = React.useState<TEvent[]>([]);
  const [active, setActive] = React.useState(false);

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

  // Only show fresh lines; clears ~3s after the turn ends.
  const nowSec = Date.now() / 1000;
  const fresh = active ? events.filter((e) => nowSec - (e.ts || 0) < 3).slice(-3) : [];
  const show = fresh.length > 0;

  return (
    <div style={{
      position: 'absolute', bottom: 80, left: '10%', right: '10%', textAlign: 'center',
      fontSize: 10, fontFamily: "'Space Mono',monospace", minHeight: 18,
      opacity: show ? 1 : 0, transition: 'opacity 0.3s', pointerEvents: 'none', zIndex: 26,
    }}>
      {fresh.map((e, i) => {
        const you = e.speaker === 'bryan' || e.speaker === 'you';
        return (
          <div key={`${e.ts}-${i}`} style={{
            color: you ? 'rgba(0,212,255,0.85)' : 'rgba(0,255,136,0.85)',
            lineHeight: 1.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            opacity: e.final ? 1 : 0.7,
          }}>
            <span style={{ opacity: 0.65 }}>{you ? 'YOU: ' : 'VANTA: '}</span>{e.text}
          </div>
        );
      })}
    </div>
  );
}
