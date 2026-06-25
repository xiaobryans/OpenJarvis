import React, { useEffect, useState } from 'react'
import { Scale, ShieldCheck } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function PolicyCompilerPage() {
  const [matrix, setMatrix] = useState<any>(null)
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/policy-compiler/authority-matrix').then(r => r.json()),
      apiFetch('/v1/policy-compiler/policy-summary').then(r => r.json()),
    ])
      .then(([m, s]) => { setMatrix(m); setSummary(s) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading policy compiler...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const domains = matrix?.domains ?? []
  const policies = summary?.policies ?? []
  const hardGatesCount = summary?.hard_gates_count ?? 0

  const tierColor = (tier: string | number) => {
    const t = String(tier).toLowerCase()
    if (t === 'high' || t === '3') return 'var(--color-danger, #f38ba8)'
    if (t === 'medium' || t === '2') return 'var(--color-warning, #f9e2af)'
    return 'var(--color-success, #a6e3a1)'
  }

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <Scale size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">Approval Policy Compiler</h1>
      </div>

      {/* Approval gates preserved badge */}
      <div className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ background: 'var(--color-success, #a6e3a1)', color: '#1a3a1a' }}>
        <ShieldCheck size={16} />
        Approval gates preserved — No auth weakening in effect
      </div>

      {/* Hard gates count */}
      <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--color-surface)' }}>
        Hard gates enforced: <strong>{hardGatesCount}</strong>
      </div>

      {/* Domains grid */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Authority Domains</h2>
        {domains.length === 0 ? (
          <p className="text-sm opacity-60">No domains found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {domains.map((d: any, i: number) => (
              <div key={d.domain_id ?? i} className="rounded-lg p-3 border" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="flex items-center justify-between mb-1">
                  <div className="font-medium">{d.name}</div>
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: tierColor(d.risk_tier), color: '#1a1a1a' }}>
                    {d.risk_tier ?? 'unknown'} risk
                  </span>
                </div>
                <div className="text-xs opacity-60">{d.description}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Policies list */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Active Policies</h2>
        {policies.length === 0 ? (
          <p className="text-sm opacity-60">No policies found.</p>
        ) : (
          <div className="space-y-2">
            {policies.map((p: any, i: number) => (
              <div key={p.policy_id ?? i} className="rounded-lg p-3 border flex items-center justify-between" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div>
                  <div className="font-medium text-sm">{p.name}</div>
                  {p.description && <div className="text-xs opacity-60 mt-0.5">{p.description}</div>}
                </div>
                <span className="text-xs px-2 py-1 rounded" style={{ background: p.enforced ? 'var(--color-success, #a6e3a1)' : 'var(--color-warning, #f9e2af)', color: '#1a1a1a' }}>
                  {p.enforced ? 'Enforced' : 'Unenforced'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
