/**
 * Plan 8B — Authority Cockpit
 *
 * Sections:
 *   A. Status header — tier, emergency stop, counts, spend
 *   B. Permission tier matrix
 *   C. Pending approvals
 *   D. Emergency stop control
 *   E. Recent audit trail
 *   F. Risk classifier / action preview (classify-only, no execution)
 *   G. Rollback/recovery visibility
 *   H. Spend + secret guardrail status
 *   J. Loading / error / empty states throughout
 *
 * All data comes from real /v1/authority/* routes.
 * No secret values displayed. Emergency stop calls real backend routes.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Shield,
  ShieldAlert,
  ShieldOff,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Eye,
  Play,
  Zap,
  Lock,
  DollarSign,
  FileText,
  RotateCcw,
  XCircle,
  Info,
} from 'lucide-react';
import type {
  AuthorityStatus,
  TierDefinition,
  ApprovalRecord,
  AuditEntry,
  RiskProfile,
  PreviewResponse,
  SpendSummary,
  SecretPolicy,
  EmergencyStopStatus,
} from '../../lib/authority-api';
import {
  fetchAuthorityStatus,
  fetchTierMatrix,
  fetchPendingApprovals,
  fetchActiveApprovals,
  fetchRecentAudit,
  fetchEmergencyStopStatus,
  activateEmergencyStop,
  clearEmergencyStop,
  grantApproval,
  denyApproval,
  revokeApproval,
  classifyAction,
  previewAction,
  fetchSpendSummary,
  fetchSecretPolicy,
} from '../../lib/authority-api';

// ---------------------------------------------------------------------------
// Shared style tokens (matches existing Catppuccin Mocha palette)
// ---------------------------------------------------------------------------

const C = {
  bg: 'var(--color-bg, #1e1e2e)',
  surface: 'var(--color-surface, #313244)',
  surfaceAlt: 'var(--color-bg-secondary, #1e1e2e)',
  border: 'var(--color-border, #45475a)',
  text: 'var(--color-text, #cdd6f4)',
  textSec: 'var(--color-text-secondary, #a6adc8)',
  textTert: 'var(--color-text-tertiary, #585b70)',
  blue: '#89b4fa',
  green: '#a6e3a1',
  yellow: '#f9e2af',
  red: '#f38588',
  orange: '#fab387',
  mauve: '#cba6f7',
  teal: '#94e2d5',
} as const;

// ---------------------------------------------------------------------------
// Tier badge colors
// ---------------------------------------------------------------------------

const TIER_COLORS: Record<number, { bg: string; text: string; label: string }> = {
  0: { bg: '#a6e3a133', text: '#a6e3a1', label: 'T0' },
  1: { bg: '#94e2d533', text: '#94e2d5', label: 'T1' },
  2: { bg: '#89b4fa33', text: '#89b4fa', label: 'T2' },
  3: { bg: '#f9e2af33', text: '#f9e2af', label: 'T3' },
  4: { bg: '#fab38733', text: '#fab387', label: 'T4' },
  5: { bg: '#f3858833', text: '#f38588', label: 'T5' },
};

const RISK_COLORS: Record<string, string> = {
  low: '#a6e3a1',
  medium: '#f9e2af',
  high: '#fab387',
  critical: '#f38588',
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function TierBadge({ tier }: { tier: number }) {
  const c = TIER_COLORS[tier] ?? { bg: '#45475a33', text: '#a6adc8', label: `T${tier}` };
  return (
    <span
      style={{
        background: c.bg,
        color: c.text,
        padding: '1px 7px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.04em',
      }}
    >
      {c.label}
    </span>
  );
}

function RiskBadge({ level }: { level: string }) {
  const color = RISK_COLORS[level.toLowerCase()] ?? C.textSec;
  return (
    <span style={{ color, fontSize: 11, fontWeight: 600 }}>
      {level.toUpperCase()}
    </span>
  );
}

function StatusDot({ active, pulse = false }: { active: boolean; pulse?: boolean }) {
  const color = active ? C.red : C.green;
  return (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: color,
        boxShadow: `0 0 6px ${color}`,
        animation: pulse && active ? 'pulse 1.5s infinite' : undefined,
      }}
    />
  );
}

function SectionCard({
  title,
  icon,
  children,
  collapsible = false,
  defaultOpen = true,
  accent,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  accent?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${accent ?? C.border}`,
        borderRadius: 10,
        overflow: 'hidden',
        marginBottom: 12,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 14px',
          borderBottom: open ? `1px solid ${C.border}` : 'none',
          cursor: collapsible ? 'pointer' : 'default',
          background: accent ? `${accent}11` : undefined,
        }}
        onClick={collapsible ? () => setOpen((o) => !o) : undefined}
      >
        <span style={{ color: accent ?? C.blue }}>{icon}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.text, flex: 1 }}>{title}</span>
        {collapsible && (open ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
      </div>
      {open && <div style={{ padding: '12px 14px' }}>{children}</div>}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '20px 0',
        color: C.textTert,
        fontSize: 13,
      }}
    >
      <Info size={18} style={{ margin: '0 auto 6px', display: 'block', opacity: 0.5 }} />
      {message}
    </div>
  );
}

function LoadingRow() {
  return (
    <div style={{ color: C.textTert, fontSize: 12, padding: '8px 0' }}>
      <RefreshCw size={13} style={{ display: 'inline', marginRight: 6, opacity: 0.5 }} />
      Loading…
    </div>
  );
}

function ErrorRow({ msg }: { msg: string }) {
  return (
    <div style={{ color: C.red, fontSize: 12, padding: '6px 0' }}>
      <XCircle size={13} style={{ display: 'inline', marginRight: 6 }} />
      {msg}
    </div>
  );
}

function Row({ label, value, valueColor }: { label: string; value: React.ReactNode; valueColor?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '5px 0',
        borderBottom: `1px solid ${C.border}22`,
        fontSize: 13,
      }}
    >
      <span style={{ color: C.textSec }}>{label}</span>
      <span style={{ color: valueColor ?? C.text, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section A — Status header
// ---------------------------------------------------------------------------

function StatusHeader({
  status,
  onRefresh,
}: {
  status: AuthorityStatus | null;
  onRefresh: () => void;
}) {
  const isStop = status?.emergency_stop_active ?? false;
  return (
    <div
      style={{
        background: isStop
          ? `linear-gradient(90deg, ${C.red}22 0%, ${C.surface} 100%)`
          : `linear-gradient(90deg, ${C.blue}11 0%, ${C.surface} 100%)`,
        border: `1px solid ${isStop ? C.red : C.blue}55`,
        borderRadius: 10,
        padding: '14px 16px',
        marginBottom: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isStop ? (
            <ShieldAlert size={20} style={{ color: C.red }} />
          ) : (
            <Shield size={20} style={{ color: C.blue }} />
          )}
          <span style={{ fontSize: 16, fontWeight: 700, color: C.text }}>
            Authority Cockpit
          </span>
          <span style={{ fontSize: 11, color: C.textTert }}>
            {status?.plan_8_version ?? 'Plan 8'}
          </span>
        </div>
        <button
          onClick={onRefresh}
          style={{
            background: 'none',
            border: 'none',
            color: C.textSec,
            cursor: 'pointer',
            padding: 4,
          }}
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {status == null ? (
        <div style={{ color: C.textTert, fontSize: 13 }}>
          <XCircle size={13} style={{ display: 'inline', marginRight: 6 }} />
          Backend unavailable — /v1/authority/status unreachable
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
          {[
            {
              label: 'Status',
              value: isStop ? '🔴 EMERGENCY STOP' : '🟢 Operational',
              color: isStop ? C.red : C.green,
            },
            {
              label: 'Pending Approvals',
              value: String(status.pending_approvals_count),
              color: status.pending_approvals_count > 0 ? C.yellow : C.textSec,
            },
            {
              label: 'Active Approvals',
              value: String(status.active_approvals_count),
              color: C.textSec,
            },
            {
              label: 'Audit Count',
              value: String(status.recent_audit_count),
              color: C.textSec,
            },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                background: `${C.bg}88`,
                border: `1px solid ${C.border}33`,
                borderRadius: 6,
                padding: '6px 10px',
              }}
            >
              <div style={{ fontSize: 11, color: C.textTert, marginBottom: 2 }}>{item.label}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: item.color }}>{item.value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section B — Permission tier matrix
// ---------------------------------------------------------------------------

function TierMatrix({ tiers }: { tiers: TierDefinition[] | null }) {
  if (!tiers) return <LoadingRow />;
  if (tiers.length === 0) return <EmptyState message="No tier data from backend." />;

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {['Tier', 'Label', 'Approval', 'Creds', 'Spend', 'Ext Sends', 'Deploy'].map((h) => (
              <th
                key={h}
                style={{
                  padding: '6px 8px',
                  textAlign: 'left',
                  borderBottom: `1px solid ${C.border}`,
                  color: C.blue,
                  fontWeight: 600,
                  fontSize: 11,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  whiteSpace: 'nowrap',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tiers.map((t) => (
            <tr key={t.tier} style={{ borderBottom: `1px solid ${C.border}22` }}>
              <td style={{ padding: '6px 8px' }}>
                <TierBadge tier={t.tier} />
              </td>
              <td style={{ padding: '6px 8px', color: C.text, maxWidth: 140 }}>
                <span style={{ fontSize: 12 }}>{t.label}</span>
              </td>
              <td style={{ padding: '6px 8px' }}>
                <span
                  style={{
                    fontSize: 11,
                    color:
                      t.required_approval_mode === 'auto_allow'
                        ? C.green
                        : t.required_approval_mode === 'prohibited'
                        ? C.red
                        : t.required_approval_mode === 'step_up'
                        ? C.orange
                        : C.yellow,
                    fontWeight: 600,
                  }}
                >
                  {t.required_approval_mode}
                </span>
              </td>
              <td style={{ padding: '6px 8px', color: t.credentials_allowed ? C.yellow : C.textTert }}>
                {t.credentials_allowed ? `✓ ${t.credential_scope}` : '—'}
              </td>
              <td style={{ padding: '6px 8px', color: t.spend_bearing_allowed ? C.orange : C.textTert }}>
                {t.spend_bearing_allowed ? `≤$${t.max_spend_per_action}` : '—'}
              </td>
              <td style={{ padding: '6px 8px', color: t.external_sends_allowed ? C.yellow : C.textTert }}>
                {t.external_sends_allowed ? '✓' : '—'}
              </td>
              <td style={{ padding: '6px 8px', color: t.production_deploy_allowed ? C.orange : C.textTert }}>
                {t.production_deploy_allowed ? '✓' : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8, fontSize: 11, color: C.textTert }}>
        T5 = Prohibited / Human-only. All autonomous execution blocked.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section C — Pending approvals
// ---------------------------------------------------------------------------

function ApprovalsList({
  approvals,
  loading,
  onGrant,
  onDeny,
}: {
  approvals: ApprovalRecord[] | null;
  loading: boolean;
  onGrant: (id: string) => void;
  onDeny: (id: string) => void;
}) {
  if (loading) return <LoadingRow />;
  if (!approvals) return <ErrorRow msg="Could not load approvals from backend." />;
  if (approvals.length === 0) {
    return <EmptyState message="No pending approvals. All authority requests have been resolved." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {approvals.map((a) => (
        <div
          key={a.approval_id}
          style={{
            background: `${C.bg}66`,
            border: `1px solid ${C.border}`,
            borderRadius: 7,
            padding: '10px 12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <TierBadge tier={a.tier} />
                <RiskBadge level={a.risk_level} />
                <span style={{ fontSize: 12, color: C.text, fontWeight: 500 }}>{a.action_type}</span>
              </div>
              <div style={{ fontSize: 12, color: C.textSec, marginBottom: 3 }}>
                {a.action_preview || '(no description)'}
              </div>
              {a.affected_files.length > 0 && (
                <div style={{ fontSize: 11, color: C.textTert }}>
                  Files: {a.affected_files.slice(0, 3).join(', ')}
                  {a.affected_files.length > 3 ? ` +${a.affected_files.length - 3} more` : ''}
                </div>
              )}
              {a.affected_systems.length > 0 && (
                <div style={{ fontSize: 11, color: C.textTert }}>
                  Systems: {a.affected_systems.join(', ')}
                </div>
              )}
              <div style={{ fontSize: 11, color: C.textTert, marginTop: 2 }}>
                Mode: {a.mode} · Requester: {a.requester}
                {a.expires_at && ` · Expires: ${a.expires_at.slice(0, 19)}`}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button
                onClick={() => onGrant(a.approval_id)}
                style={{
                  background: `${C.green}22`,
                  border: `1px solid ${C.green}55`,
                  color: C.green,
                  borderRadius: 5,
                  padding: '4px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Grant
              </button>
              <button
                onClick={() => onDeny(a.approval_id)}
                style={{
                  background: `${C.red}22`,
                  border: `1px solid ${C.red}55`,
                  color: C.red,
                  borderRadius: 5,
                  padding: '4px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Deny
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section D — Emergency stop control
// ---------------------------------------------------------------------------

function EmergencyStopControl({
  status,
  onActivate,
  onClear,
  busy,
}: {
  status: EmergencyStopStatus | null;
  onActivate: () => void;
  onClear: () => void;
  busy: boolean;
}) {
  const [reason, setReason] = useState('');

  if (!status) return <ErrorRow msg="Emergency stop status unavailable from backend." />;

  return (
    <div>
      <div
        style={{
          background: status.active ? `${C.red}15` : `${C.surface}`,
          border: `1px solid ${status.active ? C.red : C.border}55`,
          borderRadius: 8,
          padding: '12px 14px',
          marginBottom: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <StatusDot active={status.active} pulse />
          <span style={{ fontSize: 13, fontWeight: 600, color: status.active ? C.red : C.green }}>
            {status.active ? 'EMERGENCY STOP ACTIVE' : 'Emergency Stop: Inactive'}
          </span>
        </div>
        {status.active && (
          <div style={{ fontSize: 12, color: C.textSec, marginBottom: 4 }}>
            <div>Activated by: <strong style={{ color: C.text }}>{status.activated_by ?? 'unknown'}</strong></div>
            {status.reason && <div>Reason: {status.reason}</div>}
            {status.activated_at && <div>At: {status.activated_at.slice(0, 19)}</div>}
          </div>
        )}
        {!status.active && status.cleared_at && (
          <div style={{ fontSize: 12, color: C.textTert }}>
            Last cleared: {status.cleared_at.slice(0, 19)} by {status.cleared_by ?? 'unknown'}
          </div>
        )}
      </div>

      <div style={{ fontSize: 12, color: C.orange, marginBottom: 8 }}>
        <AlertTriangle size={12} style={{ display: 'inline', marginRight: 4 }} />
        Emergency stop blocks all Tier 2+ actions and revokes all active approvals.
        Tier 0/1 read-only operations remain unaffected.
      </div>

      {!status.active ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            style={{
              flex: 1,
              background: C.bg,
              border: `1px solid ${C.border}`,
              borderRadius: 5,
              color: C.text,
              padding: '5px 8px',
              fontSize: 12,
            }}
          />
          <button
            onClick={onActivate}
            disabled={busy}
            style={{
              background: `${C.red}22`,
              border: `1px solid ${C.red}88`,
              color: C.red,
              borderRadius: 5,
              padding: '6px 14px',
              fontSize: 12,
              fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.6 : 1,
            }}
          >
            {busy ? 'Activating…' : 'Activate Emergency Stop'}
          </button>
        </div>
      ) : (
        <button
          onClick={onClear}
          disabled={busy}
          style={{
            background: `${C.green}22`,
            border: `1px solid ${C.green}88`,
            color: C.green,
            borderRadius: 5,
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: 700,
            cursor: busy ? 'not-allowed' : 'pointer',
            opacity: busy ? 0.6 : 1,
          }}
        >
          {busy ? 'Clearing…' : 'Clear Emergency Stop'}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section E — Recent audit trail
// ---------------------------------------------------------------------------

function AuditTrail({ entries }: { entries: AuditEntry[] | null }) {
  if (!entries) return <ErrorRow msg="Could not load audit trail from backend." />;
  if (entries.length === 0) {
    return <EmptyState message="No audit entries yet. Authority events will appear here." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {entries.map((e) => (
        <div
          key={e.audit_id}
          style={{
            display: 'grid',
            gridTemplateColumns: '90px 1fr 70px 80px',
            gap: 8,
            padding: '6px 8px',
            borderRadius: 5,
            background: `${C.bg}55`,
            borderLeft: `3px solid ${
              e.execution_status === 'blocked'
                ? C.red
                : e.execution_status === 'success'
                ? C.green
                : e.execution_status === 'failed'
                ? C.orange
                : C.border
            }`,
            fontSize: 12,
          }}
        >
          <span style={{ color: C.textTert, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {e.iso_ts?.slice(11, 19) ?? new Date(e.ts * 1000).toISOString().slice(11, 19)}
          </span>
          <span style={{ color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {e.action_type}
            {e.affected_resource ? ` → ${e.affected_resource}` : ''}
          </span>
          <span>
            <RiskBadge level={e.risk_level} />
          </span>
          <span
            style={{
              color:
                e.execution_status === 'success'
                  ? C.green
                  : e.execution_status === 'blocked'
                  ? C.red
                  : e.execution_status === 'failed'
                  ? C.orange
                  : C.textSec,
              fontWeight: 500,
            }}
          >
            {e.execution_status}
          </span>
        </div>
      ))}
      <div style={{ fontSize: 11, color: C.textTert, marginTop: 4 }}>
        All records scrubbed — no secret values stored in audit log.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section F — Risk classifier / action preview (classify-only)
// ---------------------------------------------------------------------------

function RiskClassifier() {
  const [input, setInput] = useState('');
  const [profile, setProfile] = useState<RiskProfile | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const classify = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError('');
    setProfile(null);
    setPreview(null);
    try {
      const p = await classifyAction(input.trim());
      if (!p) { setError('Backend unavailable or action type not recognized.'); return; }
      setProfile(p);
    } catch {
      setError('Classification failed — backend error.');
    } finally {
      setLoading(false);
    }
  };

  const runPreview = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError('');
    setPreview(null);
    try {
      const p = await previewAction(input.trim(), `Preview for: ${input.trim()}`, true);
      if (!p) { setError('Preview failed — backend unavailable.'); return; }
      setPreview(p);
    } catch {
      setError('Preview failed — backend error.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ fontSize: 12, color: C.textSec, marginBottom: 8 }}>
        Test action classification without executing anything. Enter an action type to check its tier, risk, and approval requirements.
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && classify()}
          placeholder="e.g. file_write, billing_change, read, email_send…"
          style={{
            flex: 1,
            background: C.bg,
            border: `1px solid ${C.border}`,
            borderRadius: 5,
            color: C.text,
            padding: '7px 10px',
            fontSize: 12,
          }}
        />
        <button
          onClick={classify}
          disabled={loading || !input.trim()}
          style={{
            background: `${C.blue}22`,
            border: `1px solid ${C.blue}55`,
            color: C.blue,
            borderRadius: 5,
            padding: '0 12px',
            fontSize: 12,
            fontWeight: 600,
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <Eye size={12} />
          Classify
        </button>
        <button
          onClick={runPreview}
          disabled={loading || !input.trim()}
          style={{
            background: `${C.mauve}22`,
            border: `1px solid ${C.mauve}55`,
            color: C.mauve,
            borderRadius: 5,
            padding: '0 12px',
            fontSize: 12,
            fontWeight: 600,
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <Play size={12} />
          Preview
        </button>
      </div>

      {loading && <LoadingRow />}
      {error && <ErrorRow msg={error} />}

      {profile && (
        <div style={{ background: `${C.bg}66`, border: `1px solid ${C.border}`, borderRadius: 7, padding: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <TierBadge tier={profile.recommended_tier} />
            <RiskBadge level={profile.risk_label} />
            <span style={{ fontSize: 12, fontWeight: 600, color: C.text }}>{profile.action_type}</span>
            <span style={{ fontSize: 11, color: C.textTert }}>score: {profile.risk_score}/100</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 16px', fontSize: 12 }}>
            {[
              ['Category', profile.action_category],
              ['Destructive', profile.destructive_potential],
              ['External effect', profile.external_side_effect],
              ['Money impact', profile.money_impact],
              ['Credential impact', profile.credential_impact],
              ['Privacy impact', profile.privacy_impact],
              ['Reversibility', profile.reversibility],
              ['Confirmation req.', profile.user_confirmation_required ? 'Yes' : 'No'],
            ].map(([k, v]) => (
              <div key={k} style={{ color: C.textSec }}>
                <span>{k}: </span>
                <span style={{ color: C.text, fontWeight: 500 }}>{v}</span>
              </div>
            ))}
          </div>
          {profile.irreversible_warning && (
            <div style={{ marginTop: 6, fontSize: 11, color: C.red }}>
              <AlertTriangle size={11} style={{ display: 'inline', marginRight: 4 }} />
              {profile.irreversible_warning}
            </div>
          )}
        </div>
      )}

      {preview && (
        <div
          style={{
            background: `${C.bg}66`,
            border: `1px solid ${C.mauve}33`,
            borderRadius: 7,
            padding: 10,
            marginTop: 8,
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 600, color: C.mauve, marginBottom: 6 }}>
            <Eye size={12} style={{ display: 'inline', marginRight: 4 }} />
            Action Preview (DRY-RUN ONLY — nothing executed)
          </div>
          <Row label="Requires approval" value={preview.preview.requires_human_approval ? 'Yes' : 'No'} />
          <Row label="Rollback method" value={preview.preview.rollback_method} />
          <Row label="Rollback supported" value={preview.preview.rollback_supported ? 'Yes' : 'No'} />
          <Row label="Cost estimate" value={`$${preview.preview.cost_estimate.toFixed(3)}`} />
          {preview.preview.cost_unknown_warning && (
            <Row label="Cost warning" value={preview.preview.cost_unknown_warning} valueColor={C.orange} />
          )}
          {preview.preview.irreversible_warning && (
            <Row label="Irreversible" value="⚠ YES" valueColor={C.red} />
          )}
          {preview.preview.dry_run_result && (
            <div style={{ marginTop: 6, fontSize: 11, color: C.textSec }}>
              <span style={{ color: C.textTert }}>Dry-run: </span>
              {String(preview.preview.dry_run_result.what_would_happen ?? preview.preview.dry_run_result.status ?? 'completed')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section G — Rollback / recovery visibility
// ---------------------------------------------------------------------------

function RollbackVisibility({ approvals }: { approvals: ApprovalRecord[] | null }) {
  if (!approvals) return <ErrorRow msg="Rollback data unavailable — check approval records." />;

  const withRollback = approvals.filter((a) => a.rollback_plan);
  const withoutRollback = approvals.filter((a) => !a.rollback_plan);

  if (approvals.length === 0) {
    return <EmptyState message="No approval records with rollback metadata yet." />;
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
        <div style={{ background: `${C.green}11`, border: `1px solid ${C.green}33`, borderRadius: 6, padding: '8px 10px' }}>
          <div style={{ fontSize: 11, color: C.textTert, marginBottom: 2 }}>With Rollback Plan</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{withRollback.length}</div>
        </div>
        <div style={{ background: `${C.orange}11`, border: `1px solid ${C.orange}33`, borderRadius: 6, padding: '8px 10px' }}>
          <div style={{ fontSize: 11, color: C.textTert, marginBottom: 2 }}>Without Rollback Plan</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: withoutRollback.length > 0 ? C.orange : C.textSec }}>
            {withoutRollback.length}
          </div>
        </div>
      </div>
      <div style={{ fontSize: 12, color: C.textTert }}>
        <RotateCcw size={11} style={{ display: 'inline', marginRight: 4 }} />
        Rollback records stored in <code>~/.jarvis/authority_rollback.db</code>.
        File edits: automatic. External sends: impossible. Deploys: manual.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section H — Spend + secret guardrail
// ---------------------------------------------------------------------------

function SpendSecretPanel({
  spend,
  policy,
}: {
  spend: SpendSummary | null;
  policy: SecretPolicy | null;
}) {
  return (
    <div>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.orange, marginBottom: 6 }}>
          <DollarSign size={12} style={{ display: 'inline', marginRight: 4 }} />
          Spend Guardrail
        </div>
        {spend ? (
          <div>
            <Row
              label="Session spend"
              value={`$${spend.session_spend.toFixed(3)} / $${spend.session_budget.toFixed(2)}`}
              valueColor={spend.session_spend / spend.session_budget > 0.8 ? C.orange : C.green}
            />
            <Row
              label="Day spend"
              value={`$${spend.day_spend.toFixed(3)} / $${spend.daily_budget.toFixed(2)}`}
              valueColor={spend.day_spend / spend.daily_budget > 0.8 ? C.orange : C.green}
            />
            <Row label="Alert threshold" value={`${(spend.alert_threshold_pct * 100).toFixed(0)}%`} />
          </div>
        ) : (
          <ErrorRow msg="Spend summary unavailable from backend." />
        )}
      </div>

      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.mauve, marginBottom: 6 }}>
          <Lock size={12} style={{ display: 'inline', marginRight: 4 }} />
          Secret Policy
        </div>
        {policy ? (
          <div>
            {[
              ['Never print secrets', policy.never_print_secrets],
              ['Never commit secrets', policy.never_commit_secrets],
              ['No exposure in UI/logs', policy.never_expose_in_ui_or_logs],
              ['Audit by name/scope only', policy.audit_by_name_scope_not_value],
              ['Approval for high-risk creds', policy.require_approval_for_high_risk_credential_actions],
            ].map(([label, val]) => (
              <Row
                key={String(label)}
                label={String(label)}
                value={val ? '✓ Enforced' : '✗ Off'}
                valueColor={val ? C.green : C.red}
              />
            ))}
            <div style={{ fontSize: 11, color: C.textTert, marginTop: 6 }}>
              Token patterns scanned: {policy.token_patterns_scanned?.join(', ')}
            </div>
          </div>
        ) : (
          <ErrorRow msg="Secret policy unavailable from backend." />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AuthorityCockpit component
// ---------------------------------------------------------------------------

export function AuthorityCockpit() {
  const [status, setStatus] = useState<AuthorityStatus | null | 'loading'>('loading');
  const [tiers, setTiers] = useState<TierDefinition[] | null>(null);
  const [pending, setPending] = useState<ApprovalRecord[] | null>(null);
  const [active, setActive] = useState<ApprovalRecord[] | null>(null);
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [emergencyStatus, setEmergencyStatus] = useState<EmergencyStopStatus | null>(null);
  const [spend, setSpend] = useState<SpendSummary | null>(null);
  const [secretPolicy, setSecretPolicy] = useState<SecretPolicy | null>(null);

  const [pendingLoading, setPendingLoading] = useState(true);
  const [emergencyBusy, setEmergencyBusy] = useState(false);
  const [toast, setToast] = useState('');

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  const loadAll = useCallback(async () => {
    setStatus('loading');
    const [s, t, p, a, au, e, sp, sec] = await Promise.all([
      fetchAuthorityStatus(),
      fetchTierMatrix(),
      fetchPendingApprovals(),
      fetchActiveApprovals(),
      fetchRecentAudit(20),
      fetchEmergencyStopStatus(),
      fetchSpendSummary(),
      fetchSecretPolicy(),
    ]);
    setStatus(s);
    setTiers(t?.tiers ?? null);
    setPending(p?.approvals ?? null);
    setPendingLoading(false);
    setActive(a?.approvals ?? null);
    setAudit(au?.entries ?? null);
    setEmergencyStatus(e);
    setSpend(sp);
    setSecretPolicy(sec);
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleGrant = async (id: string) => {
    const r = await grantApproval(id);
    if (r) { showToast('Approval granted.'); loadAll(); }
    else showToast('Grant failed — backend error.');
  };

  const handleDeny = async (id: string) => {
    const r = await denyApproval(id, 'denied via cockpit');
    if (r) { showToast('Approval denied.'); loadAll(); }
    else showToast('Deny failed — backend error.');
  };

  const handleActivateStop = async () => {
    setEmergencyBusy(true);
    const r = await activateEmergencyStop('Activated via Authority Cockpit');
    setEmergencyBusy(false);
    if (r) {
      showToast(`Emergency stop activated. ${r.revoked_approvals_count} approvals revoked.`);
      loadAll();
    } else {
      showToast('Emergency stop failed — backend error.');
    }
  };

  const handleClearStop = async () => {
    setEmergencyBusy(true);
    const r = await clearEmergencyStop();
    setEmergencyBusy(false);
    if (r) { showToast('Emergency stop cleared.'); loadAll(); }
    else showToast('Clear failed — backend error.');
  };

  const resolvedStatus = status === 'loading' ? null : status;

  return (
    <div style={{ position: 'relative' }}>
      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            background: C.surface,
            border: `1px solid ${C.blue}55`,
            color: C.text,
            padding: '8px 16px',
            borderRadius: 8,
            fontSize: 13,
            zIndex: 9999,
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          }}
        >
          {toast}
        </div>
      )}

      {/* Section A — Status Header */}
      <StatusHeader
        status={status === 'loading' ? null : resolvedStatus}
        onRefresh={loadAll}
      />

      {/* Section D — Emergency Stop (top priority — always visible) */}
      <SectionCard
        title="Emergency Stop & Revocation"
        icon={<ShieldOff size={14} />}
        accent={emergencyStatus?.active ? C.red : undefined}
        collapsible
        defaultOpen
      >
        <EmergencyStopControl
          status={emergencyStatus}
          onActivate={handleActivateStop}
          onClear={handleClearStop}
          busy={emergencyBusy}
        />
      </SectionCard>

      {/* Section C — Pending Approvals */}
      <SectionCard
        title={`Pending Approvals${pending ? ` (${pending.length})` : ''}`}
        icon={<CheckCircle size={14} />}
        accent={pending && pending.length > 0 ? C.yellow : undefined}
        collapsible
        defaultOpen
      >
        <ApprovalsList
          approvals={pending}
          loading={pendingLoading}
          onGrant={handleGrant}
          onDeny={handleDeny}
        />
      </SectionCard>

      {/* Section B — Permission Tier Matrix */}
      <SectionCard
        title="Permission Tier Matrix"
        icon={<Shield size={14} />}
        collapsible
        defaultOpen={false}
      >
        <TierMatrix tiers={tiers} />
      </SectionCard>

      {/* Section F — Risk Classifier / Action Preview */}
      <SectionCard
        title="Risk Classifier & Action Preview"
        icon={<Zap size={14} />}
        collapsible
        defaultOpen
      >
        <RiskClassifier />
      </SectionCard>

      {/* Section E — Audit Trail */}
      <SectionCard
        title="Recent Audit Trail"
        icon={<FileText size={14} />}
        collapsible
        defaultOpen={false}
      >
        <AuditTrail entries={audit} />
      </SectionCard>

      {/* Section G — Rollback / Recovery */}
      <SectionCard
        title="Rollback & Recovery Visibility"
        icon={<RotateCcw size={14} />}
        collapsible
        defaultOpen={false}
      >
        <RollbackVisibility approvals={active} />
      </SectionCard>

      {/* Section H — Spend + Secret Guardrail */}
      <SectionCard
        title="Spend & Secret Guardrails"
        icon={<Lock size={14} />}
        collapsible
        defaultOpen={false}
      >
        <SpendSecretPanel spend={spend} policy={secretPolicy} />
      </SectionCard>
    </div>
  );
}
