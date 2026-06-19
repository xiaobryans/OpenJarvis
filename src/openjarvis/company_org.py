"""Jarvis Company Org — Machine-readable company structure specification.

This module is the authoritative source for:
  - All Jarvis hierarchy roles (Jarvis / COS / GM / Managers / Workers / Verifier)
  - Capability coverage per role (tools, skills, allowed/blocked actions)
  - Worker team assignments (dynamic, justified by task need)
  - Escalation protocol
  - Parallel execution policy
  - Stall/timeout policy
  - Artifact output policy
  - Slack persona mapping

Design invariants:
  - Worker count is NOT fixed. Teams are assembled by task need.
  - Fake/headcount-only agents are FORBIDDEN.
  - Verifier is always independent of the team being verified.
  - Every role maps to real tools/skills or is classified REQUIRED_AND_MISSING.
  - Partial accept / subpar completion is NOT accepted.

Status legend per row:
  VERIFIED_PRESENT         — implemented and tested in this repo
  IMPLEMENTED_THIS_SPRINT  — implemented in Sprint 3
  REQUIRED_AND_MISSING     — must be present for NO_GAP_JARVIS, not yet done
  BLOCKED_WAITING_FOR_BRYAN_NOW — needs Bryan approval/input to proceed
  BLOCKED_LOCAL_TOOLCHAIN  — blocked by local environment / credentials
  BLOCKED_EXTERNAL_PROVIDER — blocked by third-party API / service
  CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN — design was changed; prior gap closed

Sprint: Full No-Gap Jarvis — Combined Sprint 3 (Company Org + Mobile Continuity)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

class CapabilityStatus(str, Enum):
    VERIFIED_PRESENT = "VERIFIED_PRESENT"
    IMPLEMENTED_THIS_SPRINT = "IMPLEMENTED_THIS_SPRINT"
    REQUIRED_AND_MISSING = "REQUIRED_AND_MISSING"
    BLOCKED_WAITING_FOR_BRYAN_NOW = "BLOCKED_WAITING_FOR_BRYAN_NOW"
    BLOCKED_LOCAL_TOOLCHAIN = "BLOCKED_LOCAL_TOOLCHAIN"
    BLOCKED_EXTERNAL_PROVIDER = "BLOCKED_EXTERNAL_PROVIDER"
    CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN = "CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN"


# ---------------------------------------------------------------------------
# Role tiers
# ---------------------------------------------------------------------------

class RoleTier(str, Enum):
    JARVIS = "jarvis"           # Top-level front door / OS
    COS = "cos"                 # Chief of Staff
    GM = "gm"                   # General Manager
    MANAGER = "manager"         # Domain manager
    WORKER = "worker"           # Virtual worker
    VERIFIER = "verifier"       # Independent audit gate


# ---------------------------------------------------------------------------
# Stall policy
# ---------------------------------------------------------------------------

@dataclass
class StallPolicy:
    """Defines stall detection and reassignment rules per role."""
    timeout_seconds: int
    reassignable: bool
    reassignment_target: str     # role_id or "manager" / "cos" / "bryan"
    stall_action: str            # "report_and_reassign" | "report_only" | "escalate"
    description: str


# ---------------------------------------------------------------------------
# Role capability spec
# ---------------------------------------------------------------------------

@dataclass
class RoleCapabilitySpec:
    """Full capability specification for one Jarvis role."""

    role_id: str
    role_title: str
    tier: RoleTier
    description: str
    responsibilities: List[str]

    required_tools: List[str]
    required_skills: List[str]
    allowed_actions: List[str]
    blocked_actions: List[str]
    output_artifacts: List[str]

    validation_gates: List[str]
    escalation_path: List[str]   # ordered: immediate escalation → final escalation

    stall_policy: StallPolicy
    reassignment_policy: str

    parallelizable: bool         # can this role's tasks run in parallel with others?
    parallel_conditions: str     # what must be true for parallelization to be safe

    slack_persona: Optional[str] = None
    slack_bot_configured: bool = False
    slack_channel: Optional[str] = None

    tool_coverage_status: CapabilityStatus = CapabilityStatus.VERIFIED_PRESENT
    skill_coverage_status: CapabilityStatus = CapabilityStatus.VERIFIED_PRESENT

    missing_tools: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_title": self.role_title,
            "tier": self.tier.value,
            "description": self.description,
            "responsibilities": self.responsibilities,
            "required_tools": self.required_tools,
            "required_skills": self.required_skills,
            "allowed_actions": self.allowed_actions,
            "blocked_actions": self.blocked_actions,
            "output_artifacts": self.output_artifacts,
            "validation_gates": self.validation_gates,
            "escalation_path": self.escalation_path,
            "stall_policy": {
                "timeout_seconds": self.stall_policy.timeout_seconds,
                "reassignable": self.stall_policy.reassignable,
                "reassignment_target": self.stall_policy.reassignment_target,
                "stall_action": self.stall_policy.stall_action,
                "description": self.stall_policy.description,
            },
            "reassignment_policy": self.reassignment_policy,
            "parallelizable": self.parallelizable,
            "parallel_conditions": self.parallel_conditions,
            "slack_persona": self.slack_persona,
            "slack_bot_configured": self.slack_bot_configured,
            "slack_channel": self.slack_channel,
            "tool_coverage_status": self.tool_coverage_status.value,
            "skill_coverage_status": self.skill_coverage_status.value,
            "missing_tools": self.missing_tools,
            "missing_skills": self.missing_skills,
        }


# ---------------------------------------------------------------------------
# Worker assignment (dynamic teams)
# ---------------------------------------------------------------------------

@dataclass
class WorkerTeam:
    """A dynamic team of workers assigned to a manager for a task context."""

    team_id: str
    manager_role_id: str
    task_context: str          # why these workers are assigned (justification)
    workers: List[str]         # list of worker role_ids
    parallelizable_workers: List[str]   # workers that can run in parallel
    sequenced_groups: List[List[str]]   # groups that must run in order
    max_stall_seconds: int
    requires_verifier: bool
    verifier_role_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "manager_role_id": self.manager_role_id,
            "task_context": self.task_context,
            "workers": self.workers,
            "parallelizable_workers": self.parallelizable_workers,
            "sequenced_groups": self.sequenced_groups,
            "max_stall_seconds": self.max_stall_seconds,
            "requires_verifier": self.requires_verifier,
            "verifier_role_id": self.verifier_role_id,
        }


# ---------------------------------------------------------------------------
# Canonical role definitions
# ---------------------------------------------------------------------------

def _build_jarvis_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="jarvis",
        role_title="Jarvis — Universal Front Door / Operating System",
        tier=RoleTier.JARVIS,
        description=(
            "Bryan's universal private AI operating system. Single entry point for all "
            "requests — personal, project, automation, research, business. Routes to COS "
            "for complex tasks. Handles simple tasks directly. Never OMNIX-only."
        ),
        responsibilities=[
            "Accept any request from Bryan",
            "Classify intent, risk, complexity",
            "Route to COS/GM for multi-step tasks",
            "Handle simple single-step tasks directly",
            "Apply governance gates (hard gates, cost law)",
            "Emit telemetry for all interactions",
            "Surface blockers immediately without working around them",
        ],
        required_tools=[
            "jarvis_registry",
            "shell_exec",
            "file_read",
            "file_write",
            "git_tool",
            "web_search",
            "knowledge_search",
            "memory_manage",
            "think",
            "llm_tool",
        ],
        required_skills=[
            "intent_classification",
            "risk_assessment",
            "routing",
            "governance",
            "cost_governance",
            "telemetry",
        ],
        allowed_actions=[
            "read_any_file",
            "run_safe_commands",
            "search_web",
            "query_memory",
            "route_to_cos",
            "handle_simple_task",
            "emit_telemetry",
            "surface_blocker",
        ],
        blocked_actions=[
            "auto_push",
            "auto_merge",
            "production_deploy",
            "external_send_without_approval",
            "expose_secrets",
            "bypass_hard_gate",
            "us13_voice_activation",
            "claim_no_gap_complete_without_evidence",
        ],
        output_artifacts=[
            "task_routing_decision",
            "front_door_result",
            "telemetry_event",
            "blocker_report",
        ],
        validation_gates=[
            "governance_constitution_check",
            "hard_gate_check",
            "cost_law_check",
        ],
        escalation_path=["cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=300,
            reassignable=False,
            reassignment_target="bryan",
            stall_action="escalate",
            description="Jarvis front door does not stall — escalates to Bryan if blocked.",
        ),
        reassignment_policy="not_applicable_front_door",
        parallelizable=False,
        parallel_conditions="Front door is serial by design — one request at a time.",
        slack_persona="jarvis-hq",
        slack_bot_configured=True,
        slack_channel="jarvis-ops",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_cos_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="cos",
        role_title="COS — Chief of Staff",
        tier=RoleTier.COS,
        description=(
            "Chief of Staff. Receives routed tasks from Jarvis front door. "
            "Prioritizes work, assembles manager/worker teams, coordinates GM. "
            "Escalates to Bryan for hard gates and unresolvable blockers."
        ),
        responsibilities=[
            "Receive task routing from Jarvis front door",
            "Prioritize tasks by urgency/impact",
            "Assemble dynamic manager teams for complex tasks",
            "Coordinate GM for execution oversight",
            "Enforce NUS governance on all delegation",
            "Escalate blockers and hard-gate actions to Bryan",
            "Emit decision records for all routing choices",
        ],
        required_tools=[
            "jarvis_registry",
            "llm_tool",
            "knowledge_search",
            "memory_manage",
            "think",
            "approval_store",
        ],
        required_skills=[
            "task_prioritization",
            "manager_selection",
            "team_assembly",
            "governance",
            "escalation",
            "decision_record_emit",
        ],
        allowed_actions=[
            "prioritize_tasks",
            "assemble_manager_team",
            "delegate_to_gm",
            "escalate_to_bryan",
            "emit_decision_record",
            "surface_blocker",
            "query_memory",
        ],
        blocked_actions=[
            "auto_push",
            "auto_merge",
            "production_deploy",
            "external_send_without_approval",
            "bypass_hard_gate",
            "claim_completion_without_evidence",
        ],
        output_artifacts=[
            "task_routing_decision",
            "activation_plan",
            "decision_record",
            "blocker_report",
        ],
        validation_gates=[
            "hard_gate_check",
            "nus_governance_check",
            "decision_record_required",
        ],
        escalation_path=["bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=600,
            reassignable=False,
            reassignment_target="bryan",
            stall_action="escalate",
            description="COS stall → escalate to Bryan with exact evidence.",
        ),
        reassignment_policy="escalate_to_bryan_with_evidence",
        parallelizable=False,
        parallel_conditions="COS is serial coordinator — orchestrates parallel work below it.",
        slack_persona="jarvis-cos",
        slack_bot_configured=True,
        slack_channel="jarvis-ops",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_gm_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="gm",
        role_title="GM — General Manager",
        tier=RoleTier.GM,
        description=(
            "General Manager. Oversees all domain managers. Coordinates parallel "
            "execution where safe. Detects stalled managers. Aggregates results "
            "and reports to COS. Does not execute tasks directly."
        ),
        responsibilities=[
            "Receive activation plan from COS",
            "Activate domain managers",
            "Coordinate parallel safe execution across managers",
            "Detect stalled managers (timeout-based)",
            "Aggregate manager results",
            "Report consolidated result to COS",
            "Surface conflicts and missing evidence",
        ],
        required_tools=[
            "jarvis_registry",
            "llm_tool",
            "knowledge_search",
            "think",
        ],
        required_skills=[
            "parallel_execution_coordination",
            "stall_detection",
            "result_aggregation",
            "conflict_surfacing",
        ],
        allowed_actions=[
            "activate_manager",
            "coordinate_parallel_execution",
            "detect_stall",
            "aggregate_results",
            "report_to_cos",
            "surface_conflict",
        ],
        blocked_actions=[
            "auto_push",
            "external_send_without_approval",
            "bypass_hard_gate",
            "execute_code_directly",
        ],
        output_artifacts=[
            "aggregated_execution_result",
            "stall_report",
            "conflict_report",
        ],
        validation_gates=[
            "result_evidence_required",
            "stall_check_required",
        ],
        escalation_path=["cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=600,
            reassignable=False,
            reassignment_target="cos",
            stall_action="report_and_reassign",
            description="GM stall → report to COS with exact evidence.",
        ),
        reassignment_policy="report_to_cos_with_fix_list",
        parallelizable=False,
        parallel_conditions="GM coordinates parallel work below it; GM itself is serial.",
        slack_persona="jarvis-gm",
        slack_bot_configured=True,
        slack_channel="jarvis-ops",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_coding_manager_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="manager-coding",
        role_title="Coding Manager",
        tier=RoleTier.MANAGER,
        description=(
            "Manages coding workers: repo inspector, test runner, linter, refactor. "
            "Assembles team dynamically based on task scope. Reports to GM."
        ),
        responsibilities=[
            "Receive coding task from GM",
            "Assemble justified coding worker team",
            "Coordinate repo-inspector, test-runner, linter, refactor workers",
            "Detect stalled coding workers",
            "Aggregate coding artifacts",
            "Report to GM with evidence",
        ],
        required_tools=[
            "shell_exec",
            "git_tool",
            "file_read",
            "file_write",
            "file_search",
            "apply_patch",
        ],
        required_skills=[
            "code_review",
            "test_execution",
            "linting",
            "refactoring",
            "diff_review",
        ],
        allowed_actions=[
            "read_code",
            "run_tests",
            "run_linter",
            "apply_targeted_patch",
            "run_git_diff",
            "run_git_status",
            "emit_artifact",
        ],
        blocked_actions=[
            "auto_push",
            "auto_merge",
            "production_deploy",
            "delete_working_code",
            "bypass_test_gate",
        ],
        output_artifacts=[
            "test_results_file",
            "lint_report_file",
            "diff_review_file",
            "coding_task_result",
        ],
        validation_gates=[
            "test_pass_required",
            "no_lint_errors_introduced",
            "diff_review_signed_off",
        ],
        escalation_path=["gm", "cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=300,
            reassignable=True,
            reassignment_target="gm",
            stall_action="report_and_reassign",
            description="Coding manager stall → report to GM, reassign if safe.",
        ),
        reassignment_policy="report_to_gm_reassign_if_safe",
        parallelizable=True,
        parallel_conditions="Safe when no shared file write conflicts exist.",
        slack_persona="jarvis-coding-mgr",
        slack_bot_configured=True,
        slack_channel="jarvis-coding",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_research_manager_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="manager-research",
        role_title="Research Manager",
        tier=RoleTier.MANAGER,
        description=(
            "Manages research and intelligence workers. Coordinates web search, "
            "knowledge retrieval, deep research, source verification."
        ),
        responsibilities=[
            "Receive research task from GM",
            "Assemble research worker team",
            "Coordinate web-searcher, knowledge-retriever, deep-research workers",
            "Verify source quality and evidence",
            "Detect stalled research workers",
            "Report to GM with verified findings",
        ],
        required_tools=[
            "web_search",
            "knowledge_search",
            "knowledge_sql",
            "retrieval",
            "llm_tool",
        ],
        required_skills=[
            "source_verification",
            "evidence_synthesis",
            "research_loop",
            "fact_checking",
        ],
        allowed_actions=[
            "search_web",
            "query_knowledge",
            "retrieve_documents",
            "synthesize_findings",
            "emit_artifact",
        ],
        blocked_actions=[
            "invent_facts",
            "claim_verified_without_source",
            "external_send_without_approval",
        ],
        output_artifacts=[
            "research_report_file",
            "source_verification_record",
            "findings_summary",
        ],
        validation_gates=[
            "source_citation_required",
            "no_hallucination_check",
            "evidence_trace_required",
        ],
        escalation_path=["gm", "cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=300,
            reassignable=True,
            reassignment_target="gm",
            stall_action="report_and_reassign",
            description="Research manager stall → report to GM.",
        ),
        reassignment_policy="report_to_gm_reassign_if_safe",
        parallelizable=True,
        parallel_conditions="Research tasks can parallelize when not sharing the same query cache.",
        slack_persona="jarvis-research-mgr",
        slack_bot_configured=True,
        slack_channel="jarvis-tasks",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_memory_manager_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="manager-memory",
        role_title="Memory Manager",
        tier=RoleTier.MANAGER,
        description=(
            "Manages memory workers: cloud sync, Obsidian export, correction. "
            "Ensures memory integrity and cross-device continuity hooks."
        ),
        responsibilities=[
            "Receive memory task from GM",
            "Coordinate cloud-sync, obsidian-exporter, correction workers",
            "Detect memory conflicts and stale artifacts",
            "Apply human corrections",
            "Report to GM with memory state evidence",
        ],
        required_tools=[
            "memory_manage",
            "storage_tools",
            "knowledge_tools",
        ],
        required_skills=[
            "memory_continuity",
            "conflict_detection",
            "correction_application",
            "cloud_sync",
        ],
        allowed_actions=[
            "read_memory",
            "write_memory",
            "sync_to_cloud",
            "export_to_obsidian",
            "apply_correction",
            "detect_conflict",
        ],
        blocked_actions=[
            "delete_verified_memory",
            "overwrite_without_conflict_check",
            "expose_secrets_in_memory",
        ],
        output_artifacts=[
            "memory_sync_report",
            "conflict_report",
            "obsidian_export",
        ],
        validation_gates=[
            "no_secret_in_memory_check",
            "conflict_check_required",
            "sync_status_confirmed",
        ],
        escalation_path=["gm", "cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=300,
            reassignable=True,
            reassignment_target="gm",
            stall_action="report_and_reassign",
            description="Memory manager stall → report to GM.",
        ),
        reassignment_policy="report_to_gm_reassign_if_safe",
        parallelizable=True,
        parallel_conditions="Memory reads can parallelize; writes require conflict check first.",
        slack_persona="jarvis-memory-mgr",
        slack_bot_configured=True,
        slack_channel="jarvis-memory",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_connector_manager_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="manager-connector",
        role_title="Connector Manager",
        tier=RoleTier.MANAGER,
        description=(
            "Manages connector agents: Slack, Telegram, Gmail (when enabled). "
            "All external sends require Bryan approval. Single-bot Slack architecture."
        ),
        responsibilities=[
            "Receive connector task from GM",
            "Gate all external sends with approval check",
            "Coordinate Slack, Telegram connector workers",
            "Report connector status and failures to GM",
        ],
        required_tools=[
            "channel_tools",
            "approval_store",
            "http_request",
        ],
        required_skills=[
            "send_gating",
            "connector_health_check",
            "approval_enforcement",
        ],
        allowed_actions=[
            "check_connector_health",
            "queue_message_for_approval",
            "send_after_approval",
            "report_connector_status",
        ],
        blocked_actions=[
            "external_send_without_approval",
            "expose_webhook_secrets",
            "send_customer_messages_without_approval",
        ],
        output_artifacts=[
            "connector_health_report",
            "send_approval_request",
            "send_confirmation",
        ],
        validation_gates=[
            "approval_required_for_all_sends",
            "no_customer_messages_in_sprint",
        ],
        escalation_path=["gm", "cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=300,
            reassignable=True,
            reassignment_target="gm",
            stall_action="report_and_reassign",
            description="Connector manager stall → report to GM.",
        ),
        reassignment_policy="report_to_gm_reassign_if_safe",
        parallelizable=False,
        parallel_conditions="Connector sends must be serial to prevent duplicate messages.",
        slack_persona="jarvis-connector-mgr",
        slack_bot_configured=True,
        slack_channel="jarvis-connectors",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_ops_safety_manager_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="manager-ops-safety",
        role_title="Ops/Safety Manager",
        tier=RoleTier.MANAGER,
        description=(
            "Manages safety policy, audit, and ops compliance. Blocks unsafe actions. "
            "Never bypassed. Escalates safety violations directly to Bryan."
        ),
        responsibilities=[
            "Enforce governance constitution",
            "Block hard-gate violations",
            "Audit agent actions for safety compliance",
            "Detect and surface unsafe patterns",
            "Report safety status to GM",
        ],
        required_tools=[
            "approval_store",
            "jarvis_registry",
            "think",
        ],
        required_skills=[
            "governance_enforcement",
            "hard_gate_check",
            "safety_audit",
            "violation_detection",
        ],
        allowed_actions=[
            "enforce_governance",
            "block_unsafe_action",
            "audit_agent_output",
            "surface_safety_violation",
            "escalate_to_bryan",
        ],
        blocked_actions=[
            "bypass_hard_gate",
            "allow_production_deploy_without_approval",
            "suppress_safety_violation",
        ],
        output_artifacts=[
            "safety_audit_report",
            "violation_report",
            "governance_check_result",
        ],
        validation_gates=[
            "hard_gate_never_bypassed",
            "all_violations_reported",
        ],
        escalation_path=["cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=120,
            reassignable=False,
            reassignment_target="bryan",
            stall_action="escalate",
            description="Safety manager stall → escalate directly to Bryan.",
        ),
        reassignment_policy="escalate_to_bryan_with_evidence",
        parallelizable=False,
        parallel_conditions="Safety enforcement is serial — must audit all actions.",
        slack_persona="jarvis-ops-safety-mgr",
        slack_bot_configured=True,
        slack_channel="jarvis-ops",
        tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
        skill_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
    )


def _build_verifier_role() -> RoleCapabilitySpec:
    return RoleCapabilitySpec(
        role_id="verifier",
        role_title="Verifier — Independent Audit Gate",
        tier=RoleTier.VERIFIER,
        description=(
            "Independent validation and audit gate. Operates outside the team being "
            "verified. Traces every claim/figure/row/status to evidence. Rejects "
            "unsupported rows, contradictions, stale artifacts, and fake readiness. "
            "Returns a concrete fix list. Blocks acceptance when evidence is incomplete."
        ),
        responsibilities=[
            "Trace every claim to evidence",
            "Surface contradictions and conflicts",
            "Reject unsupported rows",
            "Detect stale artifacts",
            "Detect fake readiness",
            "Return concrete fix list",
            "Block acceptance when evidence is incomplete",
            "Accept with full trace when evidence is sufficient",
        ],
        required_tools=[
            "jarvis_registry",
            "file_read",
            "knowledge_search",
            "think",
        ],
        required_skills=[
            "evidence_tracing",
            "contradiction_detection",
            "stale_artifact_detection",
            "fix_list_generation",
            "acceptance_gating",
        ],
        allowed_actions=[
            "read_artifacts",
            "trace_evidence",
            "reject_with_fix_list",
            "accept_with_trace",
            "surface_contradiction",
            "surface_stale_artifact",
            "block_acceptance",
        ],
        blocked_actions=[
            "self_verify",
            "verify_own_output",
            "accept_without_evidence",
            "suppress_contradiction",
            "claim_ready_without_proof",
        ],
        output_artifacts=[
            "verification_report",
            "fix_list",
            "acceptance_trace",
            "rejection_report",
        ],
        validation_gates=[
            "never_self_verify",
            "all_claims_traced",
            "fix_list_required_on_rejection",
        ],
        escalation_path=["cos", "bryan"],
        stall_policy=StallPolicy(
            timeout_seconds=300,
            reassignable=False,
            reassignment_target="cos",
            stall_action="report_only",
            description="Verifier stall → report to COS; do not reassign to prevent capture.",
        ),
        reassignment_policy="report_to_cos_only_never_reassign_to_team",
        parallelizable=False,
        parallel_conditions="Verifier is serial — must have full picture before accepting.",
        slack_persona="jarvis-hq",
        slack_bot_configured=True,
        slack_channel="jarvis-ops",
        tool_coverage_status=CapabilityStatus.IMPLEMENTED_THIS_SPRINT,
        skill_coverage_status=CapabilityStatus.IMPLEMENTED_THIS_SPRINT,
    )


def _build_worker_roles() -> List[RoleCapabilitySpec]:
    """Virtual worker roles — assembled dynamically by need, not fixed."""
    return [
        RoleCapabilitySpec(
            role_id="worker-repo-inspector",
            role_title="Worker: repo-inspector",
            tier=RoleTier.WORKER,
            description="Scans changed files, diffs, structure. Reports to Coding Manager.",
            responsibilities=["scan_changed_files", "compute_diff", "report_structure"],
            required_tools=["file_read", "file_search", "git_tool"],
            required_skills=["diff_analysis", "change_detection"],
            allowed_actions=["read_files", "run_git_diff", "scan_dirs"],
            blocked_actions=["write_files", "push", "deploy"],
            output_artifacts=["diff_report", "changed_files_list"],
            validation_gates=["output_is_structured"],
            escalation_path=["manager-coding", "gm"],
            stall_policy=StallPolicy(
                timeout_seconds=300,
                reassignable=True,
                reassignment_target="manager-coding",
                stall_action="report_and_reassign",
                description="repo-inspector stall → reassign to manager.",
            ),
            reassignment_policy="report_to_manager_reassign",
            parallelizable=True,
            parallel_conditions="Read-only; safe to parallelize.",
        ),
        RoleCapabilitySpec(
            role_id="worker-test-runner",
            role_title="Worker: test-runner",
            tier=RoleTier.WORKER,
            description="Runs targeted tests. Reports pass/fail to Coding Manager.",
            responsibilities=["run_targeted_tests", "report_pass_fail"],
            required_tools=["shell_exec"],
            required_skills=["test_execution"],
            allowed_actions=["run_tests", "read_test_output"],
            blocked_actions=["write_production_code", "push", "deploy"],
            output_artifacts=["test_result_file"],
            validation_gates=["test_output_captured"],
            escalation_path=["manager-coding", "gm"],
            stall_policy=StallPolicy(
                timeout_seconds=300,
                reassignable=True,
                reassignment_target="manager-coding",
                stall_action="report_and_reassign",
                description="test-runner stall → report to coding manager.",
            ),
            reassignment_policy="report_to_manager_reassign",
            parallelizable=True,
            parallel_conditions="Safe when test files don't share state.",
        ),
        RoleCapabilitySpec(
            role_id="worker-obsidian-exporter",
            role_title="Worker: obsidian-exporter",
            tier=RoleTier.WORKER,
            description="Exports sprint summaries, decisions, blocker ledger to Obsidian vault.",
            responsibilities=["export_sprint_summary", "export_blocker_ledger"],
            required_tools=["file_write", "knowledge_tools"],
            required_skills=["obsidian_export"],
            allowed_actions=["write_obsidian_vault", "read_docs"],
            blocked_actions=["expose_secrets", "overwrite_without_backup"],
            output_artifacts=["obsidian_export_file"],
            validation_gates=["no_secrets_in_export"],
            escalation_path=["manager-memory", "gm"],
            stall_policy=StallPolicy(
                timeout_seconds=300,
                reassignable=True,
                reassignment_target="manager-memory",
                stall_action="report_and_reassign",
                description="obsidian-exporter stall → report to memory manager.",
            ),
            reassignment_policy="report_to_manager_reassign",
            parallelizable=True,
            parallel_conditions="Export is write-only to vault; safe to parallelize different docs.",
        ),
        RoleCapabilitySpec(
            role_id="worker-memory-sync",
            role_title="Worker: memory-sync",
            tier=RoleTier.WORKER,
            description=(
                "Syncs memory to local SQLite store (founder-local architecture). "
                "Cloud multi-device sync is REQUIRED_FOR_NO_GAP_JARVIS but not needed "
                "for single-MacBook founder-local operations where SQLite is authoritative."
            ),
            responsibilities=["sync_memory_to_local_store", "report_sync_status"],
            required_tools=["memory_manage", "storage_tools"],
            required_skills=["local_memory_sync"],
            allowed_actions=["read_local_memory", "write_local_memory", "report_sync_status"],
            blocked_actions=["expose_credentials", "sync_without_conflict_check"],
            output_artifacts=["sync_status_report"],
            validation_gates=["conflict_check_passed", "no_secrets_in_memory"],
            escalation_path=["manager-memory", "gm"],
            stall_policy=StallPolicy(
                timeout_seconds=300,
                reassignable=True,
                reassignment_target="manager-memory",
                stall_action="report_and_reassign",
                description="memory-sync stall → report to memory manager.",
            ),
            reassignment_policy="report_to_manager_reassign",
            parallelizable=False,
            parallel_conditions="Memory sync is serial to prevent write conflicts.",
            tool_coverage_status=CapabilityStatus.VERIFIED_PRESENT,
            skill_coverage_status=CapabilityStatus.CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN,
            missing_skills=[],
        ),
    ]


# ---------------------------------------------------------------------------
# Company Org Spec — canonical registry
# ---------------------------------------------------------------------------

@dataclass
class CompanyOrgSpec:
    """The canonical Jarvis company org specification."""

    spec_version: str
    sprint: str
    generated_at: float
    roles: List[RoleCapabilitySpec]
    default_worker_teams: List[WorkerTeam]
    escalation_protocol: str
    voice_status: str
    no_gap_status: str
    mobile_continuity_status: str

    def get_role(self, role_id: str) -> Optional[RoleCapabilitySpec]:
        for r in self.roles:
            if r.role_id == role_id:
                return r
        return None

    def list_by_tier(self, tier: RoleTier) -> List[RoleCapabilitySpec]:
        return [r for r in self.roles if r.tier == tier]

    def list_managers(self) -> List[RoleCapabilitySpec]:
        return self.list_by_tier(RoleTier.MANAGER)

    def list_workers(self) -> List[RoleCapabilitySpec]:
        return self.list_by_tier(RoleTier.WORKER)

    def get_verifier(self) -> Optional[RoleCapabilitySpec]:
        results = self.list_by_tier(RoleTier.VERIFIER)
        return results[0] if results else None

    def get_missing_capabilities(self) -> List[Dict[str, Any]]:
        """Return all roles with REQUIRED_AND_MISSING or BLOCKED status."""
        out = []
        for r in self.roles:
            if r.tool_coverage_status == CapabilityStatus.REQUIRED_AND_MISSING:
                out.append({"role_id": r.role_id, "missing": "tools", "detail": r.missing_tools})
            if r.skill_coverage_status == CapabilityStatus.REQUIRED_AND_MISSING:
                out.append({"role_id": r.role_id, "missing": "skills", "detail": r.missing_skills})
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_version": self.spec_version,
            "sprint": self.sprint,
            "generated_at": self.generated_at,
            "escalation_protocol": self.escalation_protocol,
            "voice_status": self.voice_status,
            "no_gap_status": self.no_gap_status,
            "mobile_continuity_status": self.mobile_continuity_status,
            "roles": [r.to_dict() for r in self.roles],
            "default_worker_teams": [t.to_dict() for t in self.default_worker_teams],
        }


def _build_default_worker_teams() -> List[WorkerTeam]:
    """Default illustrative worker teams — dynamically justified by task."""
    return [
        WorkerTeam(
            team_id="coding-sprint-team",
            manager_role_id="manager-coding",
            task_context="Code inspection + test run + lint for a single sprint",
            workers=["worker-repo-inspector", "worker-test-runner"],
            parallelizable_workers=["worker-repo-inspector", "worker-test-runner"],
            sequenced_groups=[["worker-repo-inspector"], ["worker-test-runner"]],
            max_stall_seconds=300,
            requires_verifier=True,
            verifier_role_id="verifier",
        ),
        WorkerTeam(
            team_id="memory-export-team",
            manager_role_id="manager-memory",
            task_context="Sync + Obsidian export for sprint close",
            workers=["worker-memory-sync", "worker-obsidian-exporter"],
            parallelizable_workers=["worker-obsidian-exporter"],
            sequenced_groups=[["worker-memory-sync"], ["worker-obsidian-exporter"]],
            max_stall_seconds=300,
            requires_verifier=False,
        ),
    ]


def build_company_org_spec() -> CompanyOrgSpec:
    """Build the canonical Jarvis company org spec for Sprint 3."""
    roles: List[RoleCapabilitySpec] = [
        _build_jarvis_role(),
        _build_cos_role(),
        _build_gm_role(),
        _build_coding_manager_role(),
        _build_research_manager_role(),
        _build_memory_manager_role(),
        _build_connector_manager_role(),
        _build_ops_safety_manager_role(),
        _build_verifier_role(),
    ]
    roles.extend(_build_worker_roles())

    return CompanyOrgSpec(
        spec_version="3.0.0",
        sprint="Full No-Gap Jarvis — Combined Sprint 3: Company Org + Mobile Continuity",
        generated_at=time.time(),
        roles=roles,
        default_worker_teams=_build_default_worker_teams(),
        escalation_protocol="Worker → Manager → GM → COS → Bryan",
        voice_status="HOLD — separate required sprint, not activated here",
        no_gap_status="HOLD — full no-gap certification not yet complete",
        mobile_continuity_status="WIRED_AND_TESTED — API routes + local store + mobile web path via React SPA; native iOS/Android app REQUIRED_FOR_NO_GAP_JARVIS",
    )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_COMPANY_ORG_SPEC: Optional[CompanyOrgSpec] = None


def get_company_org_spec() -> CompanyOrgSpec:
    """Return the module-level company org spec singleton."""
    global _COMPANY_ORG_SPEC
    if _COMPANY_ORG_SPEC is None:
        _COMPANY_ORG_SPEC = build_company_org_spec()
    return _COMPANY_ORG_SPEC


__all__ = [
    "CapabilityStatus",
    "RoleTier",
    "StallPolicy",
    "RoleCapabilitySpec",
    "WorkerTeam",
    "CompanyOrgSpec",
    "build_company_org_spec",
    "get_company_org_spec",
]
