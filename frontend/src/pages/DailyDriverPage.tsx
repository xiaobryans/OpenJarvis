import React, { useEffect, useState } from 'react'
import { Star, AlertTriangle, XCircle } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function DailyDriverPage() {
  const [status, setStatus] = useState<any>(null)
  const [checklist, setChecklist] = useState<any[]>([])
  const [blockers, setBlockers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/daily-driver/status').then(r => r.json()),
      apiFetch('/v1/daily-driver/checklist').then(r => r.json()),
      apiFetch('/v1/daily-driver/blockers').then(r => r.json()),
    ])
      .then(([s, c, b]) => {
        setStatus(s)
        setChecklist(Array.isArray(c) ? c : (c?.checklist ?? []))
        setBlockers(Array.isArray(b) ? b : (b?.blockers ?? []))
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading daily-driver certification...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const certified = status?.certified ?? false
  const certificationStatus = status?.certification_status ?? 'pending'
  const total = checklist.length
  const certifiedCount = 0 // always 0 — not certified
  const pending = checklist.filter(c => c.status === 'pending' || !c.passed).length

  const severityColor = (sev: string) => {
    if (sev === 'critical' || sev === 'high') return 'var(--color-danger, #f38ba8)'
    if (sev === 'medium') return 'var(--color-warning, #f9e2af)'
    return 'var(--color-success, #a6e3a1)'
  }

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <Star size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">Daily-Driver Certification Harness</h1>
      </div>

      {/* Certification status — not certified */}
      <div className="rounded-lg p-4 text-center" style={{ background: 'var(--color-danger, #f38ba8)', color: '#3a0a0a' }}>
        <div className="text-lg font-bold">Certification Status: {certificationStatus.toUpperCase()}</div>
        <div className="text-sm mt-1">Not certified as daily driver — pending validation</div>
      </div>

      {/* Auto-certification blocked banner */}
      <div className="rounded-lg p-3 text-sm flex items-center gap-2" style={{ background: 'var(--color-warning, #f9e2af)', color: '#5c4a00' }}>
        <AlertTriangle size={16} />
        <span><strong>Auto-certification blocked</strong> — Certification requires manual review. No agent can self-certify.</span>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Items', value: total, color: 'var(--color-text)' },
          { label: 'Certified', value: certifiedCount, color: 'var(--color-success, #a6e3a1)' },
          { label: 'Pending', value: pending, color: 'var(--color-warning, #f9e2af)' },
          { label: 'Blockers', value: blockers.length, color: blockers.length > 0 ? 'var(--color-danger, #f38ba8)' : 'var(--color-text)' },
        ].map(stat => (
          <div key={stat.label} className="rounded-lg p-3 text-center" style={{ background: 'var(--color-surface)' }}>
            <div className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</div>
            <div className="text-xs opacity-60 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Checklist */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Certification Checklist</h2>
        {checklist.length === 0 ? (
          <p className="text-sm opacity-60">No checklist items found.</p>
        ) : (
          <div className="space-y-2">
            {checklist.map((item: any, i: number) => (
              <div key={item.id ?? i} className="rounded-lg p-3 border flex items-center gap-3" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="flex-1">
                  <div className="text-sm font-medium">{item.name ?? item.label}</div>
                  {item.description && <div className="text-xs opacity-60 mt-0.5">{item.description}</div>}
                </div>
                {item.severity && (
                  <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: severityColor(item.severity), color: '#1a1a1a' }}>
                    {item.severity}
                  </span>
                )}
                <span className="text-xs px-2 py-0.5 rounded" style={{ background: item.passed ? 'var(--color-success, #a6e3a1)' : 'var(--color-warning, #f9e2af)', color: '#1a1a1a' }}>
                  {item.passed ? 'Pass' : 'Pending'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Blockers */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Active Blockers</h2>
        {blockers.length === 0 ? (
          <p className="text-sm opacity-60">No blockers found.</p>
        ) : (
          <div className="space-y-2">
            {blockers.map((b: any, i: number) => (
              <div key={b.id ?? i} className="rounded-lg p-3 border flex items-center gap-3" style={{ borderColor: 'var(--color-danger, #f38ba8)', background: 'var(--color-surface)' }}>
                <XCircle size={16} style={{ color: 'var(--color-danger, #f38ba8)', flexShrink: 0 }} />
                <div className="flex-1">
                  <div className="text-sm font-medium">{b.name ?? b.description}</div>
                  {b.resolution && <div className="text-xs opacity-60 mt-0.5">Resolution: {b.resolution}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
