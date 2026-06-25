import React, { useEffect, useState } from 'react'
import { Cloud, CheckCircle, XCircle, ShieldCheck } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function CloudReadinessPage() {
  const [status, setStatus] = useState<any>(null)
  const [matrix, setMatrix] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/cloud-readiness/status').then(r => r.json()),
      apiFetch('/v1/cloud-readiness/prerequisites-matrix').then(r => r.json()),
    ])
      .then(([s, m]) => { setStatus(s); setMatrix(m) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading cloud readiness...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const prereqList: any[] = matrix?.prerequisites ?? []
  const macbookOffMet = status?.macbook_off_requirements_met ?? 0
  const macbookOffTotal = status?.macbook_off_requirements_total ?? 0
  const cloudExecutionLive = status?.cloud_execution_live ?? false
  const bryanCleared: any[] = status?.bryan_cleared ?? []
  const fargateReady = status?.fargate_ready ?? false
  const tailscaleReady = status?.tailscale_ready ?? false

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <Cloud size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">Cloud / Fargate / Tailscale Readiness Gate</h1>
      </div>

      {/* Cloud execution live: No banner */}
      <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--color-warning, #f9e2af)', color: '#5c4a00' }}>
        Cloud execution live: <strong>{cloudExecutionLive ? 'Yes' : 'No'}</strong> — Cloud actions require explicit Bryan approval before any live execution.
      </div>

      {/* MacBook-off requirements */}
      <div className="rounded-lg p-3 flex items-center justify-between" style={{ background: 'var(--color-surface)' }}>
        <span className="text-sm font-medium">MacBook-Off Requirements Met</span>
        <span className="text-lg font-bold" style={{ color: macbookOffMet === macbookOffTotal && macbookOffTotal > 0 ? 'var(--color-success, #a6e3a1)' : 'var(--color-warning, #f9e2af)' }}>
          {macbookOffMet} / {macbookOffTotal}
        </span>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Fargate Ready', value: fargateReady ? 'Yes' : 'No', color: fargateReady ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
          { label: 'Tailscale Ready', value: tailscaleReady ? 'Yes' : 'No', color: tailscaleReady ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
          { label: 'Prerequisites', value: prereqList.length, color: 'var(--color-text)' },
          { label: 'Bryan Cleared', value: bryanCleared.length, color: bryanCleared.length > 0 ? 'var(--color-success, #a6e3a1)' : 'var(--color-text)' },
        ].map(stat => (
          <div key={stat.label} className="rounded-lg p-3 text-center" style={{ background: 'var(--color-surface)' }}>
            <div className="text-lg font-bold" style={{ color: stat.color }}>{String(stat.value)}</div>
            <div className="text-xs opacity-60 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Prerequisites list */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Prerequisites Matrix</h2>
        {prereqList.length === 0 ? (
          <p className="text-sm opacity-60">No prerequisites found.</p>
        ) : (
          <div className="space-y-2">
            {prereqList.map((p: any, i: number) => (
              <div key={p.id ?? i} className="rounded-lg p-3 border flex items-center gap-3" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                {p.present ? (
                  <CheckCircle size={16} style={{ color: 'var(--color-success, #a6e3a1)', flexShrink: 0 }} />
                ) : (
                  <XCircle size={16} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0 }} />
                )}
                <div className="flex-1">
                  <div className="text-sm font-medium">{p.name}</div>
                  {p.description && <div className="text-xs opacity-60 mt-0.5">{p.description}</div>}
                </div>
                <span className="text-xs px-2 py-0.5 rounded" style={{ background: p.present ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)', color: '#1a1a1a' }}>
                  {p.present ? 'Present' : 'Absent'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Bryan cleared section */}
      {bryanCleared.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">Bryan-Cleared Items</h2>
          <div className="space-y-2">
            {bryanCleared.map((item: any, i: number) => (
              <div key={i} className="rounded-lg p-3 border flex items-center gap-2 text-sm" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <ShieldCheck size={14} style={{ color: 'var(--color-success, #a6e3a1)' }} />
                <span>{typeof item === 'string' ? item : item.name}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
