/**
 * Plan 4-6 — Jarvis OS API client.
 *
 * Typed wrappers for:
 *   /v1/rules/*           — Rules Engine
 *   /v1/expert-roles/*    — Expert Role Registry
 *   /v1/jarvis/*          — Self-Knowledge / Status / Roadmap
 *   /v1/productization/*  — Mobile / iOS / PWA status
 *
 * Uses apiFetch() so auth headers are always injected.
 * No secret values are ever returned or logged.
 */

import { apiFetch } from './api';

// ---------------------------------------------------------------------------
// Rules types
// ---------------------------------------------------------------------------

export interface Rule {
  rule_id: string;
  name: string;
  description: string;
  rule_type: string;
  scope: string;
  status: string;
  priority: number;
  condition: Record<string, unknown>;
  action: Record<string, unknown>;
  scope_id: string;
  source: string;
  safety_level: string;
  tags: string[];
  conflict_ids: string[];
  created_at: number;
  updated_at: number;
}

export interface RulesStats {
  total: number;
  active: number;
  inactive: number;
  conflicted: number;
  draft: number;
}

export interface RulesListResponse {
  rules: Rule[];
  count: number;
  stats: RulesStats;
}

export interface CreateRulePayload {
  name: string;
  description?: string;
  rule_type?: string;
  scope?: string;
  priority?: number;
  condition?: Record<string, unknown>;
  action?: Record<string, unknown>;
  safety_level?: string;
  tags?: string[];
}

// ---------------------------------------------------------------------------
// Expert role types
// ---------------------------------------------------------------------------

export interface ExpertRole {
  role_id: string;
  name: string;
  domain: string;
  description: string;
  trigger_conditions: string[];
  safety_level: string;
  disclaimer: string;
  status: string;
}

export interface RolesStats {
  total: number;
  active: number;
  inactive: number;
}

export interface ExpertRolesListResponse {
  roles: ExpertRole[];
  count: number;
  stats: RolesStats;
  note: string;
}

export interface SelectRolesPayload {
  text: string;
  action_type?: string;
  max_roles?: number;
}

export interface SelectRolesResponse {
  selected_roles: ExpertRole[];
  count: number;
  disclaimers: string[];
  note: string;
}

// ---------------------------------------------------------------------------
// Self-knowledge types
// ---------------------------------------------------------------------------

export interface Capability {
  id: string;
  name: string;
  status: string;
  description: string;
  plan: string;
  blocker?: string;
  external_gate?: string;
}

export interface CapabilitiesSummary {
  total: number;
  available: number;
  partial: number;
  parked: number;
  not_started: number;
}

export interface CapabilitiesResponse {
  capabilities: Capability[];
  summary: CapabilitiesSummary;
  identity: string;
  text_first: boolean;
  voice_status: string;
}

export interface JarvisStatus {
  name: string;
  identity: string;
  plan_state: Record<string, string>;
  capability_summary: { available: number; total: number };
  text_first: boolean;
  voice_parked: boolean;
  mobile_parity: string;
  approval_gates: string;
  fake_claims: boolean;
}

export interface RoadmapEntry {
  plan: string;
  name: string;
  status: string;
}

export interface RoadmapResponse {
  roadmap: RoadmapEntry[];
  active_sprint: string;
  next: string;
  note: string;
}

// ---------------------------------------------------------------------------
// Productization types
// ---------------------------------------------------------------------------

export interface ProductizationGate {
  gate: string;
  status: string;
  evidence: string;
}

export interface ProductizationStatus {
  mobile_web_pwa: { status: string; description: string; features: string[] };
  native_ios: {
    status: string;
    description: string;
    scaffold_status: string;
    scaffold_path: string;
    build_requirements: string[];
    external_gates: Record<string, string>;
  };
  app_store: { status: string; description: string; fake_claim: boolean };
  gates: ProductizationGate[];
  summary: {
    gates_total: number;
    gates_pass: number;
    gates_external: number;
    gates_not_started: number;
    pwa_ready: boolean;
    ios_scaffold_ready: boolean;
    app_store_ready: boolean;
    fake_claims: boolean;
  };
  next_steps: string[];
}

// ---------------------------------------------------------------------------
// Rules API
// ---------------------------------------------------------------------------

export async function fetchRules(params?: { scope?: string; status?: string }): Promise<RulesListResponse> {
  const qs = new URLSearchParams();
  if (params?.scope) qs.set('scope', params.scope);
  if (params?.status) qs.set('status', params.status);
  const url = `/v1/rules${qs.toString() ? '?' + qs.toString() : ''}`;
  const res = await apiFetch(url);
  return res.json();
}

export async function fetchRule(ruleId: string): Promise<{ rule: Rule }> {
  const res = await apiFetch(`/v1/rules/${encodeURIComponent(ruleId)}`);
  return res.json();
}

export async function createRule(payload: CreateRulePayload): Promise<{ rule: Rule; conflicts: string[]; warning: string }> {
  const res = await apiFetch('/v1/rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function activateRule(ruleId: string): Promise<{ rule: Rule; status: string }> {
  const res = await apiFetch(`/v1/rules/${encodeURIComponent(ruleId)}/activate`, { method: 'POST' });
  return res.json();
}

export async function deactivateRule(ruleId: string): Promise<{ rule: Rule; status: string }> {
  const res = await apiFetch(`/v1/rules/${encodeURIComponent(ruleId)}/deactivate`, { method: 'POST' });
  return res.json();
}

export async function deleteRule(ruleId: string): Promise<{ deleted: boolean }> {
  const res = await apiFetch(`/v1/rules/${encodeURIComponent(ruleId)}`, { method: 'DELETE' });
  return res.json();
}

export async function evaluateRules(ctx: { action_type?: string; project_id?: string; metadata?: Record<string, unknown> }): Promise<{ evaluation: unknown }> {
  const res = await apiFetch('/v1/rules/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ctx),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Expert roles API
// ---------------------------------------------------------------------------

export async function fetchExpertRoles(params?: { status?: string; domain?: string }): Promise<ExpertRolesListResponse> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.domain) qs.set('domain', params.domain);
  const url = `/v1/expert-roles${qs.toString() ? '?' + qs.toString() : ''}`;
  const res = await apiFetch(url);
  return res.json();
}

export async function selectRoles(payload: SelectRolesPayload): Promise<SelectRolesResponse> {
  const res = await apiFetch('/v1/expert-roles/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Self-knowledge API
// ---------------------------------------------------------------------------

export async function fetchCapabilities(status?: string): Promise<CapabilitiesResponse> {
  const url = status ? `/v1/jarvis/capabilities?status=${encodeURIComponent(status)}` : '/v1/jarvis/capabilities';
  const res = await apiFetch(url);
  return res.json();
}

export async function fetchJarvisStatus(): Promise<JarvisStatus> {
  const res = await apiFetch('/v1/jarvis/status');
  return res.json();
}

export async function fetchRoadmap(): Promise<RoadmapResponse> {
  const res = await apiFetch('/v1/jarvis/roadmap');
  return res.json();
}

// ---------------------------------------------------------------------------
// Productization API
// ---------------------------------------------------------------------------

export async function fetchProductizationStatus(): Promise<ProductizationStatus> {
  const res = await apiFetch('/v1/productization/status');
  return res.json();
}

// ---------------------------------------------------------------------------
// System status types + API
// ---------------------------------------------------------------------------

export interface ConnectorStatus {
  status: string;
  note: string;
}

export interface SystemComponentStatus {
  status: string;
  note: string;
  [key: string]: unknown;
}

export interface SystemStatusSummary {
  connectors_configured: number;
  connectors_partial: number;
  connectors_not_configured: number;
  fargate_healthy: boolean;
  pwa_ready: boolean;
  ios_scaffold_ready: boolean;
  voice_parked: boolean;
  fake_claims: boolean;
}

export interface SystemStatusResponse {
  connectors: Record<string, ConnectorStatus>;
  system: Record<string, SystemComponentStatus>;
  summary: SystemStatusSummary;
  safety: string;
}

export async function fetchSystemStatus(): Promise<SystemStatusResponse> {
  const res = await apiFetch('/v1/system/status');
  return res.json();
}

// ---------------------------------------------------------------------------
// Delegation queue types + API
// ---------------------------------------------------------------------------

export interface DelegationItem {
  delegation_id: string;
  source: string;
  source_id: string;
  title: string;
  description: string;
  status: string;
  category: string;
  authority_tier: string;
  approval_route: string | null;
  reject_route: string | null;
  created_at: string | number | null;
  expires_at: string | number | null;
  audit_id: string;
  priority: string | null;
  risk_level: string | null;
  tags: string[];
  extra: Record<string, unknown>;
}

export interface DelegationQueueResponse {
  items: DelegationItem[];
  count: number;
  by_source: { life_os: number; agent_action: number; mission: number };
  errors: Array<{ source: string; error: string }>;
  sources_probed: string[];
  note: string;
}

export interface DelegationSummary {
  total: number;
  by_source: { life_os: number; agent_action: number; mission: number };
  has_pending: boolean;
}

export async function fetchDelegationQueue(): Promise<DelegationQueueResponse> {
  const res = await apiFetch('/v1/delegation/queue');
  return res.json();
}

export async function fetchDelegationSummary(): Promise<DelegationSummary> {
  const res = await apiFetch('/v1/delegation/queue/summary');
  return res.json();
}

export async function approveItem(approvalRoute: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(approvalRoute, { method: 'POST' });
  return res.json();
}

export async function rejectItem(rejectRoute: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(rejectRoute, { method: 'POST' });
  return res.json();
}

// ---------------------------------------------------------------------------
// Follow-Up Center types + API  (Phase B1)
// ---------------------------------------------------------------------------

export interface FollowUpItem {
  item_id: string;
  source: 'life_os_task' | 'goal' | string;
  source_id: string;
  title: string;
  description: string;
  status: 'due' | 'upcoming' | 'waiting_approval' | 'snoozed' | 'completed' | string;
  due_at: number | null;
  priority: string;
  tags: string[];
  approval_required: boolean;
  approval_route: string | null;
  source_route: string | null;
  follow_up_state: Record<string, unknown> | null;
  created_at: number;
}

export interface FollowUpCenterResponse {
  items: FollowUpItem[];
  count: number;
  due_count: number;
  pending_approval_count: number;
  sources_probed: string[];
  fake_data: boolean;
  automation_honesty: boolean;
  note: string;
}

export interface FollowUpSummary {
  total: number;
  by_source: Record<string, number>;
  by_status: Record<string, number>;
  due: number;
  upcoming: number;
  waiting_approval: number;
  snoozed: number;
  fake_data: boolean;
}

export async function fetchFollowUpCenter(opts?: {
  source?: string;
  status?: string;
  limit?: number;
}): Promise<FollowUpCenterResponse> {
  const params = new URLSearchParams();
  if (opts?.source) params.set('source', opts.source);
  if (opts?.status) params.set('status', opts.status);
  if (opts?.limit) params.set('limit', String(opts.limit));
  const qs = params.toString();
  const res = await apiFetch(`/v1/follow-up-center${qs ? `?${qs}` : ''}`);
  return res.json();
}

export async function fetchFollowUpSummary(): Promise<FollowUpSummary> {
  const res = await apiFetch('/v1/follow-up-center/summary');
  return res.json();
}

export async function completeTaskFollowUp(taskId: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/v1/follow-up-center/tasks/${taskId}/complete`, { method: 'POST' });
  return res.json();
}

export async function snoozeTaskFollowUp(
  taskId: string,
  snoozeUntil: number,
  reason?: string,
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/v1/follow-up-center/tasks/${taskId}/snooze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snooze_until: snoozeUntil, reason: reason ?? '' }),
  });
  return res.json();
}
