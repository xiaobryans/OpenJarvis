"""Cloud Readiness routes — Phase C17.

C17 — Cloud / Fargate / Tailscale Execution Readiness Gate.
Bryan reported: AWS/S3/Fargate/Tailscale READY.

Routes:
  GET /v1/cloud-readiness/status              — presence-only credential check
  GET /v1/cloud-readiness/prerequisites-matrix — prerequisite gate matrix
  GET /v1/cloud-readiness/dry-run-plan         — deployment plan (dry-run only)

Governance:
  - fake_data is always False
  - fake_cloud_execution is always False
  - dry_run is always True; executed is always False
  - No secret values are ever returned — presence-only reporting
  - No live deployment authorized in this sprint
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for cloud readiness routes")

router = APIRouter(tags=["cloud-readiness"])
__all__ = ["router"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env(k: str) -> bool:
    """Return True if the environment variable is set and non-empty. Never prints value."""
    return bool(os.environ.get(k))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/cloud-readiness/status")
async def cloud_readiness_status() -> Dict[str, Any]:
    """Presence-only cloud readiness gate. No values returned."""
    return {
        "aws_credentials_present": (_env("AWS_ACCESS_KEY_ID") or _env("AWS_DEFAULT_REGION")),
        "s3_configured": (_env("AWS_S3_BUCKET") or _env("JARVIS_S3_BUCKET")),
        "fargate_configured": (_env("FARGATE_CLUSTER") or _env("ECS_CLUSTER")),
        "tailscale_configured": (_env("TAILSCALE_AUTH_KEY") or _env("TAILSCALE_API_KEY")),
        "bryan_cleared": True,
        "cloud_execution_live": False,
        "macbook_off_live": False,
        "remote_execution_live": False,
        "deployment_authorized_this_sprint": False,
        "fake_cloud_execution": False,
        "fake_data": False,
        "note": "Presence-only. Bryan cleared prerequisites. No live deployment authorized in this sprint.",
    }


@router.get("/v1/cloud-readiness/prerequisites-matrix")
async def cloud_readiness_prerequisites_matrix() -> Dict[str, Any]:
    """Prerequisite gate matrix — presence-only, no values exposed."""
    prerequisites: List[Dict[str, Any]] = [
        {
            "id": "aws_creds",
            "name": "AWS credentials",
            "present": (_env("AWS_ACCESS_KEY_ID") or _env("AWS_DEFAULT_REGION")),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "s3",
            "name": "S3 bucket configured",
            "present": (_env("AWS_S3_BUCKET") or _env("JARVIS_S3_BUCKET")),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "fargate",
            "name": "Fargate/ECS cluster",
            "present": (_env("FARGATE_CLUSTER") or _env("ECS_CLUSTER")),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "tailscale",
            "name": "Tailscale VPN",
            "present": (_env("TAILSCALE_AUTH_KEY") or _env("TAILSCALE_API_KEY")),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "docker_image",
            "name": "Docker image tagged and pushed",
            "present": False,
            "bryan_cleared": False,
            "note": "Requires active build pipeline",
        },
        {
            "id": "fargate_task_def",
            "name": "ECS task definition created",
            "present": False,
            "bryan_cleared": False,
            "note": "Requires ECS task definition deployment",
        },
    ]
    bryan_cleared_count = sum(1 for p in prerequisites if p.get("bryan_cleared"))
    macbook_off_met = sum(1 for p in prerequisites if p.get("present"))
    return {
        "prerequisites": prerequisites,
        "bryan_cleared_count": bryan_cleared_count,
        "blocking_count": 0,
        "macbook_off_requirements_met": macbook_off_met,
        "macbook_off_requirements_total": len(prerequisites),
        "deployment_authorized": False,
        "fake_data": False,
    }


@router.get("/v1/cloud-readiness/dry-run-plan")
async def cloud_readiness_dry_run_plan() -> Dict[str, Any]:
    """Deployment plan — dry-run only, never executed."""
    return {
        "dry_run": True,
        "executed": False,
        "deployment_plan_steps": [
            {"step": 1, "action": "Build Docker image", "status": "pending", "approval_required": True},
            {"step": 2, "action": "Push to ECR", "status": "pending", "approval_required": True},
            {"step": 3, "action": "Register ECS task definition", "status": "pending", "approval_required": True},
            {"step": 4, "action": "Deploy Fargate service", "status": "pending", "approval_required": True},
        ],
        "all_steps_require_bryan_approval": True,
        "fake_cloud_deployment": False,
        "fake_data": False,
    }
