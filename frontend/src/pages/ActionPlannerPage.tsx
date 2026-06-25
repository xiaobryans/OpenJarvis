import React, { useEffect, useState } from 'react'
import { GitBranch } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function ActionPlannerPage() {
  const [systems, setSystems] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/action-planner/systems').then(r => r.json()),
      apiFetch('/v1/action-planner/templates').then(r => r.json()),
    ])
      .then(([s, t]) => {
        setSystems(Array.isArray(s) ? s : (s?.systems ?? []))
        setTemplates(Array.isArray(t) ? t : (t?.templates ?? []))
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading action planner...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <GitBranch size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">Cross-System Action Planner</h1>
      </div>

      {/* Honesty banner */}
      <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--color-warning, #f9e2af)', color: '#5c4a00' }}>
        Dry-run only — No actions are executed automatically. All cross-system plans require explicit approval before execution.
      </div>

      {/* Systems grid */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Connected Systems</h2>
        {systems.length === 0 ? (
          <p className="text-sm opacity-60">No systems found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {systems.map((s: any, i: number) => (
              <div key={s.system_id ?? i} className="rounded-lg p-3 border" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div className="font-medium">{s.name}</div>
                <div className="text-sm opacity-70 mt-1">{s.status ?? s.description}</div>
                {s.capabilities && (
                  <div className="text-xs mt-1 opacity-60">{Array.isArray(s.capabilities) ? s.capabilities.join(', ') : s.capabilities}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Templates list */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Action Templates</h2>
        {templates.length === 0 ? (
          <p className="text-sm opacity-60">No templates found.</p>
        ) : (
          <div className="space-y-2">
            {templates.map((t: any, i: number) => (
              <div key={t.template_id ?? i} className="rounded-lg p-3 border flex items-center justify-between" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <div>
                  <div className="font-medium text-sm">{t.name}</div>
                  {t.description && <div className="text-xs opacity-60 mt-0.5">{t.description}</div>}
                </div>
                <div className="text-xs px-2 py-1 rounded" style={{ background: 'var(--color-bg)', color: 'var(--color-accent)' }}>
                  {t.steps?.length ?? t.step_count ?? 0} steps
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
