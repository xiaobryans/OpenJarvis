import { useState, useEffect } from 'react';
import { Share2, XCircle, AlertTriangle } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface MemoryGraphStatus {
  total_namespaces?: number;
  total_entries?: number;
  entity_extraction?: string;
  knowledge_graph?: string;
  planned_capabilities?: string[];
}

interface MemoryNamespace {
  name: string;
  entry_count: number;
}

interface NamespacesResponse {
  namespaces: MemoryNamespace[];
}

const PLANNED_FEATURES = [
  'entity_extraction',
  'relation_mapping',
  'contradiction_detection',
  'cloud_sync',
];

export function MemoryGraphPage() {
  const [status, setStatus] = useState<MemoryGraphStatus | null>(null);
  const [namespaces, setNamespaces] = useState<MemoryNamespace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/memory-graph/status').then((r) => r.json()),
      apiFetch('/v1/memory-graph/namespaces').then((r) => r.json()),
    ])
      .then(([s, n]: [MemoryGraphStatus, NamespacesResponse]) => {
        setStatus(s);
        setNamespaces(n?.namespaces ?? []);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load Memory Graph'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Memory Graph...</span>
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
    { label: 'Namespaces', value: status?.total_namespaces ?? namespaces.length },
    { label: 'Total Entries', value: status?.total_entries ?? namespaces.reduce((a, n) => a + n.entry_count, 0) },
    { label: 'Entity Extraction', value: status?.entity_extraction ?? 'Not yet' },
    { label: 'Knowledge Graph', value: status?.knowledge_graph ?? 'Not yet' },
  ];

  const plannedFeatures = status?.planned_capabilities ?? PLANNED_FEATURES;

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Share2 size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Memory Graph</h1>
      </div>

      {/* Honesty banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, #f97316 8%, transparent)', border: '1px solid color-mix(in srgb, #f97316 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: '#f97316', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Memory graph is metadata-only. Entity extraction and knowledge graph not yet implemented.
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

      {/* Namespace list */}
      {namespaces.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <Share2 size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No namespaces found.</p>
        </div>
      ) : (
        <div>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text)' }}>Namespaces</h2>
          <div className="space-y-2">
            {namespaces.map((ns, i) => (
              <div
                key={i}
                className="flex items-center justify-between px-4 py-3 rounded-xl"
                style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
              >
                <span className="text-sm" style={{ color: 'var(--color-text)' }}>{ns.name}</span>
                <span
                  className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                  style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' }}
                >
                  {ns.entry_count} entries
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Planned capabilities */}
      <div>
        <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text)' }}>Planned Capabilities</h2>
        <div className="flex flex-wrap gap-2">
          {plannedFeatures.map((f, i) => (
            <span
              key={i}
              className="text-xs px-3 py-1 rounded-full"
              style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}
            >
              {f} — coming soon
            </span>
          ))}
        </div>
      </div>

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/memory-graph/status · Phase B16 · No fake data
      </p>
    </div>
  );
}
