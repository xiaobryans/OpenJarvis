"""Memory OS Governance — forget, edit, and export controls.

Implemented in Sprint 1 (real):
  - forget(entry_id)          Hard-delete a raw memory entry
  - forget_distilled(id)      Hard-delete a distilled entry
  - edit(entry_id, ...)       Update content/status/confidence of raw entry
  - export_namespace(...)     Export raw entries as JSON-able list
  - export_all()              Full export of all raw + distilled entries

Planned, NOT implemented in Sprint 1 (honest placeholders):
  - audit_trail               Full immutable audit log of all governance actions
  - approval_workflow         Require approval before deleting entries above
                              a confidence threshold
  - bulk_forget               Batch delete by namespace/project/kind
  - expiry_enforcement        Automatic hard-delete of expired entries on schedule
  - cross_device_sync         Sync governance actions to cloud/other devices

These placeholders are tracked with NOT_IMPLEMENTED status.  They must not be
claimed as complete.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.memory.store import JarvisMemory, MemoryEntry
from openjarvis.memory.distilled import DistilledMemory, DistilledEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Planned-not-complete registry
# ---------------------------------------------------------------------------

NOT_IMPLEMENTED_GOVERNANCE_CONTROLS = [
    {
        "control": "audit_trail",
        "status": "NOT_IMPLEMENTED",
        "sprint": "planned_future",
        "description": (
            "Immutable append-only audit log of all forget/edit/export actions. "
            "Required for compliance; not yet built."
        ),
    },
    {
        "control": "approval_workflow",
        "status": "NOT_IMPLEMENTED",
        "sprint": "planned_future",
        "description": (
            "Require explicit owner approval before hard-deleting entries with "
            "confidence >= 0.9 or kind='decision'. Not yet built."
        ),
    },
    {
        "control": "bulk_forget",
        "status": "NOT_IMPLEMENTED",
        "sprint": "planned_future",
        "description": (
            "Batch delete all entries in a namespace/project/kind with a single "
            "operation. Not yet built."
        ),
    },
    {
        "control": "expiry_enforcement",
        "status": "NOT_IMPLEMENTED",
        "sprint": "planned_future",
        "description": (
            "Scheduled task that hard-deletes entries past their expires_at "
            "timestamp. Not yet built."
        ),
    },
    {
        "control": "cross_device_sync",
        "status": "NOT_IMPLEMENTED",
        "sprint": "planned_future",
        "description": (
            "Propagate governance actions (forget/edit) to cloud and other "
            "devices. Requires cloud sync sprint."
        ),
    },
]


@dataclass
class GovernanceResult:
    """Result of a governance action."""
    action: str
    entry_id: str
    success: bool
    detail: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "entry_id": self.entry_id,
            "success": self.success,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class MemoryGovernance:
    """Governance controls for JarvisMemory and DistilledMemory.

    Note: audit trail, approval workflow, and expiry enforcement are NOT
    implemented in Sprint 1.  See NOT_IMPLEMENTED_GOVERNANCE_CONTROLS.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory: Optional[JarvisMemory] = None,
        distilled: Optional[DistilledMemory] = None,
    ) -> None:
        db = Path(db_path) if db_path else None
        self._memory = memory or JarvisMemory(db_path=db)
        self._distilled = distilled or DistilledMemory(
            db_path=db or self._memory._db_path
        )

    def forget(self, entry_id: str) -> GovernanceResult:
        """Hard-delete a raw memory entry.

        NOTE: audit trail NOT implemented in Sprint 1.
        High-confidence entries are deleted without approval — approval
        workflow is planned but not built.
        """
        existing = self._memory.get(entry_id)
        if existing is None:
            return GovernanceResult(
                action="forget",
                entry_id=entry_id,
                success=False,
                detail=f"entry_id={entry_id!r} not found in raw memory",
            )
        deleted = self._memory.delete(entry_id)
        logger.info(
            "Governance.forget: entry_id=%s kind=%s confidence=%.2f deleted=%s",
            entry_id, existing.kind, existing.confidence, deleted,
        )
        return GovernanceResult(
            action="forget",
            entry_id=entry_id,
            success=deleted,
            detail=(
                f"deleted raw entry kind={existing.kind!r} "
                f"confidence={existing.confidence:.2f} "
                f"[audit_trail=NOT_IMPLEMENTED]"
            ),
        )

    def forget_distilled(self, entry_id: str) -> GovernanceResult:
        """Hard-delete a distilled memory entry."""
        existing = self._distilled.get(entry_id)
        if existing is None:
            return GovernanceResult(
                action="forget_distilled",
                entry_id=entry_id,
                success=False,
                detail=f"entry_id={entry_id!r} not found in distilled memory",
            )
        deleted = self._distilled.delete(entry_id)
        return GovernanceResult(
            action="forget_distilled",
            entry_id=entry_id,
            success=deleted,
            detail=(
                f"deleted distilled entry kind={existing.kind!r} "
                f"[audit_trail=NOT_IMPLEMENTED]"
            ),
        )

    def edit(
        self,
        entry_id: str,
        *,
        new_content: Optional[str] = None,
        new_status: Optional[str] = None,
        new_confidence: Optional[float] = None,
    ) -> GovernanceResult:
        """Edit a raw memory entry.

        NOTE: audit trail NOT implemented in Sprint 1.
        """
        updated = self._memory.update(
            entry_id,
            content=new_content,
            status=new_status,
            confidence=new_confidence,
        )
        if updated is None:
            return GovernanceResult(
                action="edit",
                entry_id=entry_id,
                success=False,
                detail=f"entry_id={entry_id!r} not found",
            )
        return GovernanceResult(
            action="edit",
            entry_id=entry_id,
            success=True,
            detail=(
                f"updated: content_changed={new_content is not None} "
                f"status={updated.status!r} confidence={updated.confidence:.2f} "
                f"[audit_trail=NOT_IMPLEMENTED]"
            ),
        )

    def export_namespace(
        self,
        namespace: str,
        *,
        project_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Export all raw memory entries in a namespace as a list of dicts."""
        entries = self._memory.list_by_namespace(
            namespace, project_id=project_id, limit=limit
        )
        return [e.to_dict() for e in entries]

    def export_all(self) -> Dict[str, Any]:
        """Full export of all raw + distilled entries.

        Returns a dict with 'raw' and 'distilled' lists.
        Use for backup or migration.
        """
        namespaces = self._memory.list_namespaces()
        raw: List[Dict[str, Any]] = []
        for ns in namespaces:
            entries = self._memory.list_by_namespace(
                ns["namespace"],
                project_id=ns["project_id"] or None,
                limit=10000,
            )
            raw.extend(e.to_dict() for e in entries)

        distilled: List[Dict[str, Any]] = []
        for kind in ("summary", "decision", "pattern", "preference", "lesson"):
            entries_d = self._distilled.list_by_kind(kind, limit=10000)
            distilled.extend(e.to_dict() for e in entries_d)

        return {
            "raw_count": len(raw),
            "distilled_count": len(distilled),
            "raw": raw,
            "distilled": distilled,
            "not_implemented_controls": NOT_IMPLEMENTED_GOVERNANCE_CONTROLS,
        }

    @staticmethod
    def governance_status() -> Dict[str, Any]:
        """Return honest governance status including NOT_IMPLEMENTED controls."""
        return {
            "sprint": "plan4_sprint1_memory_os_foundation",
            "implemented": ["forget", "forget_distilled", "edit", "export_namespace", "export_all"],
            "not_implemented": NOT_IMPLEMENTED_GOVERNANCE_CONTROLS,
        }


__all__ = [
    "GovernanceResult",
    "MemoryGovernance",
    "NOT_IMPLEMENTED_GOVERNANCE_CONTROLS",
]
