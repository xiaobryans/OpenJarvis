"""Post-NUS Hierarchical Orchestrator — Manager Registry.

Provides the initial set of domain managers for the company agent hierarchy.
Each manager is defined by a ManagerContract. Managers are registered,
not automatically active.

Registration invariants:
  - No duplicate manager_id values.
  - All required ManagerContract fields present.
  - manager_id must be unique across the registry.
  - Adding a future manager requires only a new ManagerContract entry —
    no code changes to activation logic (metadata-driven).

Initial registry: 17 domain managers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from openjarvis.orchestrator.contracts import (
    ManagerContract,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_BLOCKED,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
)

# ---------------------------------------------------------------------------
# Shared policy templates (reduce duplication)
# ---------------------------------------------------------------------------

_STD_TOOL_POLICY = {
    "allowed_by_default": False,
    "requires_explicit_allowlist": True,
}

_STD_VALIDATION_POLICY = {
    "require_structured_output": True,
    "require_decision_record": True,
    "no_raw_chain_of_thought": True,
}

_STD_ESCALATION_POLICY = {
    "escalate_to": "cos_gm",
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
    "scorecard_target": "manager_level",
    "failure_learning": True,
    "recommendation_eligible": True,
}

_LOW_MODEL_POOL = ["local", "cheap"]
_MID_MODEL_POOL = ["local", "cheap", "mid"]
_PREM_MODEL_POOL = ["local", "cheap", "mid", "premium"]

_ALWAYS_BLOCKED = [
    "production_deploy",
    "auto_push",
    "auto_merge",
    "send_external_message",
    "access_secrets",
    "destructive_data_op",
]


def _make_manager(
    manager_id: str,
    name: str,
    department: str,
    responsibility: str,
    skill_domains: List[str],
    worker_pool: List[str],
    allowed_action_types: List[str],
    model_pool: Optional[List[str]] = None,
    risk_ceiling: str = RISK_MEDIUM,
    status: str = STATUS_ACTIVE,
    extra_blocked: Optional[List[str]] = None,
) -> ManagerContract:
    blocked = list(_ALWAYS_BLOCKED) + (extra_blocked or [])
    return ManagerContract(
        manager_id=manager_id,
        name=name,
        department=department,
        responsibility=responsibility,
        input_contract={
            "format": "TaskRoutingRequest",
            "required_fields": ["intent", "risk_level", "complexity_level", "domains_required"],
        },
        output_contract={
            "format": "ActivationPlan_partial",
            "required_fields": ["selected_workers", "activation_reasons", "skip_reasons"],
            "no_raw_chain_of_thought": True,
        },
        skill_domains=skill_domains,
        worker_pool=worker_pool,
        allowed_action_types=allowed_action_types,
        blocked_action_types=blocked,
        model_pool=model_pool or _MID_MODEL_POOL,
        risk_ceiling=risk_ceiling,
        tool_policy=dict(_STD_TOOL_POLICY),
        validation_policy=dict(_STD_VALIDATION_POLICY),
        escalation_policy=dict(_STD_ESCALATION_POLICY),
        telemetry_policy=dict(_STD_TELEMETRY_POLICY),
        nus_learning_hooks=dict(_STD_NUS_HOOKS),
        status=status,
    )


# ---------------------------------------------------------------------------
# Initial manager definitions
# ---------------------------------------------------------------------------

_INITIAL_MANAGERS: List[ManagerContract] = [

    _make_manager(
        manager_id="coding_manager",
        name="Coding Manager",
        department="Engineering",
        responsibility=(
            "Orchestrates all code implementation tasks: backend, frontend, "
            "refactoring, integration, dependency management, git commits."
        ),
        skill_domains=["backend", "frontend", "refactoring", "integration", "git", "dependencies"],
        worker_pool=[
            "backend_worker", "frontend_worker", "refactor_worker",
            "integration_worker", "dependency_worker", "git_commit_worker",
            "performance_worker",
        ],
        allowed_action_types=["local_read", "local_analysis", "file_edit_dry_run", "git_status"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_manager(
        manager_id="architecture_manager",
        name="Architecture Manager",
        department="Engineering",
        responsibility=(
            "Oversees system design, contracts, integration architecture, "
            "and scalability decisions. Routes to architecture workers."
        ),
        skill_domains=["system_design", "contracts", "integration_architecture", "scalability"],
        worker_pool=[
            "system_architecture_worker", "contract_design_worker",
            "integration_architecture_worker", "scalability_worker",
        ],
        allowed_action_types=["local_read", "local_analysis", "design_dry_run"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    _make_manager(
        manager_id="testing_validation_manager",
        name="Testing & Validation Manager",
        department="Quality",
        responsibility=(
            "Manages all test execution, regression testing, acceptance evidence, "
            "and doctor readiness checks."
        ),
        skill_domains=["unit_testing", "integration_testing", "regression", "acceptance", "doctor"],
        worker_pool=[
            "unit_test_worker", "integration_test_worker", "regression_test_worker",
            "doctor_check_worker", "acceptance_evidence_worker",
        ],
        allowed_action_types=["local_read", "local_analysis", "test_dry_run", "doctor_check"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_manager(
        manager_id="code_review_manager",
        name="Code Review Manager",
        department="Quality",
        responsibility=(
            "Coordinates structured code review, diff analysis, and "
            "approval gate decisions before any commit or merge."
        ),
        skill_domains=["code_review", "diff_analysis", "approval_gates"],
        worker_pool=["security_code_worker", "refactor_worker"],
        allowed_action_types=["local_read", "local_analysis", "diff_review_dry_run"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
    ),

    _make_manager(
        manager_id="debugging_manager",
        name="Debugging Manager",
        department="Engineering",
        responsibility=(
            "Routes debugging tasks: root cause analysis, failure triage, "
            "error pattern recognition, and repair loop coordination."
        ),
        skill_domains=["debugging", "error_analysis", "root_cause", "repair_loop"],
        worker_pool=["debug_worker"],
        allowed_action_types=["local_read", "local_analysis", "log_analysis"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_manager(
        manager_id="research_manager",
        name="Research Manager",
        department="Intelligence",
        responsibility=(
            "Coordinates local knowledge research, codebase exploration, "
            "and bounded web research tasks."
        ),
        skill_domains=["local_research", "codebase_search", "knowledge_retrieval"],
        worker_pool=["local_research_worker"],
        allowed_action_types=["local_read", "local_analysis", "search"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_manager(
        manager_id="memory_knowledge_manager",
        name="Memory & Knowledge Manager",
        department="Intelligence",
        responsibility=(
            "Manages knowledge ingestion, memory store operations, "
            "and knowledge retrieval for context building."
        ),
        skill_domains=["memory", "knowledge_store", "context_retrieval"],
        worker_pool=["local_research_worker"],
        allowed_action_types=["local_read", "local_analysis", "memory_read"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_manager(
        manager_id="documentation_manager",
        name="Documentation Manager",
        department="Engineering",
        responsibility=(
            "Manages documentation creation, updates, and consistency checks. "
            "Never creates duplicate docs."
        ),
        skill_domains=["documentation", "changelog", "readme", "architecture_docs"],
        worker_pool=["documentation_worker"],
        allowed_action_types=["local_read", "local_analysis", "doc_dry_run"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_manager(
        manager_id="product_ux_manager",
        name="Product & UX Manager",
        department="Product",
        responsibility=(
            "Coordinates product requirements analysis, UX review, "
            "and feature scoping decisions."
        ),
        skill_domains=["product", "ux", "requirements", "feature_scoping"],
        worker_pool=["frontend_worker", "documentation_worker"],
        allowed_action_types=["local_read", "local_analysis", "ux_review_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_manager(
        manager_id="operations_automation_manager",
        name="Operations & Automation Manager",
        department="Operations",
        responsibility=(
            "Manages runtime operations, automation scheduling, "
            "and operational health monitoring."
        ),
        skill_domains=["runtime_ops", "automation", "scheduling", "health_monitoring"],
        worker_pool=["runtime_ops_worker"],
        allowed_action_types=["local_read", "local_analysis", "ops_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_manager(
        manager_id="governance_safety_manager",
        name="Governance & Safety Manager",
        department="Governance",
        responsibility=(
            "Enforces safety gates, policy compliance, risk classification, "
            "and approval scope decisions. Blocks dangerous actions."
        ),
        skill_domains=["governance", "safety", "policy_enforcement", "risk_classification"],
        worker_pool=[
            "secret_safety_worker", "policy_gate_worker",
            "risk_classification_worker", "approval_scope_worker",
        ],
        allowed_action_types=["local_read", "policy_check", "risk_assessment"],
        model_pool=_PREM_MODEL_POOL,
        risk_ceiling=RISK_BLOCKED,
        extra_blocked=["bypass_governance", "bypass_safety_gate"],
    ),

    _make_manager(
        manager_id="release_packaging_manager",
        name="Release & Packaging Manager",
        department="Releases",
        responsibility=(
            "Coordinates release preparation, changelog, version bump, "
            "and packaging readiness. Does NOT trigger actual deploys."
        ),
        skill_domains=["release", "packaging", "versioning", "changelog"],
        worker_pool=["release_packaging_worker"],
        allowed_action_types=["local_read", "local_analysis", "release_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
        extra_blocked=["trigger_deploy", "trigger_auto_push"],
        status=STATUS_INACTIVE,
    ),

    _make_manager(
        manager_id="data_manager",
        name="Data Manager",
        department="Data",
        responsibility=(
            "Manages data analysis tasks, schema review, "
            "and data-safe query coordination."
        ),
        skill_domains=["data_analysis", "schema_review", "query_analysis"],
        worker_pool=["cost_analysis_worker"],
        allowed_action_types=["local_read", "local_analysis", "data_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),

    _make_manager(
        manager_id="cost_routing_manager",
        name="Cost & Routing Manager",
        department="Operations",
        responsibility=(
            "Optimises model/provider selection, tracks token costs, "
            "enforces budget caps, and surfaces provider sufficiency gaps."
        ),
        skill_domains=["cost_analysis", "model_routing", "budget_enforcement", "provider_gaps"],
        worker_pool=["cost_analysis_worker"],
        allowed_action_types=["local_read", "local_analysis", "routing_dry_run"],
        model_pool=_LOW_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_manager(
        manager_id="nus_learning_manager",
        name="NUS Learning Manager",
        department="Intelligence",
        responsibility=(
            "Coordinates NUS learning cycle: telemetry ingestion, scorecard "
            "generation, failure pattern analysis, and recommendation workflow."
        ),
        skill_domains=["nus_learning", "telemetry", "scorecard", "failure_patterns"],
        worker_pool=["nus_learning_worker"],
        allowed_action_types=["local_read", "local_analysis", "nus_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_LOW,
    ),

    _make_manager(
        manager_id="connector_auth_manager",
        name="Connector & Auth Manager",
        department="Connectors",
        responsibility=(
            "Manages connector readiness, auth configuration review, "
            "and integration health. Does NOT access live secrets."
        ),
        skill_domains=["connectors", "auth_review", "integration_health"],
        worker_pool=[],
        allowed_action_types=["local_read", "local_analysis", "connector_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_HIGH,
        extra_blocked=["access_live_secrets", "rotate_credentials"],
        status=STATUS_INACTIVE,
    ),

    _make_manager(
        manager_id="runtime_ops_manager",
        name="Runtime Ops Manager",
        department="Operations",
        responsibility=(
            "Handles runtime lifecycle, process monitoring, crash analysis, "
            "and operational recovery planning."
        ),
        skill_domains=["runtime_lifecycle", "process_monitoring", "crash_analysis"],
        worker_pool=["runtime_ops_worker"],
        allowed_action_types=["local_read", "local_analysis", "runtime_dry_run"],
        model_pool=_MID_MODEL_POOL,
        risk_ceiling=RISK_MEDIUM,
    ),
]


# ---------------------------------------------------------------------------
# ManagerRegistry
# ---------------------------------------------------------------------------

class ManagerRegistry:
    """Registry of domain managers.

    Enforces uniqueness, provides lookup by ID/domain, and validates
    all manager contracts on load.

    Future managers can be added via register() without code changes
    to activation logic (metadata-driven design).
    """

    def __init__(self) -> None:
        self._managers: Dict[str, ManagerContract] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for m in _INITIAL_MANAGERS:
            self._register_unchecked(m)

    def _register_unchecked(self, manager: ManagerContract) -> None:
        if manager.manager_id in self._managers:
            raise ValueError(
                f"Duplicate manager_id '{manager.manager_id}' — "
                "each manager must have a unique ID."
            )
        errors = manager.validate()
        if errors:
            raise ValueError(
                f"Manager '{manager.manager_id}' has contract errors: {errors}"
            )
        self._managers[manager.manager_id] = manager

    def register(self, manager: ManagerContract) -> None:
        """Register a new manager. Raises ValueError on duplicate or invalid contract."""
        self._register_unchecked(manager)

    def get(self, manager_id: str) -> Optional[ManagerContract]:
        return self._managers.get(manager_id)

    def list_all(self) -> List[ManagerContract]:
        return list(self._managers.values())

    def list_active(self) -> List[ManagerContract]:
        return [m for m in self._managers.values() if m.status == STATUS_ACTIVE]

    def list_by_domain(self, domain: str) -> List[ManagerContract]:
        return [
            m for m in self._managers.values()
            if domain in m.skill_domains
        ]

    def ids(self) -> List[str]:
        return list(self._managers.keys())

    def count(self) -> int:
        return len(self._managers)

    def has_duplicate_ids(self) -> bool:
        return False  # invariant: _register_unchecked raises on duplicate

    def validate_all(self) -> Dict[str, List[str]]:
        """Return dict of manager_id → [errors]. Empty list = valid."""
        return {mid: m.validate() for mid, m in self._managers.items()}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count(),
            "manager_ids": self.ids(),
            "managers": [m.to_dict() for m in self.list_all()],
        }


# Module-level singleton
_registry: Optional[ManagerRegistry] = None


def get_manager_registry() -> ManagerRegistry:
    global _registry
    if _registry is None:
        _registry = ManagerRegistry()
    return _registry


__all__ = [
    "ManagerRegistry",
    "get_manager_registry",
]
