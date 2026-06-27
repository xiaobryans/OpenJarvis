"""Self-improvement log endpoint — GET /v1/improvement-log.

Feeds the Mission Control panel (weekly counts per category) and the recent
change-log list. Read-only; no secrets.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/v1/improvement-log")
async def improvement_log(limit: int = 20) -> dict:
    """Recent self-improvement entries + weekly counts per category."""
    from openjarvis.business.improvement_log import ImprovementLog

    log = ImprovementLog()
    return {
        "entries": log.recent(limit),
        "weekly_counts": log.weekly_counts(),
        "pending": log.pending(),
    }
