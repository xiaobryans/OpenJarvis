import { useState, useEffect } from 'react';
import { ShoppingBag, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

type TabId = 'status' | 'policy';

export function MarketplaceGovernancePage() {
  const [status, setStatus] = useState<any>(null);
  const [policy, setPolicy] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('status');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, p] = await Promise.all([
        apiFetch('/v1/marketplace-governance/status').then(r => r.json()),
        apiFetch('/v1/marketplace-governance/policy').then(r => r.json()),
      ]);
      setStatus(s);
      setPolicy(p);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}><RefreshCw size={20} className="animate-spin mr-2" /> Loading...</div>;
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const policies = policy?.policies || [];

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <ShoppingBag size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Marketplace Governance</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Plugin review and governance framework</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-warning, #f9e2af) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>Manual review required for all plugins. No automated pipeline. No live marketplace.</p>
        </div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
        {(['status', 'policy'] as TabId[]).map(t => (
          <button key={t} onClick={() => setTab(t)} className="flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors" style={{ background: tab === t ? 'var(--color-bg-tertiary)' : 'transparent', color: tab === t ? 'var(--color-text)' : 'var(--color-text-secondary)' }}>
            {t === 'status' ? 'Status' : 'Policy'}
          </button>
        ))}
      </div>

      {tab === 'status' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: 'Review Pipeline', value: status?.review_pipeline_live ? 'Live' : 'No', ok: status?.review_pipeline_live },
            { label: 'Permission Scoring', value: status?.permission_scoring_live ? 'Yes' : 'No', ok: status?.permission_scoring_live },
            { label: 'Dry Run Only', value: status?.dry_run_only ? 'Yes' : 'No', ok: status?.dry_run_only },
            { label: 'Live Marketplace', value: status?.live_marketplace_claims ? 'Yes' : 'No', ok: false },
          ].map(item => (
            <div key={item.label} className="p-4 rounded-lg flex items-center gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              {item.ok ? <CheckCircle size={18} style={{ color: 'var(--color-success, #a6e3a1)', flexShrink: 0 }} /> : <XCircle size={18} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0 }} />}
              <div>
                <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{item.label}</div>
                <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{item.value}</div>
              </div>
            </div>
          ))}
          {(status?.gate_notes || []).map((note: string, i: number) => (
            <div key={i} className="col-span-1 sm:col-span-2 px-3 py-2 rounded" style={{ background: 'var(--color-bg-tertiary)', border: '1px solid var(--color-border)' }}>
              <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{note}</p>
            </div>
          ))}
        </div>
      )}

      {tab === 'policy' && (
        <div className="space-y-3">
          {policies.map((pol: any) => (
            <div key={pol.policy_id} className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{pol.name}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono shrink-0" style={{ background: pol.enforced ? 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)' : 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)', color: pol.enforced ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' }}>
                  {pol.enforced ? 'ENFORCED' : 'NOT ENFORCED'}
                </span>
              </div>
              <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{pol.description}</p>
              {!pol.enforced && pol.gate && <p className="text-xs mt-1" style={{ color: 'var(--color-warning, #f9e2af)' }}>{pol.gate}</p>}
            </div>
          ))}
        </div>
      )}

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/marketplace-governance/status, /v1/marketplace-governance/policy · fake_data={String(status?.fake_data ?? false)}
      </div>
    </div>
  );
}
