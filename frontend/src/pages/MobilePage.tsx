/**
 * MobilePage — Plan 4 mobile-safe Jarvis dashboard.
 *
 * Single-column, touch-friendly view with configurable backend targeting:
 *   - Local mode:  targets same origin (MacBook Jarvis server)
 *   - Remote mode: targets AWS ECS Fargate always-on backend
 *
 * Backend is stored in localStorage key "jarvis_mobile_backend_url".
 * The remote backend exposes CORS headers, so direct fetch works.
 *
 * API endpoints consumed:
 *   GET /health                       — backend reachability
 *   GET /v1/system/health             — memory_os sub-key
 *   GET /v1/memory/status             — semantic search, cloud sync, distillation
 *   GET /v1/mobile/continuity/status  — cross-device backend state
 *   GET /v1/approvals/pending         — pending approval queue (local only)
 */

import { useEffect, useRef, useState } from 'react';
import { fetchPendingApprovals, type PendingApproval } from '../lib/api';

// ---------------------------------------------------------------------------
// Backend URL management
// ---------------------------------------------------------------------------

const LS_KEY = 'jarvis_mobile_backend_url';
const AWS_BACKEND = 'http://52.221.255.60:3091';

function getStoredBackend(): string {
  try {
    return localStorage.getItem(LS_KEY) ?? '';
  } catch {
    return '';
  }
}

function storeBackend(url: string): void {
  try {
    if (url) {
      localStorage.setItem(LS_KEY, url);
    } else {
      localStorage.removeItem(LS_KEY);
    }
  } catch {
    // ignore
  }
}

async function backendFetch(backendUrl: string, path: string): Promise<Response> {
  const base = backendUrl.replace(/\/$/, '');
  const url = base ? `${base}${path}` : path;
  return fetch(url, { headers: { Accept: 'application/json' } });
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HealthStatus {
  reachable: boolean;
  status?: string;
  version?: string;
  uptime_seconds?: number;
  memory_os?: {
    sprint?: string;
    total_entries?: number;
    vector_search?: string;
    cloud_sync_available?: boolean;
    cloud_sync_backend?: string;
    ai_distillation_available?: boolean;
  };
  runtime?: {
    deployment?: string;
    macbook_off_capable?: boolean;
  };
}

interface MemoryStatus {
  memory_os?: { sprint?: string; total_entries?: number; total_distilled?: number };
  semantic_search?: { vector_search?: string; active_ranker?: string };
  cloud_sync?: { available?: boolean; backend?: string; last_error?: string | null };
  ai_distillation?: { ai_available?: boolean };
}

interface ContinuityBackend {
  name?: string;
  backend_name?: string;
  availability: string;
  macbook_off_capable: boolean;
  notes?: string;
}

interface ContinuityStatus {
  backends?: ContinuityBackend[];
  active_backend?: string;
  cross_device_ready?: boolean;
  active_task_description?: string;
  active_task_status?: string;
  // Plan 4 AWS fields
  runtime_macbook_off_capable?: boolean;
  runtime_deployment?: string;
  runtime_always_on_status?: string;
  state_sync_macbook_off_capable?: boolean;
  mobile_client_available?: boolean;
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

const STATUS_COLOR: Record<string, string> = {
  ok: 'var(--color-success, #22c55e)',
  error: 'var(--color-error, #ef4444)',
  warn: 'var(--color-warn, #f59e0b)',
  info: 'var(--color-accent, #4fd1ff)',
};

function Dot({ color }: { color: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
      }}
    />
  );
}

function Card({
  title,
  children,
  borderColor,
}: {
  title: string;
  children: React.ReactNode;
  borderColor?: string;
}) {
  return (
    <section
      style={{
        background: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 90%, transparent)',
        border: `1px solid ${borderColor ?? 'color-mix(in srgb, var(--color-border, #333) 60%, transparent)'}`,
        borderRadius: '12px',
        padding: '16px',
        marginBottom: '12px',
      }}
    >
      <h2
        style={{
          fontSize: '11px',
          fontWeight: 600,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--color-text-muted, #888)',
          marginBottom: '10px',
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function Row({ label, value, dot }: { label: string; value: string; dot?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '8px',
        padding: '4px 0',
        fontSize: '13px',
        borderBottom: '1px solid color-mix(in srgb, var(--color-border, #333) 30%, transparent)',
      }}
    >
      <span style={{ color: 'var(--color-text-muted, #aaa)' }}>{label}</span>
      <span
        style={{
          color: 'var(--color-text, #eee)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '12px',
          fontFamily: 'monospace',
          textAlign: 'right',
          maxWidth: '60%',
          wordBreak: 'break-all',
        }}
      >
        {dot && <Dot color={dot} />}
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function MobilePage() {
  const [backendUrl, setBackendUrl] = useState<string>(getStoredBackend);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [memory, setMemory] = useState<MemoryStatus | null>(null);
  const [continuity, setContinuity] = useState<ContinuityStatus | null>(null);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isRemote = backendUrl.trim() !== '';
  const targetLabel = isRemote
    ? `AWS (${backendUrl.replace(/^https?:\/\//, '').split(':')[0]})`
    : 'Local (MacBook)';

  const fetchAll = async (url?: string) => {
    const base = url ?? backendUrl;
    setRefreshing(true);

    try {
      const res = await backendFetch(base, '/v1/system/health');
      if (res.ok) {
        const data = await res.json();
        setHealth({ reachable: true, ...data });
      } else {
        setHealth({ reachable: false });
      }
    } catch {
      setHealth({ reachable: false });
    }

    try {
      const res = await backendFetch(base, '/v1/memory/status');
      if (res.ok) setMemory(await res.json());
    } catch {
      // non-fatal
    }

    try {
      const res = await backendFetch(base, '/v1/mobile/continuity/status');
      if (res.ok) setContinuity(await res.json());
    } catch {
      // non-fatal
    }

    // Approvals: local only (write operation context — no remote support yet)
    if (!base) {
      try {
        const pending = await fetchPendingApprovals();
        setApprovals(pending);
      } catch {
        setApprovals([]);
      }
    } else {
      setApprovals([]);
    }

    setLastRefresh(new Date());
    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => {
    fetchAll();
    intervalRef.current = setInterval(fetchAll, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendUrl]);

  const switchBackend = (url: string) => {
    storeBackend(url);
    setBackendUrl(url);
    setLoading(true);
    setHealth(null);
    setMemory(null);
    setContinuity(null);
  };

  const isReachable = health?.reachable ?? false;
  const memOS = health?.memory_os;

  return (
    <div
      style={{
        maxWidth: '480px',
        margin: '0 auto',
        padding: '16px 12px 32px',
        minHeight: '100%',
        color: 'var(--color-text, #eee)',
        fontFamily: 'var(--font-sans, system-ui, sans-serif)',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Dot color={isReachable ? STATUS_COLOR.ok : STATUS_COLOR.error} />
          <span style={{ fontSize: '18px', fontWeight: 700, letterSpacing: '-0.01em' }}>
            Jarvis
          </span>
          <span
            style={{
              fontSize: '11px',
              background: 'color-mix(in srgb, var(--color-accent, #4fd1ff) 12%, transparent)',
              color: 'var(--color-accent, #4fd1ff)',
              border: '1px solid color-mix(in srgb, var(--color-accent, #4fd1ff) 30%, transparent)',
              borderRadius: '4px',
              padding: '1px 6px',
            }}
          >
            mobile
          </span>
        </div>
        <button
          onClick={() => fetchAll()}
          disabled={refreshing}
          style={{
            fontSize: '12px',
            padding: '6px 12px',
            background: 'color-mix(in srgb, var(--color-accent, #4fd1ff) 10%, transparent)',
            color: 'var(--color-accent, #4fd1ff)',
            border: '1px solid color-mix(in srgb, var(--color-accent, #4fd1ff) 25%, transparent)',
            borderRadius: '6px',
            cursor: refreshing ? 'not-allowed' : 'pointer',
            opacity: refreshing ? 0.6 : 1,
          }}
        >
          {refreshing ? '…' : 'Refresh'}
        </button>
      </div>

      {/* Backend selector */}
      <div
        style={{
          display: 'flex',
          gap: '6px',
          marginBottom: '16px',
          padding: '10px',
          background: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 80%, transparent)',
          border: '1px solid color-mix(in srgb, var(--color-border, #333) 50%, transparent)',
          borderRadius: '10px',
        }}
      >
        <button
          onClick={() => switchBackend('')}
          style={{
            flex: 1,
            padding: '7px 0',
            fontSize: '12px',
            fontWeight: !isRemote ? 600 : 400,
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            background: !isRemote
              ? 'color-mix(in srgb, var(--color-accent, #4fd1ff) 18%, transparent)'
              : 'transparent',
            color: !isRemote ? 'var(--color-accent, #4fd1ff)' : 'var(--color-text-muted, #888)',
            transition: 'all 0.15s',
          }}
        >
          Local
        </button>
        <button
          onClick={() => switchBackend(AWS_BACKEND)}
          style={{
            flex: 1,
            padding: '7px 0',
            fontSize: '12px',
            fontWeight: isRemote ? 600 : 400,
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            background: isRemote
              ? 'color-mix(in srgb, #f59e0b 18%, transparent)'
              : 'transparent',
            color: isRemote ? '#f59e0b' : 'var(--color-text-muted, #888)',
            transition: 'all 0.15s',
          }}
        >
          AWS Always-On
        </button>
      </div>

      {/* Backend target badge */}
      <div
        style={{
          fontSize: '11px',
          color: 'var(--color-text-muted, #888)',
          marginBottom: '14px',
          fontFamily: 'monospace',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
      >
        <span>Target:</span>
        <span style={{ color: isRemote ? '#f59e0b' : 'var(--color-text, #eee)' }}>
          {isRemote ? backendUrl : 'same origin'}
        </span>
        {isRemote && (
          <span
            style={{
              fontSize: '10px',
              background: 'color-mix(in srgb, #f59e0b 12%, transparent)',
              color: '#f59e0b',
              border: '1px solid color-mix(in srgb, #f59e0b 25%, transparent)',
              borderRadius: '3px',
              padding: '1px 5px',
            }}
          >
            ALWAYS-ON
          </span>
        )}
      </div>

      {loading ? (
        <div
          style={{
            textAlign: 'center',
            padding: '40px 0',
            color: 'var(--color-text-muted, #888)',
            fontSize: '14px',
          }}
        >
          Connecting to {targetLabel}…
        </div>
      ) : (
        <>
          {/* Backend Health */}
          <Card
            title="Backend"
            borderColor={
              isReachable
                ? 'color-mix(in srgb, var(--color-success, #22c55e) 25%, transparent)'
                : 'color-mix(in srgb, var(--color-error, #ef4444) 25%, transparent)'
            }
          >
            <Row
              label="Status"
              value={isReachable ? 'Reachable' : 'Unreachable'}
              dot={isReachable ? STATUS_COLOR.ok : STATUS_COLOR.error}
            />
            <Row label="Target" value={targetLabel} />
            {health?.version && <Row label="Version" value={health.version} />}
            {health?.uptime_seconds !== undefined && (
              <Row label="Uptime" value={`${Math.round(health.uptime_seconds)}s`} />
            )}
            {health?.runtime && (
              <Row
                label="MacBook-off"
                value={health.runtime.macbook_off_capable ? 'Yes (AWS)' : 'No (local only)'}
                dot={health.runtime.macbook_off_capable ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
            )}
            {memOS && (
              <>
                <Row label="Memory entries" value={String(memOS.total_entries ?? '—')} />
                <Row
                  label="Cloud sync"
                  value={memOS.cloud_sync_available ? (memOS.cloud_sync_backend ?? 'S3') : 'Local only'}
                  dot={memOS.cloud_sync_available ? STATUS_COLOR.ok : STATUS_COLOR.warn}
                />
                <Row
                  label="Vector search"
                  value={memOS.vector_search?.replace('ACTIVE_', '').replace('BLOCKED_', '⚠ ') ?? '—'}
                />
              </>
            )}
          </Card>

          {/* Memory OS */}
          {memory && (
            <Card title="Memory OS">
              <Row
                label="Total entries"
                value={String(memory.memory_os?.total_entries ?? '—')}
              />
              <Row label="Distilled" value={String(memory.memory_os?.total_distilled ?? '—')} />
              <Row label="Ranker" value={memory.semantic_search?.active_ranker ?? '—'} />
              <Row
                label="Cloud sync"
                value={
                  memory.cloud_sync?.available
                    ? `${memory.cloud_sync.backend ?? 'S3'} ✓`
                    : 'Local only'
                }
                dot={memory.cloud_sync?.available ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
              <Row
                label="AI distillation"
                value={memory.ai_distillation?.ai_available ? 'Available' : 'Unavailable'}
                dot={memory.ai_distillation?.ai_available ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
            </Card>
          )}

          {/* Continuity */}
          {continuity && (
            <Card title="Cross-Device Continuity">
              {continuity.active_task_description ? (
                <>
                  <div
                    style={{
                      fontSize: '13px',
                      color: 'var(--color-text, #eee)',
                      marginBottom: '8px',
                      padding: '8px',
                      background:
                        'color-mix(in srgb, var(--color-accent, #4fd1ff) 5%, transparent)',
                      borderRadius: '6px',
                      border:
                        '1px solid color-mix(in srgb, var(--color-accent, #4fd1ff) 15%, transparent)',
                    }}
                  >
                    {continuity.active_task_description}
                  </div>
                  <Row label="Task status" value={continuity.active_task_status ?? '—'} />
                </>
              ) : (
                <div
                  style={{
                    fontSize: '13px',
                    color: 'var(--color-text-muted, #888)',
                    padding: '4px 0',
                    marginBottom: '4px',
                  }}
                >
                  No active task
                </div>
              )}
              <Row
                label="Cross-device ready"
                value={continuity.cross_device_ready ? 'Yes (Gist)' : 'No'}
                dot={continuity.cross_device_ready ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
              <Row
                label="Runtime (MacBook-off)"
                value={
                  continuity.runtime_macbook_off_capable
                    ? `Yes — ${continuity.runtime_deployment ?? 'cloud'}`
                    : 'No — localhost only'
                }
                dot={
                  continuity.runtime_macbook_off_capable ? STATUS_COLOR.ok : STATUS_COLOR.warn
                }
              />
              <Row
                label="State sync (MacBook-off)"
                value={continuity.state_sync_macbook_off_capable ? 'Yes (Gist + S3)' : 'Partial'}
                dot={continuity.state_sync_macbook_off_capable ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
              {continuity.backends?.map((b) => {
                const name = b.name ?? b.backend_name ?? 'backend';
                const avail = b.availability.replace('BackendAvailability.', '');
                return (
                  <Row
                    key={name}
                    label={name}
                    value={avail}
                    dot={
                      b.availability.includes('available') ? STATUS_COLOR.ok : STATUS_COLOR.warn
                    }
                  />
                );
              })}
              {continuity.runtime_always_on_status && (
                <div
                  style={{
                    fontSize: '11px',
                    color: 'var(--color-text-muted, #888)',
                    marginTop: '8px',
                    padding: '6px 8px',
                    background:
                      'color-mix(in srgb, var(--color-border, #333) 20%, transparent)',
                    borderRadius: '6px',
                    lineHeight: '1.4',
                  }}
                >
                  {continuity.runtime_always_on_status}
                </div>
              )}
            </Card>
          )}

          {/* Approvals (local only) */}
          {!isRemote && (
            <Card
              title={`Pending Approvals${approvals.length > 0 ? ` (${approvals.length})` : ''}`}
              borderColor={
                approvals.length > 0
                  ? 'color-mix(in srgb, var(--color-warn, #f59e0b) 30%, transparent)'
                  : undefined
              }
            >
              {approvals.length === 0 ? (
                <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                  No pending approvals
                </div>
              ) : (
                approvals.map((a) => (
                  <div
                    key={a.id}
                    style={{
                      padding: '8px',
                      marginBottom: '6px',
                      background:
                        'color-mix(in srgb, var(--color-warn, #f59e0b) 6%, transparent)',
                      border:
                        '1px solid color-mix(in srgb, var(--color-warn, #f59e0b) 20%, transparent)',
                      borderRadius: '8px',
                      fontSize: '13px',
                    }}
                  >
                    <div style={{ fontWeight: 500, marginBottom: '2px' }}>{a.action_type}</div>
                    <div style={{ color: 'var(--color-text-muted, #aaa)', fontSize: '12px' }}>
                      {a.description}
                    </div>
                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--color-text-muted, #888)',
                        marginTop: '4px',
                      }}
                    >
                      Tier: {a.tier} · {new Date(a.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                ))
              )}
            </Card>
          )}
          {isRemote && (
            <Card title="Pending Approvals">
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                Approvals not available in remote mode — switch to Local.
              </div>
            </Card>
          )}

          {/* Footer */}
          {lastRefresh && (
            <div
              style={{
                textAlign: 'center',
                fontSize: '11px',
                color: 'var(--color-text-muted, #666)',
                paddingTop: '8px',
              }}
            >
              Last updated: {lastRefresh.toLocaleTimeString()} · auto-refreshes every 30s
            </div>
          )}
        </>
      )}
    </div>
  );
}
