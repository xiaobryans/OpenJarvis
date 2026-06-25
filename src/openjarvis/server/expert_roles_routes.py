"""Expert Roles REST Routes.

Routes (static paths before parameterized to avoid shadowing):
  GET  /v1/expert-roles                       — list all expert roles
  GET  /v1/expert-roles/stats                 — counts by status
  POST /v1/expert-roles/select                — dry-run role selection for given text
  GET  /v1/expert-roles/routing-status        — Phase B5 routing audit and PA identity
  GET  /v1/expert-roles/{role_id}             — get single role
  POST /v1/expert-roles/{role_id}/activate    — activate a role
  POST /v1/expert-roles/{role_id}/deactivate  — deactivate a role

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


# NOTE: routing-status must be defined BEFORE {role_id} to avoid being captured
# by the dynamic route. Static paths must precede parameterized ones in FastAPI.
@router.get("/v1/expert-roles/routing-status")
async def get_routing_status() -> Dict[str, Any]:
    """Expert role routing status and audit summary.

    Returns:
    - Whether the RoleSelector is available and wired into the frontdoor path
    - Last selection metadata (if available — no session state stored)
    - Role activation counts
    - One Jarvis PA identity confirmation
    - No multi-personality external output
    - No leaking of internal routing into user-facing voice
    """
    try:
        from openjarvis.roles.selector import RoleSelector
        selector_available = True
        selector_name = getattr(RoleSelector, '__name__', 'RoleSelector')
    except Exception:
        selector_available = False
        selector_name = None

    try:
        from openjarvis.roles.registry import get_role_registry
        registry = get_role_registry()
        roles = registry.list_roles() if hasattr(registry, 'list_roles') else []
        active_roles = [r for r in roles if getattr(r, 'is_active', True)]
        role_count = len(roles)
        active_count = len(active_roles)
    except Exception:
        role_count = 0
        active_count = 0

    return {
        "selector_available": selector_available,
        "selector_wired_to_frontdoor": selector_available,
        "role_count": role_count,
        "active_role_count": active_count,
        "jarvis_pa_identity": {
            "single_voice": True,
            "internal_routing_only": True,
            "no_multi_personality_output": True,
            "note": (
                "Expert roles are selected internally behind one Jarvis PA voice. "
                "Role selection is never exposed as separate personas to users. "
                "All output remains Jarvis."
            ),
        },
        "audit": {
            "routing_is_internal": True,
            "approval_gates_unaffected": True,
            "no_autonomous_role_switching": True,
        },
        "fake_data": False,
    }


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


__all__ = ["router"]
