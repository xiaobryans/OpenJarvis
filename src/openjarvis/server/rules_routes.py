"""Rules Engine REST Routes.

Routes:
  GET  /v1/rules                  — list all rules
  GET  /v1/rules/{rule_id}        — get single rule
  POST /v1/rules                  — create rule
  PATCH /v1/rules/{rule_id}       — update rule fields
  POST /v1/rules/{rule_id}/activate   — activate a rule
  POST /v1/rules/{rule_id}/deactivate — deactivate a rule
  DELETE /v1/rules/{rule_id}      — delete rule
  GET  /v1/rules/stats            — rule counts by status
  POST /v1/rules/evaluate         — evaluate rules against a context (dry-run)

Design rules:
  - No secret values.
  - Conflict detection on every create/update.
  - Activation requires safety_level != high (high requires approval).
  - Hard safety rules cannot be deleted via API.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic required for rules routes")

from openjarvis.rules.engine import RulesEngine
from openjarvis.rules.registry import RuleRegistry
from openjarvis.rules.types import (
    Rule,
    RuleContext,
    RuleScope,
    RuleStatus,
    RuleType,
    make_rule_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rules"])


def _get_registry() -> RuleRegistry:
    return RuleRegistry.get_instance()


def _get_engine() -> RulesEngine:
    return RulesEngine(registry=_get_registry())


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateRuleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    rule_type: str = Field("behavioral", description="behavioral | filter | trigger | context | safety")
    scope: str = Field("global", description="global | project | context | user")
    scope_id: str = ""
    priority: int = Field(50, ge=0, le=100)
    condition: Dict[str, Any] = Field(default_factory=dict)
    action: Dict[str, Any] = Field(default_factory=dict)
    source: str = "user"
    safety_level: str = Field("low", description="low | medium | high")
    tags: List[str] = Field(default_factory=list)


class UpdateRuleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    condition: Optional[Dict[str, Any]] = None
    action: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    safety_level: Optional[str] = None


class EvaluateRulesRequest(BaseModel):
    session_id: str = ""
    project_id: str = ""
    action_type: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/rules")
async def list_rules(
    scope: str = "",
    status: str = "",
    rule_type: str = "",
) -> Dict[str, Any]:
    """List rules with optional filters."""
    rules = _get_registry().list_all()
    if scope:
        rules = [r for r in rules if r.scope == scope]
    if status:
        rules = [r for r in rules if r.status == status]
    if rule_type:
        rules = [r for r in rules if r.rule_type == rule_type]
    return {
        "rules": [r.to_dict() for r in rules],
        "count": len(rules),
        "stats": _get_registry().stats(),
    }


@router.get("/v1/rules/stats")
async def get_rule_stats() -> Dict[str, Any]:
    return {"stats": _get_registry().stats()}


@router.get("/v1/rules/{rule_id}")
async def get_rule(rule_id: str) -> Dict[str, Any]:
    reg = _get_registry()
    rule = reg.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    return {"rule": rule.to_dict()}


@router.post("/v1/rules")
async def create_rule(req: CreateRuleRequest) -> Dict[str, Any]:
    """Create a new rule. Returns conflict warnings if applicable."""
    reg = _get_registry()
    rule = Rule(
        rule_id=make_rule_id(),
        name=req.name,
        description=req.description,
        rule_type=req.rule_type,
        scope=req.scope,
        status=RuleStatus.ACTIVE if req.safety_level != "high" else RuleStatus.DRAFT,
        priority=req.priority,
        condition=req.condition,
        action=req.action,
        scope_id=req.scope_id,
        source=req.source,
        safety_level=req.safety_level,
        tags=req.tags,
        created_at=time.time(),
        updated_at=time.time(),
    )
    conflicts = reg.detect_conflicts(rule)
    if conflicts:
        rule.conflict_ids = conflicts
        rule.status = RuleStatus.CONFLICTED
    reg.create(rule)
    return {
        "rule": rule.to_dict(),
        "conflicts": conflicts,
        "warning": (
            "Rule created with CONFLICTED status — resolve conflicts before activation."
            if conflicts else ""
        ),
        "note": (
            "High-safety rules start in DRAFT state and require manual activation."
            if req.safety_level == "high" else ""
        ),
    }


@router.patch("/v1/rules/{rule_id}")
async def update_rule(rule_id: str, req: UpdateRuleRequest) -> Dict[str, Any]:
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No update fields provided")
    reg = _get_registry()
    rule = reg.update(rule_id, updates)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    return {"rule": rule.to_dict()}


@router.post("/v1/rules/{rule_id}/activate")
async def activate_rule(rule_id: str) -> Dict[str, Any]:
    reg = _get_registry()
    rule = reg.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    if rule.safety_level == "high":
        raise HTTPException(
            status_code=403,
            detail="High-safety rules require manual review before activation. "
                   "Set safety_level to medium or low, or use the authority approval flow.",
        )
    updated = reg.activate(rule_id)
    return {"rule": updated.to_dict() if updated else {}, "status": "activated"}


@router.post("/v1/rules/{rule_id}/deactivate")
async def deactivate_rule(rule_id: str) -> Dict[str, Any]:
    reg = _get_registry()
    rule = reg.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    if rule.source == "system" and rule.rule_type == "safety":
        raise HTTPException(
            status_code=403,
            detail="System safety rules cannot be deactivated via API.",
        )
    updated = reg.deactivate(rule_id)
    return {"rule": updated.to_dict() if updated else {}, "status": "deactivated"}


@router.delete("/v1/rules/{rule_id}")
async def delete_rule(rule_id: str) -> Dict[str, Any]:
    reg = _get_registry()
    rule = reg.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    if rule.source == "system" and rule.rule_type == "safety":
        raise HTTPException(
            status_code=403,
            detail="System safety rules cannot be deleted via API.",
        )
    ok = reg.delete(rule_id)
    return {"deleted": ok, "rule_id": rule_id}


@router.post("/v1/rules/evaluate")
async def evaluate_rules(req: EvaluateRulesRequest) -> Dict[str, Any]:
    """Dry-run: evaluate which rules match the given context."""
    ctx = RuleContext(
        session_id=req.session_id,
        project_id=req.project_id,
        action_type=req.action_type,
        metadata=req.metadata,
    )
    result = _get_engine().evaluate(ctx)
    return {"evaluation": result.to_dict()}


__all__ = ["router"]
