/**
 * Plan 4-6 — Rules Manager Page
 *
 * Route: /rules
 * Lists all rules in the engine, shows active/inactive/conflicted status,
 * allows create/activate/deactivate/delete, and can evaluate a context.
 *
 * All data from real /v1/rules/* routes.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Plus,
  PlayCircle,
  PauseCircle,
  Trash2,
  ChevronDown,
  ChevronUp,
  Zap,
  Info,
} from 'lucide-react';
import type { Rule, RulesStats } from '../lib/jarvis-api';
import {
  fetchRules,
  activateRule,
  deactivateRule,
  deleteRule,
  createRule,
  evaluateRules,
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
// Small helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  let bg = 'rgba(166,227,161,0.12)';
  let color = C.success;
  let icon = <CheckCircle size={11} />;

  if (status === 'inactive') {
    bg = 'rgba(166,173,200,0.1)';
    color = C.textSec;
    icon = <PauseCircle size={11} />;
  } else if (status === 'conflicted') {
    bg = 'rgba(243,139,168,0.12)';
    color = C.error;
    icon = <AlertTriangle size={11} />;
  } else if (status === 'draft') {
    bg = 'rgba(249,226,175,0.1)';
    color = C.warning;
    icon = <Info size={11} />;
  }

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono"
      style={{ background: bg, color }}
    >
      {icon}
      {status}
    </span>
  );
}

function SafetyBadge({ level }: { level: string }) {
  const safe = level === 'safe';
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono"
      style={{
        background: safe ? 'rgba(166,227,161,0.1)' : 'rgba(249,226,175,0.1)',
        color: safe ? C.success : C.warning,
      }}
    >
      {level}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Stats strip
// ---------------------------------------------------------------------------

function StatsStrip({ stats }: { stats: RulesStats }) {
  const cells = [
    { label: 'Total', value: stats.total, color: C.text },
    { label: 'Active', value: stats.active, color: C.success },
    { label: 'Inactive', value: stats.inactive, color: C.textSec },
    { label: 'Conflicted', value: stats.conflicted, color: C.error },
    { label: 'Draft', value: stats.draft, color: C.warning },
  ];
  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-6">
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
// Rule row
// ---------------------------------------------------------------------------

function RuleRow({
  rule,
  onActivate,
  onDeactivate,
  onDelete,
}: {
  rule: Rule;
  onActivate: (id: string) => void;
  onDeactivate: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="rounded-lg mb-2 overflow-hidden"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex-1 flex items-start gap-3 text-left"
          style={{ color: C.text }}
        >
          <span className="mt-0.5">
            {expanded ? <ChevronUp size={14} style={{ color: C.textTert }} /> : <ChevronDown size={14} style={{ color: C.textTert }} />}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm">{rule.name}</span>
              <StatusBadge status={rule.status} />
              <SafetyBadge level={rule.safety_level} />
              {rule.conflict_ids.length > 0 && (
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  style={{ background: 'rgba(243,139,168,0.12)', color: C.error }}
                >
                  {rule.conflict_ids.length} conflict{rule.conflict_ids.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            <div className="text-xs mt-0.5 truncate" style={{ color: C.textSec }}>
              {rule.description || 'No description'}
            </div>
          </div>
        </button>

        <div className="flex items-center gap-1 shrink-0">
          {rule.status !== 'active' && (
            <button
              disabled={busy}
              onClick={() => act(() => onActivate(rule.rule_id) as unknown as Promise<unknown>)}
              className="p-1.5 rounded transition-colors cursor-pointer disabled:opacity-50"
              style={{ color: C.success }}
              title="Activate"
              onMouseEnter={(e) => (e.currentTarget.style.background = C.surfaceAlt)}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <PlayCircle size={15} />
            </button>
          )}
          {rule.status === 'active' && (
            <button
              disabled={busy}
              onClick={() => act(() => onDeactivate(rule.rule_id) as unknown as Promise<unknown>)}
              className="p-1.5 rounded transition-colors cursor-pointer disabled:opacity-50"
              style={{ color: C.textSec }}
              title="Deactivate"
              onMouseEnter={(e) => (e.currentTarget.style.background = C.surfaceAlt)}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <PauseCircle size={15} />
            </button>
          )}
          <button
            disabled={busy}
            onClick={() => act(() => onDelete(rule.rule_id) as unknown as Promise<unknown>)}
            className="p-1.5 rounded transition-colors cursor-pointer disabled:opacity-50"
            style={{ color: C.error }}
            title="Delete"
            onMouseEnter={(e) => (e.currentTarget.style.background = C.surfaceAlt)}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      {expanded && (
        <div
          className="px-4 py-3 text-xs grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5"
          style={{ borderTop: `1px solid ${C.border}`, color: C.textSec }}
        >
          <div><span style={{ color: C.textTert }}>rule_id: </span>{rule.rule_id}</div>
          <div><span style={{ color: C.textTert }}>type: </span>{rule.rule_type}</div>
          <div><span style={{ color: C.textTert }}>scope: </span>{rule.scope}/{rule.scope_id || 'global'}</div>
          <div><span style={{ color: C.textTert }}>priority: </span>{rule.priority}</div>
          <div><span style={{ color: C.textTert }}>source: </span>{rule.source}</div>
          {rule.tags.length > 0 && (
            <div className="col-span-1 sm:col-span-2">
              <span style={{ color: C.textTert }}>tags: </span>
              {rule.tags.join(', ')}
            </div>
          )}
          {rule.conflict_ids.length > 0 && (
            <div className="col-span-1 sm:col-span-2">
              <span style={{ color: C.error }}>conflicts: </span>
              {rule.conflict_ids.join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create rule form
// ---------------------------------------------------------------------------

function CreateRuleForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [ruleType, setRuleType] = useState('behavior');
  const [scope, setScope] = useState('global');
  const [priority, setPriority] = useState(50);
  const [effect, setEffect] = useState('allow');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [warn, setWarn] = useState('');

  const handleSubmit = async () => {
    if (!name.trim()) { setErr('Name is required'); return; }
    setBusy(true);
    setErr('');
    setWarn('');
    try {
      const res = await createRule({
        name: name.trim(),
        description: desc.trim() || undefined,
        rule_type: ruleType,
        scope,
        priority,
        action: { effect },
      });
      if (res.warning) setWarn(res.warning);
      setName(''); setDesc('');
      setOpen(false);
      onCreated();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to create rule');
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors cursor-pointer"
        style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.text }}
        onMouseEnter={(e) => (e.currentTarget.style.background = C.surfaceAlt)}
        onMouseLeave={(e) => (e.currentTarget.style.background = C.surface)}
      >
        <Plus size={14} style={{ color: C.accent }} />
        New rule
      </button>
    );
  }

  return (
    <div
      className="rounded-lg p-4 mb-4"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <div className="text-sm font-medium mb-3" style={{ color: C.text }}>New Rule</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="col-span-1 sm:col-span-2">
          <label className="text-xs mb-1 block" style={{ color: C.textTert }}>Name *</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-1.5 rounded text-sm outline-none"
            style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
            placeholder="e.g. Block external API calls"
          />
        </div>
        <div className="col-span-1 sm:col-span-2">
          <label className="text-xs mb-1 block" style={{ color: C.textTert }}>Description</label>
          <input
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            className="w-full px-3 py-1.5 rounded text-sm outline-none"
            style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
            placeholder="Optional description"
          />
        </div>
        <div>
          <label className="text-xs mb-1 block" style={{ color: C.textTert }}>Rule type</label>
          <select
            value={ruleType}
            onChange={(e) => setRuleType(e.target.value)}
            className="w-full px-3 py-1.5 rounded text-sm outline-none"
            style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
          >
            {['behavior','safety','privacy','compliance','connector','skill','ui','memory'].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs mb-1 block" style={{ color: C.textTert }}>Scope</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="w-full px-3 py-1.5 rounded text-sm outline-none"
            style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
          >
            {['global','project','user','session','connector','skill'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs mb-1 block" style={{ color: C.textTert }}>Priority (0–100)</label>
          <input
            type="number"
            min={0}
            max={100}
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            className="w-full px-3 py-1.5 rounded text-sm outline-none"
            style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
          />
        </div>
        <div>
          <label className="text-xs mb-1 block" style={{ color: C.textTert }}>Effect</label>
          <select
            value={effect}
            onChange={(e) => setEffect(e.target.value)}
            className="w-full px-3 py-1.5 rounded text-sm outline-none"
            style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
          >
            {['allow','block','enable','disable','require','override'].map((e) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
        </div>
      </div>

      {err && (
        <div className="mt-2 text-xs flex items-center gap-1" style={{ color: C.error }}>
          <XCircle size={12} />{err}
        </div>
      )}
      {warn && (
        <div className="mt-2 text-xs flex items-center gap-1" style={{ color: C.warning }}>
          <AlertTriangle size={12} />{warn}
        </div>
      )}

      <div className="flex gap-2 mt-4">
        <button
          onClick={handleSubmit}
          disabled={busy}
          className="px-4 py-1.5 rounded text-sm cursor-pointer disabled:opacity-50"
          style={{ background: C.accent, color: '#1e1e2e' }}
        >
          {busy ? 'Creating…' : 'Create'}
        </button>
        <button
          onClick={() => { setOpen(false); setErr(''); setWarn(''); }}
          className="px-4 py-1.5 rounded text-sm cursor-pointer"
          style={{ background: C.surfaceAlt, color: C.textSec, border: `1px solid ${C.border}` }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evaluate panel
// ---------------------------------------------------------------------------

function EvaluatePanel() {
  const [open, setOpen] = useState(false);
  const [actionType, setActionType] = useState('');
  const [result, setResult] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const handleEval = async () => {
    setBusy(true);
    setErr('');
    try {
      const res = await evaluateRules({ action_type: actionType || undefined });
      setResult(res.evaluation);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Evaluation failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="rounded-lg overflow-hidden mb-6"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <button
        className="flex items-center gap-2 w-full px-4 py-3 text-sm text-left cursor-pointer"
        style={{ color: C.text }}
        onClick={() => setOpen(!open)}
      >
        <Zap size={14} style={{ color: C.accent }} />
        Evaluate rules context
        {open ? <ChevronUp size={14} className="ml-auto" style={{ color: C.textTert }} /> : <ChevronDown size={14} className="ml-auto" style={{ color: C.textTert }} />}
      </button>
      {open && (
        <div className="px-4 pb-4" style={{ borderTop: `1px solid ${C.border}` }}>
          <div className="mt-3 flex gap-2">
            <input
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              placeholder="action_type (optional, e.g. 'coding')"
              className="flex-1 px-3 py-1.5 rounded text-sm outline-none"
              style={{ background: C.surfaceAlt, border: `1px solid ${C.border}`, color: C.text }}
            />
            <button
              onClick={handleEval}
              disabled={busy}
              className="px-4 py-1.5 rounded text-sm cursor-pointer disabled:opacity-50"
              style={{ background: C.accent, color: '#1e1e2e' }}
            >
              {busy ? 'Running…' : 'Evaluate'}
            </button>
          </div>
          {err && <div className="mt-2 text-xs" style={{ color: C.error }}>{err}</div>}
          {result !== null && (
            <pre
              className="mt-3 text-xs p-3 rounded overflow-auto max-h-48"
              style={{ background: C.surfaceAlt, color: C.textSec, border: `1px solid ${C.border}` }}
            >
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function RulesManagerPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [stats, setStats] = useState<RulesStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchRules(statusFilter ? { status: statusFilter } : undefined);
      setRules(res.rules);
      setStats(res.stats);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load rules');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleActivate = async (id: string) => {
    await activateRule(id);
    load();
  };
  const handleDeactivate = async (id: string) => {
    await deactivateRule(id);
    load();
  };
  const handleDelete = async (id: string) => {
    await deleteRule(id);
    load();
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold" style={{ color: C.text }}>
              Rules Manager
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
            Live rules engine — active/inactive status, conflict detection, priority-ordered evaluation.
            All data from{' '}
            <code style={{ fontFamily: 'monospace', fontSize: 11, color: C.textTert }}>/v1/rules/*</code>.
          </p>
        </header>

        {/* Stats */}
        {stats && <StatsStrip stats={stats} />}

        {/* Evaluate */}
        <EvaluatePanel />

        {/* Filter + create */}
        <div className="flex items-center gap-3 mb-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 rounded text-sm outline-none"
            style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.textSec }}
          >
            <option value="">All statuses</option>
            {['active','inactive','conflicted','draft'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <CreateRuleForm onCreated={load} />
        </div>

        {/* Error */}
        {error && (
          <div
            className="rounded-lg px-4 py-3 mb-4 flex items-center gap-2 text-sm"
            style={{ background: 'rgba(243,139,168,0.1)', color: C.error, border: `1px solid rgba(243,139,168,0.2)` }}
          >
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-sm text-center py-12" style={{ color: C.textTert }}>
            Loading rules…
          </div>
        )}

        {/* Empty */}
        {!loading && !error && rules.length === 0 && (
          <div
            className="rounded-lg px-4 py-10 text-center"
            style={{ background: C.surface, border: `1px solid ${C.border}` }}
          >
            <div className="text-sm" style={{ color: C.textTert }}>No rules found. Create your first rule above.</div>
          </div>
        )}

        {/* Rules list */}
        {!loading && rules.map((rule) => (
          <RuleRow
            key={rule.rule_id}
            rule={rule}
            onActivate={handleActivate}
            onDeactivate={handleDeactivate}
            onDelete={handleDelete}
          />
        ))}
      </div>
    </div>
  );
}
