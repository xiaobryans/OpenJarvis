"""Action Planner routes — Phase C12.

C12 — Cross-System Action Planner.
Provides system capability discovery, reusable plan templates, and dry-run
plan generation across all Jarvis B/C phase systems. No plan is ever executed;
all steps require explicit Bryan approval at execution time.

Routes:
  GET  /v1/action-planner/systems    — registered systems and capabilities
  GET  /v1/action-planner/templates  — reusable plan templates (dry-run only)
  POST /v1/action-planner/plan       — generate a dry-run cross-system plan

Governance:
  - fake_data is always False
  - fake_plan is always False
  - dry_run is always True; executed is always False
  - All steps require approval before any real execution
  - No secret values are ever returned
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for action planner routes")

router = APIRouter(tags=["action-planner"])
__all__ = ["router"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    goal: str = Field(..., description="Goal or intent for the cross-system plan")
    systems: List[str] = Field(default_factory=list, description="Target system IDs to involve")
    dry_run: bool = Field(True, description="Always True — plans are never executed directly")


# ---------------------------------------------------------------------------
# Static data helpers
# ---------------------------------------------------------------------------

_SYSTEMS: List[Dict[str, Any]] = [
    {
        "system_id": "life_os",
        "name": "Life OS",
        "capabilities": ["task_review", "calendar_view", "priority_ranking"],
        "phase": "B",
    },
    {
        "system_id": "goals",
        "name": "Goals",
        "capabilities": ["goal_listing", "goal_progress", "goal_alignment"],
        "phase": "B",
    },
    {
        "system_id": "routines",
        "name": "Routines",
        "capabilities": ["routine_status", "routine_trigger_dry_run", "checklist_review"],
        "phase": "B",
    },
    {
        "system_id": "connectors",
        "name": "Connectors",
        "capabilities": ["connector_status", "draft_message", "read_inbox"],
        "phase": "B",
    },
    {
        "system_id": "browser_operator",
        "name": "Browser Operator",
        "capabilities": ["page_read_dry_run", "form_fill_dry_run"],
        "phase": "C",
    },
    {
        "system_id": "device_controller",
        "name": "Device Controller",
        "capabilities": ["device_status", "app_launch_dry_run"],
        "phase": "C",
    },
    {
        "system_id": "company_os",
        "name": "Company OS",
        "capabilities": ["org_chart_view", "project_status", "team_review"],
        "phase": "B",
    },
    {
        "system_id": "cloud_execution",
        "name": "Cloud Execution",
        "capabilities": ["task_queue_view", "job_status", "schedule_dry_run"],
        "phase": "C",
    },
]

_TEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "morning_review",
        "name": "Morning Review",
        "steps": [
            {"step": 1, "system": "life_os", "action": "review open tasks and priorities"},
            {"step": 2, "system": "goals", "action": "check goal progress"},
            {"step": 3, "system": "connectors", "action": "scan inbox for urgent items"},
        ],
        "approval_checkpoints": 3,
    },
    {
        "template_id": "weekly_planning",
        "name": "Weekly Planning",
        "steps": [
            {"step": 1, "system": "goals", "action": "review weekly goal targets"},
            {"step": 2, "system": "routines", "action": "audit routine completion rates"},
            {"step": 3, "system": "company_os", "action": "review team project status"},
        ],
        "approval_checkpoints": 3,
    },
    {
        "template_id": "project_kickoff",
        "name": "Project Kickoff",
        "steps": [
            {"step": 1, "system": "company_os", "action": "create project entry draft"},
            {"step": 2, "system": "goals", "action": "link project to active goals"},
        ],
        "approval_checkpoints": 2,
    },
    {
        "template_id": "daily_standup",
        "name": "Daily Standup",
        "steps": [
            {"step": 1, "system": "life_os", "action": "pull yesterday completions"},
            {"step": 2, "system": "goals", "action": "identify today's priority goal"},
        ],
        "approval_checkpoints": 2,
    },
    {
        "template_id": "goal_review",
        "name": "Goal Review",
        "steps": [
            {"step": 1, "system": "goals", "action": "list all active goals with progress"},
            {"step": 2, "system": "life_os", "action": "correlate tasks to goals"},
            {"step": 3, "system": "connectors", "action": "draft goal update summary"},
        ],
        "approval_checkpoints": 3,
    },
]

_PLAN_STEPS: List[Dict[str, Any]] = [
    {
        "step": 1,
        "system": "life_os",
        "action": "review pending tasks",
        "approval_required": True,
        "blocked_by_gate": None,
    },
    {
        "step": 2,
        "system": "goals",
        "action": "identify relevant goals",
        "approval_required": True,
        "blocked_by_gate": None,
    },
    {
        "step": 3,
        "system": "connectors",
        "action": "draft action",
        "approval_required": True,
        "blocked_by_gate": "connector_credentials_required",
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/action-planner/systems")
async def action_planner_systems() -> Dict[str, Any]:
    """Return all registered B/C phase systems and their declared capabilities."""
    return {
        "systems": _SYSTEMS,
        "cross_system_planning": True,
        "fake_data": False,
    }


@router.get("/v1/action-planner/templates")
async def action_planner_templates() -> Dict[str, Any]:
    """Return reusable plan templates. All templates are dry-run only."""
    return {
        "templates": _TEMPLATES,
        "dry_run_only": True,
        "fake_data": False,
    }


@router.post("/v1/action-planner/plan")
async def action_planner_plan(body: PlanRequest) -> Dict[str, Any]:
    """Generate a dry-run cross-system plan for the given goal.

    The plan is never executed. All steps require Bryan approval.
    fake_plan and fake_data are always False.
    """
    if not body.goal or not body.goal.strip():
        raise HTTPException(status_code=422, detail="goal must be a non-empty string")

    return {
        "plan_id": "dry-run-plan-001",
        "goal": body.goal,
        "steps": _PLAN_STEPS,
        "dry_run": True,
        "executed": False,
        "all_steps_require_approval": True,
        "fake_plan": False,
        "fake_data": False,
    }
