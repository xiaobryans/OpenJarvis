"""Scale control routes — Phase C7.

Reports on control plane status, MacBook-off readiness, queue state, and
platform parity gaps. cloud_execution_live and fake_cloud_readiness are
always False unless proven by external deployment.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(tags=["scale-control"])
__all__ = ["router"]

logger = logging.getLogger(__name__)


@router.get("/v1/scale-control/status")
async def scale_status() -> Dict[str, Any]:
    """Return current control plane and device readiness status."""
    return {
        "control_plane_available": True,
        "device_readiness": {
            "desktop_local": "active",
            "mobile_pwa": "not_deployed",
            "cloud_fargate": "not_deployed",
        },
        "cloud_execution_live": False,
        "workbench_scale_live": False,
        "queue_execution_live": False,
        "approval_gates_active": True,
        "fake_cloud_readiness": False,
        "fake_data": False,
        "note": (
            "Scale control. Desktop active. "
            "Mobile PWA and Fargate require external deployment."
        ),
    }


@router.get("/v1/scale-control/macbook-off-readiness")
async def macbook_off_readiness() -> Dict[str, Any]:
    """Return MacBook-off readiness checklist.

    macbook_off_live is always False until Fargate deployment is proven.
    """
    requirements: List[Dict[str, Any]] = [
        {
            "req": "Fargate/ECS deployment",
            "met": False,
            "gate": "Requires AWS deployment",
        },
        {
            "req": "Tailscale VPN node",
            "met": False,
            "gate": "Requires Tailscale configuration",
        },
        {
            "req": "Cloud API key routing",
            "met": False,
            "gate": "Requires cloud key vault",
        },
        {
            "req": "Always-on backend",
            "met": False,
            "gate": "Requires Fargate deployment",
        },
    ]
    requirements_met = sum(1 for r in requirements if r["met"])

    return {
        "macbook_off_live": False,
        "requirements": requirements,
        "requirements_met": requirements_met,
        "requirements_total": len(requirements),
        "fake_cloud_readiness": False,
        "fake_data": False,
        "note": (
            "MacBook-off readiness. All requirements require external deployment "
            "(Fargate + Tailscale)."
        ),
    }


@router.get("/v1/scale-control/queue-status")
async def queue_status() -> Dict[str, Any]:
    """Return pending life_os task and approval queue counts.

    Reads from live stores where available; falls back to 0 on any error.
    """
    pending_tasks = 0
    pending_approvals = 0
    source = "unavailable"

    try:
        from openjarvis.tools.approval_store import ApprovalStore  # type: ignore[import]

        store = ApprovalStore()
        pending = store.list_pending()
        pending_approvals = len(pending) if isinstance(pending, list) else 0
        source = "/v1/life-os/tasks or unavailable"
    except Exception:
        pass

    try:
        from openjarvis.orchestrator.goals import get_goal_registry  # type: ignore[import]

        registry = get_goal_registry()
        goals = registry.list_all(status="active")
        pending_tasks = len(goals) if isinstance(goals, list) else 0
        source = "/v1/life-os/tasks"
    except Exception:
        pass

    return {
        "pending_tasks": pending_tasks,
        "pending_approvals": pending_approvals,
        "remote_execution_live": False,
        "auto_dispatch_live": False,
        "approval_required_for_dispatch": True,
        "fake_data": False,
        "source": source,
    }


@router.get("/v1/scale-control/parity-status")
async def parity_status() -> Dict[str, Any]:
    """Return desktop/mobile parity status and known gaps."""
    return {
        "desktop_status": "active",
        "mobile_pwa_status": "not_deployed",
        "parity_achieved": False,
        "parity_gaps": [
            {
                "gap": "Push notifications",
                "desktop": False,
                "mobile": False,
                "gate": "Requires OS notification permission + PWA",
            },
            {
                "gap": "Offline mode",
                "desktop": False,
                "mobile": False,
                "gate": "Service worker partial",
            },
            {
                "gap": "Real-time sync",
                "desktop": False,
                "mobile": False,
                "gate": "Requires WebSocket + cloud node",
            },
        ],
        "fake_parity": False,
        "fake_data": False,
    }
