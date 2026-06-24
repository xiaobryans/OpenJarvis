"""Workspace sync status — B8 layer tracking for Plan 2C/2H.

Tracks five layers of workspace sync readiness without performing live
cloud calls or reading secret values.

Layers (in order):
  1. local_git_index       — git is available and repo has tracked files
  2. s3_config             — S3 artifact bucket env vars are present
  3. sync_code_present     — cloud_sync.py and related sync code exist
  4. sync_executed         — a sync has been performed (REQUIRES_DEPLOYMENT)
  5. cloud_worker_access   — Fargate worker has S3 access (REQUIRES_DEPLOYMENT)

Layers 4 and 5 are always REQUIRES_DEPLOYMENT in this code-only sprint.
They can only be confirmed after live Fargate deployment and sync execution.

Design rules:
- No live S3 calls.
- No secret values. No full bucket names in responses.
- No claims of sync_executed or cloud_worker_access without live proof.
- B8 is open until layers 4 and 5 are confirmed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Layer status constants
# ---------------------------------------------------------------------------

LAYER_OK = "ok"
LAYER_MISSING = "missing"
LAYER_NOT_CONFIGURED = "not_configured"
LAYER_REQUIRES_DEPLOYMENT = "requires_deployment"
LAYER_UNKNOWN = "unknown"

SYNC_STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
SYNC_STATUS_CODE_READY = "CODE_READY"
SYNC_STATUS_CONFIGURED_NOT_SYNCED = "CONFIGURED_NOT_SYNCED"
SYNC_STATUS_PARTIAL = "PARTIAL"
SYNC_STATUS_BLOCKED = "BLOCKED"
SYNC_STATUS_READY = "READY"


# ---------------------------------------------------------------------------
# Status dataclass
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceSyncStatus:
    """Multi-layer workspace sync readiness for B8.

    Each layer is assessed independently. No live S3 calls.
    sync_executed and cloud_worker_access require Fargate deployment proof.
    """

    local_git_index: str         # LAYER_* constant
    s3_config: str               # LAYER_* constant
    sync_code_present: str       # LAYER_* constant
    sync_executed: str           # always LAYER_REQUIRES_DEPLOYMENT until live proof
    cloud_worker_access: str     # always LAYER_REQUIRES_DEPLOYMENT until live proof

    git_tracked_count: int
    s3_configured: bool
    sync_code_file_count: int    # count only, no paths

    status: str                  # SYNC_STATUS_* constant
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layers": {
                "local_git_index": self.local_git_index,
                "s3_config": self.s3_config,
                "sync_code_present": self.sync_code_present,
                "sync_executed": self.sync_executed,
                "cloud_worker_access": self.cloud_worker_access,
            },
            "git_tracked_count": self.git_tracked_count,
            "s3_configured": self.s3_configured,
            "sync_code_file_count": self.sync_code_file_count,
            "status": self.status,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Layer checks
# ---------------------------------------------------------------------------


def _check_git_index() -> tuple:
    """Check local git index. Returns (layer_status, tracked_count)."""
    try:
        from openjarvis.plan9.workspace_root import git_is_available, workspace_sync_summary
        if not git_is_available():
            return LAYER_MISSING, 0
        summary = workspace_sync_summary()
        count = summary.get("git_tracked_count", 0)
        return LAYER_OK, count
    except Exception:
        return LAYER_UNKNOWN, 0


def _check_s3_config() -> bool:
    """Return True if S3 artifact store env vars are present (presence-only)."""
    required = [
        "OMNIX_WORKBENCH_MEMORY_BUCKET",
        "OMNIX_WORKBENCH_ARTIFACT_BUCKET",
        "OMNIX_WORKBENCH_AWS_REGION",
    ]
    return all(os.environ.get(v, "").strip() for v in required)


def _check_sync_code() -> tuple:
    """Check sync code files exist. Returns (layer_status, file_count)."""
    expected = ["cloud_sync.py", "cloud_memory.py"]
    src_memory = Path(__file__).parent
    found = sum(1 for f in expected if (src_memory / f).exists())
    if found == 0:
        return LAYER_MISSING, 0
    if found == len(expected):
        return LAYER_OK, found
    return LAYER_MISSING, found


# ---------------------------------------------------------------------------
# Main status function
# ---------------------------------------------------------------------------


def get_workspace_sync_status() -> WorkspaceSyncStatus:
    """Return honest multi-layer workspace sync status for B8.

    No live S3 calls. sync_executed and cloud_worker_access are always
    LAYER_REQUIRES_DEPLOYMENT until live Fargate deployment proof.
    """
    git_layer, git_count = _check_git_index()
    s3_ok = _check_s3_config()
    code_layer, code_count = _check_sync_code()

    s3_layer = LAYER_OK if s3_ok else LAYER_NOT_CONFIGURED
    sync_executed_layer = LAYER_REQUIRES_DEPLOYMENT
    cloud_worker_layer = LAYER_REQUIRES_DEPLOYMENT

    layers_ok = sum([
        git_layer == LAYER_OK,
        s3_layer == LAYER_OK,
        code_layer == LAYER_OK,
    ])

    if layers_ok == 3:
        status = SYNC_STATUS_CONFIGURED_NOT_SYNCED
        detail = (
            "Git index, S3 config, and sync code all present. "
            "Sync not yet executed — requires Fargate worker deployment (B6). "
            "B8 remains open until worker performs actual S3 sync."
        )
    elif layers_ok == 2:
        status = SYNC_STATUS_PARTIAL
        missing = []
        if git_layer != LAYER_OK:
            missing.append("git index")
        if s3_layer != LAYER_OK:
            missing.append("S3 config")
        if code_layer != LAYER_OK:
            missing.append("sync code")
        detail = f"Partial workspace sync setup. Missing: {', '.join(missing)}."
    elif layers_ok == 1:
        status = SYNC_STATUS_BLOCKED
        detail = "Workspace sync blocked — multiple required layers missing or not configured."
    else:
        status = SYNC_STATUS_NOT_CONFIGURED
        detail = "Workspace sync not configured — no git index, S3 config, or sync code found."

    return WorkspaceSyncStatus(
        local_git_index=git_layer,
        s3_config=s3_layer,
        sync_code_present=code_layer,
        sync_executed=sync_executed_layer,
        cloud_worker_access=cloud_worker_layer,
        git_tracked_count=git_count,
        s3_configured=s3_ok,
        sync_code_file_count=code_count,
        status=status,
        detail=detail,
    )


__all__ = [
    "WorkspaceSyncStatus",
    "get_workspace_sync_status",
    "SYNC_STATUS_NOT_CONFIGURED",
    "SYNC_STATUS_CODE_READY",
    "SYNC_STATUS_CONFIGURED_NOT_SYNCED",
    "SYNC_STATUS_PARTIAL",
    "SYNC_STATUS_BLOCKED",
    "SYNC_STATUS_READY",
    "LAYER_OK",
    "LAYER_MISSING",
    "LAYER_NOT_CONFIGURED",
    "LAYER_REQUIRES_DEPLOYMENT",
    "LAYER_UNKNOWN",
]
