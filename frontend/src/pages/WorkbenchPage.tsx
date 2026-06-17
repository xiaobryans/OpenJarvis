import { useState, useCallback, useEffect, useRef } from 'react';
import {
  Code2,
  Play,
  RotateCcw,
  GitBranch,
  GitCommit,
  Send,
  FileSearch,
  Terminal,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  ChevronRight,
  ChevronDown,
  DollarSign,
  Shield,
  Eye,
  EyeOff,
  Layers,
  Cpu,
  Zap,
  X,
  RefreshCw,
  Lock,
  Unlock,
} from 'lucide-react';
import { apiFetch } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Subtask {
  id: string;
  index: number;
  description: string;
  tool_id: string;
  params: Record<string, unknown>;
  worker_tier: string;
  requires_approval: boolean;
  status: string;
  output?: string;
  error?: string;
  cost_usd: number;
  job_id?: string;
  started_at?: number;
  finished_at?: number;
}

interface TaskPlan {
  session_id: string;
  task_id: string;
  prompt: string;
  repo_path: string;
  subtasks: Subtask[];
  dry_run: boolean;
  stop_on_blocker: boolean;
  status: string;
  task_type?: string;
  final_report?: string;
  diff_preview?: string;
  validation_output?: string;
  likely_files?: string[];
  risks?: string[];
  validation_commands?: string[];
  approval_gates?: string[];
  created_at: number;
  finished_at?: number;
  total_cost_usd: number;
}

interface RepoStatus {
  ok: boolean;
  repo_path: string;
  status: string;
  branch: string;
  recent_commits: string;
}

interface DoctorCheck {
  check: string;
  status: string;
  evidence: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function describeNetworkError(e: unknown): string {
  const msg = String(e);
  if (
    msg.includes('Load failed') ||
    msg.includes('Failed to fetch') ||
    msg.includes('NetworkError') ||
    msg.includes('network error')
  ) {
    return (
      'Network/timeout error: The backend request failed. This may be caused by a ' +
      'search scanning a large directory. Check /v1/system/health and try a more ' +
      'specific prompt or a narrower repo path. (' + msg + ')'
    );
  }
  return msg;
}

const TASK_TYPE_COLORS: Record<string, string> = {
  tiny_marker: 'text-gray-400',
  documentation: 'text-blue-400',
  bug_fix: 'text-orange-400',
  complex_implementation: 'text-purple-400',
  planning_only: 'text-cyan-400',
  research: 'text-teal-400',
};

const TASK_TYPE_LABELS: Record<string, string> = {
  tiny_marker: 'Tiny Task',
  documentation: 'Documentation',
  bug_fix: 'Bug Fix',
  complex_implementation: 'Complex Implementation',
  planning_only: 'Planning Only',
  research: 'Research',
};

const TIER_COLORS: Record<string, string> = {
  local: 'text-green-400',
  'cloud-cheap': 'text-yellow-400',
  'high-trust': 'text-red-400',
};

const TIER_LABELS: Record<string, string> = {
  local: 'Local',
  'cloud-cheap': 'Cheap',
  'high-trust': 'High-Trust',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  done: <CheckCircle2 size={14} className="text-green-400" />,
  failed: <X size={14} className="text-red-400" />,
  running: <Loader2 size={14} className="text-blue-400 animate-spin" />,
  pending: <Clock size={14} className="text-gray-400" />,
  skipped_dry_run: <EyeOff size={14} className="text-gray-500" />,
  awaiting_approval: <Lock size={14} className="text-yellow-400" />,
};

function statusIcon(status: string) {
  return STATUS_ICONS[status] ?? <Clock size={14} className="text-gray-400" />;
}

function formatCost(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.001) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RepoStatusPanel({ repoPath }: { repoPath: string }) {
  const [status, setStatus] = useState<RepoStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    if (!repoPath) return;
    setLoading(true);
    apiFetch(`/v1/workbench/repo/status?repo_path=${encodeURIComponent(repoPath)}`)
      .then((r) => r.json())
      .then((d) => setStatus(d))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, [repoPath]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="rounded-lg border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
          <GitBranch size={14} />
          Repo Status
        </div>
        <button onClick={refresh} className="p-1 rounded hover:opacity-70 cursor-pointer" style={{ color: 'var(--color-text-secondary)' }}>
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
        </button>
      </div>
      {status ? (
        <div className="space-y-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          <div className="flex gap-2">
            <span className="text-blue-400 font-mono">{status.branch || '(no branch)'}</span>
            <span className="text-gray-500">{status.repo_path}</span>
          </div>
          {status.status && (
            <pre className="font-mono text-xs overflow-auto max-h-20 p-1 rounded" style={{ background: 'var(--color-bg-tertiary)' }}>
              {status.status.trim() || 'clean'}
            </pre>
          )}
          {status.recent_commits && (
            <pre className="font-mono text-xs overflow-auto max-h-20 p-1 rounded" style={{ background: 'var(--color-bg-tertiary)' }}>
              {status.recent_commits.trim()}
            </pre>
          )}
        </div>
      ) : (
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {loading ? 'Loading…' : 'No repo status (check repo path)'}
        </p>
      )}
    </div>
  );
}

function SubtaskRow({ subtask, onApprove, sessionId }: {
  subtask: Subtask;
  onApprove?: (subtaskId: string) => void;
  sessionId: string;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded border text-xs" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div
        className="flex items-center gap-2 p-2 cursor-pointer hover:opacity-80"
        onClick={() => setExpanded((e) => !e)}
      >
        <span>{statusIcon(subtask.status)}</span>
        <span className="font-mono text-gray-500 w-5 text-right shrink-0">[{subtask.index}]</span>
        <span className="flex-1 truncate" style={{ color: 'var(--color-text-primary)' }}>{subtask.description}</span>
        <span className={`font-mono text-xs px-1 rounded ${TIER_COLORS[subtask.worker_tier] ?? 'text-gray-400'}`}>
          {TIER_LABELS[subtask.worker_tier] ?? subtask.worker_tier}
        </span>
        <span className="font-mono text-gray-500">{formatCost(subtask.cost_usd)}</span>
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </div>
      {expanded && (
        <div className="px-3 pb-2 space-y-1 border-t" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex gap-4 mt-1 text-gray-500">
            <span>Tool: <code className="text-blue-400">{subtask.tool_id}</code></span>
            <span>Status: <code>{subtask.status}</code></span>
            {subtask.requires_approval && (
              <span className="flex items-center gap-1 text-yellow-400"><Shield size={10} />Requires approval</span>
            )}
          </div>
          {subtask.output && (
            <pre className="mt-1 p-2 rounded text-xs overflow-auto max-h-40 font-mono" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' }}>
              {subtask.output.slice(0, 1000)}
            </pre>
          )}
          {subtask.error && (
            <pre className="mt-1 p-2 rounded text-xs overflow-auto max-h-24 font-mono text-red-400" style={{ background: 'var(--color-bg-tertiary)' }}>
              {subtask.error}
            </pre>
          )}
          {subtask.status === 'awaiting_approval' && onApprove && (
            <button
              onClick={() => onApprove(subtask.id)}
              className="mt-2 flex items-center gap-1 px-3 py-1 rounded text-xs font-medium cursor-pointer"
              style={{ background: 'var(--color-accent)', color: '#fff' }}
            >
              <Unlock size={11} /> Approve &amp; Execute
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function PlanningDetailsPanel({ plan }: { plan: TaskPlan }) {
  const show = plan.task_type && plan.task_type !== 'tiny_marker';
  if (!show) return null;
  const isPlanOnly = plan.task_type === 'planning_only';
  return (
    <div className="rounded-lg border p-3 space-y-2 text-xs mb-2" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2 font-medium" style={{ color: 'var(--color-text-primary)' }}>
        <Layers size={12} />
        <span>Planning Details</span>
        {isPlanOnly && (
          <span className="ml-auto text-cyan-400 font-medium">⚠ Plan Only — no writes until approved</span>
        )}
      </div>
      {(plan.likely_files?.length ?? 0) > 0 && (
        <div>
          <div className="text-xs font-medium mb-0.5" style={{ color: 'var(--color-text-secondary)' }}>Likely Files</div>
          {plan.likely_files!.map((f) => (
            <div key={f} className="font-mono text-blue-400 text-xs">{f}</div>
          ))}
        </div>
      )}
      {(plan.risks?.length ?? 0) > 0 && (
        <div>
          <div className="text-xs font-medium mb-0.5 text-yellow-400">Risks</div>
          {plan.risks!.map((r) => (
            <div key={r} className="text-yellow-300 text-xs">{r}</div>
          ))}
        </div>
      )}
      {(plan.validation_commands?.length ?? 0) > 0 && (
        <div>
          <div className="text-xs font-medium mb-0.5 text-green-400">Validation Commands</div>
          {plan.validation_commands!.map((c) => (
            <div key={c} className="font-mono text-green-300 text-xs">{c}</div>
          ))}
        </div>
      )}
      {(plan.approval_gates?.length ?? 0) > 0 && (
        <div>
          <div className="text-xs font-medium mb-0.5" style={{ color: 'var(--color-text-secondary)' }}>Approval Gates</div>
          {plan.approval_gates!.map((g) => (
            <div key={g} className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{g}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function DiffPanel({ diff }: { diff: string }) {
  return (
    <div className="rounded-lg border" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2 p-3 border-b text-sm font-medium" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}>
        <Eye size={14} /> Diff Preview
      </div>
      <pre className="p-3 text-xs overflow-auto max-h-64 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
        {diff || '(no diff — working tree clean)'}
      </pre>
    </div>
  );
}

function ValidationPanel({ output }: { output: string }) {
  const pass = output && !output.toLowerCase().includes('error') && !output.toLowerCase().includes('failed');
  return (
    <div className="rounded-lg border" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2 p-3 border-b text-sm font-medium" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}>
        <Terminal size={14} /> Validation Output
        {output && (
          <span className={`ml-auto text-xs px-2 py-0.5 rounded ${pass ? 'text-green-400 bg-green-900/30' : 'text-red-400 bg-red-900/30'}`}>
            {pass ? 'PASS' : 'CHECK'}
          </span>
        )}
      </div>
      <pre className="p-3 text-xs overflow-auto max-h-48 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
        {output || '(no validation output yet)'}
      </pre>
    </div>
  );
}

function CostPanel({ plan }: { plan: TaskPlan | null }) {
  if (!plan) return null;
  const byTier: Record<string, number> = {};
  for (const st of plan.subtasks) {
    byTier[st.worker_tier] = (byTier[st.worker_tier] ?? 0) + st.cost_usd;
  }
  return (
    <div className="rounded-lg border p-3 space-y-1 text-xs" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2 font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
        <DollarSign size={13} /> Cost Tracking
      </div>
      <div className="flex justify-between" style={{ color: 'var(--color-text-secondary)' }}>
        <span>Total:</span>
        <span className="font-mono">{formatCost(plan.total_cost_usd)}</span>
      </div>
      {Object.entries(byTier).map(([tier, cost]) => (
        <div key={tier} className="flex justify-between" style={{ color: 'var(--color-text-secondary)' }}>
          <span className={TIER_COLORS[tier] ?? 'text-gray-400'}>{TIER_LABELS[tier] ?? tier}:</span>
          <span className="font-mono">{formatCost(cost)}</span>
        </div>
      ))}
      <div className="flex justify-between border-t pt-1 mt-1" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
        <span>Subtasks:</span>
        <span>{plan.subtasks.length}</span>
      </div>
    </div>
  );
}

function GovernancePanel({ plan, dryRun }: { plan: TaskPlan | null; dryRun: boolean }) {
  if (!plan) return null;
  const modesDiffer = plan.dry_run !== dryRun;
  return (
    <div className="rounded-lg border p-3 space-y-1 text-xs" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2 font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
        <Shield size={13} /> Governance
      </div>
      {modesDiffer && (
        <div className="text-yellow-400 text-xs py-0.5">
          ⚠ Mode changed — next execute: {dryRun ? 'DRY-RUN' : 'LIVE'}
        </div>
      )}
      {[
        ['Mode', dryRun ? '⏭️ DRY-RUN' : '🔴 LIVE'],
        ['Stop on blocker', plan.stop_on_blocker ? '✅ Yes' : '❌ No'],
        ['Workers can commit', '❌ Never (enforced)'],
        ['Approval gate', '✅ Active (commit/push/delete)'],
        ['Changed-file review', '✅ Active'],
      ].map(([label, value]) => (
        <div key={label} className="flex justify-between" style={{ color: 'var(--color-text-secondary)' }}>
          <span>{label}:</span>
          <span className="font-mono">{value}</span>
        </div>
      ))}
    </div>
  );
}

function FinalReportPanel({ report }: { report: string }) {
  return (
    <div className="rounded-lg border" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2 p-3 border-b text-sm font-medium" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}>
        <Layers size={14} /> Final Report
      </div>
      <pre className="p-3 text-xs overflow-auto max-h-80 font-mono whitespace-pre-wrap" style={{ color: 'var(--color-text-secondary)' }}>
        {report}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main WorkbenchPage
// ---------------------------------------------------------------------------

export function WorkbenchPage() {
  // Workspace
  const [repoPath, setRepoPath] = useState('/Users/user/OpenJarvis');
  const [prompt, setPrompt] = useState('');
  const [dryRun, setDryRun] = useState(true);
  const [stopOnBlocker, setStopOnBlocker] = useState(true);

  // Plan/execution state
  const [plan, setPlan] = useState<TaskPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'subtasks' | 'diff' | 'validation' | 'report'>('subtasks');

  // Diff panel
  const [liveDiff, setLiveDiff] = useState('');
  const [diffLoading, setDiffLoading] = useState(false);

  // Doctor
  const [doctorChecks, setDoctorChecks] = useState<DoctorCheck[]>([]);
  const [doctorLoaded, setDoctorLoaded] = useState(false);

  const promptRef = useRef<HTMLTextAreaElement>(null);

  // Run doctor on mount
  useEffect(() => {
    apiFetch(`/v1/workbench/doctor?repo_path=${encodeURIComponent(repoPath)}`)
      .then((r) => r.json())
      .then((d) => { setDoctorChecks(d.checks ?? []); setDoctorLoaded(true); })
      .catch(() => setDoctorLoaded(true));
  }, [repoPath]);

  const handlePlan = useCallback(async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/v1/workbench/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, repo_path: repoPath, dry_run: dryRun, stop_on_blocker: stopOnBlocker }),
      });
      const data = await res.json();
      if (data.ok) {
        setPlan(data.plan);
        setActiveTab('subtasks');
      } else {
        setError(data.detail ?? 'Plan failed');
      }
    } catch (e) {
      setError(describeNetworkError(e));
    } finally {
      setLoading(false);
    }
  }, [prompt, repoPath, dryRun, stopOnBlocker]);

  const handleExecute = useCallback(async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/v1/workbench/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          repo_path: repoPath,
          dry_run: dryRun,
          stop_on_blocker: stopOnBlocker,
          session_id: plan?.session_id ?? '',
          task_id: plan?.task_id ?? '',
          approved_subtask_ids: [],
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setPlan(data.plan);
        setActiveTab('subtasks');
      } else {
        setError(data.detail ?? 'Execute failed');
      }
    } catch (e) {
      setError(describeNetworkError(e));
    } finally {
      setLoading(false);
    }
  }, [prompt, repoPath, dryRun, stopOnBlocker, plan]);

  const handleApprove = useCallback(async (subtaskId: string) => {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/v1/workbench/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: plan.session_id,
          task_id: plan.task_id,
          subtask_id: subtaskId,
          prompt: plan.prompt,
          repo_path: plan.repo_path,
        }),
      });
      const data = await res.json();
      if (data.ok) setPlan(data.plan);
      else setError(data.detail ?? 'Approve failed');
    } catch (e) {
      setError(describeNetworkError(e));
    } finally {
      setLoading(false);
    }
  }, [plan]);

  const handleRefreshDiff = useCallback(async () => {
    setDiffLoading(true);
    try {
      const res = await apiFetch('/v1/workbench/diff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath }),
      });
      const data = await res.json();
      setLiveDiff(data.diff ?? '');
      setActiveTab('diff');
    } catch {
      setLiveDiff('(diff error)');
    } finally {
      setDiffLoading(false);
    }
  }, [repoPath]);

  const statusColor = plan
    ? {
        done: 'text-green-400',
        done_dry_run: 'text-blue-400',
        failed: 'text-red-400',
        blocked: 'text-orange-400',
        awaiting_approval: 'text-yellow-400',
        running: 'text-blue-400',
        planned: 'text-gray-400',
      }[plan.status] ?? 'text-gray-400'
    : '';

  const pendingApprovals = plan?.subtasks.filter((s) => s.status === 'awaiting_approval') ?? [];
  const doctorFails = doctorChecks.filter((c) => c.status === 'fail').length;

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: 'var(--color-bg-primary)' }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
        <Code2 size={18} style={{ color: 'var(--color-accent)' }} />
        <span className="font-semibold text-sm" style={{ color: 'var(--color-text-primary)' }}>
          Jarvis Coding Workbench
        </span>
        <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)' }}>
          US14A — Cursor/Windsurf Replacement
        </span>
        {doctorLoaded && (
          <span className={`ml-auto text-xs flex items-center gap-1 ${doctorFails === 0 ? 'text-green-400' : 'text-red-400'}`}>
            {doctorFails === 0 ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
            {doctorFails === 0 ? 'Ready' : `${doctorFails} check(s) failed`}
          </span>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar: controls */}
        <div className="w-72 shrink-0 flex flex-col gap-3 p-3 border-r overflow-y-auto" style={{ borderColor: 'var(--color-border)' }}>
          {/* Workspace */}
          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Workspace / Repo</label>
            <input
              className="w-full text-xs px-2 py-1.5 rounded font-mono"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              placeholder="/path/to/repo"
            />
          </div>

          <RepoStatusPanel repoPath={repoPath} />

          {/* Mode toggles */}
          <div className="flex gap-2">
            <button
              onClick={() => setDryRun((d) => !d)}
              className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium cursor-pointer transition-colors ${dryRun ? 'text-blue-400' : 'text-red-400'}`}
              style={{ background: 'var(--color-bg-secondary)', border: `1px solid ${dryRun ? 'rgba(96,165,250,0.4)' : 'rgba(248,113,113,0.4)'}` }}
            >
              {dryRun ? <EyeOff size={12} /> : <Eye size={12} />}
              {dryRun ? 'Dry-Run' : 'LIVE'}
            </button>
            <button
              onClick={() => setStopOnBlocker((s) => !s)}
              className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium cursor-pointer transition-colors ${stopOnBlocker ? 'text-orange-400' : 'text-gray-400'}`}
              style={{ background: 'var(--color-bg-secondary)', border: `1px solid ${stopOnBlocker ? 'rgba(251,146,60,0.4)' : 'var(--color-border)'}` }}
            >
              <AlertTriangle size={12} />
              {stopOnBlocker ? 'Stop on Blocker' : 'Continue on Err'}
            </button>
          </div>

          {/* Task Prompt */}
          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Task Prompt</label>
            <textarea
              ref={promptRef}
              className="w-full text-xs px-2 py-2 rounded resize-none font-mono"
              rows={4}
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the coding task for Jarvis Manager…"
            />
          </div>

          {/* Action buttons */}
          <div className="space-y-2">
            <button
              onClick={handlePlan}
              disabled={loading || !prompt.trim()}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded text-xs font-medium cursor-pointer disabled:opacity-40"
              style={{ background: 'var(--color-bg-tertiary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
            >
              <FileSearch size={13} /> Plan Only
            </button>
            <button
              onClick={handleExecute}
              disabled={loading || !prompt.trim()}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded text-xs font-medium cursor-pointer disabled:opacity-40"
              style={{ background: 'var(--color-accent)', color: '#fff' }}
            >
              {loading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              {loading ? 'Running…' : dryRun ? 'Execute (Dry-Run)' : 'Execute (LIVE)'}
            </button>
            <button
              onClick={handleRefreshDiff}
              disabled={diffLoading}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded text-xs font-medium cursor-pointer disabled:opacity-40"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}
            >
              {diffLoading ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
              Refresh Diff
            </button>
          </div>

          {/* Pending Approvals */}
          {pendingApprovals.length > 0 && (
            <div className="rounded-lg border p-2 space-y-1" style={{ borderColor: 'rgba(251,191,36,0.4)', background: 'rgba(251,191,36,0.05)' }}>
              <div className="flex items-center gap-2 text-xs font-medium text-yellow-400">
                <Lock size={12} /> {pendingApprovals.length} Awaiting Approval
              </div>
              {pendingApprovals.map((st) => (
                <div key={st.id} className="flex items-center justify-between text-xs">
                  <span className="text-gray-400 truncate">{st.description}</span>
                  <button
                    onClick={() => handleApprove(st.id)}
                    className="ml-2 px-2 py-0.5 rounded text-xs text-green-400 cursor-pointer hover:opacity-80 shrink-0"
                    style={{ border: '1px solid rgba(74,222,128,0.4)' }}
                  >
                    Approve
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Cost panel */}
          <CostPanel plan={plan} />
          <GovernancePanel plan={plan} dryRun={dryRun} />

          {/* Doctor checks */}
          {doctorLoaded && (
            <div className="rounded-lg border p-2 space-y-1" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <div className="text-xs font-medium mb-1 flex items-center gap-1" style={{ color: 'var(--color-text-primary)' }}>
                <Cpu size={12} /> Readiness ({doctorChecks.filter((c) => c.status === 'pass').length}/{doctorChecks.length})
              </div>
              {doctorChecks.map((c) => (
                <div key={c.check} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {c.status === 'pass' ? <CheckCircle2 size={10} className="text-green-400 shrink-0" />
                    : c.status === 'fail' ? <X size={10} className="text-red-400 shrink-0" />
                    : <AlertTriangle size={10} className="text-yellow-400 shrink-0" />}
                  <span className="truncate">{c.check}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Main content area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Plan status bar */}
          {plan && (
            <div className="flex items-center gap-3 px-4 py-2 border-b text-xs shrink-0" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <span className={`font-mono font-bold ${statusColor}`}>{plan.status.toUpperCase()}</span>
              <span style={{ color: 'var(--color-text-secondary)' }}>Session: <code className="text-blue-300">{plan.session_id}</code></span>
              <span style={{ color: 'var(--color-text-secondary)' }}>Task: <code className="text-blue-300">{plan.task_id}</code></span>
              {plan.task_type && (
                <span
                  className={`px-2 py-0.5 rounded font-mono text-xs ${TASK_TYPE_COLORS[plan.task_type] ?? 'text-gray-400'}`}
                  style={{ background: 'var(--color-bg-tertiary)' }}
                >
                  {TASK_TYPE_LABELS[plan.task_type] ?? plan.task_type}
                </span>
              )}
              <span className="ml-auto font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                {formatCost(plan.total_cost_usd)}
              </span>
            </div>
          )}

          {/* Tabs */}
          <div className="flex border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
            {(['subtasks', 'diff', 'validation', 'report'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-xs font-medium cursor-pointer border-b-2 transition-colors ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent'
                }`}
                style={{ color: activeTab === tab ? undefined : 'var(--color-text-secondary)' }}
              >
                {tab === 'subtasks' && <><Layers size={11} className="inline mr-1" />Manager Plan</>}
                {tab === 'diff' && <><Eye size={11} className="inline mr-1" />Diff</>}
                {tab === 'validation' && <><Terminal size={11} className="inline mr-1" />Validation</>}
                {tab === 'report' && <><Zap size={11} className="inline mr-1" />Report</>}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {error && (
              <div className="flex items-start gap-2 p-3 rounded text-xs text-red-400" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}>
                <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {activeTab === 'subtasks' && (
              <>
                {!plan && (
                  <div className="flex flex-col items-center justify-center h-48 gap-3" style={{ color: 'var(--color-text-secondary)' }}>
                    <Code2 size={32} className="opacity-30" />
                    <p className="text-sm">Enter a task prompt and click <strong>Plan Only</strong> or <strong>Execute</strong></p>
                    <p className="text-xs opacity-60">Jarvis Manager will decompose the task into subtasks and route each to the best worker tier</p>
                  </div>
                )}
                {plan && (
                  <div className="space-y-1.5">
                    <PlanningDetailsPanel plan={plan} />
                    <div className="text-xs font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-secondary)' }}>
                      <Cpu size={12} />
                      {plan.subtasks.length} subtasks &bull; routed by Jarvis Manager
                    </div>
                    {plan.subtasks.map((st) => (
                      <SubtaskRow
                        key={st.id}
                        subtask={st}
                        onApprove={handleApprove}
                        sessionId={plan.session_id}
                      />
                    ))}
                  </div>
                )}
              </>
            )}

            {activeTab === 'diff' && (
              <DiffPanel diff={plan?.diff_preview ?? liveDiff} />
            )}

            {activeTab === 'validation' && (
              <ValidationPanel output={plan?.validation_output ?? ''} />
            )}

            {activeTab === 'report' && (
              plan?.final_report ? (
                <FinalReportPanel report={plan.final_report} />
              ) : (
                <div className="flex items-center justify-center h-32 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  Execute a task to see the final report
                </div>
              )
            )}
          </div>

          {/* Commit/Push controls — gated behind Manager approval */}
          {plan && (
            <div className="flex items-center gap-3 px-4 py-2 border-t shrink-0" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <Shield size={12} /> Manager-gated commit/push
              </div>
              <div className="ml-auto flex gap-2">
                <button
                  onClick={() => {
                    const commitSt = plan.subtasks.find((s) => s.tool_id === 'git_commit' && s.status === 'awaiting_approval');
                    if (commitSt) handleApprove(commitSt.id);
                  }}
                  disabled={loading || !plan.subtasks.some((s) => s.tool_id === 'git_commit' && s.status === 'awaiting_approval')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium cursor-pointer disabled:opacity-30"
                  style={{ background: 'var(--color-bg-tertiary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                >
                  <GitCommit size={12} /> Approve Commit
                </button>
                <button
                  onClick={() => {
                    const pushSt = plan.subtasks.find((s) => s.tool_id === 'git_push' && s.status === 'awaiting_approval');
                    if (pushSt) handleApprove(pushSt.id);
                  }}
                  disabled={loading || !plan.subtasks.some((s) => s.tool_id === 'git_push' && s.status === 'awaiting_approval')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium cursor-pointer disabled:opacity-30"
                  style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.4)', color: 'rgb(96,165,250)' }}
                >
                  <Send size={12} /> Approve Push
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
