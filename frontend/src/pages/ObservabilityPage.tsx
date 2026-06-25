import { useState, useEffect } from 'react';
import { Activity, XCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import {
  fetchHealthSummary,
  fetchReliabilityMetrics,
  type HealthSummary,
  type HealthComponent,
  type ReliabilityMetrics,
  type ObservabilityAlert,
} from '../lib/jarvis-api';

type Tab = 'health' | 'metrics';

function StatusDot({ status }: { status: string }) {
  const color =
    status === 'healthy'     ? 'var(--color-success, #a6e3a1)' :
    status === 'degraded'    ? 'var(--color-warning, #f9e2af)' :
    status === 'unavailable' ? 'var(--color-danger, #f38ba8)' :
                               'var(--color-text-tertiary)';
  return (
    <span
      className="w-2 h-2 rounded-full shrink-0 inline-block"
      style={{ background: color, boxShadow: `0 0 6px ${color}` }}
    />
  );
}

function ComponentCard({ component }: { component: HealthComponent }) {
  return (
    <div
      className="rounded-xl px-4 py-4 space-y-2"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex items-center gap-2">
        <StatusDot status={component.status} />
        <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{component.name}</span>
        <span
          className="text-[10px] px-1.5 py-0.5 rounded font-mono ml-auto"
          style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}
        >
          {component.status}
        </span>
      </div>
      {component.note && (
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{component.note}</p>
      )}
    </div>
  );
}

function AlertBanner({ alert }: { alert: ObservabilityAlert }) {
  const isError = alert.level === 'error';
  const color = isError ? 'var(--color-danger, #f38ba8)' : 'var(--color-warning, #f9e2af)';
  return (
    <div
      className="flex items-start gap-2 rounded-xl px-4 py-3"
      style={{
        background: `color-mix(in srgb, ${color} 8%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 20%, transparent)`,
      }}
    >
      <AlertTriangle size={14} style={{ color, flexShrink: 0, marginTop: 1 }} />
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{alert.message}</p>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: unknown }) {
  return (
    <div
      className="flex items-center justify-between px-4 py-3 rounded-xl"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{label}</span>
      <span className="text-sm font-medium font-mono" style={{ color: 'var(--color-text)' }}>
        {String(value)}
      </span>
    </div>
  );
}

const KEY_METRICS = ['scheduler_started', 'failed_routines', 'pending_approvals', 'stale_goals', 'memory_namespaces'];

export function ObservabilityPage() {
  const [tab, setTab] = useState<Tab>('health');
  const [health, setHealth] = useState<HealthSummary | null>(null);
  const [metrics, setMetrics] = useState<ReliabilityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([fetchHealthSummary(), fetchReliabilityMetrics()])
      .then(([h, m]) => {
        setHealth(h);
        setMetrics(m);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load observability data'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading observability data...</span>
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

  const components = health?.components ?? [];
  const alerts = metrics?.alerts ?? [];
  const metricValues = (metrics?.metrics ?? {}) as Record<string, unknown>;

  const overallColor =
    health?.overall_status === 'healthy'     ? 'var(--color-success, #a6e3a1)' :
    health?.overall_status === 'degraded'    ? 'var(--color-warning, #f9e2af)' :
    health?.overall_status === 'unavailable' ? 'var(--color-danger, #f38ba8)' :
                                               'var(--color-text-tertiary)';

  const tabs: { id: Tab; label: string }[] = [
    { id: 'health', label: 'Health' },
    { id: 'metrics', label: 'Metrics' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Activity size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Observability &amp; Reliability</h1>
        {health?.overall_status && (
          <span className="text-xs px-2 py-0.5 rounded-full font-medium ml-auto" style={{ color: overallColor, border: `1px solid ${overallColor}` }}>
            {health.overall_status}
          </span>
        )}
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a, i) => <AlertBanner key={i} alert={a} />)}
        </div>
      )}

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

      {/* Health tab */}
      {tab === 'health' && (
        <>
          {/* Summary chips */}
          {health && (
            <div className="flex flex-wrap gap-3">
              {[
                { label: 'Healthy', value: health.healthy_count, color: 'var(--color-success, #a6e3a1)', icon: CheckCircle },
                { label: 'Degraded', value: health.degraded_count, color: 'var(--color-warning, #f9e2af)', icon: AlertTriangle },
                { label: 'Unavailable', value: health.unavailable_count, color: 'var(--color-danger, #f38ba8)', icon: XCircle },
              ].map(({ label, value, color, icon: Icon }) => (
                <div
                  key={label}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl"
                  style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
                >
                  <Icon size={13} style={{ color }} />
                  <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{label}</span>
                  <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{value}</span>
                </div>
              ))}
            </div>
          )}

          {components.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Activity size={32} style={{ color: 'var(--color-text-tertiary)' }} />
              <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No component data available.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {components.map((c) => <ComponentCard key={c.component_id} component={c} />)}
            </div>
          )}
        </>
      )}

      {/* Metrics tab */}
      {tab === 'metrics' && (
        <>
          <div className="space-y-2">
            {KEY_METRICS.filter((k) => k in metricValues).map((k) => (
              <MetricRow key={k} label={k} value={metricValues[k]} />
            ))}
            {/* Any extra metrics not in our key list */}
            {Object.entries(metricValues)
              .filter(([k]) => !KEY_METRICS.includes(k))
              .map(([k, v]) => (
                <MetricRow key={k} label={k} value={v} />
              ))
            }
            {Object.keys(metricValues).length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <Activity size={32} style={{ color: 'var(--color-text-tertiary)' }} />
                <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No metrics available.</p>
              </div>
            )}
          </div>

          {/* Cost tracking note */}
          <div
            className="flex items-start gap-2 rounded-xl px-4 py-3"
            style={{ background: 'var(--color-bg-tertiary)', border: '1px solid var(--color-border)' }}
          >
            <Info size={14} style={{ color: 'var(--color-text-tertiary)', flexShrink: 0, marginTop: 1 }} />
            <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              Cost tracking requires provider billing API (external gate — not yet live)
            </p>
          </div>
        </>
      )}
    </div>
  );
}
