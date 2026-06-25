import { useState, useEffect } from 'react';
import { ClipboardCheck, RefreshCw, AlertTriangle, XCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

const dimStatusColor: Record<string, string> = {
  ready: 'var(--color-success, #a6e3a1)',
  partial: 'var(--color-warning, #f9e2af)',
  not_ready: 'var(--color-danger, #f38ba8)',
};

export function ProductReadinessPage() {
  const [matrix, setMatrix] = useState<any>(null);
  const [multiUser, setMultiUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, u] = await Promise.all([
        apiFetch('/v1/product-readiness/matrix').then(r => r.json()),
        apiFetch('/v1/product-readiness/multi-user-status').then(r => r.json()),
      ]);
      setMatrix(m);
      setMultiUser(u);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}><RefreshCw size={20} className="animate-spin mr-2" /> Loading...</div>;
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const dims = matrix?.readiness_dimensions || [];
  const ready = dims.filter((d: any) => d.status === 'ready').length;
  const partial = dims.filter((d: any) => d.status === 'partial').length;
  const notReady = dims.filter((d: any) => d.status === 'not_ready').length;

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <ClipboardCheck size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Product &amp; Multi-User Readiness</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Readiness matrix and multi-user status</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      {/* Danger honesty banner */}
      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-danger, #f38ba8) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-danger, #f38ba8) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>Production multi-user support not available. Single-user mode only. Multi-user requires external auth/RBAC gates.</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Dimensions', value: dims.length || 6 },
          { label: 'Ready', value: ready },
          { label: 'Partial', value: partial },
          { label: 'Not Ready', value: notReady },
        ].map(s => (
          <div key={s.label} className="p-3 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
            <div className="text-xs mb-1" style={{ color: 'var(--color-text-tertiary)' }}>{s.label}</div>
            <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Readiness grid */}
      <div>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-secondary)' }}>Readiness Dimensions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {dims.map((dim: any) => (
            <div key={dim.dimension_id} className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{dim.name}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono shrink-0" style={{ background: 'transparent', color: dimStatusColor[dim.status] || 'var(--color-text-tertiary)', border: `1px solid ${dimStatusColor[dim.status] || 'var(--color-border)'}` }}>
                  {dim.status.replace('_', ' ').toUpperCase()}
                </span>
              </div>
              <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{dim.description}</p>
              {dim.gap && <p className="text-xs mt-1" style={{ color: 'var(--color-warning, #f9e2af)' }}>{dim.gap}</p>}
            </div>
          ))}
        </div>
      </div>

      {/* Multi-user panel */}
      <div className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-secondary)' }}>Multi-User Status</h2>
        <div className="flex items-center gap-3">
          <XCircle size={32} style={{ color: 'var(--color-danger, #f38ba8)' }} />
          <div>
            <div className="font-semibold" style={{ color: 'var(--color-text)' }}>Multi-User: Not Live</div>
            <div className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>Single-user mode: {multiUser?.single_user_mode ? 'Active' : 'Unknown'}</div>
          </div>
        </div>
      </div>

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/product-readiness/matrix, /v1/product-readiness/multi-user-status · fake_data={String(matrix?.fake_data ?? false)}
      </div>
    </div>
  );
}
