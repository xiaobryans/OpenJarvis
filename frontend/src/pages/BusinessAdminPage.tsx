import { useState, useEffect } from 'react';
import { Briefcase, XCircle, Shield, AlertTriangle, CheckCircle } from 'lucide-react';
import {
  fetchBusinessAdminDashboard,
  fetchBusinessAdminWorkflows,
  type AdminCategory,
  type BusinessAdminDashboard,
  type BusinessWorkflow,
} from '../lib/jarvis-api';

type Tab = 'categories' | 'workflows';

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    available:     { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    partial:       { bg: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' },
    unavailable:   { bg: 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)', color: 'var(--color-danger, #f38ba8)' },
    external_gate: { bg: 'color-mix(in srgb, var(--color-info, #89dceb) 12%, transparent)', color: 'var(--color-info, #89dceb)' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

function CategoryCard({ cat }: { cat: AdminCategory }) {
  return (
    <div
      className="rounded-xl px-4 py-4 space-y-3"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Briefcase size={14} style={{ color: 'var(--color-accent)' }} />
        <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{cat.name}</span>
        <StatusChip status={cat.status} />
      </div>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>{cat.description}</p>
      {cat.external_gate && (
        <p className="text-[11px]" style={{ color: 'var(--color-info, #89dceb)' }}>
          External gate: {cat.external_gate}
        </p>
      )}
      {cat.actions.length > 0 && (
        <ul className="space-y-1.5 pl-1">
          {cat.actions.map((a) => (
            <li key={a.action_id} className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <span className="w-1 h-1 rounded-full shrink-0" style={{ background: 'var(--color-text-tertiary)' }} />
              <span className="flex-1">{a.name}</span>
              {a.approval_required && (
                <span className="flex items-center gap-1" style={{ color: 'var(--color-warning, #f9e2af)' }}>
                  <Shield size={11} />
                  <span className="text-[10px]">approval</span>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function WorkflowRow({ wf }: { wf: BusinessWorkflow }) {
  return (
    <div
      className="rounded-xl px-4 py-3 flex flex-wrap items-start gap-3"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{wf.name}</span>
          <StatusChip status={wf.available ? 'available' : 'unavailable'} />
          <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}>
            {wf.category}
          </span>
          {wf.approval_required && (
            <span className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--color-warning, #f9e2af)' }}>
              <Shield size={10} />approval
            </span>
          )}
        </div>
        {wf.source_route && (
          <code className="text-[10px] font-mono" style={{ color: 'var(--color-text-tertiary)' }}>{wf.source_route}</code>
        )}
        {wf.gate && (
          <p className="text-xs" style={{ color: 'var(--color-info, #89dceb)' }}>Gate: {wf.gate}</p>
        )}
      </div>
    </div>
  );
}

export function BusinessAdminPage() {
  const [tab, setTab] = useState<Tab>('categories');
  const [dashboard, setDashboard] = useState<BusinessAdminDashboard | null>(null);
  const [workflows, setWorkflows] = useState<BusinessWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchBusinessAdminDashboard(),
      fetchBusinessAdminWorkflows(),
    ])
      .then(([dash, wfData]) => {
        setDashboard(dash);
        setWorkflows(wfData.workflows ?? []);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load business admin data'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading business admin...</span>
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

  const categories = dashboard?.categories ?? [];
  const approvalGates = workflows.filter((w) => w.approval_required).length;

  const tabs: { id: Tab; label: string }[] = [
    { id: 'categories', label: 'Categories' },
    { id: 'workflows', label: 'Workflows' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Briefcase size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Business &amp; Admin OS</h1>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Categories Available', value: dashboard?.available_now ?? 0, icon: CheckCircle, color: 'var(--color-success, #a6e3a1)' },
          { label: 'Workflows Available', value: workflows.filter((w) => w.available).length, icon: Briefcase },
          { label: 'Approval Gates: Active', value: approvalGates, icon: Shield, color: 'var(--color-warning, #f9e2af)' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className="rounded-xl px-4 py-3 flex flex-col gap-1"
            style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
          >
            <div className="flex items-center gap-1.5">
              <Icon size={13} style={{ color: color ?? 'var(--color-text-tertiary)' }} />
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
            </div>
            <span className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>{value}</span>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
            style={{
              background: tab === t.id ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
              color: tab === t.id ? 'var(--color-text)' : 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Approval gates warning */}
      {dashboard?.approval_gates_active && (
        <div
          className="flex items-start gap-2 rounded-xl px-4 py-3"
          style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-warning, #f9e2af) 20%, transparent)' }}
        >
          <AlertTriangle size={14} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 1 }} />
          <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            Approval gates are active. Actions with approval_required=true will not execute without explicit approval.
          </p>
        </div>
      )}

      {/* Tab content */}
      {tab === 'categories' && (
        categories.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Briefcase size={32} style={{ color: 'var(--color-text-tertiary)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No categories found.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {categories.map((cat) => (
              <CategoryCard key={cat.category_id} cat={cat} />
            ))}
          </div>
        )
      )}

      {tab === 'workflows' && (
        workflows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Briefcase size={32} style={{ color: 'var(--color-text-tertiary)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No workflows found.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {workflows.map((wf) => (
              <WorkflowRow key={wf.workflow_id} wf={wf} />
            ))}
          </div>
        )
      )}
    </div>
  );
}
