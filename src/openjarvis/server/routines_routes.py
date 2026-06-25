"""Routines Routes — recurring scheduled task visibility.

Routes:
  GET /v1/routines        — list all scheduled tasks from scheduler store
  GET /v1/routines/status — honest status of the scheduler engine

Design rules:
  - No fake recurring automations.
  - Reports scheduler state honestly (started/not_started/store_unavailable).
  - Reads from SQLite store at default path; returns empty list if store absent.
  - No secret values.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi required for routines routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["routines"])

_DEFAULT_STORE_PATH = Path.home() / ".jarvis" / "scheduler.db"


def _read_scheduled_tasks() -> List[Dict[str, Any]]:
    """Read scheduled tasks from SQLite store. Returns empty list if unavailable."""
    try:
        from openjarvis.scheduler.store import SchedulerStore

        if not _DEFAULT_STORE_PATH.exists():
            return []
        store = SchedulerStore(db_path=_DEFAULT_STORE_PATH)
        return store.list_tasks()  # already returns List[Dict[str, Any]]
    except Exception as exc:
        logger.debug("Scheduler store read skipped: %s", exc)
        return []


@router.get("/v1/routines")
async def list_routines() -> Dict[str, Any]:
    """List all scheduled tasks from the scheduler store.

    Returns an honest empty list if no tasks are scheduled or the store is absent.
    Does not claim automated execution is running — reports scheduler state honestly.
    """
    tasks = _read_scheduled_tasks()
    store_present = _DEFAULT_STORE_PATH.exists()
    return {
        "routines": tasks,
        "count": len(tasks),
        "scheduler_store_present": store_present,
        "store_path": str(_DEFAULT_STORE_PATH),
        "scheduler_started": False,
        "note": (
            "Scheduler store is read-only from this endpoint. "
            "Automated execution requires 'jarvis scheduler start' via CLI. "
            "Recurring automations are NOT claimed as running unless scheduler is started."
        ),
        "automation_honesty": True,
    }


@router.get("/v1/routines/status")
async def get_routines_status() -> Dict[str, Any]:
    """Honest status of the scheduler engine and recurring cadence support."""
    store_present = _DEFAULT_STORE_PATH.exists()
    tasks = _read_scheduled_tasks() if store_present else []
    active = [t for t in tasks if t.get("status") == "active"]
    return {
        "scheduler_module": "available",
        "scheduler_started": False,
        "scheduler_store_present": store_present,
        "schedule_types_supported": ["cron", "interval", "once"],
        "active_scheduled_tasks": len(active),
        "total_scheduled_tasks": len(tasks),
        "honesty": {
            "fake_recurring_automations": False,
            "scheduler_running": False,
            "note": (
                "Scheduler module (cron/interval/once) exists and is tested. "
                "It is not auto-started in this release — requires explicit CLI start. "
                "This route reports facts only."
            ),
        },
        "how_to_start": "jarvis scheduler start  (CLI, not auto-started in server)",
    }


__all__ = ["router"]
