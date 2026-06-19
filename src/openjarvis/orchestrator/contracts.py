"""Post-NUS Hierarchical Orchestrator — Core Contracts.

Defines the canonical contract types for all hierarchy layers:
  - ManagerContract  — domain manager definition
  - WorkerContract   — specialist worker definition
  - TaskRoutingRequest — input to the dynamic activation planner
  - ActivationPlan   — output of the dynamic activation planner
  - ModelProviderSufficiencyGap — model/provider gap disclosure

Design rules:
  - All fields use primitive types for JSON/dict serialisation.
  - No runtime state in contracts. Contracts are pure metadata.
  - Contracts are extensible via metadata dicts (future-proof).
  - No raw chain-of-thought. Only structured decision fields.
  - Duplicate IDs are a registry invariant violation (enforced in registries).
  - Registered contracts are not active by default.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_BLOCKED = "blocked"

COMPLEXITY_SIMPLE = "simple"
COMPLEXITY_MODERATE = "moderate"
COMPLEXITY_COMPLEX = "complex"

STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
STATUS_DEGRADED = "degraded"
STATUS_BLOCKED = "blocked"

LATENCY_FAST = "fast"
LATENCY_NORMAL = "normal"
LATENCY_RELAXED = "relaxed"

_VALID_RISK_LEVELS = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_BLOCKED})
_VALID_COMPLEXITY_LEVELS = frozenset({COMPLEXITY_SIMPLE, COMPLEXITY_MODERATE, COMPLEXITY_COMPLEX})
_VALID_STATUSES = frozenset({STATUS_ACTIVE, STATUS_INACTIVE, STATUS_DEGRADED, STATUS_BLOCKED})
_VALID_LATENCY = frozenset({LATENCY_FAST, LATENCY_NORMAL, LATENCY_RELAXED})

# Hierarchy levels — must match NUS 1F decision_record.py
LEVEL_JARVIS_PA = "jarvis_pa"
LEVEL_COS_GM = "cos_gm"
LEVEL_MANAGER = "manager"
LEVEL_WORKER = "worker"
LEVEL_VALIDATOR = "validator"
LEVEL_GOVERNANCE = "governance"


# ---------------------------------------------------------------------------
# ManagerContract
# ---------------------------------------------------------------------------

@dataclass
class ManagerContract:
    """Contract for a domain manager in the company agent hierarchy.

    All fields are required for registration. Missing critical fields
    default to most-restrictive interpretation.
    """
    manager_id: str
    name: str
    department: str
    responsibility: str
    input_contract: Dict[str, Any]
    output_contract: Dict[str, Any]
    skill_domains: List[str]
    worker_pool: List[str]
    allowed_action_types: List[str]
    blocked_action_types: List[str]
    model_pool: List[str]
    risk_ceiling: str
    tool_policy: Dict[str, Any]
    validation_policy: Dict[str, Any]
    escalation_policy: Dict[str, Any]
    telemetry_policy: Dict[str, Any]
    nus_learning_hooks: Dict[str, Any]
    status: str = STATUS_ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Return list of validation errors. Empty list = valid."""
        errors: List[str] = []
        if not self.manager_id:
            errors.append("manager_id is required")
        if not self.name:
            errors.append("name is required")
        if not self.department:
            errors.append("department is required")
        if not self.responsibility:
            errors.append("responsibility is required")
        if not isinstance(self.input_contract, dict):
            errors.append("input_contract must be a dict")
        if not isinstance(self.output_contract, dict):
            errors.append("output_contract must be a dict")
        if not isinstance(self.skill_domains, list):
            errors.append("skill_domains must be a list")
        if not isinstance(self.worker_pool, list):
            errors.append("worker_pool must be a list")
        if not isinstance(self.allowed_action_types, list):
            errors.append("allowed_action_types must be a list")
        if not isinstance(self.blocked_action_types, list):
            errors.append("blocked_action_types must be a list")
        if not isinstance(self.model_pool, list):
            errors.append("model_pool must be a list")
        if self.risk_ceiling not in _VALID_RISK_LEVELS:
            errors.append(f"risk_ceiling must be one of {sorted(_VALID_RISK_LEVELS)}")
        if not isinstance(self.tool_policy, dict):
            errors.append("tool_policy must be a dict")
        if not isinstance(self.validation_policy, dict):
            errors.append("validation_policy must be a dict")
        if not isinstance(self.escalation_policy, dict):
            errors.append("escalation_policy must be a dict")
        if not isinstance(self.telemetry_policy, dict):
            errors.append("telemetry_policy must be a dict")
        if not isinstance(self.nus_learning_hooks, dict):
            errors.append("nus_learning_hooks must be a dict")
        if self.status not in _VALID_STATUSES:
            errors.append(f"status must be one of {sorted(_VALID_STATUSES)}")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "name": self.name,
            "department": self.department,
            "responsibility": self.responsibility,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "skill_domains": self.skill_domains,
            "worker_pool": self.worker_pool,
            "allowed_action_types": self.allowed_action_types,
            "blocked_action_types": self.blocked_action_types,
            "model_pool": self.model_pool,
            "risk_ceiling": self.risk_ceiling,
            "tool_policy": self.tool_policy,
            "validation_policy": self.validation_policy,
            "escalation_policy": self.escalation_policy,
            "telemetry_policy": self.telemetry_policy,
            "nus_learning_hooks": self.nus_learning_hooks,
            "status": self.status,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# WorkerContract
# ---------------------------------------------------------------------------

@dataclass
class WorkerContract:
    """Contract for a specialist worker in the company agent hierarchy.

    Workers are activated only when justified by the dynamic activation planner.
    Registered workers are NOT active workers.
    """
    worker_id: str
    name: str
    manager_id: str
    department: str
    responsibility: str
    skills: List[str]
    input_contract: Dict[str, Any]
    output_contract: Dict[str, Any]
    allowed_tools: List[str]
    blocked_tools: List[str]
    allowed_action_types: List[str]
    blocked_action_types: List[str]
    model_pool: List[str]
    risk_ceiling: str
    validation_requirements: Dict[str, Any]
    escalation_path: Dict[str, Any]
    telemetry_policy: Dict[str, Any]
    nus_learning_hooks: Dict[str, Any]
    status: str = STATUS_ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Return list of validation errors. Empty list = valid."""
        errors: List[str] = []
        if not self.worker_id:
            errors.append("worker_id is required")
        if not self.name:
            errors.append("name is required")
        if not self.manager_id:
            errors.append("manager_id is required")
        if not self.department:
            errors.append("department is required")
        if not self.responsibility:
            errors.append("responsibility is required")
        if not isinstance(self.skills, list):
            errors.append("skills must be a list")
        if not isinstance(self.input_contract, dict):
            errors.append("input_contract must be a dict")
        if not isinstance(self.output_contract, dict):
            errors.append("output_contract must be a dict")
        if not isinstance(self.allowed_tools, list):
            errors.append("allowed_tools must be a list")
        if not isinstance(self.blocked_tools, list):
            errors.append("blocked_tools must be a list")
        if not isinstance(self.allowed_action_types, list):
            errors.append("allowed_action_types must be a list")
        if not isinstance(self.blocked_action_types, list):
            errors.append("blocked_action_types must be a list")
        if not isinstance(self.model_pool, list):
            errors.append("model_pool must be a list")
        if self.risk_ceiling not in _VALID_RISK_LEVELS:
            errors.append(f"risk_ceiling must be one of {sorted(_VALID_RISK_LEVELS)}")
        if not isinstance(self.validation_requirements, dict):
            errors.append("validation_requirements must be a dict")
        if not isinstance(self.escalation_path, dict):
            errors.append("escalation_path must be a dict")
        if not isinstance(self.telemetry_policy, dict):
            errors.append("telemetry_policy must be a dict")
        if not isinstance(self.nus_learning_hooks, dict):
            errors.append("nus_learning_hooks must be a dict")
        if self.status not in _VALID_STATUSES:
            errors.append(f"status must be one of {sorted(_VALID_STATUSES)}")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "manager_id": self.manager_id,
            "department": self.department,
            "responsibility": self.responsibility,
            "skills": self.skills,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "allowed_tools": self.allowed_tools,
            "blocked_tools": self.blocked_tools,
            "allowed_action_types": self.allowed_action_types,
            "blocked_action_types": self.blocked_action_types,
            "model_pool": self.model_pool,
            "risk_ceiling": self.risk_ceiling,
            "validation_requirements": self.validation_requirements,
            "escalation_path": self.escalation_path,
            "telemetry_policy": self.telemetry_policy,
            "nus_learning_hooks": self.nus_learning_hooks,
            "status": self.status,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# TaskRoutingRequest
# ---------------------------------------------------------------------------

@dataclass
class TaskRoutingRequest:
    """Input to the dynamic activation planner.

    Describes the task so the planner can select the minimum sufficient
    team of managers and workers without fixed formulas.
    """
    request_id: str
    user_request_summary: str
    intent: str
    risk_level: str
    complexity_level: str
    domains_required: List[str]
    required_skills: List[str]
    required_tools: List[str]
    validation_required: bool
    context_budget: int
    cost_budget: float
    latency_requirement: str
    autonomy_profile: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_request_summary: str,
        intent: str,
        risk_level: str = RISK_LOW,
        complexity_level: str = COMPLEXITY_SIMPLE,
        domains_required: Optional[List[str]] = None,
        required_skills: Optional[List[str]] = None,
        required_tools: Optional[List[str]] = None,
        validation_required: bool = True,
        context_budget: int = 8000,
        cost_budget: float = 0.10,
        latency_requirement: str = LATENCY_NORMAL,
        autonomy_profile: str = "safe_autopilot",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "TaskRoutingRequest":
        return cls(
            request_id=uuid.uuid4().hex,
            user_request_summary=user_request_summary,
            intent=intent,
            risk_level=risk_level,
            complexity_level=complexity_level,
            domains_required=domains_required or [],
            required_skills=required_skills or [],
            required_tools=required_tools or [],
            validation_required=validation_required,
            context_budget=context_budget,
            cost_budget=cost_budget,
            latency_requirement=latency_requirement,
            autonomy_profile=autonomy_profile,
            session_id=session_id,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_request_summary": self.user_request_summary,
            "intent": self.intent,
            "risk_level": self.risk_level,
            "complexity_level": self.complexity_level,
            "domains_required": self.domains_required,
            "required_skills": self.required_skills,
            "required_tools": self.required_tools,
            "validation_required": self.validation_required,
            "context_budget": self.context_budget,
            "cost_budget": self.cost_budget,
            "latency_requirement": self.latency_requirement,
            "autonomy_profile": self.autonomy_profile,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# ActivationPlan
# ---------------------------------------------------------------------------

@dataclass
class ActivationPlan:
    """Output of the dynamic activation planner.

    Records which managers/workers were selected, why each was selected
    or skipped, the model routing plan, governance/validation plan,
    and the structured decision record ID.

    No raw chain-of-thought. Only structured evidence fields.
    """
    plan_id: str
    request_id: str
    created_at: float
    selected_managers: List[str]
    selected_workers: List[str]
    skipped_managers: List[str]
    skipped_workers: List[str]
    activation_reasons: Dict[str, str]
    skip_reasons: Dict[str, str]
    validation_plan: Dict[str, Any]
    governance_plan: Dict[str, Any]
    model_routing_plan: Dict[str, Any]
    cost_estimate: float
    context_estimate: int
    risk_assessment: Dict[str, Any]
    escalation_plan: Dict[str, Any]
    stop_conditions: List[str]
    structured_decision_record_id: str
    nus_learning_tags: List[str]
    model_provider_gaps: List["ModelProviderSufficiencyGap"] = field(default_factory=list)
    no_raw_chain_of_thought: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        request_id: str,
        selected_managers: List[str],
        selected_workers: List[str],
        skipped_managers: List[str],
        skipped_workers: List[str],
        activation_reasons: Dict[str, str],
        skip_reasons: Dict[str, str],
        validation_plan: Optional[Dict[str, Any]] = None,
        governance_plan: Optional[Dict[str, Any]] = None,
        model_routing_plan: Optional[Dict[str, Any]] = None,
        cost_estimate: float = 0.0,
        context_estimate: int = 0,
        risk_assessment: Optional[Dict[str, Any]] = None,
        escalation_plan: Optional[Dict[str, Any]] = None,
        stop_conditions: Optional[List[str]] = None,
        structured_decision_record_id: str = "",
        nus_learning_tags: Optional[List[str]] = None,
        model_provider_gaps: Optional[List["ModelProviderSufficiencyGap"]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ActivationPlan":
        return cls(
            plan_id=uuid.uuid4().hex,
            request_id=request_id,
            created_at=time.time(),
            selected_managers=selected_managers,
            selected_workers=selected_workers,
            skipped_managers=skipped_managers,
            skipped_workers=skipped_workers,
            activation_reasons=activation_reasons,
            skip_reasons=skip_reasons,
            validation_plan=validation_plan or {},
            governance_plan=governance_plan or {},
            model_routing_plan=model_routing_plan or {},
            cost_estimate=cost_estimate,
            context_estimate=context_estimate,
            risk_assessment=risk_assessment or {},
            escalation_plan=escalation_plan or {},
            stop_conditions=stop_conditions or [],
            structured_decision_record_id=structured_decision_record_id,
            nus_learning_tags=nus_learning_tags or [],
            model_provider_gaps=model_provider_gaps or [],
            no_raw_chain_of_thought=True,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "request_id": self.request_id,
            "created_at": self.created_at,
            "selected_managers": self.selected_managers,
            "selected_workers": self.selected_workers,
            "skipped_managers": self.skipped_managers,
            "skipped_workers": self.skipped_workers,
            "activation_reasons": self.activation_reasons,
            "skip_reasons": self.skip_reasons,
            "validation_plan": self.validation_plan,
            "governance_plan": self.governance_plan,
            "model_routing_plan": self.model_routing_plan,
            "cost_estimate": self.cost_estimate,
            "context_estimate": self.context_estimate,
            "risk_assessment": self.risk_assessment,
            "escalation_plan": self.escalation_plan,
            "stop_conditions": self.stop_conditions,
            "structured_decision_record_id": self.structured_decision_record_id,
            "nus_learning_tags": self.nus_learning_tags,
            "model_provider_gaps": [g.to_dict() for g in self.model_provider_gaps],
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# ModelProviderSufficiencyGap
# ---------------------------------------------------------------------------

@dataclass
class ModelProviderSufficiencyGap:
    """Disclosure record for a missing or insufficient model/provider.

    Required by the model/provider sufficiency disclosure rule:
    never silently skip a gap — always surface what is needed and why.
    """
    gap_id: str
    missing_provider: str
    reason_needed: str
    why_insufficient: str
    improvement_unlocked: str
    cost_complexity_tradeoff: str
    fallback_used: str
    fallback_quality_tradeoff: str
    detected_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        missing_provider: str,
        reason_needed: str,
        why_insufficient: str,
        improvement_unlocked: str,
        cost_complexity_tradeoff: str,
        fallback_used: str,
        fallback_quality_tradeoff: str,
    ) -> "ModelProviderSufficiencyGap":
        return cls(
            gap_id=uuid.uuid4().hex[:12],
            missing_provider=missing_provider,
            reason_needed=reason_needed,
            why_insufficient=why_insufficient,
            improvement_unlocked=improvement_unlocked,
            cost_complexity_tradeoff=cost_complexity_tradeoff,
            fallback_used=fallback_used,
            fallback_quality_tradeoff=fallback_quality_tradeoff,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "missing_provider": self.missing_provider,
            "reason_needed": self.reason_needed,
            "why_insufficient": self.why_insufficient,
            "improvement_unlocked": self.improvement_unlocked,
            "cost_complexity_tradeoff": self.cost_complexity_tradeoff,
            "fallback_used": self.fallback_used,
            "fallback_quality_tradeoff": self.fallback_quality_tradeoff,
            "detected_at": self.detected_at,
        }


__all__ = [
    "ManagerContract",
    "WorkerContract",
    "TaskRoutingRequest",
    "ActivationPlan",
    "ModelProviderSufficiencyGap",
    "RISK_LOW",
    "RISK_MEDIUM",
    "RISK_HIGH",
    "RISK_BLOCKED",
    "COMPLEXITY_SIMPLE",
    "COMPLEXITY_MODERATE",
    "COMPLEXITY_COMPLEX",
    "STATUS_ACTIVE",
    "STATUS_INACTIVE",
    "STATUS_DEGRADED",
    "STATUS_BLOCKED",
    "LATENCY_FAST",
    "LATENCY_NORMAL",
    "LATENCY_RELAXED",
    "LEVEL_JARVIS_PA",
    "LEVEL_COS_GM",
    "LEVEL_MANAGER",
    "LEVEL_WORKER",
    "LEVEL_VALIDATOR",
    "LEVEL_GOVERNANCE",
]
