import { useState, useEffect } from 'react';
import { Layers, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

export function ScaleControlPage() {
  const [status, setStatus] = useState<any>(null);
  const [macbookOff, setMacbookOff] = useState<any>(null);
  const [parity, setParity] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, m, p] = await Promise.all([
        apiFetch('/v1/scale-control/status').then(r => r.json()),
        apiFetch('/v1/scale-control/macbook-off-readiness').then(r => r.json()),
        apiFetch('/v1/scale-control/parity-status').then(r => r.json()),
      ]);
      setStatus(s);
      setMacbookOff(m);
      setParity(p);
    } catch (e: any) {
      setError(e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-64" style={{ color: 'var(--color-text-secondary)' }}><RefreshCw size={20} className="animate-spin mr-2" /> Loading...</div>;
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error} <button onClick={load} className="ml-4 underline">Retry</button></div>;

  const requirements = macbookOff?.requirements || [];
  const parityGaps = parity?.parity_gaps || [];
  const deviceReadiness = status?.device_readiness || {};

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Layers size={24} style={{ color: 'var(--color-accent)' }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Scale Control Plane</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Cross-device and cloud scale status</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-lg" style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}><RefreshCw size={16} /></button>
      </div>

      <div className="px-4 py-3 rounded-lg border" style={{ background: 'color-mix(in srgb, var(--color-danger, #f38ba8) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--color-danger, #f38ba8) 30%, transparent)' }}>
        <div className="flex items-start gap-2"><AlertTriangle size={16} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 2 }} />
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>MacBook-off cloud execution not live. All 4 deployment requirements unmet. Desktop active only.</p>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Desktop', value: deviceReadiness.desktop || 'Active' },
          { label: 'Mobile PWA', value: deviceReadiness.mobile_pwa || 'Not deployed' },
          { label: 'Cloud Fargate', value: deviceReadiness.cloud_fargate || 'Not deployed' },
          { label: 'Cloud Exec', value: 'Never' },
        ].map(s => (
          <div key={s.label} className="p-3 rounded-lg" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
            <div className="text-xs mb-1" style={{ color: 'var(--color-text-tertiary)' }}>{s.label}</div>
            <div className="font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* MacBook-off readiness */}
      <div>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-secondary)' }}>MacBook-Off Readiness ({macbookOff?.requirements_met ?? 0}/{macbookOff?.requirements_total ?? 4} met)</h2>
        <div className="space-y-2">
          {requirements.map((req: any) => (
            <div key={req.req_id} className="p-3 rounded-lg flex items-start gap-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
              {req.met ? <CheckCircle size={16} style={{ color: 'var(--color-success, #a6e3a1)', flexShrink: 0, marginTop: 1 }} /> : <XCircle size={16} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0, marginTop: 1 }} />}
              <div>
                <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{req.name}</div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{req.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Parity gaps */}
      <div>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-secondary)' }}>Parity Gaps</h2>
        {parityGaps.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>No parity gaps found.</p>
        ) : (
          <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
                  <th className="px-4 py-2 text-left text-xs" style={{ color: 'var(--color-text-secondary)' }}>Gap</th>
                  <th className="px-4 py-2 text-left text-xs" style={{ color: 'var(--color-text-secondary)' }}>Desktop</th>
                  <th className="px-4 py-2 text-left text-xs" style={{ color: 'var(--color-text-secondary)' }}>Mobile</th>
                </tr>
              </thead>
              <tbody>
                {parityGaps.map((gap: any, i: number) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--color-border)', background: i % 2 === 0 ? 'transparent' : 'var(--color-bg-secondary)' }}>
                    <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text)' }}>{gap.name}</td>
                    <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-success, #a6e3a1)' }}>{gap.desktop}</td>
                    <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-danger, #f38ba8)' }}>{gap.mobile}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="text-xs pt-2" style={{ color: 'var(--color-text-tertiary)', borderTop: '1px solid var(--color-border)' }}>
        Data source: GET /v1/scale-control/status, /v1/scale-control/macbook-off-readiness, /v1/scale-control/parity-status · fake_data={String(status?.fake_data ?? false)}
      </div>
    </div>
  );
}
