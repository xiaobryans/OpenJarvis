"""Doctor and readiness REST routes — Ultra Sprint 7.

Routes:
  GET /v1/doctor?project_id=omnix          — run all 12 diagnostic checks
  GET /v1/doctor/project?project_id=omnix  — project-specific checks only
  GET /v1/readiness?project_id=omnix       — readiness gate evaluation
  GET /v1/readiness/report?project_id=omnix — full V1 evidence summary

Governance:
  - No secrets in any response
  - No real outbound sends
  - No auto-fix
  - Honest status: no fake green if backend unreachable
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for doctor routes")

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/v1/doctor")
async def run_doctor(project_id: str = "omnix") -> Dict[str, Any]:
    """Run all 12 Jarvis diagnostic checks for a project.

    Returns pass/warn/fail/not_configured for each check with evidence.
    Never returns fake green status.
    """
    from openjarvis.doctor.checks import run_all_checks

    results = run_all_checks(project_id=project_id)
    by_status: Dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "project_id": project_id,
        "total_checks": len(results),
        "by_status": by_status,
        "checks": [r.to_dict() for r in results],
    }


@router.get("/v1/doctor/project")
async def run_doctor_project(project_id: str = "omnix") -> Dict[str, Any]:
    """Run project-specific diagnostic checks.

    Checks: project registry, git status, handoff freshness,
    packaged app metadata.
    """
    from openjarvis.doctor.checks import (
        check_git_worktree_status,
        check_handoff_freshness,
        check_packaged_app_build_metadata,
        check_project_registry_health,
    )

    checks = [
        check_project_registry_health(project_id),
        check_git_worktree_status(project_id),
        check_handoff_freshness(project_id),
        check_packaged_app_build_metadata(project_id),
    ]
    by_status: Dict[str, int] = {}
    for r in checks:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "project_id": project_id,
        "total_checks": len(checks),
        "by_status": by_status,
        "checks": [r.to_dict() for r in checks],
    }


@router.get("/v1/readiness")
async def evaluate_readiness(project_id: str = "omnix") -> Dict[str, Any]:
    """Evaluate Jarvis V1 daily-driver readiness gate for a project.

    8 categories, 4 verdicts: ready / warn / hold / unsafe.
    Never self-accepts without evidence.
    UNSAFE if safety/governance check fails.
    HOLD if required evidence is missing.
    """
    from openjarvis.doctor.readiness import evaluate_readiness as _eval

    report = _eval(project_id=project_id)
    return report.to_dict()


@router.get("/v1/readiness/report")
async def readiness_report(project_id: str = "omnix") -> Dict[str, Any]:
    """Generate full V1 readiness evidence summary.

    Includes: tool/skill/watchdog counts, accepted checkpoints,
    unsafe actions blocked, remaining limitations, post-V1 roadmap.
    """
    from openjarvis.doctor.readiness import generate_v1_report

    return generate_v1_report(project_id=project_id)


__all__ = ["router"]
