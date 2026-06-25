"""Multi-Device Status REST Routes (B17).

Routes:
  GET /v1/multi-device/status             — overall multi-device session status
  GET /v1/multi-device/capability-matrix  — per-device capability matrix
  GET /v1/multi-device/workbench-queue    — life-os tasks eligible for workbench/cloud delegation

Design:
  - fake_data: False, fake_live: False in all responses
  - Desktop local session only; mobile PWA and cloud require external deployment gates
  - Workbench queue reads from /v1/life-os task store (graceful fallback on import failure)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for multi_device routes")

logger = logging.getLogger(__name__)
router = APIRouter(tags=["multi-device"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# GET /v1/multi-device/status
# ---------------------------------------------------------------------------


@router.get("/v1/multi-device/status")
async def multi_device_status() -> Dict[str, Any]:
    """Return current multi-device session status.

    Desktop local session is active. Mobile PWA and cloud execution require
    Tailscale + Fargate deployment (external gates — never claimed without proof).
    """
    return {
        "sessions": [
            {
                "session_id": "desktop_local",
                "device_type": "Desktop (macOS)",
                "status": "active",
                "capabilities": [
                    "chat",
                    "memory",
                    "rules",
                    "expert_roles",
                    "local_execution",
                ],
                "live": True,
                "gate": None,
            },
            {
                "session_id": "mobile_pwa",
                "device_type": "Mobile PWA",
                "status": "requires_deployment",
                "capabilities": ["chat", "memory"],
                "live": False,
                "gate": "Tailscale + Fargate deployment required",
            },
            {
                "session_id": "cloud_fargate",
                "device_type": "Cloud (Fargate)",
                "status": "requires_deployment",
                "capabilities": ["long_running_tasks", "connector_workflows"],
                "live": False,
                "gate": "Fargate stack deployment required",
            },
        ],
        "active_sessions": 1,
        "phone_control_live": False,
        "macbook_off_cloud_execution_live": False,
        "fargate_cloud_live": False,
        "pwa_installed": False,
        "fake_live": False,
        "fake_data": False,
        "note": (
            "Desktop active. Mobile PWA and cloud execution require "
            "Tailscale + Fargate deployment."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/multi-device/capability-matrix
# ---------------------------------------------------------------------------


@router.get("/v1/multi-device/capability-matrix")
async def capability_matrix() -> Dict[str, Any]:
    """Return per-device capability matrix with gate conditions for unavailable capabilities."""
    return {
        "devices": [
            {
                "device": "Desktop",
                "chat": True,
                "memory": True,
                "connectors": "partial",
                "cloud_execution": False,
            },
            {
                "device": "Mobile PWA",
                "chat": False,
                "memory": False,
                "connectors": False,
                "cloud_execution": False,
                "gate": "Tailscale required",
            },
            {
                "device": "Cloud Fargate",
                "chat": False,
                "memory": False,
                "connectors": False,
                "cloud_execution": False,
                "gate": "Fargate deployment required",
            },
        ],
        "fake_live": False,
        "fake_data": False,
        "note": "Capability matrix only. Desktop is the only live device.",
    }


# ---------------------------------------------------------------------------
# GET /v1/multi-device/workbench-queue
# ---------------------------------------------------------------------------

_WORKBENCH_TAGS = {"workbench", "cloud", "async", "batch"}


@router.get("/v1/multi-device/workbench-queue")
async def workbench_queue() -> Dict[str, Any]:
    """Return life-os tasks eligible for workbench/cloud delegation.

    Reads from the PersonalOS task store when available.
    Filters to tasks tagged workbench/cloud/async/batch or with approval_required=True.
    Gracefully degrades to empty list on import or runtime failure.
    """
    tasks: List[Dict[str, Any]] = []
    source = "/v1/life-os/tasks"

    try:
        from openjarvis.jarvis_os.personal_os import PersonalOS  # type: ignore

        os_instance = PersonalOS()
        all_tasks = os_instance.list_tasks()
        for task in all_tasks:
            tags = set(getattr(task, "tags", []) or [])
            approval_required = getattr(task, "approval_required", False)
            if tags & _WORKBENCH_TAGS or approval_required:
                tasks.append(
                    task.to_dict() if hasattr(task, "to_dict") else vars(task)
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench_queue: could not read life-os tasks: %s", exc)
        tasks = []

    return {
        "workbench_tasks": tasks,
        "count": len(tasks),
        "phone_control_available": False,
        "remote_execution_available": False,
        "fake_data": False,
        "source": source,
    }
