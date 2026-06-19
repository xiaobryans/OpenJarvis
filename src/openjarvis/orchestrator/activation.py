"""Post-NUS Hierarchical Orchestrator — Dynamic Activation Planner.

Takes a TaskRoutingRequest and produces an ActivationPlan that selects the
minimum sufficient team of managers and workers without fixed formulas.

Activation policy (non-negotiable):
  - No fixed formulas like "simple task = 1 manager + 1 worker."
  - Activate as many managers/workers as justified.
  - Prefer minimum sufficient team.
  - Expand only based on evidence.
  - Every activation must have rationale.
  - Every skipped relevant role must have rationale.
  - Duplicate/similar workers must not both activate unless justified.
  - Cheap models cannot approve critical/high-risk actions.

Activation factors (all evaluated per request):
  - intent
  - risk level
  - complexity level
  - domains required
  - required skills
  - required tools
  - validation needs
  - cost budget
  - context budget
  - latency requirement
  - NUS scorecards (if available)
  - autonomy profile
  - governance policy

Model routing integration:
  - Integrates with existing ModelRouter (workbench/model_router.py).
  - Routes by task metadata, not hardcoded agent names.
  - Discloses model/provider gaps when tiers are insufficient.
  - Critical/safety actions require premium tier + governance.

NUS integration:
  - Emits structured decision records via NUS 1F decision_record.py.
  - No raw chain-of-thought stored.
  - All activation decisions tagged with NUS learning tags.
  - Hierarchy levels: jarvis_pa → cos_gm → manager → worker → validator → governance.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from openjarvis.orchestrator.contracts import (
    ActivationPlan,
    ManagerContract,
    ModelProviderSufficiencyGap,
    TaskRoutingRequest,
    WorkerContract,
    COMPLEXITY_COMPLEX,
    COMPLEXITY_MODERATE,
    COMPLEXITY_SIMPLE,
    RISK_BLOCKED,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    STATUS_ACTIVE,
    LATENCY_FAST,
)
from openjarvis.orchestrator.manager_registry import ManagerRegistry, get_manager_registry
from openjarvis.orchestrator.worker_registry import WorkerRegistry, get_worker_registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model tier routing constants (mirrors workbench/model_router.py)
# ---------------------------------------------------------------------------

MODEL_TIER_LOCAL = "local"
MODEL_TIER_CHEAP = "cheap"
MODEL_TIER_MID = "mid"
MODEL_TIER_PREMIUM = "premium"

_CRITICAL_RISK_REQUIRES_PREMIUM = frozenset({RISK_HIGH, RISK_BLOCKED})

# ---------------------------------------------------------------------------
# Domain → manager ID mapping (metadata-driven, not hardcoded per task)
# ---------------------------------------------------------------------------

_DOMAIN_TO_MANAGER: Dict[str, str] = {
    "backend": "coding_manager",
    "frontend": "coding_manager",
    "api_routes": "coding_manager",
    "refactoring": "coding_manager",
    "integration": "coding_manager",
    "git": "coding_manager",
    "dependencies": "coding_manager",
    "system_design": "architecture_manager",
    "contracts": "architecture_manager",
    "integration_architecture": "architecture_manager",
    "scalability": "architecture_manager",
    "unit_testing": "testing_validation_manager",
    "integration_testing": "testing_validation_manager",
    "regression": "testing_validation_manager",
    "acceptance": "testing_validation_manager",
    "doctor": "testing_validation_manager",
    "code_review": "code_review_manager",
    "diff_analysis": "code_review_manager",
    "debugging": "debugging_manager",
    "root_cause": "debugging_manager",
    "local_research": "research_manager",
    "codebase_search": "research_manager",
    "memory": "memory_knowledge_manager",
    "knowledge_store": "memory_knowledge_manager",
    "documentation": "documentation_manager",
    "changelog": "documentation_manager",
    "product": "product_ux_manager",
    "ux": "product_ux_manager",
    "runtime_ops": "operations_automation_manager",
    "automation": "operations_automation_manager",
    "governance": "governance_safety_manager",
    "safety": "governance_safety_manager",
    "policy_enforcement": "governance_safety_manager",
    "release": "release_packaging_manager",
    "packaging": "release_packaging_manager",
    "data_analysis": "data_manager",
    "schema_review": "data_manager",
    "cost_analysis": "cost_routing_manager",
    "model_routing": "cost_routing_manager",
    "nus_learning": "nus_learning_manager",
    "telemetry": "nus_learning_manager",
    "connectors": "connector_auth_manager",
    "auth_review": "connector_auth_manager",
    "runtime_lifecycle": "runtime_ops_manager",
}

# Skill → worker ID mapping
_SKILL_TO_WORKER: Dict[str, str] = {
    "python": "backend_worker",
    "api_routes": "backend_worker",
    "fastapi": "backend_worker",
    "backend_logic": "backend_worker",
    "typescript": "frontend_worker",
    "react": "frontend_worker",
    "nextjs": "frontend_worker",
    "css": "frontend_worker",
    "pytest": "test_worker",
    "unit_testing": "unit_test_worker",
    "test_fixtures": "test_worker",
    "debugging": "debug_worker",
    "root_cause_analysis": "debug_worker",
    "refactoring": "refactor_worker",
    "integration": "integration_worker",
    "api_clients": "integration_worker",
    "security_review": "security_code_worker",
    "secret_scan": "secret_safety_worker",
    "performance": "performance_worker",
    "dependency_management": "dependency_worker",
    "git": "git_commit_worker",
    "commit_preparation": "git_commit_worker",
    "system_design": "system_architecture_worker",
    "contract_design": "contract_design_worker",
    "integration_architecture": "integration_architecture_worker",
    "scalability": "scalability_worker",
    "integration_testing": "integration_test_worker",
    "regression_testing": "regression_test_worker",
    "doctor_checks": "doctor_check_worker",
    "acceptance_evidence": "acceptance_evidence_worker",
    "policy_evaluation": "policy_gate_worker",
    "risk_classification": "risk_classification_worker",
    "approval_scoping": "approval_scope_worker",
    "local_search": "local_research_worker",
    "codebase_exploration": "local_research_worker",
    "documentation": "documentation_worker",
    "technical_writing": "documentation_worker",
    "release_preparation": "release_packaging_worker",
    "versioning": "release_packaging_worker",
    "runtime_monitoring": "runtime_ops_worker",
    "cost_analysis": "cost_analysis_worker",
    "token_estimation": "cost_analysis_worker",
    "nus_telemetry": "nus_learning_worker",
    "scorecard_generation": "nus_learning_worker",
}


# ---------------------------------------------------------------------------
# DynamicActivationPlanner
# ---------------------------------------------------------------------------

class DynamicActivationPlanner:
    """Dynamic activation planner for the company agent hierarchy.

    Selects the minimum sufficient team of managers/workers justified by the
    task routing request. Never uses fixed formulas.

    Usage:
        planner = DynamicActivationPlanner()
        plan = planner.plan(request)
    """

    def __init__(
        self,
        manager_registry: Optional[ManagerRegistry] = None,
        worker_registry: Optional[WorkerRegistry] = None,
    ) -> None:
        self._managers = manager_registry or get_manager_registry()
        self._workers = worker_registry or get_worker_registry()
        self._nus_feedback: Optional[Dict[str, Any]] = None  # loaded lazily

    def _load_nus_feedback(self) -> Dict[str, Any]:
        """Load available NUS scorecard/failure data to inform activation.

        Reads from LearningStore (failure patterns, outcomes) and LearnedRouter
        (routing recommendations). Returns empty dict if unavailable — graceful
        degradation, not a hard failure.
        """
        feedback: Dict[str, Any] = {
            "failure_patterns": [],
            "recent_outcomes": [],
            "routing_recommendations": [],
            "loaded": False,
        }
        try:
            from openjarvis.nus.learning_store import LearningStore
            store = LearningStore()
            patterns = store.load_recent_patterns(limit=20)
            outcomes = store.load_recent_outcomes(limit=20)
            feedback["failure_patterns"] = patterns
            feedback["recent_outcomes"] = outcomes
            feedback["loaded"] = True
        except Exception as exc:
            logger.debug("NUS LearningStore not available for activation: %s", exc)

        try:
            from openjarvis.nus.learned_routing import get_learned_router
            router = get_learned_router()
            recs = router.get_recommendations()
            feedback["routing_recommendations"] = [r.to_dict() for r in recs[-10:]]
        except Exception as exc:
            logger.debug("NUS LearnedRouter not available for activation: %s", exc)

        return feedback

    def _apply_nus_feedback(
        self,
        feedback: Dict[str, Any],
        request: TaskRoutingRequest,
        activation_reasons: Dict[str, str],
        skip_reasons: Dict[str, str],
        selected_managers: List[str],
        selected_workers: List[str],
        skipped_managers: List[str],
        skipped_workers: List[str],
    ) -> List[str]:
        """Apply NUS failure/scorecard data to augment activation decisions.

        Returns additional NUS-sourced tags.
        """
        extra_tags: List[str] = []

        if not feedback.get("loaded"):
            extra_tags.append("nus_feedback:not_available")
            return extra_tags

        extra_tags.append("nus_feedback:loaded")

        # Count recent failures for context
        patterns = feedback.get("failure_patterns", [])
        outcomes = feedback.get("recent_outcomes", [])
        failure_count = sum(
            1 for o in outcomes if o.get("success") is False or o.get("status") == "failed"
        )
        if failure_count > 0:
            extra_tags.append(f"nus_prior_failures:{failure_count}")
            # Escalate validation requirement if prior failures exist
            if failure_count >= 3 and "testing_validation_manager" not in selected_managers:
                mgr = self._managers.get("testing_validation_manager")
                if mgr and mgr.status == STATUS_ACTIVE:
                    selected_managers.append("testing_validation_manager")
                    if "testing_validation_manager" in skipped_managers:
                        skipped_managers.remove("testing_validation_manager")
                        skip_reasons.pop("testing_validation_manager", None)
                    activation_reasons["testing_validation_manager"] = (
                        f"NUS feedback: {failure_count} recent failures → validation escalated"
                    )
                    extra_tags.append("nus_escalated:testing_validation_manager")

        # Tag pattern types
        for p in patterns[:5]:
            ptype = p.get("pattern_type", "unknown")
            if ptype:
                extra_tags.append(f"nus_pattern:{ptype}")

        return extra_tags

    def plan(self, request: TaskRoutingRequest) -> ActivationPlan:
        """Produce an ActivationPlan for the given TaskRoutingRequest.

        All activation/skip decisions include structured rationale.
        No raw chain-of-thought stored.
        """
        selected_managers: List[str] = []
        selected_workers: List[str] = []
        skipped_managers: List[str] = []
        skipped_workers: List[str] = []
        activation_reasons: Dict[str, str] = {}
        skip_reasons: Dict[str, str] = {}
        model_provider_gaps: List[ModelProviderSufficiencyGap] = []

        all_manager_ids = self._managers.ids()
        all_worker_ids = self._workers.ids()

        # 1. Determine candidate managers based on domains + risk/complexity
        candidate_manager_ids = self._select_candidate_managers(request)

        for mid in all_manager_ids:
            manager = self._managers.get(mid)
            if manager is None:
                continue
            if mid in candidate_manager_ids:
                reason = candidate_manager_ids[mid]
                # Don't activate inactive managers unless explicitly needed
                if manager.status != STATUS_ACTIVE:
                    skipped_managers.append(mid)
                    skip_reasons[mid] = f"manager status={manager.status} (not active); {reason}"
                    continue
                selected_managers.append(mid)
                activation_reasons[mid] = reason
            else:
                skipped_managers.append(mid)
                skip_reasons[mid] = self._build_skip_reason_manager(manager, request)

        # 2. Determine candidate workers based on skills + tools + selected managers
        candidate_worker_ids = self._select_candidate_workers(request, selected_managers)

        for wid in all_worker_ids:
            worker = self._workers.get(wid)
            if worker is None:
                continue
            if wid in candidate_worker_ids:
                reason = candidate_worker_ids[wid]
                if worker.status != STATUS_ACTIVE:
                    skipped_workers.append(wid)
                    skip_reasons[wid] = f"worker status={worker.status} (not active); {reason}"
                    continue
                # Dedup: skip if a nearly identical worker already selected for same skill
                if self._is_redundant_worker(wid, worker, selected_workers):
                    skipped_workers.append(wid)
                    skip_reasons[wid] = (
                        f"redundant: overlapping skills already covered by selected worker; {reason}"
                    )
                    continue
                selected_workers.append(wid)
                activation_reasons[wid] = reason
            else:
                skipped_workers.append(wid)
                skip_reasons[wid] = self._build_skip_reason_worker(worker, request, selected_managers)

        # 3. Always include governance_safety_manager for high/blocked risk
        if request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM:
            if "governance_safety_manager" not in selected_managers:
                gm = self._managers.get("governance_safety_manager")
                if gm and gm.status == STATUS_ACTIVE:
                    selected_managers.append("governance_safety_manager")
                    if "governance_safety_manager" in skipped_managers:
                        skipped_managers.remove("governance_safety_manager")
                        del skip_reasons["governance_safety_manager"]
                    activation_reasons["governance_safety_manager"] = (
                        f"risk_level={request.risk_level} requires governance gate"
                    )

        # 4. Always include cost_routing_manager for complex/high-cost scenarios
        if (
            request.cost_budget > 0.50
            or request.complexity_level == COMPLEXITY_COMPLEX
        ):
            if "cost_routing_manager" not in selected_managers:
                crm = self._managers.get("cost_routing_manager")
                if crm and crm.status == STATUS_ACTIVE:
                    selected_managers.append("cost_routing_manager")
                    if "cost_routing_manager" in skipped_managers:
                        skipped_managers.remove("cost_routing_manager")
                        del skip_reasons["cost_routing_manager"]
                    activation_reasons["cost_routing_manager"] = (
                        f"cost_budget=${request.cost_budget:.2f} or complexity={request.complexity_level}"
                        " — cost routing analysis justified"
                    )

        # 5. Build model routing plan
        model_routing_plan = self._build_model_routing_plan(
            request, selected_managers, selected_workers, model_provider_gaps
        )

        # 6. Build validation and governance plans
        validation_plan = self._build_validation_plan(request, selected_workers)
        governance_plan = self._build_governance_plan(request, selected_managers)

        # 7. Build risk assessment
        risk_assessment = {
            "risk_level": request.risk_level,
            "complexity_level": request.complexity_level,
            "validation_required": request.validation_required,
            "governance_required": request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM,
            "premium_model_required": request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM,
            "autonomy_profile": request.autonomy_profile,
        }

        # 8. Build stop conditions
        stop_conditions = self._build_stop_conditions(request)

        # 9. NUS learning tags + live scorecard feedback
        nus_feedback = self._load_nus_feedback()
        extra_nus_tags = self._apply_nus_feedback(
            nus_feedback, request,
            activation_reasons, skip_reasons,
            selected_managers, selected_workers,
            skipped_managers, skipped_workers,
        )
        nus_tags = self._build_nus_tags(request, selected_managers, selected_workers)
        nus_tags.extend(extra_nus_tags)

        # 10. Create structured decision record (NUS 1F)
        dr_id = self._create_decision_record(
            request, selected_managers, selected_workers, risk_assessment
        )

        # 11. Cost/context estimates
        cost_estimate = self._estimate_cost(request, selected_managers, selected_workers)
        context_estimate = self._estimate_context(request, selected_managers, selected_workers)

        # 12. Escalation plan
        escalation_plan = {
            "trigger": "validation_failure_or_blocker",
            "escalate_to": "cos_gm",
            "max_retries": 3,
            "stop_on_blocker": True,
            "require_bryan_approval_for": ["high_risk_action", "production_deploy", "external_send"],
        }

        return ActivationPlan.create(
            request_id=request.request_id,
            selected_managers=selected_managers,
            selected_workers=selected_workers,
            skipped_managers=skipped_managers,
            skipped_workers=skipped_workers,
            activation_reasons=activation_reasons,
            skip_reasons=skip_reasons,
            validation_plan=validation_plan,
            governance_plan=governance_plan,
            model_routing_plan=model_routing_plan,
            cost_estimate=cost_estimate,
            context_estimate=context_estimate,
            risk_assessment=risk_assessment,
            escalation_plan=escalation_plan,
            stop_conditions=stop_conditions,
            structured_decision_record_id=dr_id,
            nus_learning_tags=nus_tags,
            model_provider_gaps=model_provider_gaps,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_candidate_managers(
        self, request: TaskRoutingRequest
    ) -> Dict[str, str]:
        """Return dict of manager_id → activation_reason for managers that should activate."""
        candidates: Dict[str, str] = {}

        # Map domains to managers
        for domain in request.domains_required:
            mid = _DOMAIN_TO_MANAGER.get(domain)
            if mid and mid not in candidates:
                candidates[mid] = f"domain={domain} required by request"

        # High/complex tasks need architecture review
        if request.complexity_level == COMPLEXITY_COMPLEX:
            if "architecture_manager" not in candidates:
                candidates["architecture_manager"] = (
                    f"complexity={request.complexity_level} justifies architecture oversight"
                )

        # Any validation → testing_validation_manager
        if request.validation_required:
            if "testing_validation_manager" not in candidates:
                candidates["testing_validation_manager"] = (
                    "validation_required=True"
                )

        # High/blocked risk → governance
        if request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM:
            if "governance_safety_manager" not in candidates:
                candidates["governance_safety_manager"] = (
                    f"risk_level={request.risk_level} requires governance gate"
                )

        # Explicit skills → relevant managers
        for skill in request.required_skills:
            wid = _SKILL_TO_WORKER.get(skill)
            if wid:
                w = self._workers.get(wid)
                if w and w.manager_id not in candidates:
                    candidates[w.manager_id] = (
                        f"skill={skill} requires worker={wid} under manager={w.manager_id}"
                    )

        return candidates

    def _select_candidate_workers(
        self,
        request: TaskRoutingRequest,
        selected_manager_ids: List[str],
    ) -> Dict[str, str]:
        """Return dict of worker_id → activation_reason for workers that should activate."""
        candidates: Dict[str, str] = {}

        # Map required skills to workers
        for skill in request.required_skills:
            wid = _SKILL_TO_WORKER.get(skill)
            if wid and wid not in candidates:
                w = self._workers.get(wid)
                if w and w.manager_id in selected_manager_ids:
                    candidates[wid] = f"skill={skill} required; manager={w.manager_id} selected"

        # Map required tools to workers that allow them
        for tool in request.required_tools:
            for worker in self._workers.list_all():
                if (
                    tool in worker.allowed_tools
                    and worker.manager_id in selected_manager_ids
                    and worker.worker_id not in candidates
                ):
                    candidates[worker.worker_id] = (
                        f"tool={tool} allowed by worker; manager={worker.manager_id} selected"
                    )

        # Validation: add doctor_check_worker if testing_validation_manager selected
        if (
            request.validation_required
            and "testing_validation_manager" in selected_manager_ids
            and "doctor_check_worker" not in candidates
        ):
            candidates["doctor_check_worker"] = (
                "validation_required=True + testing_validation_manager selected"
            )

        # Governance: add policy_gate_worker for high risk
        if (
            request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM
            and "governance_safety_manager" in selected_manager_ids
            and "policy_gate_worker" not in candidates
        ):
            candidates["policy_gate_worker"] = (
                f"risk_level={request.risk_level} + governance_safety_manager selected"
            )

        return candidates

    def _is_redundant_worker(
        self,
        wid: str,
        worker: WorkerContract,
        already_selected: List[str],
    ) -> bool:
        """Return True if this worker's skills are already covered by a selected worker."""
        for selected_id in already_selected:
            selected = self._workers.get(selected_id)
            if selected is None:
                continue
            overlap = set(worker.skills) & set(selected.skills)
            # Redundant if >50% skill overlap with same manager
            if (
                overlap
                and len(overlap) / max(len(worker.skills), 1) > 0.5
                and worker.manager_id == selected.manager_id
            ):
                return True
        return False

    def _build_skip_reason_manager(
        self, manager: ManagerContract, request: TaskRoutingRequest
    ) -> str:
        domains_overlap = set(manager.skill_domains) & set(request.domains_required)
        if not domains_overlap:
            return (
                f"no domain overlap: manager domains={manager.skill_domains}, "
                f"request domains={request.domains_required}"
            )
        return (
            f"domains overlap={list(domains_overlap)} but not selected "
            f"(another manager covers this; minimum sufficient team)"
        )

    def _build_skip_reason_worker(
        self,
        worker: WorkerContract,
        request: TaskRoutingRequest,
        selected_manager_ids: List[str],
    ) -> str:
        if worker.manager_id not in selected_manager_ids:
            return (
                f"manager={worker.manager_id} not selected "
                f"(worker only activates under selected managers)"
            )
        skills_overlap = set(worker.skills) & set(request.required_skills)
        if not skills_overlap:
            return (
                f"no skill overlap: worker skills={worker.skills[:3]}, "
                f"required={request.required_skills}"
            )
        return "not required for this task (minimum sufficient team)"

    def _build_model_routing_plan(
        self,
        request: TaskRoutingRequest,
        selected_managers: List[str],
        selected_workers: List[str],
        gaps: List[ModelProviderSufficiencyGap],
    ) -> Dict[str, Any]:
        """Build model routing recommendations. Discloses gaps."""
        tier = MODEL_TIER_MID
        reason = f"complexity={request.complexity_level}, risk={request.risk_level}"

        if request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM:
            tier = MODEL_TIER_PREMIUM
            reason = f"risk={request.risk_level} requires premium tier for safety"
        elif request.complexity_level == COMPLEXITY_SIMPLE and request.risk_level == RISK_LOW:
            tier = MODEL_TIER_CHEAP
            reason = "simple+low-risk task qualifies for cheap tier"
        elif request.latency_requirement == LATENCY_FAST:
            tier = MODEL_TIER_CHEAP
            reason = "fast latency requirement prefers cheap tier"

        # Cheap model cannot approve critical actions
        critical_approval_check = {
            "cheap_model_blocked_for_approval": True,
            "critical_action_requires": MODEL_TIER_PREMIUM,
            "rule": "cheap models cannot approve critical/high-risk actions",
        }

        # Model/provider sufficiency check
        # In this sprint: dry-run/read-only framework — existing ModelRouter tiers sufficient
        # Future: real autonomous execution may need dedicated provider keys
        provider_sufficiency = {
            "available_tiers": [MODEL_TIER_LOCAL, MODEL_TIER_CHEAP, MODEL_TIER_MID, MODEL_TIER_PREMIUM],
            "sufficient_for_sprint": True,
            "sprint_scope": "dry_run_read_only_framework",
            "future_gap": (
                "Real autonomous worker execution will require verified provider keys "
                "and production model access — not needed for this sprint."
            ),
        }

        return {
            "recommended_tier": tier,
            "tier_reason": reason,
            "critical_approval_check": critical_approval_check,
            "provider_sufficiency": provider_sufficiency,
            "routing_policy": "metadata_driven_not_hardcoded",
            "per_worker_routing": {
                wid: self._worker_model_tier(wid, request) for wid in selected_workers
            },
        }

    def _worker_model_tier(self, worker_id: str, request: TaskRoutingRequest) -> str:
        worker = self._workers.get(worker_id)
        if worker is None:
            return MODEL_TIER_MID
        if request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM:
            if MODEL_TIER_PREMIUM in worker.model_pool:
                return MODEL_TIER_PREMIUM
        if MODEL_TIER_MID in worker.model_pool:
            return MODEL_TIER_MID
        if MODEL_TIER_CHEAP in worker.model_pool:
            return MODEL_TIER_CHEAP
        return MODEL_TIER_LOCAL

    def _build_validation_plan(
        self, request: TaskRoutingRequest, selected_workers: List[str]
    ) -> Dict[str, Any]:
        return {
            "validation_required": request.validation_required,
            "validators": (
                ["doctor_check_worker", "acceptance_evidence_worker"]
                if request.validation_required else []
            ),
            "require_structured_output": True,
            "no_raw_chain_of_thought": True,
            "require_decision_record": True,
        }

    def _build_governance_plan(
        self, request: TaskRoutingRequest, selected_managers: List[str]
    ) -> Dict[str, Any]:
        return {
            "governance_required": request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM,
            "governance_manager": (
                "governance_safety_manager"
                if "governance_safety_manager" in selected_managers else None
            ),
            "hard_gates_active": True,
            "blocked_actions": [
                "production_deploy", "auto_push", "auto_merge",
                "send_external_message", "access_secrets",
            ],
            "approval_required_for": ["high_risk_action", "production_deploy"],
            "us13_voice_parked": True,
        }

    def _build_stop_conditions(self, request: TaskRoutingRequest) -> List[str]:
        conditions = [
            "validation_failure_after_max_retries",
            "governance_gate_blocked",
            "budget_exceeded",
            "context_budget_exceeded",
        ]
        if request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM:
            conditions.append("high_risk_action_without_approval")
        return conditions

    def _build_nus_tags(
        self,
        request: TaskRoutingRequest,
        selected_managers: List[str],
        selected_workers: List[str],
    ) -> List[str]:
        tags = [
            f"intent:{request.intent}",
            f"risk:{request.risk_level}",
            f"complexity:{request.complexity_level}",
            f"autonomy_profile:{request.autonomy_profile}",
            f"managers_selected:{len(selected_managers)}",
            f"workers_selected:{len(selected_workers)}",
            "orchestrator:hierarchical",
            "sprint:post_nus_hierarchical_orchestrator",
        ]
        for domain in request.domains_required:
            tags.append(f"domain:{domain}")
        return tags

    def _create_decision_record(
        self,
        request: TaskRoutingRequest,
        selected_managers: List[str],
        selected_workers: List[str],
        risk_assessment: Dict[str, Any],
    ) -> str:
        """Create a NUS 1F structured decision record. Returns record_id."""
        try:
            from openjarvis.nus.decision_record import build_action_decision_record, LEVEL_COS_GM

            record = build_action_decision_record(
                action_type="orchestration_activation_plan",
                decision="dry_run",
                reason="orchestrator_activation_plan_created",
                evidence={
                    "request_id": request.request_id,
                    "risk_assessment": risk_assessment,
                    "domains_required": request.domains_required,
                    "required_skills": request.required_skills,
                },
                session_id=request.session_id or "orchestrator_dry_run",
                hierarchy_level=LEVEL_COS_GM,
                risk_level=request.risk_level,
                agent_metadata={
                    "selected_managers": selected_managers,
                    "selected_workers": selected_workers,
                },
                nus_learning_tags=[
                    f"intent:{request.intent}",
                    f"risk:{request.risk_level}",
                    "orchestration:activation_plan",
                ],
            )
            return record.get("record_id", f"dr_{uuid.uuid4().hex[:12]}")
        except Exception as exc:
            logger.warning("Could not create NUS decision record: %s", exc)
            return f"dr_{uuid.uuid4().hex[:12]}"

    def _estimate_cost(
        self,
        request: TaskRoutingRequest,
        selected_managers: List[str],
        selected_workers: List[str],
    ) -> float:
        """Conservative cost estimate based on tier and team size. Dry-run only."""
        base = 0.001 * len(selected_workers)
        if request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM:
            base *= 5.0
        elif request.complexity_level == COMPLEXITY_COMPLEX:
            base *= 3.0
        elif request.complexity_level == COMPLEXITY_MODERATE:
            base *= 1.5
        return min(base, request.cost_budget)

    def _estimate_context(
        self,
        request: TaskRoutingRequest,
        selected_managers: List[str],
        selected_workers: List[str],
    ) -> int:
        """Conservative context estimate. Dry-run only."""
        base = 500 * len(selected_workers)
        if request.complexity_level == COMPLEXITY_COMPLEX:
            base *= 3
        elif request.complexity_level == COMPLEXITY_MODERATE:
            base *= 2
        return min(base, request.context_budget)

    def get_status(self) -> Dict[str, Any]:
        """Return activation planner status summary."""
        feedback = self._load_nus_feedback()
        return {
            "activation_planner": "active",
            "manager_count": len(self._managers.ids()),
            "worker_count": len(self._workers.ids()),
            "nus_feedback_available": feedback.get("loaded", False),
            "nus_failure_patterns_loaded": len(feedback.get("failure_patterns", [])),
            "nus_recent_outcomes_loaded": len(feedback.get("recent_outcomes", [])),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_planner: Optional[DynamicActivationPlanner] = None


def get_activation_planner() -> DynamicActivationPlanner:
    global _planner
    if _planner is None:
        _planner = DynamicActivationPlanner()
    return _planner


__all__ = [
    "DynamicActivationPlanner",
    "get_activation_planner",
]
