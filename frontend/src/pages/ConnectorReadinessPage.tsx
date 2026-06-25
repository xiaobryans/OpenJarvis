import React, { useEffect, useState } from 'react'
import { Plug, ShieldCheck } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function ConnectorReadinessPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch('/v1/connector-readiness/status')
      .then(r => r.json())
      .then(d => setData(d))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading connector readiness...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const connectors: any[] = data?.connectors ?? []

  const statusColor = (status: string) => {
    if (status === 'ready_prerequisite') return 'var(--color-success, #a6e3a1)'
    if (status === 'blocked') return 'var(--color-danger, #f38ba8)'
    return 'var(--color-warning, #f9e2af)'
  }

  const total = connectors.length
  const ready = connectors.filter(c => c.status === 'ready_prerequisite').length
  const blocked = connectors.filter(c => c.status === 'blocked').length
  const notConfigured = connectors.filter(c => c.status === 'not_configured').length

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <Plug size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">Connector Readiness Verification</h1>
      </div>

      {/* No credential values badge */}
      <div className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ background: 'var(--color-success, #a6e3a1)', color: '#1a3a1a' }}>
        <ShieldCheck size={16} />
        No credential values in response — presence-only reporting
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total', value: total, color: 'var(--color-text)' },
          { label: 'Ready', value: ready, color: 'var(--color-success, #a6e3a1)' },
          { label: 'Blocked', value: blocked, color: 'var(--color-danger, #f38ba8)' },
          { label: 'Not Configured', value: notConfigured, color: 'var(--color-warning, #f9e2af)' },
        ].map(stat => (
          <div key={stat.label} className="rounded-lg p-3 text-center" style={{ background: 'var(--color-surface)' }}>
            <div className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</div>
            <div className="text-xs opacity-60 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Connector cards */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Connectors</h2>
        {connectors.length === 0 ? (
          <p className="text-sm opacity-60">No connectors found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {connectors.map((c: any, i: number) => (
              <div key={c.connector_id ?? i} className="rounded-lg p-3 border" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="flex items-center justify-between mb-1">
                  <div className="font-medium">{c.name}</div>
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: statusColor(c.status), color: '#1a1a1a' }}>
                    {c.status}
                  </span>
                </div>
                {c.reason && <div className="text-xs opacity-60 mt-1">{c.reason}</div>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
