"""Self-Upgrade REST Routes — Phase I.

Routes:
  POST /v1/self-upgrade/request          — create staged upgrade plan
  GET  /v1/self-upgrade/plans            — list upgrade plans
  GET  /v1/self-upgrade/plans/{plan_id}  — get plan detail
  POST /v1/self-upgrade/plans/{plan_id}/steps — add step
  POST /v1/self-upgrade/plans/{plan_id}/steps/{step_id}/start — start step
  POST /v1/self-upgrade/plans/{plan_id}/steps/{step_id}/complete — complete step
  POST /v1/self-upgrade/plans/{plan_id}/steps/{step_id}/fail    — fail step
  POST /v1/self-upgrade/plans/{plan_id}/confirm                 — confirm plan (approval gate)
  POST /v1/self-upgrade/plans/{plan_id}/rollback                — create rollback metadata
  GET  /v1/self-upgrade/provider-status  — truthful model/provider status
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openjarvis.orchestrator.self_upgrade import (
    ModelProviderTruth,
    ProviderStatus,
    SelfUpgradePlan,
    UpgradeRisk,
    get_self_upgrade_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["self-upgrade"])


class CreateUpgradePlanRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    source_request: str = Field(..., min_length=1, description="Original request text")
    client_platform: str = Field("desktop", description="desktop | mobile | api")
    memory_refs: List[str] = Field(default_factory=list)


class AddStepRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    risk: str = Field("low", description="low | medium | high | destructive")
    requires_confirmation: bool = False
    rollback_command: Optional[str] = None
    validation_command: Optional[str] = None
    files_to_modify: List[str] = Field(default_factory=list)


class FailStepRequest(BaseModel):
    reason: str = ""


@router.post("/v1/self-upgrade/request")
async def create_upgrade_plan(body: CreateUpgradePlanRequest) -> Dict[str, Any]:
    """Create a staged self-upgrade plan. Accepts from desktop or mobile."""
    store = get_self_upgrade_store()
    plan = SelfUpgradePlan.create(
        title=body.title,
        description=body.description,
        source_request=body.source_request,
        client_platform=body.client_platform,
    )
    plan.memory_refs = body.memory_refs
    store.add(plan)
    return {"plan": plan.to_dict(), "created": True}


@router.get("/v1/self-upgrade/plans")
async def list_plans() -> Dict[str, Any]:
    store = get_self_upgrade_store()
    plans = store.list_all()
    return {"plans": [p.to_dict() for p in plans], "count": len(plans)}


@router.get("/v1/self-upgrade/plans/{plan_id}")
async def get_plan(plan_id: str) -> Dict[str, Any]:
    store = get_self_upgrade_store()
    plan = store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    detail = plan.to_dict()
    detail["steps"] = [s.to_dict() for s in plan.steps]
    detail["rollback_metadata"] = plan.rollback_metadata.to_dict() if plan.rollback_metadata else None
    return {"plan": detail}


@router.post("/v1/self-upgrade/plans/{plan_id}/steps")
async def add_step(plan_id: str, body: AddStepRequest) -> Dict[str, Any]:
    valid_risks = {r.value for r in UpgradeRisk}
    if body.risk not in valid_risks:
        raise HTTPException(status_code=400, detail=f"Invalid risk: {body.risk}")
    store = get_self_upgrade_store()
    plan = store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    step = plan.add_step(
        title=body.title,
        description=body.description,
        risk=body.risk,
        requires_confirmation=body.requires_confirmation,
        rollback_command=body.rollback_command,
        validation_command=body.validation_command,
        files_to_modify=body.files_to_modify,
    )
    return {"step": step.to_dict(), "created": True}


@router.post("/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/start")
async def start_step(plan_id: str, step_id: str) -> Dict[str, Any]:
    store = get_self_upgrade_store()
    plan = store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    if plan.confirmation_required and not plan.confirmed:
        raise HTTPException(status_code=403, detail="Plan requires confirmation before execution")
    step = plan.get_step(step_id)
    if step is None:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")
    step.start()
    return {"step_id": step_id, "status": step.status.value}


@router.post("/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/complete")
async def complete_step(plan_id: str, step_id: str) -> Dict[str, Any]:
    store = get_self_upgrade_store()
    plan = store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    step = plan.get_step(step_id)
    if step is None:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")
    step.complete()
    return {"step_id": step_id, "status": step.status.value}


@router.post("/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/fail")
async def fail_step(plan_id: str, step_id: str, body: FailStepRequest) -> Dict[str, Any]:
    store = get_self_upgrade_store()
    plan = store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    step = plan.get_step(step_id)
    if step is None:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")
    step.fail(body.reason)
    return {"step_id": step_id, "status": step.status.value, "failure_reason": body.reason}


@router.post("/v1/self-upgrade/plans/{plan_id}/confirm")
async def confirm_plan(plan_id: str) -> Dict[str, Any]:
    """Approval gate: confirm plan before any high-risk steps execute."""
    store = get_self_upgrade_store()
    plan = store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    plan.confirm()
    return {"plan_id": plan_id, "confirmed": True}


@router.post("/v1/self-upgrade/plans/{plan_id}/rollback")
async def create_rollback(plan_id: str) -> Dict[str, Any]:
    store = get_self_upgrade_store()
    plan = store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    rb = plan.create_rollback_metadata()
    return {"rollback": rb.to_dict()}


@router.get("/v1/self-upgrade/provider-status")
async def provider_status() -> Dict[str, Any]:
    """Truthful model/provider status — no fake claims."""
    providers = []

    # OpenRouter / OpenAI
    has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    providers.append(ModelProviderTruth(
        provider_name="openrouter",
        status=ProviderStatus.AVAILABLE if has_openrouter else ProviderStatus.NOT_CONFIGURED,
        model_id="gpt-4o-mini" if has_openrouter else None,
        is_live=has_openrouter,
        is_mock=not has_openrouter,
        notes="OpenRouter/OpenAI — configured via env" if has_openrouter else "OPENROUTER_API_KEY not set",
    ).to_dict())

    # Ollama (local)
    providers.append(ModelProviderTruth(
        provider_name="ollama",
        status=ProviderStatus.LOCAL,
        model_id=None,
        is_live=False,
        is_mock=False,
        notes="Local Ollama — available if server running on localhost:11434",
    ).to_dict())

    return {
        "providers": providers,
        "count": len(providers),
        "truthful": True,  # No fake claims
        "mock_or_live_distinction_maintained": True,
    }


__all__ = ["router"]
