"""Unified delegation queue — aggregates approval-pending items from all sources.

Routes:
  GET /v1/delegation/queue          — aggregated pending-approval queue
  GET /v1/delegation/queue/summary  — count summary by source

Sources probed (each with graceful degradation):
  - life_os    : /v1/life-os/approvals/pending (PersonalTask awaiting approval)
  - agent_action: /v1/approvals/pending (PendingAction agent actions)
  - mission    : /v1/tasks/pending-approval (Mission Task awaiting approval)

Approve / reject actions always route through the existing per-source endpoints.
This route NEVER bypasses approval gates and NEVER weakens auth.
Payload fields (secrets, tokens, credential paths) are stripped from agent actions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["delegation"])

# ---------------------------------------------------------------------------
# Normalised delegation item shape
# ---------------------------------------------------------------------------

class DelegationItem(BaseModel):
    delegation_id: str
    source: str                          # life_os | agent_action | mission
    source_id: str
    title: str
    description: str
    status: str
    category: str                        # personal_task | agent_action | mission_task
    authority_tier: str
    approval_route: Optional[str]        # safe route path for approve
    reject_route: Optional[str]          # safe route path for reject (None if unsupported)
    created_at: Optional[Any]
    expires_at: Optional[Any]
    audit_id: str                        # original ID for provenance
    priority: Optional[str]
    risk_level: Optional[str]
    tags: List[str]
    extra: Dict[str, Any]               # source-specific non-secret metadata


# ---------------------------------------------------------------------------
# Probe helpers
# ---------------------------------------------------------------------------


def _probe_life_os() -> tuple[List[DelegationItem], Optional[str]]:
    """Probe life-os personal tasks awaiting approval."""
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store
        store = get_personal_task_store()
        tasks = store.pending_approvals()
        items: List[DelegationItem] = []
        for task in tasks:
            d = task.to_dict()
            task_id = d.get("task_id", "")
            items.append(DelegationItem(
                delegation_id=f"life_os:{task_id}",
                source="life_os",
                source_id=task_id,
                title=d.get("title", "Untitled task"),
                description=d.get("description", ""),
                status=d.get("status", "waiting_approval"),
                category="personal_task",
                authority_tier="tier_2",
                approval_route=f"/v1/life-os/tasks/{task_id}/approve",
                reject_route=None,
                created_at=d.get("created_at"),
                expires_at=None,
                audit_id=task_id,
                priority=d.get("priority", "medium"),
                risk_level=None,
                tags=d.get("tags", []),
                extra={
                    "approval_state": d.get("approval_state"),
                    "approval_required": d.get("approval_required"),
                    "due_at": d.get("due_at"),
                    "follow_up_state": d.get("follow_up_state"),
                },
            ))
        return items, None
    except Exception as exc:
        logger.debug("life_os delegation probe failed: %s", exc)
        return [], str(exc)


def _probe_agent_actions() -> tuple[List[DelegationItem], Optional[str]]:
    """Probe proactive-agent pending actions. Payload is stripped to prevent secret leakage."""
    try:
        from openjarvis.tools.approval_store import ApprovalStore
        store = ApprovalStore()
        store.expire_stale()
        actions = store.list_pending()
        items: List[DelegationItem] = []
        for a in actions:
            d = a.to_dict() if hasattr(a, "to_dict") else dict(a)
            action_id = d.get("id", "")
            items.append(DelegationItem(
                delegation_id=f"agent_action:{action_id}",
                source="agent_action",
                source_id=action_id,
                title=d.get("action_type", "Agent action"),
                description=d.get("description", ""),
                status=d.get("status", "pending"),
                category="agent_action",
                authority_tier=str(d.get("tier", "tier_2")),
                approval_route=f"/v1/approvals/{action_id}/approve",
                reject_route=f"/v1/approvals/{action_id}/deny",
                created_at=d.get("created_at"),
                expires_at=d.get("expires_at"),
                audit_id=action_id,
                priority="medium",
                risk_level=None,
                tags=[],
                extra={
                    "permission_key": d.get("permission_key"),
                    # payload intentionally excluded — may contain sensitive data
                    "payload_present": bool(d.get("payload")),
                    "notification_sent": bool(d.get("notification_sent")),
                },
            ))
        return items, None
    except Exception as exc:
        logger.debug("agent_action delegation probe failed: %s", exc)
        return [], str(exc)


def _probe_mission_tasks() -> tuple[List[DelegationItem], Optional[str]]:
    """Probe mission tasks awaiting approval."""
    try:
        from openjarvis.mission.store import MissionStore
        from openjarvis.mission.models import TaskStatus
        store = MissionStore()
        tasks = store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
        items: List[DelegationItem] = []
        for task in tasks:
            d = task.to_dict() if hasattr(task, "to_dict") else dict(task)
            task_id = d.get("id", "")
            items.append(DelegationItem(
                delegation_id=f"mission:{task_id}",
                source="mission",
                source_id=task_id,
                title=d.get("title", task_id),
                description=d.get("description", ""),
                status=d.get("status", "awaiting_approval"),
                category="mission_task",
                authority_tier="tier_3",
                approval_route=f"/v1/tasks/{task_id}/approve",
                reject_route=f"/v1/tasks/{task_id}/deny",
                created_at=d.get("created_at"),
                expires_at=None,
                audit_id=task_id,
                priority=str(d.get("priority", 5)),
                risk_level=d.get("risk_level"),
                tags=[],
                extra={
                    "mission_id": d.get("mission_id"),
                    "assigned_agent_id": d.get("assigned_agent_id"),
                    "summary": d.get("summary"),
                },
            ))
        return items, None
    except Exception as exc:
        logger.debug("mission delegation probe failed: %s", exc)
        return [], str(exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/delegation/queue")
async def get_delegation_queue() -> Dict[str, Any]:
    """Return all pending-approval items from all delegation sources.

    Each item includes approval_route and reject_route (where available)
    so the caller can submit approve/reject to the appropriate existing
    endpoint. This route itself does NOT approve or reject anything.
    Payload fields that may contain sensitive data are not surfaced.
    """
    life_items, life_err = _probe_life_os()
    action_items, action_err = _probe_agent_actions()
    mission_items, mission_err = _probe_mission_tasks()

    all_items = life_items + action_items + mission_items
    # Sort by created_at ascending (oldest first); None sorts last
    all_items.sort(key=lambda i: (i.created_at is None, i.created_at or 0))

    errors: List[Dict[str, str]] = []
    if life_err:
        errors.append({"source": "life_os", "error": life_err})
    if action_err:
        errors.append({"source": "agent_action", "error": action_err})
    if mission_err:
        errors.append({"source": "mission", "error": mission_err})

    return {
        "items": [i.model_dump() for i in all_items],
        "count": len(all_items),
        "by_source": {
            "life_os": len(life_items),
            "agent_action": len(action_items),
            "mission": len(mission_items),
        },
        "errors": errors,
        "sources_probed": ["life_os", "agent_action", "mission"],
        "note": (
            "Approve/reject via the approval_route / reject_route on each item. "
            "This endpoint is read-only — approval gates are enforced at the source routes."
        ),
    }


@router.get("/v1/delegation/queue/summary")
async def get_delegation_summary() -> Dict[str, Any]:
    """Return count summary of pending-approval items by source."""
    life_items, _ = _probe_life_os()
    action_items, _ = _probe_agent_actions()
    mission_items, _ = _probe_mission_tasks()
    total = len(life_items) + len(action_items) + len(mission_items)
    return {
        "total": total,
        "by_source": {
            "life_os": len(life_items),
            "agent_action": len(action_items),
            "mission": len(mission_items),
        },
        "has_pending": total > 0,
    }


__all__ = ["router"]
