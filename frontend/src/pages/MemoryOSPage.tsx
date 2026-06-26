/**
 * Plan 4-6 — Memory OS
 *
 * Route: /memory-os
 * Shows VANTA memory namespaces, search capabilities, and context state.
 * Data from:
 *   - GET /v1/memory/dashboard
 *   - GET /v1/memory/namespaces
 *
 * Design rules:
 *   - No fake data anywhere.
 *   - Never claim cloud sync is live unless cloud_sync_live_claimed=true.
 *   - Never claim memory is cloud-synced unless proven.
 *   - Honest capability display throughout.
 *   - Loading, error, and empty states always present.
 *   - Mobile-responsive throughout.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  AlertTriangle,
  Brain,
  Database,
  Search,
  Cloud,
  CloudOff,
  CheckCircle2,
  XCircle,
  Layers,
  Info,
} from 'lucide-react';
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
  danger: 'var(--color-danger, #f38ba8)',
  info: 'var(--color-info, #89dceb)',
} as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MemoryNamespace {
  name: string;
  count: number;
}

interface MemoryDashboard {
  store_ok: boolean;
  namespace_count: number;
  total_entries: number;
  namespaces: MemoryNamespace[];
  search_available: boolean;
  cloud_sync_configured: boolean;
  cloud_sync_live_claimed: boolean;
  fake_data?: boolean;
  [key: string]: unknown;
}

interface MemoryNamespacesResponse {
  namespaces: MemoryNamespace[];
  count: number;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatStrip({
  namespaceCount,
  totalEntries,
  searchAvailable,
  cloudSyncConfigured,
  cloudSyncLiveClaimed,
}: {
  namespaceCount: number;
  totalEntries: number;
  searchAvailable: boolean;
  cloudSyncConfigured: boolean;
  cloudSyncLiveClaimed: boolean;
}) {
  const cloudLabel = cloudSyncLiveClaimed
    ? 'Live'
    : cloudSyncConfigured
    ? 'Configured'
    : 'Not configured';

  const cloudColor = cloudSyncLiveClaimed
    ? C.success
    : cloudSyncConfigured
    ? C.info
    : C.textTert;

  const cells = [
    {
      label: 'Namespaces',
      value: String(namespaceCount),
      icon: <Layers size={14} />,
      color: C.accent,
    },
    {
      label: 'Total Entries',
      value: String(totalEntries),
      icon: <Database size={14} />,
      color: C.accent,
    },
    {
      label: 'Search',
      value: searchAvailable ? 'Available' : 'Offline',
      icon: <Search size={14} />,
      color: searchAvailable ? C.success : C.warning,
    },
    {
      label: 'Cloud Sync',
      value: cloudLabel,
      icon: cloudSyncConfigured ? <Cloud size={14} /> : <CloudOff size={14} />,
      color: cloudColor,
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {cells.map((c) => (
        <div
          key={c.label}
          className="rounded-lg px-3 py-3 text-center"
          style={{ background: C.surface, border: `1px solid ${C.border}` }}
        >
          <div
            className="flex items-center justify-center gap-1.5 mb-1"
            style={{ color: c.color }}
          >
            {c.icon}
            <span className="text-base font-bold tabular-nums">{c.value}</span>
          </div>
          <div className="text-xs" style={{ color: C.textTert }}>
            {c.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function NamespaceCard({ ns }: { ns: MemoryNamespace }) {
  return (
    <div
      className="rounded-lg px-4 py-3 flex items-center justify-between gap-3"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-center gap-2 min-w-0">
        <Database size={13} style={{ color: C.accent, flexShrink: 0 }} />
        <span
          className="text-sm font-mono truncate"
          style={{ color: C.text }}
          title={ns.name}
        >
          {ns.name}
        </span>
      </div>
      <span
        className="text-xs tabular-nums shrink-0 px-2 py-0.5 rounded"
        style={{ background: C.surfaceAlt, color: C.textSec }}
      >
        {ns.count} {ns.count === 1 ? 'entry' : 'entries'}
      </span>
    </div>
  );
}

function CapabilityRow({
  label,
  status,
  available,
  note,
}: {
  label: string;
  status: string;
  available: boolean;
  note?: string;
}) {
  return (
    <div
      className="flex items-start gap-3 px-4 py-2.5"
      style={{ borderBottom: `1px solid ${C.border}` }}
    >
      <div className="mt-0.5 shrink-0">
        {available ? (
          <CheckCircle2 size={13} style={{ color: C.success }} />
        ) : (
          <XCircle size={13} style={{ color: C.textTert }} />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm" style={{ color: C.text }}>
            {label}
          </span>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded font-mono"
            style={{
              background: C.surfaceAlt,
              color: available ? C.success : C.textTert,
            }}
          >
            {status}
          </span>
        </div>
        {note && (
          <div className="text-xs mt-0.5" style={{ color: C.textTert }}>
            {note}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MemoryOSPage() {
  const [dashboard, setDashboard] = useState<MemoryDashboard | null>(null);
  const [namespaces, setNamespaces] = useState<MemoryNamespace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [dashRes, nsRes] = await Promise.all([
        apiFetch('/v1/memory/dashboard'),
        apiFetch('/v1/memory/namespaces'),
      ]);

      if (!dashRes.ok && !nsRes.ok) {
        setError(
          `API unavailable (dashboard: ${dashRes.status}, namespaces: ${nsRes.status})`,
        );
        return;
      }

      if (dashRes.ok) {
        const d: MemoryDashboard = await dashRes.json();
        setDashboard(d);
      } else {
        setError(`Dashboard unavailable (${dashRes.status})`);
      }

      if (nsRes.ok) {
        const n: MemoryNamespacesResponse = await nsRes.json();
        // Sort descending by count
        const sorted = [...(n.namespaces ?? [])].sort(
          (a, b) => b.count - a.count,
        );
        setNamespaces(sorted);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load memory data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Prefer namespace list from dedicated /v1/memory/namespaces endpoint;
  // fall back to dashboard namespaces sorted the same way.
  const displayedNamespaces =
    namespaces.length > 0
      ? namespaces
      : [...(dashboard?.namespaces ?? [])].sort((a, b) => b.count - a.count);

  const searchAvailable = dashboard?.search_available ?? false;
  const cloudConfigured = dashboard?.cloud_sync_configured ?? false;
  const cloudLive = dashboard?.cloud_sync_live_claimed ?? false;

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <Brain size={20} style={{ color: C.accent }} />
              <h1
                className="text-lg font-semibold"
                style={{ color: C.text }}
              >
                Memory OS
              </h1>
            </div>
            <button
              onClick={load}
              className="p-2 rounded-lg transition-colors cursor-pointer"
              style={{ color: C.textSec }}
              title="Refresh"
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = C.surface)
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = 'transparent')
              }
            >
              <RefreshCw
                size={16}
                className={loading ? 'animate-spin' : ''}
              />
            </button>
          </div>
          <p className="text-sm mt-1.5" style={{ color: C.textSec }}>
            VANTA memory namespaces, search, and context.
          </p>
        </header>

        {/* Global error */}
        {error && (
          <div
            className="rounded-lg px-4 py-3 mb-5 flex items-center gap-2 text-sm"
            style={{
              background: 'rgba(243,139,168,0.1)',
              color: C.danger,
              border: `1px solid rgba(243,139,168,0.2)`,
            }}
          >
            <AlertTriangle size={14} />
            {error}
          </div>
        )}

        {/* Store health notice */}
        {dashboard && !dashboard.store_ok && (
          <div
            className="flex items-start gap-2 px-4 py-3 rounded-lg mb-4 text-sm"
            style={{
              background: 'rgba(249,226,175,0.07)',
              border: `1px solid rgba(249,226,175,0.2)`,
            }}
          >
            <AlertTriangle
              size={14}
              className="mt-0.5 shrink-0"
              style={{ color: C.warning }}
            />
            <span style={{ color: C.textSec }}>
              Memory store reported not OK. Data shown may be partial or stale.
            </span>
          </div>
        )}

        {/* Stats strip */}
        {dashboard && (
          <StatStrip
            namespaceCount={dashboard.namespace_count}
            totalEntries={dashboard.total_entries}
            searchAvailable={searchAvailable}
            cloudSyncConfigured={cloudConfigured}
            cloudSyncLiveClaimed={cloudLive}
          />
        )}

        {/* Loading */}
        {loading && (
          <div
            className="text-sm text-center py-14"
            style={{ color: C.textTert }}
          >
            <Brain
              size={20}
              className="mx-auto mb-3 animate-pulse"
              style={{ color: C.accent }}
            />
            Loading memory data…
          </div>
        )}

        {/* Namespace list */}
        {!loading && (
          <section className="mb-8">
            <div
              className="text-xs font-medium uppercase tracking-wide mb-3"
              style={{ color: C.textTert }}
            >
              Namespaces
            </div>

            {displayedNamespaces.length > 0 ? (
              <div className="space-y-2">
                {displayedNamespaces.map((ns) => (
                  <NamespaceCard key={ns.name} ns={ns} />
                ))}
              </div>
            ) : (
              <div
                className="rounded-lg px-4 py-10 text-center"
                style={{
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                }}
              >
                <Database
                  size={22}
                  className="mx-auto mb-3"
                  style={{ color: C.textTert }}
                />
                <div
                  className="text-sm font-medium mb-1"
                  style={{ color: C.text }}
                >
                  No namespaces found
                </div>
                <div className="text-xs" style={{ color: C.textTert }}>
                  Memory will populate as VANTA stores context during
                  conversations.
                </div>
              </div>
            )}
          </section>
        )}

        {/* Capabilities section */}
        {!loading && dashboard && (
          <section className="mb-8">
            <div
              className="text-xs font-medium uppercase tracking-wide mb-3"
              style={{ color: C.textTert }}
            >
              Memory Capabilities
            </div>

            <div
              className="rounded-lg overflow-hidden"
              style={{ border: `1px solid ${C.border}` }}
            >
              <CapabilityRow
                label="Keyword search"
                status="available via /v1/memory/search"
                available={true}
                note="POST /v1/memory/search with { query, top_k }"
              />
              <CapabilityRow
                label="Semantic search"
                status={searchAvailable ? 'available' : 'offline'}
                available={searchAvailable}
                note={
                  searchAvailable
                    ? 'Vector similarity search enabled.'
                    : 'Semantic search not available in current memory backend.'
                }
              />
              <CapabilityRow
                label="Cloud sync"
                status={
                  cloudLive
                    ? 'live'
                    : cloudConfigured
                    ? 'configured — not confirmed live'
                    : 'not configured'
                }
                available={cloudLive}
                note={
                  cloudLive
                    ? 'Cloud sync is active and confirmed live.'
                    : cloudConfigured
                    ? 'Credentials present. Live sync not confirmed — requires Fargate env credentials.'
                    : 'Cloud sync requires S3 credentials in Fargate env.'
                }
              />
              <div
                className="flex items-start gap-3 px-4 py-2.5"
                style={{ borderBottom: `1px solid ${C.border}` }}
              >
                <div className="mt-0.5 shrink-0">
                  <Info size={13} style={{ color: C.info }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm" style={{ color: C.text }}>
                      AI distillation
                    </span>
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                      style={{ background: C.surfaceAlt, color: C.info }}
                    >
                      check /v1/memory/status
                    </span>
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: C.textTert }}>
                    Distillation status available via the memory/status endpoint.
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Cloud sync honesty banner */}
        {!loading && dashboard && !cloudLive && (
          <div
            className="flex items-start gap-2 px-4 py-3 rounded-lg mb-6 text-xs"
            style={{
              background: 'rgba(137,220,235,0.06)',
              border: `1px solid rgba(137,220,235,0.15)`,
            }}
          >
            <CloudOff
              size={13}
              className="mt-0.5 shrink-0"
              style={{ color: C.info }}
            />
            <span style={{ color: C.textSec }}>
              {cloudConfigured
                ? 'Cloud sync credentials are configured but live sync is not confirmed. Memory shown is from the local store only.'
                : 'Cloud sync is not configured. All memory data is local. To enable cloud sync, set S3 credentials in the Fargate environment.'}
            </span>
          </div>
        )}

        {/* Provenance footer */}
        <div className="mt-4 text-xs italic" style={{ color: C.textTert }}>
          Data from{' '}
          <code style={{ fontFamily: 'monospace', fontSize: 11 }}>
            /v1/memory/dashboard
          </code>{' '}
          — local memory store. Cloud sync requires Fargate env credentials.
        </div>
      </div>
    </div>
  );
}
