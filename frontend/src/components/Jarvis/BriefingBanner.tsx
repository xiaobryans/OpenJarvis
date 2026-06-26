/**
 * BriefingBanner — shows Bryan's latest morning briefing in the cockpit.
 *
 * - Fetches /v1/briefing/latest on mount.
 * - Shows the briefing prominently ONLY if it's unread (its id is newer than
 *   the last id the user dismissed, stored in localStorage).
 * - Displays when it was generated.
 * - "Dismiss" marks it read (persists the id) and hides it until the next
 *   briefing fires.
 *
 * Pulls from ~/.openjarvis/briefings/latest.md via the backend endpoint.
 */
import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { apiFetch } from '../../lib/api';

const DISMISS_KEY = 'vanta_briefing_dismissed_id';

interface BriefingResponse {
  exists: boolean;
  markdown: string;
  generated_at: string | null;
  id: number | null;
}

function formatWhen(iso: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function BriefingBanner() {
  const [briefing, setBriefing] = useState<BriefingResponse | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch('/v1/briefing/latest');
        if (!res.ok) return;
        const data: BriefingResponse = await res.json();
        if (cancelled) return;
        if (data.exists && data.id != null) {
          const lastDismissed = Number(localStorage.getItem(DISMISS_KEY) || '0');
          if (data.id > lastDismissed) {
            setBriefing(data);
            setDismissed(false);
          }
        }
      } catch {
        /* briefing is best-effort; never break the cockpit */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!briefing || dismissed) return null;

  const handleDismiss = () => {
    if (briefing.id != null) {
      localStorage.setItem(DISMISS_KEY, String(briefing.id));
    }
    setDismissed(true);
  };

  return (
    <div
      className="briefing-banner"
      style={{
        position: 'fixed',
        top: 14,
        left: '50%',
        transform: 'translateX(-50%)',
        width: 'min(720px, calc(100% - 32px))',
        maxHeight: '70vh',
        overflowY: 'auto',
        border: '1px solid rgba(96,165,250,0.5)',
        borderRadius: 12,
        padding: '16px 20px',
        background: 'rgba(8,12,24,0.96)',
        boxShadow: '0 10px 40px rgba(0,0,0,0.5)',
        zIndex: 60,
        color: '#e5e7eb',
        backdropFilter: 'blur(6px)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 8,
        }}
      >
        <strong style={{ fontSize: 14, letterSpacing: 0.3 }}>
          ☀️ Morning briefing
          <span style={{ opacity: 0.6, fontWeight: 400, marginLeft: 8, fontSize: 12 }}>
            generated {formatWhen(briefing.generated_at)}
          </span>
        </strong>
        <button
          onClick={handleDismiss}
          aria-label="Dismiss briefing"
          style={{
            background: 'transparent',
            border: '1px solid var(--border, #444)',
            borderRadius: 6,
            padding: '2px 10px',
            cursor: 'pointer',
            fontSize: 12,
          }}
        >
          Dismiss
        </button>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.5 }} className="briefing-md">
        <ReactMarkdown>{briefing.markdown}</ReactMarkdown>
      </div>
    </div>
  );
}

export default BriefingBanner;
