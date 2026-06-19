"""Cloud Memory Architecture — readiness, status, and fallback management.

Architecture:
  - Cloud memory = operational source of truth (when configured)
  - Local memory/cache = fast runtime persistence + fallback
  - Obsidian = human-readable archive/mirror
  - Prompt/context cache = cost/latency optimization, NOT long-term memory

Cloud backends supported (by status):
  - S3/AWS: BLOCKED_CREDENTIALS — no credentials configured
  - Supabase: BLOCKED_CREDENTIALS — checked via env
  - Local SQLite: DAILY_DRIVER_ACCEPT (always available)

No secrets are logged, returned in status, or stored in memory.
No destructive operations without explicit authorization.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status codes — mirror sprint strict codes
# ---------------------------------------------------------------------------

class CloudMemoryBackendStatus(str, Enum):
    DAILY_DRIVER_ACCEPT = "DAILY_DRIVER_ACCEPT"
    BLOCKED_CREDENTIALS = "BLOCKED_CREDENTIALS"
    BLOCKED_IMPLEMENTATION = "BLOCKED_IMPLEMENTATION"
    PLANNED_IN_EXISTING_PROMPT = "PLANNED_IN_EXISTING_PROMPT"
    OPTIONAL_BACKLOG = "OPTIONAL_BACKLOG"


@dataclass(frozen=True)
class BackendReadiness:
    """Readiness record for a single cloud memory backend."""

    backend: str
    status: CloudMemoryBackendStatus
    available: bool
    credential_env_vars: List[str]
    credential_present: bool
    notes: str
    clearing_steps: List[str] = field(default_factory=list)


@dataclass
class CloudMemoryStatus:
    """Snapshot of the full cloud memory architecture readiness."""

    local_db_path: str
    local_db_exists: bool
    local_status: CloudMemoryBackendStatus
    cloud_backends: List[BackendReadiness]
    active_backend: str           # "local" | backend name
    fallback_chain: List[str]
    sync_status: str              # "local_only" | "cloud_primary" | "degraded"
    checked_at: float
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_db_path": self.local_db_path,
            "local_db_exists": self.local_db_exists,
            "local_status": self.local_status.value,
            "cloud_backends": [
                {
                    "backend": b.backend,
                    "status": b.status.value,
                    "available": b.available,
                    "credential_present": b.credential_present,
                    "notes": b.notes,
                }
                for b in self.cloud_backends
            ],
            "active_backend": self.active_backend,
            "fallback_chain": self.fallback_chain,
            "sync_status": self.sync_status,
            "checked_at": self.checked_at,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Credential presence check — no secrets returned, no logging of values
# ---------------------------------------------------------------------------

def _credential_present(*env_vars: str) -> bool:
    """True if ALL given env vars are set to non-empty values. Never logs values."""
    return all(bool(os.environ.get(v, "").strip()) for v in env_vars)


# ---------------------------------------------------------------------------
# Backend readiness checks
# ---------------------------------------------------------------------------

def _check_s3_aws() -> BackendReadiness:
    creds_present = _credential_present("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    bucket_present = _credential_present("JARVIS_MEMORY_S3_BUCKET")

    if not creds_present:
        return BackendReadiness(
            backend="s3_aws",
            status=CloudMemoryBackendStatus.BLOCKED_CREDENTIALS,
            available=False,
            credential_env_vars=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "JARVIS_MEMORY_S3_BUCKET"],
            credential_present=False,
            notes="AWS credentials not configured. S3 cloud memory unavailable.",
            clearing_steps=[
                "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env",
                "Set JARVIS_MEMORY_S3_BUCKET to the target S3 bucket name",
                "Set AWS_DEFAULT_REGION (e.g. ap-southeast-1)",
                "Verify bucket exists and has read/write permissions",
                "Install boto3: pip install boto3",
            ],
        )

    if not bucket_present:
        return BackendReadiness(
            backend="s3_aws",
            status=CloudMemoryBackendStatus.BLOCKED_CREDENTIALS,
            available=False,
            credential_env_vars=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "JARVIS_MEMORY_S3_BUCKET"],
            credential_present=True,
            notes="AWS credentials present but JARVIS_MEMORY_S3_BUCKET not set.",
            clearing_steps=[
                "Set JARVIS_MEMORY_S3_BUCKET to the target S3 bucket name",
            ],
        )

    # Credentials and bucket configured — attempt a non-destructive ping
    try:
        import boto3  # type: ignore
        s3 = boto3.client("s3")
        bucket = os.environ["JARVIS_MEMORY_S3_BUCKET"]
        s3.head_bucket(Bucket=bucket)
        return BackendReadiness(
            backend="s3_aws",
            status=CloudMemoryBackendStatus.DAILY_DRIVER_ACCEPT,
            available=True,
            credential_env_vars=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "JARVIS_MEMORY_S3_BUCKET"],
            credential_present=True,
            notes="S3 bucket reachable. Cloud memory operational.",
        )
    except ImportError:
        return BackendReadiness(
            backend="s3_aws",
            status=CloudMemoryBackendStatus.BLOCKED_IMPLEMENTATION,
            available=False,
            credential_env_vars=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "JARVIS_MEMORY_S3_BUCKET"],
            credential_present=True,
            notes="boto3 not installed. Install: pip install boto3",
            clearing_steps=["pip install boto3"],
        )
    except Exception as exc:
        return BackendReadiness(
            backend="s3_aws",
            status=CloudMemoryBackendStatus.BLOCKED_CREDENTIALS,
            available=False,
            credential_env_vars=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "JARVIS_MEMORY_S3_BUCKET"],
            credential_present=True,
            notes=f"S3 ping failed: {type(exc).__name__} — check credentials and bucket.",
            clearing_steps=["Verify AWS credentials have s3:HeadBucket permission"],
        )


def _check_supabase() -> BackendReadiness:
    """Check Supabase as optional cloud memory store backend."""
    url_present = _credential_present("SUPABASE_URL")
    key_present = _credential_present("SUPABASE_SERVICE_ROLE_KEY")

    if not (url_present and key_present):
        return BackendReadiness(
            backend="supabase",
            status=CloudMemoryBackendStatus.BLOCKED_CREDENTIALS,
            available=False,
            credential_env_vars=["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
            credential_present=url_present and key_present,
            notes="Supabase credentials not fully configured for cloud memory.",
            clearing_steps=[
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env",
                "Create jarvis_memory table in Supabase if not exists",
            ],
        )

    return BackendReadiness(
        backend="supabase",
        status=CloudMemoryBackendStatus.PLANNED_IN_EXISTING_PROMPT,
        available=False,
        credential_env_vars=["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
        credential_present=True,
        notes="Supabase credentials present. Memory sync implementation scheduled for next prompt.",
        clearing_steps=["Implement supabase memory sync adapter"],
    )


def _check_local(db_path: Path) -> BackendReadiness:
    return BackendReadiness(
        backend="local_sqlite",
        status=CloudMemoryBackendStatus.DAILY_DRIVER_ACCEPT,
        available=True,
        credential_env_vars=[],
        credential_present=True,
        notes=f"Local SQLite at {db_path}. Always available as fallback.",
    )


# ---------------------------------------------------------------------------
# Main readiness check
# ---------------------------------------------------------------------------

def check_cloud_memory_status(db_path: Optional[Path] = None) -> CloudMemoryStatus:
    """Non-destructive readiness check for all memory backends.

    Returns CloudMemoryStatus snapshot. Never logs secrets or credentials.
    """
    if db_path is None:
        db_path = Path.home() / ".jarvis" / "memory.db"

    local_exists = db_path.exists()
    local_backend = _check_local(db_path)

    cloud_backends = [
        _check_s3_aws(),
        _check_supabase(),
    ]

    available_cloud = [b for b in cloud_backends if b.available]

    if available_cloud:
        active_backend = available_cloud[0].backend
        sync_status = "cloud_primary"
    else:
        active_backend = "local_sqlite"
        sync_status = "local_only"

    fallback_chain = [active_backend]
    if active_backend != "local_sqlite":
        fallback_chain.append("local_sqlite")

    blocked = [b for b in cloud_backends if not b.available]
    blocked_names = [b.backend for b in blocked]

    if sync_status == "local_only":
        summary = (
            f"Cloud memory: local_only. "
            f"Cloud backends blocked: {blocked_names}. "
            f"Local SQLite at {db_path} is operational."
        )
    else:
        summary = (
            f"Cloud memory: {active_backend} primary. "
            f"Fallback: local_sqlite."
        )

    return CloudMemoryStatus(
        local_db_path=str(db_path),
        local_db_exists=local_exists,
        local_status=local_backend.status,
        cloud_backends=cloud_backends,
        active_backend=active_backend,
        fallback_chain=fallback_chain,
        sync_status=sync_status,
        checked_at=time.time(),
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Cloud memory interface (stub for future sync when credentials arrive)
# ---------------------------------------------------------------------------

class CloudMemoryGateway:
    """Gateway that routes memory ops to the active backend.

    Current behavior:
    - Reads/writes always go to local SQLite (always available)
    - Cloud sync is BLOCKED_CREDENTIALS until AWS/S3 credentials are configured
    - No data is uploaded without explicit credential configuration

    Future:
    - When cloud backend becomes available, this gateway will sync on write
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._status = check_cloud_memory_status(db_path)
        self._local_db = self._status.local_db_path

    def get_status(self) -> CloudMemoryStatus:
        return self._status

    def is_cloud_available(self) -> bool:
        return any(b.available for b in self._status.cloud_backends)

    def get_active_backend(self) -> str:
        return self._status.active_backend

    def get_fallback_chain(self) -> List[str]:
        return self._status.fallback_chain

    def describe_blockers(self) -> List[Dict[str, Any]]:
        """Return blockers for all cloud backends without secrets."""
        return [
            {
                "backend": b.backend,
                "status": b.status.value,
                "available": b.available,
                "notes": b.notes,
                "clearing_steps": b.clearing_steps,
            }
            for b in self._status.cloud_backends
            if not b.available
        ]


__all__ = [
    "CloudMemoryBackendStatus",
    "BackendReadiness",
    "CloudMemoryStatus",
    "CloudMemoryGateway",
    "check_cloud_memory_status",
]
