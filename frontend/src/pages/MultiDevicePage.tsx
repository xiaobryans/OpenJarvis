import { useState, useEffect } from 'react';
import { Monitor, XCircle, AlertTriangle } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface DeviceCapability {
  name: string;
  available: boolean;
  gated?: boolean;
}

interface DeviceSession {
  device_type: string;
  status: string;
  capabilities: DeviceCapability[];
}

interface MultiDeviceStatus {
  active_sessions?: number;
  phone_control_live?: boolean;
  macbook_off_cloud_execution_live?: boolean;
  sessions?: DeviceSession[];
}

interface CapabilityMatrix {
  devices?: DeviceSession[];
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    active:    { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    inactive:  { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' },
    connected: { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    gated:     { bg: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

function LiveBadge({ live, label }: { live: boolean; label: string }) {
  return (
    <div
      className="rounded-xl px-4 py-3 flex flex-col gap-1"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
      <span
        className="text-xs font-semibold px-2 py-0.5 rounded-full self-start"
        style={{
          background: live
            ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
            : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)',
          color: live ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)',
        }}
      >
        {live ? 'Live' : 'Not live'}
      </span>
    </div>
  );
}

export function MultiDevicePage() {
  const [status, setStatus] = useState<MultiDeviceStatus | null>(null);
  const [matrix, setMatrix] = useState<CapabilityMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/multi-device/status').then((r) => r.json()),
      apiFetch('/v1/multi-device/capability-matrix').then((r) => r.json()),
    ])
      .then(([s, m]: [MultiDeviceStatus, CapabilityMatrix]) => {
        setStatus(s);
        setMatrix(m);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load Multi-Device'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Multi-Device & Workbench...</span>
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

  const sessions = status?.sessions ?? matrix?.devices ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Monitor size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Multi-Device & Workbench</h1>
      </div>

      {/* Honesty banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, #f97316 8%, transparent)', border: '1px solid color-mix(in srgb, #f97316 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: '#f97316', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Desktop active. Mobile PWA and cloud execution require Tailscale + Fargate deployment.
        </p>
      </div>

      {/* Sessions strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div
          className="rounded-xl px-4 py-3 flex flex-col gap-1"
          style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
        >
          <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>Active Sessions</span>
          <span className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>
            {status?.active_sessions ?? sessions.filter((s) => s.status?.toLowerCase() === 'active').length}
          </span>
        </div>
        <LiveBadge live={status?.phone_control_live ?? false} label="Phone Control" />
        <LiveBadge live={status?.macbook_off_cloud_execution_live ?? false} label="MacBook-Off Cloud" />
        <div
          className="rounded-xl px-4 py-3 flex flex-col gap-1"
          style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
        >
          <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>Devices</span>
          <span className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>{sessions.length}</span>
        </div>
      </div>

      {/* Device list */}
      {sessions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Monitor size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No device sessions found.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((session, i) => (
            <div
              key={i}
              className="rounded-xl p-4 space-y-3"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{session.device_type}</span>
                <StatusChip status={session.status} />
              </div>
              {session.capabilities && session.capabilities.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {session.capabilities.map((cap, j) => (
                    <span
                      key={j}
                      className="text-[10px] px-2 py-0.5 rounded-full"
                      style={{
                        background: cap.available
                          ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 12%, transparent)'
                          : cap.gated
                            ? 'color-mix(in srgb, var(--color-warning, #f9e2af) 12%, transparent)'
                            : 'var(--color-bg-tertiary)',
                        color: cap.available
                          ? 'var(--color-success, #a6e3a1)'
                          : cap.gated
                            ? 'var(--color-warning, #f9e2af)'
                            : 'var(--color-text-tertiary)',
                      }}
                    >
                      {cap.name}{cap.gated ? ' (gated)' : ''}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/multi-device/status · Phase B17 · No fake data
      </p>
    </div>
  );
}
