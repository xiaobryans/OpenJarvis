import { useState, useEffect } from 'react';
import { Target, XCircle, AlertTriangle, ChevronDown, ChevronRight, Shield, Play, PauseCircle } from 'lucide-react';
import {
  fetchLongHorizonGoals,
  fetchLongHorizonSummary,
  type LongHorizonGoal,
  type LongHorizonGoalsResponse,
  type LongHorizonSummary,
} from '../lib/jarvis-api';

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    active:    { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    paused:    { bg: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' },
    completed: { bg: 'color-mix(in srgb, var(--color-info, #89dceb) 15%, transparent)', color: 'var(--color-info, #89dceb)' },
    abandoned: { bg: 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)', color: 'var(--color-danger, #f38ba8)' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

function HorizonBadge({ horizon }: { horizon: string }) {
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}>
      {horizon}
    </span>
  );
}

function GoalCard({ goal }: { goal: LongHorizonGoal }) {
  const [expanded, setExpanded] = useState(false);
  const milestonePct = goal.milestones_total > 0
    ? Math.round((goal.milestones_completed / goal.milestones_total) * 100)
    : 0;

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      {/* Header row */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full px-4 py-4 flex items-start gap-3 text-left cursor-pointer"
        style={{ background: 'transparent' }}
      >
        <span className="mt-0.5 shrink-0" style={{ color: 'var(--color-text-tertiary)' }}>
          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </span>
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{goal.title}</span>
            <StatusChip status={goal.status} />
            <HorizonBadge horizon={goal.horizon} />
            {goal.has_continuation_state && (
              <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ color: 'var(--color-info, #89dceb)', border: '1px solid var(--color-info, #89dceb)', opacity: 0.8 }}>
                continuable
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-3 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            <span>Milestones: {goal.milestones_completed}/{goal.milestones_total} ({milestonePct}%)</span>
            {goal.next_actions_pending > 0 && <span>{goal.next_actions_pending} actions pending</span>}
            {goal.follow_up_count > 0 && <span>{goal.follow_up_count} follow-ups</span>}
          </div>
          {/* Milestone progress bar */}
          {goal.milestones_total > 0 && (
            <div className="h-1 rounded-full overflow-hidden w-full" style={{ background: 'var(--color-bg-tertiary)' }}>
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${milestonePct}%`, background: 'var(--color-accent)' }}
              />
            </div>
          )}
        </div>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div
          className="px-4 pb-4 pt-0 grid grid-cols-1 sm:grid-cols-2 gap-4"
          style={{ borderTop: '1px solid var(--color-border)' }}
        >
          <div className="space-y-2 pt-3">
            <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>{goal.description}</p>
            {goal.execution_honesty && (
              <p className="text-xs italic" style={{ color: 'var(--color-text-tertiary)' }}>{goal.execution_honesty}</p>
            )}
          </div>
          <div className="space-y-2 pt-3">
            <div className="flex flex-col gap-1.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {goal.approval_required_for_actions && (
                <div className="flex items-center gap-1.5">
                  <Shield size={11} style={{ color: 'var(--color-warning, #f9e2af)' }} />
                  <span>Approval required for all actions</span>
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <Play size={11} style={{ color: goal.has_continuation_state ? 'var(--color-success, #a6e3a1)' : 'var(--color-text-tertiary)' }} />
                <span>Can resume: {goal.has_continuation_state ? 'yes' : 'no'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <PauseCircle size={11} style={{ color: 'var(--color-text-tertiary)' }} />
                <span>Status: {goal.status}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function LongHorizonGoalsPage() {
  const [goalsData, setGoalsData] = useState<LongHorizonGoalsResponse | null>(null);
  const [summary, setSummary] = useState<LongHorizonSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([fetchLongHorizonGoals(), fetchLongHorizonSummary()])
      .then(([g, s]) => {
        setGoalsData(g);
        setSummary(s);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load long-horizon goals'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading long-horizon goals...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <XCircle size={32} className="mx-auto mb-2" style={{ color: 'var(--color-danger, #f38ba8)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{error}</p>
        </div>
      </div>
    );
  }

  const goals = goalsData?.goals ?? [];
  const stats = [
    { label: 'Total', value: summary?.total_goals ?? goals.length },
    { label: 'Active', value: summary?.active ?? goalsData?.active_count ?? 0, color: 'var(--color-success, #a6e3a1)' },
    { label: 'Paused', value: summary?.paused ?? goalsData?.paused_count ?? 0, color: 'var(--color-warning, #f9e2af)' },
    { label: 'Completed', value: summary?.completed ?? goalsData?.completed_count ?? 0, color: 'var(--color-info, #89dceb)' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Target size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Long-Horizon Goals</h1>
      </div>

      {/* Honesty banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-warning, #f9e2af) 20%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          All execution requires explicit approval. No autonomous goal execution.
        </p>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map(({ label, value, color }) => (
          <div
            key={label}
            className="rounded-xl px-4 py-3 flex flex-col gap-1"
            style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
          >
            <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
            <span className="text-2xl font-semibold" style={{ color: color ?? 'var(--color-text)' }}>{value}</span>
          </div>
        ))}
      </div>

      {/* Goals list */}
      {goals.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Target size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No long-horizon goals found.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {goals.map((goal) => (
            <GoalCard key={goal.goal_id} goal={goal} />
          ))}
        </div>
      )}
    </div>
  );
}
