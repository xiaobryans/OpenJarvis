import { useState, useEffect } from 'react';
import { ShieldCheck, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

type TabId = 'lanes' | 'arbitration';

export function ReviewGovernancePage() {
  const [govStatus, setGovStatus] = useState<any>(null);
  const [arbitration, setArbitration] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('lanes');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, a] = await Promise.all([
        apiFetch('/v1/review-governance/status').then(r => r.json()),
        apiFetch('/v1/review-governance/arbitration').then(r => r.json()),
      ]);
      setGovStatus(s);
      setArbitration(a);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}><RefreshCw size={20} className="animate-spin mr-2" /> Loading...</div>;
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const lanes = govStatus?.reviewer_lanes || [];
  const conflicts = arbitration?.conflicts || [];

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <ShieldCheck size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Review &amp; Governance</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Reviewer lanes and arbitration status</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-warning, #f9e2af) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>Approval gates always active. No auto-approval. Legal/financial require external gates.</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
        {(['lanes', 'arbitration'] as TabId[]).map(t => (
          <button key={t} onClick={() => setTab(t)} className="flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors" style={{ background: tab === t ? 'var(--color-bg-tertiary)' : 'transparent', color: tab === t ? 'var(--color-text)' : 'var(--color-text-secondary)' }}>
            {t === 'lanes' ? 'Lanes' : 'Arbitration'}
          </button>
        ))}
      </div>

      {tab === 'lanes' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {lanes.map((lane: any) => (
            <div key={lane.lane_id} className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{lane.name}</span>
                <div className="flex gap-1 flex-wrap justify-end">
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-mono" style={{ background: lane.active ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)' : 'color-mix(in srgb, var(--color-border) 50%, transparent)', color: lane.active ? 'var(--color-success, #a6e3a1)' : 'var(--color-text-tertiary)' }}>{lane.active ? 'ACTIVE' : 'INACTIVE'}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-mono" style={{ background: 'color-mix(in srgb, var(--color-accent) 15%, transparent)', color: 'var(--color-accent)' }}>{lane.approval_tier}</span>
                </div>
              </div>
              {!lane.active && lane.gate && <div className="text-xs" style={{ color: 'var(--color-warning, #f9e2af)' }}>{lane.gate}</div>}
            </div>
          ))}
        </div>
      )}

      {tab === 'arbitration' && (
        <div className="space-y-4">
          {conflicts.length === 0 ? (
            <div className="p-6 rounded-lg text-center" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              <CheckCircle size={24} style={{ color: 'var(--color-success, #a6e3a1)', margin: '0 auto 8px' }} />
              <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>No conflicts detected</p>
            </div>
          ) : (
            conflicts.map((c: any, i: number) => (
              <div key={i} className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
                <p className="text-sm" style={{ color: 'var(--color-text)' }}>{JSON.stringify(c)}</p>
              </div>
            ))
          )}
          {arbitration?.conflict_resolution && (
            <div className="p-3 rounded-lg" style={{ background: 'var(--color-bg-tertiary)', border: '1px solid var(--color-border)' }}>
              <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{arbitration.conflict_resolution}</p>
            </div>
          )}
        </div>
      )}

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/review-governance/status, /v1/review-governance/arbitration · fake_data={String(govStatus?.fake_data ?? false)}
      </div>
    </div>
  );
}
