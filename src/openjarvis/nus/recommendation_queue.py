"""NUS 1C — Persistent Recommendation Queue.

Provides a safe local JSONL queue for recommendations that persists across
sessions. Builds on LearningStore path-safety and secret-redaction patterns.

Queue item statuses (aligned with NUS 1B):
  draft → ready → needs_approval → approved/rejected/blocked → executed_dry_run/superseded

Operations:
  - enqueue recommendation
  - list pending / by status
  - update queue item status
  - load queue after restart/session
  - deduplicate similar recommendations
  - supersede stale recommendations
  - summarize queue state
  - reject unsafe persistence paths
  - redact suspicious secrets before storage

Allowed storage:
  - JSONL in safe local state path or injected temp path in tests
  - No cloud, no external DB, no secret values

Hard safety constraints:
  - No source-code edits, no auto-commit, no deploy, no external sends
  - No secret access or storage
  - Tests must use temp dirs
  - US13 voice HOLD/UNSAFE/PARKED
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.nus.learning_store import (
    _assert_safe_path,
    _is_safe_path,
    redact_suspicious,
    _DEFAULT_STORE_DIR,
)
from openjarvis.nus.recommendation_registry import (
    STATUS_DRAFT,
    STATUS_READY,
    STATUS_NEEDS_APPROVAL,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_BLOCKED,
    STATUS_EXECUTED_DRY_RUN,
    STATUS_SUPERSEDED,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    CONFIDENCE_MEDIUM,
    ACTION_LOCAL_ANALYSIS,
)

logger = logging.getLogger(__name__)

NUS1C_QUEUE_VERSION = "1.0.0"

QUEUE_FILE = "recommendation_queue.jsonl"

_ALL_STATUSES = frozenset({
    STATUS_DRAFT,
    STATUS_READY,
    STATUS_NEEDS_APPROVAL,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_BLOCKED,
    STATUS_EXECUTED_DRY_RUN,
    STATUS_SUPERSEDED,
})

_PENDING_STATUSES = frozenset({STATUS_DRAFT, STATUS_READY, STATUS_NEEDS_APPROVAL})
_TERMINAL_STATUSES = frozenset({
    STATUS_REJECTED, STATUS_BLOCKED, STATUS_EXECUTED_DRY_RUN, STATUS_SUPERSEDED
})


# ---------------------------------------------------------------------------
# QueueItem
# ---------------------------------------------------------------------------


@dataclass
class QueueItem:
    """A single item in the recommendation queue."""

    queue_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Core recommendation fields
    source: str = ""
    category: str = ""
    title: str = ""
    summary: str = ""
    rationale: str = ""
    affected_area: str = ""
    risk_level: str = RISK_LOW
    confidence: str = CONFIDENCE_MEDIUM
    required_action_type: str = ACTION_LOCAL_ANALYSIS
    approval_policy: str = ""

    # Lifecycle
    status: str = STATUS_DRAFT
    rejection_reason: Optional[str] = None
    superseded_by: Optional[str] = None
    dry_run_result: Optional[Dict[str, Any]] = None

    # Linkage
    related_recommendation_ids: List[str] = field(default_factory=list)
    related_failure_pattern_ids: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    # Deduplication key — set by caller to identify semantically similar items
    dedup_key: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "rationale": self.rationale,
            "affected_area": self.affected_area,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "required_action_type": self.required_action_type,
            "approval_policy": self.approval_policy,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "superseded_by": self.superseded_by,
            "dry_run_result": self.dry_run_result,
            "related_recommendation_ids": self.related_recommendation_ids,
            "related_failure_pattern_ids": self.related_failure_pattern_ids,
            "evidence": self.evidence,
            "dedup_key": self.dedup_key,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QueueItem":
        return cls(
            queue_id=d.get("queue_id", uuid.uuid4().hex[:16]),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
            source=d.get("source", ""),
            category=d.get("category", ""),
            title=d.get("title", ""),
            summary=d.get("summary", ""),
            rationale=d.get("rationale", ""),
            affected_area=d.get("affected_area", ""),
            risk_level=d.get("risk_level", RISK_LOW),
            confidence=d.get("confidence", CONFIDENCE_MEDIUM),
            required_action_type=d.get("required_action_type", ACTION_LOCAL_ANALYSIS),
            approval_policy=d.get("approval_policy", ""),
            status=d.get("status", STATUS_DRAFT),
            rejection_reason=d.get("rejection_reason"),
            superseded_by=d.get("superseded_by"),
            dry_run_result=d.get("dry_run_result"),
            related_recommendation_ids=d.get("related_recommendation_ids", []),
            related_failure_pattern_ids=d.get("related_failure_pattern_ids", []),
            evidence=d.get("evidence", {}),
            dedup_key=d.get("dedup_key", ""),
        )


# ---------------------------------------------------------------------------
# RecommendationQueue
# ---------------------------------------------------------------------------


class RecommendationQueue:
    """Persistent recommendation queue across sessions.

    Backed by a JSONL file in a safe local path.
    Rejects unsafe/secret paths, redacts suspicious values before persistence.
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        _assert_safe_path(self._dir)
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("RecommendationQueue: could not create dir %s: %s", self._dir, exc)

        # In-memory index keyed by queue_id
        self._items: Dict[str, QueueItem] = {}
        # Dedup index: dedup_key → queue_id (most recent non-superseded)
        self._dedup_index: Dict[str, str] = {}
        # Load persisted records
        self._load()

    # ------------------------------------------------------------------ #
    # Queue file path                                                       #
    # ------------------------------------------------------------------ #

    def _queue_path(self) -> Path:
        return self._dir / QUEUE_FILE

    # ------------------------------------------------------------------ #
    # Persistence                                                           #
    # ------------------------------------------------------------------ #

    def _load(self) -> int:
        """Load queue items from JSONL file. Returns count loaded."""
        path = self._queue_path()
        if not path.exists():
            return 0
        loaded = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    item = QueueItem.from_dict(d)
                    self._items[item.queue_id] = item
                    # Rebuild dedup index — last non-superseded wins
                    if item.dedup_key and item.status not in _TERMINAL_STATUSES:
                        self._dedup_index[item.dedup_key] = item.queue_id
                    loaded += 1
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("RecommendationQueue: load failed: %s", exc)
        return loaded

    def _save_item(self, item: QueueItem) -> None:
        """Append one item to the JSONL file (redacted)."""
        try:
            safe_dict = redact_suspicious(item.to_dict())
            line = json.dumps(safe_dict) + "\n"
            with self._queue_path().open("a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception as exc:
            logger.warning("RecommendationQueue: save failed: %s", exc)

    def _rewrite_all(self) -> None:
        """Rewrite the entire JSONL file from in-memory state (for status updates)."""
        try:
            lines = []
            for item in self._items.values():
                safe_dict = redact_suspicious(item.to_dict())
                lines.append(json.dumps(safe_dict))
            self._queue_path().write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        except Exception as exc:
            logger.warning("RecommendationQueue: rewrite failed: %s", exc)

    # ------------------------------------------------------------------ #
    # Enqueue                                                               #
    # ------------------------------------------------------------------ #

    def enqueue(
        self,
        source: str,
        category: str,
        title: str,
        summary: str,
        rationale: str = "",
        affected_area: str = "",
        risk_level: str = RISK_LOW,
        confidence: str = CONFIDENCE_MEDIUM,
        required_action_type: str = ACTION_LOCAL_ANALYSIS,
        approval_policy: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        related_recommendation_ids: Optional[List[str]] = None,
        related_failure_pattern_ids: Optional[List[str]] = None,
        dedup_key: str = "",
    ) -> QueueItem:
        """Enqueue a new recommendation.

        If dedup_key matches an existing pending item, supersedes it with the new one.
        """
        # Deduplication: if a non-terminal item with same dedup_key exists, supersede it
        if dedup_key and dedup_key in self._dedup_index:
            existing_id = self._dedup_index[dedup_key]
            existing = self._items.get(existing_id)
            if existing and existing.status not in _TERMINAL_STATUSES:
                self._supersede(existing_id, reason="dedup_superseded")

        # Determine initial status from action type + approval policy
        from openjarvis.nus.recommendation_registry import (
            resolve_approval_policy,
            _BLOCKED_POLICIES,
            _APPROVAL_POLICIES,
        )
        policy = approval_policy or resolve_approval_policy(required_action_type)
        if policy in _BLOCKED_POLICIES:
            initial_status = STATUS_BLOCKED
        elif policy in _APPROVAL_POLICIES:
            initial_status = STATUS_NEEDS_APPROVAL
        else:
            initial_status = STATUS_READY

        item = QueueItem(
            source=source,
            category=category,
            title=title,
            summary=summary,
            rationale=rationale,
            affected_area=affected_area,
            risk_level=risk_level,
            confidence=confidence,
            required_action_type=required_action_type,
            approval_policy=policy,
            status=initial_status,
            evidence=evidence or {},
            related_recommendation_ids=related_recommendation_ids or [],
            related_failure_pattern_ids=related_failure_pattern_ids or [],
            dedup_key=dedup_key,
        )

        self._items[item.queue_id] = item
        if dedup_key and initial_status not in _TERMINAL_STATUSES:
            self._dedup_index[dedup_key] = item.queue_id

        self._save_item(item)
        self._log_event(
            "recommendation_queued",
            f"Queued: {item.queue_id} status={item.status} action={required_action_type}",
        )
        return item

    # ------------------------------------------------------------------ #
    # Status updates                                                        #
    # ------------------------------------------------------------------ #

    def update_status(
        self,
        queue_id: str,
        new_status: str,
        reason: str = "",
        dry_run_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update the status of a queue item."""
        if new_status not in _ALL_STATUSES:
            return {"ok": False, "reason": f"unknown status: {new_status}"}
        item = self._items.get(queue_id)
        if not item:
            return {"ok": False, "reason": "queue_id not found"}
        if item.status == STATUS_BLOCKED and new_status == STATUS_APPROVED:
            return {"ok": False, "reason": "blocked items cannot be approved"}
        item.status = new_status
        item.updated_at = time.time()
        if reason:
            item.rejection_reason = reason
        if dry_run_result:
            item.dry_run_result = dry_run_result
        self._rewrite_all()
        return {"ok": True, "queue_id": queue_id, "status": new_status}

    def _supersede(self, queue_id: str, reason: str = "superseded") -> None:
        """Internal: supersede a queue item."""
        item = self._items.get(queue_id)
        if item:
            item.status = STATUS_SUPERSEDED
            item.updated_at = time.time()
            item.rejection_reason = reason
        self._log_event("recommendation_superseded", f"Superseded: {queue_id} reason={reason}")

    def supersede(self, queue_id: str, successor_id: str) -> Dict[str, Any]:
        """Mark queue_id as superseded by successor_id."""
        item = self._items.get(queue_id)
        if not item:
            return {"ok": False, "reason": "queue_id not found"}
        item.status = STATUS_SUPERSEDED
        item.superseded_by = successor_id
        item.updated_at = time.time()
        self._rewrite_all()
        self._log_event("recommendation_superseded", f"Superseded: {queue_id} by={successor_id}")
        return {"ok": True, "queue_id": queue_id, "status": STATUS_SUPERSEDED}

    # ------------------------------------------------------------------ #
    # Queries                                                               #
    # ------------------------------------------------------------------ #

    def list_pending(self) -> List[QueueItem]:
        """List all pending queue items (draft/ready/needs_approval)."""
        return [i for i in self._items.values() if i.status in _PENDING_STATUSES]

    def list_by_status(self, status: str) -> List[QueueItem]:
        """List queue items by exact status."""
        return [i for i in self._items.values() if i.status == status]

    def list_approved(self) -> List[QueueItem]:
        return self.list_by_status(STATUS_APPROVED)

    def list_rejected(self) -> List[QueueItem]:
        return self.list_by_status(STATUS_REJECTED)

    def list_blocked(self) -> List[QueueItem]:
        return self.list_by_status(STATUS_BLOCKED)

    def list_dry_run(self) -> List[QueueItem]:
        return self.list_by_status(STATUS_EXECUTED_DRY_RUN)

    def list_all(self) -> List[QueueItem]:
        return list(self._items.values())

    def get(self, queue_id: str) -> Optional[QueueItem]:
        return self._items.get(queue_id)

    # ------------------------------------------------------------------ #
    # Summary                                                               #
    # ------------------------------------------------------------------ #

    def summarize(self) -> Dict[str, Any]:
        """Return a summary of queue state (no secret payloads)."""
        counts: Dict[str, int] = {}
        for item in self._items.values():
            counts[item.status] = counts.get(item.status, 0) + 1

        return {
            "queue_version": NUS1C_QUEUE_VERSION,
            "total": len(self._items),
            "pending": len(self.list_pending()),
            "by_status": counts,
            "queue_file": str(self._queue_path()),
            "dedup_entries": len(self._dedup_index),
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }

    @property
    def total_count(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------ #
    # Event logging                                                         #
    # ------------------------------------------------------------------ #

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1c",
                task_id="recommendation_queue",
                event_type=event_type,
                title=f"NUS 1C: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1C queue event log skipped: %s", exc)
