import { useState, useEffect } from 'react';
import { Crosshair, RefreshCw, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import { apiFetch } from '../lib/api';

const statusColor: Record<string, string> = {
  active: 'var(--color-success, #a6e3a1)',
  paused: 'var(--color-warning, #f9e2af)',
  completed: 'var(--color-text-tertiary)',
  blocked: 'var(--color-danger, #f38ba8)',
};

export function MissionControlCPage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await apiFetch('/v1/mission-control/dashboard').then(r => r.json());
      setDashboard(d);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggle = (id: string) => setExpanded(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  if (loading) return (
    <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}>
      <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
    </div>
  );
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const missions = dashboard?.missions || [];

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Crosshair size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Mission Control</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Long-horizon mission dashboard</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}>
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Honesty banner */}
      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-warning, #f9e2af) 30%, transparent)' }}>
        <div className="flex items-start gap-2">
          <AlertTriangle size={16} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>No unapproved execution. All next steps require approval.</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Missions', value: dashboard?.total ?? 0 },
          { label: 'Active', value: dashboard?.active ?? 0 },
          { label: 'Paused', value: dashboard?.paused ?? 0 },
          { label: 'Unapproved Exec', value: 'Never' },
        ].map(s => (
          <div key={s.label} className="p-3 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
            <div className="text-xs mb-1" style={{ color: 'var(--color-text-tertiary)' }}>{s.label}</div>
            <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Dry-run indicator */}
      <div className="px-4 py-3 rounded-lg" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-warning, #f9e2af) 20%, transparent)' }}>
        <p className="text-sm font-medium" style={{ color: 'var(--color-warning, #f9e2af)' }}>All next steps require explicit approval before execution.</p>
      </div>

      {/* Mission list */}
      <div>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-secondary)' }}>Missions</h2>
        {missions.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>No missions found.</p>
        ) : (
          <div className="space-y-3">
            {missions.map((m: any) => (
              <div key={m.mission_id} className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
                <button
                  onClick={() => toggle(m.mission_id)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left"
                  style={{ background: 'var(--color-bg-secondary)' }}
                >
                  {expanded.has(m.mission_id) ? <ChevronDown size={16} style={{ color: 'var(--color-text-tertiary)' }} /> : <ChevronRight size={16} style={{ color: 'var(--color-text-tertiary)' }} />}
                  <span className="flex-1 font-medium text-sm" style={{ color: 'var(--color-text)' }}>{m.title}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-mono" style={{ background: 'color-mix(in srgb, transparent 80%, var(--color-bg-tertiary))', color: statusColor[m.status] || 'var(--color-text-tertiary)' }}>{m.status.toUpperCase()}</span>
                  {m.approval_required && <span className="text-[10px] px-2 py-0.5 rounded-full font-mono ml-1" style={{ background: 'color-mix(in srgb, var(--color-accent) 15%, transparent)', color: 'var(--color-accent)' }}>APPROVAL REQ</span>}
                </button>
                {expanded.has(m.mission_id) && (
                  <div className="px-4 py-3" style={{ background: 'var(--color-bg-tertiary)', borderTop: '1px solid var(--color-border)' }}>
                    <div className="text-xs mb-2" style={{ color: 'var(--color-text-secondary)' }}>Milestones: {m.milestones?.length ?? 0}</div>
                    {(m.milestones || []).map((ms: any) => (
                      <div key={ms.milestone_id} className="flex items-center gap-2 mb-1">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-text-tertiary)' }} />
                        <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{ms.title}</span>
                        <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>({ms.status})</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/mission-control/dashboard · No fake data · unapproved_execution={String(dashboard?.unapproved_execution ?? false)}
      </div>
    </div>
  );
}
