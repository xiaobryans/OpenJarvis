/**
 * Plan 4-6 — Expert Roles Page
 *
 * Route: /expert-roles
 * Lists all built-in expert roles, shows metadata/capabilities/triggers,
 * and lets the user dry-run role selection for a typed request.
 *
 * Important: Expert roles are internal routing aids only.
 * Single Jarvis PA voice is preserved externally — roles never speak directly.
 *
 * All data from real /v1/expert-roles/* routes.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Zap,
  CheckCircle,
  Shield,
  Brain,
  Search,
  Info,
  Router,
} from 'lucide-react';
import type { ExpertRole, RolesStats, SelectRolesResponse } from '../lib/jarvis-api';
import { fetchExpertRoles, selectRoles } from '../lib/jarvis-api';
import { apiFetch } from '../lib/api';

// ---------------------------------------------------------------------------
// Style tokens
// ---------------------------------------------------------------------------
const C = {
  text: 'var(--color-text)',
  textSec: 'var(--color-text-secondary)',
  textTert: 'var(--color-text-tertiary)',
  border: 'var(--color-border)',
  surface: 'var(--color-bg-secondary)',
  surfaceAlt: 'var(--color-bg-tertiary)',
  accent: 'var(--color-accent)',
  success: 'var(--color-success, #a6e3a1)',
  warning: 'var(--color-warning, #f9e2af)',
  error: 'var(--color-error, #f38ba8)',
};

// ---------------------------------------------------------------------------
// Routing status type
// ---------------------------------------------------------------------------

interface RoutingStatus {
  jarvis_pa_identity: string;
  internal_routing_only: boolean;
  no_multi_personality_output: boolean;
  selector_available: boolean;
  role_count: number;
  active_count: number;
  note?: string;
}

// ---------------------------------------------------------------------------
// Routing status panel
// ---------------------------------------------------------------------------

function RoutingStatusPanel({ status }: { status: RoutingStatus | null }) {
  if (status === null) {
    return (
      <div
        className="rounded-lg px-4 py-3 flex items-center gap-2 text-xs"
        style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.textTert }}
      >
        <Info size={12} />
        Routing status unavailable — check backend connectivity to{' '}
        <code style={{ fontFamily: 'monospace' }}>/v1/expert-roles/routing-status</code>.
      </div>
    );
  }

  const boolRow = (label: string, value: boolean) => (
    <div className="flex items-center gap-2">
      <span style={{ color: C.textTert }}>{label}:</span>
      <span
        className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded"
        style={{ background: value ? 'rgba(166,227,161,0.10)' : 'rgba(243,139,168,0.10)', color: value ? C.success : C.error }}
      >
        <CheckCircle size={9} />
        {value ? 'Yes' : 'No'}
      </span>
    </div>
  );

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: `1px solid ${C.border}` }}>
        <Router size={14} style={{ color: C.accent }} />
        <span className="text-sm font-medium" style={{ color: C.text }}>Routing &amp; Identity Status</span>
      </div>
      <div className="px-4 py-3 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-xs">
        <div className="flex items-center gap-2">
          <span style={{ color: C.textTert }}>Jarvis PA Identity:</span>
          <span
            className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded"
            style={{ background: 'rgba(166,227,161,0.10)', color: C.success }}
          >
            <CheckCircle size={9} />
            {status.jarvis_pa_identity || 'Single voice'}
          </span>
        </div>
        {boolRow('Internal routing only', status.internal_routing_only)}
        {boolRow('No multi-personality output', status.no_multi_personality_output)}
        {boolRow('Selector available', status.selector_available)}
        <div className="flex items-center gap-2">
          <span style={{ color: C.textTert }}>Roles:</span>
          <span style={{ color: C.text, fontFamily: 'monospace' }}>
            {status.active_count} active / {status.role_count} total
          </span>
        </div>
      </div>
      {status.note && (
        <div className="px-4 pb-3 text-xs italic" style={{ color: C.textTert }}>
          {status.note}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Domain icon mapping
// ---------------------------------------------------------------------------
const DOMAIN_ICONS: Record<string, React.ReactNode> = {
  coding: <Brain size={14} />,
  research: <Search size={14} />,
  medical: <Shield size={14} />,
  legal: <Shield size={14} />,
  financial: <Shield size={14} />,
  security: <Shield size={14} />,
  data: <Brain size={14} />,
  devops: <Brain size={14} />,
  product: <Brain size={14} />,
  creative: <Brain size={14} />,
};

function domainIcon(domain: string) {
  return DOMAIN_ICONS[domain] ?? <Brain size={14} />;
}

// ---------------------------------------------------------------------------
// Stats strip
// ---------------------------------------------------------------------------

function StatsStrip({ stats }: { stats: RolesStats }) {
  const cells = [
    { label: 'Total', value: stats.total, color: C.text },
    { label: 'Active', value: stats.active, color: C.success },
    { label: 'Inactive', value: stats.inactive, color: C.textSec },
  ];
  return (
    <div className="grid grid-cols-3 gap-3 mb-6">
      {cells.map((c) => (
        <div
          key={c.label}
          className="rounded-lg px-4 py-3 text-center"
          style={{ background: C.surface, border: `1px solid ${C.border}` }}
        >
          <div className="text-2xl font-bold tabular-nums" style={{ color: c.color }}>
            {c.value}
          </div>
          <div className="text-xs mt-1" style={{ color: C.textTert }}>
            {c.label}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Role card
// ---------------------------------------------------------------------------

function RoleCard({ role, highlighted }: { role: ExpertRole; highlighted: boolean }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-lg mb-2 overflow-hidden transition-all"
      style={{
        background: highlighted ? 'color-mix(in srgb, var(--color-accent) 6%, var(--color-bg-secondary))' : C.surface,
        border: highlighted ? `1px solid color-mix(in srgb, var(--color-accent) 30%, var(--color-border))` : `1px solid ${C.border}`,
      }}
    >
      <button
        className="flex items-center gap-3 w-full px-4 py-3 text-left"
        onClick={() => setExpanded(!expanded)}
        style={{ color: C.text }}
      >
        <span style={{ color: highlighted ? C.accent : C.textTert }}>
          {domainIcon(role.domain)}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{role.name}</span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-mono"
              style={{
                background: role.status === 'active' ? 'rgba(166,227,161,0.12)' : 'rgba(166,173,200,0.1)',
                color: role.status === 'active' ? C.success : C.textSec,
              }}
            >
              {role.status}
            </span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-mono"
              style={{ background: C.surfaceAlt, color: C.textTert }}
            >
              {role.domain}
            </span>
            {role.safety_level !== 'safe' && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded font-mono flex items-center gap-0.5"
                style={{ background: 'rgba(249,226,175,0.1)', color: C.warning }}
              >
                <AlertTriangle size={10} />{role.safety_level}
              </span>
            )}
            {highlighted && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded font-mono flex items-center gap-0.5"
                style={{ background: 'color-mix(in srgb, var(--color-accent) 12%, transparent)', color: C.accent }}
              >
                <CheckCircle size={10} />selected
              </span>
            )}
          </div>
          <div className="text-xs mt-0.5 truncate" style={{ color: C.textSec }}>
            {role.description}
          </div>
        </div>
        {expanded ? <ChevronUp size={14} style={{ color: C.textTert }} /> : <ChevronDown size={14} style={{ color: C.textTert }} />}
      </button>

      {expanded && (
        <div
          className="px-4 pb-4 text-xs"
          style={{ borderTop: `1px solid ${C.border}`, color: C.textSec }}
        >
          <div className="mt-3 mb-2" style={{ color: C.textTert }}>Trigger conditions</div>
          <div className="flex flex-wrap gap-1.5">
            {role.trigger_conditions.map((t) => (
              <span
                key={t}
                className="px-2 py-0.5 rounded-full"
                style={{ background: C.surfaceAlt, color: C.textSec, border: `1px solid ${C.border}` }}
              >
                {t}
              </span>
            ))}
          </div>
          {role.disclaimer && (
            <div
              className="mt-3 px-3 py-2 rounded flex items-start gap-2"
              style={{ background: 'rgba(249,226,175,0.06)', border: `1px solid rgba(249,226,175,0.15)` }}
            >
              <Info size={11} className="mt-0.5 shrink-0" style={{ color: C.warning }} />
              <span style={{ color: C.warning }}>{role.disclaimer}</span>
            </div>
          )}
          <div className="mt-2" style={{ color: C.textTert }}>
            role_id: <span style={{ color: C.textSec, fontFamily: 'monospace' }}>{role.role_id}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dry-run selector panel
// ---------------------------------------------------------------------------

function DryRunPanel({ roles }: { roles: ExpertRole[] }) {
  const [text, setText] = useState('');
  const [result, setResult] = useState<SelectRolesResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const handleSelect = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setErr('');
    try {
      const res = await selectRoles({ text, max_roles: 3 });
      setResult(res);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Selection failed');
    } finally {
      setBusy(false);
    }
  };

  const selectedIds = new Set(result?.selected_roles.map((r) => r.role_id) ?? []);
  const hasResult = result !== null;

  return (
    <div
      className="rounded-lg overflow-hidden mb-6"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: `1px solid ${C.border}` }}>
        <Zap size={14} style={{ color: C.accent }} />
        <span className="text-sm font-medium" style={{ color: C.text }}>Dry-run role selection</span>
        <span className="text-xs ml-auto" style={{ color: C.textTert }}>
          Internal routing only — single Jarvis PA voice preserved externally
        </span>
      </div>
      <div className="px-4 py-3">
        <div className="flex gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSelect(); }}
            placeholder="Type a request to see which expert roles would be selected…"
            className="flex-1 px-3 py-2 rounded text-sm outline-none"
            style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
          />
          <button
            onClick={handleSelect}
            disabled={busy || !text.trim()}
            className="px-4 py-2 rounded text-sm cursor-pointer disabled:opacity-50"
            style={{ background: C.accent, color: '#1e1e2e' }}
          >
            {busy ? 'Selecting…' : 'Select'}
          </button>
        </div>

        {err && <div className="mt-2 text-xs" style={{ color: C.error }}>{err}</div>}

        {hasResult && (
          <div className="mt-3">
            <div className="text-xs mb-2" style={{ color: C.textTert }}>
              {result!.count === 0
                ? 'No roles matched — Jarvis PA handles this without expert routing'
                : `${result!.count} role${result!.count !== 1 ? 's' : ''} selected (internal routing aid only)`}
            </div>
            {result!.count > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {result!.selected_roles.map((r) => (
                  <div
                    key={r.role_id}
                    className="flex items-center gap-1.5 px-2 py-1 rounded text-xs"
                    style={{ background: 'color-mix(in srgb, var(--color-accent) 8%, var(--color-bg-tertiary))', color: C.accent, border: `1px solid color-mix(in srgb, var(--color-accent) 20%, var(--color-border))` }}
                  >
                    <CheckCircle size={11} />
                    {r.name}
                  </div>
                ))}
              </div>
            )}
            {result!.disclaimers.length > 0 && (
              <div className="text-xs" style={{ color: C.warning }}>
                {result!.disclaimers.map((d, i) => <div key={i}>⚠ {d}</div>)}
              </div>
            )}
            <div className="text-xs mt-2 italic" style={{ color: C.textTert }}>{result!.note}</div>
          </div>
        )}
      </div>

      {/* Show all roles with highlights when a selection was run */}
      {hasResult && roles.length > 0 && (
        <div className="px-4 pb-4" style={{ borderTop: `1px solid ${C.border}` }}>
          <div className="text-xs mt-3 mb-2" style={{ color: C.textTert }}>All roles — highlighted = selected</div>
          {roles.map((r) => (
            <RoleCard key={r.role_id} role={r} highlighted={selectedIds.has(r.role_id)} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function ExpertRolesPage() {
  const [roles, setRoles] = useState<ExpertRole[]>([]);
  const [stats, setStats] = useState<RolesStats | null>(null);
  const [routingStatus, setRoutingStatus] = useState<RoutingStatus | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [rolesRes, routingRes] = await Promise.allSettled([
        fetchExpertRoles(),
        apiFetch('/v1/expert-roles/routing-status').then((r) => {
          if (!r.ok) throw new Error(`routing-status ${r.status}`);
          return r.json() as Promise<RoutingStatus>;
        }),
      ]);

      if (rolesRes.status === 'fulfilled') {
        setRoles(rolesRes.value.roles);
        setStats(rolesRes.value.stats);
      } else {
        throw rolesRes.reason instanceof Error
          ? rolesRes.reason
          : new Error('Failed to load expert roles');
      }

      if (routingRes.status === 'fulfilled') {
        setRoutingStatus(routingRes.value);
      } else {
        // Graceful degradation — routing status panel shows a notice instead of crashing
        setRoutingStatus(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load expert roles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold" style={{ color: C.text }}>
              Expert Roles
            </h1>
            <button
              onClick={load}
              className="p-2 rounded-lg transition-colors cursor-pointer"
              style={{ color: C.textSec }}
              title="Refresh"
              onMouseEnter={(e) => (e.currentTarget.style.background = C.surface)}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
          <p className="text-sm mt-1" style={{ color: C.textSec }}>
            Internal routing registry — single Jarvis PA voice always preserved externally.
            Roles inform response depth and framing; they never speak as separate personas.
            All data from{' '}
            <code style={{ fontFamily: 'monospace', fontSize: 11, color: C.textTert }}>/v1/expert-roles/*</code>.
          </p>
        </header>

        {stats && <StatsStrip stats={stats} />}

        {/* Dry-run only shown when roles are loaded */}
        {!loading && !error && <DryRunPanel roles={roles} />}

        {error && (
          <div
            className="rounded-lg px-4 py-3 mb-4 flex items-center gap-2 text-sm"
            style={{ background: 'rgba(243,139,168,0.1)', color: C.error, border: `1px solid rgba(243,139,168,0.2)` }}
          >
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {loading && (
          <div className="text-sm text-center py-12" style={{ color: C.textTert }}>
            Loading expert roles…
          </div>
        )}

        {/* Full role list (shown below dry-run only when dry-run is not active) */}
        {!loading && !error && (
          <div>
            <div className="text-xs mb-3" style={{ color: C.textTert }}>All registered roles</div>
            {roles.length === 0 ? (
              <div
                className="rounded-lg px-4 py-10 text-center"
                style={{ background: C.surface, border: `1px solid ${C.border}` }}
              >
                <Brain size={28} className="mx-auto mb-3 opacity-30" style={{ color: C.textTert }} />
                <div className="text-sm" style={{ color: C.textTert }}>No expert roles registered</div>
                <div className="text-xs mt-1" style={{ color: C.textTert }}>
                  Roles load from{' '}
                  <code style={{ fontFamily: 'monospace' }}>/v1/expert-roles</code>{' '}
                  — check backend connectivity.
                </div>
              </div>
            ) : (
              roles.map((r) => (
                <RoleCard key={r.role_id} role={r} highlighted={false} />
              ))
            )}
          </div>
        )}

        {/* Routing status panel — shown when not in initial loading state */}
        {!loading && routingStatus !== undefined && (
          <div className="mt-6">
            <div className="text-xs mb-3" style={{ color: C.textTert }}>Routing configuration</div>
            <RoutingStatusPanel status={routingStatus} />
          </div>
        )}
      </div>
    </div>
  );
}
