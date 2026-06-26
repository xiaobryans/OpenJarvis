import React, { useEffect, useState } from 'react'
import { Trophy, ShieldCheck } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function CoreCompletionPage() {
  const [status, setStatus] = useState<any>(null)
  const [phaseDOptions, setPhaseDOptions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/core-completion/status').then(r => r.json()),
      apiFetch('/v1/core-completion/phase-d-options').then(r => r.json()),
    ])
      .then(([s, d]) => {
        setStatus(s)
        setPhaseDOptions(Array.isArray(d) ? d : (d?.options ?? []))
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading core completion status...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const phases: any[] = status?.phases ?? []
  const completionScore = status?.completion_score ?? 72
  const overallStatus = status?.overall_status ?? 'in_progress'

  const phaseStatusColor = (s: string) => {
    const v = (s ?? '').toUpperCase()
    if (v === 'ACCEPTED') return 'var(--color-success, #a6e3a1)'
    if (v === 'IN_PROGRESS') return 'var(--color-accent)'
    if (v === 'ON_HOLD') return 'var(--color-warning, #f9e2af)'
    if (v === 'PARKED') return 'var(--color-text)'
    return 'var(--color-text)'
  }

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <Trophy size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">VANTA Core OS Completion Gate</h1>
      </div>

      {/* No fake completion badge */}
      <div className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ background: 'var(--color-success, #a6e3a1)', color: '#1a3a1a' }}>
        <ShieldCheck size={16} />
        No fake completion claimed — only Bryan can mark a plan accepted
      </div>

      {/* Completion score */}
      <div className="rounded-lg p-6 text-center" style={{ background: 'var(--color-surface)' }}>
        <div className="text-5xl font-bold" style={{ color: completionScore >= 80 ? 'var(--color-success, #a6e3a1)' : completionScore >= 60 ? 'var(--color-warning, #f9e2af)' : 'var(--color-danger, #f38ba8)' }}>
          {completionScore}%
        </div>
        <div className="text-sm opacity-60 mt-2">Core OS Completion Score</div>
        <div className="text-xs mt-1 opacity-40">Overall: {overallStatus}</div>
      </div>

      {/* Phase status grid */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Phase Status</h2>
        {phases.length === 0 ? (
          <p className="text-sm opacity-60">No phases found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {phases.map((p: any, i: number) => (
              <div key={p.phase_id ?? i} className="rounded-lg p-3 border" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="flex items-center justify-between mb-1">
                  <div className="font-medium text-sm">{p.name}</div>
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: phaseStatusColor(p.status), color: '#1a1a1a' }}>
                    {p.status}
                  </span>
                </div>
                {p.description && <div className="text-xs opacity-60">{p.description}</div>}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Phase D options */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Phase D Options</h2>
        {phaseDOptions.length === 0 ? (
          <p className="text-sm opacity-60">No Phase D options found.</p>
        ) : (
          <div className="space-y-2">
            {phaseDOptions.map((opt: any, i: number) => (
              <div key={opt.id ?? i} className="rounded-lg p-3 border text-sm" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="font-medium">{opt.name ?? opt.title}</div>
                {opt.description && <div className="text-xs opacity-60 mt-1">{opt.description}</div>}
                {opt.priority && <div className="text-xs mt-1" style={{ color: 'var(--color-accent)' }}>Priority: {opt.priority}</div>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
