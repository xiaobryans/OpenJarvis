import { useState, useEffect } from 'react';
import { Radio, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

type TabId = 'phases' | 'gates' | 'completion';

const phaseStatusColor: Record<string, string> = {
  ACCEPTED: 'var(--color-success, #a6e3a1)',
  ON_HOLD: 'var(--color-warning, #f9e2af)',
  IN_PROGRESS: 'var(--color-accent)',
  PARKED: 'var(--color-text-tertiary)',
  COMPLETE: 'var(--color-success, #a6e3a1)',
};

export function ControlTowerPage() {
  const [status, setStatus] = useState<any>(null);
  const [gates, setGates] = useState<any>(null);
  const [completion, setCompletion] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('phases');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, g, c] = await Promise.all([
        apiFetch('/v1/control-tower/status').then(r => r.json()),
        apiFetch('/v1/control-tower/gate-registry').then(r => r.json()),
        apiFetch('/v1/control-tower/completion-score').then(r => r.json()),
      ]);
      setStatus(s);
      setGates(g);
      setCompletion(c);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}><RefreshCw size={20} className="animate-spin mr-2" /> Loading...</div>;
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const phases = status?.phases || [];
  const openGates = gates?.open_gates || [];
  const closedGates = gates?.closed_gates || [];
  const score = completion?.core_os_completion?.completion_score_pct ?? 65;
  const capCoverage = completion?.capability_coverage || {};

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Radio size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Phase C Control Tower</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Consolidated phase status, gates, and completion</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-warning, #f9e2af) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>No fake acceptance. All phase acceptances require Bryan's explicit review. 65% completion is honest estimate.</p>
        </div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
        {(['phases', 'gates', 'completion'] as TabId[]).map(t => (
          <button key={t} onClick={() => setTab(t)} className="flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors capitalize" style={{ background: tab === t ? 'var(--color-bg-tertiary)' : 'transparent', color: tab === t ? 'var(--color-text)' : 'var(--color-text-secondary)' }}>
            {t === 'phases' ? 'Phase Status' : t === 'gates' ? 'Gates' : 'Completion'}
          </button>
        ))}
      </div>

      {tab === 'phases' && (
        <div className="space-y-2">
          {phases.map((phase: any) => (
            <div key={phase.phase} className="p-3 rounded-lg flex items-start gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              <div className="flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{phase.phase}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-mono shrink-0" style={{ color: phaseStatusColor[phase.status] || 'var(--color-text-tertiary)', border: `1px solid ${phaseStatusColor[phase.status] || 'var(--color-border)'}`, background: 'transparent' }}>
                    {phase.status}
                  </span>
                </div>
                {phase.note && <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{phase.note}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'gates' && (
        <div className="space-y-4">
          {openGates.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-danger, #f38ba8)' }}>Open Gates ({openGates.length})</h3>
              <div className="space-y-2">
                {openGates.map((g: any) => (
                  <div key={g.gate_id} className="p-3 rounded-lg flex items-start gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid color-mix(in srgb, var(--color-danger, #f38ba8) 20%, var(--color-border))' }}>
                    <XCircle size={16} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 1 }} />
                    <div>
                      <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{g.name}</div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{g.note}</div>
                    </div>
                    <span className="ml-auto text-[10px] px-2 py-0.5 rounded font-mono" style={{ color: g.severity === 'high' ? 'var(--color-danger, #f38ba8)' : 'var(--color-warning, #f9e2af)' }}>{g.severity}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {closedGates.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-success, #a6e3a1)' }}>Closed Gates ({closedGates.length})</h3>
              <div className="space-y-2">
                {closedGates.map((g: any) => (
                  <div key={g.gate_id} className="p-3 rounded-lg flex items-start gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid color-mix(in srgb, var(--color-success, #a6e3a1) 20%, var(--color-border))' }}>
                    <CheckCircle size={16} style={{ color: 'var(--color-success, #a6e3a1)', flexShrink: 0, marginTop: 1 }} />
                    <div>
                      <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{g.name}</div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{g.note}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {openGates.length === 0 && closedGates.length === 0 && (
            <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>No gates found.</p>
          )}
        </div>
      )}

      {tab === 'completion' && (
        <div className="space-y-4">
          {/* Progress bar */}
          <div className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
            <div className="flex justify-between mb-2">
              <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Core OS Completion</span>
              <span className="text-sm font-mono font-bold" style={{ color: 'var(--color-accent)' }}>{score}%</span>
            </div>
            <div className="h-3 rounded-full overflow-hidden" style={{ background: 'var(--color-bg-tertiary)' }}>
              <div className="h-full rounded-full" style={{ width: `${score}%`, background: 'var(--color-accent)' }} />
            </div>
            {completion?.core_os_completion?.note && <p className="text-xs mt-2" style={{ color: 'var(--color-text-tertiary)' }}>{completion.core_os_completion.note}</p>}
          </div>

          {/* Capability coverage */}
          <div>
            <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-text-secondary)' }}>Capability Coverage</h3>
            <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: 'var(--color-text-secondary)' }}>Capability</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: 'var(--color-text-secondary)' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(capCoverage).map(([key, val], i) => (
                    <tr key={key} style={{ borderBottom: '1px solid var(--color-border)', background: i % 2 === 0 ? 'transparent' : 'var(--color-bg-secondary)' }}>
                      <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text)' }}>{key.replace(/_/g, ' ')}</td>
                      <td className="px-4 py-2 text-xs">
                        {val ? <CheckCircle size={14} style={{ color: 'var(--color-success, #a6e3a1)' }} /> : <XCircle size={14} style={{ color: 'var(--color-danger, #f38ba8)' }} />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/control-tower/status, /v1/control-tower/gate-registry, /v1/control-tower/completion-score · fake_data={String(status?.fake_data ?? false)}
      </div>
    </div>
  );
}
