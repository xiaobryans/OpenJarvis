import { useState, useEffect } from 'react';
import { Building2, RefreshCw, AlertTriangle } from 'lucide-react';
import { apiFetch } from '../lib/api';

export function CompanyOSPage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [lanes, setLanes] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [d, l] = await Promise.all([
        apiFetch('/v1/company-os/dashboard').then(r => r.json()),
        apiFetch('/v1/company-os/workflow-lanes').then(r => r.json()),
      ]);
      setDashboard(d);
      setLanes(l);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}><RefreshCw size={20} className="animate-spin mr-2" /> Loading...</div>;
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const workflowLanes = lanes?.lanes || dashboard?.workflow_lanes || [];

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Building2 size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Company OS</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Company operating dashboard and workflow lanes</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-warning, #f9e2af) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>No live business execution. Local task/goal integration only. Legal/finance require external gates.</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Active Lanes', value: dashboard?.active_lanes ?? 4 },
          { label: 'Total Lanes', value: dashboard?.total_lanes ?? 6 },
          { label: 'Live Business Exec', value: 'Never' },
          { label: 'Goals/Tasks', value: 'Linked' },
        ].map(s => (
          <div key={s.label} className="p-3 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
            <div className="text-xs mb-1" style={{ color: 'var(--color-text-tertiary)' }}>{s.label}</div>
            <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Lanes grid */}
      <div>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-secondary)' }}>Workflow Lanes</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {workflowLanes.map((lane: any) => (
            <div key={lane.lane_id} className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{lane.name}</span>
                <div className="flex gap-1 flex-wrap justify-end">
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-mono" style={{ background: lane.active ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)' : 'color-mix(in srgb, var(--color-border) 50%, transparent)', color: lane.active ? 'var(--color-success, #a6e3a1)' : 'var(--color-text-tertiary)' }}>{lane.active ? 'ACTIVE' : 'INACTIVE'}</span>
                  {lane.approval_required && <span className="text-[10px] px-2 py-0.5 rounded-full font-mono" style={{ background: 'color-mix(in srgb, var(--color-accent) 15%, transparent)', color: 'var(--color-accent)' }}>APPROVAL</span>}
                </div>
              </div>
              {lane.description && <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{lane.description}</p>}
              {!lane.active && lane.gate && <p className="text-xs mt-1" style={{ color: 'var(--color-warning, #f9e2af)' }}>{lane.gate}</p>}
            </div>
          ))}
        </div>
      </div>

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/company-os/dashboard, /v1/company-os/workflow-lanes · fake_data={String(dashboard?.fake_data ?? false)}
      </div>
    </div>
  );
}
