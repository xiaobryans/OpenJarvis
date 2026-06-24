/**
 * JarvisCommandCenter — single-page Jarvis HUD (Plan 9 redesign).
 *
 * Layout:
 *   • Top compact system strip  (health · model · cloud target · Plan 9 verdict)
 *   • Central 3D orb            (LivingOrb + CosmicBackdrop)
 *   • Bottom chat composer      (always visible)
 *   • 10 compact floating HUD panels in a grid around the orb
 *
 * Panels (compact by default, click → expanded overlay):
 *   Mission Control · Cockpit · Authority · Workbench · Connectors
 *   Agents · Memory · Plan 9 · Logs/Audit · Settings
 *
 * No sidebar. No route navigation for normal use.
 * All information is reachable from this one page.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { CosmicBackdrop } from '../components/Jarvis/CosmicBackdrop';
import { LivingOrb } from '../components/Jarvis/LivingOrb';
import { SettingsPage } from './SettingsPage';
import { OrgChainPanel } from '../components/OrgChainPanel';
import type { OrgHierarchyData, OrgChainFetchState } from '../components/OrgChainPanel';
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
  last_sync?: string;
}
interface Plan9Status {
  verdict?: string;
  mobile_cloud_live: number;
  mac_local_live: number;
  parked: number;
  gaps: number;
  last_checked?: string;
}
interface AgentEntry { id: string; name: string; kind: 'manager' | 'worker'; status: string; domain: string; }
interface RoutingStatus {
  provider_count: number;
  model_count: number;
  non_fallback_model_count: number;
  kimi_benchmarked: boolean;
  glm_benchmarked?: boolean;
  glm_5_2_available?: boolean;
  kimi_k2_6_available?: boolean;
  heavy_coding_route_preference?: string;
  role_declaration_count: number;
  pa_front_door_model: string;
  active_routing_policy: string;
  blocked_providers: string[];
  benchmark_status: Record<string, string>;
  policy_labels?: Record<string, string>;
  provider_health: Record<string, string>;
  unknown_needs_metadata?: number;
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

// ─────────────────────────────────────────────────────────────────────────────
// Tiny helpers
// ─────────────────────────────────────────────────────────────────────────────

function dot(s: StatusDot): React.ReactNode {
  const colors: Record<StatusDot, string> = {
    ok: '#3ddc97',
    warn: '#f59e0b',
    error: '#ef4444',
    unknown: '#6b7280',
  };
  return (
    <span
      style={{
        display: 'inline-block',
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: colors[s],
        boxShadow: `0 0 4px ${colors[s]}`,
        flexShrink: 0,
      }}
    />
  );
}

function ts() { return new Date().toLocaleTimeString(); }

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
      try {
        const j = await r.json();
        detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j);
      } catch { /* non-json error body */ }
      onState({ status: 'error', httpStatus: r.status, detail, at: ts() });
      return;
    }
    await onData(r);
    onState({ status: 'ok', httpStatus: r.status, at: ts() });
  } catch (e) {
    onState({ status: 'error', detail: String(e), at: ts() });
  }
}

function BackendError({
  endpoint,
  target,
  httpStatus,
  detail,
  lastOk,
}: {
  endpoint: string;
  target: string;
  httpStatus?: number;
  detail?: string;
  lastOk?: string;
}) {
  return (
    <div style={{ color: '#ef4444', fontSize: 10 }}>
      <div>⚠ <code style={{ fontSize: 9 }}>{endpoint}</code></div>
      <div style={{ color: '#9ca3af' }}>Target: {target}</div>
      {httpStatus != null && <div>HTTP status: {httpStatus}</div>}
      {detail && <div style={{ color: '#fca5a5' }}>{detail}</div>}
      {lastOk && <div style={{ color: '#9ca3af' }}>Last OK: {lastOk}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Compact HUD panel card
// ─────────────────────────────────────────────────────────────────────────────

interface HUDCardProps {
  id: PanelId;
  icon: string;
  label: string;
  status: StatusDot;
  lines: (string | React.ReactNode)[];
  onExpand: (id: PanelId) => void;
  badge?: string | number;
}

function HUDCard({ id, icon, label, status, lines, onExpand, badge }: HUDCardProps) {
  return (
    <button
      onClick={() => onExpand(id)}
      className="group text-left transition-all duration-150"
      style={{
        background: 'rgba(8, 14, 28, 0.82)',
        border: '1px solid rgba(34, 211, 238, 0.09)',
        backdropFilter: 'blur(10px)',
        borderRadius: 10,
        padding: '8px 10px',
        minWidth: 0,
        cursor: 'pointer',
        position: 'relative',
      }}
      title={`Click to expand ${label}`}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 12 }}>{icon}</span>
        <span style={{ fontSize: 10, fontWeight: 600, color: 'rgba(160,200,240,0.8)', letterSpacing: '0.03em', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {label}
        </span>
        {dot(status)}
        {badge !== undefined && (
          <span style={{
            fontSize: 9, background: status === 'warn' ? 'rgba(245,158,11,0.2)' : 'rgba(34,211,238,0.15)',
            color: status === 'warn' ? '#f59e0b' : '#22d3ee', borderRadius: 4, padding: '1px 5px',
          }}>{badge}</span>
        )}
      </div>
      {lines.slice(0, 2).map((line, i) => (
        <div key={i} style={{ fontSize: 10, color: 'rgba(140,180,210,0.6)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.4 }}>
          {line}
        </div>
      ))}
      <div style={{
        position: 'absolute', bottom: 4, right: 6, fontSize: 8,
        color: 'rgba(34,211,238,0.2)',
        opacity: 0,
        transition: 'opacity 0.15s',
      }} className="group-hover:opacity-100">
        expand ↗
      </div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Expanded overlay modal
// ─────────────────────────────────────────────────────────────────────────────

function Overlay({ title, icon, onClose, children }: {
  title: string; icon: string; onClose: () => void; children: React.ReactNode;
}) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
        background: 'rgba(2, 4, 10, 0.88)',
        backdropFilter: 'blur(16px)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        position: 'relative', width: '100%', maxWidth: 640,
        maxHeight: '82vh', overflow: 'hidden',
        background: '#080f1c',
        border: '1px solid rgba(34, 211, 238, 0.16)',
        borderRadius: 16,
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '12px 16px', borderBottom: '1px solid rgba(34,211,238,0.08)',
          flexShrink: 0,
        }}>
          <span style={{ fontSize: 16 }}>{icon}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'rgba(180,220,255,0.9)', flex: 1 }}>{title}</span>
          <button
            onClick={onClose}
            style={{ fontSize: 11, color: 'rgba(120,160,200,0.5)', cursor: 'pointer', background: 'none', border: 'none' }}
          >
            ✕ close
          </button>
        </div>
        <div style={{ overflowY: 'auto', padding: '12px 16px', flex: 1 }}>
          {children}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel detail components (expanded overlays)
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
  return (
    <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', color: 'rgba(34,211,238,0.4)', textTransform: 'uppercase', marginTop: 12, marginBottom: 4 }}>
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export function JarvisCockpitPage() {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── core state ──
  const [expandedPanel, setExpandedPanel] = useState<PanelId | null>(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [lastReply, setLastReply] = useState('');
  const [phase, setPhase] = useState<TurnPhase>('idle');

  // ── fetched data ──
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [apiTarget, setApiTarget] = useState('');
  const [model, setModel] = useState('');
  const [version, setVersion] = useState('');
  const [pendingApprovals, setPendingApprovals] = useState<number>(0);
  const [approvalItems, setApprovalItems] = useState<{ id: string; description?: string; status?: string }[]>([]);
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
  const [gitCommit, setGitCommit] = useState('');
  const [orgHierarchy, setOrgHierarchy] = useState<OrgHierarchyData | null>(null);
  const [orgChainFetch, setOrgChainFetch] = useState<OrgChainFetchState>({ status: 'idle' });
  const [fetchState, setFetchState] = useState<Record<string, PanelFetchState>>({});

  const setPanelFetch = (key: string) => (s: PanelFetchState) => {
    setFetchState(prev => ({ ...prev, [key]: s }));
  };

  const panelErr = (key: string) => fetchState[key]?.status === 'error';

  // ── status helpers ──
  const statusForMem = (): StatusDot => {
    if (!apiOk) return 'unknown';
    if (!memStatus) return 'unknown';
    return memStatus.cloud_sync_available ? 'ok' : 'warn';
  };

  const statusForPlan9 = (): StatusDot => {
    if (!plan9) return 'unknown';
    if (plan9.gaps > 0) return 'warn';
    return 'ok';
  };

  const statusForAgents = (): StatusDot => {
    if (panelErr('registry') || panelErr('capabilities')) return 'error';
    if (!registry && !agents.length) return 'unknown';
    return (registry?.total_roles ?? agents.length) > 0 ? 'ok' : 'warn';
  };

  const connectorLive = connectors.filter(c => c.connected).length;
  const statusForConnectors = (): StatusDot => {
    if (panelErr('connectors')) return 'error';
    if (connectors.length === 0) return fetchState.connectors?.status === 'ok' ? 'warn' : 'unknown';
    return connectorLive === connectors.length ? 'ok' : (connectorLive > 0 ? 'warn' : 'error');
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Data fetchers
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
      setApprovalItems(list.slice(0, 10).map((a: { approval_id?: string; action_preview?: string; action_type?: string; status?: string }) => ({
        id: a.approval_id ?? 'unknown',
        description: a.action_preview ?? a.action_type,
        status: a.status,
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
      const all: { name?: string; is_connected?: boolean; endpoint?: string }[] =
        Array.isArray(d) ? d : (d?.connectors ?? []);
      setConnectors(all.map(c => ({
        name: c.name ?? 'unknown',
        connected: !!c.is_connected,
        endpoint: c.endpoint,
      })));
    });

    await fetchTracked('/v1/memory/status', setPanelFetch('memory'), async (r) => {
      const d = await r.json();
      const mos = d.memory_os ?? {};
      const cs = d.cloud_sync ?? {};
      setMemStatus({
        total_entries: mos.total_entries ?? 0,
        cloud_sync_available: cs.available ?? false,
        bucket: cs.bucket,
        rust_available: d.rust_available,
        last_sync: undefined,
      });
      setMemLastRefresh(ts());
    });

    await fetchTracked('/v1/memory/rust-status', setPanelFetch('rust'), async (r) => {
      const d = await r.json();
      setMemStatus(prev => prev ? { ...prev, rust_available: d.rust_available } : {
        total_entries: 0,
        cloud_sync_available: false,
        rust_available: d.rust_available,
      });
    });

    await fetchTracked('/v1/parity/status', setPanelFetch('parity'), async (r) => {
      const d = await r.json();
      setPlan9({
        verdict: d.plan9_verdict ?? undefined,
        mobile_cloud_live: d.mobile_cloud_live ?? 0,
        mac_local_live: d.mac_local_live ?? 0,
        parked: Array.isArray(d.parked) ? d.parked.length : 0,
        gaps: Array.isArray(d.gaps) ? d.gaps.length : 0,
        last_checked: ts(),
      });
      setPlan9LastRefresh(ts());
    });

    await fetchTracked('/v1/capabilities/status', setPanelFetch('capabilities'), async (r) => {
      const d = await r.json();
      const caps: { capability_id?: string; display_name?: string; domain?: string; status?: string }[] =
        Array.isArray(d) ? d : (d?.capabilities ?? []);
      const domainMap = new Map<string, AgentEntry>();
      caps.forEach(cap => {
        const domain = cap.domain ?? 'unknown';
        if (!domainMap.has(domain)) {
          domainMap.set(domain, {
            id: domain,
            name: domain.replace(/_/g, ' '),
            kind: 'manager',
            status: cap.status ?? 'active',
            domain,
          });
        }
      });
      setAgents(Array.from(domainMap.values()));
    });

    await fetchTracked('/v1/plan9/registry', setPanelFetch('registry'), async (r) => {
      const d = await r.json();
      setRegistry({
        total_roles: d.total_roles ?? 0,
        total_managers: d.total_managers ?? 0,
        total_workers: d.total_workers ?? 0,
      });
    });

    await fetchTracked('/v1/mac-worker/status', setPanelFetch('macWorker'), async (r) => {
      const d = await r.json();
      setMacWorkerStatus({
        queued: d.total_tasks ?? d.queued ?? 0,
        running: d.running ?? 0,
        failed: d.failed ?? 0,
      });
    });

    await fetchTracked('/v1/model-routing/status', setPanelFetch('routing'), async (r) => {
      const d = await r.json();
      setRoutingStatus({
        provider_count: d.provider_count ?? 0,
        model_count: d.model_count ?? 0,
        non_fallback_model_count: d.non_fallback_model_count ?? 0,
        kimi_benchmarked: d.kimi_benchmarked ?? false,
        glm_benchmarked: d.glm_benchmarked ?? false,
        glm_5_2_available: d.glm_5_2_available ?? false,
        kimi_k2_6_available: d.kimi_k2_6_available ?? false,
        heavy_coding_route_preference: d.heavy_coding_route_preference ?? '',
        role_declaration_count: d.role_declaration_count ?? 0,
        pa_front_door_model: d.pa_front_door_model ?? '—',
        active_routing_policy: d.active_routing_policy ?? '—',
        blocked_providers: d.blocked_providers ?? [],
        benchmark_status: d.benchmark_status ?? {},
        policy_labels: d.policy_labels ?? {},
        provider_health: d.provider_health ?? {},
        unknown_needs_metadata: d.unknown_needs_metadata ?? 0,
      });
    });

    await fetchTracked('/v1/orchestration/policy', setPanelFetch('orchestration'), async (r) => {
      const d = await r.json();
      setOrchestration({
        elastic_pool_roles: (d.elastic_pools?.roles ?? []).length,
        dag_rules: (d.parallel_dag?.safety_rules ?? []).length,
        retrieval_teams: Object.keys(d.retrieval_worker_policies ?? {}).length,
      });
    });

    await fetchTracked('/v1/plan9/runtime-proof-checklist', setPanelFetch('runtimeProof'), async (r) => {
      const d = await r.json();
      setRuntimeProof({
        total_items: d.total_items ?? 0,
        verified_count: d.verified_count ?? 0,
        pending_count: d.pending_count ?? 0,
      });
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
    // Determine API target from stored settings
    const baseUrl: string = (typeof window !== 'undefined' &&
      (localStorage.getItem('oj-server-url') ?? '')) || 'localhost:8000';
    setApiTarget(baseUrl);

    const check = () => checkHealth().then(ok => {
      setApiOk(ok);
      if (ok) fetchAll(ok);
    });
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

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
      const res = await apiFetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: model || 'default', messages: [{ role: 'user', content: msg }], stream: false }),
      });
      const data = await res.json();
      const reply: string = data?.choices?.[0]?.message?.content ?? data?.error ?? 'No reply.';
      setLastReply(reply.slice(0, 600));
      setPhase('idle');
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
        mode === 'push' ? `Pushed ${push.entries_transferred ?? '?'} entries to S3` :
        mode === 'pull' ? `Pulled ${pull.imported ?? '?'} / ${pull.total_from_s3 ?? '?'} entries from S3` :
        `Push: ${push.entries_transferred ?? '?'} | Pull: ${pull.imported ?? '?'} entries`,
      );
      setMemStatus(prev => prev ? { ...prev, total_entries: d.total_entries_after ?? prev.total_entries } : prev);
    } catch (err) {
      setSyncResult(`Sync error: ${String(err)}`);
    } finally {
      setSyncBusy(false);
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Compact panel data
  // ─────────────────────────────────────────────────────────────────────────

  const connectorOffline = connectors.filter(c => !c.connected);
  const connectorBadge = connectors.length > 0
    ? `${connectorLive}/${connectors.length}`
    : (fetchState.connectors?.status === 'ok' ? '0/0' : '—');

  const panelCards: HUDCardProps[] = [
    {
      id: 'mission',
      icon: '🎯',
      label: 'Mission Control',
      status: apiOk ? (panelErr('parity') ? 'error' : 'ok') : (apiOk === false ? 'error' : 'unknown'),
      lines: [
        apiOk ? 'Cloud + local: reachable' : 'Backend unreachable',
        plan9
          ? `Plan 9: ${plan9.gaps} gaps · ${plan9.parked} parked · ☁${plan9.mobile_cloud_live}/🖥${plan9.mac_local_live}`
          : panelErr('parity')
            ? `Error ${fetchState.parity?.httpStatus ?? ''}`
            : (fetchState.parity?.status === 'loading' ? 'Fetching parity…' : 'Parity: no data'),
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'cockpit',
      icon: '⚡',
      label: 'Cockpit',
      status: apiOk ? (panelErr('health') ? 'error' : 'ok') : 'error',
      lines: [
        model
          ? `Runtime model: ${model}${routingStatus?.pa_front_door_model ? ` · PA: ${routingStatus.pa_front_door_model}` : ''}`
          : (panelErr('health') ? `Health error ${fetchState.health?.httpStatus ?? ''}` : 'Model: fetching…'),
        version ? `v${version}${gitCommit ? ` · ${gitCommit.slice(0, 8)}` : ''}` : 'Version: —',
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'authority',
      icon: '🛑',
      label: 'Authority',
      status: panelErr('approvals') ? 'error' : (pendingApprovals > 0 ? 'warn' : 'ok'),
      badge: pendingApprovals > 0 ? pendingApprovals : undefined,
      lines: [
        panelErr('approvals')
          ? `Approvals error ${fetchState.approvals?.httpStatus ?? ''}`
          : (pendingApprovals > 0 ? `${pendingApprovals} pending approval(s)` : 'No pending approvals'),
        'Emergency stop available',
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'workbench',
      icon: '🔧',
      label: 'Workbench',
      status: panelErr('macWorker') || panelErr('orchestration') ? 'error' : (apiOk ? 'ok' : 'unknown'),
      lines: [
        macWorkerStatus
          ? `Mac queue: ${macWorkerStatus.queued} queued · ${macWorkerStatus.running} running · ${macWorkerStatus.failed} failed`
          : (panelErr('macWorker') ? `Mac worker error ${fetchState.macWorker?.httpStatus ?? ''}` : 'Mac queue: fetching…'),
        orchestration
          ? `DAG rules: ${orchestration.dag_rules} · Elastic pools: ${orchestration.elastic_pool_roles} · Retrieval teams: ${orchestration.retrieval_teams}`
          : (panelErr('orchestration') ? 'Orchestration policy unavailable' : 'Orchestration: fetching…'),
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'connectors',
      icon: '🔌',
      label: 'Connectors',
      status: statusForConnectors(),
      badge: connectorBadge,
      lines: [
        panelErr('connectors')
          ? `Connectors error ${fetchState.connectors?.httpStatus ?? ''}`
          : connectors.length === 0
            ? '0 connectors configured'
            : `${connectorLive} connected · ${connectorOffline.length} offline`,
        connectors.length === 0
          ? 'Configure connectors in settings'
          : connectorOffline.length === 0
            ? 'All configured connectors connected'
            : `Offline: ${connectorOffline.slice(0, 3).map(c => c.name).join(', ')}`,
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'agents',
      icon: '🤖',
      label: 'Agents',
      status: statusForAgents(),
      badge: (registry?.total_roles ?? agents.length) || undefined,
      lines: [
        registry
          ? `${registry.total_managers} managers · ${registry.total_workers} workers · ${registry.total_roles} roles`
          : panelErr('registry')
            ? `Registry error ${fetchState.registry?.httpStatus ?? ''}`
            : (apiOk ? 'Registry: fetching…' : 'Backend unreachable'),
        agents.length ? `${agents.length} capability domains` : '',
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'memory',
      icon: '🧠',
      label: 'Memory',
      status: panelErr('memory') || panelErr('rust') ? 'error' : statusForMem(),
      lines: [
        memStatus
          ? `${memStatus.total_entries} entries · Rust: ${memStatus.rust_available ? 'active' : 'MISSING'}`
          : (panelErr('memory') ? `Memory error ${fetchState.memory?.httpStatus ?? ''}` : (apiOk ? 'Memory: fetching…' : 'Backend unreachable')),
        memStatus
          ? (memStatus.cloud_sync_available ? `S3 sync: active (${memStatus.bucket ?? 'bucket'})` : 'S3 sync: unavailable')
          : '',
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'plan9',
      icon: '🚀',
      label: 'Plan 9',
      status: statusForPlan9(),
      lines: [
        plan9
          ? `Verdict: ${plan9.verdict ?? '—'} · ☁${plan9.mobile_cloud_live} · 🖥${plan9.mac_local_live}`
          : (panelErr('parity') ? 'Parity unavailable' : (apiOk ? 'Plan 9: fetching…' : 'Backend unreachable')),
        runtimeProof
          ? `Runtime proof: ${runtimeProof.verified_count}/${runtimeProof.total_items} verified · ${runtimeProof.pending_count} pending`
          : (plan9 ? (plan9.gaps > 0 ? `${plan9.gaps} gaps remaining` : 'Capability matrix: no gaps') : ''),
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'logs',
      icon: '📜',
      label: 'Logs / Audit',
      status: logs.length > 0 ? 'ok' : 'warn',
      lines: [
        logs.length > 0 ? logs[0].text.slice(0, 50) : 'No audit events in HUD (audit stream not wired)',
        pendingApprovals > 0 ? `${pendingApprovals} approval(s) pending` : 'Approvals tracked via /v1/approvals/pending',
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'routing',
      icon: '🔀',
      label: 'Model Routing',
      status: panelErr('routing') ? 'error' : (routingStatus ? (routingStatus.blocked_providers.length > 0 ? 'warn' : 'ok') : 'unknown'),
      badge: routingStatus ? `${routingStatus.provider_count}p/${routingStatus.non_fallback_model_count}m` : undefined,
      lines: [
        routingStatus
          ? `${routingStatus.provider_count} providers · ${routingStatus.non_fallback_model_count} cloud models · ${routingStatus.role_declaration_count} roles`
          : (panelErr('routing') ? `Routing error ${fetchState.routing?.httpStatus ?? ''}` : (apiOk ? 'Routing: fetching…' : 'Backend unreachable')),
        routingStatus
          ? `PA: ${routingStatus.pa_front_door_model} · GLM: ${routingStatus.glm_5_2_available ? 'avail' : 'pending'} · Kimi: ${routingStatus.kimi_k2_6_available ? 'avail' : 'pending'}`
          : '',
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'org-chain',
      icon: '🏗',
      label: 'Org Chain',
      status: orgChainFetch.status === 'ok' ? 'ok' : orgChainFetch.status === 'error' ? 'error' : 'unknown',
      lines: [
        orgChainFetch.status === 'ok' && orgHierarchy
          ? `PA → COS/GM → ${orgHierarchy.nodes.filter(n => n.layer === 'manager').length}M / ${orgHierarchy.nodes.filter(n => n.layer === 'worker').length}W → Reviewer`
          : orgChainFetch.status === 'error'
            ? `Hierarchy unavailable (${orgChainFetch.httpStatus ?? 'err'})`
            : orgChainFetch.status === 'loading'
              ? 'Loading org hierarchy…'
              : 'Bryan → PA → COS/GM → chain',
        orgChainFetch.status === 'ok' && orgHierarchy
          ? `Reviewer: independent · self-verify blocked`
          : 'Approval: PA-gated only',
      ],
      onExpand: setExpandedPanel,
    },
    {
      id: 'settings',
      icon: '⚙️',
      label: 'Settings',
      status: 'ok',
      lines: ['Configure server, model, theme', 'Developer tools'],
      onExpand: setExpandedPanel,
    },
  ];

  // ─────────────────────────────────────────────────────────────────────────
  // Expanded overlay content
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
                <Row label="Mobile/Cloud live" value={plan9.mobile_cloud_live} status="ok" />
                <Row label="Mac/Local live" value={plan9.mac_local_live} status="ok" />
                <Row label="Capability gaps" value={plan9.gaps} status={plan9.gaps > 0 ? 'warn' : 'ok'} />
                <Row label="Parked" value={plan9.parked} />
                <Row label="Last checked" value={plan9LastRefresh || '—'} />
              </>
            ) : (
              <BackendError endpoint="/v1/parity/status" target={apiTarget} />
            )}
            <SectionHeading>Pending Approvals</SectionHeading>
            {pendingApprovals === 0
              ? <Row label="Approvals" value="None pending" status="ok" />
              : approvalItems.map(a => <Row key={a.id} label={a.id} value={a.description ?? a.status ?? '—'} status="warn" />)
            }
          </Overlay>
        );

      case 'cockpit':
        return (
          <Overlay title="Cockpit — Runtime" icon="⚡" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Runtime Engine</SectionHeading>
            <Row label="Active model" value={model || '—'} />
            <Row label="Server version" value={version ? `v${version}` : '—'} />
            <Row label="API target" value={apiTarget || '—'} />
            <Row label="Health" value={apiOk ? 'OK' : 'Unreachable'} status={apiOk ? 'ok' : 'error'} />
            <SectionHeading>Mac Worker Queue</SectionHeading>
            {macWorkerStatus ? (
              <>
                <Row label="Queued tasks" value={macWorkerStatus.queued} />
                <Row label="Running" value={macWorkerStatus.running} />
                <Row label="Failed" value={macWorkerStatus.failed} status={macWorkerStatus.failed > 0 ? 'warn' : 'ok'} />
              </>
            ) : (
              <BackendError endpoint="/v1/mac-worker/status" target={apiTarget} />
            )}
          </Overlay>
        );

      case 'authority':
        return (
          <Overlay title="Authority / Emergency Stop" icon="🛑" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Pending Approvals (/v1/authority/approvals/pending)</SectionHeading>
            {pendingApprovals === 0
              ? <Row label="Queue" value="Empty — no pending approvals" status="ok" />
              : approvalItems.map(a => (
                <Row key={a.id} label={a.id.slice(0, 20)} value={a.description ?? '—'} status="warn" />
              ))
            }
            <SectionHeading>Recent Audit ({auditCount})</SectionHeading>
            {auditEntries.length === 0
              ? <Row label="Audit" value="No events yet — GET /v1/authority/audit" status="warn" />
              : auditEntries.map((e, i) => (
                <Row key={i} label={e.action_type ?? 'event'} value={e.execution_status ?? '—'} status={e.execution_status === 'failed' ? 'error' : 'ok'} />
              ))
            }
            <SectionHeading>Emergency Stop</SectionHeading>
            <Row label="Status" value="Active — triggers UNSAFE verdict on violation" status="ok" />
            <Row label="Gate" value="Hard gates require explicit Bryan approval" />
            <div style={{ marginTop: 12, padding: 8, background: 'rgba(239,68,68,0.06)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.15)' }}>
              <div style={{ fontSize: 10, color: '#ef4444', fontWeight: 600, marginBottom: 4 }}>Hard-gated operations</div>
              {['Production deploy', 'Destructive git ops', 'IAM / billing changes', 'Outbound sends'].map(g => (
                <div key={g} style={{ fontSize: 10, color: 'rgba(239,100,100,0.7)', padding: '1px 0' }}>• {g}</div>
              ))}
            </div>
          </Overlay>
        );

      case 'workbench':
        return (
          <Overlay title="Workbench" icon="🔧" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Coding Workflow</SectionHeading>
            {workflowStatus
              ? <Row label={workflowStatus.workflow_id ?? 'last'} value={workflowStatus.status ?? '—'} status={workflowStatus.status === 'COMPLETE' ? 'ok' : 'warn'} />
              : <Row label="Workflow" value="No workflow run yet — POST /v1/coding/workflow/run" status="warn" />
            }
            <SectionHeading>Available Operations</SectionHeading>
            {[
              ['Coding / workflow', '/v1/coding/workflow/run', 'WIRED'],
              ['Coding / read file', '/v1/coding/files/read', 'WIRED'],
              ['Coding / diff stage', '/v1/coding/diff/stage', 'WIRED'],
              ['Testing / run', '/v1/testing/run', 'WIRED'],
              ['Testing / lint', '/v1/testing/lint', 'WIRED'],
              ['Git / commit', '/v1/git/commit', 'WIRED'],
              ['Git / push', '/v1/git/push', 'WIRED'],
              ['Git / create branch', '/v1/coding/create-branch', 'WIRED'],
              ['Deploy / plan', '/v1/deploy/plan', 'DRY_RUN_ONLY'],
              ['Files / index', '/v1/files/index', 'WIRED'],
            ].map(([name, route, s]) => (
              <Row key={route} label={String(name)} value={<code style={{ fontSize: 9 }}>{route}</code>} status={s === 'WIRED' ? 'ok' : 'warn'} />
            ))}
            <SectionHeading>Mac Worker Queue</SectionHeading>
            {macWorkerStatus
              ? <Row label="Queue depth" value={`${macWorkerStatus.queued} tasks`} status={macWorkerStatus.failed > 0 ? 'warn' : 'ok'} />
              : <BackendError endpoint="/v1/mac-worker/status" target={apiTarget} />
            }
          </Overlay>
        );

      case 'connectors':
        return (
          <Overlay title="Connectors" icon="🔌" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Connector Status</SectionHeading>
            {connectors.length === 0
              ? <BackendError endpoint="/v1/connectors" target={apiTarget} lastOk={''} />
              : connectors.map(c => (
                <Row key={c.name} label={c.name} value={c.endpoint ?? (c.connected ? 'connected' : 'disconnected')} status={c.connected ? 'ok' : 'error'} />
              ))
            }
          </Overlay>
        );

      case 'agents':
        return (
          <Overlay title="Agent Roster" icon="🤖" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Plan 9 Manager Domains ({agents.length})</SectionHeading>
            {agents.length === 0
              ? <BackendError endpoint="/v1/capabilities/status" target={apiTarget} lastOk={plan9LastRefresh} />
              : agents.map(a => (
                <Row key={a.id} label={a.name} value={a.domain} status="ok" />
              ))
            }
            <SectionHeading>Capability Summary</SectionHeading>
            {plan9 ? (
              <>
                <Row label="Cloud/Mobile live" value={plan9.mobile_cloud_live} status="ok" />
                <Row label="Mac/Local live" value={plan9.mac_local_live} status="ok" />
                <Row label="Remaining gaps" value={plan9.gaps} status={plan9.gaps > 0 ? 'warn' : 'ok'} />
              </>
            ) : (
              <BackendError endpoint="/v1/parity/status" target={apiTarget} />
            )}
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
                <Row label="Rust extension" value={memStatus.rust_available ? 'Installed' : 'Not installed (pure-Python path active)'} status={memStatus.rust_available ? 'ok' : 'warn'} />
                <Row label="Last refreshed" value={memLastRefresh || '—'} />
              </>
            ) : (
              <BackendError endpoint="/v1/memory/status" target={apiTarget} lastOk={memLastRefresh} />
            )}
            <SectionHeading>Cross-Device Sync (Plan 9)</SectionHeading>
            <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.7)', marginBottom: 8, lineHeight: 1.6 }}>
              MacBook writes → push to S3. ECS/iPhone → pull from S3.<br />
              Pull to sync cloud ECS with latest MacBook memory.
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(['push', 'pull', 'both'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => handleMemorySync(mode)}
                  disabled={syncBusy || !apiOk}
                  style={{
                    fontSize: 10, padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                    background: syncBusy ? 'rgba(34,211,238,0.05)' : 'rgba(34,211,238,0.12)',
                    color: '#22d3ee', border: '1px solid rgba(34,211,238,0.2)',
                    opacity: syncBusy || !apiOk ? 0.4 : 1,
                  }}
                >
                  {syncBusy ? '…' : mode}
                </button>
              ))}
            </div>
            {syncResult && (
              <div style={{ marginTop: 8, fontSize: 10, color: '#3ddc97', padding: '4px 8px', background: 'rgba(61,220,151,0.08)', borderRadius: 4 }}>
                ✓ {syncResult}
              </div>
            )}
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
            ) : (
              <BackendError endpoint="/v1/parity/status" target={apiTarget} />
            )}
            <SectionHeading>Memory Parity</SectionHeading>
            {memStatus ? (
              <>
                <Row label="Backend" value="SQLite (pure-Python, no Rust needed for routes)" status="ok" />
                <Row label="S3 sync" value={memStatus.cloud_sync_available ? 'Active' : 'Unavailable'} status={memStatus.cloud_sync_available ? 'ok' : 'warn'} />
                <Row label="Entries" value={memStatus.total_entries} />
              </>
            ) : <BackendError endpoint="/v1/memory/status" target={apiTarget} />}
            <SectionHeading>Plan 9 Routes</SectionHeading>
            {['/v1/capabilities/status', '/v1/parity/status', '/v1/files/index',
              '/v1/plan9/runtime-proof-checklist', '/v1/coding/search'].map(r => (
              <Row key={r} label={r} value="WIRED" status="ok" />
            ))}
          </Overlay>
        );

      case 'logs':
        return (
          <Overlay title="Logs / Audit" icon="📜" onClose={() => setExpandedPanel(null)}>
            <SectionHeading>Recent Events</SectionHeading>
            {logs.length === 0 ? (
              <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.5)' }}>No events captured this session.</div>
            ) : logs.map((l, i) => (
              <Row key={i} label={l.time} value={l.text} status={l.level === 'error' ? 'error' : 'ok'} />
            ))}
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
                <Row label="Cloud models available" value={routingStatus.non_fallback_model_count} status="ok" />
                <Row label="Total catalog (incl. fallback)" value={routingStatus.model_count} />
                <Row label="Role declarations" value={routingStatus.role_declaration_count} status="ok" />
                <Row label="Active routing policy" value={routingStatus.active_routing_policy} status="ok" />
              </>
            ) : (
              <BackendError endpoint="/v1/model-routing/status" target={apiTarget} />
            )}
            <SectionHeading>PA Front-Door Route</SectionHeading>
            {routingStatus ? (
              <>
                <Row label="PA model" value={routingStatus.pa_front_door_model} status="ok" />
                <Row label="PA policy" value="GPT/OpenAI stable route — not Ollama/Kimi" status="ok" />
              </>
            ) : null}
            <SectionHeading>Heavy Coding Route (temporary policy)</SectionHeading>
            {routingStatus ? (
              <>
                <Row
                  label="GLM-5.2 available"
                  value={routingStatus.glm_5_2_available ? 'Yes' : 'Not in catalog / key missing'}
                  status={routingStatus.glm_5_2_available ? 'ok' : 'warn'}
                />
                <Row
                  label="Kimi K2.6 available"
                  value={routingStatus.kimi_k2_6_available ? 'Yes' : 'Not in catalog / key missing'}
                  status={routingStatus.kimi_k2_6_available ? 'ok' : 'warn'}
                />
                <Row
                  label="Heavy-coding preference"
                  value={routingStatus.heavy_coding_route_preference || 'GLM-5.2 → Kimi K2.6 → catalog'}
                  status="ok"
                />
                <Row
                  label="Unknown/unbenchmarked"
                  value={routingStatus.unknown_needs_metadata ?? 0}
                />
              </>
            ) : null}
            <SectionHeading>Kimi / GLM Benchmark Status</SectionHeading>
            {routingStatus ? (
              <>
                <Row
                  label="Kimi benchmark"
                  value={routingStatus.kimi_benchmarked ? 'Accepted' : 'KIMI_NOT_BENCHMARKED'}
                  status={routingStatus.kimi_benchmarked ? 'ok' : 'warn'}
                />
                <Row
                  label="GLM benchmark"
                  value={routingStatus.glm_benchmarked ? 'Accepted' : 'GLM_NOT_FULLY_BENCHMARK_ACCEPTED'}
                  status={routingStatus.glm_benchmarked ? 'ok' : 'warn'}
                />
                {Object.entries(routingStatus.benchmark_status).map(([k, v]) => (
                  <Row key={k} label={`Benchmark: ${k}`} value={String(v)} status={v === 'ACCEPTED' ? 'ok' : 'warn'} />
                ))}
                {routingStatus.policy_labels && Object.entries(routingStatus.policy_labels).map(([k, v]) => (
                  <Row key={k} label={`Policy: ${k}`} value={String(v)} />
                ))}
              </>
            ) : null}
            <SectionHeading>Provider Health</SectionHeading>
            {routingStatus ? (
              Object.entries(routingStatus.provider_health).map(([provider, health]) => (
                <Row
                  key={provider}
                  label={provider}
                  value={String(health)}
                  status={health === 'configured' || health === 'local' || health === 'no_key_required' ? 'ok' : 'warn'}
                />
              ))
            ) : null}
            {routingStatus && routingStatus.blocked_providers.length > 0 && (
              <>
                <SectionHeading>Blocked / Unconfigured Providers</SectionHeading>
                {routingStatus.blocked_providers.map(p => (
                  <Row key={p} label={p} value="not configured (API key missing)" status="warn" />
                ))}
              </>
            )}
            <SectionHeading>Routing Policy Notes</SectionHeading>
            <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.7)', lineHeight: 1.6 }}>
              <div>• Heavy coding: GLM-5.2 preferred → Kimi K2.6 → best coding catalog model (dynamic)</div>
              <div>• Sonnet: high-risk / final-review / validation-failure escalation only</div>
              <div>• Cheap routes are capability-specific (not one universal model)</div>
              <div>• Research roles prefer Perplexity/Sonar (web-grounded)</div>
              <div>• Security/billing/IAM/deploy: Anthropic Claude only</div>
              <div>• Ollama/local: offline fallback only</div>
              <div>• No manual model picker in normal UI</div>
            </div>
          </Overlay>
        );

      case 'org-chain':
        return (
          <Overlay title="Jarvis PA — Org Chain & Loop Architecture" icon="🏗" onClose={() => setExpandedPanel(null)}>
            <OrgChainPanel
              data={orgHierarchy}
              fetchState={orgChainFetch}
              apiTarget={apiTarget}
            />
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
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div
      style={{ position: 'relative', display: 'flex', flexDirection: 'column', width: '100%', height: '100%', overflow: 'hidden', background: '#02040a' }}
    >
      <CosmicBackdrop phase={phase} voiceEnabled={false} />

      {/* Expanded panel overlay */}
      {expandedPanel && renderExpanded(expandedPanel)}

      {/* ── Top system strip ── */}
      <div style={{
        position: 'relative', zIndex: 10, flexShrink: 0,
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '4px 12px',
        borderBottom: '1px solid rgba(34,211,238,0.07)',
        background: 'rgba(2,4,10,0.6)',
        backdropFilter: 'blur(8px)',
        fontSize: 10,
        color: 'rgba(140,180,210,0.6)',
        overflow: 'hidden',
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {dot(apiOk ? 'ok' : apiOk === false ? 'error' : 'unknown')}
          <span style={{ color: apiOk ? '#3ddc97' : '#ef4444' }}>
            {apiOk ? 'Jarvis live' : (apiOk === false ? 'Backend unreachable' : 'Connecting…')}
          </span>
        </span>
        <span>·</span>
        <span>{model || '—'}</span>
        {version && <><span>·</span><span>v{version}</span></>}
        <span>·</span>
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: 'rgba(100,140,180,0.5)' }}>{apiTarget || 'localhost:8000'}</span>
        {plan9 && (
          <>
            <span>·</span>
            <span style={{ color: plan9.gaps === 0 ? '#3ddc97' : '#f59e0b' }}>
              Plan 9: {plan9.gaps === 0 ? 'All live' : `${plan9.gaps} gaps`}
            </span>
          </>
        )}
        <span style={{ marginLeft: 'auto', color: 'rgba(80,120,160,0.4)', fontSize: 9 }}>
          ⌘K palette · Voice: parked
        </span>
      </div>

      {/* ── Orb zone ── */}
      <div style={{ position: 'relative', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: 16, paddingBottom: 8 }}>
        <LivingOrb phase={phase} voiceEnabled={false} size={150} />
      </div>

      {/* ── Chat composer ── */}
      <div style={{ position: 'relative', zIndex: 10, flexShrink: 0, padding: '0 12px 8px' }}>
        <div style={{
          display: 'flex', alignItems: 'flex-end', gap: 8,
          borderRadius: 14, padding: '8px 12px',
          background: 'rgba(10, 16, 32, 0.82)',
          border: '1px solid rgba(34, 211, 238, 0.13)',
          backdropFilter: 'blur(8px)',
        }}>
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Jarvis anything… (Enter to send, Shift+Enter for newline)"
            disabled={sending}
            style={{
              flex: 1, resize: 'none', background: 'transparent', outline: 'none',
              fontSize: 13, lineHeight: '1.5', color: 'rgba(200,220,255,0.90)',
              maxHeight: 100, border: 'none',
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={sending || !input.trim()}
            style={{
              fontSize: 13, padding: '4px 12px', borderRadius: 8, flexShrink: 0,
              background: sending ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.2)',
              color: 'rgba(34,211,238,0.9)', border: '1px solid rgba(34,211,238,0.2)',
              opacity: sending || !input.trim() ? 0.4 : 1, cursor: 'pointer',
            }}
          >
            {sending ? '…' : '↑'}
          </button>
        </div>
        {lastReply && (
          <div style={{
            marginTop: 6, fontSize: 11, lineHeight: 1.55, borderRadius: 10, padding: '8px 12px',
            background: 'rgba(10, 18, 32, 0.75)',
            color: 'rgba(160, 210, 180, 0.88)',
            border: '1px solid rgba(61, 220, 151, 0.10)',
            maxHeight: 120, overflowY: 'auto',
          }}>
            {lastReply}
          </div>
        )}
      </div>

      {/* ── HUD panel grid ── */}
      <div style={{ position: 'relative', zIndex: 10, flex: 1, overflowY: 'auto', padding: '4px 10px 12px' }}>
        <div style={{ display: 'grid', gap: 7, gridTemplateColumns: 'repeat(auto-fill, minmax(148px, 1fr))' }}>
          {panelCards.map(card => (
            <HUDCard key={card.id} {...card} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default JarvisCockpitPage;
