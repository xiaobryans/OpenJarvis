"""Plan 9 — Mac Worker Queue (Section 19).

The Mac worker is NOT the main parity path.
Mac worker handles ONLY irreducible Mac-only tasks:
  - Reinstalling /Applications/OpenJarvis.app
  - Controlling Mac apps / System Settings / Finder
  - Reading unsynced Mac-only files
  - Keychain-only credentials (until migrated)
  - Mac hardware / screen / audio tasks

Cloud-native parity handles ALL other tasks:
  - Coding, tests, commits, pushes
  - Backend/cloud deploys (with Bryan approval)
  - Memory, connectors
  - Safe files (allowlisted)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class MacTaskType(str, Enum):
    APP_REINSTALL = "app_reinstall"              # /Applications/OpenJarvis.app
    MAC_APP_CONTROL = "mac_app_control"          # Finder, System Settings, etc.
    UNSYNCED_FILE_READ = "unsynced_file_read"    # local-only unsynced files
    KEYCHAIN_CREDENTIAL = "keychain_credential"  # Keychain-only credentials
    MAC_HARDWARE = "mac_hardware"                # screen/audio/hardware tasks


class MacTaskStatus(str, Enum):
    QUEUED = "QUEUED"          # submitted; Mac offline
    PENDING_APPROVAL = "PENDING_APPROVAL"  # waiting for Bryan approval
    EXECUTING = "EXECUTING"    # Mac is online, executing
    COMPLETED = "COMPLETED"    # finished successfully
    FAILED = "FAILED"          # failed with error
    CANCELLED = "CANCELLED"    # cancelled by Bryan


@dataclass
class MacWorkerTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: MacTaskType = MacTaskType.APP_REINSTALL
    display_name: str = ""
    description: str = ""
    submitted_by: str = "bryan"
    submitted_from: str = "mobile"   # surface that submitted
    status: MacTaskStatus = MacTaskStatus.QUEUED
    requires_approval: bool = False
    approval_evidence: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "display_name": self.display_name,
            "description": self.description,
            "submitted_by": self.submitted_by,
            "submitted_from": self.submitted_from,
            "status": self.status.value,
            "requires_approval": self.requires_approval,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class MacWorkerQueue:
    """In-memory Mac worker queue.

    Stores tasks submitted from mobile for execution when MacBook comes online.
    Both mobile and MacBook surfaces can read queue status.

    In production, this would be backed by a durable store (S3, Supabase, etc.)
    to survive restarts. This implementation is the schema/contract.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, MacWorkerTask] = {}

    def submit(self, task: MacWorkerTask) -> str:
        """Submit a Mac-only task. Returns task_id."""
        task.status = MacTaskStatus.QUEUED
        task.updated_at = time.time()
        self._tasks[task.task_id] = task
        return task.task_id

    def get(self, task_id: str) -> Optional[MacWorkerTask]:
        return self._tasks.get(task_id)

    def list_pending(self) -> List[MacWorkerTask]:
        return [t for t in self._tasks.values() if t.status == MacTaskStatus.QUEUED]

    def list_all(self) -> List[MacWorkerTask]:
        return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    def mark_executing(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status == MacTaskStatus.QUEUED:
            task.status = MacTaskStatus.EXECUTING
            task.updated_at = time.time()
            return True
        return False

    def mark_completed(self, task_id: str, result: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status == MacTaskStatus.EXECUTING:
            task.status = MacTaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            task.updated_at = time.time()
            return True
        return False

    def mark_failed(self, task_id: str, error: str) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.status = MacTaskStatus.FAILED
            task.error = error
            task.updated_at = time.time()
            return True
        return False

    def status_summary(self) -> Dict:
        summary: Dict[str, int] = {}
        for task in self._tasks.values():
            summary[task.status.value] = summary.get(task.status.value, 0) + 1
        return {
            "total": len(self._tasks),
            "queued": summary.get("QUEUED", 0),
            "executing": summary.get("EXECUTING", 0),
            "completed": summary.get("COMPLETED", 0),
            "failed": summary.get("FAILED", 0),
        }

    def to_api_response(self) -> Dict:
        return {
            "queue_status": self.status_summary(),
            "tasks": [t.to_dict() for t in self.list_all()],
        }


# Singleton (scoped to process; production would use durable backend)
_MAC_QUEUE: Optional[MacWorkerQueue] = None


def get_mac_worker_queue() -> MacWorkerQueue:
    global _MAC_QUEUE
    if _MAC_QUEUE is None:
        _MAC_QUEUE = MacWorkerQueue()
    return _MAC_QUEUE


# ---------------------------------------------------------------------------
# Mac task type classifications
# ---------------------------------------------------------------------------

# These task types MUST use the Mac worker queue — not cloud-native paths
MAC_ONLY_TASK_TYPES: List[MacTaskType] = [
    MacTaskType.APP_REINSTALL,
    MacTaskType.MAC_APP_CONTROL,
    MacTaskType.UNSYNCED_FILE_READ,
    MacTaskType.KEYCHAIN_CREDENTIAL,
    MacTaskType.MAC_HARDWARE,
]

# These task types MUST use cloud-native paths — not Mac worker queue
CLOUD_NATIVE_TASK_TYPES = [
    "coding",
    "test_run",
    "commit",
    "push",
    "backend_deploy",
    "memory_read",
    "memory_write",
    "connector_read",
    "connector_write",
    "safe_file_read",
    "chat",
    "research",
]
