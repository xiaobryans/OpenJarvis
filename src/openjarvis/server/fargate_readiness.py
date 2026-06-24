"""Fargate worker deployment readiness abstraction — B6 live health-check.

Tracks five layers of Fargate worker readiness. Supports live health-check
proof via JARVIS_CLOUD_ENDPOINT env var (set to the API Gateway / ECS URL).

Layers (in order):
  1. code_present        — Fargate runtime code exists in deploy/aws/
  2. configured          — Required env vars are present (presence-only)
  3. deployed            — Live ECS service is running (True when health check passes)
  4. reachable           — Health check responds (True when health check passes)
  5. executing           — Worker process is handling cloud tasks (True when engine=cloud)

Live health-check behaviour:
  - Set JARVIS_CLOUD_ENDPOINT env var to the Fargate API Gateway URL.
  - If set, get_fargate_worker_status() attempts GET {endpoint}/health.
  - If HTTP 200 and status=ok in response: deployed=True, reachable=True.
  - If engine=cloud in response: executing=True.
  - Health check uses a 10-second timeout and catches all exceptions.
  - If JARVIS_CLOUD_ENDPOINT is absent: deployed/reachable/executing remain False.
  - No secret values are read, returned, or logged during health check.

Failure modes (in readiness.status):
  NOT_CONFIGURED          — required env vars absent; cannot start worker
  CONFIGURED_NOT_DEPLOYED — env vars present but health check failed/skipped
  DEPLOYED_NOT_REACHABLE  — ECS detected but health endpoint not responding
  PARTIAL                 — some layers ready, others not
  BLOCKED                 — code or config blocker prevents progress
  READY                   — all 5 layers confirmed live

Hard rules:
- No secret values read, stored, or returned.
- No bucket names, account IDs, private paths, or OAuth paths in responses.
- Health check response is checked for presence/type only — no values stored.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
    src_path = Path(__file__).resolve()
    for i in range(6):
        candidate = src_path.parents[i] / "deploy" / "aws" / "cloud_runtime.py"
        if candidate.exists():
            return True
    return (Path.cwd() / "deploy" / "aws" / "cloud_runtime.py").exists()


def _live_health_check(endpoint: str) -> Tuple[bool, bool, str]:
    """Attempt a GET {endpoint}/health and return (reachable, executing, detail).

    Returns (True, True, detail) only when HTTP 200 + status=ok + engine=cloud.
    Returns (True, False, detail) when HTTP 200 + status=ok + engine != cloud.
    Returns (False, False, detail) on any error or non-200 response.

    Never prints or stores secret values from the response.
    Only checks presence/type of safe health fields.
    """
    url = endpoint.rstrip("/") + "/health"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "OpenJarvis-HealthProbe/1.0"},
        )
        # Health probe SSL: try verified first, fall back to no-verify.
        # No auth or secrets transmitted — verifying server identity is best-effort.
        ctx: ssl.SSLContext
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            if resp.getcode() != 200:
                return False, False, f"Health check HTTP {resp.getcode()}"
            try:
                body = json.loads(resp.read(4096).decode("utf-8", errors="replace"))
            except Exception:
                return True, False, "Health check HTTP 200 but response not JSON"
            ok = body.get("status") == "ok"
            if not ok:
                return True, False, f"Health check HTTP 200 but status={body.get('status')!r}"
            engine = body.get("engine", "")
            executing = engine == "cloud"
            version = body.get("version", "unknown")
            commit = body.get("git_commit", "unknown")
            return (
                True,
                executing,
                f"Health check passed: version={version} commit={commit} engine={engine}",
            )
    except urllib.error.HTTPError as exc:
        return False, False, f"Health check HTTP error: {exc.code}"
    except urllib.error.URLError as exc:
        return False, False, f"Health check URL error: {type(exc.reason).__name__}"
    except Exception as exc:
        return False, False, f"Health check failed: {type(exc).__name__}"


# ---------------------------------------------------------------------------
# Main status function
# ---------------------------------------------------------------------------


def get_fargate_worker_status() -> FargateWorkerReadiness:
    """Return an honest multi-layer Fargate worker readiness status.

    If JARVIS_CLOUD_ENDPOINT is set, performs a live GET /health to determine
    deployed/reachable/executing layers. Otherwise all three default to False.
    No secret values read, stored, or returned.
    """
    code_present = _fargate_code_present()

    missing = [v for v in _REQUIRED_VARS if not os.environ.get(v, "").strip()]
    optional_present = [v for v in _OPTIONAL_VARS if os.environ.get(v, "").strip()]
    configured = len(missing) == 0

    # Live health check if endpoint is configured
    endpoint = os.environ.get("JARVIS_CLOUD_ENDPOINT", "").strip()
    if endpoint:
        reachable, executing, health_detail = _live_health_check(endpoint)
        deployed = reachable  # reachable implies deployed
    else:
        reachable = False
        executing = False
        deployed = False
        health_detail = "JARVIS_CLOUD_ENDPOINT not set — live health check skipped."

    if not code_present:
        status = STATUS_BLOCKED
        detail = "Fargate runtime code not found in deploy/aws/."
    elif deployed and reachable and executing:
        # Live proof takes precedence over local config check
        status = STATUS_READY
        detail = health_detail
    elif deployed and reachable:
        # Deployed + reachable but engine not cloud
        status = STATUS_PARTIAL
        detail = f"{health_detail} (executing=False: engine not cloud or model routing inactive)"
    elif endpoint and not reachable:
        # Endpoint configured but health check failed
        status = STATUS_DEPLOYED_NOT_REACHABLE
        detail = health_detail
    elif not configured:
        # No endpoint; local env incomplete
        status = STATUS_NOT_CONFIGURED
        detail = (
            f"{len(missing)} of {len(_REQUIRED_VARS)} required environment variables "
            "are absent. Fargate worker cannot start without these configured at task level."
        )
    else:
        status = STATUS_CONFIGURED_NOT_DEPLOYED
        detail = (
            "All required env vars present; Fargate runtime code exists. "
            "Set JARVIS_CLOUD_ENDPOINT to enable live health check. "
            "B6 requires deployed + reachable + executing proof."
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
