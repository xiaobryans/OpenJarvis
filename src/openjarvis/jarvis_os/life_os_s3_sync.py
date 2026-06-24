"""Life-OS task S3 sync — B7 cloud sync closure.

Exports SQLitePersonalTaskStore entries to S3 under the 'life_os_tasks/' prefix,
using the existing OMNIX_WORKBENCH_MEMORY_BUCKET configuration.

Design rules (non-negotiable):
- No secret values logged, printed, or returned.
- No bucket names in external responses (truncated to first 8 chars + '...').
- Graceful: all methods return status dicts on failure.
- No live S3 calls if bucket env var is missing.
- Only safe task metadata exported to S3 (task text, status, timestamps, IDs).
- Task content is exported as-is; caller is responsible for not storing secrets
  in Life-OS tasks. The sync layer does not filter content.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ENV_BUCKET = "OMNIX_WORKBENCH_MEMORY_BUCKET"
_ENV_REGION = "OMNIX_WORKBENCH_AWS_REGION"
_ENV_PROFILE = "OMNIX_WORKBENCH_AWS_PROFILE"
_S3_PREFIX = "life_os_tasks"
_S3_KEY = f"{_S3_PREFIX}/tasks.jsonl"
_MAX_TASKS = 10_000


@dataclass
class LifeOSSyncResult:
    """Result of a Life-OS task sync push or pull."""
    operation: str
    success: bool
    tasks_exported: int
    bucket_truncated: str
    s3_key: str
    elapsed_ms: float
    detail: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "success": self.success,
            "tasks_exported": self.tasks_exported,
            "bucket": self.bucket_truncated,
            "s3_key": self.s3_key,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "detail": self.detail,
            "error": self.error,
        }


class LifeOSTaskS3Sync:
    """Syncs SQLitePersonalTaskStore tasks to S3 under life_os_tasks/ prefix.

    Reuses OMNIX_WORKBENCH_MEMORY_BUCKET from the existing Fargate env config.
    No boto3 session is created until push() is called.
    """

    def _get_bucket(self) -> str:
        return os.environ.get(_ENV_BUCKET, "").strip()

    def _get_region(self) -> str:
        return os.environ.get(_ENV_REGION, "ap-southeast-1").strip()

    def _get_profile(self) -> str:
        return os.environ.get(_ENV_PROFILE, "").strip()

    def _make_s3_client(self):
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for Life-OS S3 sync. pip install boto3")
        bucket = self._get_bucket()
        if not bucket:
            raise ValueError(f"{_ENV_BUCKET} must be set for Life-OS S3 sync")
        kwargs: Dict[str, Any] = {"region_name": self._get_region()}
        profile = self._get_profile()
        if profile:
            kwargs["profile_name"] = profile
        session = boto3.Session(**kwargs)
        return session.client("s3"), bucket

    def _load_tasks(self) -> List[Dict[str, Any]]:
        """Read all tasks from SQLitePersonalTaskStore as serializable dicts."""
        try:
            from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore
            store = SQLitePersonalTaskStore()
            tasks = store.list_tasks()
            result = []
            for task in tasks:
                if hasattr(task, "to_dict"):
                    result.append(task.to_dict())
                elif hasattr(task, "__dict__"):
                    result.append({k: v for k, v in task.__dict__.items()
                                   if not k.startswith("_")})
                else:
                    result.append({"raw": str(task)})
            return result[:_MAX_TASKS]
        except Exception as exc:
            logger.warning("LifeOSTaskS3Sync: could not load tasks: %s", type(exc).__name__)
            return []

    def push(self) -> LifeOSSyncResult:
        """Export all Life-OS tasks from SQLite to S3. Returns status dict."""
        start = time.time()
        bucket = self._get_bucket()
        if not bucket:
            return LifeOSSyncResult(
                operation="push", success=False,
                tasks_exported=0,
                bucket_truncated="",
                s3_key=_S3_KEY,
                elapsed_ms=(time.time() - start) * 1000,
                detail=f"{_ENV_BUCKET} not configured — cannot sync to S3",
                error="bucket_not_configured",
            )

        tasks = self._load_tasks()
        bucket_trunc = (bucket[:8] + "...") if len(bucket) > 8 else bucket

        try:
            s3, _ = self._make_s3_client()
        except Exception as exc:
            return LifeOSSyncResult(
                operation="push", success=False,
                tasks_exported=0,
                bucket_truncated=bucket_trunc,
                s3_key=_S3_KEY,
                elapsed_ms=(time.time() - start) * 1000,
                detail="S3 client creation failed",
                error=str(exc),
            )

        body = "\n".join(json.dumps(t, default=str) for t in tasks).encode("utf-8")
        try:
            s3.put_object(
                Bucket=bucket,
                Key=_S3_KEY,
                Body=body,
                ContentType="application/x-ndjson",
            )
        except Exception as exc:
            return LifeOSSyncResult(
                operation="push", success=False,
                tasks_exported=len(tasks),
                bucket_truncated=bucket_trunc,
                s3_key=_S3_KEY,
                elapsed_ms=(time.time() - start) * 1000,
                detail="S3 put_object failed",
                error=str(exc),
            )

        elapsed = (time.time() - start) * 1000
        return LifeOSSyncResult(
            operation="push", success=True,
            tasks_exported=len(tasks),
            bucket_truncated=bucket_trunc,
            s3_key=_S3_KEY,
            elapsed_ms=elapsed,
            detail=f"Exported {len(tasks)} Life-OS tasks to S3 in {elapsed:.0f}ms",
        )

    def get_sync_readiness(self) -> Dict[str, Any]:
        """Return readiness status without performing a sync. No S3 calls."""
        bucket_configured = bool(self._get_bucket())
        try:
            from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore
            store = SQLitePersonalTaskStore()
            store_available = True
            task_count = store.task_count() if store.db_exists() else 0
        except Exception:
            store_available = False
            task_count = 0

        if not bucket_configured:
            status = "NOT_CONFIGURED"
            detail = f"{_ENV_BUCKET} not set — S3 sync unavailable"
        elif not store_available:
            status = "STORE_UNAVAILABLE"
            detail = "SQLitePersonalTaskStore not importable — cannot export tasks"
        else:
            status = "READY_TO_SYNC"
            detail = f"SQLite store available ({task_count} tasks); S3 bucket configured"

        return {
            "s3_bucket_configured": bucket_configured,
            "local_store_available": store_available,
            "local_task_count": task_count,
            "s3_key": _S3_KEY,
            "status": status,
            "detail": detail,
        }


__all__ = [
    "LifeOSTaskS3Sync",
    "LifeOSSyncResult",
]
