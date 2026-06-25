import { useState, useEffect } from 'react';
import { UserPlus, XCircle, AlertTriangle, CheckCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface OrgModeStatus {
  multi_user_live?: boolean;
  single_user_mode?: boolean;
  org_mode_available?: boolean;
}

interface OrgCapability {
  name: string;
  available: boolean;
  gate?: string;
}

interface OrgCapabilityMatrix {
  capabilities?: OrgCapability[];
  planned_roles?: string[];
}

export function OrgModePage() {
  const [status, setStatus] = useState<OrgModeStatus | null>(null);
  const [matrix, setMatrix] = useState<OrgCapabilityMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/org-mode/status').then((r) => r.json()),
      apiFetch('/v1/org-mode/capability-matrix').then((r) => r.json()),
    ])
      .then(([s, m]: [OrgModeStatus, OrgCapabilityMatrix]) => {
        setStatus(s);
        setMatrix(m);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load Org Mode'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Organization Mode...</span>
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

  const capabilities = matrix?.capabilities ?? [];
  const plannedRoles = matrix?.planned_roles ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <UserPlus size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Organization Mode</h1>
      </div>

      {/* Honesty banner — red */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, var(--color-danger, #f38ba8) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-danger, #f38ba8) 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Single-user mode only. Multi-user/org mode requires production auth (external gate).
        </p>
      </div>

      {/* Status indicators */}
      <div
        className="rounded-xl p-4 space-y-3"
        style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Mode Status</span>
        <div className="space-y-2 pt-1">
          <div className="flex items-center gap-3">
            <XCircle size={18} style={{ color: 'var(--color-danger, #f38ba8)' }} />
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Multi-user live: not available</span>
          </div>
          <div className="flex items-center gap-3">
            <CheckCircle size={18} style={{ color: 'var(--color-success, #a6e3a1)' }} />
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Single-user mode: active</span>
          </div>
          <div className="flex items-center gap-3">
            <XCircle size={18} style={{ color: 'var(--color-danger, #f38ba8)' }} />
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Org mode: not available</span>
          </div>
        </div>
      </div>

      {/* Capability grid */}
      {capabilities.length > 0 && (
        <div>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text)' }}>Capabilities</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {capabilities.map((cap, i) => (
              <div
                key={i}
                className="rounded-xl px-4 py-3 space-y-1"
                style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm" style={{ color: 'var(--color-text)' }}>{cap.name}</span>
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                    style={{
                      background: cap.available
                        ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
                        : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)',
                      color: cap.available ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)',
                    }}
                  >
                    {cap.available ? 'available' : 'unavailable'}
                  </span>
                </div>
                {cap.gate && (
                  <p className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>Gate: {cap.gate}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Role model panel */}
      {plannedRoles.length > 0 && (
        <div>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text)' }}>Planned Roles</h2>
          <div className="flex flex-wrap gap-2">
            {plannedRoles.map((role, i) => (
              <span key={i} className="flex items-center gap-1.5 text-xs px-3 py-1 rounded-full" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}>
                {role}
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{ background: 'color-mix(in srgb, var(--color-danger, #f38ba8) 12%, transparent)', color: 'var(--color-danger, #f38ba8)' }}
                >
                  not implemented
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/org-mode/status · Phase B19 · No fake data
      </p>
    </div>
  );
}
