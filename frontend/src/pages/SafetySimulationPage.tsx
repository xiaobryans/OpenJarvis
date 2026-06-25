import { useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw, CheckCircle, XCircle, Shield } from 'lucide-react';
import { apiFetch } from '../lib/api';

type TabId = 'status' | 'rollback' | 'policy';

export function SafetySimulationPage() {
  const [status, setStatus] = useState<any>(null);
  const [rollback, setRollback] = useState<any>(null);
  const [policy, setPolicy] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('status');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, r, p] = await Promise.all([
        apiFetch('/v1/safety-simulation/status').then(res => res.json()),
        apiFetch('/v1/safety-simulation/rollback-matrix').then(res => res.json()),
        apiFetch('/v1/safety-simulation/policy-checks').then(res => res.json()),
      ]);
      setStatus(s);
      setRollback(r);
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

  const rollbackCaps = rollback?.rollback_capabilities || [];
  const hardGates = policy?.hard_gates || [];

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Shield size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Safety &amp; Simulation Framework</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Dry-run safety, rollback matrix, and policy checks</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-warning, #f9e2af) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-warning, #f9e2af)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>All simulations are dry-run only. No real execution. Rollback is manual and approval-gated.</p>
        </div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
        {(['status', 'rollback', 'policy'] as TabId[]).map(t => (
          <button key={t} onClick={() => setTab(t)} className="flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors capitalize" style={{ background: tab === t ? 'var(--color-bg-tertiary)' : 'transparent', color: tab === t ? 'var(--color-text)' : 'var(--color-text-secondary)' }}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'status' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: 'Dry Run Only', value: status?.dry_run_only ?? true, invertOk: false },
            { label: 'Real Execution', value: status?.real_execution ?? false, invertOk: true },
            { label: 'Destructive Actions Blocked', value: status?.destructive_actions_blocked ?? true, invertOk: false },
            { label: 'Simulation Framework', value: status?.simulation_framework_available ?? true, invertOk: false },
          ].map(item => (
            <div key={item.label} className="p-4 rounded-lg flex items-center gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              {(item.invertOk ? !item.value : item.value) ? <CheckCircle size={18} style={{ color: 'var(--color-success, #a6e3a1)', flexShrink: 0 }} /> : <XCircle size={18} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0 }} />}
              <div>
                <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{item.label}</div>
                <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{String(item.value)}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'rollback' && (
        <div className="space-y-2">
          {rollbackCaps.map((cap: any) => (
            <div key={cap.target} className="p-3 rounded-lg flex items-start gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              {cap.available ? <CheckCircle size={16} style={{ color: 'var(--color-success, #a6e3a1)', flexShrink: 0, marginTop: 1 }} /> : <XCircle size={16} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 1 }} />}
              <div className="flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{cap.target}</span>
                  {cap.approval_required && <span className="text-[10px] px-2 py-0.5 rounded-full font-mono" style={{ background: 'color-mix(in srgb, var(--color-accent) 15%, transparent)', color: 'var(--color-accent)' }}>APPROVAL</span>}
                </div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{cap.method}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'policy' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Hard Gates', value: policy?.hard_gate_count ?? 14 },
              { label: 'Soft Gates', value: policy?.soft_gate_count ?? 7 },
              { label: 'Enforced', value: policy?.gates_enforced ? 'Yes' : 'No' },
              { label: 'Bypassing', value: policy?.bypassing_gates ? 'Yes' : 'Never' },
            ].map(s => (
              <div key={s.label} className="p-3 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
                <div className="text-xs mb-1" style={{ color: 'var(--color-text-tertiary)' }}>{s.label}</div>
                <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{s.value}</div>
              </div>
            ))}
          </div>
          <div className="p-4 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
            <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-text-secondary)' }}>Hard Gates</h3>
            <div className="space-y-1">
              {hardGates.map((gate: string, i: number) => (
                <div key={i} className="flex items-center gap-2">
                  <Shield size={10} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0 }} />
                  <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{gate}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/safety-simulation/status, /v1/safety-simulation/rollback-matrix, /v1/safety-simulation/policy-checks · fake_data={String(status?.fake_data ?? false)}
      </div>
    </div>
  );
}
