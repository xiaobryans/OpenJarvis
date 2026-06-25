import React, { useEffect, useState } from 'react'
import { FlaskConical, AlertTriangle } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function FinalSmokePage() {
  const [checklist, setChecklist] = useState<any[]>([])
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/final-smoke/checklist').then(r => r.json()),
      apiFetch('/v1/final-smoke/status').then(r => r.json()),
    ])
      .then(([c, s]) => {
        setChecklist(Array.isArray(c) ? c : (c?.checklist ?? []))
        setStatus(s)
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading final smoke checklist...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const total = checklist.length
  const pending = checklist.filter(c => c.status === 'pending').length
  const blocked = checklist.filter(c => c.status === 'blocked').length
  const passed = checklist.filter(c => c.status === 'passed' || c.status === 'done').length

  const itemColor = (s: string) => {
    if (s === 'blocked') return 'var(--color-danger, #f38ba8)'
    if (s === 'pending') return 'var(--color-warning, #f9e2af)'
    if (s === 'passed' || s === 'done') return 'var(--color-success, #a6e3a1)'
    return 'var(--color-text)'
  }

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <FlaskConical size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">Core OS Final Smoke Orchestrator</h1>
      </div>

      {/* Manual proof required banner */}
      <div className="rounded-lg p-3 text-sm flex items-center gap-2" style={{ background: 'var(--color-warning, #f9e2af)', color: '#5c4a00' }}>
        <AlertTriangle size={16} />
        <span><strong>Manual proof required</strong> — Smoke tests are not automatically executed. Each item must be manually verified and confirmed.</span>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Items', value: total, color: 'var(--color-text)' },
          { label: 'Passed', value: passed, color: 'var(--color-success, #a6e3a1)' },
          { label: 'Pending', value: pending, color: 'var(--color-warning, #f9e2af)' },
          { label: 'Blocked', value: blocked, color: 'var(--color-danger, #f38ba8)' },
        ].map(stat => (
          <div key={stat.label} className="rounded-lg p-3 text-center" style={{ background: 'var(--color-surface)' }}>
            <div className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</div>
            <div className="text-xs opacity-60 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Checklist */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Smoke Checklist</h2>
        {checklist.length === 0 ? (
          <p className="text-sm opacity-60">No checklist items found.</p>
        ) : (
          <div className="space-y-2">
            {checklist.map((item: any, i: number) => (
              <div key={item.id ?? i} className="rounded-lg p-3 border flex items-center gap-3" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: itemColor(item.status) }} />
                <div className="flex-1">
                  <div className="text-sm font-medium">{item.name ?? item.label}</div>
                  {item.description && <div className="text-xs opacity-60 mt-0.5">{item.description}</div>}
                </div>
                <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: itemColor(item.status), color: '#1a1a1a' }}>
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
