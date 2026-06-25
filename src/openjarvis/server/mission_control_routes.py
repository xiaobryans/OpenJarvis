"""REST endpoints for Long-Horizon Mission Control — Phase C2.

Routes:
  GET  /v1/mission-control/dashboard                               — mission dashboard (reads MissionStore if available)
  GET  /v1/mission-control/missions/{mission_id}/dependency-graph  — dependency graph for a mission
  GET  /v1/mission-control/missions/{mission_id}/risk-assessment   — risk & authority tier for a mission
  POST /v1/mission-control/missions/{mission_id}/dry-run-next-step — dry-run next step plan (no execution)

NOTE: These endpoints use the /v1/mission-control/ prefix and do NOT conflict with
      /v1/missions/* endpoints defined in mission_routes.py.

Governance:
  - unapproved_execution: False in all responses — always
  - auto_execute: False in all responses — always
  - approval_required: True for all mutating operations
  - fake_data: False in all responses
  - dry-run-next-step is dry-run only — nothing is executed or persisted
  - No secrets in any response
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for mission_control_routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mission-control"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# Graceful MissionStore import
# ---------------------------------------------------------------------------


def _load_mission_store() -> Optional[Any]:
    """Attempt to load MissionStore. Returns instance or None if unavailable."""
    try:
        from openjarvis.mission.store import MissionStore  # type: ignore
        return MissionStore()
    except Exception as exc:
        logger.debug("MissionStore unavailable: %s", exc)
        return None


def _safe_list(store: Any) -> List[Any]:
    """Safely call store.list(), returning [] on any error."""
    try:
        result = store.list()
        return list(result) if result is not None else []
    except Exception as exc:
        logger.debug("MissionStore.list() failed: %s", exc)
        return []


def _safe_get(store: Any, mission_id: str) -> Optional[Any]:
    """Safely look up a mission by ID, returning None if not found or on error."""
    try:
        # Try .get() first, then fall back to scanning .list()
        if hasattr(store, "get"):
            result = store.get(mission_id)
            return result
        # Fallback: scan list
        missions = _safe_list(store)
        for m in missions:
            mid = getattr(m, "id", None) or getattr(m, "mission_id", None)
            if str(mid) == str(mission_id):
                return m
        return None
    except Exception as exc:
        logger.debug("MissionStore lookup for %s failed: %s", mission_id, exc)
        return None


def _mission_to_dashboard_row(m: Any) -> Dict[str, Any]:
    """Convert a mission object or dict to the dashboard row schema."""
    if isinstance(m, dict):
        return {
            "mission_id": str(m.get("id") or m.get("mission_id", "")),
            "title": str(m.get("title", "")),
            "status": str(m.get("status", "unknown")),
            "milestones": list(m.get("milestones", [])),
            "checkpoints": list(m.get("checkpoints", [])),
            "dependencies": list(m.get("dependencies", [])),
            "risk_level": str(m.get("risk_level", "unknown")),
            "authority_tier": str(m.get("authority_tier", "unknown")),
            "next_approved_step": None,
            "approval_required": True,
            "auto_execute": False,
        }
    return {
        "mission_id": str(getattr(m, "id", "") or getattr(m, "mission_id", "")),
        "title": str(getattr(m, "title", "")),
        "status": str(
            getattr(m, "status", {}).value
            if hasattr(getattr(m, "status", None), "value")
            else getattr(m, "status", "unknown")
        ),
        "milestones": list(getattr(m, "milestones", [])),
        "checkpoints": list(getattr(m, "checkpoints", [])),
        "dependencies": list(getattr(m, "dependencies", [])),
        "risk_level": str(
            getattr(m, "risk_level", {}).value
            if hasattr(getattr(m, "risk_level", None), "value")
            else getattr(m, "risk_level", "unknown")
        ),
        "authority_tier": str(getattr(m, "authority_tier", "unknown")),
        "next_approved_step": None,
        "approval_required": True,
        "auto_execute": False,
    }


def _mission_status_str(m: Any) -> str:
    """Extract status string from a mission object."""
    raw = getattr(m, "status", None)
    if raw is None:
        return "unknown"
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class DryRunNextStepRequest(BaseModel):
    step_type: str = Field(..., min_length=1, description="Type of step (non-empty)")
    title: str = Field(..., min_length=1, description="Step title (non-empty)")
    reason: str = Field("", description="Optional reason for the step")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/mission-control/dashboard")
async def mission_control_dashboard() -> Dict[str, Any]:
    """Return mission dashboard. Reads from MissionStore if available; returns empty list otherwise."""
    try:
        store = _load_mission_store()
        source: str
        rows: List[Dict[str, Any]]

        if store is not None:
            raw_missions = _safe_list(store)
            rows = [_mission_to_dashboard_row(m) for m in raw_missions]
            source = "mission_store"
        else:
            rows = []
            source = "unavailable"

        active = sum(1 for r in rows if r.get("status") in ("active", "in_progress", "running"))
        paused = sum(1 for r in rows if r.get("status") in ("paused", "on_hold", "blocked"))

        return {
            "missions": rows,
            "total": len(rows),
            "active": active,
            "paused": paused,
            "unapproved_execution": False,
            "fake_data": False,
            "source": source,
            "note": (
                "Mission Control dashboard. No unapproved execution. "
                "All next steps require explicit approval."
            ),
        }
    except Exception as exc:
        logger.exception("mission_control_dashboard error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/v1/mission-control/missions/{mission_id}/dependency-graph")
async def mission_control_dependency_graph(mission_id: str) -> Dict[str, Any]:
    """Return dependency graph for a mission. 404 if store is available and mission is not found."""
    try:
        store = _load_mission_store()
        found: bool
        dependencies: List[Dict[str, Any]]

        if store is not None:
            mission = _safe_get(store, mission_id)
            if mission is None:
                raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
            found = True
            raw_deps = (
                mission.get("dependencies", [])
                if isinstance(mission, dict)
                else list(getattr(mission, "dependencies", []))
            )
            dependencies = []
            for dep in raw_deps:
                if isinstance(dep, dict):
                    dependencies.append(
                        {
                            "dep_id": str(dep.get("id") or dep.get("dep_id", "")),
                            "title": str(dep.get("title", "")),
                            "status": str(dep.get("status", "unknown")),
                            "blocking": bool(dep.get("blocking", False)),
                        }
                    )
                else:
                    dependencies.append(
                        {
                            "dep_id": str(getattr(dep, "id", "") or getattr(dep, "dep_id", "")),
                            "title": str(getattr(dep, "title", "")),
                            "status": str(
                                getattr(dep, "status", {}).value
                                if hasattr(getattr(dep, "status", None), "value")
                                else getattr(dep, "status", "unknown")
                            ),
                            "blocking": bool(getattr(dep, "blocking", False)),
                        }
                    )
        else:
            # Store unavailable — return graceful response
            found = False
            dependencies = []

        return {
            "mission_id": mission_id,
            "found": found,
            "dependencies": dependencies,
            "dependency_resolution_auto": False,
            "approval_required_to_unblock": True,
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("mission_control_dependency_graph error (mission=%s): %s", mission_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/v1/mission-control/missions/{mission_id}/risk-assessment")
async def mission_control_risk_assessment(mission_id: str) -> Dict[str, Any]:
    """Return risk level and authority tier for a mission."""
    try:
        store = _load_mission_store()
        found: bool
        risk_level: str
        authority_tier: str
        risk_factors: List[Any]

        if store is not None:
            mission = _safe_get(store, mission_id)
            if mission is None:
                raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
            found = True
            if isinstance(mission, dict):
                risk_level = str(mission.get("risk_level", "unknown"))
                authority_tier = str(mission.get("authority_tier", "unknown"))
                risk_factors = list(mission.get("risk_factors", []))
            else:
                raw_risk = getattr(mission, "risk_level", None)
                risk_level = str(raw_risk.value if hasattr(raw_risk, "value") else raw_risk or "unknown")
                authority_tier = str(getattr(mission, "authority_tier", "unknown"))
                risk_factors = list(getattr(mission, "risk_factors", []))
        else:
            found = False
            risk_level = "unknown"
            authority_tier = "unknown"
            risk_factors = []

        return {
            "mission_id": mission_id,
            "found": found,
            "risk_level": risk_level,
            "authority_tier": authority_tier,
            "risk_factors": risk_factors,
            "auto_proceed": False,
            "approval_required": True,
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("mission_control_risk_assessment error (mission=%s): %s", mission_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/v1/mission-control/missions/{mission_id}/dry-run-next-step")
async def mission_control_dry_run_next_step(
    mission_id: str, body: DryRunNextStepRequest
) -> Dict[str, Any]:
    """Dry-run only — produce a plan for the next step without executing anything."""
    try:
        step_type = body.step_type
        title = body.title

        plan = [
            {
                "step": 1,
                "description": f"Validate step type and authority for mission {mission_id}",
            },
            {
                "step": 2,
                "description": "Request approval for next step",
            },
            {
                "step": 3,
                "description": f"Execute: {title} (requires explicit approval — not auto-executed)",
            },
        ]

        return {
            "mission_id": mission_id,
            "dry_run": True,
            "step_type": step_type,
            "title": title,
            "executed": False,
            "auto_execute": False,
            "approval_required": True,
            "plan": plan,
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("mission_control_dry_run_next_step error (mission=%s): %s", mission_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")
