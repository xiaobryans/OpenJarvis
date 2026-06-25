import React, { useEffect, useState } from 'react'
import { Smartphone, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function IOSReadinessPage() {
  const [status, setStatus] = useState<any>(null)
  const [prereqs, setPrereqs] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/ios-readiness/status').then(r => r.json()),
      apiFetch('/v1/ios-readiness/prerequisites').then(r => r.json()),
    ])
      .then(([s, p]) => { setStatus(s); setPrereqs(p) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6" style={{ color: 'var(--color-text)' }}>Loading iOS readiness...</div>
  if (error) return <div className="p-6" style={{ color: 'var(--color-danger, #f38ba8)' }}>Error: {error}</div>

  const prereqList: any[] = prereqs?.prerequisites ?? []
  const xcodePresent = status?.xcode_present ?? false
  const cocoapodsPresent = status?.cocoapods_present ?? false
  const iosRustTargetsCount = status?.ios_rust_targets_count ?? 0
  const tauriIosDeferred = status?.tauri_ios_init_deferred ?? true
  const nativeIosAppReady = status?.native_ios_app_ready ?? false
  const clearedByBryan: any[] = prereqs?.cleared_by_bryan ?? []

  return (
    <div className="p-6 space-y-6" style={{ color: 'var(--color-text)' }}>
      <div className="flex items-center gap-3">
        <Smartphone size={24} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-2xl font-bold">iOS / Mobile App Readiness Gate</h1>
      </div>

      {/* native_ios_app_ready: No prominently */}
      <div className="rounded-lg p-4 text-center" style={{ background: 'var(--color-danger, #f38ba8)', color: '#3a0a0a' }}>
        <div className="text-lg font-bold">Native iOS App Ready: No</div>
        <div className="text-sm mt-1">iOS app is not yet built or distributed</div>
      </div>

      {/* tauri_ios_init_deferred banner */}
      {tauriIosDeferred && (
        <div className="rounded-lg p-3 text-sm flex items-center gap-2" style={{ background: 'var(--color-warning, #f9e2af)', color: '#5c4a00' }}>
          <AlertTriangle size={16} />
          <span><strong>Tauri iOS init deferred</strong> — Bryan must explicitly authorize Tauri iOS initialization before proceeding.</span>
        </div>
      )}

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Xcode Present', value: xcodePresent ? 'Yes' : 'No', color: xcodePresent ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
          { label: 'CocoaPods Present', value: cocoapodsPresent ? 'Yes' : 'No', color: cocoapodsPresent ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
          { label: 'iOS Rust Targets', value: iosRustTargetsCount, color: iosRustTargetsCount > 0 ? 'var(--color-success, #a6e3a1)' : 'var(--color-warning, #f9e2af)' },
          { label: 'iOS Ready', value: nativeIosAppReady ? 'Yes' : 'No', color: nativeIosAppReady ? 'var(--color-success, #a6e3a1)' : 'var(--color-danger, #f38ba8)' },
        ].map(stat => (
          <div key={stat.label} className="rounded-lg p-3 text-center" style={{ background: 'var(--color-surface)' }}>
            <div className="text-lg font-bold" style={{ color: stat.color }}>{String(stat.value)}</div>
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

      {/* Prerequisites cleared by Bryan */}
      {clearedByBryan.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">Prerequisites Cleared by Bryan</h2>
          <div className="space-y-2">
            {clearedByBryan.map((item: any, i: number) => (
              <div key={i} className="rounded-lg p-3 border flex items-center gap-2 text-sm" style={{ borderColor: 'var(--color-surface)', background: 'var(--color-surface)' }}>
                <CheckCircle size={14} style={{ color: 'var(--color-success, #a6e3a1)' }} />
                <span>{typeof item === 'string' ? item : item.name}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
