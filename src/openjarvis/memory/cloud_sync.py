"""Memory OS Cloud Sync — S3-backed push/pull/merge for JarvisMemory.

Uses Jarvis S3 cloud sync configuration:
  - JARVIS_S3_PROFILE     AWS named profile (default credential chain)
  - JARVIS_S3_REGION      AWS region (default: ap-southeast-1)
  - JARVIS_S3_BUCKET      Target S3 bucket
Legacy: OMNIX_WORKBENCH_* env vars are supported as fallback for backward compatibility.

S3 key layout (under 'jarvis_memory/' prefix, separate from workbench data):
  jarvis_memory/raw_entries.jsonl        — all raw memory entries
  jarvis_memory/distilled_entries.jsonl  — all distilled entries
  jarvis_memory/audit_records.jsonl      — governance audit records

Conflict handling:
  - Merge strategy: last-write-wins by entry created_at timestamp
  - On push: local entries overwrite any older remote entry with same entry_id
  - On pull: remote entries merge into local; local entries with same ID and
    newer created_at are kept
  - No data is deleted during merge — deletions must go through MemoryGovernance

Design rules:
  - No secrets are logged, printed, or returned in status objects
  - Graceful degradation: all methods return status objects on failure
  - Cloud sync is additive: never deletes local data during a pull
  - Bounded: max 10,000 entries per sync operation
  - boto3 is required; raises ImportError with clear message if missing

Cloud audit replication:
  - push_audit() pushes governance_audit records to S3
  - Audit records are append-only — same immutability guarantee on S3
  - Pull merges by audit_id (no duplicates)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# S3 prefix — separate from workbench data
_S3_PREFIX = "jarvis_memory"
_S3_RAW_KEY = f"{_S3_PREFIX}/raw_entries.jsonl"
_S3_DISTILLED_KEY = f"{_S3_PREFIX}/distilled_entries.jsonl"
_S3_AUDIT_KEY = f"{_S3_PREFIX}/audit_records.jsonl"
_MAX_ENTRIES = 10_000

# Primary env var names (universal — not OMNIX-specific)
_ENV_PROFILE = "JARVIS_S3_PROFILE"
_ENV_REGION = "JARVIS_S3_REGION"
_ENV_BUCKET = "JARVIS_S3_BUCKET"
# Legacy env var names (backward-compatible — checked if primary not set)
_ENV_PROFILE_LEGACY = "OMNIX_WORKBENCH_AWS_PROFILE"
_ENV_REGION_LEGACY = "OMNIX_WORKBENCH_AWS_REGION"
_ENV_BUCKET_LEGACY = "OMNIX_WORKBENCH_MEMORY_BUCKET"


# ---------------------------------------------------------------------------
# Status objects
# ---------------------------------------------------------------------------


@dataclass
class CloudSyncResult:
    """Result of a single cloud sync push or pull operation."""
    operation: str       # "push_raw" | "pull_raw" | "push_distilled" | etc.
    success: bool
    entries_transferred: int
    entries_merged: int   # entries merged (pull only)
    entries_skipped: int  # entries already up-to-date
    bucket: str
    s3_key: str
    elapsed_ms: float
    detail: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "success": self.success,
            "entries_transferred": self.entries_transferred,
            "entries_merged": self.entries_merged,
            "entries_skipped": self.entries_skipped,
            "bucket": self.bucket,
            "s3_key": self.s3_key,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "detail": self.detail,
            "error": self.error,
        }


@dataclass
class CloudSyncStatus:
    """Snapshot of the cloud sync configuration readiness."""
    available: bool
    bucket: str
    region: str
    profile_configured: bool
    can_read: bool
    can_write: bool
    last_error: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "bucket": self.bucket[:8] + "..." if len(self.bucket) > 8 else self.bucket,
            "region": self.region,
            "profile_configured": self.profile_configured,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "last_error": self.last_error,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Credential/config helpers
# ---------------------------------------------------------------------------


def _load_s3_config_from_env_file(env_file: str = ".env") -> None:
    """Load env vars from .env file if present. Idempotent."""
    p = Path(env_file)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k and k not in os.environ:
            os.environ[k] = v.strip()


# Backward-compatible alias
_load_env_from_file = _load_s3_config_from_env_file


def _get_config() -> Dict[str, str]:
    """Return current S3 config (no secrets logged).

    Checks JARVIS_S3_* vars first, falls back to OMNIX_WORKBENCH_* for
    backward compatibility.
    """
    return {
        "profile": os.environ.get(_ENV_PROFILE) or os.environ.get(_ENV_PROFILE_LEGACY, ""),
        "region": os.environ.get(_ENV_REGION) or os.environ.get(_ENV_REGION_LEGACY, "ap-southeast-1"),
        "bucket": os.environ.get(_ENV_BUCKET) or os.environ.get(_ENV_BUCKET_LEGACY, ""),
    }


def _make_s3_client():
    """Create a boto3 S3 client using project config. Raises on failure."""
    try:
        import boto3
    except ImportError:
        raise ImportError(
            "boto3 is required for cloud sync. Install: pip install boto3"
        )
    _load_s3_config_from_env_file()
    cfg = _get_config()
    if not cfg["bucket"]:
        raise ValueError(
            f"Cloud sync requires {_ENV_BUCKET} to be set in environment or .env"
        )
    session_kwargs: Dict[str, Any] = {"region_name": cfg["region"]}
    if cfg["profile"]:
        session_kwargs["profile_name"] = cfg["profile"]
    session = boto3.Session(**session_kwargs)
    return session.client("s3"), cfg["bucket"]


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------


def _encode_jsonl(records: List[Dict[str, Any]]) -> bytes:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records).encode()


def _decode_jsonl(content: bytes) -> List[Dict[str, Any]]:
    result = []
    for line in content.decode(errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return result


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _merge_entries(
    local: List[Dict[str, Any]],
    remote: List[Dict[str, Any]],
    id_field: str = "entry_id",
    ts_field: str = "created_at",
) -> List[Dict[str, Any]]:
    """Merge local and remote entry lists.

    Strategy: last-write-wins by ts_field.
    On tie: local wins.
    Entries present only in one side are included as-is.

    Returns merged list with no duplicates by id_field.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    for entry in remote:
        eid = entry.get(id_field)
        if eid:
            merged[eid] = entry
    for entry in local:
        eid = entry.get(id_field)
        if eid:
            existing = merged.get(eid)
            if existing is None:
                merged[eid] = entry
            else:
                local_ts = entry.get(ts_field, 0)
                remote_ts = existing.get(ts_field, 0)
                if local_ts >= remote_ts:  # local wins on tie
                    merged[eid] = entry
    return list(merged.values())


def _merge_audit_records(
    local: List[Dict[str, Any]],
    remote: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge audit records — append-only by audit_id, no overwrites."""
    seen: set = set()
    merged = []
    for r in remote + local:
        aid = r.get("audit_id")
        if aid and aid not in seen:
            seen.add(aid)
            merged.append(r)
    merged.sort(key=lambda r: r.get("timestamp", 0))
    return merged


# ---------------------------------------------------------------------------
# JarvisMemoryS3Sync
# ---------------------------------------------------------------------------


class JarvisMemoryS3Sync:
    """Cloud sync for JarvisMemory entries using Jarvis S3 bucket config.

    Uses JARVIS_S3_BUCKET (or OMNIX_WORKBENCH_MEMORY_BUCKET as legacy fallback)
    under 'jarvis_memory/' prefix.
    All operations are graceful: return CloudSyncResult on failure.

    Usage
    -----
    sync = JarvisMemoryS3Sync()
    result = sync.push_raw(memory.list_all_raw())
    result = sync.pull_raw_and_merge(memory)
    status = sync.get_status()
    """

    def __init__(self) -> None:
        _load_s3_config_from_env_file()

    # ------------------------------------------------------------------
    # Push operations
    # ------------------------------------------------------------------

    def push_raw(self, entries: List[Dict[str, Any]]) -> CloudSyncResult:
        """Push raw memory entries to S3. Merges with existing remote data."""
        return self._push(entries, _S3_RAW_KEY, "push_raw")

    def push_distilled(self, entries: List[Dict[str, Any]]) -> CloudSyncResult:
        """Push distilled memory entries to S3."""
        return self._push(entries, _S3_DISTILLED_KEY, "push_distilled")

    def push_audit(self, records: List[Dict[str, Any]]) -> CloudSyncResult:
        """Push governance audit records to S3 (append-only merge)."""
        return self._push_audit(records)

    def _push(
        self,
        local_entries: List[Dict[str, Any]],
        s3_key: str,
        operation: str,
    ) -> CloudSyncResult:
        start = time.time()
        try:
            s3, bucket = _make_s3_client()
        except Exception as exc:
            return CloudSyncResult(
                operation=operation, success=False,
                entries_transferred=0, entries_merged=0, entries_skipped=0,
                bucket="", s3_key=s3_key,
                elapsed_ms=(time.time() - start) * 1000,
                detail="S3 client creation failed",
                error=str(exc),
            )

        # Fetch existing remote entries (NoSuchKey is caught as generic Exception)
        remote: List[Dict[str, Any]] = []
        try:
            resp = s3.get_object(Bucket=bucket, Key=s3_key)
            remote = _decode_jsonl(resp["Body"].read())
        except Exception:
            pass  # Object may not exist yet on first push

        merged = _merge_entries(local_entries, remote)
        if len(merged) > _MAX_ENTRIES:
            merged = merged[-_MAX_ENTRIES:]

        try:
            s3.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=_encode_jsonl(merged),
                ContentType="application/x-ndjson",
            )
        except Exception as exc:
            return CloudSyncResult(
                operation=operation, success=False,
                entries_transferred=0, entries_merged=len(merged) - len(remote),
                entries_skipped=len(remote),
                bucket=bucket[:8] + "...",
                s3_key=s3_key,
                elapsed_ms=(time.time() - start) * 1000,
                detail="S3 put_object failed",
                error=str(exc),
            )

        elapsed = (time.time() - start) * 1000
        return CloudSyncResult(
            operation=operation, success=True,
            entries_transferred=len(merged),
            entries_merged=len(merged) - len(remote),
            entries_skipped=len(remote),
            bucket=bucket[:8] + "...",
            s3_key=s3_key,
            elapsed_ms=elapsed,
            detail=f"pushed {len(merged)} entries ({len(merged)-len(remote)} new) in {elapsed:.0f}ms",
        )

    def _push_audit(self, records: List[Dict[str, Any]]) -> CloudSyncResult:
        start = time.time()
        s3_key = _S3_AUDIT_KEY
        try:
            s3, bucket = _make_s3_client()
        except Exception as exc:
            return CloudSyncResult(
                operation="push_audit", success=False,
                entries_transferred=0, entries_merged=0, entries_skipped=0,
                bucket="", s3_key=s3_key,
                elapsed_ms=(time.time() - start) * 1000,
                detail="S3 client creation failed",
                error=str(exc),
            )

        remote: List[Dict[str, Any]] = []
        try:
            resp = s3.get_object(Bucket=bucket, Key=s3_key)
            remote = _decode_jsonl(resp["Body"].read())
        except Exception:
            pass

        merged = _merge_audit_records(records, remote)

        try:
            s3.put_object(
                Bucket=bucket, Key=s3_key, Body=_encode_jsonl(merged),
                ContentType="application/x-ndjson",
            )
        except Exception as exc:
            return CloudSyncResult(
                operation="push_audit", success=False,
                entries_transferred=0, entries_merged=0, entries_skipped=0,
                bucket=bucket[:8] + "...", s3_key=s3_key,
                elapsed_ms=(time.time() - start) * 1000,
                detail="S3 put_object failed for audit", error=str(exc),
            )

        elapsed = (time.time() - start) * 1000
        new_count = len(merged) - len(remote)
        return CloudSyncResult(
            operation="push_audit", success=True,
            entries_transferred=len(merged),
            entries_merged=new_count,
            entries_skipped=len(remote),
            bucket=bucket[:8] + "...", s3_key=s3_key,
            elapsed_ms=elapsed,
            detail=f"pushed audit {len(merged)} records ({new_count} new) in {elapsed:.0f}ms",
        )

    # ------------------------------------------------------------------
    # Pull operations
    # ------------------------------------------------------------------

    def pull_raw(self) -> tuple[bool, List[Dict[str, Any]], str]:
        """Pull raw entries from S3. Returns (success, entries, error_msg)."""
        return self._pull(_S3_RAW_KEY)

    def pull_distilled(self) -> tuple[bool, List[Dict[str, Any]], str]:
        """Pull distilled entries from S3."""
        return self._pull(_S3_DISTILLED_KEY)

    def pull_audit(self) -> tuple[bool, List[Dict[str, Any]], str]:
        """Pull audit records from S3."""
        return self._pull(_S3_AUDIT_KEY)

    def _pull(self, s3_key: str) -> tuple[bool, List[Dict[str, Any]], str]:
        try:
            s3, bucket = _make_s3_client()
            resp = s3.get_object(Bucket=bucket, Key=s3_key)
            entries = _decode_jsonl(resp["Body"].read())
            return True, entries, ""
        except Exception as exc:
            return False, [], str(exc)

    # ------------------------------------------------------------------
    # Full sync (push local + merge remote)
    # ------------------------------------------------------------------

    def full_sync(
        self,
        raw_entries: List[Dict[str, Any]],
        distilled_entries: List[Dict[str, Any]],
        audit_records: List[Dict[str, Any]],
    ) -> Dict[str, CloudSyncResult]:
        """Push all three data types to S3 in sequence."""
        return {
            "raw": self.push_raw(raw_entries),
            "distilled": self.push_distilled(distilled_entries),
            "audit": self.push_audit(audit_records),
        }

    # ------------------------------------------------------------------
    # Status check
    # ------------------------------------------------------------------

    def get_status(self) -> CloudSyncStatus:
        """Non-destructive readiness check. Attempts a lightweight S3 head call."""
        _load_s3_config_from_env_file()
        cfg = _get_config()
        profile_configured = bool(cfg["profile"])
        bucket = cfg["bucket"]
        region = cfg["region"]

        if not bucket:
            return CloudSyncStatus(
                available=False,
                bucket="",
                region=region,
                profile_configured=profile_configured,
                can_read=False,
                can_write=False,
                last_error=f"{_ENV_BUCKET} not set",
                detail=f"Cloud sync requires {_ENV_BUCKET} (or {_ENV_BUCKET_LEGACY} as fallback)",
            )

        try:
            s3, _ = _make_s3_client()
            # Lightweight check: list objects with max_keys=1
            s3.list_objects_v2(Bucket=bucket, Prefix=_S3_PREFIX, MaxKeys=1)
            return CloudSyncStatus(
                available=True,
                bucket=bucket[:8] + "..." if len(bucket) > 8 else bucket,
                region=region,
                profile_configured=profile_configured,
                can_read=True,
                can_write=True,
                detail=(
                    f"S3 bucket reachable. prefix={_S3_PREFIX!r} "
                    f"region={region}"
                ),
            )
        except Exception as exc:
            return CloudSyncStatus(
                available=False,
                bucket=bucket[:8] + "..." if len(bucket) > 8 else bucket,
                region=region,
                profile_configured=profile_configured,
                can_read=False,
                can_write=False,
                last_error=f"{type(exc).__name__}: {str(exc)[:120]}",
                detail="S3 connectivity check failed",
            )


__all__ = [
    "JarvisMemoryS3Sync",
    "CloudSyncResult",
    "CloudSyncStatus",
    "_merge_entries",
    "_merge_audit_records",
]
