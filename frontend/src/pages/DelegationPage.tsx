/**
 * Plan 4-6 B7 — Life-Business OS Delegation Queue
 *
 * Route: /delegation
 * Shows all pending-approval items from all delegation sources:
 *   - Life-OS personal tasks awaiting approval
 *   - Proactive agent action approvals
 *   - Mission tasks awaiting approval
 *
 * Approve/reject actions route through the existing source-specific
 * endpoints. This page never bypasses approval gates.
 * All data from real /v1/delegation/* routes.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Shield,
  Clock,
  Zap,
  User,
  Target,
  ListTodo,
  Info,
} from 'lucide-react';
import type { DelegationItem, DelegationQueueResponse } from '../lib/jarvis-api';
import {
  fetchDelegationQueue,
  approveItem,
  rejectItem,
} from '../lib/jarvis-api';

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
// Source icons
// ---------------------------------------------------------------------------

function SourceIcon({ source }: { source: string }) {
  if (source === 'life_os') return <ListTodo size={14} />;
  if (source === 'agent_action') return <Zap size={14} />;
  if (source === 'mission') return <Target size={14} />;
  return <User size={14} />;
}

// ---------------------------------------------------------------------------
// Category badge
// ---------------------------------------------------------------------------

function CategoryBadge({ category }: { category: string }) {
  const cfg: Record<string, { bg: string; color: string }> = {
    personal_task: { bg: 'rgba(137,180,250,0.12)', color: 'var(--color-accent, #89b4fa)' },
    agent_action: { bg: 'rgba(249,226,175,0.12)', color: 'var(--color-warning, #f9e2af)' },
    mission_task: { bg: 'rgba(166,227,161,0.12)', color: 'var(--color-success, #a6e3a1)' },
  };
  const style = cfg[category] ?? { bg: C.surfaceAlt, color: C.textSec };
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono"
      style={{ background: style.bg, color: style.color }}
    >
      {category.replace(/_/g, ' ')}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Source strip stats
// ---------------------------------------------------------------------------

function SourceStrip({ by_source }: { by_source: { life_os: number; agent_action: number; mission: number } }) {
  const cells = [
    { label: 'Life-OS tasks', value: by_source.life_os, icon: <ListTodo size={13} />, color: C.accent },
    { label: 'Agent actions', value: by_source.agent_action, icon: <Zap size={13} />, color: C.warning },
    { label: 'Mission tasks', value: by_source.mission, icon: <Target size={13} />, color: C.success },
  ];
  return (
    <div className="grid grid-cols-3 gap-3 mb-6">
      {cells.map((c) => (
        <div
          key={c.label}
          className="rounded-lg px-4 py-3 text-center"
          style={{ background: C.surface, border: `1px solid ${C.border}` }}
        >
          <div className="flex items-center justify-center gap-1.5 mb-1" style={{ color: c.color }}>
            {c.icon}
            <span className="text-xl font-bold tabular-nums">{c.value}</span>
          </div>
          <div className="text-xs" style={{ color: C.textTert }}>{c.label}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Action buttons
// ---------------------------------------------------------------------------

function ActionButtons({
  item,
  onApproved,
}: {
  item: DelegationItem;
  onApproved: () => void;
}) {
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null);
  const [result, setResult] = useState<{ ok: boolean; label: string } | null>(null);

  if (!item.approval_route) {
    return (
      <div className="text-xs italic" style={{ color: C.textTert }}>
        No approval route available for this item type.
      </div>
    );
  }

  const handleApprove = async () => {
    if (!item.approval_route) return;
    setBusy('approve');
    try {
      await approveItem(item.approval_route);
      setResult({ ok: true, label: 'Approved' });
      setTimeout(onApproved, 800);
    } catch (e: unknown) {
      setResult({ ok: false, label: e instanceof Error ? e.message : 'Approve failed' });
    } finally {
      setBusy(null);
    }
  };

  const handleReject = async () => {
    if (!item.reject_route) return;
    setBusy('reject');
    try {
      await rejectItem(item.reject_route);
      setResult({ ok: true, label: 'Rejected' });
      setTimeout(onApproved, 800);
    } catch (e: unknown) {
      setResult({ ok: false, label: e instanceof Error ? e.message : 'Reject failed' });
    } finally {
      setBusy(null);
    }
  };

  if (result) {
    return (
      <div
        className="flex items-center gap-1.5 text-xs"
        style={{ color: result.ok ? C.success : C.error }}
      >
        {result.ok ? <CheckCircle size={12} /> : <XCircle size={12} />}
        {result.label}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleApprove}
        disabled={!!busy}
        className="flex items-center gap-1 px-3 py-1.5 rounded text-xs cursor-pointer disabled:opacity-50 transition-colors"
        style={{ background: 'rgba(166,227,161,0.15)', color: C.success, border: `1px solid rgba(166,227,161,0.25)` }}
        title="Approve this item"
      >
        <CheckCircle size={12} />
        {busy === 'approve' ? 'Approving…' : 'Approve'}
      </button>
      {item.reject_route && (
        <button
          onClick={handleReject}
          disabled={!!busy}
          className="flex items-center gap-1 px-3 py-1.5 rounded text-xs cursor-pointer disabled:opacity-50 transition-colors"
          style={{ background: 'rgba(243,139,168,0.12)', color: C.error, border: `1px solid rgba(243,139,168,0.22)` }}
          title="Reject this item"
        >
          <XCircle size={12} />
          {busy === 'reject' ? 'Rejecting…' : 'Reject'}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delegation item row
// ---------------------------------------------------------------------------

function DelegationRow({
  item,
  onRefresh,
}: {
  item: DelegationItem;
  onRefresh: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const tierColor = item.authority_tier === 'tier_3'
    ? C.warning
    : item.authority_tier === 'tier_4' || item.authority_tier === 'tier_5'
    ? C.error
    : C.textSec;

  return (
    <div
      className="rounded-lg mb-2 overflow-hidden"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-start gap-3 px-4 py-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-0.5 shrink-0"
          style={{ color: C.textTert }}
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        <div
          className="mt-0.5 shrink-0"
          style={{ color: item.source === 'life_os' ? C.accent : item.source === 'agent_action' ? C.warning : C.success }}
        >
          <SourceIcon source={item.source} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm" style={{ color: C.text }}>
              {item.title}
            </span>
            <CategoryBadge category={item.category} />
            <span
              className="text-[10px] font-mono px-1.5 py-0.5 rounded"
              style={{ background: C.surfaceAlt, color: tierColor }}
            >
              {item.authority_tier}
            </span>
            {item.priority && (
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                style={{ background: C.surfaceAlt, color: C.textTert }}
              >
                p:{item.priority}
              </span>
            )}
            {item.risk_level && item.risk_level !== 'low' && (
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-0.5"
                style={{ background: 'rgba(243,139,168,0.1)', color: C.error }}
              >
                <AlertTriangle size={10} />{item.risk_level}
              </span>
            )}
          </div>

          {item.description && (
            <div className="text-xs mt-0.5 line-clamp-2" style={{ color: C.textSec }}>
              {item.description}
            </div>
          )}

          {item.expires_at && (
            <div className="text-xs mt-0.5 flex items-center gap-1" style={{ color: C.warning }}>
              <Clock size={10} /> Expires: {String(item.expires_at)}
            </div>
          )}
        </div>

        <div className="shrink-0 flex items-center">
          <ActionButtons item={item} onApproved={onRefresh} />
        </div>
      </div>

      {expanded && (
        <div
          className="px-4 pb-4 text-xs"
          style={{ borderTop: `1px solid ${C.border}`, color: C.textSec }}
        >
          <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5">
            <div><span style={{ color: C.textTert }}>audit_id: </span>
              <span style={{ fontFamily: 'monospace' }}>{item.audit_id}</span>
            </div>
            <div><span style={{ color: C.textTert }}>source: </span>{item.source}</div>
            <div><span style={{ color: C.textTert }}>status: </span>{item.status}</div>
            {item.approval_route && (
              <div><span style={{ color: C.textTert }}>approval route: </span>
                <span style={{ fontFamily: 'monospace' }}>{item.approval_route}</span>
              </div>
            )}
            {item.reject_route && (
              <div><span style={{ color: C.textTert }}>reject route: </span>
                <span style={{ fontFamily: 'monospace' }}>{item.reject_route}</span>
              </div>
            )}
            {item.tags.length > 0 && (
              <div className="col-span-2">
                <span style={{ color: C.textTert }}>tags: </span>{item.tags.join(', ')}
              </div>
            )}
          </div>

          {/* Extra metadata (non-secret) */}
          {Object.keys(item.extra).length > 0 && (
            <div className="mt-2">
              <div className="mb-1" style={{ color: C.textTert }}>metadata</div>
              {Object.entries(item.extra).map(([k, v]) => (
                v !== null && v !== undefined && (
                  <div key={k}>
                    <span style={{ color: C.textTert }}>{k}: </span>
                    <span>{String(v)}</span>
                  </div>
                )
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source error notice
// ---------------------------------------------------------------------------

function SourceErrors({ errors }: { errors: Array<{ source: string; error: string }> }) {
  if (!errors.length) return null;
  return (
    <div className="mb-4 space-y-1">
      {errors.map((e) => (
        <div
          key={e.source}
          className="flex items-center gap-2 px-3 py-2 rounded text-xs"
          style={{ background: 'rgba(249,226,175,0.08)', border: `1px solid rgba(249,226,175,0.2)`, color: C.warning }}
        >
          <Info size={12} />
          <span><strong>{e.source}</strong>: {e.error}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function DelegationPage() {
  const [data, setData] = useState<DelegationQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'life_os' | 'agent_action' | 'mission'>('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchDelegationQueue();
      setData(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load delegation queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = data?.items.filter((i) => filter === 'all' || i.source === filter) ?? [];

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold" style={{ color: C.text }}>
              Delegation Queue
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
            Pending-approval items across all Life-Business OS sources.
            Approve and reject through existing gated routes — this page never bypasses approval gates.
            All data from{' '}
            <code style={{ fontFamily: 'monospace', fontSize: 11, color: C.textTert }}>/v1/delegation/queue</code>.
          </p>
        </header>

        {/* Source stats */}
        {data && <SourceStrip by_source={data.by_source} />}

        {/* Approval gate notice */}
        <div
          className="flex items-start gap-2 px-4 py-3 rounded-lg mb-4 text-xs"
          style={{ background: 'rgba(137,180,250,0.06)', border: `1px solid rgba(137,180,250,0.15)` }}
        >
          <Shield size={13} className="mt-0.5 shrink-0" style={{ color: C.accent }} />
          <span style={{ color: C.textSec }}>
            Approval and rejection actions route through the source-specific authority endpoints.
            High-risk and Tier 3+ actions require explicit sign-off. Gates are not weakened by this UI.
          </span>
        </div>

        {/* Source errors */}
        {data && <SourceErrors errors={data.errors} />}

        {/* Global error */}
        {error && (
          <div
            className="rounded-lg px-4 py-3 mb-4 flex items-center gap-2 text-sm"
            style={{ background: 'rgba(243,139,168,0.1)', color: C.error, border: `1px solid rgba(243,139,168,0.2)` }}
          >
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {/* Filter */}
        <div className="flex items-center gap-2 mb-4">
          {(['all', 'life_os', 'agent_action', 'mission'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="px-3 py-1.5 rounded text-xs cursor-pointer transition-colors"
              style={{
                background: filter === f
                  ? 'color-mix(in srgb, var(--color-accent) 15%, var(--color-bg-tertiary))'
                  : C.surface,
                color: filter === f ? C.accent : C.textSec,
                border: filter === f
                  ? `1px solid color-mix(in srgb, var(--color-accent) 30%, var(--color-border))`
                  : `1px solid ${C.border}`,
              }}
            >
              {f.replace(/_/g, ' ')}
              {data && f !== 'all' && (
                <span className="ml-1.5 tabular-nums" style={{ color: C.textTert }}>
                  ({f === 'life_os' ? data.by_source.life_os : f === 'agent_action' ? data.by_source.agent_action : data.by_source.mission})
                </span>
              )}
              {data && f === 'all' && (
                <span className="ml-1.5 tabular-nums" style={{ color: C.textTert }}>
                  ({data.count})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Loading */}
        {loading && (
          <div className="text-sm text-center py-12" style={{ color: C.textTert }}>
            Loading delegation queue…
          </div>
        )}

        {/* Empty */}
        {!loading && !error && filtered.length === 0 && (
          <div
            className="rounded-lg px-4 py-12 text-center"
            style={{ background: C.surface, border: `1px solid ${C.border}` }}
          >
            <CheckCircle size={24} className="mx-auto mb-3" style={{ color: C.success }} />
            <div className="text-sm font-medium" style={{ color: C.text }}>
              No pending approvals
            </div>
            <div className="text-xs mt-1" style={{ color: C.textTert }}>
              {filter === 'all'
                ? 'All three sources are empty — no items require approval right now.'
                : `No pending items in the ${filter.replace(/_/g, ' ')} queue.`}
            </div>
          </div>
        )}

        {/* Items */}
        {!loading && filtered.map((item) => (
          <DelegationRow
            key={item.delegation_id}
            item={item}
            onRefresh={load}
          />
        ))}

        {/* Note */}
        {data && !loading && (
          <div className="mt-4 text-xs italic" style={{ color: C.textTert }}>
            {data.note}
          </div>
        )}
      </div>
    </div>
  );
}
