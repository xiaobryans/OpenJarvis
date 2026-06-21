/**
 * JarvisCockpitPage — unified one-page front-door cockpit.
 *
 * Bryan's locked direction:
 * - No persistent sidebar/panels in daily-driver mode
 * - Central orb + command input
 * - Compact at-a-glance module cards (runtime, connectors, authority/stop,
 *   approvals, memory, tasks, audit, settings, setup, mobile)
 * - Modules expand inline or as overlays on the same page
 * - Settings = small gear icon → modal overlay
 * - Legacy routes remain under Settings → Developer/Debug
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { CosmicBackdrop } from '../components/Jarvis/CosmicBackdrop';
import { LivingOrb } from '../components/Jarvis/LivingOrb';
import { SettingsPage } from './SettingsPage';
import { apiFetch, checkHealth } from '../lib/api';
import type { TurnPhase } from '../hooks/useVoiceTurn';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModuleCard {
  id: string;
  icon: string;
  label: string;
  value?: string;
  status?: 'ok' | 'warn' | 'error' | 'unknown';
  route?: string;
  overlay?: boolean;
}

// ---------------------------------------------------------------------------
// Inline helpers
// ---------------------------------------------------------------------------

function statusColor(s?: ModuleCard['status']): string {
  switch (s) {
    case 'ok': return '#3ddc97';
    case 'warn': return '#f59e0b';
    case 'error': return '#ef4444';
    default: return '#6b7280';
  }
}

// ---------------------------------------------------------------------------
// Module card component
// ---------------------------------------------------------------------------

function Card({
  card,
  onClick,
}: {
  card: ModuleCard;
  onClick: (card: ModuleCard) => void;
}) {
  return (
    <button
      onClick={() => onClick(card)}
      className="group flex flex-col items-start gap-1 rounded-xl px-3 py-2.5 transition-all duration-150 cursor-pointer text-left"
      style={{
        background: 'rgba(14, 20, 36, 0.72)',
        border: '1px solid rgba(34, 211, 238, 0.10)',
        backdropFilter: 'blur(8px)',
        minWidth: 0,
      }}
    >
      <div className="flex items-center gap-2 w-full">
        <span style={{ fontSize: '1rem', lineHeight: 1 }}>{card.icon}</span>
        <span
          className="text-[11px] font-medium tracking-wide truncate flex-1"
          style={{ color: 'rgba(160, 200, 240, 0.75)' }}
        >
          {card.label}
        </span>
        {card.status && (
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: statusColor(card.status), boxShadow: `0 0 4px ${statusColor(card.status)}` }}
          />
        )}
      </div>
      {card.value && (
        <span
          className="text-[10px] truncate max-w-full"
          style={{ color: 'rgba(120, 160, 200, 0.55)' }}
        >
          {card.value}
        </span>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main cockpit
// ---------------------------------------------------------------------------

export function JarvisCockpitPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [lastReply, setLastReply] = useState('');
  const [phase, setPhase] = useState<TurnPhase>('idle');

  // Module state
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [model, setModel] = useState('');
  const [connectorSummary, setConnectorSummary] = useState('');
  const [pendingApprovals, setPendingApprovals] = useState<number>(0);
  const [version, setVersion] = useState('');

  // ---------------------------------------------------------------------------
  // Bootstrap data fetches
  // ---------------------------------------------------------------------------

  useEffect(() => {
    checkHealth().then(ok => {
      setApiOk(ok);
      if (ok) {
        apiFetch('/health')
          .then(r => r.json())
          .then(d => {
            setModel(d.model ?? '');
            setVersion(d.version ?? '');
          })
          .catch(() => {});

        apiFetch('/v1/approvals/pending')
          .then(r => r.json())
          .then(d => {
            const list = Array.isArray(d) ? d : (d?.items ?? []);
            setPendingApprovals(list.length);
          })
          .catch(() => {});

        apiFetch('/v1/connectors')
          .then(r => r.json())
          .then(d => {
            const all: { is_connected?: boolean }[] = Array.isArray(d) ? d : (d?.connectors ?? []);
            const live = all.filter(c => c.is_connected).length;
            setConnectorSummary(`${live}/${all.length} live`);
          })
          .catch(() => { setConnectorSummary('unknown'); });
      }
    });

    const interval = setInterval(() => {
      checkHealth().then(setApiOk);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // ---------------------------------------------------------------------------
  // Command submit
  // ---------------------------------------------------------------------------

  const handleSubmit = useCallback(async () => {
    const msg = input.trim();
    if (!msg || sending) return;
    setSending(true);
    setPhase('thinking');
    setLastReply('');
    setInput('');

    try {
      const res = await apiFetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: model || 'default',
          messages: [{ role: 'user', content: msg }],
          stream: false,
        }),
      });
      const data = await res.json();
      const reply: string = data?.choices?.[0]?.message?.content ?? data?.error ?? 'No reply.';
      setLastReply(reply.slice(0, 400));
      setPhase('idle');
    } catch (err) {
      setLastReply(`Error: ${String(err)}`);
      setPhase('error');
    } finally {
      setSending(false);
    }
  }, [input, sending, model]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  // ---------------------------------------------------------------------------
  // Module cards definition
  // ---------------------------------------------------------------------------

  const cards: ModuleCard[] = [
    {
      id: 'runtime',
      icon: '⚡',
      label: 'Runtime',
      value: model ? `${model} · v${version}` : 'connecting…',
      status: apiOk === null ? 'unknown' : apiOk ? 'ok' : 'error',
    },
    {
      id: 'connectors',
      icon: '🔌',
      label: 'Connectors',
      value: connectorSummary || 'loading…',
      status: connectorSummary.startsWith('0/') ? 'warn' : connectorSummary ? 'ok' : 'unknown',
      route: 'data-sources',
    },
    {
      id: 'authority',
      icon: '🛑',
      label: 'Authority / Stop',
      value: 'Emergency stop',
      status: 'ok',
      route: 'authority',
    },
    {
      id: 'approvals',
      icon: '✅',
      label: 'Approvals',
      value: pendingApprovals > 0 ? `${pendingApprovals} pending` : 'none pending',
      status: pendingApprovals > 0 ? 'warn' : 'ok',
      route: 'mission-control',
    },
    {
      id: 'memory',
      icon: '🧠',
      label: 'Memory',
      value: 'Rust bridge pending',
      status: 'warn',
    },
    {
      id: 'tasks',
      icon: '📋',
      label: 'Tasks / Goals',
      value: 'Mission Control',
      route: 'mission-control',
      status: 'ok',
    },
    {
      id: 'audit',
      icon: '📜',
      label: 'Audit',
      value: 'Logs & traces',
      route: 'logs',
      status: 'ok',
    },
    {
      id: 'settings',
      icon: '⚙️',
      label: 'Settings',
      value: 'Configure Jarvis',
      overlay: true,
      status: 'ok',
    },
    {
      id: 'setup',
      icon: '🔧',
      label: 'Setup / Blockers',
      value: 'Get Started',
      route: 'get-started',
      status: apiOk ? 'ok' : 'warn',
    },
    {
      id: 'mobile',
      icon: '📱',
      label: 'Mobile',
      value: '192.168.1.16:8000/mobile',
      status: apiOk ? 'ok' : 'unknown',
    },
  ];

  const handleCardClick = useCallback((card: ModuleCard) => {
    if (card.id === 'settings' || card.overlay) {
      setSettingsOpen(true);
    } else if (card.route) {
      navigate(`/${card.route}`);
    }
  }, [navigate]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div
      className="relative flex flex-col w-full h-full overflow-hidden"
      style={{ background: '#02040a' }}
    >
      <CosmicBackdrop phase={phase} voiceEnabled={false} />

      {/* Settings overlay */}
      {settingsOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(2, 4, 10, 0.92)', backdropFilter: 'blur(12px)' }}
        >
          <div
            className="relative w-full max-w-2xl max-h-[85vh] overflow-auto rounded-2xl"
            style={{ background: '#0d1117', border: '1px solid rgba(34, 211, 238, 0.15)' }}
          >
            <button
              onClick={() => setSettingsOpen(false)}
              className="absolute top-3 right-4 z-10 text-sm cursor-pointer"
              style={{ color: 'rgba(160, 200, 240, 0.5)' }}
            >
              ✕ close
            </button>
            <SettingsPage />
          </div>
        </div>
      )}

      {/* Top gear button */}
      <div className="absolute top-3 right-4 z-20 flex items-center gap-2">
        <button
          onClick={() => setSettingsOpen(true)}
          className="text-lg cursor-pointer transition-opacity hover:opacity-80"
          title="Settings"
          style={{ opacity: 0.45 }}
        >
          ⚙️
        </button>
      </div>

      {/* Orb zone */}
      <div className="relative flex-none flex items-center justify-center pt-8 pb-2">
        <div className="relative flex items-center justify-center">
          <div className="relative z-10">
            <LivingOrb phase={phase} voiceEnabled={false} size={160} />
          </div>
        </div>
      </div>

      {/* Command input */}
      <div className="relative z-10 shrink-0 px-4 pb-2">
        <div
          className="flex items-end gap-2 rounded-2xl px-4 py-2"
          style={{
            background: 'rgba(14, 20, 36, 0.80)',
            border: '1px solid rgba(34, 211, 238, 0.14)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Jarvis anything… (Enter to send)"
            disabled={sending}
            className="flex-1 resize-none bg-transparent outline-none text-sm leading-relaxed"
            style={{
              color: 'rgba(200, 220, 255, 0.90)',
              maxHeight: '120px',
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={sending || !input.trim()}
            className="text-sm px-3 py-1 rounded-lg shrink-0 transition-opacity"
            style={{
              background: sending ? 'rgba(34, 211, 238, 0.15)' : 'rgba(34, 211, 238, 0.22)',
              color: 'rgba(34, 211, 238, 0.85)',
              border: '1px solid rgba(34, 211, 238, 0.20)',
              opacity: sending || !input.trim() ? 0.5 : 1,
            }}
          >
            {sending ? '…' : '↑'}
          </button>
        </div>
        {lastReply && (
          <div
            className="mt-2 text-xs leading-relaxed rounded-xl px-3 py-2"
            style={{
              background: 'rgba(14, 20, 36, 0.70)',
              color: 'rgba(160, 210, 180, 0.85)',
              border: '1px solid rgba(61, 220, 151, 0.10)',
            }}
          >
            {lastReply}
          </div>
        )}
      </div>

      {/* Module cards grid */}
      <div className="relative z-10 flex-1 overflow-y-auto px-3 pb-4 pt-2">
        <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))' }}>
          {cards.map(card => (
            <Card key={card.id} card={card} onClick={handleCardClick} />
          ))}
        </div>
      </div>

      {/* Footer status */}
      <div
        className="relative z-10 shrink-0 flex items-center justify-center gap-3 py-1.5 text-[10px]"
        style={{ color: 'rgba(120, 150, 200, 0.35)' }}
      >
        <span
          className="flex items-center gap-1"
          style={{ color: apiOk ? 'rgba(61, 220, 151, 0.5)' : 'rgba(239, 68, 68, 0.5)' }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: apiOk ? '#3ddc97' : '#ef4444' }}
          />
          {apiOk ? 'Backend live' : 'Backend unreachable'}
        </span>
        <span>·</span>
        <span>⌘K command palette</span>
        <span>·</span>
        <span>Voice: parked</span>
      </div>
    </div>
  );
}

export default JarvisCockpitPage;
