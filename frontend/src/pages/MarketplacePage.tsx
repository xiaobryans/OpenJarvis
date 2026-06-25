import { useState, useEffect } from 'react';
import { ShoppingBag, XCircle, AlertTriangle } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface MarketplaceStatus {
  local_plugins_count?: number;
  marketplace_live?: boolean;
  auto_install?: string;
}

interface Plugin {
  name: string;
  status: string;
  safety_level?: string;
  source?: string;
  marketplace_verified?: boolean;
}

interface PluginsResponse {
  plugins: Plugin[];
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    active:    { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    inactive:  { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' },
    available: { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    pending:   { bg: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

export function MarketplacePage() {
  const [status, setStatus] = useState<MarketplaceStatus | null>(null);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/marketplace/status').then((r) => r.json()),
      apiFetch('/v1/marketplace/plugins').then((r) => r.json()),
    ])
      .then(([s, p]: [MarketplaceStatus, PluginsResponse]) => {
        setStatus(s);
        setPlugins(p?.plugins ?? []);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load Marketplace'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Plugin Marketplace...</span>
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

  const stats = [
    { label: 'Local Plugins', value: status?.local_plugins_count ?? plugins.length },
    { label: 'Marketplace Live', value: status?.marketplace_live ? 'Yes' : 'No' },
    { label: 'Auto-Install', value: status?.auto_install ?? 'Blocked' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <ShoppingBag size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Plugin Marketplace</h1>
      </div>

      {/* Honesty banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, #f97316 8%, transparent)', border: '1px solid color-mix(in srgb, #f97316 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: '#f97316', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          No live marketplace. Local registry only. Third-party plugins require manual security review.
        </p>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
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

      {/* Plugin list */}
      {plugins.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <ShoppingBag size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No plugins found.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {plugins.map((plugin, i) => (
            <div
              key={i}
              className="flex items-center gap-3 px-4 py-3 rounded-xl flex-wrap"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
            >
              <span className="text-sm font-medium flex-1 min-w-0" style={{ color: 'var(--color-text)' }}>{plugin.name}</span>
              <div className="flex items-center gap-1.5 flex-wrap">
                <StatusChip status={plugin.status} />
                {plugin.safety_level && (
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' }}
                  >
                    {plugin.safety_level}
                  </span>
                )}
                {plugin.source && (
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{ background: 'color-mix(in srgb, var(--color-info, #89dceb) 12%, transparent)', color: 'var(--color-info, #89dceb)' }}
                  >
                    {plugin.source}
                  </span>
                )}
                {plugin.marketplace_verified === false && (
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' }}
                  >
                    Unverified
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/marketplace/status · Phase B18 · No fake data
      </p>
    </div>
  );
}
