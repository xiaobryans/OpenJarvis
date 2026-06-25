"""Org Mode REST Routes (B19).

Routes:
  GET  /v1/org-mode/status             — org mode availability (single-user only)
  GET  /v1/org-mode/capability-matrix  — planned org capabilities with gate conditions
  POST /v1/org-mode/dry-run/invite     — dry-run user invite (never executes)

Design:
  - fake_data: False in all responses
  - Single-user only; multi-user/org mode requires production auth (external gate)
  - All capabilities are dry-run/planned only
  - Email addresses are NEVER echoed back in responses
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for org_mode routes")

logger = logging.getLogger(__name__)
router = APIRouter(tags=["org-mode"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# GET /v1/org-mode/status
# ---------------------------------------------------------------------------


@router.get("/v1/org-mode/status")
async def org_mode_status() -> Dict[str, Any]:
    """Return org mode availability. Single-user only; multi-user requires external gate."""
    return {
        "multi_user_live": False,  # No production multi-user auth
        "org_mode_available": False,
        "single_user_mode": True,
        "production_auth_ready": False,
        "external_gate": (
            "Multi-user/org mode requires production auth, user management, "
            "and role-based access control (external gate)."
        ),
        "dry_run_only": True,
        "fake_data": False,
        "note": (
            "Org mode is single-user only. "
            "Multi-user/organization mode requires production auth setup (external gate)."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/org-mode/capability-matrix
# ---------------------------------------------------------------------------


@router.get("/v1/org-mode/capability-matrix")
async def capability_matrix() -> Dict[str, Any]:
    """Return org mode capability matrix. All capabilities are dry-run/planned only."""
    return {
        "capabilities": [
            {
                "name": "Multi-user accounts",
                "available": False,
                "gate": "Production auth required",
            },
            {
                "name": "Role-based access control (RBAC)",
                "available": False,
                "gate": "RBAC not yet implemented",
            },
            {
                "name": "Team delegation",
                "available": False,
                "gate": "Multi-user auth required",
            },
            {
                "name": "Audit log per user",
                "available": False,
                "gate": "Multi-user auth required",
            },
            {
                "name": "Org-level policies",
                "available": False,
                "gate": "Multi-user auth required",
            },
            {
                "name": "Invitation system",
                "available": False,
                "gate": "Email service + auth required",
            },
        ],
        "role_model": {
            "planned_roles": ["owner", "admin", "member", "viewer", "guest"],
            "implemented": False,
            "note": "Role model planned but not yet implemented.",
        },
        "multi_user_live": False,
        "fake_data": False,
        "note": "Org mode capability matrix only. No live multi-user functionality.",
    }


# ---------------------------------------------------------------------------
# POST /v1/org-mode/dry-run/invite
# ---------------------------------------------------------------------------


class DryRunInviteRequest(BaseModel):
    email: str = Field(..., description="Invitee email address (never echoed back)")
    role: str = Field(..., description="Planned role for invitee")
    message: str = Field("", description="Optional personal message for the invite")


@router.post("/v1/org-mode/dry-run/invite")
async def dry_run_invite(body: DryRunInviteRequest) -> Dict[str, Any]:
    """Dry-run user invite — records intent only, never sends email or creates accounts.

    The email address is NEVER echoed back in the response.
    Multi-user auth and email connector are required for real execution (external gate).
    """
    try:
        role = body.role.strip() or "member"
        return {
            "dry_run": True,
            "executed": False,
            "email": "<redacted>",  # Never echo real email back
            "role": role,
            "would_send_invite": False,
            "gate": "Multi-user auth and email connector required",
            "production_auth_required": True,
            "fake_data": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("dry_run_invite: unexpected error: %s", exc)
        return {
            "dry_run": True,
            "executed": False,
            "email": "<redacted>",
            "role": "unknown",
            "would_send_invite": False,
            "gate": "Multi-user auth and email connector required",
            "production_auth_required": True,
            "fake_data": False,
            "error": "Could not process invite request",
        }
