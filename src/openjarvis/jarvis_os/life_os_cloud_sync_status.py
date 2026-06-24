"""Life-OS cloud sync status — B7 layer tracking.

Tracks five layers of Life-OS data sync readiness without performing live
cloud calls or reading secret values.

Layers (in order):
  1. local_store_type    — what storage backend is in use (in_memory / sqlite)
  2. s3_configured       — S3 bucket env vars present (presence-only)
  3. sync_code_present   — cloud_sync module importable
  4. sync_executed       — sync has actually run (False — requires Fargate)
  5. worker_access       — cloud worker can read/write store (False — requires Fargate)

Hard rules:
- No live S3 calls.
- No secret values read, stored, or returned.
- sync_executed and worker_access are always False without live Fargate proof.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

# Layer status constants (matches workspace_sync_status convention)
LAYER_OK = "ok"
LAYER_MISSING = "missing"
LAYER_NOT_CONFIGURED = "not_configured"
LAYER_REQUIRES_DEPLOYMENT = "requires_deployment"
LAYER_UNKNOWN = "unknown"

# Store type constants
STORE_LOCAL_MEMORY = "in_memory"
STORE_LOCAL_SQLITE = "sqlite"
STORE_CLOUD = "cloud"

# Overall status constants
STATUS_LOCAL_ONLY = "LOCAL_ONLY"
STATUS_SQLITE_LOCAL = "SQLITE_LOCAL"
STATUS_CONFIGURED_NOT_SYNCED = "CONFIGURED_NOT_SYNCED"
STATUS_REQUIRES_DEPLOYMENT = "REQUIRES_DEPLOYMENT"
STATUS_READY = "READY"


@dataclass
class LifeOSCloudSyncStatus:
    """Honest multi-layer Life-OS data sync status."""

    local_store_type: str       # in_memory / sqlite
    s3_configured: str          # LAYER_OK / LAYER_NOT_CONFIGURED
    sync_code_present: str      # LAYER_OK / LAYER_MISSING
    sync_executed: str          # always LAYER_REQUIRES_DEPLOYMENT
    worker_access: str          # always LAYER_REQUIRES_DEPLOYMENT

    local_task_count: int       # tasks in local store (count only)
    status: str                 # STATUS_* constant
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_store_type": self.local_store_type,
            "s3_configured": self.s3_configured,
            "sync_code_present": self.sync_code_present,
            "sync_executed": self.sync_executed,
            "worker_access": self.worker_access,
            "local_task_count": self.local_task_count,
            "status": self.status,
            "detail": self.detail,
        }


def get_life_os_cloud_sync_status() -> LifeOSCloudSyncStatus:
    """Return an honest multi-layer Life-OS cloud sync status.

    No live network calls. No secret values. Presence-only env var checks.
    sync_executed and worker_access are always LAYER_REQUIRES_DEPLOYMENT.
    """
    # Layer 1: determine store type
    local_store_type = STORE_LOCAL_MEMORY
    local_task_count = 0
    try:
        from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore, STORE_TYPE_SQLITE
        store = SQLitePersonalTaskStore()
        if store.db_exists():
            local_store_type = STORE_LOCAL_SQLITE
            local_task_count = store.task_count()
        else:
            local_store_type = STORE_LOCAL_SQLITE  # SQLite module present; DB not yet created
    except Exception:
        local_store_type = STORE_LOCAL_MEMORY

    # Layer 2: S3 configured (presence-only)
    memory_bucket_ok = bool(os.environ.get("OMNIX_WORKBENCH_MEMORY_BUCKET", "").strip())
    artifact_bucket_ok = bool(os.environ.get("OMNIX_WORKBENCH_ARTIFACT_BUCKET", "").strip())
    region_ok = bool(os.environ.get("OMNIX_WORKBENCH_AWS_REGION", "").strip())
    provider_aws = os.environ.get("OMNIX_WORKBENCH_STORAGE_PROVIDER", "").strip() == "aws"
    s3_configured = (
        LAYER_OK
        if (memory_bucket_ok and region_ok and provider_aws)
        else LAYER_NOT_CONFIGURED
    )

    # Layer 3: sync code present
    try:
        from openjarvis.memory.cloud_sync import CloudSync  # noqa: F401
        sync_code_present = LAYER_OK
    except Exception:
        sync_code_present = LAYER_MISSING

    # Layers 4-5: always requires deployment — no live calls
    sync_executed = LAYER_REQUIRES_DEPLOYMENT
    worker_access = LAYER_REQUIRES_DEPLOYMENT

    # Determine overall status
    if local_store_type == STORE_LOCAL_MEMORY:
        status = STATUS_LOCAL_ONLY
        detail = (
            "Life-OS data stored in-memory only — tasks are lost on restart. "
            "SQLite backend present; update get_personal_task_store() to use it."
        )
    elif s3_configured == LAYER_NOT_CONFIGURED:
        status = STATUS_SQLITE_LOCAL
        detail = (
            "Life-OS data persisted to SQLite locally. "
            "S3 not configured — cloud sync unavailable. B7 blocked."
        )
    else:
        status = STATUS_REQUIRES_DEPLOYMENT
        detail = (
            "Life-OS data in SQLite locally; S3 configured. "
            "Cloud sync requires deployed Fargate worker (B6). B7 remains open."
        )

    return LifeOSCloudSyncStatus(
        local_store_type=local_store_type,
        s3_configured=s3_configured,
        sync_code_present=sync_code_present,
        sync_executed=sync_executed,
        worker_access=worker_access,
        local_task_count=local_task_count,
        status=status,
        detail=detail,
    )


__all__ = [
    "LifeOSCloudSyncStatus",
    "get_life_os_cloud_sync_status",
    "LAYER_OK",
    "LAYER_MISSING",
    "LAYER_NOT_CONFIGURED",
    "LAYER_REQUIRES_DEPLOYMENT",
    "STORE_LOCAL_MEMORY",
    "STORE_LOCAL_SQLITE",
    "STATUS_LOCAL_ONLY",
    "STATUS_SQLITE_LOCAL",
    "STATUS_CONFIGURED_NOT_SYNCED",
    "STATUS_REQUIRES_DEPLOYMENT",
    "STATUS_READY",
]
