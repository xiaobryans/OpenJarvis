"""Memory OS Governance — forget, edit, export, audit trail, approval, bulk, expiry.

Sprint 1 (carried forward):
  - forget(entry_id)          Hard-delete a raw memory entry
  - forget_distilled(id)      Hard-delete a distilled entry
  - edit(entry_id, ...)       Update content/status/confidence
  - export_namespace(...)     Export raw entries as JSON list
  - export_all()              Full export of raw + distilled

Sprint 2 (new):
  - GovernanceAuditLog        Immutable append-only audit trail (SQLite triggers
                              enforce no DELETE/UPDATE on audit rows)
  - ApprovalRequired          Exception raised when a protected entry is deleted
                              without force=True
  - forget(..., force=False)  Approval gate: confidence>=0.9 or protected kind
                              requires force=True or raises ApprovalRequired
  - bulk_forget(...)          Batch delete by filters with dry_run and safety gates
  - enforce_expiry(...)       Delete all entries past their expires_at timestamp
  - BulkForgetResult          Structured result for bulk operations
  - ExpiryEnforcementResult   Structured result for expiry enforcement

Cloud/cross-device sync governance actions: BLOCKED — requires cloud sync sprint.
Audit trail is local SQLite only in Sprint 2; cloud replication planned.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from openjarvis.memory.store import JarvisMemory, MemoryEntry, MEMORY_STATUSES
from openjarvis.memory.distilled import DistilledMemory, DistilledEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protected kinds + approval threshold
# ---------------------------------------------------------------------------

PROTECTED_KINDS = frozenset({"decision", "preference"})
HIGH_CONFIDENCE_THRESHOLD = 0.9

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ApprovalRequired(Exception):
    """Raised when a protected memory entry is deleted without force=True.

    Attributes
    ----------
    entry_id    The entry that was blocked
    reason      Human-readable explanation
    """

    def __init__(self, entry_id: str, reason: str) -> None:
        super().__init__(
            f"Approval required to delete entry {entry_id!r}: {reason}. "
            "Pass force=True to override."
        )
        self.entry_id = entry_id
        self.reason = reason


# ---------------------------------------------------------------------------
# GovernanceAuditLog — immutable append-only
# ---------------------------------------------------------------------------


@dataclass
class AuditRecord:
    """A single immutable audit log entry."""
    audit_id: str
    action: str          # forget | forget_distilled | edit | bulk_forget | enforce_expiry | export
    entry_id: str        # primary entry affected ('' for bulk/expiry)
    entry_kind: str      # kind of affected entry ('' if unknown)
    confidence_before: float   # confidence of entry at time of action (-1.0 = N/A)
    timestamp: float
    actor: str           # 'system' or caller label
    detail: str          # free-form detail
    forced: bool         # True if force=True was used to bypass approval

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "action": self.action,
            "entry_id": self.entry_id,
            "entry_kind": self.entry_kind,
            "confidence_before": self.confidence_before,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "detail": self.detail,
            "forced": self.forced,
        }


class GovernanceAuditLog:
    """Immutable append-only governance audit trail.

    Uses SQLite triggers to prevent DELETE and UPDATE on audit rows.
    Provides no delete method — the log is truly append-only.

    Cross-device/cloud replication: BLOCKED — planned future sprint.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS governance_audit (
                    audit_id          TEXT PRIMARY KEY,
                    action            TEXT NOT NULL,
                    entry_id          TEXT NOT NULL DEFAULT '',
                    entry_kind        TEXT NOT NULL DEFAULT '',
                    confidence_before REAL NOT NULL DEFAULT -1.0,
                    timestamp         REAL NOT NULL,
                    actor             TEXT NOT NULL DEFAULT 'system',
                    detail            TEXT NOT NULL DEFAULT '',
                    forced            INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_ts "
                "ON governance_audit(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_entry "
                "ON governance_audit(entry_id)"
            )
            # Immutability triggers — prevent deletion of audit rows
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
                BEFORE DELETE ON governance_audit
                BEGIN
                    SELECT RAISE(ABORT, 'governance_audit is immutable: DELETE forbidden');
                END
            """)
            # Prevent update of existing audit rows
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_update
                BEFORE UPDATE ON governance_audit
                BEGIN
                    SELECT RAISE(ABORT, 'governance_audit is immutable: UPDATE forbidden');
                END
            """)
            conn.commit()

    def append(
        self,
        action: str,
        *,
        entry_id: str = "",
        entry_kind: str = "",
        confidence_before: float = -1.0,
        actor: str = "system",
        detail: str = "",
        forced: bool = False,
    ) -> AuditRecord:
        """Append an immutable audit record. Cannot be deleted or modified."""
        record = AuditRecord(
            audit_id=uuid.uuid4().hex[:20],
            action=action,
            entry_id=entry_id,
            entry_kind=entry_kind,
            confidence_before=confidence_before,
            timestamp=time.time(),
            actor=actor,
            detail=detail,
            forced=forced,
        )
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO governance_audit
                   (audit_id, action, entry_id, entry_kind, confidence_before,
                    timestamp, actor, detail, forced)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    record.audit_id,
                    record.action,
                    record.entry_id,
                    record.entry_kind,
                    record.confidence_before,
                    record.timestamp,
                    record.actor,
                    record.detail,
                    int(record.forced),
                ),
            )
            conn.commit()
        return record

    def get_all(self, limit: int = 200) -> List[AuditRecord]:
        """Return audit records ordered newest-first."""
        limit = max(1, min(limit, 10000))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM governance_audit ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_by_entry(self, entry_id: str) -> List[AuditRecord]:
        """Return all audit records for a specific entry_id."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM governance_audit WHERE entry_id=? "
                "ORDER BY timestamp DESC",
                (entry_id,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM governance_audit"
            ).fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AuditRecord:
        return AuditRecord(
            audit_id=row["audit_id"],
            action=row["action"],
            entry_id=row["entry_id"] or "",
            entry_kind=row["entry_kind"] or "",
            confidence_before=row["confidence_before"],
            timestamp=row["timestamp"],
            actor=row["actor"] or "system",
            detail=row["detail"] or "",
            forced=bool(row["forced"]),
        )


# ---------------------------------------------------------------------------
# Bulk forget result
# ---------------------------------------------------------------------------


@dataclass
class BulkForgetResult:
    """Result of a bulk_forget operation."""
    deleted_count: int
    skipped_count: int         # entries skipped due to safety gates
    dry_run: bool
    entries_matched: int       # total entries found before safety filtering
    skipped_ids: List[str]     # entry_ids skipped (approval required)
    deleted_ids: List[str]
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deleted_count": self.deleted_count,
            "skipped_count": self.skipped_count,
            "dry_run": self.dry_run,
            "entries_matched": self.entries_matched,
            "skipped_ids": self.skipped_ids,
            "deleted_ids": self.deleted_ids,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Expiry enforcement result
# ---------------------------------------------------------------------------


@dataclass
class ExpiryEnforcementResult:
    """Result of enforce_expiry operation."""
    deleted_count: int
    dry_run: bool
    entries_expired: int       # total entries found past expires_at
    deleted_ids: List[str]
    now_ts: float              # timestamp used as 'now' reference

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deleted_count": self.deleted_count,
            "dry_run": self.dry_run,
            "entries_expired": self.entries_expired,
            "deleted_ids": self.deleted_ids,
            "now_ts": self.now_ts,
        }


# ---------------------------------------------------------------------------
# GovernanceResult (carried from Sprint 1)
# ---------------------------------------------------------------------------


@dataclass
class GovernanceResult:
    """Result of a single governance action."""
    action: str
    entry_id: str
    success: bool
    detail: str
    timestamp: float = field(default_factory=time.time)
    audit_id: Optional[str] = None    # Sprint 2: audit trail record ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "entry_id": self.entry_id,
            "success": self.success,
            "detail": self.detail,
            "timestamp": self.timestamp,
            "audit_id": self.audit_id,
        }


# ---------------------------------------------------------------------------
# MemoryGovernance — full Sprint 2 implementation
# ---------------------------------------------------------------------------


class MemoryGovernance:
    """Governance controls for JarvisMemory and DistilledMemory.

    Sprint 2 additions:
      - Immutable audit trail (GovernanceAuditLog)
      - Approval gate: forget() raises ApprovalRequired for protected entries
        unless force=True is passed
      - bulk_forget() with dry_run and safety gates
      - enforce_expiry() deterministically deletes expired entries

    Cloud/cross-device audit replication: BLOCKED (planned sprint).
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory: Optional[JarvisMemory] = None,
        distilled: Optional[DistilledMemory] = None,
    ) -> None:
        db = Path(db_path) if db_path else None
        self._memory = memory or JarvisMemory(db_path=db)
        self._distilled = distilled or DistilledMemory(
            db_path=db or self._memory._db_path
        )
        self._audit = GovernanceAuditLog(db or self._memory._db_path)

    # ------------------------------------------------------------------
    # Approval-gated forget
    # ------------------------------------------------------------------

    def forget(
        self,
        entry_id: str,
        *,
        force: bool = False,
        actor: str = "system",
    ) -> GovernanceResult:
        """Hard-delete a raw memory entry.

        Protected entries (confidence >= HIGH_CONFIDENCE_THRESHOLD or
        kind in PROTECTED_KINDS) require force=True or raise ApprovalRequired.

        Raises
        ------
        ApprovalRequired  if protected and force=False
        """
        existing = self._memory.get(entry_id)
        if existing is None:
            return GovernanceResult(
                action="forget",
                entry_id=entry_id,
                success=False,
                detail=f"entry_id={entry_id!r} not found in raw memory",
            )

        needs_approval = (
            existing.confidence >= HIGH_CONFIDENCE_THRESHOLD
            or existing.kind in PROTECTED_KINDS
        )
        if needs_approval and not force:
            raise ApprovalRequired(
                entry_id,
                f"confidence={existing.confidence:.2f}, kind={existing.kind!r}. "
                f"Protected entry requires force=True.",
            )

        deleted = self._memory.delete(entry_id)
        audit = self._audit.append(
            "forget",
            entry_id=entry_id,
            entry_kind=existing.kind,
            confidence_before=existing.confidence,
            actor=actor,
            detail=f"deleted={deleted} forced={force}",
            forced=force,
        )
        logger.info(
            "Governance.forget: entry_id=%s kind=%s confidence=%.2f forced=%s",
            entry_id, existing.kind, existing.confidence, force,
        )
        return GovernanceResult(
            action="forget",
            entry_id=entry_id,
            success=deleted,
            detail=(
                f"deleted raw entry kind={existing.kind!r} "
                f"confidence={existing.confidence:.2f} forced={force}"
            ),
            audit_id=audit.audit_id,
        )

    def forget_distilled(
        self,
        entry_id: str,
        *,
        force: bool = False,
        actor: str = "system",
    ) -> GovernanceResult:
        """Hard-delete a distilled memory entry."""
        existing = self._distilled.get(entry_id)
        if existing is None:
            return GovernanceResult(
                action="forget_distilled",
                entry_id=entry_id,
                success=False,
                detail=f"entry_id={entry_id!r} not found in distilled memory",
            )

        needs_approval = (
            existing.confidence >= HIGH_CONFIDENCE_THRESHOLD
            or existing.kind in PROTECTED_KINDS
        )
        if needs_approval and not force:
            raise ApprovalRequired(
                entry_id,
                f"distilled confidence={existing.confidence:.2f}, kind={existing.kind!r}.",
            )

        deleted = self._distilled.delete(entry_id)
        audit = self._audit.append(
            "forget_distilled",
            entry_id=entry_id,
            entry_kind=existing.kind,
            confidence_before=existing.confidence,
            actor=actor,
            detail=f"deleted={deleted} forced={force}",
            forced=force,
        )
        return GovernanceResult(
            action="forget_distilled",
            entry_id=entry_id,
            success=deleted,
            detail=f"deleted distilled kind={existing.kind!r} forced={force}",
            audit_id=audit.audit_id,
        )

    # ------------------------------------------------------------------
    # Edit (audited)
    # ------------------------------------------------------------------

    def edit(
        self,
        entry_id: str,
        *,
        new_content: Optional[str] = None,
        new_status: Optional[str] = None,
        new_confidence: Optional[float] = None,
        actor: str = "system",
    ) -> GovernanceResult:
        """Edit a raw memory entry (audited)."""
        existing = self._memory.get(entry_id)
        if existing is None:
            return GovernanceResult(
                action="edit",
                entry_id=entry_id,
                success=False,
                detail=f"entry_id={entry_id!r} not found",
            )
        updated = self._memory.update(
            entry_id,
            content=new_content,
            status=new_status,
            confidence=new_confidence,
        )
        if updated is None:
            return GovernanceResult(
                action="edit",
                entry_id=entry_id,
                success=False,
                detail="update returned None unexpectedly",
            )
        audit = self._audit.append(
            "edit",
            entry_id=entry_id,
            entry_kind=existing.kind,
            confidence_before=existing.confidence,
            actor=actor,
            detail=(
                f"content_changed={new_content is not None} "
                f"status={updated.status!r} confidence={updated.confidence:.2f}"
            ),
        )
        return GovernanceResult(
            action="edit",
            entry_id=entry_id,
            success=True,
            detail=(
                f"updated: status={updated.status!r} "
                f"confidence={updated.confidence:.2f}"
            ),
            audit_id=audit.audit_id,
        )

    # ------------------------------------------------------------------
    # Bulk forget
    # ------------------------------------------------------------------

    def bulk_forget(
        self,
        *,
        namespace: Optional[str] = None,
        project_id: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        max_confidence: Optional[float] = None,
        dry_run: bool = True,
        force: bool = False,
        actor: str = "system",
        limit: int = 500,
    ) -> BulkForgetResult:
        """Batch-delete raw memory entries matching the given filters.

        Safety gates:
          - dry_run=True by default: returns what would be deleted without deleting
          - max_confidence: if set, only delete entries with confidence <= this value
            (prevents bulk-deletion of high-confidence memories by accident)
          - Protected entries (high-confidence or protected kind) are skipped unless
            force=True is passed
          - limit: maximum entries to process in one call (default 500)

        Returns BulkForgetResult with counts, IDs, and audit trail.
        """
        if not any([namespace, project_id, kind, status, max_confidence is not None]):
            return BulkForgetResult(
                deleted_count=0,
                skipped_count=0,
                dry_run=dry_run,
                entries_matched=0,
                skipped_ids=[],
                deleted_ids=[],
                detail="no filters specified — bulk_forget requires at least one filter",
            )

        # Fetch candidates
        if namespace:
            candidates = self._memory.list_by_namespace(
                namespace, project_id=project_id, limit=limit
            )
        else:
            # Use a broad search with kind/status filter
            candidates = self._memory.list_by_namespace(
                namespace or "global",
                project_id=project_id,
                limit=limit,
            ) if namespace else self._memory.search(
                ".",  # dot matches all content (LIKE '%  .  %' won't work — use list)
                project_id=project_id,
                kind=kind,
                status=status,
                limit=limit,
                exclude_deleted=False,
            )

        # Apply optional filters
        filtered = []
        for e in candidates:
            if kind is not None and e.kind != kind:
                continue
            if status is not None and e.status != status:
                continue
            if max_confidence is not None and e.confidence > max_confidence:
                continue
            filtered.append(e)

        deleted_ids: List[str] = []
        skipped_ids: List[str] = []

        for entry in filtered:
            is_protected = (
                entry.confidence >= HIGH_CONFIDENCE_THRESHOLD
                or entry.kind in PROTECTED_KINDS
            )
            if is_protected and not force:
                skipped_ids.append(entry.entry_id)
                continue

            if not dry_run:
                self._memory.delete(entry.entry_id)
                deleted_ids.append(entry.entry_id)
            else:
                deleted_ids.append(entry.entry_id)  # dry_run: list what would be deleted

        if not dry_run and deleted_ids:
            self._audit.append(
                "bulk_forget",
                entry_id=",".join(deleted_ids[:10]) + ("..." if len(deleted_ids) > 10 else ""),
                actor=actor,
                detail=(
                    f"bulk deleted {len(deleted_ids)} entries "
                    f"filters: ns={namespace} project={project_id} kind={kind} "
                    f"status={status} max_conf={max_confidence} forced={force}"
                ),
                forced=force,
            )

        actual_deleted = len(deleted_ids) if not dry_run else 0
        return BulkForgetResult(
            deleted_count=actual_deleted,
            skipped_count=len(skipped_ids),
            dry_run=dry_run,
            entries_matched=len(filtered),
            skipped_ids=skipped_ids,
            deleted_ids=deleted_ids,
            detail=(
                f"dry_run={dry_run}: matched={len(filtered)} "
                f"would_delete={len(deleted_ids)} "
                f"skipped={len(skipped_ids)} (approval required)"
            ),
        )

    # ------------------------------------------------------------------
    # Expiry enforcement
    # ------------------------------------------------------------------

    def enforce_expiry(
        self,
        *,
        dry_run: bool = False,
        now: Optional[float] = None,
        actor: str = "system",
    ) -> ExpiryEnforcementResult:
        """Delete all raw memory entries past their expires_at timestamp.

        Parameters
        ----------
        dry_run     If True, report what would be deleted without deleting.
        now         Override the current time (for deterministic testing).
        actor       Label for audit trail.

        Returns ExpiryEnforcementResult with counts and IDs.
        """
        now_ts = now if now is not None else time.time()
        expired = self._memory.list_expired(now=now_ts)

        deleted_ids: List[str] = []
        if not dry_run:
            for entry in expired:
                self._memory.delete(entry.entry_id)
                deleted_ids.append(entry.entry_id)

            if deleted_ids:
                self._audit.append(
                    "enforce_expiry",
                    entry_id=",".join(deleted_ids[:10]) + ("..." if len(deleted_ids) > 10 else ""),
                    actor=actor,
                    detail=(
                        f"expired {len(deleted_ids)} entries at now_ts={now_ts:.1f}"
                    ),
                )
        else:
            deleted_ids = [e.entry_id for e in expired]

        return ExpiryEnforcementResult(
            deleted_count=len(deleted_ids) if not dry_run else 0,
            dry_run=dry_run,
            entries_expired=len(expired),
            deleted_ids=deleted_ids,
            now_ts=now_ts,
        )

    # ------------------------------------------------------------------
    # Export (audited)
    # ------------------------------------------------------------------

    def export_namespace(
        self,
        namespace: str,
        *,
        project_id: Optional[str] = None,
        limit: int = 1000,
        actor: str = "system",
    ) -> List[Dict[str, Any]]:
        """Export raw memory entries as a list of dicts (audited)."""
        entries = self._memory.list_by_namespace(
            namespace, project_id=project_id, limit=limit
        )
        self._audit.append(
            "export",
            entry_id=f"namespace:{namespace}",
            actor=actor,
            detail=f"exported {len(entries)} entries project={project_id}",
        )
        return [e.to_dict() for e in entries]

    def export_all(self, actor: str = "system") -> Dict[str, Any]:
        """Full export of all raw + distilled entries (audited)."""
        namespaces = self._memory.list_namespaces()
        raw: List[Dict[str, Any]] = []
        for ns in namespaces:
            entries = self._memory.list_by_namespace(
                ns["namespace"],
                project_id=ns["project_id"] or None,
                limit=10000,
            )
            raw.extend(e.to_dict() for e in entries)

        distilled: List[Dict[str, Any]] = []
        for kind in ("summary", "decision", "pattern", "preference", "lesson"):
            entries_d = self._distilled.list_by_kind(kind, limit=10000)
            distilled.extend(e.to_dict() for e in entries_d)

        self._audit.append(
            "export_all",
            actor=actor,
            detail=f"exported raw={len(raw)} distilled={len(distilled)}",
        )
        return {
            "raw_count": len(raw),
            "distilled_count": len(distilled),
            "raw": raw,
            "distilled": distilled,
        }

    # ------------------------------------------------------------------
    # Audit log access
    # ------------------------------------------------------------------

    @property
    def audit_log(self) -> GovernanceAuditLog:
        """Direct access to the immutable audit log."""
        return self._audit

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @staticmethod
    def governance_status() -> Dict[str, Any]:
        """Return honest governance status."""
        return {
            "sprint": "plan4_sprint2_memory_os_completion",
            "implemented": [
                "forget (with approval gate)",
                "forget_distilled (with approval gate)",
                "edit (audited)",
                "bulk_forget (with dry_run, safety gates)",
                "enforce_expiry (deterministic, testable)",
                "export_namespace (audited)",
                "export_all (audited)",
                "immutable_audit_trail (SQLite triggers)",
                "approval_workflow (force=True gate)",
            ],
            "not_implemented": [
                {
                    "control": "cloud_audit_replication",
                    "status": "BLOCKED_NO_CLOUD_SYNC",
                    "detail": "Audit trail is local SQLite only. Cloud replication requires cloud sync sprint.",
                },
            ],
        }


__all__ = [
    "ApprovalRequired",
    "AuditRecord",
    "BulkForgetResult",
    "ExpiryEnforcementResult",
    "GovernanceAuditLog",
    "GovernanceResult",
    "MemoryGovernance",
    "HIGH_CONFIDENCE_THRESHOLD",
    "PROTECTED_KINDS",
]
