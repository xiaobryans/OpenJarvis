/**
 * Plan 4-6 — Routines & Cadence Center
 *
 * Route: /routines
 * Shows recurring scheduled tasks managed by Jarvis.
 * Data from:
 *   - GET /v1/routines
 *   - GET /v1/routines/summary
 *   - GET /v1/routines/status
 *
 * Design rules:
 *   - No fake data anywhere.
 *   - Never claim automations are running when scheduler_started=false.
 *   - Loading, error, and empty states always present.
 *   - Mobile-responsive throughout.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  AlertTriangle,
  Info,
  CalendarClock,
  CheckCircle2,
  PauseCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Terminal,
  Cpu,
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

interface Routine {
  id?: string;
  name?: string;
  schedule_type?: string;
  status?: string;
  next_run?: string | null;
  description?: string;
  created_at?: string | null;
  [key: string]: unknown;
}

interface RoutinesResponse {
  routines: Routine[];
  count: number;
  scheduler_started: boolean;
  automation_honesty?: string;
}

interface RoutinesSummary {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  active: number;
  paused: number;
  completed: number;
  failed: number;
  scheduler_started: boolean;
  fake_data?: boolean;
  automation_honesty?: string;
}

interface RoutinesStatus {
  scheduler_started: boolean;
  scheduler_module?: string;
  schedule_types_supported?: string[];
  total_scheduled_tasks?: number;
  honesty?: string;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatStrip({
  total,
  active,
  paused,
  completed,
  failed,
}: {
  total: number;
  active: number;
  paused: number;
  completed: number;
  failed: number;
}) {
  const cells = [
    { label: 'Total', value: total, color: C.accent },
    { label: 'Active', value: active, color: C.success },
    { label: 'Paused', value: paused, color: C.warning },
    { label: 'Completed', value: completed, color: C.textSec },
    { label: 'Failed', value: failed, color: C.danger },
  ];
  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-6">
      {cells.map((c) => (
        <div
          key={c.label}
          className="rounded-lg px-3 py-3 text-center"
          style={{ background: C.surface, border: `1px solid ${C.border}` }}
        >
          <div
            className="text-xl font-bold tabular-nums"
            style={{ color: c.color }}
          >
            {c.value}
          </div>
          <div className="text-xs mt-0.5" style={{ color: C.textTert }}>
            {c.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function SchedulerBanner({
  started,
  module,
  honesty,
}: {
  started: boolean;
  module?: string;
  honesty?: string;
}) {
  return (
    <div
      className="flex items-start gap-3 px-4 py-3 rounded-lg mb-5 text-sm"
      style={{
        background: 'rgba(137,220,235,0.07)',
        border: `1px solid rgba(137,220,235,0.2)`,
      }}
    >
      <Info size={15} className="mt-0.5 shrink-0" style={{ color: C.info }} />
      <div style={{ color: C.textSec }}>
        {started ? (
          <span>
            Scheduler is <strong style={{ color: C.success }}>running</strong>
            {module ? ` (module: ${module})` : ''}. Automations are active.
          </span>
        ) : (
          <span>
            Scheduler module available{module ? ` (${module})` : ''}.{' '}
            <strong style={{ color: C.warning }}>Not auto-started.</strong> Use{' '}
            <code
              className="px-1.5 py-0.5 rounded text-xs"
              style={{
                background: C.surfaceAlt,
                fontFamily: 'monospace',
                color: C.info,
              }}
            >
              jarvis scheduler start
            </code>{' '}
            CLI to run automations.
          </span>
        )}
        {honesty && (
          <div className="mt-1 text-xs italic" style={{ color: C.textTert }}>
            {honesty}
          </div>
        )}
      </div>
    </div>
  );
}

function ScheduleTypeChips({ types }: { types: string[] }) {
  if (!types.length) return null;
  return (
    <div className="flex flex-wrap gap-2 mb-5 items-center">
      <span className="text-xs" style={{ color: C.textTert }}>
        Supported schedule types:
      </span>
      {types.map((t) => (
        <span
          key={t}
          className="px-2 py-0.5 rounded text-xs font-mono"
          style={{
            background: C.surfaceAlt,
            color: C.accent,
            border: `1px solid ${C.border}`,
          }}
        >
          {t}
        </span>
      ))}
    </div>
  );
}

function statusIcon(status: string | undefined) {
  switch (status) {
    case 'active':
      return <CheckCircle2 size={13} style={{ color: C.success }} />;
    case 'paused':
      return <PauseCircle size={13} style={{ color: C.warning }} />;
    case 'failed':
      return <XCircle size={13} style={{ color: C.danger }} />;
    case 'completed':
      return <CheckCircle2 size={13} style={{ color: C.textTert }} />;
    default:
      return <Clock size={13} style={{ color: C.textTert }} />;
  }
}

function statusColor(status: string | undefined): string {
  switch (status) {
    case 'active':
      return C.success;
    case 'paused':
      return C.warning;
    case 'failed':
      return C.danger;
    default:
      return C.textTert;
  }
}

function RoutineCard({ routine }: { routine: Routine }) {
  const [expanded, setExpanded] = useState(false);
  const name = routine.name ?? routine.id ?? 'Unnamed routine';
  const scheduleType = routine.schedule_type ?? 'unknown';
  const status = routine.status ?? 'unknown';

  return (
    <div
      className="rounded-lg mb-2 overflow-hidden"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-start gap-3 px-4 py-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-0.5 shrink-0 cursor-pointer"
          style={{ color: C.textTert }}
          title={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        <div className="mt-0.5 shrink-0">{statusIcon(status)}</div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="font-medium text-sm"
              style={{ color: C.text }}
            >
              {name}
            </span>
            <span
              className="px-2 py-0.5 rounded text-[10px] font-mono"
              style={{ background: C.surfaceAlt, color: statusColor(status) }}
            >
              {status}
            </span>
            <span
              className="px-2 py-0.5 rounded text-[10px] font-mono"
              style={{ background: C.surfaceAlt, color: C.accent }}
            >
              {scheduleType}
            </span>
          </div>

          {routine.description && (
            <div
              className="text-xs mt-0.5 line-clamp-2"
              style={{ color: C.textSec }}
            >
              {routine.description}
            </div>
          )}

          {routine.next_run && (
            <div
              className="flex items-center gap-1 text-xs mt-0.5"
              style={{ color: C.info }}
            >
              <Clock size={10} />
              Next run: {routine.next_run}
            </div>
          )}
        </div>
      </div>

      {expanded && (
        <div
          className="px-4 pb-4 text-xs"
          style={{
            borderTop: `1px solid ${C.border}`,
            color: C.textSec,
          }}
        >
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
            {routine.id && (
              <div>
                <span style={{ color: C.textTert }}>id: </span>
                <span style={{ fontFamily: 'monospace' }}>{String(routine.id)}</span>
              </div>
            )}
            <div>
              <span style={{ color: C.textTert }}>schedule_type: </span>
              {scheduleType}
            </div>
            <div>
              <span style={{ color: C.textTert }}>status: </span>
              {status}
            </div>
            {routine.next_run && (
              <div>
                <span style={{ color: C.textTert }}>next_run: </span>
                {routine.next_run}
              </div>
            )}
            {routine.created_at && (
              <div>
                <span style={{ color: C.textTert }}>created_at: </span>
                {String(routine.created_at)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function RoutinesCenterPage() {
  const [routinesData, setRoutinesData] = useState<RoutinesResponse | null>(null);
  const [summary, setSummary] = useState<RoutinesSummary | null>(null);
  const [statusData, setStatusData] = useState<RoutinesStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [routinesRes, summaryRes, statusRes] = await Promise.all([
        apiFetch('/v1/routines'),
        apiFetch('/v1/routines/summary'),
        apiFetch('/v1/routines/status'),
      ]);

      // Parse each response independently so a partial failure surfaces clearly
      const routinesJson: RoutinesResponse = routinesRes.ok
        ? await routinesRes.json()
        : { routines: [], count: 0, scheduler_started: false };

      const summaryJson: RoutinesSummary = summaryRes.ok
        ? await summaryRes.json()
        : {
            total: 0,
            by_type: {},
            by_status: {},
            active: 0,
            paused: 0,
            completed: 0,
            failed: 0,
            scheduler_started: false,
          };

      const statusJson: RoutinesStatus = statusRes.ok
        ? await statusRes.json()
        : { scheduler_started: false };

      setRoutinesData(routinesJson);
      setSummary(summaryJson);
      setStatusData(statusJson);

      if (!routinesRes.ok && !summaryRes.ok && !statusRes.ok) {
        setError(
          `API unavailable (routines: ${routinesRes.status}, summary: ${summaryRes.status}, status: ${statusRes.status})`,
        );
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load routines data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const schedulerStarted =
    statusData?.scheduler_started ??
    summary?.scheduler_started ??
    routinesData?.scheduler_started ??
    false;

  const supportedTypes = statusData?.schedule_types_supported ?? [];

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-10">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <CalendarClock size={20} style={{ color: C.accent }} />
              <h1 className="text-lg font-semibold" style={{ color: C.text }}>
                Routines &amp; Cadence
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
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
          <p className="text-sm mt-1.5" style={{ color: C.textSec }}>
            Recurring scheduled tasks managed by Jarvis.
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

        {/* Scheduler status banner */}
        <SchedulerBanner
          started={schedulerStarted}
          module={statusData?.scheduler_module}
          honesty={statusData?.honesty ?? routinesData?.automation_honesty}
        />

        {/* Stats strip */}
        {summary && (
          <StatStrip
            total={summary.total}
            active={summary.active}
            paused={summary.paused}
            completed={summary.completed}
            failed={summary.failed}
          />
        )}

        {/* Schedule type chips */}
        <ScheduleTypeChips types={supportedTypes} />

        {/* Loading */}
        {loading && (
          <div
            className="text-sm text-center py-14"
            style={{ color: C.textTert }}
          >
            <Cpu size={20} className="mx-auto mb-3 animate-pulse" />
            Loading routines…
          </div>
        )}

        {/* Routine cards */}
        {!loading && routinesData && routinesData.routines.length > 0 && (
          <div>
            <div
              className="text-xs font-medium mb-3 uppercase tracking-wide"
              style={{ color: C.textTert }}
            >
              {routinesData.count} routine
              {routinesData.count !== 1 ? 's' : ''}
            </div>
            {routinesData.routines.map((r, idx) => (
              <RoutineCard key={r.id ?? idx} routine={r} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && (!routinesData || routinesData.routines.length === 0) && (
          <div
            className="rounded-lg px-4 py-14 text-center"
            style={{ background: C.surface, border: `1px solid ${C.border}` }}
          >
            <Terminal
              size={24}
              className="mx-auto mb-3"
              style={{ color: C.textTert }}
            />
            <div
              className="text-sm font-medium mb-1"
              style={{ color: C.text }}
            >
              No routines configured
            </div>
            <div className="text-xs" style={{ color: C.textTert }}>
              Create recurring automations via the CLI:
            </div>
            <code
              className="inline-block mt-2 px-3 py-1.5 rounded text-xs"
              style={{
                background: C.surfaceAlt,
                color: C.info,
                fontFamily: 'monospace',
                border: `1px solid ${C.border}`,
              }}
            >
              jarvis routine create --name &quot;Daily digest&quot; --schedule &quot;0 9 * * *&quot;
            </code>
            <div className="text-xs mt-3" style={{ color: C.textTert }}>
              Routines are stored locally. No connector credentials required.
            </div>
          </div>
        )}

        {/* Honesty footer */}
        <div
          className="mt-6 text-xs italic"
          style={{ color: C.textTert }}
        >
          Data from{' '}
          <code style={{ fontFamily: 'monospace', fontSize: 11 }}>
            /v1/routines
          </code>{' '}
          — local scheduler store only. No connector credentials required.
        </div>
      </div>
    </div>
  );
}
