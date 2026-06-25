import { useState, useEffect } from 'react';
import { Globe, XCircle, AlertTriangle } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface BrowserStatus {
  browser_operator_available: boolean;
  dry_run_only: boolean;
  external_gates: string[];
}

interface CapabilityCategory {
  category: string;
  available: boolean;
  approval_tier: string;
}

interface CapabilityMatrix {
  categories: CapabilityCategory[];
}

function AvailabilityChip({ available }: { available: boolean }) {
  return (
    <span
      className="text-[10px] px-2 py-0.5 rounded-full font-medium"
      style={{
        background: available
          ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
          : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)',
        color: available ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)',
      }}
    >
      {available ? 'available' : 'blocked'}
    </span>
  );
}

export function BrowserOperatorPage() {
  const [status, setStatus] = useState<BrowserStatus | null>(null);
  const [matrix, setMatrix] = useState<CapabilityMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/browser-operator/status').then((r) => r.json()),
      apiFetch('/v1/browser-operator/capability-matrix').then((r) => r.json()),
    ])
      .then(([s, m]: [BrowserStatus, CapabilityMatrix]) => {
        setStatus(s);
        setMatrix(m);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load Browser Operator'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Browser Operator...</span>
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

  const categories = matrix?.categories ?? [];
  const gates = status?.external_gates ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Globe size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Browser / Web Operator</h1>
      </div>

      {/* Honesty banner — red */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, var(--color-danger, #f38ba8) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-danger, #f38ba8) 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Browser operator is dry-run only. No live browser control. All actions require Tier 3/4 approval.
        </p>
      </div>

      {/* Status panel */}
      <div
        className="rounded-xl p-4 space-y-3"
        style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Status</span>
        <div className="flex flex-wrap gap-2 pt-1">
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-medium"
            style={{
              background: status?.browser_operator_available
                ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
                : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)',
              color: status?.browser_operator_available ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)',
            }}
          >
            {status?.browser_operator_available ? 'operator available' : 'operator unavailable'}
          </span>
          {status?.dry_run_only && (
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' }}
            >
              dry-run only
            </span>
          )}
        </div>
        {gates.length > 0 && (
          <div className="space-y-1 pt-1">
            <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>External gates required:</span>
            {gates.map((g, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-warning, #f9e2af)' }}>
                <AlertTriangle size={11} />
                <span>{g}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Capability matrix */}
      {categories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Globe size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No capability data found.</p>
        </div>
      ) : (
        <div>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text)' }}>Capability Matrix</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {categories.map((cat, i) => (
              <div
                key={i}
                className="rounded-xl px-4 py-3 flex items-center justify-between gap-3"
                style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
              >
                <div className="flex flex-col gap-1">
                  <span className="text-sm" style={{ color: 'var(--color-text)' }}>{cat.category}</span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded self-start"
                    style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}
                  >
                    Tier {cat.approval_tier}
                  </span>
                </div>
                <AvailabilityChip available={cat.available} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/browser-operator/status · Phase B15 · No fake data
      </p>
    </div>
  );
}
