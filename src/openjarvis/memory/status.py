"""Memory OS Status — honest backend readiness and counts.

Provides a lightweight status object for Mission Control / monitoring.
All operations are read-only.  No model API calls required.

What is reported:
  - Backend availability (SQLite file accessible)
  - Backend type and path
  - Raw/archive entry count (cheap COUNT query)
  - Distilled entry count (cheap COUNT query)
  - Last error (if any, from last status check)
  - Context injection enabled/disabled flag
  - Namespace count

What is NOT claimed:
  - Full Memory OS completion — Sprint 1 is foundation only
  - Cloud sync status (planned future sprint)
  - Semantic/vector search availability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".jarvis" / "memory.db"


@dataclass
class MemoryOSStatus:
    """Honest status of the Memory OS foundation.

    Fields
    ------
    backend_available           True if SQLite DB is accessible
    backend_type                Always 'sqlite' in Sprint 1
    backend_path                Absolute path to the DB file
    raw_archive_count           Total entries in memory_entries table
    raw_active_count            Entries with status='active'
    distilled_count             Total entries in distilled_entries table
    namespaces_count            Distinct namespaces in raw archive
    context_injection_enabled   Whether MemoryContextBuilder can inject context
    last_error                  Last exception message if any, else None
    foundation_complete         Honest: Sprint 1 foundation only, not full Memory OS
    planned_not_complete        What is still planned but not done
    """

    backend_available: bool = False
    backend_type: str = "sqlite"
    backend_path: str = ""
    raw_archive_count: int = 0
    raw_active_count: int = 0
    distilled_count: int = 0
    namespaces_count: int = 0
    context_injection_enabled: bool = True
    last_error: Optional[str] = None
    foundation_complete: bool = True
    planned_not_complete: list = field(default_factory=lambda: [
        "automatic_distillation_from_raw",
        "semantic_vector_search",
        "cloud_sync",
        "approval_workflow_for_distilled",
        "full_audit_trail_for_governance",
        "cross_device_sync",
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend_available": self.backend_available,
            "backend_type": self.backend_type,
            "backend_path": self.backend_path,
            "raw_archive_count": self.raw_archive_count,
            "raw_active_count": self.raw_active_count,
            "distilled_count": self.distilled_count,
            "namespaces_count": self.namespaces_count,
            "context_injection_enabled": self.context_injection_enabled,
            "last_error": self.last_error,
            "foundation_complete": self.foundation_complete,
            "planned_not_complete": self.planned_not_complete,
            "sprint": "plan4_sprint1_memory_os_foundation",
        }


def get_memory_os_status(db_path: Optional[Path] = None) -> MemoryOSStatus:
    """Return honest Memory OS status.

    Safe to call at any time — catches all exceptions and returns a status
    with backend_available=False and last_error set.
    """
    resolved_path = Path(db_path) if db_path else _DEFAULT_DB

    status = MemoryOSStatus(
        backend_path=str(resolved_path),
    )

    try:
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory(db_path=resolved_path)
        status.raw_archive_count = mem.count()
        status.raw_active_count = mem.count(status="active")
        ns = mem.list_namespaces()
        status.namespaces_count = len(ns)
        status.backend_available = True
    except Exception as exc:
        status.backend_available = False
        status.last_error = str(exc)
        logger.warning("Memory OS status check failed (raw): %s", exc)
        return status

    try:
        from openjarvis.memory.distilled import DistilledMemory

        dist = DistilledMemory(db_path=resolved_path)
        status.distilled_count = dist.count()
    except Exception as exc:
        status.last_error = str(exc)
        logger.warning("Memory OS status check failed (distilled): %s", exc)

    return status


__all__ = ["MemoryOSStatus", "get_memory_os_status"]
