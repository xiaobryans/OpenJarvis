import React, { useEffect, useState } from 'react'
import { Zap, CheckCircle, XCircle, Clock } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function ExecutionReadinessPage() {
  const [status, setStatus] = useState<any>(null)
  const [matrix, setMatrix] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/execution-readiness/status').then(r => r.json()),
      apiFetch('/v1/execution-readiness/matrix').then(r => r.json()),
    ]).then(([s, m]) => { setStatus(s); setMatrix(m) }).catch(e => setError(String(e))).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading execution readiness...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const systems = status?.systems ?? []
  const classes = matrix?.action_classes ?? []

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <Zap size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">Execution Readiness Manager</h1>
      </div>

      {/* Honesty banner */}
      <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--color-warning, #f9e2af)', color: '#5c4a00' }}>
        Autonomous execution live: <strong>No</strong> — All actions require explicit approval.
      </div>

      {/* Systems grid */}
      <section>
        <h2 className="text-lg font-semibold mb-3">System Readiness</h2>
        {systems.length === 0 ? (
          <p className="text-sm opacity-60">No systems found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {systems.map((s: any) => (
              <div key={s.system_id} className="rounded-lg p-3 border" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="font-medium">{s.name}</div>
                <div className="text-sm opacity-70 mt-1">{s.status}</div>
                <div className="text-xs mt-1" style={{ color: s.approval_required ? 'var(--color-warning, #f9e2af)' : 'var(--color-success, #a6e3a1)' }}>
                  {s.approval_required ? 'Approval required' : 'No approval needed'}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Action classes */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Action Classes</h2>
        {classes.length === 0 ? (
          <p className="text-sm opacity-60">No action classes found.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {classes.map((c: any) => (
              <div key={c.class_id} className="rounded-lg p-3 border text-sm" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="font-medium">{c.name}</div>
                <div className="opacity-60 mt-1">Tier {c.min_approval_tier}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
