/**
 * Plan 4-6 — Command Center Page
 *
 * Route: /command-center
 * Unified Task / Goal / Project OS view.
 *
 * All data from real /v1/command-center/* routes.
 * No fake data. Loading, error, and empty states required.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Shield,
  Tag,
  Clock,
  ListTodo,
  Target,
  FolderOpen,
  LayoutDashboard,
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
};

// ---------------------------------------------------------------------------
// API types
// ---------------------------------------------------------------------------

interface CommandItem {
  item_id: string;
  source: string;
  source_id: string;
  title: string;
  description?: string;
  status: string;
  priority?: string;
  tags?: string[];
  approval_required?: boolean;
  due_at?: string | null;
  source_route?: string;
  // Goal-specific
  pending_milestones?: number;
  pending_actions?: number;
  follow_up_count?: number;
}

interface CommandCenterResponse {
  items: CommandItem[];
  count: number;
  by_source: Record<string, number>;
  by_status: Record<string, number>;
  sources_probed: string[];
  fake_data?: boolean;
}

interface CommandCenterSummary {
  tasks: { total: number; pending: number; in_progress: number; waiting_approval: number };
  goals: { total: number; active: number; paused: number };
  projects: { total: number; active: number };
  grand_total: number;
  fake_data?: boolean;
}

// ---------------------------------------------------------------------------
// Source config helpers
// ---------------------------------------------------------------------------

function sourceConfig(source: string): { label: string; bg: string; color: string; icon: React.ReactNode } {
  if (source === 'task' || source === 'tasks')
    return { label: 'Task', bg: 'rgba(137,220,235,0.10)', color: C.info, icon: <ListTodo size={12} /> };
  if (source === 'goal' || source === 'goals')
    return { label: 'Goal', bg: 'rgba(166,227,161,0.10)', color: C.success, icon: <Target size={12} /> };
  if (source === 'project' || source === 'projects')
    return {
      label: 'Project',
      bg: 'rgba(203,166,247,0.10)',
      color: 'var(--color-mauve, #cba6f7)',
      icon: <FolderOpen size={12} />,
    };
  return { label: source, bg: C.surfaceAlt, color: C.textSec, icon: <ListTodo size={12} /> };
}

function statusConfig(status: string): { label: string; color: string; bg: string } {
  const s = status.toLowerCase();
  if (s === 'in_progress' || s === 'active')
    return { label: s === 'in_progress' ? 'In Progress' : 'Active', color: C.info, bg: 'rgba(137,220,235,0.10)' };
  if (s === 'waiting_approval' || s === 'pending_approval')
    return { label: 'Waiting Approval', color: C.warning, bg: 'rgba(249,226,175,0.10)' };
  if (s === 'done' || s === 'completed')
    return { label: 'Done', color: C.success, bg: 'rgba(166,227,161,0.10)' };
  if (s === 'blocked' || s === 'failed')
    return { label: s.charAt(0).toUpperCase() + s.slice(1), color: C.danger, bg: 'rgba(243,139,168,0.10)' };
  if (s === 'paused')
    return { label: 'Paused', color: C.warning, bg: 'rgba(249,226,175,0.08)' };
  // pending / default
  return { label: s.charAt(0).toUpperCase() + s.slice(1), color: C.textSec, bg: C.surfaceAlt };
}

function priorityConfig(priority: string): { color: string } {
  const p = priority.toLowerCase();
  if (p === 'critical' || p === 'urgent') return { color: C.danger };
  if (p === 'high') return { color: C.warning };
  if (p === 'low') return { color: C.textTert };
  return { color: C.textSec };
}

// ---------------------------------------------------------------------------
// Stats strip
// ---------------------------------------------------------------------------

function StatsStrip({ summary }: { summary: CommandCenterSummary }) {
  const cells = [
    { label: 'Tasks', value: summary.tasks.total, color: C.info },
    { label: 'Goals', value: summary.goals.total, color: C.success },
    { label: 'Projects', value: summary.projects.total, color: 'var(--color-mauve, #cba6f7)' },
    { label: 'Total', value: summary.grand_total, color: C.text },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
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
// Item card
// ---------------------------------------------------------------------------

function ItemCard({ item }: { item: CommandItem }) {
  const [expanded, setExpanded] = useState(false);
  const src = sourceConfig(item.source);
  const st = statusConfig(item.status);

  return (
    <div
      className="rounded-lg mb-2 overflow-hidden transition-all"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <button
        className="flex items-start gap-3 w-full px-4 py-3 text-left"
        onClick={() => setExpanded(!expanded)}
        style={{ color: C.text }}
      >
        {/* Expand toggle */}
        <span className="mt-0.5 shrink-0" style={{ color: C.textTert }}>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>

        <div className="flex-1 min-w-0">
          {/* Title row */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Source badge */}
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono"
              style={{ background: src.bg, color: src.color }}
            >
              {src.icon}
              {src.label}
            </span>

            {/* Status chip */}
            <span
              className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono"
              style={{ background: st.bg, color: st.color }}
            >
              {st.label}
            </span>

            {/* Priority */}
            {item.priority && (
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                style={{ background: C.surfaceAlt, color: priorityConfig(item.priority).color }}
              >
                p:{item.priority}
              </span>
            )}

            {/* Approval shield */}
            {item.approval_required && (
              <span
                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px]"
                style={{ background: 'rgba(249,226,175,0.10)', color: C.warning }}
                title="Approval required"
              >
                <Shield size={10} /> approval
              </span>
            )}
          </div>

          {/* Title */}
          <div className="font-medium text-sm mt-1 truncate" style={{ color: C.text }}>
            {item.title}
          </div>

          {/* Description */}
          {item.description && (
            <div className="text-xs mt-0.5 line-clamp-2" style={{ color: C.textSec }}>
              {item.description}
            </div>
          )}

          {/* Due date */}
          {item.due_at && (
            <div className="flex items-center gap-1 text-xs mt-1" style={{ color: C.warning }}>
              <Clock size={10} /> Due: {String(item.due_at)}
            </div>
          )}

          {/* Tags */}
          {item.tags && item.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {item.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px]"
                  style={{ background: C.surfaceAlt, color: C.textTert, border: `1px solid ${C.border}` }}
                >
                  <Tag size={9} />
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div
          className="px-4 pb-4 pt-3 text-xs"
          style={{ borderTop: `1px solid ${C.border}`, color: C.textSec }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
            <div>
              <span style={{ color: C.textTert }}>item_id: </span>
              <span style={{ fontFamily: 'monospace' }}>{item.item_id}</span>
            </div>
            <div>
              <span style={{ color: C.textTert }}>source: </span>{item.source}
            </div>
            <div>
              <span style={{ color: C.textTert }}>status: </span>{item.status}
            </div>
            {item.source_id && (
              <div>
                <span style={{ color: C.textTert }}>source_id: </span>
                <span style={{ fontFamily: 'monospace' }}>{item.source_id}</span>
              </div>
            )}
            {item.source_route && (
              <div className="col-span-1 sm:col-span-2">
                <span style={{ color: C.textTert }}>route: </span>
                <code style={{ fontFamily: 'monospace', color: C.textTert }}>{item.source_route}</code>
              </div>
            )}
            {/* Goal-specific fields */}
            {item.pending_milestones !== undefined && (
              <div>
                <span style={{ color: C.textTert }}>pending milestones: </span>{item.pending_milestones}
              </div>
            )}
            {item.pending_actions !== undefined && (
              <div>
                <span style={{ color: C.textTert }}>pending actions: </span>{item.pending_actions}
              </div>
            )}
            {item.follow_up_count !== undefined && (
              <div>
                <span style={{ color: C.textTert }}>follow-ups: </span>{item.follow_up_count}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter button helper
// ---------------------------------------------------------------------------

function FilterBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded text-xs cursor-pointer transition-colors"
      style={{
        background: active
          ? 'color-mix(in srgb, var(--color-accent) 15%, var(--color-bg-tertiary))'
          : C.surface,
        color: active ? C.accent : C.textSec,
        border: active
          ? `1px solid color-mix(in srgb, var(--color-accent) 30%, var(--color-border))`
          : `1px solid ${C.border}`,
      }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type SourceFilter = 'all' | 'tasks' | 'goals' | 'projects';
type StatusFilter = 'all' | 'pending' | 'in_progress' | 'waiting_approval';

export function CommandCenterPage() {
  const [items, setItems] = useState<CommandItem[]>([]);
  const [summary, setSummary] = useState<CommandCenterSummary | null>(null);
  const [sourcesProbed, setSourcesProbed] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [itemsRes, summaryRes] = await Promise.all([
        apiFetch('/v1/command-center'),
        apiFetch('/v1/command-center/summary'),
      ]);

      if (!itemsRes.ok) throw new Error(`Command center items failed: ${itemsRes.status}`);
      if (!summaryRes.ok) throw new Error(`Command center summary failed: ${summaryRes.status}`);

      const itemsData: CommandCenterResponse = await itemsRes.json();
      const summaryData: CommandCenterSummary = await summaryRes.json();

      setItems(itemsData.items ?? []);
      setSourcesProbed(itemsData.sources_probed ?? []);
      setSummary(summaryData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load Command Center');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Apply filters
  const filtered = items.filter((item) => {
    const srcMatch =
      sourceFilter === 'all' ||
      item.source === sourceFilter ||
      item.source === sourceFilter.replace(/s$/, ''); // tasks→task, goals→goal, projects→project
    const stMatch =
      statusFilter === 'all' ||
      item.status === statusFilter ||
      (statusFilter === 'in_progress' && item.status === 'active');
    return srcMatch && stMatch;
  });

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <LayoutDashboard size={18} style={{ color: C.accent }} />
              <h1 className="text-lg font-semibold" style={{ color: C.text }}>
                Command Center
              </h1>
            </div>
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
            Tasks, Goals, and Projects — unified OS view. All data from{' '}
            <code style={{ fontFamily: 'monospace', fontSize: 11, color: C.textTert }}>
              /v1/command-center
            </code>.
          </p>
        </header>

        {/* Stats strip */}
        {summary && <StatsStrip summary={summary} />}

        {/* Error */}
        {error && (
          <div
            className="rounded-lg px-4 py-3 mb-4 flex items-center gap-2 text-sm"
            style={{ background: 'rgba(243,139,168,0.1)', color: C.danger, border: `1px solid rgba(243,139,168,0.2)` }}
          >
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-sm text-center py-12" style={{ color: C.textTert }}>
            Loading command center…
          </div>
        )}

        {!loading && !error && (
          <>
            {/* Source filter */}
            <div className="mb-3">
              <div className="text-xs mb-2" style={{ color: C.textTert }}>Source</div>
              <div className="flex flex-wrap gap-2">
                {(['all', 'tasks', 'goals', 'projects'] as SourceFilter[]).map((f) => (
                  <FilterBtn key={f} active={sourceFilter === f} onClick={() => setSourceFilter(f)}>
                    {f === 'all' ? 'All Sources' : f.charAt(0).toUpperCase() + f.slice(1)}
                  </FilterBtn>
                ))}
              </div>
            </div>

            {/* Status filter */}
            <div className="mb-5">
              <div className="text-xs mb-2" style={{ color: C.textTert }}>Status</div>
              <div className="flex flex-wrap gap-2">
                {(['all', 'pending', 'in_progress', 'waiting_approval'] as StatusFilter[]).map((f) => (
                  <FilterBtn key={f} active={statusFilter === f} onClick={() => setStatusFilter(f)}>
                    {f === 'all'
                      ? 'All Statuses'
                      : f === 'in_progress'
                      ? 'In Progress'
                      : f === 'waiting_approval'
                      ? 'Waiting Approval'
                      : f.charAt(0).toUpperCase() + f.slice(1)}
                  </FilterBtn>
                ))}
              </div>
            </div>

            {/* Count line */}
            <div className="text-xs mb-3" style={{ color: C.textTert }}>
              Showing {filtered.length} of {items.length} item{items.length !== 1 ? 's' : ''}
            </div>

            {/* Empty state */}
            {filtered.length === 0 ? (
              <div
                className="rounded-lg px-4 py-12 text-center"
                style={{ background: C.surface, border: `1px solid ${C.border}` }}
              >
                <LayoutDashboard size={28} className="mx-auto mb-3 opacity-30" style={{ color: C.textTert }} />
                <div className="text-sm font-medium" style={{ color: C.text }}>
                  No active items
                </div>
                <div className="text-xs mt-1" style={{ color: C.textTert }}>
                  {items.length > 0
                    ? 'No items match the current filters. Try changing source or status filter.'
                    : 'No tasks, goals, or projects found. Items appear here once they are created.'}
                </div>
              </div>
            ) : (
              <div>
                {filtered.map((item) => (
                  <ItemCard key={item.item_id} item={item} />
                ))}
              </div>
            )}

            {/* Provenance footer */}
            {sourcesProbed.length > 0 && (
              <div
                className="mt-6 px-4 py-3 rounded-lg text-xs"
                style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.textTert }}
              >
                <span>Sources probed: </span>
                <span>{sourcesProbed.join(' · ')}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
