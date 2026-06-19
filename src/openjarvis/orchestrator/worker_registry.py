"""Post-NUS Hierarchical Orchestrator — Worker Registry.

Provides the initial set of specialist workers for the company agent hierarchy.
Each worker is defined by a WorkerContract. Workers are registered,
not automatically active.

Registration invariants:
  - No duplicate worker_id values.
  - All required WorkerContract fields present.
  - worker_id must be unique across the registry.
  - manager_id must reference a valid manager in the manager registry.
  - Adding a future worker requires only a new WorkerContract entry —
    no code changes to activation logic (metadata-driven).

Initial registry: 30 specialist workers across 6 departments.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from openjarvis.orchestrator.contracts import (
    WorkerContract,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_BLOCKED,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
)

# ---------------------------------------------------------------------------
# Shared policy templates
# ---------------------------------------------------------------------------

_STD_TOOL_POLICY_WORKER = {
    "allowed_by_default": False,
    "requires_explicit_allowlist": True,
}

_STD_VALIDATION_REQS = {
    "require_structured_output": True,
    "require_decision_record": True,
    "no_raw_chain_of_thought": True,
}

_STD_ESCALATION_PATH = {
    "escalate_to": "manager",
    "max_retries": 3,
    "stop_on_blocker": True,
}

_STD_TELEMETRY_POLICY = {
    "emit_events": True,
    "emit_decision_records": True,
    "emit_nus_tags": True,
}

_STD_NUS_HOOKS = {
    "learning_enabled": True,
    "scorecard_target": "worker_level",
    "failure_learning": True,
    "recommendation_eligible": True,
}

_LOW_MODEL_POOL = ["local", "cheap"]
_MID_MODEL_POOL = ["local", "cheap", "mid"]
_PREM_MODEL_POOL = ["local", "cheap", "mid", "premium"]

_ALWAYS_BLOCKED_TOOLS = [
    "production_deploy_tool",
    "auto_push_tool",
    "auto_merge_tool",
    "send_external_message_tool",
    "secret_access_tool",
    "destructive_data_tool",
]

_ALWAYS_BLOCKED_ACTIONS = [
    "production_deploy",
    "auto_push",
    "auto_merge",
    "send_external_message",
    "access_secrets",
    "destructive_data_op",
]


def _make_worker(
    worker_id: str,
    name: str,
    manager_id: str,
    department: str,
    responsibility: str,
    skills: List[str],
    allowed_tools: List[str],
    allowed_action_types: List[str],
    model_pool: Optional[List[str]] = None,
    risk_ceiling: str = RISK_LOW,
    status: str = STATUS_ACTIVE,
    extra_blocked_tools: Optional[List[str]] = None,
    extra_blocked_actions: Optional[List[str]] = None,
) -> WorkerContract:
    blocked_tools = list(_ALWAYS_BLOCKED_TOOLS) + (extra_blocked_tools or [])
    blocked_actions = list(_ALWAYS_BLOCKED_ACTIONS) + (extra_blocked_actions or [])
    return WorkerContract(
        worker_id=worker_id,
        name=name,
        manager_id=manager_id,
        department=department,
        responsibility=responsibility,
        skills=skills,
        input_contract={
            "format": "subtask",
            "required_fields": ["task_description", "skill_match", "context"],
        },
        output_contract={
            "format": "worker_result",
            "required_fields": ["result_summary", "evidence", "decision_record_id"],
            "no_raw_chain_of_thought": True,
        },
        allowed_tools=allowed_tools,
        blocked_tools=blocked_tools,
        allowed_action_types=allowed_action_types,
        blocked_action_types=blocked_actions,
        model_pool=model_pool or _MID_MODEL_POOL,
        risk_ceiling=risk_ceiling,
        validation_requirements=dict(_STD_VALIDATION_REQS),
        escalation_path=dict(_STD_ESCALATION_PATH),
        telemetry_policy=dict(_STD_TELEMETRY_POLICY),
        nus_learning_hooks=dict(_STD_NUS_HOOKS),
        status=status,
    )


# ---------------------------------------------------------------------------
# Initial worker definitions
# ---------------------------------------------------------------------------

_INITIAL_WORKERS: List[WorkerContract] = [

    # ------------------------------------------------------------------
    # Coding workers (manager: coding_manager)
    # ------------------------------------------------------------------

    _make_worker(
        worker_id="backend_worker",
        name="Backend Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility="Implements backend logic, API routes, and server-side features.",
        skills=["python", "api_routes", "fastapi", "backend_logic"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep", "git_status"],
        allowed_action_types=["local_read", "local_analysis", "file_edit_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_worker(
        worker_id="frontend_worker",
        name="Frontend Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility="Implements frontend components, UI logic, and client-side features.",
        skills=["typescript", "react", "nextjs", "css", "ui_logic"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep"],
        allowed_action_types=["local_read", "local_analysis", "file_edit_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="test_worker",
        name="Test Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility="Writes and runs unit tests, integration tests, and test fixtures.",
        skills=["pytest", "unit_testing", "test_fixtures", "coverage"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep", "test_dry_run"],
        allowed_action_types=["local_read", "local_analysis", "test_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="debug_worker",
        name="Debug Worker",
        manager_id="debugging_manager",
        department="Engineering",
        responsibility="Performs root cause analysis, error triage, and repair planning.",
        skills=["debugging", "root_cause_analysis", "error_triage", "log_analysis"],
        allowed_tools=["file_read", "grep", "log_read"],
        allowed_action_types=["local_read", "local_analysis", "log_analysis"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="refactor_worker",
        name="Refactor Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility="Plans and executes safe code refactoring with change traceability.",
        skills=["refactoring", "code_cleanup", "rename", "extract_function"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep"],
        allowed_action_types=["local_read", "local_analysis", "file_edit_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_worker(
        worker_id="integration_worker",
        name="Integration Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility="Implements integrations between services, APIs, and external systems.",
        skills=["integration", "api_clients", "webhook", "connectors"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep"],
        allowed_action_types=["local_read", "local_analysis", "file_edit_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_worker(
        worker_id="security_code_worker",
        name="Security Code Worker",
        manager_id="code_review_manager",
        department="Engineering",
        responsibility="Performs security-focused code review: injection risks, secret leaks, unsafe patterns.",
        skills=["security_review", "injection_detection", "secret_scan", "unsafe_pattern_detection"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    _make_worker(
        worker_id="performance_worker",
        name="Performance Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility="Analyses and improves code performance: bottlenecks, memory, query optimisation.",
        skills=["performance", "profiling", "bottleneck_analysis", "query_optimisation"],
        allowed_tools=["file_read", "grep", "local_analysis"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="dependency_worker",
        name="Dependency Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility="Manages package dependencies, version pinning, and dependency conflicts.",
        skills=["dependency_management", "version_pinning", "conflict_resolution"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis", "file_edit_dry_run"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="git_commit_worker",
        name="Git Commit Worker",
        manager_id="coding_manager",
        department="Engineering",
        responsibility=(
            "Prepares git commits: staged files, commit messages, pre-commit checks. "
            "Does NOT auto-push. Push requires explicit Bryan approval."
        ),
        skills=["git", "commit_preparation", "commit_message", "pre_commit"],
        allowed_tools=["git_status", "git_diff", "git_commit_dry_run"],
        allowed_action_types=["local_read", "git_status", "git_commit_dry_run"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
        extra_blocked_tools=["git_push_tool", "git_merge_tool"],
        extra_blocked_actions=["git_push", "git_merge", "git_force_push"],
    ),

    # ------------------------------------------------------------------
    # Architecture workers (manager: architecture_manager)
    # ------------------------------------------------------------------

    _make_worker(
        worker_id="system_architecture_worker",
        name="System Architecture Worker",
        manager_id="architecture_manager",
        department="Engineering",
        responsibility="Designs and reviews system-level architecture, component boundaries, and data flows.",
        skills=["system_design", "component_boundaries", "data_flow", "architecture_review"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis", "design_dry_run"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    _make_worker(
        worker_id="contract_design_worker",
        name="Contract Design Worker",
        manager_id="architecture_manager",
        department="Engineering",
        responsibility="Designs and validates agent/service contracts, schemas, and API shapes.",
        skills=["contract_design", "schema_design", "api_design", "interface_contracts"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis", "design_dry_run"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    _make_worker(
        worker_id="integration_architecture_worker",
        name="Integration Architecture Worker",
        manager_id="architecture_manager",
        department="Engineering",
        responsibility="Plans integration architecture: event flows, message buses, service boundaries.",
        skills=["integration_architecture", "event_flow", "message_bus", "service_boundaries"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis", "design_dry_run"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    _make_worker(
        worker_id="scalability_worker",
        name="Scalability Worker",
        manager_id="architecture_manager",
        department="Engineering",
        responsibility="Reviews and plans scalability: concurrency, caching, load handling.",
        skills=["scalability", "concurrency", "caching", "load_analysis"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    # ------------------------------------------------------------------
    # Testing/Validation workers (manager: testing_validation_manager)
    # ------------------------------------------------------------------

    _make_worker(
        worker_id="unit_test_worker",
        name="Unit Test Worker",
        manager_id="testing_validation_manager",
        department="Quality",
        responsibility="Writes and validates unit tests for individual functions and classes.",
        skills=["unit_testing", "pytest", "mocking", "assertions"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep", "test_dry_run"],
        allowed_action_types=["local_read", "local_analysis", "test_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="integration_test_worker",
        name="Integration Test Worker",
        manager_id="testing_validation_manager",
        department="Quality",
        responsibility="Writes and validates integration tests across service boundaries.",
        skills=["integration_testing", "end_to_end", "api_testing"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep", "test_dry_run"],
        allowed_action_types=["local_read", "local_analysis", "test_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="regression_test_worker",
        name="Regression Test Worker",
        manager_id="testing_validation_manager",
        department="Quality",
        responsibility="Plans and validates regression test coverage for changed code paths.",
        skills=["regression_testing", "coverage_analysis", "change_impact"],
        allowed_tools=["file_read", "grep", "test_dry_run"],
        allowed_action_types=["local_read", "local_analysis", "test_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="doctor_check_worker",
        name="Doctor Check Worker",
        manager_id="testing_validation_manager",
        department="Quality",
        responsibility="Runs doctor/readiness checks and reports failures with structured evidence.",
        skills=["doctor_checks", "readiness_verification", "system_health"],
        allowed_tools=["file_read", "grep", "doctor_check"],
        allowed_action_types=["local_read", "local_analysis", "doctor_check"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="acceptance_evidence_worker",
        name="Acceptance Evidence Worker",
        manager_id="testing_validation_manager",
        department="Quality",
        responsibility="Collects and structures acceptance evidence for sprint checkpoints.",
        skills=["acceptance_evidence", "checkpoint_validation", "evidence_collection"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    # ------------------------------------------------------------------
    # Governance/Safety workers (manager: governance_safety_manager)
    # ------------------------------------------------------------------

    _make_worker(
        worker_id="secret_safety_worker",
        name="Secret Safety Worker",
        manager_id="governance_safety_manager",
        department="Governance",
        responsibility="Scans for secret leaks, hardcoded credentials, and unsafe token exposure.",
        skills=["secret_scan", "credential_detection", "token_safety"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
        extra_blocked_tools=["secret_access_tool", "credential_write_tool"],
    ),

    _make_worker(
        worker_id="policy_gate_worker",
        name="Policy Gate Worker",
        manager_id="governance_safety_manager",
        department="Governance",
        responsibility="Evaluates actions against governance policies and hard gates. Blocks violations.",
        skills=["policy_evaluation", "hard_gate_enforcement", "compliance_check"],
        allowed_tools=["file_read", "grep", "policy_check"],
        allowed_action_types=["local_read", "policy_check"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_BLOCKED,
    ),

    _make_worker(
        worker_id="risk_classification_worker",
        name="Risk Classification Worker",
        manager_id="governance_safety_manager",
        department="Governance",
        responsibility="Classifies task risk level and surfaces risk factors with evidence.",
        skills=["risk_classification", "risk_factor_analysis", "safety_assessment"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    _make_worker(
        worker_id="approval_scope_worker",
        name="Approval Scope Worker",
        manager_id="governance_safety_manager",
        department="Governance",
        responsibility="Determines which actions require explicit Bryan approval and scopes approval requests.",
        skills=["approval_scoping", "action_classification", "scope_analysis"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    # ------------------------------------------------------------------
    # Research/Docs/Ops workers
    # ------------------------------------------------------------------

    _make_worker(
        worker_id="local_research_worker",
        name="Local Research Worker",
        manager_id="research_manager",
        department="Intelligence",
        responsibility="Searches local codebase and knowledge store for relevant context.",
        skills=["local_search", "codebase_exploration", "context_retrieval"],
        allowed_tools=["file_read", "grep", "local_search"],
        allowed_action_types=["local_read", "local_analysis", "search"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="documentation_worker",
        name="Documentation Worker",
        manager_id="documentation_manager",
        department="Engineering",
        responsibility="Writes and updates technical documentation. Never creates duplicate docs.",
        skills=["documentation", "technical_writing", "changelog", "readme"],
        allowed_tools=["file_read", "file_edit_dry_run", "grep"],
        allowed_action_types=["local_read", "local_analysis", "doc_dry_run"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="release_packaging_worker",
        name="Release Packaging Worker",
        manager_id="release_packaging_manager",
        department="Releases",
        responsibility=(
            "Prepares release artifacts: changelogs, version bumps, packaging readiness. "
            "Does NOT trigger deploys, DMG builds, or notarization."
        ),
        skills=["release_preparation", "versioning", "changelog_generation"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis", "release_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
        extra_blocked_tools=["deploy_tool", "dmg_tool", "notarize_tool"],
        extra_blocked_actions=["trigger_deploy", "build_dmg", "notarize"],
        status=STATUS_INACTIVE,
    ),

    _make_worker(
        worker_id="runtime_ops_worker",
        name="Runtime Ops Worker",
        manager_id="runtime_ops_manager",
        department="Operations",
        responsibility="Monitors runtime health, process state, and coordinates operational recovery.",
        skills=["runtime_monitoring", "process_health", "operational_recovery"],
        allowed_tools=["file_read", "grep", "local_analysis"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_worker(
        worker_id="cost_analysis_worker",
        name="Cost Analysis Worker",
        manager_id="cost_routing_manager",
        department="Operations",
        responsibility="Analyses token/cost estimates, model routing decisions, and budget impact.",
        skills=["cost_analysis", "token_estimation", "budget_analysis", "model_routing"],
        allowed_tools=["file_read", "grep"],
        allowed_action_types=["local_read", "local_analysis"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_worker(
        worker_id="data_worker",
        name="Data Worker",
        manager_id="data_manager",
        department="Data",
        responsibility="Performs data analysis, schema inspection, and safe data query review.",
        skills=["data_analysis", "schema_review", "query_analysis", "data_safety"],
        allowed_tools=["file_read", "grep", "local_analysis"],
        allowed_action_types=["local_read", "local_analysis", "data_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_worker(
        worker_id="nus_learning_worker",
        name="NUS Learning Worker",
        manager_id="nus_learning_manager",
        department="Intelligence",
        responsibility=(
            "Ingests telemetry, generates scorecards, analyses failure patterns, "
            "and feeds NUS recommendation workflow."
        ),
        skills=["nus_telemetry", "scorecard_generation", "failure_pattern_analysis"],
        allowed_tools=["file_read", "grep", "nus_dry_run"],
        allowed_action_types=["local_read", "local_analysis", "nus_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),
]


# ---------------------------------------------------------------------------
# WorkerRegistry
# ---------------------------------------------------------------------------

class WorkerRegistry:
    """Registry of specialist workers.

    Enforces uniqueness, validates manager references, provides lookup
    by ID/manager/skill, and validates all worker contracts on load.

    Future workers can be added via register() without code changes to
    activation logic (metadata-driven design).
    """

    def __init__(self) -> None:
        self._workers: Dict[str, WorkerContract] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for w in _INITIAL_WORKERS:
            self._register_unchecked(w)

    def _register_unchecked(self, worker: WorkerContract) -> None:
        if worker.worker_id in self._workers:
            raise ValueError(
                f"Duplicate worker_id '{worker.worker_id}' — "
                "each worker must have a unique ID."
            )
        errors = worker.validate()
        if errors:
            raise ValueError(
                f"Worker '{worker.worker_id}' has contract errors: {errors}"
            )
        self._workers[worker.worker_id] = worker

    def register(self, worker: WorkerContract) -> None:
        """Register a new worker. Raises ValueError on duplicate or invalid contract."""
        self._register_unchecked(worker)

    def get(self, worker_id: str) -> Optional[WorkerContract]:
        return self._workers.get(worker_id)

    def list_all(self) -> List[WorkerContract]:
        return list(self._workers.values())

    def list_active(self) -> List[WorkerContract]:
        return [w for w in self._workers.values() if w.status == STATUS_ACTIVE]

    def list_by_manager(self, manager_id: str) -> List[WorkerContract]:
        return [w for w in self._workers.values() if w.manager_id == manager_id]

    def list_by_skill(self, skill: str) -> List[WorkerContract]:
        return [w for w in self._workers.values() if skill in w.skills]

    def ids(self) -> List[str]:
        return list(self._workers.keys())

    def count(self) -> int:
        return len(self._workers)

    def has_duplicate_ids(self) -> bool:
        return False  # invariant: _register_unchecked raises on duplicate

    def validate_all(self) -> Dict[str, List[str]]:
        """Return dict of worker_id → [errors]. Empty list = valid."""
        return {wid: w.validate() for wid, w in self._workers.items()}

    def validate_manager_references(self, valid_manager_ids: List[str]) -> Dict[str, str]:
        """Return dict of worker_id → error for workers with invalid manager_id."""
        errors: Dict[str, str] = {}
        for wid, w in self._workers.items():
            if w.manager_id not in valid_manager_ids:
                errors[wid] = f"manager_id '{w.manager_id}' not found in manager registry"
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count(),
            "worker_ids": self.ids(),
            "workers": [w.to_dict() for w in self.list_all()],
        }


# Module-level singleton
_registry: Optional[WorkerRegistry] = None


def get_worker_registry() -> WorkerRegistry:
    global _registry
    if _registry is None:
        _registry = WorkerRegistry()
    return _registry


__all__ = [
    "WorkerRegistry",
    "get_worker_registry",
]
