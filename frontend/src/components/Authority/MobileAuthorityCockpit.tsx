/**
 * Plan 8B — Mobile Authority Cockpit
 *
 * Compact but capability-equivalent mobile view of Plan 8 authority state.
 * Uses direct fetch with the mobile backend URL + API key (same as MobilePage).
 *
 * Sections:
 *   - Authority status + emergency stop indicator
 *   - Emergency stop / clear control
 *   - Pending approvals (approve/deny)
 *   - Quick risk classifier
 *   - Recent audit trail (compact)
 *   - Tier summary
 */

import { useCallback, useEffect, useState } from 'react';
import type { AuthorityStatus, ApprovalRecord, AuditEntry, RiskProfile } from '../../lib/authority-api';

// ---------------------------------------------------------------------------
// Mobile fetch helper — uses explicit backend URL + API key
// ---------------------------------------------------------------------------

async function mobileFetch<T>(
  backendUrl: string,
  apiKey: string,
  path: string,
  opts?: RequestInit,
): Promise<T | null> {
  try {
    const base = backendUrl.replace(/\/$/, '');
    const url = base ? `${base}${path}` : path;
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;
    if (opts?.body) headers['Content-Type'] = 'application/json';
    const res = await fetch(url, { ...opts, headers });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Mobile style tokens
// ---------------------------------------------------------------------------

const M = {
  surface: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 90%, transparent)',
  border: 'color-mix(in srgb, var(--color-border, #333) 70%, transparent)',
  text: 'var(--color-text, #eee)',
  textMuted: 'var(--color-text-muted, #888)',
  green: 'var(--color-success, #22c55e)',
  red: 'var(--color-error, #ef4444)',
  yellow: 'var(--color-warn, #f59e0b)',
  accent: 'var(--color-accent, #4fd1ff)',
};

const TIER_COLORS_M: Record<number, string> = {
  0: '#a6e3a1', 1: '#94e2d5', 2: '#89b4fa',
  3: '#f9e2af', 4: '#fab387', 5: '#f38588',
};
const RISK_COLORS_M: Record<string, string> = {
  low: '#a6e3a1', medium: '#f9e2af', high: '#fab387', critical: '#f38588',
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function MobileRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: `1px solid ${M.border}`, fontSize: 12 }}>
      <span style={{ color: M.textMuted }}>{label}</span>
      <span style={{ color: color ?? M.text, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function MobileEmptyState({ msg }: { msg: string }) {
  return <div style={{ fontSize: 12, color: M.textMuted, textAlign: 'center', padding: '12px 0' }}>{msg}</div>;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface Props {
  backendUrl: string;
  apiKey: string;
}

export function MobileAuthorityCockpit({ backendUrl, apiKey }: Props) {
  const [status, setStatus] = useState<AuthorityStatus | null>(null);
  const [pending, setPending] = useState<ApprovalRecord[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [emergencyBusy, setEmergencyBusy] = useState(false);
  const [toast, setToast] = useState('');
  const [classifyInput, setClassifyInput] = useState('');
  const [classifyResult, setClassifyResult] = useState<RiskProfile | null>(null);
  const [classifyLoading, setClassifyLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  const fetch_ = useCallback(
    <T,>(path: string, opts?: RequestInit) => mobileFetch<T>(backendUrl, apiKey, path, opts),
    [backendUrl, apiKey],
  );

  const loadAll = useCallback(async () => {
    setLoading(true);
    const [s, p, a] = await Promise.all([
      fetch_<AuthorityStatus>('/v1/authority/status'),
      fetch_<{ approvals: ApprovalRecord[] }>('/v1/authority/approvals/pending'),
      fetch_<{ entries: AuditEntry[] }>('/v1/authority/audit?limit=5'),
    ]);
    setStatus(s);
    setPending(p?.approvals ?? []);
    setAudit(a?.entries ?? []);
    setLoading(false);
  }, [fetch_]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleActivateStop = async () => {
    setEmergencyBusy(true);
    const r = await fetch_<{ active: boolean; revoked_approvals_count: number }>(
      '/v1/authority/emergency-stop/set',
      { method: 'POST', body: JSON.stringify({ activated_by: 'mobile_cockpit', reason: 'Activated via mobile' }) },
    );
    setEmergencyBusy(false);
    if (r) { showToast(`Emergency stop activated. ${r.revoked_approvals_count} approvals revoked.`); loadAll(); }
    else showToast('Emergency stop failed.');
  };

  const handleClearStop = async () => {
    setEmergencyBusy(true);
    const r = await fetch_<{ active: boolean }>(
      '/v1/authority/emergency-stop/clear',
      { method: 'POST', body: JSON.stringify({ cleared_by: 'mobile_cockpit' }) },
    );
    setEmergencyBusy(false);
    if (r) { showToast('Emergency stop cleared.'); loadAll(); }
    else showToast('Clear failed.');
  };

  const handleGrant = async (id: string) => {
    await fetch_(`/v1/authority/approvals/${id}/grant`, {
      method: 'POST',
      body: JSON.stringify({ expires_in_seconds: 3600 }),
    });
    showToast('Granted.');
    loadAll();
  };

  const handleDeny = async (id: string) => {
    await fetch_(`/v1/authority/approvals/${id}/deny`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'denied via mobile cockpit' }),
    });
    showToast('Denied.');
    loadAll();
  };

  const handleClassify = async () => {
    if (!classifyInput.trim()) return;
    setClassifyLoading(true);
    const r = await fetch_<RiskProfile>('/v1/authority/classify', {
      method: 'POST',
      body: JSON.stringify({ action_type: classifyInput.trim() }),
    });
    setClassifyResult(r);
    setClassifyLoading(false);
  };

  const isStop = status?.emergency_stop_active ?? false;
  const stopBorderColor = isStop
    ? 'color-mix(in srgb, var(--color-error, #ef4444) 30%, transparent)'
    : 'color-mix(in srgb, var(--color-border, #333) 70%, transparent)';

  return (
    <section
      style={{
        background: M.surface,
        backdropFilter: 'blur(16px)',
        border: `1px solid ${stopBorderColor}`,
        borderRadius: 14,
        padding: '14px 16px',
        marginTop: 12,
      }}
    >
      {/* Toast */}
      {toast && (
        <div style={{ position: 'fixed', bottom: 20, left: '50%', transform: 'translateX(-50%)', background: '#313244', color: '#cdd6f4', padding: '8px 16px', borderRadius: 8, fontSize: 13, zIndex: 9999 }}>
          {toast}
        </div>
      )}

      {/* Header */}
      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, cursor: 'pointer' }}
        onClick={() => setExpanded((e) => !e)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
              background: isStop ? M.red : M.green,
              boxShadow: `0 0 6px ${isStop ? M.red : M.green}`,
            }}
          />
          <span style={{ fontSize: 14, fontWeight: 700, color: M.text }}>
            Authority Cockpit
          </span>
          {isStop && (
            <span style={{ fontSize: 10, color: M.red, fontWeight: 700, padding: '1px 6px', background: 'rgba(239,68,68,0.15)', borderRadius: 4 }}>
              STOP ACTIVE
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {pending.length > 0 && (
            <span style={{ fontSize: 11, color: M.yellow, fontWeight: 600 }}>
              {pending.length} pending
            </span>
          )}
          <span style={{ fontSize: 11, color: M.textMuted }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Collapsed summary */}
      {!expanded && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {[
            { label: 'Status', val: isStop ? '🔴 STOP' : '🟢 OK', color: isStop ? M.red : M.green },
            { label: 'Pending', val: String(status?.pending_approvals_count ?? '—'), color: M.text },
            { label: 'Audit', val: String(status?.recent_audit_count ?? '—'), color: M.text },
          ].map((item) => (
            <div key={item.label} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 6, padding: '5px 9px', flex: '1 0 80px' }}>
              <div style={{ fontSize: 10, color: M.textMuted }}>{item.label}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: item.color }}>{item.val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Expanded content */}
      {expanded && (
        <div>
          {loading && <div style={{ fontSize: 12, color: M.textMuted, padding: '8px 0' }}>Loading authority data…</div>}

          {/* Emergency stop */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: M.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              Emergency Stop
            </div>
            <div
              style={{
                background: isStop ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${isStop ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 8,
                padding: '8px 10px',
                marginBottom: 8,
                fontSize: 12,
                color: isStop ? M.red : M.green,
                fontWeight: 600,
              }}
            >
              {isStop ? '🔴 EMERGENCY STOP ACTIVE — Tier 2+ actions blocked' : '🟢 No emergency stop active'}
            </div>
            <div style={{ fontSize: 11, color: M.textMuted, marginBottom: 6 }}>
              ⚠ Emergency stop blocks all Tier 2+ actions and revokes active approvals.
            </div>
            {!isStop ? (
              <button
                onClick={handleActivateStop}
                disabled={emergencyBusy}
                style={{
                  background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
                  color: M.red, borderRadius: 6, padding: '7px 14px',
                  fontSize: 12, fontWeight: 700, cursor: emergencyBusy ? 'not-allowed' : 'pointer',
                  width: '100%', opacity: emergencyBusy ? 0.6 : 1,
                }}
              >
                {emergencyBusy ? 'Activating…' : '🛑 Activate Emergency Stop'}
              </button>
            ) : (
              <button
                onClick={handleClearStop}
                disabled={emergencyBusy}
                style={{
                  background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)',
                  color: M.green, borderRadius: 6, padding: '7px 14px',
                  fontSize: 12, fontWeight: 700, cursor: emergencyBusy ? 'not-allowed' : 'pointer',
                  width: '100%', opacity: emergencyBusy ? 0.6 : 1,
                }}
              >
                {emergencyBusy ? 'Clearing…' : '✅ Clear Emergency Stop'}
              </button>
            )}
          </div>

          {/* Pending approvals */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: M.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              Pending Approvals ({pending.length})
            </div>
            {pending.length === 0 ? (
              <MobileEmptyState msg="No pending approvals." />
            ) : (
              pending.map((a) => (
                <div
                  key={a.approval_id}
                  style={{
                    background: 'rgba(249,226,175,0.06)', border: '1px solid rgba(249,226,175,0.2)',
                    borderRadius: 8, padding: '8px 10px', marginBottom: 6,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: M.text }}>{a.action_type}</span>
                    <span style={{ fontSize: 10, color: RISK_COLORS_M[a.risk_level] ?? M.textMuted, fontWeight: 700 }}>
                      {a.risk_level.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: M.textMuted, marginBottom: 6 }}>
                    Tier {a.tier} · {a.requester}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => handleGrant(a.approval_id)}
                      style={{
                        flex: 1, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)',
                        color: M.green, borderRadius: 5, padding: '5px 0', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                      }}
                    >Grant</button>
                    <button
                      onClick={() => handleDeny(a.approval_id)}
                      style={{
                        flex: 1, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
                        color: M.red, borderRadius: 5, padding: '5px 0', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                      }}
                    >Deny</button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Risk classifier */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: M.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              Risk Classifier (No execution)
            </div>
            <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
              <input
                value={classifyInput}
                onChange={(e) => setClassifyInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleClassify()}
                placeholder="Action type (e.g. file_write)"
                style={{
                  flex: 1, padding: '6px 8px', fontSize: 12, borderRadius: 6,
                  background: 'var(--color-surface, #1a1a1c)',
                  color: M.text, border: `1px solid ${M.border}`,
                }}
              />
              <button
                onClick={handleClassify}
                disabled={classifyLoading || !classifyInput.trim()}
                style={{
                  background: 'rgba(79,209,255,0.1)', border: '1px solid rgba(79,209,255,0.25)',
                  color: M.accent, borderRadius: 6, padding: '0 12px', fontSize: 12,
                  fontWeight: 600, cursor: classifyLoading ? 'not-allowed' : 'pointer',
                }}
              >
                {classifyLoading ? '…' : 'Check'}
              </button>
            </div>
            {classifyResult && (
              <div
                style={{
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 7, padding: '8px 10px', fontSize: 12,
                  borderLeft: `3px solid ${TIER_COLORS_M[classifyResult.recommended_tier] ?? M.textMuted}`,
                }}
              >
                <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                  <span style={{ color: TIER_COLORS_M[classifyResult.recommended_tier] ?? M.text, fontWeight: 700 }}>
                    Tier {classifyResult.recommended_tier}
                  </span>
                  <span style={{ color: RISK_COLORS_M[classifyResult.risk_label] ?? M.text, fontWeight: 600 }}>
                    {classifyResult.risk_label.toUpperCase()}
                  </span>
                  <span style={{ color: M.textMuted }}>score: {classifyResult.risk_score}/100</span>
                </div>
                <MobileRow label="Category" value={classifyResult.action_category} />
                <MobileRow label="Reversibility" value={classifyResult.reversibility} />
                <MobileRow label="Approval req." value={classifyResult.user_confirmation_required ? 'Yes' : 'No'} />
                {classifyResult.irreversible_warning && (
                  <div style={{ fontSize: 11, color: M.red, marginTop: 4 }}>⚠ {classifyResult.irreversible_warning}</div>
                )}
              </div>
            )}
          </div>

          {/* Recent audit */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: M.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              Recent Audit (5 latest)
            </div>
            {audit.length === 0 ? (
              <MobileEmptyState msg="No audit entries yet." />
            ) : (
              audit.map((e) => (
                <div
                  key={e.audit_id}
                  style={{
                    display: 'flex', justifyContent: 'space-between',
                    padding: '4px 0', borderBottom: `1px solid ${M.border}`,
                    fontSize: 11, gap: 8,
                  }}
                >
                  <span style={{ color: M.textMuted, whiteSpace: 'nowrap' }}>
                    {e.iso_ts?.slice(11, 19) ?? new Date(e.ts * 1000).toISOString().slice(11, 19)}
                  </span>
                  <span style={{ color: M.text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.action_type}
                  </span>
                  <span style={{ color: RISK_COLORS_M[e.risk_level] ?? M.textMuted, fontWeight: 600 }}>
                    {e.risk_level}
                  </span>
                  <span
                    style={{
                      color: e.execution_status === 'success' ? M.green : e.execution_status === 'blocked' ? M.red : M.textMuted,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {e.execution_status}
                  </span>
                </div>
              ))
            )}
          </div>

          {/* Tier summary */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: M.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              Tier Summary
            </div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {[
                { t: 0, label: 'Read-only', mode: 'auto' },
                { t: 1, label: 'Draft', mode: 'auto' },
                { t: 2, label: 'Low-risk', mode: '1x' },
                { t: 3, label: 'Med-write', mode: '1x' },
                { t: 4, label: 'High-risk', mode: 'step-up' },
                { t: 5, label: 'PROHIBIT', mode: 'blocked' },
              ].map(({ t, label, mode }) => (
                <div
                  key={t}
                  style={{
                    background: `${TIER_COLORS_M[t]}22`, border: `1px solid ${TIER_COLORS_M[t]}44`,
                    borderRadius: 5, padding: '4px 7px', fontSize: 10, textAlign: 'center',
                  }}
                >
                  <div style={{ color: TIER_COLORS_M[t], fontWeight: 700 }}>T{t}</div>
                  <div style={{ color: M.textMuted }}>{label}</div>
                  <div style={{ color: M.textMuted, fontSize: 9 }}>{mode}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
