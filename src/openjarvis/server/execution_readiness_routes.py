"""Execution Readiness routes — Phase C11.

C11 — Autonomous Execution Readiness Manager.
Surfaces readiness status and approval gate requirements for all Jarvis
execution systems. No action is ever executed autonomously; all actions
require explicit Bryan approval.

Routes:
  GET  /v1/execution-readiness/status    — per-system readiness + overall state
  GET  /v1/execution-readiness/matrix    — action class approval matrix
  POST /v1/execution-readiness/dry-run-check — dry-run gate check (never executes)

Governance:
  - fake_data is always False
  - No autonomous execution without explicit Bryan approval
  - dry_run and executed flags are always set correctly
  - No secret values are ever returned
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for execution readiness routes")

router = APIRouter(tags=["execution-readiness"])
__all__ = ["router"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class DryRunCheckRequest(BaseModel):
    action_class: str = Field(..., description="Action class identifier")
    system_id: str = Field(..., description="Target system identifier")
    description: str = Field("", description="Human-readable description of the action")


# ---------------------------------------------------------------------------
# Static data helpers
# ---------------------------------------------------------------------------

_SYSTEMS: List[Dict[str, Any]] = [
    {
        "system_id": "life_os",
        "name": "Life OS",
        "status": "ready_local",
        "approval_required": True,
        "gate": "bryan_approval_required",
    },
    {
        "system_id": "goals",
        "name": "Goals",
        "status": "ready_local",
        "approval_required": True,
        "gate": "bryan_approval_required",
    },
    {
        "system_id": "routines",
        "name": "Routines",
        "status": "ready_local",
        "approval_required": True,
        "gate": "bryan_approval_required",
    },
    {
        "system_id": "connectors",
        "name": "Connectors",
        "status": "blocked_external",
        "approval_required": True,
        "gate": "connector_credentials_required",
    },
    {
        "system_id": "browser_operator",
        "name": "Browser Operator",
        "status": "blocked_gate",
        "approval_required": True,
        "gate": "browser_automation_gate",
    },
    {
        "system_id": "device_controller",
        "name": "Device Controller",
        "status": "blocked_gate",
        "approval_required": True,
        "gate": "device_control_gate",
    },
    {
        "system_id": "company_os",
        "name": "Company OS",
        "status": "ready_local",
        "approval_required": True,
        "gate": "bryan_approval_required",
    },
    {
        "system_id": "cloud_execution",
        "name": "Cloud Execution",
        "status": "blocked_external",
        "approval_required": True,
        "gate": "cloud_execution_gate",
    },
]

_ACTION_CLASSES: List[Dict[str, Any]] = [
    {
        "class_id": "read_only",
        "name": "Read Only",
        "min_approval_tier": 1,
        "blocked_without_approval": True,
    },
    {
        "class_id": "local_write",
        "name": "Local Write",
        "min_approval_tier": 2,
        "blocked_without_approval": True,
    },
    {
        "class_id": "connector_action",
        "name": "Connector Action",
        "min_approval_tier": 3,
        "blocked_without_approval": True,
    },
    {
        "class_id": "external_send",
        "name": "External Send",
        "min_approval_tier": 3,
        "blocked_without_approval": True,
    },
    {
        "class_id": "cloud_execution",
        "name": "Cloud Execution",
        "min_approval_tier": 4,
        "blocked_without_approval": True,
    },
    {
        "class_id": "destructive",
        "name": "Destructive",
        "min_approval_tier": 5,
        "blocked_without_approval": True,
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/execution-readiness/status")
async def execution_readiness_status() -> Dict[str, Any]:
    """Return per-system readiness and overall autonomous execution state.

    All systems require explicit Bryan approval before any action may run.
    No system executes autonomously. fake_data is always False.
    """
    return {
        "systems": _SYSTEMS,
        "overall_readiness": "partial",
        "autonomous_execution_live": False,
        "approval_required_for_all_actions": True,
        "fake_readiness": False,
        "fake_data": False,
        "note": "No system may execute autonomously without explicit Bryan approval.",
    }


@router.get("/v1/execution-readiness/matrix")
async def execution_readiness_matrix() -> Dict[str, Any]:
    """Return the action class approval matrix.

    All action classes require explicit approval.
    Autonomous execution is not live.
    """
    return {
        "action_classes": _ACTION_CLASSES,
        "all_require_approval": True,
        "autonomous_execution_live": False,
        "fake_data": False,
    }


@router.post("/v1/execution-readiness/dry-run-check")
async def dry_run_check(body: DryRunCheckRequest) -> Dict[str, Any]:
    """Gate check for a proposed action — dry run only, never executes.

    Returns whether the action *would* be allowed if approval were granted.
    The action is never executed. approval_gate_bypassed is always False.
    """
    if not body.action_class or not body.action_class.strip():
        raise HTTPException(status_code=422, detail="action_class must be a non-empty string")
    if not body.system_id or not body.system_id.strip():
        raise HTTPException(status_code=422, detail="system_id must be a non-empty string")

    # Only read_only actions would be permitted (still require approval in practice)
    would_be_allowed = body.action_class == "read_only"

    return {
        "would_be_allowed": would_be_allowed,
        "requires_approval": True,
        "dry_run": True,
        "executed": False,
        "approval_gate_bypassed": False,
        "fake_data": False,
    }
