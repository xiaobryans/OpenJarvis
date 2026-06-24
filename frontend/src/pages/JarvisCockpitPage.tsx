/**
 * JarvisNeuralCommandCenter — Plan 1 Cinematic One-Page Cockpit.
 *
 * Layout:
 *   Desktop: Left mode rail (52px) + top status bar + work surface (mode-driven)
 *   Mobile:  Top status bar + work surface + bottom tab bar
 *
 * Modes (not separate pages — same one-page cockpit):
 *   mission   — Jarvis core + chat + org spine + pending alerts
 *   workbench — coding / testing / workflow tools
 *   approvals — approval mode takeover (amber state)
 *   audit     — authority audit log + governance
 *   memory    — memory store + cross-device sync
 *   system    — all 24 modules grid + Plan 9 + routing + org chain
 *   voice     — voice status (US13 PARKED — honest state)
 *
 * Design invariants:
 *   - Bryan interacts ONLY with Jarvis PA.
 *   - Workers/managers/COS/GM/reviewer are internal org layers, never direct chat participants.
 *   - Real state drives everything. If unavailable, show honest unavailable state.
 *   - No fake live activity. No fake worker motion.
 *   - Approval mode gets full-attention amber treatment.
 *   - Command palette (⌘K) accessible from any mode.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CosmicBackdrop } from '../components/Jarvis/CosmicBackdrop';
import { LivingOrb } from '../components/Jarvis/LivingOrb';
import { SettingsPage } from './SettingsPage';
import { OrgChainPanel } from '../components/OrgChainPanel';
import { CockpitCommandPalette } from '../components/CockpitCommandPalette';
import type { OrgHierarchyData, OrgChainFetchState } from '../components/OrgChainPanel';
import type { FocusMode } from '../components/CockpitCommandPalette';
import { apiFetch, checkHealth } from '../lib/api';
import type { TurnPhase } from '../hooks/useVoiceTurn';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type PanelId =
  | 'mission' | 'cockpit' | 'authority' | 'workbench' | 'connectors'
  | 'agents' | 'memory' | 'plan9' | 'logs' | 'settings' | 'routing'
  | 'org-chain';

type StatusDot = 'ok' | 'warn' | 'error' | 'unknown';

interface ConnectorInfo { name: string; connected: boolean; endpoint?: string; }
interface MemoryStatus {
  total_entries: number;
  cloud_sync_available: boolean;
  bucket?: string;
  rust_available?: boolean;
}
interface Plan9Status {
  verdict?: string;
  mobile_cloud_live: number;
  mac_local_live: number;
  parked: number;
  gaps: number;
}
interface AgentEntry { id: string; name: string; kind: 'manager' | 'worker'; status: string; domain: string; }
interface RoutingStatus {
  provider_count: number;
  model_count: number;
  non_fallback_model_count: number;
  kimi_benchmarked: boolean;
  glm_5_2_available?: boolean;
  kimi_k2_6_available?: boolean;
  role_declaration_count: number;
  pa_front_door_model: string;
  active_routing_policy: string;
  blocked_providers: string[];
  benchmark_status: Record<string, string>;
  policy_labels?: Record<string, string>;
  provider_health: Record<string, string>;
  heavy_coding_route_preference?: string;
}
interface PanelFetchState {
  status: 'loading' | 'ok' | 'error';
  httpStatus?: number;
  detail?: string;
  at?: string;
}
interface RegistryStatus {
  total_roles: number;
  total_managers: number;
  total_workers: number;
}
interface OrchestrationSummary {
  elastic_pool_roles: number;
  dag_rules: number;
  retrieval_teams: number;
}
interface RuntimeProofSummary {
  total_items: number;
  verified_count: number;
  pending_count: number;
}
interface ApprovalItem {
  id: string;
  description?: string;
  status?: string;
  action_type?: string;
  tier?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Canonical module registry — 24 modules, honest availability states
// ─────────────────────────────────────────────────────────────────────────────

interface ModuleEntry {
  id: PanelId | string;
  icon: string;
  label: string;
  mode: FocusMode;
  availability: 'live' | 'unavailable' | 'parked' | 'pending_plan_2' | 'pending_plan_3' | 'pending_plan_4' | 'pending_plan_5' | 'local_only' | 'cloud_ready';
  description: string;
}

const ALL_MODULES: ModuleEntry[] = [
  { id: 'mission',    icon: '🎯', label: 'Mission Control',          mode: 'mission',   availability: 'live',          description: 'Jarvis core, chat, canonical chain status' },
  { id: 'chat',       icon: '💬', label: 'Chat / Command',           mode: 'mission',   availability: 'live',          description: 'Bryan ↔ Jarvis PA — the only user-facing interface' },
  { id: 'workbench',  icon: '🔧', label: 'Workbench',               mode: 'workbench', availability: 'live',          description: 'Local coding, testing, diff, git workflow' },
  { id: 'cloud-wb',   icon: '☁️',  label: 'Cloud Workbench',         mode: 'workbench', availability: 'pending_plan_2', description: 'Cloud-hosted coding agents — Pending Plan 2' },
  { id: 'authority',  icon: '🛑', label: 'Authority',               mode: 'approvals', availability: 'live',          description: 'Hard gates, emergency stop, audit authority' },
  { id: 'approvals',  icon: '✅', label: 'Approvals',               mode: 'approvals', availability: 'live',          description: 'Bryan approval queue — PA-gated only' },
  { id: 'audit',      icon: '📜', label: 'Audit / Logs',            mode: 'audit',     availability: 'live',          description: 'Governance audit trail, event log' },
  { id: 'memory',     icon: '🧠', label: 'Memory',                  mode: 'memory',    availability: 'live',          description: 'Memory store + S3 cloud sync' },
  { id: 'connectors', icon: '🔌', label: 'Connectors',              mode: 'system',    availability: 'live',          description: 'Data source integrations' },
  { id: 'plan9',      icon: '🚀', label: 'Plan 9 / System',         mode: 'system',    availability: 'live',          description: 'Cross-device parity matrix, capability status' },
  { id: 'settings',   icon: '⚙️',  label: 'Settings',               mode: 'system',    availability: 'live',          description: 'Server URL, model, auth, theme' },
  { id: 'skills',     icon: '🎓', label: 'Skills',                  mode: 'system',    availability: 'pending_plan_4', description: 'ECC skill packs — Pending Plan 4' },
  { id: 'research',   icon: '🔬', label: 'Research',                mode: 'system',    availability: 'pending_plan_4', description: 'Research assistant — Pending Plan 4' },
  { id: 'lifeos',     icon: '♾️',  label: 'Life OS',                 mode: 'system',    availability: 'pending_plan_5', description: 'Personal life management — Pending Plan 5' },
  { id: 'bizos',      icon: '💼', label: 'Business OS',             mode: 'system',    availability: 'pending_plan_5', description: 'Business operations OS — Pending Plan 5' },
  { id: 'finance',    icon: '💰', label: 'Finance / Admin',         mode: 'system',    availability: 'pending_plan_5', description: 'Financial management — Pending Plan 5' },
  { id: 'notifs',     icon: '🔔', label: 'Notifications',           mode: 'system',    availability: 'live',          description: 'Notification channels (Telegram, Slack, email)' },
  { id: 'voice',      icon: '🎙',  label: 'Voice',                   mode: 'voice',     availability: 'parked',        description: 'Voice interface — US13 PARKED/UNSAFE' },
  { id: 'devices',    icon: '🤖', label: 'Devices / Robotics',      mode: 'system',    availability: 'pending_plan_5', description: 'Peripheral device control — Pending' },
  { id: 'releases',   icon: '📦', label: 'Releases / Signing',      mode: 'system',    availability: 'live',          description: 'App packaging, code signing, notarisation' },
  { id: 'routing',    icon: '🔀', label: 'Model Routing',           mode: 'system',    availability: 'live',          description: 'Provider routing matrix, PA front-door model' },
  { id: 'devtools',   icon: '👨‍💻', label: 'Developer Tools',         mode: 'system',    availability: 'live',          description: 'Trace debugger, energy dashboard, benchmarks' },
  { id: 'mobile',     icon: '📱', label: 'Mobile Control Center',   mode: 'system',    availability: 'live',          description: 'Mobile/PWA session state' },
  { id: 'org-chain',  icon: '🏗',  label: 'Org Chain / AI Org',     mode: 'system',    availability: 'live',          description: 'PA→COS/GM→Managers→Workers→Reviewer chain' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function dot(s: StatusDot): React.ReactNode {
  const c = { ok: '#3ddc97', warn: '#f59e0b', error: '#ef4444', unknown: '#6b7280' }[s];
  return <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: c, boxShadow: `0 0 4px ${c}`, flexShrink: 0 }} />;
}

function ts() { return new Date().toLocaleTimeString(); }

function availBadge(a: ModuleEntry['availability']): { label: string; color: string } {
  const map: Record<ModuleEntry['availability'], { label: string; color: string }> = {
    live:           { label: 'Live',           color: '#3ddc97' },
    unavailable:    { label: 'Unavailable',    color: '#6b7280' },
    parked:         { label: 'Parked',         color: '#f59e0b' },
    pending_plan_2: { label: 'Plan 2',         color: '#60a5fa' },
    pending_plan_3: { label: 'Plan 3',         color: '#60a5fa' },
    pending_plan_4: { label: 'Plan 4',         color: '#a78bfa' },
    pending_plan_5: { label: 'Plan 5',         color: '#a78bfa' },
    local_only:     { label: 'Local only',     color: '#f59e0b' },
    cloud_ready:    { label: 'Cloud ready',    color: '#3ddc97' },
  };
  return map[a] ?? { label: a, color: '#6b7280' };
}

async function parseApprovalActionError(res: Response): Promise<string> {
  let detail = res.statusText || `HTTP ${res.status}`;
  try {
    const j = await res.json();
    if (typeof j.detail === 'string') detail = j.detail;
    else if (typeof j.error === 'string') detail = j.error;
    else if (typeof j.message === 'string') detail = j.message;
    else if (j.detail != null) detail = JSON.stringify(j.detail);
  } catch { /* non-json body */ }
  return detail;
}

async function fetchTracked(
  path: string,
  onState: (s: PanelFetchState) => void,
  onData: (r: Response) => Promise<void>,
): Promise<void> {
  onState({ status: 'loading' });
  try {
    const r = await apiFetch(path);
    if (!r.ok) {
      let detail = r.statusText;
      try { const j = await r.json(); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* non-json */ }
      onState({ status: 'error', httpStatus: r.status, detail, at: ts() });
      return;
    }
    await onData(r);
    onState({ status: 'ok', httpStatus: r.status, at: ts() });
  } catch (e) {
    onState({ status: 'error', detail: String(e), at: ts() });
  }
}

function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setNarrow(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return narrow;
}

// ─────────────────────────────────────────────────────────────────────────────
// Primitive building blocks
// ─────────────────────────────────────────────────────────────────────────────

function Row({ label, value, status }: { label: string; value: React.ReactNode; status?: StatusDot }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '5px 0', borderBottom: '1px solid rgba(34,211,238,0.05)' }}>
      <span style={{ fontSize: 10, color: 'rgba(120,160,200,0.5)', minWidth: 120, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 11, color: 'rgba(190,220,255,0.85)', flex: 1, wordBreak: 'break-all' }}>{value}</span>
      {status && <span style={{ flexShrink: 0 }}>{dot(status)}</span>}
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.4)', textTransform: 'uppercase', marginTop: 12, marginBottom: 4 }}>{children}</div>;
}

function BackendError({ endpoint, target, httpStatus, detail, lastOk }: { endpoint: string; target: string; httpStatus?: number; detail?: string; lastOk?: string }) {
  return (
    <div style={{ color: '#ef4444', fontSize: 10 }}>
      <div>⚠ <code style={{ fontSize: 9 }}>{endpoint}</code></div>
      <div style={{ color: '#9ca3af' }}>Target: {target}</div>
      {httpStatus != null && <div>HTTP: {httpStatus}</div>}
      {detail && <div style={{ color: '#fca5a5' }}>{detail}</div>}
      {lastOk && <div style={{ color: '#9ca3af' }}>Last OK: {lastOk}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Overlay modal — preserved from original cockpit
// ─────────────────────────────────────────────────────────────────────────────

function Overlay({ title, icon, onClose, children }: { title: string; icon: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, background: 'rgba(2,4,10,0.88)', backdropFilter: 'blur(16px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ position: 'relative', width: '100%', maxWidth: 640, maxHeight: '82vh', overflow: 'hidden', background: '#080f1c', border: '1px solid rgba(34,211,238,0.16)', borderRadius: 16, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px', borderBottom: '1px solid rgba(34,211,238,0.08)', flexShrink: 0 }}>
          <span style={{ fontSize: 16 }}>{icon}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'rgba(180,220,255,0.9)', flex: 1 }}>{title}</span>
          <button onClick={onClose} style={{ fontSize: 11, color: 'rgba(120,160,200,0.5)', cursor: 'pointer', background: 'none', border: 'none' }}>✕ close</button>
        </div>
        <div style={{ overflowY: 'auto', padding: '12px 16px', flex: 1 }}>{children}</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Top Status Bar
// ─────────────────────────────────────────────────────────────────────────────

interface TopStatusProps {
  apiOk: boolean | null;
  model: string;
  version: string;
  gitCommit: string;
  apiTarget: string;
  plan9: Plan9Status | null;
  pendingApprovals: number;
  connectorLive: number;
  connectorTotal: number;
  activeMode: FocusMode;
  onPalette: () => void;
  onMode: (m: FocusMode) => void;
}

function TopStatusBar({ apiOk, model, version, gitCommit, apiTarget, plan9, pendingApprovals, connectorLive, connectorTotal, activeMode, onPalette, onMode }: TopStatusProps) {
  const modeLabel: Record<FocusMode, string> = {
    mission: 'Mission', workbench: 'Workbench', approvals: 'Approvals',
    audit: 'Audit', memory: 'Memory', system: 'System', voice: 'Voice [PARKED]',
  };
  return (
    <div style={{ position: 'relative', zIndex: 20, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 0, height: 36, borderBottom: '1px solid rgba(34,211,238,0.08)', background: 'rgba(2,4,10,0.8)', backdropFilter: 'blur(10px)' }}>
      {/* Left: Jarvis identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 12px', borderRight: '1px solid rgba(34,211,238,0.07)', height: '100%', flexShrink: 0 }}>
        {dot(apiOk ? 'ok' : apiOk === false ? 'error' : 'unknown')}
        <span style={{ fontSize: 11, fontWeight: 700, color: apiOk ? '#22d3ee' : '#6b7280', fontFamily: 'var(--font-display, sans-serif)', letterSpacing: '0.05em' }}>JARVIS</span>
        {version && <span style={{ fontSize: 9, color: 'rgba(80,120,160,0.5)', fontFamily: 'var(--font-hud, monospace)' }}>v{version}</span>}
        {gitCommit && <span style={{ fontSize: 9, color: 'rgba(60,100,140,0.4)', fontFamily: 'var(--font-hud, monospace)' }}>{gitCommit.slice(0, 7)}</span>}
      </div>

      {/* Center: active mode indicator */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
        {pendingApprovals > 0 && (
          <button
            onClick={() => onMode('approvals')}
            style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 9, padding: '2px 8px', background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.35)', borderRadius: 4, color: '#f59e0b', cursor: 'pointer', animation: 'orb-pulse-med 2s ease-in-out infinite' }}
          >
            🛑 {pendingApprovals} approval{pendingApprovals !== 1 ? 's' : ''} pending
          </button>
        )}
        <span style={{ fontSize: 10, color: 'rgba(100,140,180,0.5)' }}>{modeLabel[activeMode]}</span>
      </div>

      {/* Right: system stats */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 12px', borderLeft: '1px solid rgba(34,211,238,0.07)', height: '100%', fontSize: 9, color: 'rgba(100,140,180,0.5)', flexShrink: 0 }}>
        {model && <span style={{ fontFamily: 'var(--font-hud, monospace)' }}>{model.split('/').pop()?.slice(0, 20) ?? model}</span>}
        {plan9 && <span style={{ color: plan9.gaps === 0 ? '#3ddc97' : '#f59e0b' }}>P9:{plan9.gaps === 0 ? '✓' : plan9.gaps + '⚠'}</span>}
        {connectorTotal > 0 && <span style={{ color: connectorLive === connectorTotal ? '#3ddc97' : '#f59e0b' }}>{connectorLive}/{connectorTotal}∫</span>}
        <span style={{ color: 'rgba(60,100,140,0.4)', fontFamily: 'var(--font-hud, monospace)' }}>{apiTarget.replace(/^https?:\/\//, '').slice(0, 20)}</span>
        <button onClick={onPalette} style={{ fontSize: 9, padding: '2px 7px', background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.18)', borderRadius: 4, color: 'rgba(100,180,220,0.7)', cursor: 'pointer', fontFamily: 'var(--font-hud, monospace)' }}>⌘K</button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Left Mode Rail (desktop)
// ─────────────────────────────────────────────────────────────────────────────

const MODE_RAIL: Array<{ id: FocusMode; icon: string; label: string }> = [
  { id: 'mission',   icon: '🎯', label: 'Mission'   },
  { id: 'workbench', icon: '🔧', label: 'Workbench' },
  { id: 'approvals', icon: '🛑', label: 'Approvals' },
  { id: 'audit',     icon: '📜', label: 'Audit'     },
  { id: 'memory',    icon: '🧠', label: 'Memory'    },
  { id: 'system',    icon: '⚙️',  label: 'System'    },
  { id: 'voice',     icon: '🎙',  label: 'Voice'     },
];

function LeftModeRail({ active, pendingApprovals, onMode }: { active: FocusMode; pendingApprovals: number; onMode: (m: FocusMode) => void }) {
  return (
    <div style={{ width: 52, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '8px 0', gap: 2, background: 'rgba(4,8,18,0.9)', borderRight: '1px solid rgba(34,211,238,0.07)', overflowY: 'auto' }}>
      {MODE_RAIL.map(m => {
        const isActive = m.id === active;
        const hasApproval = m.id === 'approvals' && pendingApprovals > 0;
        return (
          <button
            key={m.id}
            title={m.label}
            onClick={() => onMode(m.id)}
            style={{
              position: 'relative', width: 40, height: 40, borderRadius: 10, cursor: 'pointer', border: 'none',
              background: isActive ? 'rgba(34,211,238,0.12)' : 'transparent',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
              transition: 'background 0.15s',
              outline: isActive ? '1px solid rgba(34,211,238,0.25)' : 'none',
            }}
          >
            {m.icon}
            {hasApproval && (
              <span style={{ position: 'absolute', top: 4, right: 4, width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', boxShadow: '0 0 6px #f59e0b' }} />
            )}
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mobile bottom tab bar
// ─────────────────────────────────────────────────────────────────────────────

const MOBILE_TABS: Array<{ id: FocusMode; icon: string; label: string }> = [
  { id: 'mission',   icon: '🎯', label: 'Mission'   },
  { id: 'workbench', icon: '🔧', label: 'Work'      },
  { id: 'approvals', icon: '🛑', label: 'Approve'   },
  { id: 'memory',    icon: '🧠', label: 'Memory'    },
  { id: 'system',    icon: '⚙️',  label: 'System'    },
];

function MobileTabBar({ active, pendingApprovals, onMode }: { active: FocusMode; pendingApprovals: number; onMode: (m: FocusMode) => void }) {
  return (
    <div style={{ flexShrink: 0, display: 'flex', background: 'rgba(4,8,18,0.95)', borderTop: '1px solid rgba(34,211,238,0.08)', paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}>
      {MOBILE_TABS.map(m => {
        const isActive = active === m.id || (m.id === 'approvals' && active === 'approvals');
        const hasBadge = m.id === 'approvals' && pendingApprovals > 0;
        return (
          <button
            key={m.id}
            onClick={() => onMode(m.id)}
            style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3, padding: '8px 4px', border: 'none', background: 'transparent', cursor: 'pointer', position: 'relative' }}
          >
            <span style={{ fontSize: 18 }}>{m.icon}</span>
            <span style={{ fontSize: 9, color: isActive ? '#22d3ee' : 'rgba(100,140,180,0.5)', fontWeight: isActive ? 600 : 400 }}>{m.label}</span>
            {hasBadge && <span style={{ position: 'absolute', top: 6, right: '30%', width: 7, height: 7, borderRadius: '50%', background: '#f59e0b' }} />}
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mini org chain spine (mission mode sidebar)
// ─────────────────────────────────────────────────────────────────────────────

interface MiniChainProps {
  orgHierarchy: OrgHierarchyData | null;
  orgFetchOk: boolean;
  registry: RegistryStatus | null;
  pendingApprovals: number;
  onOrgChain: () => void;
}

function MiniOrgSpine({ orgHierarchy, orgFetchOk, registry, pendingApprovals, onOrgChain }: MiniChainProps) {
  const chainSteps = [
    { icon: '🔷', label: 'Jarvis PA', sub: 'user-facing only', color: '#22d3ee' },
    { icon: '🎛',  label: 'COS / GM', sub: 'command coordinator', color: '#a78bfa' },
    { icon: '📋', label: `Managers (${registry?.total_managers ?? '…'})`, sub: 'domain owners', color: '#34d399' },
    { icon: '⚙️',  label: `Workers (${registry?.total_workers ?? '…'})`, sub: 'execution cells', color: '#60a5fa' },
    { icon: '🔍', label: 'Reviewer', sub: 'independent · self-verify blocked', color: '#fb923c' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.35)', textTransform: 'uppercase', marginBottom: 8 }}>Canonical Chain</div>
      {chainSteps.map((s, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0, width: 16 }}>
            <span style={{ fontSize: 11 }}>{s.icon}</span>
            {i < chainSteps.length - 1 && <div style={{ width: 1, height: 8, background: 'rgba(100,140,180,0.2)', marginTop: 2 }} />}
          </div>
          <div>
            <div style={{ fontSize: 10, color: s.color, fontWeight: 600, lineHeight: 1.3 }}>{s.label}</div>
            <div style={{ fontSize: 9, color: 'rgba(100,140,180,0.45)', lineHeight: 1.2 }}>{s.sub}</div>
          </div>
        </div>
      ))}
      {pendingApprovals > 0 && (
        <div style={{ marginTop: 10, padding: '5px 8px', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 6, fontSize: 10, color: '#f59e0b' }}>
          {pendingApprovals} action{pendingApprovals !== 1 ? 's' : ''} pending Bryan approval
        </div>
      )}
      {orgFetchOk && (
        <button onClick={onOrgChain} style={{ marginTop: 6, fontSize: 9, color: 'rgba(34,211,238,0.4)', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', textDecoration: 'underline' }}>
          full org chain →
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Module grid card (used in system mode and as mini cards elsewhere)
// ─────────────────────────────────────────────────────────────────────────────

function ModuleCard({ mod, onClick, fetchErr }: { mod: ModuleEntry; onClick: () => void; fetchErr?: boolean }) {
  const ab = availBadge(mod.availability);
  const isLive = mod.availability === 'live' && !fetchErr;
  return (
    <button
      onClick={onClick}
      style={{
        textAlign: 'left', background: 'rgba(8,14,28,0.82)', border: `1px solid rgba(34,211,238,${isLive ? '0.1' : '0.05'})`,
        backdropFilter: 'blur(10px)', borderRadius: 10, padding: '8px 10px', cursor: 'pointer', minWidth: 0,
        transition: 'border-color 0.15s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
        <span style={{ fontSize: 14 }}>{mod.icon}</span>
        <span style={{ fontSize: 10, fontWeight: 600, color: 'rgba(160,200,240,0.8)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mod.label}</span>
        <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, background: `${ab.color}1a`, color: ab.color, border: `1px solid ${ab.color}33` }}>{ab.label}</span>
      </div>
      <div style={{ fontSize: 9, color: 'rgba(100,140,180,0.5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mod.description}</div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mode work surfaces
// ─────────────────────────────────────────────────────────────────────────────

// — Mission —
interface MissionSurfaceProps {
  phase: TurnPhase;
  apiOk: boolean | null;
  input: string;
  sending: boolean;
  lastReply: string;
  onInputChange: (v: string) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
  pendingApprovals: number;
  orgHierarchy: OrgHierarchyData | null;
  orgFetchOk: boolean;
  registry: RegistryStatus | null;
  routingStatus: RoutingStatus | null;
  onExpandPanel: (id: PanelId) => void;
  onMode: (m: FocusMode) => void;
  isNarrow: boolean;
}

function MissionSurface({ phase, apiOk, input, sending, lastReply, onInputChange, onKeyDown, onSubmit, pendingApprovals, orgHierarchy, orgFetchOk, registry, routingStatus, onExpandPanel, onMode, isNarrow }: MissionSurfaceProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Approval banner — shown whenever approval is pending, any mode */}
      {pendingApprovals > 0 && (
        <button
          onClick={() => onMode('approvals')}
          style={{ flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '8px 16px', background: 'rgba(245,158,11,0.12)', borderBottom: '1px solid rgba(245,158,11,0.25)', cursor: 'pointer', border: 'none', width: '100%' }}
        >
          <span style={{ fontSize: 13 }}>🛑</span>
          <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 600 }}>
            {pendingApprovals} action{pendingApprovals !== 1 ? 's' : ''} pending Bryan approval — click to review
          </span>
          <span style={{ fontSize: 10, color: 'rgba(245,158,11,0.5)' }}>→</span>
        </button>
      )}

      {/* Main mission area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: isNarrow ? 'column' : 'row', overflow: 'hidden', minHeight: 0 }}>

        {/* Left: Jarvis orb + chat */}
        <div style={{ flex: isNarrow ? 'none' : 2, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: isNarrow ? '16px 12px 8px' : '24px 16px 12px', overflow: 'hidden', minWidth: 0 }}>
          {/* Orb */}
          <div style={{ flexShrink: 0, position: 'relative' }}>
            <LivingOrb phase={phase} voiceEnabled={true} size={isNarrow ? 120 : 160} />
            {/* State label */}
            <div style={{ position: 'absolute', bottom: -18, left: '50%', transform: 'translateX(-50%)', whiteSpace: 'nowrap', fontSize: 9, color: 'rgba(100,150,200,0.5)', fontFamily: 'var(--font-hud, monospace)', letterSpacing: '0.06em' }}>
              {phase === 'waiting_for_silence' ? 'APPROVAL PENDING' : phase === 'error' ? 'ERROR' : phase === 'thinking' ? 'PROCESSING' : phase === 'speaking' ? 'RESPONDING' : 'READY'}
            </div>
          </div>

          {/* Chat reply */}
          {lastReply && (
            <div style={{ marginTop: 24, width: '100%', maxWidth: 480, fontSize: 12, lineHeight: 1.6, borderRadius: 12, padding: '10px 14px', background: 'rgba(10,18,32,0.75)', color: 'rgba(160,210,180,0.88)', border: '1px solid rgba(61,220,151,0.1)', maxHeight: isNarrow ? 80 : 140, overflowY: 'auto' }}>
              {lastReply}
            </div>
          )}

          {/* Chat input */}
          <div style={{ width: '100%', maxWidth: 520, marginTop: lastReply ? 10 : 28, flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, borderRadius: 14, padding: '8px 12px', background: 'rgba(10,16,32,0.82)', border: '1px solid rgba(34,211,238,0.13)', backdropFilter: 'blur(8px)' }}>
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={e => onInputChange(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={apiOk ? 'Ask Jarvis anything… (Enter to send)' : 'Backend unreachable — check server URL in Settings'}
                disabled={sending || !apiOk}
                style={{ flex: 1, resize: 'none', background: 'transparent', outline: 'none', fontSize: 13, lineHeight: '1.5', color: 'rgba(200,220,255,0.90)', maxHeight: 100, border: 'none', fontFamily: 'var(--font-display, sans-serif)' }}
              />
              <button
                onClick={onSubmit}
                disabled={sending || !input.trim() || !apiOk}
                style={{ fontSize: 13, padding: '4px 12px', borderRadius: 8, flexShrink: 0, background: sending ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.2)', color: 'rgba(34,211,238,0.9)', border: '1px solid rgba(34,211,238,0.2)', opacity: sending || !input.trim() || !apiOk ? 0.4 : 1, cursor: 'pointer' }}
              >
                {sending ? '…' : '↑'}
              </button>
            </div>
            <div style={{ marginTop: 4, fontSize: 9, color: 'rgba(60,100,140,0.4)', textAlign: 'center' }}>Bryan → Jarvis PA · all interactions through Jarvis only</div>
          </div>

          {/* Mini system stats row */}
          {!isNarrow && (
            <div style={{ display: 'flex', gap: 12, marginTop: 16, fontSize: 9, color: 'rgba(80,120,160,0.45)' }}>
              {routingStatus && <span>PA model: {routingStatus.pa_front_door_model}</span>}
              {routingStatus && <span>·</span>}
              {routingStatus && <span>{routingStatus.provider_count} providers</span>}
              <span>·</span>
              <button onClick={() => onExpandPanel('routing')} style={{ background: 'none', border: 'none', color: 'rgba(34,211,238,0.3)', fontSize: 9, cursor: 'pointer', textDecoration: 'underline' }}>routing →</button>
            </div>
          )}
        </div>

        {/* Right: Org spine + quick context (desktop only) */}
        {!isNarrow && (
          <div style={{ width: 220, flexShrink: 0, padding: '20px 14px', borderLeft: '1px solid rgba(34,211,238,0.07)', overflowY: 'auto' }}>
            <MiniOrgSpine
              orgHierarchy={orgHierarchy}
              orgFetchOk={orgFetchOk}
              registry={registry}
              pendingApprovals={pendingApprovals}
              onOrgChain={() => onExpandPanel('org-chain')}
            />

            {/* Quick links */}
            <div style={{ marginTop: 20, fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.35)', textTransform: 'uppercase', marginBottom: 8 }}>Quick access</div>
            {[
              { icon: '🔧', label: 'Workbench', m: 'workbench' as FocusMode },
              { icon: '🛑', label: 'Approvals', m: 'approvals' as FocusMode },
              { icon: '🧠', label: 'Memory', m: 'memory' as FocusMode },
              { icon: '⚙️', label: 'System', m: 'system' as FocusMode },
            ].map(q => (
              <button key={q.m} onClick={() => onMode(q.m)} style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%', padding: '4px 0', background: 'none', border: 'none', cursor: 'pointer', fontSize: 10, color: 'rgba(120,160,200,0.6)', textAlign: 'left' }}>
                <span>{q.icon}</span><span>{q.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// — Approval mode —
interface ApprovalBusyState {
  id: string;
  action: 'approve' | 'deny';
}

interface ApprovalSurfaceProps {
  approvalItems: ApprovalItem[];
  pendingApprovals: number;
  fetchState: Record<string, PanelFetchState>;
  apiTarget: string;
  onApprove: (id: string) => void;
  onDeny: (id: string) => void;
  approvalBusy: ApprovalBusyState | null;
  approvalErrors: Record<string, string>;
  auditEntries: { action_type?: string; execution_status?: string }[];
  isNarrow: boolean;
}

function ApprovalSurface({ approvalItems, pendingApprovals, fetchState, apiTarget, onApprove, onDeny, approvalBusy, approvalErrors, auditEntries, isNarrow }: ApprovalSurfaceProps) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: isNarrow ? '12px' : '20px 24px' }}>
      {/* Amber header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, padding: '10px 14px', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 12 }}>
        <span style={{ fontSize: 18 }}>🛑</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b' }}>
            {pendingApprovals > 0 ? `${pendingApprovals} Action${pendingApprovals !== 1 ? 's' : ''} Pending Bryan Approval` : 'No pending approvals'}
          </div>
          <div style={{ fontSize: 10, color: 'rgba(245,158,11,0.6)', marginTop: 1 }}>Bryan approves or denies through Jarvis PA only. No action taken without explicit approval.</div>
        </div>
      </div>

      {/* Approval chain reminder */}
      <div style={{ fontSize: 9, color: 'rgba(100,140,180,0.45)', marginBottom: 16, padding: '6px 10px', background: 'rgba(8,14,28,0.5)', borderRadius: 6, fontFamily: 'var(--font-hud, monospace)' }}>
        Worker/Manager → Domain Manager validates → Reviewer checks risk → COS/GM escalates → Jarvis PA asks Bryan → Bryan approves/denies → COS/GM routes back
      </div>

      {/* Pending approvals list */}
      {fetchState.approvals?.status === 'error' ? (
        <BackendError endpoint="/v1/authority/approvals/pending" target={apiTarget} />
      ) : pendingApprovals === 0 ? (
        <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 11, color: 'rgba(80,120,160,0.4)' }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>✓</div>
          No pending approvals. All clear.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {approvalItems.map(a => {
            const isBusy = approvalBusy?.id === a.id;
            const busyAction = isBusy ? approvalBusy?.action : null;
            const itemError = approvalErrors[a.id];
            return (
            <div key={a.id} style={{ background: 'rgba(8,14,28,0.85)', border: `1px solid ${itemError ? 'rgba(239,68,68,0.35)' : 'rgba(245,158,11,0.2)'}`, borderRadius: 12, padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: 'rgba(200,220,255,0.9)', fontWeight: 600 }}>{a.description ?? a.action_type ?? 'Action pending approval'}</div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                    {a.action_type && <span style={{ fontSize: 9, padding: '1px 5px', background: 'rgba(34,211,238,0.1)', color: '#22d3ee', borderRadius: 3 }}>{a.action_type}</span>}
                    {a.tier && <span style={{ fontSize: 9, padding: '1px 5px', background: 'rgba(245,158,11,0.1)', color: '#f59e0b', borderRadius: 3 }}>{a.tier}</span>}
                    <span style={{ fontSize: 9, padding: '1px 5px', background: 'rgba(100,120,140,0.15)', color: 'rgba(140,160,180,0.6)', borderRadius: 3, fontFamily: 'var(--font-hud, monospace)' }}>{a.id.slice(0, 16)}</span>
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => onApprove(a.id)}
                  disabled={isBusy}
                  style={{ flex: 1, padding: '7px', borderRadius: 8, fontSize: 11, fontWeight: 600, background: isBusy && busyAction === 'approve' ? 'rgba(61,220,151,0.05)' : 'rgba(61,220,151,0.15)', color: '#3ddc97', border: '1px solid rgba(61,220,151,0.3)', cursor: isBusy ? 'wait' : 'pointer', opacity: isBusy ? 0.6 : 1 }}
                >
                  {isBusy && busyAction === 'approve' ? 'Approving…' : '✓ Approve'}
                </button>
                <button
                  onClick={() => onDeny(a.id)}
                  disabled={isBusy}
                  style={{ flex: 1, padding: '7px', borderRadius: 8, fontSize: 11, fontWeight: 600, background: isBusy && busyAction === 'deny' ? 'rgba(239,68,68,0.05)' : 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.25)', cursor: isBusy ? 'wait' : 'pointer', opacity: isBusy ? 0.6 : 1 }}
                >
                  {isBusy && busyAction === 'deny' ? 'Denying…' : '✗ Deny'}
                </button>
              </div>
              {itemError && (
                <div style={{ marginTop: 8, fontSize: 10, color: '#fca5a5', padding: '6px 8px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, lineHeight: 1.4 }}>
                  ⚠ {itemError}
                </div>
              )}
            </div>
            );
          })}
        </div>
      )}

      {/* Hard gates reminder */}
      <div style={{ marginTop: 20, padding: '8px 12px', background: 'rgba(239,68,68,0.06)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.12)' }}>
        <div style={{ fontSize: 10, color: '#ef4444', fontWeight: 600, marginBottom: 4 }}>Hard-gated operations — require explicit Bryan approval</div>
        {['Production deploy', 'Destructive git ops', 'IAM / billing changes', 'Outbound sends (Slack/Telegram/email)', 'Secret access', 'Governance bypass'].map(g => (
          <div key={g} style={{ fontSize: 10, color: 'rgba(239,100,100,0.6)', padding: '1px 0' }}>• {g}</div>
        ))}
      </div>
    </div>
  );
}

// — Workbench —
function WorkbenchSurface({ workflowStatus, macWorkerStatus, orchestration, fetchState, apiTarget, isNarrow, onExpand }: {
  workflowStatus: { status?: string; workflow_id?: string; commit_hash?: string } | null;
  macWorkerStatus: { queued: number; running: number; failed: number } | null;
  orchestration: OrchestrationSummary | null;
  fetchState: Record<string, PanelFetchState>;
  apiTarget: string;
  isNarrow: boolean;
  onExpand: (id: PanelId) => void;
}) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: isNarrow ? '12px' : '20px 24px' }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.4)', textTransform: 'uppercase', marginBottom: 16 }}>Workbench — Local Coding Environment</div>
      <div style={{ display: 'grid', gridTemplateColumns: isNarrow ? '1fr' : '1fr 1fr', gap: 12 }}>

        {/* Coding workflow */}
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>🔧 Coding Workflow</div>
          {workflowStatus
            ? <Row label={workflowStatus.workflow_id ?? 'Last run'} value={workflowStatus.status ?? '—'} status={workflowStatus.status === 'COMPLETE' ? 'ok' : 'warn'} />
            : fetchState.workflow?.status === 'error'
              ? <BackendError endpoint="/v1/coding/workflow/status" target={apiTarget} />
              : <Row label="Status" value="No workflow run yet" status="warn" />
          }
          <button onClick={() => onExpand('workbench')} style={{ marginTop: 8, fontSize: 9, color: 'rgba(34,211,238,0.4)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>details →</button>
        </div>

        {/* Mac worker queue */}
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>⚡ Mac Worker Queue</div>
          {macWorkerStatus ? (
            <>
              <Row label="Queued" value={macWorkerStatus.queued} />
              <Row label="Running" value={macWorkerStatus.running} />
              <Row label="Failed" value={macWorkerStatus.failed} status={macWorkerStatus.failed > 0 ? 'warn' : 'ok'} />
            </>
          ) : <BackendError endpoint="/v1/mac-worker/status" target={apiTarget} />}
        </div>

        {/* Orchestration policy */}
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>📐 Orchestration Policy</div>
          {orchestration ? (
            <>
              <Row label="DAG safety rules" value={orchestration.dag_rules} status="ok" />
              <Row label="Elastic pool roles" value={orchestration.elastic_pool_roles} status="ok" />
              <Row label="Retrieval teams" value={orchestration.retrieval_teams} status="ok" />
            </>
          ) : <Row label="Status" value={fetchState.orchestration?.status === 'error' ? 'Error fetching' : 'Loading…'} status={fetchState.orchestration?.status === 'error' ? 'error' : 'unknown'} />}
        </div>

        {/* Available ops */}
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>📡 Available Operations</div>
          {[
            ['Coding workflow', 'WIRED'],
            ['File read/diff', 'WIRED'],
            ['Testing / lint', 'WIRED'],
            ['Git commit/push', 'WIRED'],
            ['Deploy plan', 'DRY_RUN_ONLY'],
          ].map(([name, s]) => (
            <Row key={name} label={String(name)} value={s} status={s === 'WIRED' ? 'ok' : 'warn'} />
          ))}
        </div>

        {/* Cloud workbench */}
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(96,165,250,0.12)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>☁️ Cloud Workbench</div>
          <div style={{ fontSize: 10, color: 'rgba(96,165,250,0.6)', padding: '4px 8px', background: 'rgba(96,165,250,0.08)', borderRadius: 6 }}>
            Pending Plan 2 — cloud-hosted coding agents not yet deployed.
          </div>
        </div>
      </div>
    </div>
  );
}

// — Audit —
function AuditSurface({ logs, auditEntries, auditCount, fetchState, apiTarget, isNarrow }: {
  logs: { text: string; level: string; time: string }[];
  auditEntries: { action_type?: string; execution_status?: string; actor?: string }[];
  auditCount: number;
  fetchState: Record<string, PanelFetchState>;
  apiTarget: string;
  isNarrow: boolean;
}) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: isNarrow ? '12px' : '20px 24px' }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.4)', textTransform: 'uppercase', marginBottom: 16 }}>Audit / Governance Log</div>
      <div style={{ display: 'grid', gridTemplateColumns: isNarrow ? '1fr' : '1fr 1fr', gap: 12 }}>
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px', gridColumn: isNarrow ? 'auto' : '1/-1' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>📜 Recent Events ({auditCount} total)</div>
          {fetchState.audit?.status === 'error'
            ? <BackendError endpoint="/v1/authority/audit" target={apiTarget} />
            : auditEntries.length === 0
              ? <div style={{ fontSize: 10, color: 'rgba(100,140,180,0.4)', padding: '8px 0' }}>No audit events captured yet.</div>
              : auditEntries.map((e, i) => (
                <Row key={i} label={e.action_type ?? 'event'} value={e.execution_status ?? '—'} status={e.execution_status === 'failed' ? 'error' : 'ok'} />
              ))
          }
        </div>
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>🛡 Governance Gates</div>
          <Row label="Secret scan" value="Active on all API responses" status="ok" />
          <Row label="Hard gates" value="Approval required for deploy / destructive ops" status="ok" />
          <Row label="Cost control" value="Changed-file-only review enforced" status="ok" />
          <Row label="No raw CoT" value="Structured decision records only" status="ok" />
          <Row label="No hallucination" value="Zero-hallucination rule — AGENTS.md" status="ok" />
        </div>
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>📡 Session Events</div>
          {logs.length === 0
            ? <div style={{ fontSize: 10, color: 'rgba(100,140,180,0.4)' }}>No events this session.</div>
            : logs.slice(0, 6).map((l, i) => (
              <Row key={i} label={l.time} value={l.text.slice(0, 60)} status={l.level === 'error' ? 'error' : 'ok'} />
            ))
          }
        </div>
      </div>
    </div>
  );
}

// — Memory —
function MemorySurface({ memStatus, memLastRefresh, syncBusy, syncResult, apiOk, fetchState, apiTarget, onSync, isNarrow }: {
  memStatus: MemoryStatus | null;
  memLastRefresh: string;
  syncBusy: boolean;
  syncResult: string;
  apiOk: boolean | null;
  fetchState: Record<string, PanelFetchState>;
  apiTarget: string;
  onSync: (mode: 'push' | 'pull' | 'both') => void;
  isNarrow: boolean;
}) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: isNarrow ? '12px' : '20px 24px' }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.4)', textTransform: 'uppercase', marginBottom: 16 }}>Memory — Cross-Device Store</div>
      <div style={{ display: 'grid', gridTemplateColumns: isNarrow ? '1fr' : '1fr 1fr', gap: 12 }}>
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>🧠 Memory Store</div>
          {memStatus ? (
            <>
              <Row label="Total entries" value={memStatus.total_entries} />
              <Row label="Cloud sync" value={memStatus.cloud_sync_available ? 'Active (S3)' : 'Unavailable'} status={memStatus.cloud_sync_available ? 'ok' : 'warn'} />
              {memStatus.bucket && <Row label="S3 bucket" value={memStatus.bucket} />}
              <Row label="Rust extension" value={memStatus.rust_available ? 'Installed' : 'Pure-Python (fallback)'} status={memStatus.rust_available ? 'ok' : 'warn'} />
              <Row label="Last refreshed" value={memLastRefresh || '—'} />
            </>
          ) : (
            fetchState.memory?.status === 'error'
              ? <BackendError endpoint="/v1/memory/status" target={apiTarget} lastOk={memLastRefresh} />
              : <div style={{ fontSize: 10, color: 'rgba(100,140,180,0.4)' }}>Loading…</div>
          )}
        </div>
        <div style={{ background: 'rgba(8,14,28,0.85)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: 12, padding: '12px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(160,200,240,0.8)', marginBottom: 8 }}>☁️ Cross-Device Sync (Plan 9)</div>
          <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.6)', marginBottom: 10, lineHeight: 1.6 }}>
            MacBook writes → push to S3. ECS/iPhone → pull from S3.
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {(['push', 'pull', 'both'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => onSync(mode)}
                disabled={syncBusy || !apiOk}
                style={{ fontSize: 10, padding: '4px 10px', borderRadius: 6, cursor: 'pointer', background: syncBusy ? 'rgba(34,211,238,0.05)' : 'rgba(34,211,238,0.12)', color: '#22d3ee', border: '1px solid rgba(34,211,238,0.2)', opacity: syncBusy || !apiOk ? 0.4 : 1 }}
              >
                {syncBusy ? '…' : mode}
              </button>
            ))}
          </div>
          {syncResult && (
            <div style={{ marginTop: 8, fontSize: 10, color: '#3ddc97', padding: '4px 8px', background: 'rgba(61,220,151,0.08)', borderRadius: 4 }}>✓ {syncResult}</div>
          )}
        </div>
      </div>
    </div>
  );
}

// — Voice —
function VoiceSurface({ isNarrow }: { isNarrow: boolean }) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: isNarrow ? '12px' : '20px 24px' }}>
      <div style={{ maxWidth: 480, margin: '0 auto', paddingTop: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>🎙</div>
        <div style={{ fontSize: 16, fontWeight: 600, color: 'rgba(160,200,240,0.7)', marginBottom: 8 }}>Voice Interface</div>
        <div style={{ display: 'inline-block', fontSize: 10, padding: '3px 10px', background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 4, color: '#f59e0b', marginBottom: 16 }}>
          US13 · PARKED · UNSAFE
        </div>
        <div style={{ fontSize: 11, color: 'rgba(100,140,180,0.5)', lineHeight: 1.7 }}>
          Voice interface (US13) is currently parked.<br />
          Voice capability exists in the backend (useVoiceTurn hook, /v1/voice/turn/* routes) but is not activated in this cockpit.<br />
          Will be unlocked in a future plan sprint after safety review.
        </div>
      </div>
    </div>
  );
}

// — System (all 24 modules grid + plan9 + routing + org chain) —
interface SystemSurfaceProps {
  plan9: Plan9Status | null;
  routingStatus: RoutingStatus | null;
  registry: RegistryStatus | null;
  runtimeProof: RuntimeProofSummary | null;
  agents: AgentEntry[];
  connectors: ConnectorInfo[];
  fetchState: Record<string, PanelFetchState>;
  apiTarget: string;
  plan9LastRefresh: string;
  orgHierarchy: OrgHierarchyData | null;
  orgChainFetch: OrgChainFetchState;
  onExpand: (id: PanelId) => void;
  isNarrow: boolean;
}

function SystemSurface({ plan9, routingStatus, registry, runtimeProof, agents, connectors, fetchState, apiTarget, plan9LastRefresh, orgHierarchy, orgChainFetch, onExpand, isNarrow }: SystemSurfaceProps) {
  const connectorLive = connectors.filter(c => c.connected).length;

  function panelStatus(key: string): StatusDot {
    const s = fetchState[key]?.status;
    if (s === 'error') return 'error';
    if (s === 'ok') return 'ok';
    if (s === 'loading') return 'warn';
    return 'unknown';
  }

  const systemCards: Array<{ id: PanelId; icon: string; label: string; status: StatusDot; line1: string; line2: string }> = [
    {
      id: 'mission', icon: '🎯', label: 'Mission Control', status: panelStatus('health'),
      line1: plan9 ? `P9: ${plan9.gaps} gaps · ${plan9.parked} parked` : 'Fetching…',
      line2: `Cloud: ${plan9?.mobile_cloud_live ?? '—'} · Local: ${plan9?.mac_local_live ?? '—'}`,
    },
    {
      id: 'cockpit', icon: '⚡', label: 'Cockpit / Runtime', status: panelStatus('health'),
      line1: routingStatus ? `PA: ${routingStatus.pa_front_door_model}` : 'Loading…',
      line2: routingStatus ? `${routingStatus.provider_count} providers · ${routingStatus.non_fallback_model_count} cloud models` : '',
    },
    {
      id: 'authority', icon: '🛑', label: 'Authority', status: panelStatus('approvals'),
      line1: 'Emergency stop available',
      line2: 'Hard gates require Bryan approval',
    },
    {
      id: 'workbench', icon: '🔧', label: 'Workbench', status: panelStatus('macWorker'),
      line1: 'Local coding/testing/git workflow',
      line2: fetchState.orchestration?.status === 'ok' ? 'Orchestration policy loaded' : 'Orchestration: fetching…',
    },
    {
      id: 'connectors', icon: '🔌', label: 'Connectors', status: connectors.length > 0 ? (connectorLive === connectors.length ? 'ok' : 'warn') : 'unknown',
      line1: connectors.length > 0 ? `${connectorLive}/${connectors.length} connected` : '0 connectors configured',
      line2: connectors.filter(c => !c.connected).slice(0, 2).map(c => c.name).join(', ') || 'All connected',
    },
    {
      id: 'agents', icon: '🤖', label: 'Agent Roster', status: panelStatus('registry'),
      line1: registry ? `${registry.total_managers} managers · ${registry.total_workers} workers` : 'Loading…',
      line2: registry ? `${registry.total_roles} total roles` : agents.length ? `${agents.length} domains` : '',
    },
    {
      id: 'memory', icon: '🧠', label: 'Memory', status: panelStatus('memory'),
      line1: 'Memory store + S3 cross-device sync',
      line2: '',
    },
    {
      id: 'plan9', icon: '🚀', label: 'Plan 9 / Parity', status: plan9 ? (plan9.gaps > 0 ? 'warn' : 'ok') : 'unknown',
      line1: plan9 ? `Verdict: ${plan9.verdict ?? '—'}` : 'Fetching…',
      line2: runtimeProof ? `Proof: ${runtimeProof.verified_count}/${runtimeProof.total_items} verified` : '',
    },
    {
      id: 'logs', icon: '📜', label: 'Logs / Audit', status: panelStatus('audit'),
      line1: 'Authority audit trail',
      line2: 'Governance: all gates active',
    },
    {
      id: 'routing', icon: '🔀', label: 'Model Routing', status: panelStatus('routing'),
      line1: routingStatus ? `${routingStatus.provider_count} providers · ${routingStatus.role_declaration_count} roles` : 'Loading…',
      line2: routingStatus ? `GLM-5.2: ${routingStatus.glm_5_2_available ? '✓' : '–'} · Kimi: ${routingStatus.kimi_k2_6_available ? '✓' : '–'}` : '',
    },
    {
      id: 'org-chain', icon: '🏗', label: 'Org Chain', status: orgChainFetch.status === 'ok' ? 'ok' : orgChainFetch.status === 'error' ? 'error' : 'unknown',
      line1: orgHierarchy ? `PA → COS/GM → ${orgHierarchy.nodes.filter(n => n.layer === 'manager').length}M → Reviewer` : 'Loading…',
      line2: 'Reviewer: independent · self-verify blocked',
    },
    {
      id: 'settings', icon: '⚙️', label: 'Settings', status: 'ok',
      line1: 'Server URL, model, auth, theme',
      line2: 'Developer tools & preferences',
    },
  ];

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: isNarrow ? '12px' : '16px 20px' }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.4)', textTransform: 'uppercase', marginBottom: 12 }}>All Modules — System Overview</div>

      {/* System module grid */}
      <div style={{ display: 'grid', gap: 7, gridTemplateColumns: isNarrow ? 'repeat(auto-fill, minmax(140px, 1fr))' : 'repeat(auto-fill, minmax(160px, 1fr))', marginBottom: 20 }}>
        {systemCards.map(card => (
          <button
            key={card.id}
            onClick={() => onExpand(card.id)}
            className="group"
            style={{ textAlign: 'left', background: 'rgba(8,14,28,0.82)', border: '1px solid rgba(34,211,238,0.09)', backdropFilter: 'blur(10px)', borderRadius: 10, padding: '8px 10px', cursor: 'pointer', minWidth: 0, position: 'relative', transition: 'border-color 0.15s' }}
            title={`Click to expand ${card.label}`}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 12 }}>{card.icon}</span>
              <span style={{ fontSize: 10, fontWeight: 600, color: 'rgba(160,200,240,0.8)', letterSpacing: '0.03em', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{card.label}</span>
              {dot(card.status)}
            </div>
            <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.6)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.4 }}>{card.line1}</div>
            {card.line2 && <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.4 }}>{card.line2}</div>}
            <div style={{ position: 'absolute', bottom: 4, right: 6, fontSize: 8, color: 'rgba(34,211,238,0.2)', opacity: 0, transition: 'opacity 0.15s' }} className="group-hover:opacity-100">expand ↗</div>
          </button>
        ))}
      </div>

      {/* 24 canonical modules availability table */}
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.4)', textTransform: 'uppercase', marginBottom: 10 }}>All 24 Canonical Modules</div>
      <div style={{ display: 'grid', gap: 5, gridTemplateColumns: isNarrow ? '1fr' : 'repeat(auto-fill, minmax(220px, 1fr))' }}>
        {ALL_MODULES.map(m => {
          const ab = availBadge(m.availability);
          return (
            <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', background: 'rgba(8,14,28,0.6)', border: '1px solid rgba(34,211,238,0.06)', borderRadius: 7 }}>
              <span style={{ fontSize: 12, flexShrink: 0 }}>{m.icon}</span>
              <span style={{ fontSize: 10, color: 'rgba(140,180,210,0.7)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.label}</span>
              <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, background: `${ab.color}18`, color: ab.color, border: `1px solid ${ab.color}2a`, flexShrink: 0 }}>{ab.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export function JarvisCockpitPage() {
  const isNarrow = useIsNarrow();

  // Mode + palette state
  const [activeMode, setActiveMode] = useState<FocusMode>('mission');
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [expandedPanel, setExpandedPanel] = useState<PanelId | null>(null);

  // Core state
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [lastReply, setLastReply] = useState('');
  const [phase, setPhase] = useState<TurnPhase>('idle');

  // Fetched data — all preserved from original cockpit
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [apiTarget, setApiTarget] = useState('');
  const [model, setModel] = useState('');
  const [version, setVersion] = useState('');
  const [gitCommit, setGitCommit] = useState('');
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [approvalItems, setApprovalItems] = useState<ApprovalItem[]>([]);
  const [approvalBusy, setApprovalBusy] = useState<ApprovalBusyState | null>(null);
  const [approvalErrors, setApprovalErrors] = useState<Record<string, string>>({});
  const [auditCount, setAuditCount] = useState(0);
  const [auditEntries, setAuditEntries] = useState<{ action_type?: string; execution_status?: string; actor?: string }[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState<{ status?: string; workflow_id?: string; commit_hash?: string } | null>(null);
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [memStatus, setMemStatus] = useState<MemoryStatus | null>(null);
  const [memLastRefresh, setMemLastRefresh] = useState('');
  const [plan9, setPlan9] = useState<Plan9Status | null>(null);
  const [plan9LastRefresh, setPlan9LastRefresh] = useState('');
  const [agents, setAgents] = useState<AgentEntry[]>([]);
  const [logs, setLogs] = useState<{ text: string; level: string; time: string }[]>([]);
  const [macWorkerStatus, setMacWorkerStatus] = useState<{ queued: number; running: number; failed: number } | null>(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncResult, setSyncResult] = useState('');
  const [routingStatus, setRoutingStatus] = useState<RoutingStatus | null>(null);
  const [registry, setRegistry] = useState<RegistryStatus | null>(null);
  const [orchestration, setOrchestration] = useState<OrchestrationSummary | null>(null);
  const [runtimeProof, setRuntimeProof] = useState<RuntimeProofSummary | null>(null);
  const [orgHierarchy, setOrgHierarchy] = useState<OrgHierarchyData | null>(null);
  const [orgChainFetch, setOrgChainFetch] = useState<OrgChainFetchState>({ status: 'idle' });
  const [fetchState, setFetchState] = useState<Record<string, PanelFetchState>>({});

  const setPanelFetch = (key: string) => (s: PanelFetchState) => setFetchState(prev => ({ ...prev, [key]: s }));
  const connectorLive = connectors.filter(c => c.connected).length;

  // Derive cockpit orb phase from real state
  const cockpitPhase: TurnPhase = (() => {
    if (phase !== 'idle') return phase;
    if (pendingApprovals > 0) return 'waiting_for_silence'; // amber = approval
    if (fetchState.approvals?.status === 'error' || fetchState.health?.status === 'error') return 'error';
    if (sending) return 'thinking';
    return 'idle';
  })();

  // ─────────────────────────────────────────────────────────────────────────
  // Data fetchers — all preserved from original cockpit
  // ─────────────────────────────────────────────────────────────────────────

  const fetchAll = useCallback(async (isOk: boolean) => {
    if (!isOk) return;

    await fetchTracked('/health', setPanelFetch('health'), async (r) => {
      const d = await r.json();
      setModel(d.model ?? '');
      setVersion(d.version ?? '');
      setGitCommit(d.git_commit ?? '');
    });

    await fetchTracked('/v1/authority/approvals/pending', setPanelFetch('approvals'), async (r) => {
      const d = await r.json();
      const list = d?.approvals ?? [];
      setPendingApprovals(d?.count ?? list.length);
      setApprovalItems(list.slice(0, 20).map((a: { approval_id?: string; action_preview?: string; action_type?: string; status?: string; tier?: string }) => ({
        id: a.approval_id ?? 'unknown',
        description: a.action_preview ?? a.action_type,
        status: a.status,
        action_type: a.action_type,
        tier: a.tier,
      })));
    });

    await fetchTracked('/v1/authority/audit?limit=10', setPanelFetch('audit'), async (r) => {
      const d = await r.json();
      const entries = d?.entries ?? [];
      setAuditCount(d?.total_count ?? entries.length);
      setAuditEntries(entries.slice(0, 10));
      setLogs(entries.slice(0, 8).map((e: { action_type?: string; execution_status?: string; ts?: number }) => ({
        text: `${e.action_type ?? 'event'} — ${e.execution_status ?? 'unknown'}`,
        level: e.execution_status === 'failed' ? 'error' : 'info',
        time: e.ts ? new Date(e.ts * 1000).toLocaleTimeString() : '',
      })));
    });

    await fetchTracked('/v1/coding/workflow/status', setPanelFetch('workflow'), async (r) => {
      const d = await r.json();
      setWorkflowStatus(d?.last_workflow ?? null);
    });

    await fetchTracked('/v1/connectors', setPanelFetch('connectors'), async (r) => {
      const d = await r.json();
      const all: { name?: string; is_connected?: boolean; endpoint?: string }[] = Array.isArray(d) ? d : (d?.connectors ?? []);
      setConnectors(all.map(c => ({ name: c.name ?? 'unknown', connected: !!c.is_connected, endpoint: c.endpoint })));
    });

    await fetchTracked('/v1/memory/status', setPanelFetch('memory'), async (r) => {
      const d = await r.json();
      const mos = d.memory_os ?? {};
      const cs = d.cloud_sync ?? {};
      setMemStatus({ total_entries: mos.total_entries ?? 0, cloud_sync_available: cs.available ?? false, bucket: cs.bucket, rust_available: d.rust_available });
      setMemLastRefresh(ts());
    });

    await fetchTracked('/v1/parity/status', setPanelFetch('parity'), async (r) => {
      const d = await r.json();
      setPlan9({ verdict: d.plan9_verdict ?? undefined, mobile_cloud_live: d.mobile_cloud_live ?? 0, mac_local_live: d.mac_local_live ?? 0, parked: Array.isArray(d.parked) ? d.parked.length : 0, gaps: Array.isArray(d.gaps) ? d.gaps.length : 0 });
      setPlan9LastRefresh(ts());
    });

    await fetchTracked('/v1/capabilities/status', setPanelFetch('capabilities'), async (r) => {
      const d = await r.json();
      const caps: { capability_id?: string; display_name?: string; domain?: string; status?: string }[] = Array.isArray(d) ? d : (d?.capabilities ?? []);
      const domainMap = new Map<string, AgentEntry>();
      caps.forEach(cap => {
        const domain = cap.domain ?? 'unknown';
        if (!domainMap.has(domain)) domainMap.set(domain, { id: domain, name: domain.replace(/_/g, ' '), kind: 'manager', status: cap.status ?? 'active', domain });
      });
      setAgents(Array.from(domainMap.values()));
    });

    await fetchTracked('/v1/plan9/registry', setPanelFetch('registry'), async (r) => {
      const d = await r.json();
      setRegistry({ total_roles: d.total_roles ?? 0, total_managers: d.total_managers ?? 0, total_workers: d.total_workers ?? 0 });
    });

    await fetchTracked('/v1/mac-worker/status', setPanelFetch('macWorker'), async (r) => {
      const d = await r.json();
      setMacWorkerStatus({ queued: d.total_tasks ?? d.queued ?? 0, running: d.running ?? 0, failed: d.failed ?? 0 });
    });

    await fetchTracked('/v1/model-routing/status', setPanelFetch('routing'), async (r) => {
      const d = await r.json();
      setRoutingStatus({
        provider_count: d.provider_count ?? 0, model_count: d.model_count ?? 0, non_fallback_model_count: d.non_fallback_model_count ?? 0,
        kimi_benchmarked: d.kimi_benchmarked ?? false, glm_5_2_available: d.glm_5_2_available ?? false, kimi_k2_6_available: d.kimi_k2_6_available ?? false,
        heavy_coding_route_preference: d.heavy_coding_route_preference ?? '', role_declaration_count: d.role_declaration_count ?? 0,
        pa_front_door_model: d.pa_front_door_model ?? '—', active_routing_policy: d.active_routing_policy ?? '—',
        blocked_providers: d.blocked_providers ?? [], benchmark_status: d.benchmark_status ?? {},
        policy_labels: d.policy_labels ?? {}, provider_health: d.provider_health ?? {},
      });
    });

    await fetchTracked('/v1/orchestration/policy', setPanelFetch('orchestration'), async (r) => {
      const d = await r.json();
      setOrchestration({ elastic_pool_roles: (d.elastic_pools?.roles ?? []).length, dag_rules: (d.parallel_dag?.safety_rules ?? []).length, retrieval_teams: Object.keys(d.retrieval_worker_policies ?? {}).length });
    });

    await fetchTracked('/v1/plan9/runtime-proof-checklist', setPanelFetch('runtimeProof'), async (r) => {
      const d = await r.json();
      setRuntimeProof({ total_items: d.total_items ?? 0, verified_count: d.verified_count ?? 0, pending_count: d.pending_count ?? 0 });
    });

    setOrgChainFetch({ status: 'loading' });
    try {
      const r = await apiFetch('/v1/plan9/org-hierarchy');
      if (!r.ok) {
        let detail = r.statusText;
        try { const j = await r.json(); detail = j.detail ?? detail; } catch { /* ok */ }
        setOrgChainFetch({ status: 'error', httpStatus: r.status, detail: String(detail) });
      } else {
        const d = await r.json();
        setOrgHierarchy(d as OrgHierarchyData);
        setOrgChainFetch({ status: 'ok' });
      }
    } catch (e) {
      setOrgChainFetch({ status: 'error', detail: String(e) });
    }
  }, []);

  useEffect(() => {
    const baseUrl: string = (typeof window !== 'undefined' && (localStorage.getItem('oj-server-url') ?? '')) || 'localhost:8000';
    setApiTarget(baseUrl);
    const check = () => checkHealth().then(ok => { setApiOk(ok); if (ok) fetchAll(ok); });
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // ⌘K palette
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setPaletteOpen(p => !p); }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Actions
  // ─────────────────────────────────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    const msg = input.trim();
    if (!msg || sending) return;
    setSending(true);
    setPhase('thinking');
    setLastReply('');
    setInput('');
    try {
      const res = await apiFetch('/v1/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: model || 'default', messages: [{ role: 'user', content: msg }], stream: false }) });
      const data = await res.json();
      const reply: string = data?.choices?.[0]?.message?.content ?? data?.error ?? 'No reply.';
      setLastReply(reply.slice(0, 800));
      setPhase('speaking');
      setTimeout(() => setPhase('idle'), 3000);
    } catch (err) {
      setLastReply(`Error: ${String(err)}`);
      setPhase('error');
    } finally {
      setSending(false);
    }
  }, [input, sending, model]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  }, [handleSubmit]);

  const handleMemorySync = useCallback(async (mode: 'push' | 'pull' | 'both') => {
    setSyncBusy(true);
    setSyncResult('');
    try {
      const res = await apiFetch(`/v1/memory/sync?mode=${mode}`, { method: 'POST' });
      const d = await res.json();
      const pull = d.pull ?? {};
      const push = d.push ?? {};
      setSyncResult(
        mode === 'push' ? `Pushed ${push.entries_transferred ?? '?'} entries` :
        mode === 'pull' ? `Pulled ${pull.imported ?? '?'} / ${pull.total_from_s3 ?? '?'}` :
        `Push: ${push.entries_transferred ?? '?'} | Pull: ${pull.imported ?? '?'}`,
      );
      setMemStatus(prev => prev ? { ...prev, total_entries: d.total_entries_after ?? prev.total_entries } : prev);
    } catch (err) {
      setSyncResult(`Sync error: ${String(err)}`);
    } finally {
      setSyncBusy(false);
    }
  }, []);

  const handleApprove = useCallback(async (id: string) => {
    setApprovalBusy({ id, action: 'approve' });
    setApprovalErrors(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const res = await apiFetch(`/v1/approvals/${id}/approve`, { method: 'POST' });
      if (!res.ok) {
        const detail = await parseApprovalActionError(res);
        setApprovalErrors(prev => ({ ...prev, [id]: `Approve failed (HTTP ${res.status}): ${detail}` }));
        return;
      }
      setPendingApprovals(p => Math.max(0, p - 1));
      setApprovalItems(prev => prev.filter(a => a.id !== id));
      setApprovalErrors(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      setApprovalErrors(prev => ({ ...prev, [id]: `Approve failed: ${String(err)}` }));
    } finally {
      setApprovalBusy(null);
    }
  }, []);

  const handleDeny = useCallback(async (id: string) => {
    setApprovalBusy({ id, action: 'deny' });
    setApprovalErrors(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const res = await apiFetch(`/v1/approvals/${id}/deny`, { method: 'POST' });
      if (!res.ok) {
        const detail = await parseApprovalActionError(res);
        setApprovalErrors(prev => ({ ...prev, [id]: `Deny failed (HTTP ${res.status}): ${detail}` }));
        return;
      }
      setPendingApprovals(p => Math.max(0, p - 1));
      setApprovalItems(prev => prev.filter(a => a.id !== id));
      setApprovalErrors(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      setApprovalErrors(prev => ({ ...prev, [id]: `Deny failed: ${String(err)}` }));
    } finally {
      setApprovalBusy(null);
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Expanded overlays — all preserved from original + org-chain
  // ─────────────────────────────────────────────────────────────────────────

  function renderExpanded(id: PanelId) {
    switch (id) {
      case 'mission':
        return (
          <Overlay title="Mission Control" icon="🎯" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>System Health</SectionHeading>
            <Row label="Backend" value={apiOk ? 'Reachable' : 'Unreachable'} status={apiOk ? 'ok' : 'error'} />
            <Row label="Target" value={apiTarget || '—'} />
            <Row label="Model" value={model || '—'} />
            <Row label="Version" value={version ? `v${version}` : '—'} />
            <SectionHeading>Plan 9 Parity</SectionHeading>
            {plan9 ? (
              <>
                <Row label="Cloud/Mobile live" value={plan9.mobile_cloud_live} status="ok" />
                <Row label="Mac/Local live" value={plan9.mac_local_live} status="ok" />
                <Row label="Capability gaps" value={plan9.gaps} status={plan9.gaps > 0 ? 'warn' : 'ok'} />
                <Row label="Parked" value={plan9.parked} />
                <Row label="Last checked" value={plan9LastRefresh || '—'} />
              </>
            ) : <BackendError endpoint="/v1/parity/status" target={apiTarget} />}
            <SectionHeading>Pending Approvals</SectionHeading>
            {pendingApprovals === 0
              ? <Row label="Approvals" value="None pending" status="ok" />
              : approvalItems.map(a => <Row key={a.id} label={a.id.slice(0, 20)} value={a.description ?? a.status ?? '—'} status="warn" />)
            }
          </Overlay>
        );
      case 'cockpit':
        return (
          <Overlay title="Cockpit — Runtime" icon="⚡" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Runtime Engine</SectionHeading>
            <Row label="Active model" value={model || '—'} />
            <Row label="Server version" value={version ? `v${version}` : '—'} />
            <Row label="Git commit" value={gitCommit || '—'} />
            <Row label="API target" value={apiTarget || '—'} />
            <Row label="Health" value={apiOk ? 'OK' : 'Unreachable'} status={apiOk ? 'ok' : 'error'} />
            <SectionHeading>Mac Worker Queue</SectionHeading>
            {macWorkerStatus ? (
              <>
                <Row label="Queued tasks" value={macWorkerStatus.queued} />
                <Row label="Running" value={macWorkerStatus.running} />
                <Row label="Failed" value={macWorkerStatus.failed} status={macWorkerStatus.failed > 0 ? 'warn' : 'ok'} />
              </>
            ) : <BackendError endpoint="/v1/mac-worker/status" target={apiTarget} />}
          </Overlay>
        );
      case 'authority':
        return (
          <Overlay title="Authority / Emergency Stop" icon="🛑" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Pending Approvals</SectionHeading>
            {pendingApprovals === 0
              ? <Row label="Queue" value="Empty — no pending approvals" status="ok" />
              : approvalItems.map(a => <Row key={a.id} label={a.id.slice(0, 20)} value={a.description ?? '—'} status="warn" />)
            }
            <SectionHeading>Recent Audit ({auditCount})</SectionHeading>
            {auditEntries.length === 0
              ? <Row label="Audit" value="No events yet" status="warn" />
              : auditEntries.map((e, i) => <Row key={i} label={e.action_type ?? 'event'} value={e.execution_status ?? '—'} status={e.execution_status === 'failed' ? 'error' : 'ok'} />)
            }
            <SectionHeading>Hard-Gated Operations</SectionHeading>
            {['Production deploy', 'Destructive git ops', 'IAM / billing changes', 'Outbound sends'].map(g => (
              <Row key={g} label="blocked" value={g} status="error" />
            ))}
          </Overlay>
        );
      case 'workbench':
        return (
          <Overlay title="Workbench" icon="🔧" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Coding Workflow</SectionHeading>
            {workflowStatus
              ? <Row label={workflowStatus.workflow_id ?? 'last'} value={workflowStatus.status ?? '—'} status={workflowStatus.status === 'COMPLETE' ? 'ok' : 'warn'} />
              : <Row label="Workflow" value="No workflow run yet" status="warn" />
            }
            <SectionHeading>Available Operations</SectionHeading>
            {[['Coding / workflow', '/v1/coding/workflow/run', 'WIRED'], ['Coding / read file', '/v1/coding/files/read', 'WIRED'], ['Testing / run', '/v1/testing/run', 'WIRED'], ['Testing / lint', '/v1/testing/lint', 'WIRED'], ['Git / commit', '/v1/git/commit', 'WIRED'], ['Deploy / plan', '/v1/deploy/plan', 'DRY_RUN_ONLY']].map(([name, route, s]) => (
              <Row key={route} label={String(name)} value={<code style={{ fontSize: 9 }}>{route}</code>} status={s === 'WIRED' ? 'ok' : 'warn'} />
            ))}
          </Overlay>
        );
      case 'connectors':
        return (
          <Overlay title="Connectors" icon="🔌" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Connector Status</SectionHeading>
            {connectors.length === 0
              ? <BackendError endpoint="/v1/connectors" target={apiTarget} />
              : connectors.map(c => <Row key={c.name} label={c.name} value={c.endpoint ?? (c.connected ? 'connected' : 'disconnected')} status={c.connected ? 'ok' : 'error'} />)
            }
          </Overlay>
        );
      case 'agents':
        return (
          <Overlay title="Agent Roster" icon="🤖" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Plan 9 Manager Domains ({agents.length})</SectionHeading>
            {agents.length === 0
              ? <BackendError endpoint="/v1/capabilities/status" target={apiTarget} lastOk={plan9LastRefresh} />
              : agents.map(a => <Row key={a.id} label={a.name} value={a.domain} status="ok" />)
            }
            <SectionHeading>Registry Summary</SectionHeading>
            {registry ? (
              <>
                <Row label="Total managers" value={registry.total_managers} status="ok" />
                <Row label="Total workers" value={registry.total_workers} status="ok" />
                <Row label="Total roles" value={registry.total_roles} status="ok" />
              </>
            ) : <BackendError endpoint="/v1/plan9/registry" target={apiTarget} />}
          </Overlay>
        );
      case 'memory':
        return (
          <Overlay title="Memory Backend" icon="🧠" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Memory Store</SectionHeading>
            {memStatus ? (
              <>
                <Row label="Total entries" value={memStatus.total_entries} />
                <Row label="Cloud sync" value={memStatus.cloud_sync_available ? 'Active (S3)' : 'Unavailable'} status={memStatus.cloud_sync_available ? 'ok' : 'warn'} />
                {memStatus.bucket && <Row label="S3 bucket" value={memStatus.bucket} />}
                <Row label="Rust extension" value={memStatus.rust_available ? 'Installed' : 'Not installed'} status={memStatus.rust_available ? 'ok' : 'warn'} />
              </>
            ) : <BackendError endpoint="/v1/memory/status" target={apiTarget} lastOk={memLastRefresh} />}
            <SectionHeading>Cross-Device Sync</SectionHeading>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
              {(['push', 'pull', 'both'] as const).map(mode => (
                <button key={mode} onClick={() => handleMemorySync(mode)} disabled={syncBusy || !apiOk} style={{ fontSize: 10, padding: '4px 10px', borderRadius: 6, cursor: 'pointer', background: 'rgba(34,211,238,0.12)', color: '#22d3ee', border: '1px solid rgba(34,211,238,0.2)', opacity: syncBusy || !apiOk ? 0.4 : 1 }}>
                  {syncBusy ? '…' : mode}
                </button>
              ))}
            </div>
            {syncResult && <div style={{ marginTop: 8, fontSize: 10, color: '#3ddc97' }}>✓ {syncResult}</div>}
          </Overlay>
        );
      case 'plan9':
        return (
          <Overlay title="Plan 9 — Cross-Device Parity" icon="🚀" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Capability Matrix</SectionHeading>
            {plan9 ? (
              <>
                <Row label="Cloud/Mobile live" value={plan9.mobile_cloud_live} status="ok" />
                <Row label="Mac/Local live" value={plan9.mac_local_live} status="ok" />
                <Row label="Gaps" value={plan9.gaps} status={plan9.gaps > 0 ? 'warn' : 'ok'} />
                <Row label="Parked" value={plan9.parked} />
                <Row label="Last checked" value={plan9LastRefresh || '—'} />
              </>
            ) : <BackendError endpoint="/v1/parity/status" target={apiTarget} />}
            <SectionHeading>Runtime Proof</SectionHeading>
            {runtimeProof ? (
              <>
                <Row label="Total items" value={runtimeProof.total_items} />
                <Row label="Verified" value={runtimeProof.verified_count} status="ok" />
                <Row label="Pending" value={runtimeProof.pending_count} status={runtimeProof.pending_count > 0 ? 'warn' : 'ok'} />
              </>
            ) : <Row label="Runtime proof" value="Loading…" />}
          </Overlay>
        );
      case 'logs':
        return (
          <Overlay title="Logs / Audit" icon="📜" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Recent Events</SectionHeading>
            {logs.length === 0
              ? <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.5)' }}>No events captured this session.</div>
              : logs.map((l, i) => <Row key={i} label={l.time} value={l.text} status={l.level === 'error' ? 'error' : 'ok'} />)
            }
            <SectionHeading>Governance</SectionHeading>
            <Row label="Secret scan" value="Active on all API responses" status="ok" />
            <Row label="Hard gates" value="Approval required for deploy / destructive ops" status="ok" />
            <Row label="Cost control" value="Changed-file-only review enforced" status="ok" />
          </Overlay>
        );
      case 'routing':
        return (
          <Overlay title="Model Routing — Plan 9K" icon="🔀" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Routing System Status</SectionHeading>
            {routingStatus ? (
              <>
                <Row label="Providers configured" value={routingStatus.provider_count} status="ok" />
                <Row label="Cloud models (non-fallback)" value={routingStatus.non_fallback_model_count} status="ok" />
                <Row label="Role declarations" value={routingStatus.role_declaration_count} status="ok" />
                <Row label="Active policy" value={routingStatus.active_routing_policy} status="ok" />
              </>
            ) : <BackendError endpoint="/v1/model-routing/status" target={apiTarget} />}
            <SectionHeading>PA Front-Door Route</SectionHeading>
            {routingStatus && (
              <>
                <Row label="PA model" value={routingStatus.pa_front_door_model} status="ok" />
                <Row label="GLM-5.2 avail" value={routingStatus.glm_5_2_available ? 'Yes' : 'No / key missing'} status={routingStatus.glm_5_2_available ? 'ok' : 'warn'} />
                <Row label="Kimi K2.6 avail" value={routingStatus.kimi_k2_6_available ? 'Yes' : 'No / key missing'} status={routingStatus.kimi_k2_6_available ? 'ok' : 'warn'} />
              </>
            )}
            <SectionHeading>Provider Health</SectionHeading>
            {routingStatus ? (
              Object.entries(routingStatus.provider_health).map(([p, h]) => (
                <Row key={p} label={p} value={String(h)} status={h === 'configured' || h === 'local' || h === 'no_key_required' ? 'ok' : 'warn'} />
              ))
            ) : null}
          </Overlay>
        );
      case 'org-chain':
        return (
          <Overlay title="Jarvis PA — Org Chain & Loop Architecture" icon="🏗" onClose={() => setExpandedPanel(null)}>
            <OrgChainPanel data={orgHierarchy} fetchState={orgChainFetch} apiTarget={apiTarget} />
          </Overlay>
        );
      case 'settings':
        return (
          <Overlay title="Settings" icon="⚙️" onClose={() => setExpandedPanel(null)}>
            <SettingsPage />
          </Overlay>
        );
      default:
        return null;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Work surface dispatcher
  // ─────────────────────────────────────────────────────────────────────────

  function renderWorkSurface() {
    switch (activeMode) {
      case 'mission':
        return (
          <MissionSurface
            phase={cockpitPhase}
            apiOk={apiOk}
            input={input}
            sending={sending}
            lastReply={lastReply}
            onInputChange={setInput}
            onKeyDown={handleKeyDown}
            onSubmit={handleSubmit}
            pendingApprovals={pendingApprovals}
            orgHierarchy={orgHierarchy}
            orgFetchOk={orgChainFetch.status === 'ok'}
            registry={registry}
            routingStatus={routingStatus}
            onExpandPanel={setExpandedPanel}
            onMode={setActiveMode}
            isNarrow={isNarrow}
          />
        );
      case 'workbench':
        return (
          <WorkbenchSurface
            workflowStatus={workflowStatus}
            macWorkerStatus={macWorkerStatus}
            orchestration={orchestration}
            fetchState={fetchState}
            apiTarget={apiTarget}
            isNarrow={isNarrow}
            onExpand={setExpandedPanel}
          />
        );
      case 'approvals':
        return (
          <ApprovalSurface
            approvalItems={approvalItems}
            pendingApprovals={pendingApprovals}
            fetchState={fetchState}
            apiTarget={apiTarget}
            onApprove={handleApprove}
            onDeny={handleDeny}
            approvalBusy={approvalBusy}
            approvalErrors={approvalErrors}
            auditEntries={auditEntries}
            isNarrow={isNarrow}
          />
        );
      case 'audit':
        return (
          <AuditSurface
            logs={logs}
            auditEntries={auditEntries}
            auditCount={auditCount}
            fetchState={fetchState}
            apiTarget={apiTarget}
            isNarrow={isNarrow}
          />
        );
      case 'memory':
        return (
          <MemorySurface
            memStatus={memStatus}
            memLastRefresh={memLastRefresh}
            syncBusy={syncBusy}
            syncResult={syncResult}
            apiOk={apiOk}
            fetchState={fetchState}
            apiTarget={apiTarget}
            onSync={handleMemorySync}
            isNarrow={isNarrow}
          />
        );
      case 'system':
        return (
          <SystemSurface
            plan9={plan9}
            routingStatus={routingStatus}
            registry={registry}
            runtimeProof={runtimeProof}
            agents={agents}
            connectors={connectors}
            fetchState={fetchState}
            apiTarget={apiTarget}
            plan9LastRefresh={plan9LastRefresh}
            orgHierarchy={orgHierarchy}
            orgChainFetch={orgChainFetch}
            onExpand={setExpandedPanel}
            isNarrow={isNarrow}
          />
        );
      case 'voice':
        return <VoiceSurface isNarrow={isNarrow} />;
      default:
        return null;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', width: '100%', height: '100%', overflow: 'hidden', background: '#02040a', fontFamily: 'var(--font-display, sans-serif)' }}>
      <CosmicBackdrop phase={cockpitPhase} voiceEnabled={pendingApprovals > 0 || sending} />

      {/* Command palette */}
      <CockpitCommandPalette
        open={paletteOpen}
        pendingApprovals={pendingApprovals}
        onClose={() => setPaletteOpen(false)}
        onNavigate={(mode) => { setActiveMode(mode); setPaletteOpen(false); }}
      />

      {/* Overlay */}
      {expandedPanel && renderExpanded(expandedPanel)}

      {/* Top status bar */}
      <TopStatusBar
        apiOk={apiOk}
        model={model}
        version={version}
        gitCommit={gitCommit}
        apiTarget={apiTarget}
        plan9={plan9}
        pendingApprovals={pendingApprovals}
        connectorLive={connectorLive}
        connectorTotal={connectors.length}
        activeMode={activeMode}
        onPalette={() => setPaletteOpen(true)}
        onMode={setActiveMode}
      />

      {/* Main area: left rail (desktop) + work surface */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0, position: 'relative', zIndex: 10 }}>
        {/* Left mode rail — desktop only */}
        {!isNarrow && (
          <LeftModeRail
            active={activeMode}
            pendingApprovals={pendingApprovals}
            onMode={setActiveMode}
          />
        )}

        {/* Work surface */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative', minWidth: 0 }}>
          {renderWorkSurface()}
        </div>
      </div>

      {/* Mobile bottom tabs */}
      {isNarrow && (
        <MobileTabBar
          active={activeMode}
          pendingApprovals={pendingApprovals}
          onMode={setActiveMode}
        />
      )}
    </div>
  );
}

export default JarvisCockpitPage;
