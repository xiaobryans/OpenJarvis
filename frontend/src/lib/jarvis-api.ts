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

// ---------------------------------------------------------------------------
// Routines Center types + API  (Phase B2)
// ---------------------------------------------------------------------------

export interface RoutinesSummary {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  active: number;
  paused: number;
  completed: number;
  failed: number;
  scheduler_started: boolean;
  fake_data: boolean;
  automation_honesty: boolean;
  note: string;
}

export async function fetchRoutinesSummary(): Promise<RoutinesSummary> {
  const res = await apiFetch('/v1/routines/summary');
  return res.json();
}

// ---------------------------------------------------------------------------
// Memory OS types + API  (Phase B3)
// ---------------------------------------------------------------------------

export interface MemoryDashboard {
  store_ok: boolean;
  namespace_count: number;
  total_entries: number;
  namespaces: Array<{ name: string; count: number } | Record<string, unknown>>;
  search_available: boolean;
  cloud_sync_configured: boolean;
  cloud_sync_live_claimed: boolean;
  fake_data: boolean;
  note: string;
}

export async function fetchMemoryDashboard(): Promise<MemoryDashboard> {
  const res = await apiFetch('/v1/memory/dashboard');
  return res.json();
}

// ---------------------------------------------------------------------------
// Command Center types + API  (Phase B4)
// ---------------------------------------------------------------------------

export interface CommandCenterItem {
  item_id: string;
  source: 'life_os_task' | 'goal' | 'project' | string;
  source_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  tags: string[];
  approval_required: boolean;
  due_at: number | null;
  source_route: string | null;
  horizon?: string;
  pending_milestones?: number;
  pending_actions?: number;
  follow_up_count?: number;
}

export interface CommandCenterResponse {
  items: CommandCenterItem[];
  count: number;
  by_source: Record<string, number>;
  by_status: Record<string, number>;
  sources_probed: string[];
  fake_data: boolean;
  note: string;
}

export interface CommandCenterSummary {
  tasks: { total: number; pending: number; in_progress: number; waiting_approval: number };
  goals: { total: number; active: number; paused: number };
  projects: { total: number; active: number };
  grand_total: number;
  fake_data: boolean;
}

export async function fetchCommandCenter(opts?: {
  source?: string;
  status?: string;
  limit?: number;
}): Promise<CommandCenterResponse> {
  const params = new URLSearchParams();
  if (opts?.source) params.set('source', opts.source);
  if (opts?.status) params.set('status', opts.status);
  if (opts?.limit) params.set('limit', String(opts.limit));
  const qs = params.toString();
  const res = await apiFetch(`/v1/command-center${qs ? `?${qs}` : ''}`);
  return res.json();
}

export async function fetchCommandCenterSummary(): Promise<CommandCenterSummary> {
  const res = await apiFetch('/v1/command-center/summary');
  return res.json();
}

// ---------------------------------------------------------------------------
// Expert routing status types + API  (Phase B5)
// ---------------------------------------------------------------------------

export interface ExpertRoutingStatus {
  selector_available: boolean;
  selector_wired_to_frontdoor: boolean;
  role_count: number;
  active_role_count: number;
  jarvis_pa_identity: {
    single_voice: boolean;
    internal_routing_only: boolean;
    no_multi_personality_output: boolean;
    note: string;
  };
  audit: {
    routing_is_internal: boolean;
    approval_gates_unaffected: boolean;
    no_autonomous_role_switching: boolean;
  };
  fake_data: boolean;
}

export async function fetchExpertRoutingStatus(): Promise<ExpertRoutingStatus> {
  const res = await apiFetch('/v1/expert-roles/routing-status');
  return res.json();
}

// ---------------------------------------------------------------------------
// Skills Expansion types + API  (Phase B7)
// ---------------------------------------------------------------------------

export interface SkillsCatalogSummary {
  total: number;
  available: number;
  blocked: number;
  disabled: number;
  not_configured: number;
  planned: number;
  has_intake_queue: boolean;
  intake_queue_size: number;
  marketplace_live: boolean;
  fake_data: boolean;
  automation_honesty: boolean;
  note: string;
}

export interface SkillPermission {
  skill_id: string;
  name: string;
  safety_level: string;
  requires_approval: boolean;
  network_access: boolean;
  data_access: boolean;
  approval_tier: string;
}

export async function fetchSkillsCatalogSummary(): Promise<SkillsCatalogSummary> {
  const res = await apiFetch('/v1/skills/catalog/summary');
  return res.json();
}

export async function fetchSkillPermissions(): Promise<{ skills: SkillPermission[]; count: number; permission_gates_active: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/skills/permissions');
  return res.json();
}

// ---------------------------------------------------------------------------
// Connector Workflows types + API  (Phase B8)
// ---------------------------------------------------------------------------

export interface ConnectorWorkflow {
  workflow_id: string;
  name: string;
  dry_run_only: boolean;
  requires_approval: boolean;
}

export interface ConnectorEntry {
  connector_id: string;
  name: string;
  status: string;
  credential_gate: string;
  available_workflows: ConnectorWorkflow[];
  live: boolean;
  fake_live: boolean;
}

export interface ConnectorWorkflowsResponse {
  connectors: ConnectorEntry[];
  live_connector_count: number;
  configured_count: number;
  total: number;
  fake_live: boolean;
  fake_data: boolean;
  note: string;
}

export async function fetchConnectorWorkflows(): Promise<ConnectorWorkflowsResponse> {
  const res = await apiFetch('/v1/connector-workflows');
  return res.json();
}

// ---------------------------------------------------------------------------
// Proactive Operator types + API  (Phase B9)
// ---------------------------------------------------------------------------

export interface ProactiveSuggestion {
  type: string;
  title: string;
  description: string;
  source: string;
  source_id?: string;
  action_required?: string;
  priority: string;
  approval_route?: string;
  action_type?: string;
  cli_command?: string;
}

export interface ProactiveSuggestionsResponse {
  suggestions: ProactiveSuggestion[];
  count: number;
  sources_probed: string[];
  execution_blocked: boolean;
  approval_gates_preserved: boolean;
  fake_data: boolean;
  automation_honesty: boolean;
  note: string;
}

export interface StaleItem {
  task_id: string;
  title: string;
  status: string;
  age_days: number;
  source: string;
}

export interface NextAction {
  rank: number;
  action: string;
  reason: string;
  source: string;
  approval_required: boolean;
  priority: string;
}

export async function fetchProactiveSuggestions(): Promise<ProactiveSuggestionsResponse> {
  const res = await apiFetch('/v1/proactive/suggestions');
  return res.json();
}

export async function fetchStaleItems(): Promise<{ stale_tasks: StaleItem[]; count: number; threshold_days: number; action_blocked: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/proactive/stale-items');
  return res.json();
}

export async function fetchNextActions(): Promise<{ next_actions: NextAction[]; count: number; auto_execute: boolean; approval_required_for_any_action: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/proactive/next-actions');
  return res.json();
}

// ---------------------------------------------------------------------------
// Business/Admin types + API  (Phase B10)
// ---------------------------------------------------------------------------

export interface AdminAction {
  action_id: string;
  name: string;
  approval_required: boolean;
  live: boolean;
}

export interface AdminCategory {
  category_id: string;
  name: string;
  description: string;
  status: string;
  actions: AdminAction[];
  external_gate: string | null;
  fake_completion: boolean;
}

export interface BusinessAdminDashboard {
  categories: AdminCategory[];
  total_categories: number;
  available_now: number;
  approval_gates_active: boolean;
  fake_completion: boolean;
  fake_data: boolean;
  note: string;
}

export interface BusinessWorkflow {
  workflow_id: string;
  name: string;
  category: string;
  source_route: string | null;
  approval_required: boolean;
  available: boolean;
  gate?: string;
}

export async function fetchBusinessAdminDashboard(): Promise<BusinessAdminDashboard> {
  const res = await apiFetch('/v1/business-admin/dashboard');
  return res.json();
}

export async function fetchBusinessAdminWorkflows(): Promise<{ workflows: BusinessWorkflow[]; count: number; available_count: number; fake_data: boolean }> {
  const res = await apiFetch('/v1/business-admin/workflows');
  return res.json();
}

// ---------------------------------------------------------------------------
// Observability types + API  (Phase B11)
// ---------------------------------------------------------------------------

export interface HealthComponent {
  component_id: string;
  name: string;
  status: 'healthy' | 'degraded' | 'unavailable' | string;
  note: string;
}

export interface HealthSummary {
  components: HealthComponent[];
  healthy_count: number;
  degraded_count: number;
  unavailable_count: number;
  overall_status: string;
  fake_data: boolean;
  note: string;
}

export interface ObservabilityAlert {
  level: 'warn' | 'error' | string;
  message: string;
}

export interface ReliabilityMetrics {
  metrics: Record<string, unknown>;
  thresholds: Record<string, unknown>;
  alerts: ObservabilityAlert[];
  cost_tracking: { budget_metadata_available: boolean; live_cost_data: boolean; note: string };
  fake_data: boolean;
  secret_safe: boolean;
}

export async function fetchHealthSummary(): Promise<HealthSummary> {
  const res = await apiFetch('/v1/observability/health-summary');
  return res.json();
}

export async function fetchReliabilityMetrics(): Promise<ReliabilityMetrics> {
  const res = await apiFetch('/v1/observability/reliability-metrics');
  return res.json();
}

// ---------------------------------------------------------------------------
// Long-Horizon Goals types + API  (Phase B12)
// ---------------------------------------------------------------------------

export interface LongHorizonGoal {
  goal_id: string;
  title: string;
  description: string;
  horizon: string;
  status: string;
  owner: string;
  tags: string[];
  milestones_total: number;
  milestones_completed: number;
  milestones_pending: number;
  next_actions_total: number;
  next_actions_pending: number;
  has_continuation_state: boolean;
  follow_up_count: number;
  auto_execute: false;
  approval_required_for_actions: true;
  execution_honesty: string;
}

export interface LongHorizonGoalsResponse {
  goals: LongHorizonGoal[];
  count: number;
  active_count: number;
  paused_count: number;
  completed_count: number;
  auto_execute: false;
  fake_data: boolean;
  note: string;
}

export interface LongHorizonSummary {
  total_goals: number;
  active: number;
  paused: number;
  completed: number;
  abandoned: number;
  total_pending_milestones: number;
  total_pending_actions: number;
  approval_required_for_execution: true;
  auto_execute: false;
  fake_data: boolean;
}

export async function fetchLongHorizonGoals(): Promise<LongHorizonGoalsResponse> {
  const res = await apiFetch('/v1/long-horizon/goals');
  return res.json();
}

export async function fetchLongHorizonSummary(): Promise<LongHorizonSummary> {
  const res = await apiFetch('/v1/long-horizon/summary');
  return res.json();
}

// ---------------------------------------------------------------------------
// Finance/Admin OS types + API  (Phase B13)
// ---------------------------------------------------------------------------

export interface FinanceAdminCategory {
  category_id: string;
  name: string;
  status: string;
  description: string;
  actions: Array<{ action_id: string; name: string; approval_required: boolean; live: boolean; route?: string }>;
  external_gate: string | null;
  fake_completion: boolean;
}

export interface FinanceAdminDashboard {
  categories: FinanceAdminCategory[];
  total_categories: number;
  available_now: number;
  approval_gates_active: boolean;
  live_financial_execution: boolean;
  fake_completion: boolean;
  fake_data: boolean;
  note: string;
}

export async function fetchFinanceAdminDashboard(): Promise<FinanceAdminDashboard> {
  const res = await apiFetch('/v1/finance-admin/dashboard');
  return res.json();
}

// ---------------------------------------------------------------------------
// Research OS types + API  (Phase B14)
// ---------------------------------------------------------------------------

export interface ResearchSection {
  section_id: string;
  name: string;
  status: string;
  description: string;
  source_route: string | null;
  live_web_retrieval: boolean;
  fake_research: boolean;
  external_gate?: string;
}

export interface ResearchTemplate {
  template_id: string;
  name: string;
  description: string;
  fields: string[];
  live_output: boolean;
}

export interface ResearchOSDashboard {
  sections: ResearchSection[];
  live_web_retrieval: boolean;
  fake_research: boolean;
  fake_data: boolean;
  provenance: string;
  note: string;
}

export async function fetchResearchOSDashboard(): Promise<ResearchOSDashboard> {
  const res = await apiFetch('/v1/research-os/dashboard');
  return res.json();
}

export async function fetchResearchTemplates(): Promise<{ templates: ResearchTemplate[]; count: number; live_output: boolean; fake_research: boolean; fake_data: boolean; note: string }> {
  const res = await apiFetch('/v1/research-os/templates');
  return res.json();
}

// ---------------------------------------------------------------------------
// Browser Operator types + API  (Phase B15)
// ---------------------------------------------------------------------------

export interface BrowserAction {
  action_id: string;
  name: string;
  dry_run_only: boolean;
  approval_required: boolean;
}

export interface BrowserOperatorStatus {
  browser_operator_available: boolean;
  dry_run_only: boolean;
  supported_actions: BrowserAction[];
  external_gates: string[];
  safety: Record<string, boolean>;
  fake_live: boolean;
  fake_data: boolean;
  note: string;
}

export async function fetchBrowserOperatorStatus(): Promise<BrowserOperatorStatus> {
  const res = await apiFetch('/v1/browser-operator/status');
  return res.json();
}

export async function fetchBrowserCapabilityMatrix(): Promise<{ categories: Array<{ category: string; available: boolean; dry_run_only: boolean; approval_tier: string; reason?: string }>; live_browser: boolean; fake_live: boolean; fake_data: boolean; note: string }> {
  const res = await apiFetch('/v1/browser-operator/capability-matrix');
  return res.json();
}

// ---------------------------------------------------------------------------
// Memory Graph types + API  (Phase B16)
// ---------------------------------------------------------------------------

export interface MemoryGraphStatus {
  graph_available: boolean;
  namespace_count: number;
  total_entries: number;
  entity_extraction: boolean;
  relation_mapping: boolean;
  contradiction_detection: boolean;
  cloud_sync_live: boolean;
  knowledge_graph_live: boolean;
  fake_data: boolean;
  note: string;
}

export interface MemoryGraphNamespace {
  name: string;
  entry_count: number;
  searchable: boolean;
  source: string;
}

export async function fetchMemoryGraphStatus(): Promise<MemoryGraphStatus> {
  const res = await apiFetch('/v1/memory-graph/status');
  return res.json();
}

export async function fetchMemoryGraphNamespaces(): Promise<{ namespaces: MemoryGraphNamespace[]; count: number; cloud_backed: boolean; knowledge_graph_entities: number; fake_data: boolean; source: string }> {
  const res = await apiFetch('/v1/memory-graph/namespaces');
  return res.json();
}

// ---------------------------------------------------------------------------
// Multi-Device types + API  (Phase B17)
// ---------------------------------------------------------------------------

export interface DeviceSession {
  session_id: string;
  device_type: string;
  status: string;
  capabilities: string[];
  live: boolean;
  gate?: string;
}

export interface MultiDeviceStatus {
  sessions: DeviceSession[];
  active_sessions: number;
  phone_control_live: boolean;
  macbook_off_cloud_execution_live: boolean;
  fargate_cloud_live: boolean;
  pwa_installed: boolean;
  fake_live: boolean;
  fake_data: boolean;
  note: string;
}

export async function fetchMultiDeviceStatus(): Promise<MultiDeviceStatus> {
  const res = await apiFetch('/v1/multi-device/status');
  return res.json();
}

export async function fetchMultiDeviceCapabilityMatrix(): Promise<{ devices: unknown[]; fake_live: boolean; fake_data: boolean; note: string }> {
  const res = await apiFetch('/v1/multi-device/capability-matrix');
  return res.json();
}

// ---------------------------------------------------------------------------
// Marketplace types + API  (Phase B18)
// ---------------------------------------------------------------------------

export interface MarketplacePlugin {
  plugin_id: string;
  name: string;
  version: string;
  status: string;
  safety_level: string;
  source: string;
  marketplace_verified: boolean;
  auto_installed: boolean;
}

export interface MarketplaceStatus {
  marketplace_live: boolean;
  local_registry_available: boolean;
  local_skill_count: number;
  review_queue_size: number;
  auto_install: boolean;
  network_install: boolean;
  fake_data: boolean;
  fake_marketplace: boolean;
  note: string;
}

export async function fetchMarketplaceStatus(): Promise<MarketplaceStatus> {
  const res = await apiFetch('/v1/marketplace/status');
  return res.json();
}

export async function fetchMarketplacePlugins(): Promise<{ plugins: MarketplacePlugin[]; count: number; marketplace_live: boolean; fake_marketplace: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/marketplace/plugins');
  return res.json();
}

// ---------------------------------------------------------------------------
// Org Mode types + API  (Phase B19)
// ---------------------------------------------------------------------------

export interface OrgModeStatus {
  multi_user_live: boolean;
  org_mode_available: boolean;
  single_user_mode: boolean;
  production_auth_ready: boolean;
  external_gate: string;
  dry_run_only: boolean;
  fake_data: boolean;
  note: string;
}

export async function fetchOrgModeStatus(): Promise<OrgModeStatus> {
  const res = await apiFetch('/v1/org-mode/status');
  return res.json();
}

export async function fetchOrgModeCapabilityMatrix(): Promise<{ capabilities: unknown[]; role_model: unknown; multi_user_live: boolean; fake_data: boolean; note: string }> {
  const res = await apiFetch('/v1/org-mode/capability-matrix');
  return res.json();
}

// ---------------------------------------------------------------------------
// Device Controller types + API  (Phase B20)
// ---------------------------------------------------------------------------

export interface DeviceControllerStatus {
  robotics_available: boolean;
  device_control_live: boolean;
  simulator_mode: boolean;
  supported_device_types: Array<{ type: string; live: boolean; gate: string }>;
  physical_world_execution: boolean;
  fake_live: boolean;
  fake_data: boolean;
  safety: Record<string, unknown>;
  note: string;
}

export async function fetchDeviceControllerStatus(): Promise<DeviceControllerStatus> {
  const res = await apiFetch('/v1/device-controller/status');
  return res.json();
}

export async function fetchDeviceSafetyMatrix(): Promise<{ safety_rules: Array<{ rule_id: string; description: string; enforced: boolean }>; physical_world_execution: boolean; fake_live: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/device-controller/safety-matrix');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C1 — Autonomous Org types + API
// ---------------------------------------------------------------------------
export interface AutonomousOrgStatus {
  org_kernel_available: boolean;
  one_jarvis_pa_identity: boolean;
  single_pa_voice: string;
  internal_team: Array<{ role_id: string; name: string; type: string; live: boolean; approval_gated: boolean; gate?: string }>;
  active_roles: number;
  autonomous_execution_live: boolean;
  omnix_is_jarvis_core: boolean;
  fake_data: boolean;
  note: string;
}
export async function fetchAutonomousOrgStatus(): Promise<AutonomousOrgStatus> {
  const res = await apiFetch('/v1/autonomous-org/status');
  return res.json();
}
export async function fetchAutonomousOrgCapabilityMatrix(): Promise<{ capabilities: unknown[]; one_jarvis_pa_identity: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/autonomous-org/capability-matrix');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C2 — Mission Control types + API
// ---------------------------------------------------------------------------
export interface MissionControlDashboard {
  missions: Array<{ mission_id: string; title: string; status: string; milestones: unknown[]; approval_required: boolean; auto_execute: boolean }>;
  total: number;
  active: number;
  paused: number;
  unapproved_execution: boolean;
  fake_data: boolean;
  note: string;
}
export async function fetchMissionControlDashboard(): Promise<MissionControlDashboard> {
  const res = await apiFetch('/v1/mission-control/dashboard');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C3 — Review/Governance types + API
// ---------------------------------------------------------------------------
export interface ReviewGovernanceStatus {
  governance_available: boolean;
  reviewer_lanes: Array<{ lane_id: string; name: string; active: boolean; auto_approve: boolean; approval_tier: string; gate?: string }>;
  active_lanes: number;
  approval_gates_active: boolean;
  bypassing_approval_gates: boolean;
  fake_data: boolean;
}
export async function fetchReviewGovernanceStatus(): Promise<ReviewGovernanceStatus> {
  const res = await apiFetch('/v1/review-governance/status');
  return res.json();
}
export async function fetchArbitrationStatus(): Promise<{ arbitration_available: boolean; conflicts: unknown[]; conflict_resolution: string; auto_resolve: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/review-governance/arbitration');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C4 — Product Readiness types + API
// ---------------------------------------------------------------------------
export interface ProductReadinessDimension {
  dimension_id: string;
  name: string;
  status: string;
  description: string;
  production_multi_user: boolean;
  gap?: string;
}
export interface ProductReadinessMatrix {
  readiness_dimensions: ProductReadinessDimension[];
  production_multi_user_ready: boolean;
  claiming_production_support: boolean;
  fake_data: boolean;
}
export async function fetchProductReadinessMatrix(): Promise<ProductReadinessMatrix> {
  const res = await apiFetch('/v1/product-readiness/matrix');
  return res.json();
}
export async function fetchMultiUserStatus(): Promise<{ multi_user_live: boolean; local_dry_run_model: boolean; admin_approval_required: boolean; inviting_real_users: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/product-readiness/multi-user-status');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C5 — Marketplace Governance types + API
// ---------------------------------------------------------------------------
export interface MarketplaceGovernanceStatus {
  governance_framework_available: boolean;
  review_pipeline_live: boolean;
  permission_scoring_live: boolean;
  dry_run_only: boolean;
  live_marketplace_claims: boolean;
  fake_data: boolean;
}
export async function fetchMarketplaceGovernanceStatus(): Promise<MarketplaceGovernanceStatus> {
  const res = await apiFetch('/v1/marketplace-governance/status');
  return res.json();
}
export async function fetchMarketplaceGovernancePolicy(): Promise<{ policies: Array<{ policy_id: string; name: string; enforced: boolean; description: string; gate?: string }>; live_marketplace: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/marketplace-governance/policy');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C6 — Enterprise Governance types + API
// ---------------------------------------------------------------------------
export interface EnterpriseAuditSummary {
  audit_entries: unknown[];
  total_entries: number;
  audit_live: boolean;
  secret_safe: boolean;
  fake_data: boolean;
}
export async function fetchEnterpriseAuditSummary(): Promise<EnterpriseAuditSummary> {
  const res = await apiFetch('/v1/enterprise-governance/audit-summary');
  return res.json();
}
export async function fetchEnterpriseReliability(): Promise<{ slo_targets: unknown[]; live_billing_integration: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/enterprise-governance/reliability');
  return res.json();
}
export async function fetchEnterpriseCostControl(): Promise<{ cost_tracking_available: boolean; live_billing_integration: boolean; provider_routing_visible: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/enterprise-governance/cost-control');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C7 — Scale Control types + API
// ---------------------------------------------------------------------------
export interface ScaleControlStatus {
  control_plane_available: boolean;
  device_readiness: Record<string, string>;
  cloud_execution_live: boolean;
  approval_gates_active: boolean;
  fake_cloud_readiness: boolean;
  fake_data: boolean;
}
export async function fetchScaleControlStatus(): Promise<ScaleControlStatus> {
  const res = await apiFetch('/v1/scale-control/status');
  return res.json();
}
export async function fetchMacbookOffReadiness(): Promise<{ macbook_off_live: boolean; requirements: unknown[]; requirements_met: number; requirements_total: number; fake_data: boolean }> {
  const res = await apiFetch('/v1/scale-control/macbook-off-readiness');
  return res.json();
}
export async function fetchParityStatus(): Promise<{ desktop_status: string; mobile_pwa_status: string; parity_achieved: boolean; parity_gaps: unknown[]; fake_data: boolean }> {
  const res = await apiFetch('/v1/scale-control/parity-status');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C8 — Company OS types + API
// ---------------------------------------------------------------------------
export interface CompanyOSDashboard {
  operating_status: string;
  workflow_lanes: Array<{ lane_id: string; name: string; active: boolean; approval_required: boolean; gate?: string }>;
  active_lanes: number;
  live_business_execution: boolean;
  goals_count: number;
  tasks_count: number;
  fake_data: boolean;
}
export async function fetchCompanyOSDashboard(): Promise<CompanyOSDashboard> {
  const res = await apiFetch('/v1/company-os/dashboard');
  return res.json();
}
export async function fetchCompanyOSLanes(): Promise<{ lanes: unknown[]; owner_approval_required: boolean; live_business_execution: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/company-os/workflow-lanes');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C9 — Safety Simulation types + API
// ---------------------------------------------------------------------------
export interface SafetySimulationStatus {
  simulation_framework_available: boolean;
  dry_run_only: boolean;
  real_execution: boolean;
  destructive_actions_blocked: boolean;
  fake_data: boolean;
}
export async function fetchSafetySimulationStatus(): Promise<SafetySimulationStatus> {
  const res = await apiFetch('/v1/safety-simulation/status');
  return res.json();
}
export async function fetchRollbackMatrix(): Promise<{ rollback_capabilities: unknown[]; automated_rollback_live: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/safety-simulation/rollback-matrix');
  return res.json();
}
export async function fetchPolicyChecks(): Promise<{ hard_gate_count: number; soft_gate_count: number; gates_enforced: boolean; bypassing_gates: boolean; fake_data: boolean }> {
  const res = await apiFetch('/v1/safety-simulation/policy-checks');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase C10 — Control Tower types + API
// ---------------------------------------------------------------------------
export interface ControlTowerStatus {
  phases: Array<{ phase: string; status: string; note: string }>;
  active_sprint: string;
  fake_acceptance: boolean;
  fake_data: boolean;
}
export async function fetchControlTowerStatus(): Promise<ControlTowerStatus> {
  const res = await apiFetch('/v1/control-tower/status');
  return res.json();
}
export async function fetchGateRegistry(): Promise<{ open_gates: unknown[]; closed_gates: unknown[]; open_count: number; closed_count: number; fake_data: boolean }> {
  const res = await apiFetch('/v1/control-tower/gate-registry');
  return res.json();
}
export async function fetchCompletionScore(): Promise<{ core_os_completion: { completion_score_pct: number; plans_accepted: string[]; phases_in_progress: string[] }; capability_coverage: Record<string, boolean>; fake_data: boolean }> {
  const res = await apiFetch('/v1/control-tower/completion-score');
  return res.json();
}

// ─── Phase C11-C20 Types ────────────────────────────────────────

export interface ExecutionReadinessStatus {
  systems: Array<{ system_id: string; name: string; status: string; approval_required: boolean; gate?: string }>
  overall_readiness: string
  autonomous_execution_live: boolean
  approval_required_for_all_actions: boolean
  fake_readiness: boolean
  fake_data: boolean
}

export interface ActionPlannerSystems {
  systems: Array<{ system_id: string; name: string; capabilities: string[] }>
  cross_system_planning: boolean
  fake_data: boolean
}

export interface PolicyAuthorityMatrix {
  domains: Array<{ domain_id: string; name: string; risk_tier: number; approval_required: boolean; hard_gated: boolean }>
  hard_gates_count: number
  hard_gates_preserved: boolean
  approval_gates_weakened: boolean
  fake_data: boolean
}

export interface ConnectorReadinessStatus {
  connectors: Array<{ connector_id: string; name: string; status: string; bryan_cleared: boolean; presence_only: boolean; no_credential_value: boolean }>
  total: number
  ready_prerequisite_count: number
  blocked_count: number
  not_configured_count: number
  fake_live_claims: boolean
  secrets_in_response: boolean
  fake_data: boolean
}

export interface IOSReadinessStatus {
  xcode_present: boolean
  xcode_version: string
  cocoapods_present: boolean
  ios_rust_targets: string[]
  ios_rust_targets_count: number
  prerequisites_bryan_cleared: boolean
  tauri_ios_init_run: boolean
  tauri_ios_init_deferred: boolean
  native_ios_app_ready: boolean
  fake_ios_readiness: boolean
  fake_data: boolean
}

export interface SigningReadinessStatus {
  notarytool_present: boolean
  apple_api_issuer_present: boolean
  apple_api_key_present: boolean
  apple_api_key_path_present: boolean
  apple_team_id_present: boolean
  apple_signing_identity_present: boolean
  prerequisites_bryan_cleared: boolean
  actual_signing_run: boolean
  actual_notarization_run: boolean
  signing_deferred: boolean
  fake_notarization: boolean
  fake_data: boolean
}

export interface CloudReadinessStatus {
  aws_credentials_present: boolean
  s3_configured: boolean
  fargate_configured: boolean
  tailscale_configured: boolean
  bryan_cleared: boolean
  cloud_execution_live: boolean
  macbook_off_live: boolean
  fake_cloud_execution: boolean
  fake_data: boolean
}

export interface FinalSmokeChecklist {
  checklist: Array<{ item_id: string; name: string; status: string; requires_manual_proof: boolean; auto_passable: boolean; blocked_reason?: string }>
  total: number
  passed: number
  pending_manual_proof: number
  manual_proof_required: boolean
  auto_pass_blocked: boolean
  fake_data: boolean
}

export interface DailyDriverStatus {
  certification_status: string
  certified: boolean
  auto_certification_blocked: boolean
  daily_driver_sessions_recorded: number
  manual_certification_required: boolean
  fake_certification: boolean
  fake_data: boolean
}

export interface CoreCompletionStatus {
  phases: Array<{ phase: string; status: string; note: string }>
  completion_classification: string
  fake_completion: boolean
  fake_100_percent: boolean
  completion_score_pct: number
  fake_score: boolean
  phase_d_ready: boolean
  fake_data: boolean
}

// ─── Phase C11-C20 Fetch Functions ──────────────────────────────

export async function fetchExecutionReadinessStatus(): Promise<ExecutionReadinessStatus> {
  const res = await apiFetch('/v1/execution-readiness/status')
  return res.json()
}

export async function fetchExecutionReadinessMatrix(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/execution-readiness/matrix')
  return res.json()
}

export async function fetchActionPlannerSystems(): Promise<ActionPlannerSystems> {
  const res = await apiFetch('/v1/action-planner/systems')
  return res.json()
}

export async function fetchActionPlannerTemplates(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/action-planner/templates')
  return res.json()
}

export async function fetchPolicyAuthorityMatrix(): Promise<PolicyAuthorityMatrix> {
  const res = await apiFetch('/v1/policy-compiler/authority-matrix')
  return res.json()
}

export async function fetchPolicySummary(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/policy-compiler/policy-summary')
  return res.json()
}

export async function fetchConnectorReadinessStatus(): Promise<ConnectorReadinessStatus> {
  const res = await apiFetch('/v1/connector-readiness/status')
  return res.json()
}

export async function fetchIOSReadinessStatus(): Promise<IOSReadinessStatus> {
  const res = await apiFetch('/v1/ios-readiness/status')
  return res.json()
}

export async function fetchIOSPrerequisites(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/ios-readiness/prerequisites')
  return res.json()
}

export async function fetchSigningReadinessStatus(): Promise<SigningReadinessStatus> {
  const res = await apiFetch('/v1/signing-readiness/status')
  return res.json()
}

export async function fetchSigningPrerequisites(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/signing-readiness/prerequisites')
  return res.json()
}

export async function fetchCloudReadinessStatus(): Promise<CloudReadinessStatus> {
  const res = await apiFetch('/v1/cloud-readiness/status')
  return res.json()
}

export async function fetchCloudPrerequisitesMatrix(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/cloud-readiness/prerequisites-matrix')
  return res.json()
}

export async function fetchFinalSmokeChecklist(): Promise<FinalSmokeChecklist> {
  const res = await apiFetch('/v1/final-smoke/checklist')
  return res.json()
}

export async function fetchFinalSmokeStatus(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/final-smoke/status')
  return res.json()
}

export async function fetchDailyDriverStatus(): Promise<DailyDriverStatus> {
  const res = await apiFetch('/v1/daily-driver/status')
  return res.json()
}

export async function fetchDailyDriverChecklist(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/daily-driver/checklist')
  return res.json()
}

export async function fetchDailyDriverBlockers(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/daily-driver/blockers')
  return res.json()
}

export async function fetchCoreCompletionStatus(): Promise<CoreCompletionStatus> {
  const res = await apiFetch('/v1/core-completion/status')
  return res.json()
}

export async function fetchPhaseDOptions(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/core-completion/phase-d-options')
  return res.json()
}

export async function fetchReadinessClassification(): Promise<Record<string, unknown>> {
  const res = await apiFetch('/v1/core-completion/readiness-classification')
  return res.json()
}
