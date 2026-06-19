"""Runtime Recovery — last-known status, failed task record, safe resume guidance.

Provides:
  - RuntimeStatusRecord: last-known runtime health snapshot
  - FailedTaskRecord: structured record of a failed task (no raw CoT)
  - BlockerRecord: blocked action/capability record
  - RuntimeRecoveryStore: disk-backed store at ~/.jarvis/runtime_recovery.json
  - check_runtime_recovery(): doctor-style status check

Design rules:
  - No raw chain-of-thought in any record.
  - No automatic dangerous resume — safe resume guidance only.
  - No secret values stored.
  - Bounded retention: last 100 failed tasks.
  - Graceful degradation: disk unavailable → in-memory only.
  - Doctor-observable via check_runtime_recovery().
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_RECOVERY_FILE = Path.home() / ".jarvis" / "runtime_recovery.json"
_MAX_FAILED_TASKS = 100


# ---------------------------------------------------------------------------
# Data records
# ---------------------------------------------------------------------------

@dataclass
class RuntimeStatusRecord:
    """Last-known runtime health snapshot."""
    recorded_at: float
    status: str  # "healthy" | "degraded" | "failed" | "recovering"
    provider_status: str  # "available" | "BLOCKED_PROVIDER"
    active_projects: List[str]
    last_request_id: Optional[str]
    last_trace_id: Optional[str]
    uptime_note: str
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recorded_at": self.recorded_at,
            "status": self.status,
            "provider_status": self.provider_status,
            "active_projects": self.active_projects,
            "last_request_id": self.last_request_id,
            "last_trace_id": self.last_trace_id,
            "uptime_note": self.uptime_note,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeStatusRecord":
        return cls(
            recorded_at=d.get("recorded_at", 0.0),
            status=d.get("status", "unknown"),
            provider_status=d.get("provider_status", "unknown"),
            active_projects=d.get("active_projects", []),
            last_request_id=d.get("last_request_id"),
            last_trace_id=d.get("last_trace_id"),
            uptime_note=d.get("uptime_note", ""),
        )


@dataclass
class FailedTaskRecord:
    """Structured record of a failed task. No raw chain-of-thought."""
    record_id: str
    recorded_at: float
    request_id: str
    trace_id: Optional[str]
    intent: str
    project_id: Optional[str]
    failure_summary: str  # human-readable, no raw CoT
    blocker_type: Optional[str]
    blocker_detail: Optional[str]
    safe_resume_guidance: str
    resolved: bool = False
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "recorded_at": self.recorded_at,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "intent": self.intent,
            "project_id": self.project_id,
            "failure_summary": self.failure_summary,
            "blocker_type": self.blocker_type,
            "blocker_detail": self.blocker_detail,
            "safe_resume_guidance": self.safe_resume_guidance,
            "resolved": self.resolved,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FailedTaskRecord":
        return cls(
            record_id=d.get("record_id", uuid.uuid4().hex[:12]),
            recorded_at=d.get("recorded_at", 0.0),
            request_id=d.get("request_id", ""),
            trace_id=d.get("trace_id"),
            intent=d.get("intent", ""),
            project_id=d.get("project_id"),
            failure_summary=d.get("failure_summary", ""),
            blocker_type=d.get("blocker_type"),
            blocker_detail=d.get("blocker_detail"),
            safe_resume_guidance=d.get("safe_resume_guidance", ""),
            resolved=d.get("resolved", False),
        )


# ---------------------------------------------------------------------------
# RuntimeRecoveryStore
# ---------------------------------------------------------------------------

class RuntimeRecoveryStore:
    """Disk-backed store for runtime status snapshots and failed task records.

    Writes to ~/.jarvis/runtime_recovery.json. Graceful degradation if
    disk unavailable.
    """

    def __init__(self) -> None:
        self._status: Optional[RuntimeStatusRecord] = None
        self._failed_tasks: List[FailedTaskRecord] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not _RECOVERY_FILE.exists():
            return
        try:
            data = json.loads(_RECOVERY_FILE.read_text(encoding="utf-8"))
            if "last_status" in data and data["last_status"]:
                self._status = RuntimeStatusRecord.from_dict(data["last_status"])
            for ft in data.get("failed_tasks", []):
                self._failed_tasks.append(FailedTaskRecord.from_dict(ft))
        except Exception as exc:
            logger.warning("RuntimeRecoveryStore load failed (non-fatal): %s", exc)

    def _save(self) -> bool:
        try:
            _RECOVERY_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 1,
                "saved_at": time.time(),
                "last_status": self._status.to_dict() if self._status else None,
                "failed_tasks": [ft.to_dict() for ft in self._failed_tasks[-_MAX_FAILED_TASKS:]],
            }
            tmp = _RECOVERY_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(_RECOVERY_FILE)
            return True
        except Exception as exc:
            logger.debug("RuntimeRecoveryStore save failed (non-fatal): %s", exc)
            return False

    def record_status(
        self,
        status: str,
        provider_status: str,
        active_projects: List[str],
        last_request_id: Optional[str] = None,
        last_trace_id: Optional[str] = None,
        uptime_note: str = "",
    ) -> RuntimeStatusRecord:
        """Record the current runtime status snapshot."""
        self._ensure_loaded()
        record = RuntimeStatusRecord(
            recorded_at=time.time(),
            status=status,
            provider_status=provider_status,
            active_projects=active_projects,
            last_request_id=last_request_id,
            last_trace_id=last_trace_id,
            uptime_note=uptime_note,
        )
        self._status = record
        self._save()
        return record

    def record_failed_task(
        self,
        request_id: str,
        intent: str,
        failure_summary: str,
        trace_id: Optional[str] = None,
        project_id: Optional[str] = None,
        blocker_type: Optional[str] = None,
        blocker_detail: Optional[str] = None,
        safe_resume_guidance: str = "Re-run with corrected inputs; check doctor output first.",
    ) -> FailedTaskRecord:
        """Record a failed task. No raw CoT stored."""
        self._ensure_loaded()
        record = FailedTaskRecord(
            record_id=uuid.uuid4().hex[:12],
            recorded_at=time.time(),
            request_id=request_id,
            trace_id=trace_id,
            intent=intent,
            project_id=project_id,
            failure_summary=failure_summary,
            blocker_type=blocker_type,
            blocker_detail=blocker_detail,
            safe_resume_guidance=safe_resume_guidance,
        )
        self._failed_tasks.append(record)
        # Trim to max
        if len(self._failed_tasks) > _MAX_FAILED_TASKS:
            self._failed_tasks = self._failed_tasks[-_MAX_FAILED_TASKS:]
        self._save()
        return record

    def get_last_status(self) -> Optional[RuntimeStatusRecord]:
        self._ensure_loaded()
        return self._status

    def get_unresolved_failures(self) -> List[FailedTaskRecord]:
        self._ensure_loaded()
        return [ft for ft in self._failed_tasks if not ft.resolved]

    def resolve_failure(self, record_id: str) -> bool:
        self._ensure_loaded()
        for ft in self._failed_tasks:
            if ft.record_id == record_id:
                ft.resolved = True
                self._save()
                return True
        return False

    def get_recovery_status(self) -> Dict[str, Any]:
        """Return structured recovery status for doctor/status checks."""
        self._ensure_loaded()
        unresolved = self.get_unresolved_failures()
        status = self._status
        return {
            "file_path": str(_RECOVERY_FILE),
            "file_exists": _RECOVERY_FILE.exists(),
            "last_status": status.to_dict() if status else None,
            "unresolved_failure_count": len(unresolved),
            "total_failed_tasks": len(self._failed_tasks),
            "recent_failures": [
                {
                    "record_id": ft.record_id,
                    "intent": ft.intent,
                    "failure_summary": ft.failure_summary,
                    "blocker_type": ft.blocker_type,
                    "safe_resume_guidance": ft.safe_resume_guidance,
                }
                for ft in unresolved[-5:]
            ],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[RuntimeRecoveryStore] = None


def get_recovery_store() -> RuntimeRecoveryStore:
    global _store
    if _store is None:
        _store = RuntimeRecoveryStore()
    return _store


__all__ = [
    "RuntimeStatusRecord",
    "FailedTaskRecord",
    "RuntimeRecoveryStore",
    "get_recovery_store",
]
