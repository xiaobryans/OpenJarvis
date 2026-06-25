import React, { useEffect, useState } from 'react'
import { ShieldCheck, CheckCircle, XCircle } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function SigningReadinessPage() {
  const [status, setStatus] = useState<any>(null)
  const [prereqs, setPrereqs] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/signing-readiness/status').then(r => r.json()),
      apiFetch('/v1/signing-readiness/prerequisites').then(r => r.json()),
    ])
      .then(([s, p]) => { setStatus(s); setPrereqs(p) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading signing readiness...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const prereqList: any[] = prereqs?.prerequisites ?? []
  const notarytoolPresent = status?.notarytool_present ?? false
  const notarizationDeferred = status?.notarization_deferred ?? true
  const credsPresent = status?.all_creds_present ?? false
  const signingCredsPresent = status?.signing_creds_present ?? false
  const buildArtifactPresent = status?.build_artifact_present ?? false

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <ShieldCheck size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">macOS Signing / Notarization Readiness Gate</h1>
      </div>

      {/* No credential values badge */}
      <div className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ background: 'var(--color-success, #a6e3a1)', color: '#1a3a1a' }}>
        <ShieldCheck size={16} />
        No credential values in response — presence-only reporting
      </div>

      {/* Notarization deferred banner */}
      {notarizationDeferred && (
        <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--color-warning, #f9e2af)', color: '#5c4a00' }}>
          <strong>Notarization deferred</strong> — No build artifact present. Notarization will run only after a signed Tauri build is produced.
        </div>
      )}

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Notarytool Present', value: notarytoolPresent ? 'Yes' : 'No', color: notarytoolPresent ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
          { label: 'Signing Creds', value: signingCredsPresent ? 'Present' : 'Missing', color: signingCredsPresent ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
          { label: 'All Creds Present', value: credsPresent ? 'Yes' : 'No', color: credsPresent ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
          { label: 'Build Artifact', value: buildArtifactPresent ? 'Present' : 'None', color: buildArtifactPresent ? 'var(--color-success, #a6e3a1)' : 'var(--color-warning, #f9e2af)' },
        ].map(stat => (
          <div key={stat.label} className="rounded-lg p-3 text-center" style={{ background: 'var(--color-surface)' }}>
            <div className="text-lg font-bold" style={{ color: stat.color }}>{stat.value}</div>
            <div className="text-xs opacity-60 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Prerequisites checklist */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Prerequisites Checklist</h2>
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
    </div>
  )
}
