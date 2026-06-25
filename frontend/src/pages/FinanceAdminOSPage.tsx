import { useState, useEffect } from 'react';
import { DollarSign, XCircle, AlertTriangle, Shield } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface FinanceAction {
  name: string;
  approval_required?: boolean;
}

interface FinanceCategory {
  name: string;
  status: string;
  description: string;
  actions: FinanceAction[];
  external_gate?: string;
}

interface FinanceDashboard {
  categories: FinanceCategory[];
  live_financial_execution?: string;
  approval_gates?: string;
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    available: { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    partial:   { bg: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' },
    planned:   { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

function CategoryCard({ cat }: { cat: FinanceCategory }) {
  return (
    <div
      className="rounded-xl p-4 space-y-3"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{cat.name}</span>
        <StatusChip status={cat.status} />
      </div>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>{cat.description}</p>
      {cat.actions && cat.actions.length > 0 && (
        <div className="space-y-1">
          {cat.actions.map((action, i) => (
            <div key={i} className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <span>{action.name}</span>
              {action.approval_required && (
                <span className="flex items-center gap-0.5" style={{ color: 'var(--color-warning, #f9e2af)' }}>
                  <Shield size={10} />
                  <span className="text-[10px]">approval</span>
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      {cat.external_gate && (
        <p className="text-[10px] px-2 py-1 rounded" style={{ background: 'color-mix(in srgb, #f97316 10%, transparent)', color: '#f97316' }}>
          Gate: {cat.external_gate}
        </p>
      )}
    </div>
  );
}

export function FinanceAdminOSPage() {
  const [data, setData] = useState<FinanceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiFetch('/v1/finance-admin/dashboard')
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch((e) => setError(e?.message ?? 'Failed to load finance dashboard'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Finance & Admin OS...</span>
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

  const categories = data?.categories ?? [];
  const stats = [
    { label: 'Categories', value: categories.length },
    { label: 'Available Now', value: categories.filter((c) => c.status?.toLowerCase() === 'available').length },
    { label: 'Live Financial Execution', value: data?.live_financial_execution ?? 'Never' },
    { label: 'Approval Gates', value: data?.approval_gates ?? 'Active' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <DollarSign size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Finance & Admin OS</h1>
      </div>

      {/* Honesty banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, #f97316 8%, transparent)', border: '1px solid color-mix(in srgb, #f97316 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: '#f97316', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          No live financial execution. Templates and task-based tracking only. External gates required for bank/payment integration.
        </p>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map(({ label, value }) => (
          <div
            key={label}
            className="rounded-xl px-4 py-3 flex flex-col gap-1"
            style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
          >
            <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
            <span className="text-lg font-semibold leading-tight" style={{ color: 'var(--color-text)' }}>{value}</span>
          </div>
        ))}
      </div>

      {/* Category grid */}
      {categories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <DollarSign size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No finance categories found.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {categories.map((cat, i) => (
            <CategoryCard key={i} cat={cat} />
          ))}
        </div>
      )}

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/finance-admin/dashboard · Phase B13 · No fake data
      </p>
    </div>
  );
}
