/**
 * CockpitCommandPalette — ⌘K quick-navigation overlay.
 *
 * Design invariants:
 *   - No unsafe actions exposed without approval gates.
 *   - Only navigates to modes/panels — never executes production ops.
 *   - Keyboard-driven: ↑↓ navigate, Enter confirm, Esc close.
 */

import { useEffect, useRef, useState } from 'react';

export type FocusMode =
  | 'mission'
  | 'workbench'
  | 'approvals'
  | 'audit'
  | 'memory'
  | 'system'
  | 'voice';

export interface PaletteCommand {
  id: string;
  icon: string;
  label: string;
  group: string;
  mode?: FocusMode;
  detail?: string;
}

const ALL_COMMANDS: PaletteCommand[] = [
  // Primary modes
  { id: 'go-mission',    icon: '🎯', label: 'Mission Control',          group: 'Modes', mode: 'mission',    detail: 'Jarvis core + chat + canonical chain' },
  { id: 'go-workbench',  icon: '🔧', label: 'Workbench',                group: 'Modes', mode: 'workbench',  detail: 'Coding / testing / workflow tools' },
  { id: 'go-approvals',  icon: '🛑', label: 'Approvals',                 group: 'Modes', mode: 'approvals',  detail: 'Pending actions requiring Bryan approval' },
  { id: 'go-audit',      icon: '📜', label: 'Audit / Logs',              group: 'Modes', mode: 'audit',      detail: 'Authority audit trail & event log' },
  { id: 'go-memory',     icon: '🧠', label: 'Memory',                    group: 'Modes', mode: 'memory',     detail: 'Memory store + cross-device sync' },
  { id: 'go-system',     icon: '⚙️',  label: 'System / Plan 9',          group: 'Modes', mode: 'system',     detail: 'All modules, routing, connectors, org chain' },
  { id: 'go-voice',      icon: '🎙',  label: 'Voice [PARKED]',            group: 'Modes', mode: 'voice',      detail: 'Voice interface — US13 PARKED' },
  // System modules
  { id: 'mod-routing',   icon: '🔀', label: 'Model Routing',             group: 'System', mode: 'system',   detail: 'Provider routing matrix & PA front-door model' },
  { id: 'mod-connectors',icon: '🔌', label: 'Connectors',                group: 'System', mode: 'system',   detail: 'Data source integrations' },
  { id: 'mod-org',       icon: '🏗',  label: 'Org Chain / AI Organization', group: 'System', mode: 'system', detail: 'PA→COS/GM→Managers→Workers→Reviewer chain' },
  { id: 'mod-plan9',     icon: '🚀', label: 'Plan 9 / Parity',           group: 'System', mode: 'system',   detail: 'Cross-device capability parity matrix' },
  { id: 'mod-releases',  icon: '📦', label: 'Releases / Signing',        group: 'System', mode: 'system',   detail: 'App packaging, signing, notarisation' },
  { id: 'mod-finance',   icon: '💰', label: 'Finance / Admin',           group: 'System', mode: 'system',   detail: 'Pending Plan 5' },
  { id: 'mod-research',  icon: '🔬', label: 'Research',                  group: 'System', mode: 'system',   detail: 'Pending Plan 4' },
  { id: 'mod-lifeos',    icon: '♾️',  label: 'Life OS',                   group: 'System', mode: 'system',   detail: 'Pending Plan 5' },
  { id: 'mod-biz',       icon: '💼', label: 'Business OS',               group: 'System', mode: 'system',   detail: 'Pending Plan 5' },
  { id: 'mod-notifs',    icon: '🔔', label: 'Notifications',             group: 'System', mode: 'system',   detail: 'Notification channels' },
  { id: 'mod-mobile',    icon: '📱', label: 'Mobile Control Center',     group: 'System', mode: 'system',   detail: 'Mobile/PWA session management' },
  { id: 'mod-devices',   icon: '🤖', label: 'Devices / Robotics',        group: 'System', mode: 'system',   detail: 'Pending' },
  { id: 'mod-devtools',  icon: '👨‍💻', label: 'Developer Tools',           group: 'System', mode: 'system',   detail: 'Trace debugger, energy dashboard' },
  { id: 'mod-skills',    icon: '🎓', label: 'Skills',                    group: 'System', mode: 'system',   detail: 'Pending Plan 4' },
  { id: 'mod-settings',  icon: '⚙️',  label: 'Settings',                  group: 'System', mode: 'system',   detail: 'Server URL, model, theme' },
  // Mission actions
  { id: 'open-chat',     icon: '💬', label: 'Open Chat / Command',       group: 'Actions', mode: 'mission',  detail: 'Send a message to Jarvis PA' },
  { id: 'open-approval', icon: '✅', label: 'Review Pending Approvals',  group: 'Actions', mode: 'approvals', detail: 'View and approve/deny queued actions' },
];

interface Props {
  open: boolean;
  pendingApprovals: number;
  onClose: () => void;
  onNavigate: (mode: FocusMode) => void;
}

export function CockpitCommandPalette({ open, pendingApprovals, onClose, onNavigate }: Props) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = ALL_COMMANDS.filter(
    c => !query || c.label.toLowerCase().includes(query.toLowerCase()) || c.group.toLowerCase().includes(query.toLowerCase()),
  );

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); return; }
      if (e.key === 'Enter' && filtered[selected]) {
        const cmd = filtered[selected];
        if (cmd.mode) onNavigate(cmd.mode);
        onClose();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, filtered, selected, onClose, onNavigate]);

  if (!open) return null;

  const grouped: Record<string, PaletteCommand[]> = {};
  for (const cmd of filtered) {
    if (!grouped[cmd.group]) grouped[cmd.group] = [];
    grouped[cmd.group].push(cmd);
  }

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '15vh', background: 'rgba(2,4,10,0.75)', backdropFilter: 'blur(12px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ width: '100%', maxWidth: 540, background: '#080f1c', border: '1px solid rgba(34,211,238,0.18)', borderRadius: 16, boxShadow: '0 32px 80px rgba(0,0,0,0.7)', overflow: 'hidden' }}>
        {/* Search header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderBottom: '1px solid rgba(34,211,238,0.08)' }}>
          <span style={{ fontSize: 14, color: 'rgba(100,150,200,0.5)' }}>⌘</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Jump to module, mode, or action…"
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', fontSize: 13, color: 'rgba(200,220,255,0.9)', fontFamily: 'var(--font-display, sans-serif)' }}
          />
          {pendingApprovals > 0 && (
            <span style={{ fontSize: 9, background: 'rgba(245,158,11,0.2)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 4, padding: '2px 6px' }}>
              {pendingApprovals} pending
            </span>
          )}
          <span style={{ fontSize: 9, color: 'rgba(80,120,160,0.5)' }}>Esc to close</span>
        </div>

        {/* Results */}
        <div ref={listRef} style={{ maxHeight: '55vh', overflowY: 'auto', padding: '6px 0' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '20px 14px', fontSize: 11, color: 'rgba(120,160,200,0.4)', textAlign: 'center' }}>No commands matching "{query}"</div>
          ) : (
            Object.entries(grouped).map(([group, cmds]) => (
              <div key={group}>
                <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.3)', padding: '8px 14px 4px' }}>{group}</div>
                {cmds.map(cmd => {
                  const idx = filtered.indexOf(cmd);
                  const isActive = idx === selected;
                  return (
                    <button
                      key={cmd.id}
                      onClick={() => { if (cmd.mode) onNavigate(cmd.mode); onClose(); }}
                      style={{
                        width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 10,
                        padding: '7px 14px', background: isActive ? 'rgba(34,211,238,0.08)' : 'transparent',
                        border: 'none', cursor: 'pointer', borderLeft: isActive ? '2px solid rgba(34,211,238,0.5)' : '2px solid transparent',
                      }}
                    >
                      <span style={{ fontSize: 14, flexShrink: 0 }}>{cmd.icon}</span>
                      <span style={{ flex: 1 }}>
                        <span style={{ fontSize: 12, color: isActive ? 'rgba(180,220,255,0.95)' : 'rgba(160,200,240,0.8)', display: 'block' }}>{cmd.label}</span>
                        {cmd.detail && <span style={{ fontSize: 10, color: 'rgba(100,140,180,0.5)' }}>{cmd.detail}</span>}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <div style={{ padding: '6px 14px', borderTop: '1px solid rgba(34,211,238,0.06)', display: 'flex', gap: 12, fontSize: 9, color: 'rgba(80,120,160,0.4)' }}>
          <span>↑↓ navigate</span><span>↵ select</span><span>Esc close</span>
        </div>
      </div>
    </div>
  );
}

export default CockpitCommandPalette;
