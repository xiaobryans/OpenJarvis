import { useState, useEffect } from 'react';
import { Cpu, XCircle, AlertTriangle, CheckCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface DeviceControllerStatus {
  device_control_live?: boolean;
  simulator_mode?: boolean;
  physical_world_execution?: boolean;
  supported_device_types?: SupportedDevice[];
}

interface SupportedDevice {
  type: string;
  live?: boolean;
  gate?: string;
}

interface SafetyRule {
  rule: string;
  enforced: boolean;
}

interface SafetyMatrix {
  safety_rules?: SafetyRule[];
}

export function DeviceControllerPage() {
  const [status, setStatus] = useState<DeviceControllerStatus | null>(null);
  const [safetyMatrix, setSafetyMatrix] = useState<SafetyMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/device-controller/status').then((r) => r.json()),
      apiFetch('/v1/device-controller/safety-matrix').then((r) => r.json()),
    ])
      .then(([s, m]: [DeviceControllerStatus, SafetyMatrix]) => {
        setStatus(s);
        setSafetyMatrix(m);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load Device Controller'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Device Controller...</span>
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

  const deviceTypes = status?.supported_device_types ?? [];
  const safetyRules = safetyMatrix?.safety_rules ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Cpu size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Device Controller</h1>
      </div>

      {/* Honesty banner — red */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, var(--color-danger, #f38ba8) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-danger, #f38ba8) 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Device controller is simulator/dry-run only. No physical device control. Tier 4 approval required.
        </p>
      </div>

      {/* Status badges */}
      <div
        className="rounded-xl p-4 space-y-3"
        style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Runtime Status</span>
        <div className="flex flex-wrap gap-2 pt-1">
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-medium"
            style={{
              background: status?.device_control_live
                ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
                : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)',
              color: status?.device_control_live ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)',
            }}
          >
            {status?.device_control_live ? 'control live' : 'control offline'}
          </span>
          {status?.simulator_mode && (
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' }}
            >
              simulator mode
            </span>
          )}
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-medium"
            style={{
              background: status?.physical_world_execution
                ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
                : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)',
              color: status?.physical_world_execution ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)',
            }}
          >
            {status?.physical_world_execution ? 'physical execution on' : 'no physical execution'}
          </span>
        </div>
      </div>

      {/* Device types */}
      {deviceTypes.length > 0 && (
        <div>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text)' }}>Supported Device Types</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {deviceTypes.map((device, i) => (
              <div
                key={i}
                className="rounded-xl px-4 py-3 space-y-1.5"
                style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm" style={{ color: 'var(--color-text)' }}>{device.type}</span>
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                    style={{
                      background: device.live
                        ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
                        : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)',
                      color: device.live ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)',
                    }}
                  >
                    {device.live ? 'live' : 'not live'}
                  </span>
                </div>
                {device.gate && (
                  <p className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>Gate: {device.gate}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Safety matrix */}
      {safetyRules.length > 0 && (
        <div>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text)' }}>Safety Rules</h2>
          <div className="space-y-2">
            {safetyRules.map((rule, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl"
                style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
              >
                <span className="text-sm flex-1" style={{ color: 'var(--color-text-secondary)' }}>{rule.rule}</span>
                {rule.enforced ? (
                  <div className="flex items-center gap-1 shrink-0">
                    <CheckCircle size={13} style={{ color: 'var(--color-success, #a6e3a1)' }} />
                    <span className="text-[10px]" style={{ color: 'var(--color-success, #a6e3a1)' }}>enforced</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 shrink-0">
                    <XCircle size={13} style={{ color: 'var(--color-danger, #f38ba8)' }} />
                    <span className="text-[10px]" style={{ color: 'var(--color-danger, #f38ba8)' }}>not enforced</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state for device types */}
      {deviceTypes.length === 0 && safetyRules.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Cpu size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No device data found.</p>
        </div>
      )}

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/device-controller/status · Phase B20 · No fake data
      </p>
    </div>
  );
}
