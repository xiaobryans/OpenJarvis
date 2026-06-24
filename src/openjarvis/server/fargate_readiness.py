"""Fargate worker deployment readiness abstraction — B6 code-side gating.

Tracks five layers of Fargate worker readiness without performing live
cloud calls or reading secret values.

Layers (in order):
  1. code_present        — Fargate runtime code exists in deploy/aws/
  2. configured          — Required env vars are present (presence-only)
  3. deployed            — Live ECS service is running (False until external proof)
  4. reachable           — Health check responds from Fargate task (False until live)
  5. executing           — Worker process is handling tasks (False until live)

Failure modes (in readiness.status):
  NOT_CONFIGURED         — required env vars absent; cannot start worker
  CONFIGURED_NOT_DEPLOYED — env vars present but no live Fargate service running
  DEPLOYED_NOT_REACHABLE  — service exists but health check fails
  PARTIAL                 — some layers ready, others not
  BLOCKED                 — code or config blocker prevents progress
  READY                   — all layers confirmed live (requires real health check proof)

Hard rules:
- This module never performs live network calls.
- No secret values read, stored, or returned.
- No bucket names, account IDs, private paths, or OAuth paths in responses.
- `deployed`, `reachable`, `executing` are always False in this code-only sprint.
  They can only become True after live Fargate deployment with health check proof.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Required env var names (presence-only — never their values)
# ---------------------------------------------------------------------------

_REQUIRED_VARS: List[str] = [
    "OMNIX_WORKBENCH_AWS_REGION",
    "OMNIX_WORKBENCH_MEMORY_BUCKET",
    "OMNIX_WORKBENCH_ARTIFACT_BUCKET",
    "OMNIX_WORKBENCH_STORAGE_PROVIDER",
    "OPENJARVIS_API_KEY",
]

_OPTIONAL_VARS: List[str] = [
    "OMNIX_WORKBENCH_STATE_TABLE",
    "OMNIX_WORKBENCH_AWS_PROFILE",
]

# Failure mode constants
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
STATUS_CONFIGURED_NOT_DEPLOYED = "CONFIGURED_NOT_DEPLOYED"
STATUS_DEPLOYED_NOT_REACHABLE = "DEPLOYED_NOT_REACHABLE"
STATUS_PARTIAL = "PARTIAL"
STATUS_BLOCKED = "BLOCKED"
STATUS_READY = "READY"


# ---------------------------------------------------------------------------
# Readiness dataclass
# ---------------------------------------------------------------------------


@dataclass
class FargateWorkerReadiness:
    """Multi-layer Fargate worker readiness status.

    Fields are honest — none are faked.
    `deployed`, `reachable`, `executing` are only True after live
    deployment with external verification.
    """

    code_present: bool      # Layer 1 — runtime code exists
    configured: bool        # Layer 2 — env vars present (presence-only)
    deployed: bool          # Layer 3 — ECS service live (external proof required)
    reachable: bool         # Layer 4 — health endpoint responds (live network)
    executing: bool         # Layer 5 — worker handling tasks (live proof)

    missing_vars_count: int      # count only — no names in base dict
    optional_vars_present_count: int

    status: str             # STATUS_* constant
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        """Return a dict safe for auth-gated endpoints."""
        return {
            "code_present": self.code_present,
            "configured": self.configured,
            "deployed": self.deployed,
            "reachable": self.reachable,
            "executing": self.executing,
            "missing_vars_count": self.missing_vars_count,
            "optional_vars_present_count": self.optional_vars_present_count,
            "status": self.status,
            "detail": self.detail,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Return public-safe dict — no config booleans, no env var counts."""
        return {
            "code_present": self.code_present,
            "deployed": self.deployed,
            "reachable": self.reachable,
            "executing": self.executing,
            "status": self.status,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Layer checks
# ---------------------------------------------------------------------------


def _fargate_code_present() -> bool:
    """Return True if Fargate runtime code exists in deploy/aws/."""
    # Try from this file's location (src/openjarvis/server/ → repo root)
    src_path = Path(__file__).resolve()
    for i in range(6):
        candidate = src_path.parents[i] / "deploy" / "aws" / "cloud_runtime.py"
        if candidate.exists():
            return True
    # Try from cwd
    cwd_candidate = Path.cwd() / "deploy" / "aws" / "cloud_runtime.py"
    return cwd_candidate.exists()


# ---------------------------------------------------------------------------
# Main status function
# ---------------------------------------------------------------------------


def get_fargate_worker_status() -> FargateWorkerReadiness:
    """Return an honest multi-layer Fargate worker readiness status.

    No live network calls. No secret values. Presence-only env var checks.
    `deployed`, `reachable`, `executing` are always False — they require
    live external verification after Fargate deployment.
    """
    code_present = _fargate_code_present()

    missing = [v for v in _REQUIRED_VARS if not os.environ.get(v, "").strip()]
    optional_present = [v for v in _OPTIONAL_VARS if os.environ.get(v, "").strip()]
    configured = len(missing) == 0

    # Layers 3–5: always False until live deployment proof
    deployed = False
    reachable = False
    executing = False

    if not code_present:
        status = STATUS_BLOCKED
        detail = (
            "Fargate runtime code not found in deploy/aws/ — "
            "cannot determine worker readiness."
        )
    elif not configured:
        status = STATUS_NOT_CONFIGURED
        detail = (
            f"{len(missing)} of {len(_REQUIRED_VARS)} required environment variables "
            "are absent. Fargate worker cannot start without these configured at task level."
        )
    else:
        status = STATUS_CONFIGURED_NOT_DEPLOYED
        detail = (
            "All required env vars present; Fargate runtime code exists. "
            "Worker is NOT deployed — ECS service must be started externally. "
            "B6 remains open until live Fargate deployment is verified."
        )

    return FargateWorkerReadiness(
        code_present=code_present,
        configured=configured,
        deployed=deployed,
        reachable=reachable,
        executing=executing,
        missing_vars_count=len(missing),
        optional_vars_present_count=len(optional_present),
        status=status,
        detail=detail,
    )


__all__ = [
    "FargateWorkerReadiness",
    "get_fargate_worker_status",
    "STATUS_NOT_CONFIGURED",
    "STATUS_CONFIGURED_NOT_DEPLOYED",
    "STATUS_DEPLOYED_NOT_REACHABLE",
    "STATUS_PARTIAL",
    "STATUS_BLOCKED",
    "STATUS_READY",
]
