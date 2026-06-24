"""Expert Roles REST Routes.

Routes:
  GET  /v1/expert-roles           — list all expert roles
  GET  /v1/expert-roles/{role_id} — get single role
  POST /v1/expert-roles/{role_id}/activate   — activate a role
  POST /v1/expert-roles/{role_id}/deactivate — deactivate a role
  GET  /v1/expert-roles/stats     — counts by status
  POST /v1/expert-roles/select    — dry-run role selection for given text

Design rules:
  - No secret values returned.
  - Role output is always synthesized through Jarvis PA (not exposed as separate characters).
  - High-safety roles (legal/finance) always include disclaimer in response.
  - Selection audit record is returned but not persisted (dry-run only).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic required for expert roles routes")

from openjarvis.orchestrator.expert_roles import ExpertRoleRegistry, RoleSelector

logger = logging.getLogger(__name__)

router = APIRouter(tags=["expert-roles"])

_registry = ExpertRoleRegistry.get_instance()
_selector = RoleSelector(registry=_registry)


class SelectRolesRequest(BaseModel):
    text: str = Field(..., min_length=1)
    action_type: str = ""
    session_id: str = ""
    max_roles: int = Field(3, ge=1, le=5)
    include_high_safety: bool = False


@router.get("/v1/expert-roles")
async def list_roles(
    status: str = "",
    domain: str = "",
) -> Dict[str, Any]:
    roles = _registry.list_all()
    if status:
        roles = [r for r in roles if r.status == status]
    if domain:
        roles = [r for r in roles if r.domain == domain]
    return {
        "roles": [r.to_dict() for r in roles],
        "count": len(roles),
        "stats": _registry.stats(),
        "note": "Expert roles are internal. They do not appear as separate speakers in Jarvis responses.",
    }


@router.get("/v1/expert-roles/stats")
async def get_role_stats() -> Dict[str, Any]:
    return {"stats": _registry.stats()}


@router.get("/v1/expert-roles/{role_id}")
async def get_role(role_id: str) -> Dict[str, Any]:
    role = _registry.get(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"Expert role '{role_id}' not found")
    return {"role": role.to_dict()}


@router.post("/v1/expert-roles/{role_id}/activate")
async def activate_role(role_id: str) -> Dict[str, Any]:
    role = _registry.activate(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"Expert role '{role_id}' not found")
    return {"role": role.to_dict(), "status": "activated"}


@router.post("/v1/expert-roles/{role_id}/deactivate")
async def deactivate_role(role_id: str) -> Dict[str, Any]:
    role = _registry.deactivate(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"Expert role '{role_id}' not found")
    return {"role": role.to_dict(), "status": "deactivated"}


@router.post("/v1/expert-roles/select")
async def select_roles(req: SelectRolesRequest) -> Dict[str, Any]:
    """Dry-run: select relevant expert roles for given text (no execution)."""
    selected = _selector.select(
        text=req.text,
        action_type=req.action_type,
        max_roles=req.max_roles,
        include_high_safety=req.include_high_safety,
    )
    audit = _selector.audit_selection(
        session_id=req.session_id,
        selected=selected,
        trigger_text=req.text,
        action_type=req.action_type,
    )
    disclaimers = [r.disclaimer for r in selected if r.disclaimer]
    return {
        "selected_roles": [r.to_dict() for r in selected],
        "count": len(selected),
        "audit": audit.to_dict(),
        "disclaimers": disclaimers,
        "note": "Role output is always synthesized through one unified Jarvis PA voice.",
    }


__all__ = ["router"]
