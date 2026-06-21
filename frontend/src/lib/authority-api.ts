/**
 * Plan 8B — Authority API client.
 *
 * Typed wrappers for all /v1/authority/* routes from Plan 8 backend.
 * Uses apiFetch() so auth headers are always injected.
 * No secret values are ever returned or logged here.
 */

import { apiFetch } from './api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthorityStatus {
  plan_8_version: string;
  emergency_stop_active: boolean;
  emergency_stop_status: EmergencyStopStatus;
  pending_approvals_count: number;
  active_approvals_count: number;
  recent_audit_count: number;
  authority_tier_max: number;
  blocked_by_emergency_stop: boolean;
  status: 'operational' | 'emergency_stop_active' | string;
}

export interface EmergencyStopStatus {
  active: boolean;
  activated_at: string | null;
  activated_by: string | null;
  reason: string | null;
  cleared_at: string | null;
  cleared_by: string | null;
  status: 'active' | 'inactive' | string;
}

export interface TierDefinition {
  tier: number;
  label: string;
  description: string;
  allowed_action_types: string[];
  blocked_action_types: string[];
  required_approval_mode: string;
  step_up_required: boolean;
  required_audit_fields: string[];
  audit_on_execution: boolean;
  rollback_required: boolean;
  rollback_method: string;
  credentials_allowed: boolean;
  credential_scope: string;
  spend_bearing_allowed: boolean;
  max_spend_per_action: number;
  external_sends_allowed: boolean;
  production_deploy_allowed: boolean;
  account_changes_allowed: boolean;
}

export interface TierMatrix {
  tiers: TierDefinition[];
  tier_count: number;
}

export interface ApprovalRecord {
  approval_id: string;
  requester: string;
  action_type: string;
  action_preview: string;
  risk_level: string;
  tier: number;
  affected_systems: string[];
  affected_files: string[];
  affected_accounts: string[];
  estimated_spend: number;
  rollback_plan: string;
  scope: string;
  mode: string;
  status: string;
  audit_trace_id: string;
  created_at: string;
  granted_at: string | null;
  expires_at: string | null;
  context: Record<string, unknown>;
  error_reason: string;
  revocation_reason: string;
}

export interface ApprovalsResponse {
  approvals: ApprovalRecord[];
  count: number;
}

export interface AuditEntry {
  audit_id: string;
  ts: number;
  iso_ts: string;
  action_type: string;
  actor: string;
  tier: number;
  risk_level: string;
  approval_decision: string;
  execution_status: string;
  affected_resource: string;
  rollback_metadata: string;
  error_info: string;
  retry_count: number;
  connector: string;
  approval_id: string | null;
  audit_trace_id: string;
  context: Record<string, unknown>;
}

export interface AuditResponse {
  entries: AuditEntry[];
  count: number;
  total_count: number;
}

export interface RiskProfile {
  action_type: string;
  action_category: string;
  destructive_potential: string;
  external_side_effect: string;
  money_impact: string;
  credential_impact: string;
  privacy_impact: string;
  production_impact: string;
  reversibility: string;
  user_confirmation_required: boolean;
  risk_score: number;
  recommended_tier: number;
  risk_label: string;
  blocking_reason: string;
  irreversible_warning: string;
}

export interface ActionPreview {
  action_id: string;
  action_type: string;
  action_description: string;
  target_system: string;
  files_affected: string[];
  resources_affected: string[];
  accounts_affected: string[];
  diff_summary: string;
  change_count: number;
  external_side_effects: string[];
  side_effect_irreversible: boolean;
  cost_estimate: number;
  cost_estimate_source: string;
  cost_unknown_warning: string;
  rollback_plan: string;
  rollback_supported: boolean;
  rollback_method: string;
  irreversible_warning: string;
  requires_approval: boolean;
  tier: number;
  risk_level: string;
  dry_run_requested: boolean;
  dry_run_completed: boolean;
  dry_run_result: Record<string, unknown> | null;
  dry_run_errors: string[];
  created_at: number;
  requires_human_approval: boolean;
}

export interface PreviewResponse {
  preview: ActionPreview;
  risk_profile: RiskProfile;
}

export interface SpendSummary {
  session_id: string;
  session_spend: number;
  day_spend: number;
  daily_budget: number;
  session_budget: number;
  alert_threshold_pct: number;
}

export interface SecretPolicy {
  never_print_secrets: boolean;
  never_commit_secrets: boolean;
  never_expose_in_ui_or_logs: boolean;
  audit_by_name_scope_not_value: boolean;
  require_approval_for_high_risk_credential_actions: boolean;
  allowed_stores: string[];
  forbidden_stores: string[];
  min_tier_for_credential_read: number;
  min_tier_for_credential_write: number;
  min_tier_for_credential_admin: number;
  token_patterns_scanned: string[];
}

// ---------------------------------------------------------------------------
// Fetch helpers — all wrapped in try/catch, return null on error
// ---------------------------------------------------------------------------

async function safeFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await apiFetch(path, init);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Authority status
// ---------------------------------------------------------------------------

export async function fetchAuthorityStatus(): Promise<AuthorityStatus | null> {
  return safeFetch<AuthorityStatus>('/v1/authority/status');
}

// ---------------------------------------------------------------------------
// Tier matrix
// ---------------------------------------------------------------------------

export async function fetchTierMatrix(): Promise<TierMatrix | null> {
  return safeFetch<TierMatrix>('/v1/authority/tiers');
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

export async function fetchPendingApprovals(): Promise<ApprovalsResponse | null> {
  return safeFetch<ApprovalsResponse>('/v1/authority/approvals/pending');
}

export async function fetchActiveApprovals(): Promise<ApprovalsResponse | null> {
  return safeFetch<ApprovalsResponse>('/v1/authority/approvals/active');
}

export async function fetchRevokedApprovals(): Promise<ApprovalsResponse | null> {
  return safeFetch<ApprovalsResponse>('/v1/authority/approvals/revoked');
}

export async function grantApproval(
  approvalId: string,
  expiresInSeconds = 3600,
): Promise<{ status: string; approval_id: string } | null> {
  return safeFetch(`/v1/authority/approvals/${approvalId}/grant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expires_in_seconds: expiresInSeconds }),
  });
}

export async function denyApproval(
  approvalId: string,
  reason = '',
): Promise<{ status: string; approval_id: string } | null> {
  return safeFetch(`/v1/authority/approvals/${approvalId}/deny`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
}

export async function revokeApproval(
  approvalId: string,
  reason = '',
): Promise<{ status: string; approval_id: string } | null> {
  return safeFetch(`/v1/authority/approvals/${approvalId}/revoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
}

// ---------------------------------------------------------------------------
// Emergency stop
// ---------------------------------------------------------------------------

export async function fetchEmergencyStopStatus(): Promise<EmergencyStopStatus | null> {
  return safeFetch<EmergencyStopStatus>('/v1/authority/emergency-stop');
}

export async function activateEmergencyStop(
  reason = '',
  activatedBy = 'owner',
): Promise<{ active: boolean; revoked_approvals_count: number } | null> {
  return safeFetch('/v1/authority/emergency-stop/set', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ activated_by: activatedBy, reason }),
  });
}

export async function clearEmergencyStop(
  clearedBy = 'owner',
): Promise<{ active: boolean } | null> {
  return safeFetch('/v1/authority/emergency-stop/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cleared_by: clearedBy }),
  });
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export async function fetchRecentAudit(limit = 20): Promise<AuditResponse | null> {
  return safeFetch<AuditResponse>(`/v1/authority/audit?limit=${limit}`);
}

export async function fetchBlockedAudit(limit = 20): Promise<AuditResponse | null> {
  return safeFetch<AuditResponse>(`/v1/authority/audit/blocked?limit=${limit}`);
}

// ---------------------------------------------------------------------------
// Risk classifier + action preview
// ---------------------------------------------------------------------------

export async function classifyAction(actionType: string): Promise<RiskProfile | null> {
  return safeFetch<RiskProfile>('/v1/authority/classify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action_type: actionType }),
  });
}

export async function previewAction(
  actionType: string,
  description = '',
  runDryRun = true,
): Promise<PreviewResponse | null> {
  return safeFetch<PreviewResponse>('/v1/authority/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action_type: actionType,
      description,
      run_dry_run: runDryRun,
    }),
  });
}

// ---------------------------------------------------------------------------
// Spend + secret policy
// ---------------------------------------------------------------------------

export async function fetchSpendSummary(): Promise<SpendSummary | null> {
  return safeFetch<SpendSummary>('/v1/authority/spend/summary');
}

export async function fetchSecretPolicy(): Promise<SecretPolicy | null> {
  return safeFetch<SecretPolicy>('/v1/authority/secret-policy');
}

export async function fetchRiskMatrix(): Promise<{ matrix: RiskProfile[]; count: number } | null> {
  return safeFetch('/v1/authority/risk-matrix');
}
