"""Post-NUS Hierarchical Orchestrator — REST API Routes.

All routes are dry-run/read-only. No real code edits, external API calls,
external sends, deploys, auto-push, auto-merge, or secret access.

Routes:
  GET  /v1/orchestrator/status                   — orchestrator framework status
  GET  /v1/orchestrator/managers                 — list all registered managers
  GET  /v1/orchestrator/workers                  — list all registered workers
  POST /v1/orchestrator/activation/dry-run       — dry-run activation plan
  POST /v1/orchestrator/routing/dry-run          — dry-run model routing recommendation
  POST /v1/orchestrator/decision-records/dry-run — dry-run decision record creation
  GET  /v1/orchestrator/governance/status        — governance gate status

Safety constraints (permanent):
  - Dry-run/read-only only.
  - No writes, deploys, external sends, or secret access.
  - No self-modification, no auto-commit, no auto-push, no auto-merge.
  - No source-code mutation.
  - Production execution blocked — dry-run only.
  - US13 voice remains HOLD/UNSAFE/PARKED.
  - Dangerous actions remain blocked.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for orchestrator routes")

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class ActivationDryRunRequest(BaseModel):
    user_request_summary: str = Field(..., description="Short summary of the user's request")
    intent: str = Field(..., description="Intent category, e.g. 'implement_feature', 'debug', 'review'")
    risk_level: str = Field("low", description="low | medium | high | blocked")
    complexity_level: str = Field("simple", description="simple | moderate | complex")
    domains_required: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    validation_required: bool = True
    context_budget: int = Field(8000, description="Token context budget")
    cost_budget: float = Field(0.10, description="USD cost budget")
    latency_requirement: str = Field("normal", description="fast | normal | relaxed")
    autonomy_profile: str = Field("safe_autopilot")
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoutingDryRunRequest(BaseModel):
    intent: str
    risk_level: str = "low"
    complexity_level: str = "simple"
    action_type: str = "local_read"


class DecisionRecordDryRunRequest(BaseModel):
    action_type: str
    decision: str = "dry_run"
    reason: str
    risk_level: str = "low"
    hierarchy_level: str = "cos_gm"
    session_id: Optional[str] = None
    nus_learning_tags: List[str] = Field(default_factory=list)
    agent_metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/orchestrator/status")
def orchestrator_status() -> Dict[str, Any]:
    """Return orchestrator framework status. Read-only."""
    try:
        from openjarvis.orchestrator import (
            POST_NUS_ORCHESTRATOR_VERSION,
            get_manager_registry,
            get_worker_registry,
            get_activation_planner,
        )
        from openjarvis.nus.decision_record import get_decision_record_status

        mgr_reg = get_manager_registry()
        wrk_reg = get_worker_registry()
        dr_status = get_decision_record_status()

        return {
            "status": "ok",
            "orchestrator_version": POST_NUS_ORCHESTRATOR_VERSION,
            "manager_count": mgr_reg.count(),
            "worker_count": wrk_reg.count(),
            "active_manager_count": len(mgr_reg.list_active()),
            "active_worker_count": len(wrk_reg.list_active()),
            "decision_record_schema_version": dr_status.get("schema_version"),
            "hierarchy_levels_supported": dr_status.get("nus_hierarchy_coverage"),
            "no_raw_chain_of_thought": True,
            "dry_run_only": True,
            "blocked_actions": [
                "production_deploy", "auto_push", "auto_merge",
                "send_external_message", "access_secrets",
            ],
            "us13_voice_parked": True,
            "sprint": "post_nus_hierarchical_orchestrator",
        }
    except Exception as exc:
        logger.exception("orchestrator_status failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/orchestrator/managers")
def list_managers() -> Dict[str, Any]:
    """List all registered managers. Read-only."""
    try:
        from openjarvis.orchestrator import get_manager_registry
        reg = get_manager_registry()
        return {
            "status": "ok",
            "count": reg.count(),
            "managers": [
                {
                    "manager_id": m.manager_id,
                    "name": m.name,
                    "department": m.department,
                    "responsibility": m.responsibility,
                    "skill_domains": m.skill_domains,
                    "worker_pool": m.worker_pool,
                    "risk_ceiling": m.risk_ceiling,
                    "status": m.status,
                    "model_pool": m.model_pool,
                }
                for m in reg.list_all()
            ],
        }
    except Exception as exc:
        logger.exception("list_managers failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/orchestrator/workers")
def list_workers() -> Dict[str, Any]:
    """List all registered workers. Read-only."""
    try:
        from openjarvis.orchestrator import get_worker_registry
        reg = get_worker_registry()
        return {
            "status": "ok",
            "count": reg.count(),
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "name": w.name,
                    "manager_id": w.manager_id,
                    "department": w.department,
                    "responsibility": w.responsibility,
                    "skills": w.skills,
                    "risk_ceiling": w.risk_ceiling,
                    "status": w.status,
                    "model_pool": w.model_pool,
                }
                for w in reg.list_all()
            ],
        }
    except Exception as exc:
        logger.exception("list_workers failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/v1/orchestrator/activation/dry-run")
def activation_dry_run(request: ActivationDryRunRequest) -> Dict[str, Any]:
    """Generate a dry-run activation plan. Does not execute real code edits.

    Returns the minimum sufficient team of managers and workers with
    activation/skip rationale, model routing plan, and governance plan.
    """
    try:
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        from openjarvis.orchestrator import get_activation_planner

        task = TaskRoutingRequest.create(
            user_request_summary=request.user_request_summary,
            intent=request.intent,
            risk_level=request.risk_level,
            complexity_level=request.complexity_level,
            domains_required=request.domains_required,
            required_skills=request.required_skills,
            required_tools=request.required_tools,
            validation_required=request.validation_required,
            context_budget=request.context_budget,
            cost_budget=request.cost_budget,
            latency_requirement=request.latency_requirement,
            autonomy_profile=request.autonomy_profile,
            session_id=request.session_id,
            metadata=request.metadata,
        )

        planner = get_activation_planner()
        plan = planner.plan(task)

        return {
            "status": "ok",
            "dry_run": True,
            "plan": plan.to_dict(),
        }
    except Exception as exc:
        logger.exception("activation_dry_run failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/v1/orchestrator/routing/dry-run")
def routing_dry_run(request: RoutingDryRunRequest) -> Dict[str, Any]:
    """Dry-run model routing recommendation for a task type.

    Does not execute any model calls. Returns routing recommendation only.
    """
    try:
        from openjarvis.orchestrator.activation import (
            MODEL_TIER_CHEAP,
            MODEL_TIER_MID,
            MODEL_TIER_PREMIUM,
            _CRITICAL_RISK_REQUIRES_PREMIUM,
        )

        tier = MODEL_TIER_MID
        reason = f"complexity={request.complexity_level}, risk={request.risk_level}"

        if request.risk_level in _CRITICAL_RISK_REQUIRES_PREMIUM:
            tier = MODEL_TIER_PREMIUM
            reason = f"risk={request.risk_level} requires premium tier for safety"
        elif request.risk_level == "low" and request.complexity_level == "simple":
            tier = MODEL_TIER_CHEAP
            reason = "simple+low-risk qualifies for cheap tier"

        return {
            "status": "ok",
            "dry_run": True,
            "intent": request.intent,
            "risk_level": request.risk_level,
            "complexity_level": request.complexity_level,
            "action_type": request.action_type,
            "recommended_tier": tier,
            "tier_reason": reason,
            "cheap_blocked_for_critical_approval": True,
            "routing_policy": "metadata_driven_not_hardcoded",
            "available_tiers": ["local", "cheap", "mid", "premium"],
            "provider_sufficiency": {
                "sufficient_for_sprint": True,
                "sprint_scope": "dry_run_read_only_framework",
            },
        }
    except Exception as exc:
        logger.exception("routing_dry_run failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/v1/orchestrator/decision-records/dry-run")
def decision_records_dry_run(request: DecisionRecordDryRunRequest) -> Dict[str, Any]:
    """Create a dry-run structured decision record.

    Uses NUS 1F decision_record.py. No raw chain-of-thought stored.
    """
    try:
        from openjarvis.nus.decision_record import (
            build_action_decision_record,
            LEVEL_JARVIS_PA,
            LEVEL_COS_GM,
            LEVEL_MANAGER,
            LEVEL_WORKER,
            LEVEL_VALIDATOR,
            LEVEL_GOVERNANCE,
            _VALID_LEVELS,
        )

        level = request.hierarchy_level
        if level not in _VALID_LEVELS:
            level = LEVEL_COS_GM

        record = build_action_decision_record(
            action_type=request.action_type,
            decision=request.decision,
            reason=request.reason,
            evidence={
                "dry_run": True,
                "agent_metadata": request.agent_metadata,
            },
            session_id=request.session_id or "orchestrator_dry_run",
            hierarchy_level=level,
            risk_level=request.risk_level,
            agent_metadata=request.agent_metadata,
            nus_learning_tags=request.nus_learning_tags or ["orchestration", "dry_run"],
        )

        return {
            "status": "ok",
            "dry_run": True,
            "decision_record": record,
            "no_raw_chain_of_thought": True,
            "hierarchy_level": level,
        }
    except Exception as exc:
        logger.exception("decision_records_dry_run failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/orchestrator/governance/status")
def governance_status() -> Dict[str, Any]:
    """Return governance gate status. Read-only.

    Documents which actions are permanently blocked and which require approval.
    """
    return {
        "status": "ok",
        "dry_run_only": True,
        "permanently_blocked_actions": [
            "production_deploy",
            "auto_push",
            "auto_merge",
            "send_external_message",
            "access_secrets",
            "destructive_data_op",
            "bypass_governance",
            "bypass_safety_gate",
        ],
        "approval_required_for": [
            "high_risk_action",
            "git_push",
            "git_merge",
            "external_api_call",
        ],
        "hard_gates_active": True,
        "us13_voice_parked": True,
        "us13_voice_status": "HOLD/UNSAFE/PARKED — hands-free wake excluded",
        "orchestration_scope": "dry_run_read_only",
        "production_autonomy_status": "blocked — requires future explicit policy gate + Bryan approval",
        "hierarchy_levels": [
            "jarvis_pa",
            "cos_gm",
            "manager",
            "worker",
            "validator",
            "governance",
        ],
        "nus_applies_to_all_levels": True,
    }
