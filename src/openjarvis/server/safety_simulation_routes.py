"""Safety simulation routes — Phase C9.

Provides dry-run-only safety simulation, rollback matrix, and policy check
endpoints. real_execution and would_execute are always False.
bypassing_gates is always False.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["safety-simulation"])
__all__ = ["router"]

logger = logging.getLogger(__name__)

# Keywords that indicate a potentially destructive action
_DESTRUCTIVE_KEYWORDS = {
    "delete",
    "drop",
    "remove",
    "reset",
    "wipe",
    "clear",
    "destroy",
    "truncate",
}


def _is_destructive(action: str) -> bool:
    action_lower = action.lower()
    return any(kw in action_lower for kw in _DESTRUCTIVE_KEYWORDS)


def _blast_radius(destructive: bool) -> str:
    return "high" if destructive else "low"


def _authority_tier(destructive: bool) -> str:
    return "tier4" if destructive else "tier3"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SimulateRequest(BaseModel):
    action: str
    parameters: Optional[Dict[str, Any]] = None
    reason: Optional[str] = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/v1/safety-simulation/status")
async def simulation_status() -> Dict[str, Any]:
    """Return safety simulation framework availability and capabilities."""
    return {
        "simulation_framework_available": True,
        "dry_run_only": True,
        "real_execution": False,
        "destructive_actions_blocked": True,
        "rollback_simulations_available": True,
        "policy_checks_available": True,
        "fake_simulation": False,
        "fake_data": False,
        "note": "Safety simulation framework. All simulations are dry-run only. No real execution.",
    }


@router.post("/v1/safety-simulation/simulate")
async def simulate(body: SimulateRequest) -> Dict[str, Any]:
    """Simulate an action — never executes. Dry-run analysis only."""
    action = (body.action or "").strip()
    if not action:
        raise HTTPException(status_code=422, detail="action must be a non-empty string")

    destructive = _is_destructive(action)
    radius = _blast_radius(destructive)
    tier = _authority_tier(destructive)

    policy_checks: List[Dict[str, Any]] = [
        {
            "policy": "approval_required",
            "passed": False,
            "reason": "Approval not yet granted",
        },
        {
            "policy": "destructive_action_gate",
            "passed": not destructive,
            "reason": "Destructive action blocked" if destructive else "Non-destructive action",
        },
    ]

    return {
        "action": action[:200],
        "dry_run": True,
        "executed": False,
        "destructive": destructive,
        "blast_radius": radius,
        "approval_required": True,
        "authority_tier": tier,
        "policy_checks": policy_checks,
        "would_execute": False,
        "rollback_plan": "Manual rollback required. No automated rollback available.",
        "fake_data": False,
    }


@router.get("/v1/safety-simulation/rollback-matrix")
async def rollback_matrix() -> Dict[str, Any]:
    """Return the rollback capability matrix for all system targets."""
    return {
        "rollback_capabilities": [
            {
                "target": "config_changes",
                "rollback_available": True,
                "method": "git revert",
                "automated": False,
                "approval_required": True,
            },
            {
                "target": "database_changes",
                "rollback_available": False,
                "method": "manual restore",
                "automated": False,
                "approval_required": True,
                "gate": "No automated DB rollback",
            },
            {
                "target": "memory_store",
                "rollback_available": False,
                "method": "manual backup restore",
                "automated": False,
                "approval_required": True,
                "gate": "Backup system not deployed",
            },
            {
                "target": "goal_registry",
                "rollback_available": True,
                "method": "goal status revert",
                "automated": False,
                "approval_required": True,
            },
            {
                "target": "connector_credentials",
                "rollback_available": False,
                "method": "manual vault rotation",
                "automated": False,
                "approval_required": True,
                "gate": "External vault required",
            },
        ],
        "automated_rollback_live": False,
        "fake_rollback": False,
        "fake_data": False,
        "note": (
            "Rollback matrix. Config and goal changes are manually reversible. "
            "DB/memory/credentials require external gates."
        ),
    }


@router.get("/v1/safety-simulation/policy-checks")
async def policy_checks() -> Dict[str, Any]:
    """Return hard and soft gate actions from JarvisConstitution."""
    hard_gates: List[str] = []
    soft_gates: List[str] = []
    source = "unavailable"

    try:
        from openjarvis.governance.constitution import HARD_GATE_ACTIONS  # type: ignore[import]

        hard_gates = sorted(HARD_GATE_ACTIONS) if HARD_GATE_ACTIONS else []
        source = "constitution"
    except Exception:
        pass

    try:
        from openjarvis.governance.constitution import SOFT_GATE_ACTIONS  # type: ignore[import]

        soft_gates = sorted(SOFT_GATE_ACTIONS) if SOFT_GATE_ACTIONS else []
        source = "constitution"
    except Exception:
        pass

    return {
        "hard_gates": hard_gates,
        "hard_gate_count": len(hard_gates),
        "soft_gates": soft_gates,
        "soft_gate_count": len(soft_gates),
        "gates_enforced": True,
        "bypassing_gates": False,
        "fake_data": False,
        "source": source,
    }
