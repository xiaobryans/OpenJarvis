import { useState, useEffect } from 'react';
import { Zap, CheckCircle, XCircle, Shield, AlertTriangle } from 'lucide-react';
import { fetchConnectorWorkflows, type ConnectorEntry, type ConnectorWorkflowsResponse } from '../lib/jarvis-api';

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    configured:     { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)', label: 'Configured' },
    not_configured: { bg: 'color-mix(in srgb, var(--color-text-tertiary) 12%, transparent)', color: 'var(--color-text-tertiary)', label: 'Not Configured' },
    partial:        { bg: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)', label: 'Partial' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)', label: status };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: s.bg, color: s.color }}>
      {s.label}
    </span>
  );
}

function LiveBadge({ live }: { live: boolean }) {
  return (
    <span
      className="text-[10px] px-2 py-0.5 rounded-full font-medium"
      style={{
        background: live
          ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)'
          : 'color-mix(in srgb, var(--color-text-tertiary) 10%, transparent)',
        color: live ? 'var(--color-success, #a6e3a1)' : 'var(--color-text-tertiary)',
      }}
    >
      {live ? 'Live' : 'Dry-run only'}
    </span>
  );
}

function ConnectorCard({ connector }: { connector: ConnectorEntry }) {
  return (
    <div
      className="rounded-xl px-4 py-4 space-y-3"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Zap size={14} style={{ color: 'var(--color-accent)' }} />
        <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{connector.name}</span>
        <StatusChip status={connector.status} />
        <LiveBadge live={connector.live} />
      </div>
      {connector.available_workflows.length === 0 ? (
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>No workflows defined.</p>
      ) : (
        <ul className="space-y-1.5 pl-1">
          {connector.available_workflows.map((wf) => (
            <li key={wf.workflow_id} className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <span className="w-1 h-1 rounded-full shrink-0" style={{ background: 'var(--color-text-tertiary)' }} />
              <span className="flex-1">{wf.name}</span>
              {wf.requires_approval && (
                <span className="flex items-center gap-1" style={{ color: 'var(--color-warning, #f9e2af)' }}>
                  <Shield size={11} />
                  <span className="text-[10px]">approval</span>
                </span>
              )}
              {wf.dry_run_only && (
                <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>dry-run</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ConnectorWorkflowsPage() {
  const [data, setData] = useState<ConnectorWorkflowsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchConnectorWorkflows()
      .then(setData)
      .catch((e) => setError(e?.message ?? 'Failed to load connector workflows'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading connector workflows...</span>
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

  const connectors = data?.connectors ?? [];
  const totalWorkflows = connectors.reduce((sum, c) => sum + c.available_workflows.length, 0);

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Zap size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Connector Workflows</h1>
      </div>

      {/* Honest banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-warning, #f9e2af) 20%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Live actions require connector credentials + approval gates. dry_run_only workflows show capability plans only.
        </p>
      </div>

      {/* Stats strip */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { label: 'Configured', value: data.configured_count, icon: CheckCircle, color: 'var(--color-success, #a6e3a1)' },
            { label: 'Live', value: data.live_connector_count, icon: Zap, color: 'var(--color-accent)' },
            { label: 'Total Workflows', value: totalWorkflows, icon: Shield },
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
      )}

      {/* Connectors */}
      {connectors.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Zap size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No connectors found</p>
        </div>
      ) : (
        <div className="space-y-3">
          {connectors.map((c) => (
            <ConnectorCard key={c.connector_id} connector={c} />
          ))}
        </div>
      )}
    </div>
  );
}
