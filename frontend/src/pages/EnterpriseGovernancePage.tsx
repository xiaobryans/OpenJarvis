import { useState, useEffect } from 'react';
import { Shield, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

type TabId = 'audit' | 'reliability' | 'cost';

export function EnterpriseGovernancePage() {
  const [audit, setAudit] = useState<any>(null);
  const [reliability, setReliability] = useState<any>(null);
  const [cost, setCost] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('audit');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [a, r, c] = await Promise.all([
        apiFetch('/v1/enterprise-governance/audit-summary').then(res => res.json()),
        apiFetch('/v1/enterprise-governance/reliability').then(res => res.json()),
        apiFetch('/v1/enterprise-governance/cost-control').then(res => res.json()),
      ]);
      setAudit(a);
      setReliability(r);
      setCost(c);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}><RefreshCw size={20} className="animate-spin mr-2" /> Loading...</div>;
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const sloTargets = reliability?.slo_targets || [];

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Shield size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Enterprise Governance</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Audit, reliability, and cost control</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-warning, #f9e2af) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>Audit is secret-safe. Live billing integration not deployed. SLO metadata only.</p>
        </div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
        {(['audit', 'reliability', 'cost'] as TabId[]).map(t => (
          <button key={t} onClick={() => setTab(t)} className="flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors capitalize" style={{ background: tab === t ? 'var(--color-bg-tertiary)' : 'transparent', color: tab === t ? 'var(--color-text)' : 'var(--color-text-secondary)' }}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'audit' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            {audit?.secret_safe && <span className="text-[11px] px-2 py-1 rounded font-mono" style={{ background: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' }}>SECRET-SAFE</span>}
          </div>
          {(audit?.audit_entries?.length ?? 0) === 0 ? (
            <div className="p-6 rounded-lg text-center" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              <p className="text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>No audit entries</p>
            </div>
          ) : (
            (audit?.audit_entries || []).map((entry: any, i: number) => (
              <div key={i} className="p-3 rounded-lg text-xs" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}>
                {JSON.stringify(entry)}
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'reliability' && (
        <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
                <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Service</th>
                <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Target</th>
                <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {sloTargets.map((slo: any, i: number) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--color-border)', background: i % 2 === 0 ? 'transparent' : 'var(--color-bg-secondary)' }}>
                  <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text)' }}>{slo.service}</td>
                  <td className="px-4 py-2 text-xs font-mono" style={{ color: 'var(--color-text-secondary)' }}>{slo.target}</td>
                  <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{slo.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'cost' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: 'Cost Tracking', value: cost?.cost_tracking_available ? 'Available' : 'Unavailable', ok: cost?.cost_tracking_available },
            { label: 'Live Billing Integration', value: cost?.live_billing_integration ? 'Yes' : 'No', ok: cost?.live_billing_integration },
            { label: 'Provider Routing Visible', value: cost?.provider_routing_visible ? 'Yes' : 'No', ok: cost?.provider_routing_visible },
            { label: 'Budget Alerts', value: cost?.budget_alerts_live ? 'Live' : 'Not Deployed', ok: cost?.budget_alerts_live },
          ].map(item => (
            <div key={item.label} className="p-4 rounded-lg flex items-center gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              {item.ok ? <CheckCircle size={18} style={{ color: 'var(--color-success, #a6e3a1)', flexShrink: 0 }} /> : <XCircle size={18} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0 }} />}
              <div>
                <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{item.label}</div>
                <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{item.value}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/enterprise-governance/audit-summary, /v1/enterprise-governance/reliability, /v1/enterprise-governance/cost-control · secret_safe={String(audit?.secret_safe ?? true)}
      </div>
    </div>
  );
}
