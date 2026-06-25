/**
 * Phase B1 — Jarvis Follow-Up Center
 *
 * Route: /follow-ups
 * Aggregated view of all follow-up items from:
 *   - Life-OS personal tasks (waiting_followup status or active follow_up_state)
 *   - Long-horizon goals (follow_up_queue items)
 *
 * Design rules:
 *   - No fake data — shows empty state when no items exist.
 *   - No credential dependency — reads from local SQLite stores only.
 *   - No voice, no iOS, no signing/notarization.
 *   - Write actions (complete/snooze) preserve approval gates.
 *   - Approval-required items surface the approval route rather than auto-completing.
 *   - Mobile-responsive throughout.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle,
  Clock,
  AlertTriangle,
  Bell,
  RefreshCw,
  Target,
  ListTodo,
  ChevronDown,
  ChevronUp,
  Shield,
  Calendar,
  Tag,
  Info,
} from 'lucide-react';
import type {
  FollowUpItem,
  FollowUpCenterResponse,
  FollowUpSummary,
} from '../lib/jarvis-api';
import {
  fetchFollowUpCenter,
  fetchFollowUpSummary,
  completeTaskFollowUp,
  snoozeTaskFollowUp,
} from '../lib/jarvis-api';

// ---------------------------------------------------------------------------
// Style tokens — consistent with Plan 4-6 pages
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
// Helpers
// ---------------------------------------------------------------------------

function formatDue(dueAt: number | null): string {
  if (dueAt === null) return 'No due date';
  const d = new Date(dueAt * 1000);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / 86400000);
  if (diffDays < 0) return `Overdue by ${Math.abs(diffDays)}d`;
  if (diffDays === 0) return 'Due today';
  if (diffDays === 1) return 'Due tomorrow';
  return `Due in ${diffDays}d`;
}

function statusColor(status: string): string {
  switch (status) {
    case 'due': return C.danger;
    case 'waiting_approval': return C.warning;
    case 'snoozed': return C.textTert;
    case 'completed': return C.success;
    default: return C.info;
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'due': return 'Due';
    case 'upcoming': return 'Upcoming';
    case 'waiting_approval': return 'Needs Approval';
    case 'snoozed': return 'Snoozed';
    case 'completed': return 'Completed';
    default: return status;
  }
}

function sourceIcon(source: string) {
  if (source === 'goal') return <Target size={13} />;
  return <ListTodo size={13} />;
}

function sourceLabel(source: string): string {
  if (source === 'goal') return 'Goal';
  if (source === 'life_os_task') return 'Task';
  return source;
}

// ---------------------------------------------------------------------------
// StatsStrip
// ---------------------------------------------------------------------------

function StatsStrip({ summary }: { summary: FollowUpSummary | null }) {
  if (!summary) return null;
  const stats = [
    { label: 'Total', value: summary.total },
    { label: 'Due', value: summary.due, color: C.danger },
    { label: 'Upcoming', value: summary.upcoming },
    { label: 'Needs Approval', value: summary.waiting_approval, color: C.warning },
    { label: 'Snoozed', value: summary.snoozed, color: C.textTert },
  ];
  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-6">
      {stats.map((s) => (
        <div
          key={s.label}
          className="rounded-lg px-3 py-3 text-center"
          style={{ background: C.surface, border: `1px solid ${C.border}` }}
        >
          <div className="text-lg font-semibold" style={{ color: s.color ?? C.text }}>
            {s.value}
          </div>
          <div className="text-xs mt-0.5" style={{ color: C.textSec }}>
            {s.label}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FollowUpRow
// ---------------------------------------------------------------------------

interface FollowUpRowProps {
  item: FollowUpItem;
  onComplete: (taskId: string) => void;
  onSnooze: (taskId: string) => void;
  completing: boolean;
  snoozing: boolean;
}

function FollowUpRow({ item, onComplete, onSnooze, completing, snoozing }: FollowUpRowProps) {
  const [expanded, setExpanded] = useState(false);

  const isTask = item.source === 'life_os_task';
  const taskId = isTask ? item.source_id : null;

  return (
    <div
      className="rounded-lg mb-2"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      {/* Row header */}
      <button
        className="w-full text-left px-4 py-3 flex items-center gap-3"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        {/* Status indicator */}
        <span
          className="flex-shrink-0 rounded px-2 py-0.5 text-xs font-medium"
          style={{ background: `${statusColor(item.status)}22`, color: statusColor(item.status) }}
        >
          {statusLabel(item.status)}
        </span>

        {/* Source badge */}
        <span
          className="flex-shrink-0 flex items-center gap-1 text-xs"
          style={{ color: C.textTert }}
        >
          {sourceIcon(item.source)}
          {sourceLabel(item.source)}
        </span>

        {/* Title */}
        <span className="flex-1 text-sm font-medium truncate" style={{ color: C.text }}>
          {item.title}
        </span>

        {/* Due badge */}
        {item.due_at !== null && (
          <span className="flex-shrink-0 flex items-center gap-1 text-xs" style={{ color: C.textSec }}>
            <Clock size={12} />
            {formatDue(item.due_at)}
          </span>
        )}

        {/* Approval badge */}
        {item.approval_required && (
          <Shield size={14} style={{ color: C.warning, flexShrink: 0 }} />
        )}

        {expanded ? (
          <ChevronUp size={15} style={{ color: C.textTert, flexShrink: 0 }} />
        ) : (
          <ChevronDown size={15} style={{ color: C.textTert, flexShrink: 0 }} />
        )}
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div
          className="px-4 pb-4 border-t grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs"
          style={{ borderColor: C.border, color: C.textSec }}
        >
          <div className="col-span-1 sm:col-span-2 pt-3">
            <span style={{ color: C.textTert }}>Description: </span>
            <span style={{ color: C.text }}>{item.description || '(none)'}</span>
          </div>

          <div>
            <span style={{ color: C.textTert }}>Priority: </span>
            {item.priority}
          </div>

          <div>
            <span style={{ color: C.textTert }}>Due: </span>
            {item.due_at ? new Date(item.due_at * 1000).toLocaleString() : 'Not set'}
          </div>

          {item.tags.length > 0 && (
            <div className="col-span-1 sm:col-span-2 flex flex-wrap gap-1 items-center">
              <Tag size={11} style={{ color: C.textTert }} />
              {item.tags.map((t) => (
                <span
                  key={t}
                  className="rounded px-1.5 py-0.5"
                  style={{ background: C.surfaceAlt, color: C.textSec }}
                >
                  {t}
                </span>
              ))}
            </div>
          )}

          {item.approval_required && (
            <div className="col-span-1 sm:col-span-2 flex items-center gap-1.5 mt-1"
              style={{ color: C.warning }}>
              <Shield size={12} />
              <span>Approval required — complete via</span>
              <code className="text-xs">{item.approval_route ?? '/v1/life-os/tasks/…/approve'}</code>
            </div>
          )}

          {/* Actions */}
          {isTask && taskId && (
            <div className="col-span-1 sm:col-span-2 flex flex-wrap gap-2 mt-2">
              {!item.approval_required && item.status !== 'completed' && (
                <button
                  onClick={() => onComplete(taskId)}
                  disabled={completing}
                  className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium"
                  style={{
                    background: `${C.success}22`,
                    color: C.success,
                    border: `1px solid ${C.success}44`,
                    opacity: completing ? 0.6 : 1,
                  }}
                >
                  <CheckCircle size={12} />
                  {completing ? 'Completing…' : 'Mark Done'}
                </button>
              )}

              {item.status !== 'snoozed' && item.status !== 'completed' && (
                <button
                  onClick={() => onSnooze(taskId)}
                  disabled={snoozing}
                  className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium"
                  style={{
                    background: `${C.textTert}22`,
                    color: C.textSec,
                    border: `1px solid ${C.border}`,
                    opacity: snoozing ? 0.6 : 1,
                  }}
                >
                  <Bell size={12} />
                  {snoozing ? 'Snoozing…' : 'Snooze 1 day'}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

type FilterSource = '' | 'life_os_task' | 'goal';
type FilterStatus = '' | 'due' | 'upcoming' | 'waiting_approval' | 'snoozed';

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function FollowUpCenterPage() {
  const [data, setData] = useState<FollowUpCenterResponse | null>(null);
  const [summary, setSummary] = useState<FollowUpSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<FilterSource>('');
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('');
  const [completing, setCompleting] = useState<string | null>(null);
  const [snoozing, setSnoozing] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [d, s] = await Promise.all([
        fetchFollowUpCenter({
          source: sourceFilter || undefined,
          status: statusFilter || undefined,
        }),
        fetchFollowUpSummary(),
      ]);
      setData(d);
      setSummary(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load follow-ups');
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleComplete = useCallback(async (taskId: string) => {
    setCompleting(taskId);
    setActionMsg(null);
    try {
      const result = await completeTaskFollowUp(taskId);
      if (result.action === 'approval_required') {
        setActionMsg(`Task requires approval — use the approval route to complete it.`);
      } else {
        setActionMsg('Task marked as done.');
        await load();
      }
    } catch {
      setActionMsg('Failed to complete task — please retry.');
    } finally {
      setCompleting(null);
    }
  }, [load]);

  const handleSnooze = useCallback(async (taskId: string) => {
    setSnoozing(taskId);
    setActionMsg(null);
    try {
      const oneDayFromNow = Date.now() / 1000 + 86400;
      await snoozeTaskFollowUp(taskId, oneDayFromNow, 'Snoozed from Follow-Up Center');
      setActionMsg('Follow-up snoozed for 1 day.');
      await load();
    } catch {
      setActionMsg('Failed to snooze — please retry.');
    } finally {
      setSnoozing(null);
    }
  }, [load]);

  const items = data?.items ?? [];
  const filterBtns: Array<{ label: string; value: FilterStatus; color?: string }> = [
    { label: 'All', value: '' },
    { label: 'Due', value: 'due', color: C.danger },
    { label: 'Upcoming', value: 'upcoming' },
    { label: 'Needs Approval', value: 'waiting_approval', color: C.warning },
    { label: 'Snoozed', value: 'snoozed' },
  ];
  const sourceBtns: Array<{ label: string; value: FilterSource }> = [
    { label: 'All sources', value: '' },
    { label: 'Tasks', value: 'life_os_task' },
    { label: 'Goals', value: 'goal' },
  ];

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: C.text }}>
            Follow-Up Center
          </h1>
          <p className="text-sm mt-0.5" style={{ color: C.textSec }}>
            Unified view of all follow-ups — tasks, goals, and delegation items.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded"
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            color: C.textSec,
            opacity: loading ? 0.6 : 1,
          }}
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stats strip */}
      <StatsStrip summary={summary} />

      {/* Filter row */}
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {statusFilter !== '' || sourceFilter !== '' ? (
          <span className="text-xs" style={{ color: C.textTert }}>Status:</span>
        ) : null}
        {filterBtns.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className="rounded px-2.5 py-1 text-xs"
            style={{
              background: statusFilter === f.value ? `${C.accent}22` : C.surface,
              border: `1px solid ${statusFilter === f.value ? C.accent : C.border}`,
              color: statusFilter === f.value ? C.accent : (f.color ?? C.textSec),
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-xs" style={{ color: C.textTert }}>Source:</span>
        {sourceBtns.map((s) => (
          <button
            key={s.value}
            onClick={() => setSourceFilter(s.value)}
            className="rounded px-2.5 py-1 text-xs"
            style={{
              background: sourceFilter === s.value ? `${C.accent}22` : C.surface,
              border: `1px solid ${sourceFilter === s.value ? C.accent : C.border}`,
              color: sourceFilter === s.value ? C.accent : C.textSec,
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Action feedback */}
      {actionMsg && (
        <div
          className="mb-4 flex items-center gap-2 px-3 py-2 rounded text-xs"
          style={{ background: `${C.info}18`, border: `1px solid ${C.info}44`, color: C.info }}
        >
          <Info size={13} />
          {actionMsg}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 py-8 justify-center" style={{ color: C.textTert }}>
          <RefreshCw size={16} className="animate-spin" />
          <span className="text-sm">Loading follow-ups…</span>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div
          className="rounded-lg px-4 py-6 text-center"
          style={{ background: C.surface, border: `1px solid ${C.border}` }}
        >
          <AlertTriangle size={24} className="mx-auto mb-2 opacity-50" style={{ color: C.danger }} />
          <div className="text-sm" style={{ color: C.danger }}>
            {error}
          </div>
          <div className="text-xs mt-1" style={{ color: C.textTert }}>
            Backend connectivity issue — check <code>/v1/follow-up-center</code>.
          </div>
          <button
            onClick={load}
            className="mt-3 text-xs px-3 py-1.5 rounded"
            style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.textSec }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && items.length === 0 && (
        <div
          className="rounded-lg px-4 py-10 text-center"
          style={{ background: C.surface, border: `1px solid ${C.border}` }}
        >
          <CheckCircle size={28} className="mx-auto mb-3 opacity-30" style={{ color: C.success }} />
          <div className="text-sm font-medium" style={{ color: C.textSec }}>
            No follow-ups
          </div>
          <div className="text-xs mt-1" style={{ color: C.textTert }}>
            {(sourceFilter || statusFilter)
              ? 'No items match the current filter.'
              : 'No pending follow-ups found across tasks and goals.'}
          </div>
          {(sourceFilter || statusFilter) && (
            <button
              onClick={() => { setSourceFilter(''); setStatusFilter(''); }}
              className="mt-3 text-xs px-3 py-1.5 rounded"
              style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.textSec }}
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* Items list */}
      {!loading && !error && items.length > 0 && (
        <div>
          <div className="text-xs mb-3" style={{ color: C.textTert }}>
            {items.length} item{items.length !== 1 ? 's' : ''}
            {(sourceFilter || statusFilter) && ' (filtered)'}
          </div>
          {items.map((item) => (
            <FollowUpRow
              key={item.item_id}
              item={item}
              onComplete={handleComplete}
              onSnooze={handleSnooze}
              completing={completing === item.source_id}
              snoozing={snoozing === item.source_id}
            />
          ))}
        </div>
      )}

      {/* Provenance footer */}
      <div
        className="mt-6 flex items-center gap-2 text-xs px-3 py-2 rounded"
        style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.textTert }}
      >
        <Calendar size={12} />
        <span>Data from <code>/v1/follow-up-center</code> — local stores only.</span>
        <span className="ml-2">
          No connector credentials required.
        </span>
        {data && !data.fake_data && (
          <span className="ml-auto" style={{ color: C.success }}>
            ✓ Honest data
          </span>
        )}
      </div>
    </div>
  );
}
