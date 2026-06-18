"""US15 Diff Review — structured approve/reject workflow for Workbench changes.

Design rules:
- Reject NEVER silently applies changes.
- Approve is always recorded in the event log and approval store.
- Manual-review state parks the diff for human inspection.
- All state transitions are persisted in SQLite for audit.
- No guarded file write happens without an approved DiffReview.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_DB = Path.home() / ".openjarvis" / "workbench_diff_review.db"

DiffReviewStatus = str

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_MANUAL_REVIEW = "manual_review"
STATUS_EXPIRED = "expired"

_VALID_STATUSES = {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_MANUAL_REVIEW, STATUS_EXPIRED}


@dataclass
class FileSummary:
    path: str
    change_type: str  # "modified" | "added" | "deleted" | "renamed"
    additions: int
    deletions: int
    preview: str  # First 500 chars of diff hunk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "change_type": self.change_type,
            "additions": self.additions,
            "deletions": self.deletions,
            "preview": self.preview[:500],
        }


@dataclass
class DiffReview:
    review_id: str
    session_id: str
    task_id: str
    repo_path: str
    raw_diff: str
    changed_files: List[FileSummary]
    status: DiffReviewStatus
    reject_reason: str
    approved_by: str  # "manager" | "auto" | ""
    approval_note: str
    created_at: float
    updated_at: float
    dry_run: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "repo_path": self.repo_path,
            "status": self.status,
            "changed_file_count": len(self.changed_files),
            "changed_files": [f.to_dict() for f in self.changed_files],
            "reject_reason": self.reject_reason,
            "approved_by": self.approved_by,
            "approval_note": self.approval_note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "dry_run": self.dry_run,
            "raw_diff_preview": self.raw_diff[:1000],
        }


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------


def _parse_diff(raw_diff: str) -> List[FileSummary]:
    """Parse a unified diff into FileSummary entries."""
    summaries: List[FileSummary] = []
    current_path = ""
    current_change_type = "modified"
    additions = 0
    deletions = 0
    hunks: List[str] = []

    def flush() -> None:
        if current_path:
            summaries.append(FileSummary(
                path=current_path,
                change_type=current_change_type,
                additions=additions,
                deletions=deletions,
                preview="\n".join(hunks[:20]),
            ))

    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            flush()
            additions = 0
            deletions = 0
            hunks = []
            current_change_type = "modified"
            parts = line.split(" b/", 1)
            current_path = parts[1] if len(parts) == 2 else line
        elif line.startswith("new file mode"):
            current_change_type = "added"
        elif line.startswith("deleted file mode"):
            current_change_type = "deleted"
        elif line.startswith("rename to"):
            current_change_type = "renamed"
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
            if len(hunks) < 20:
                hunks.append(line)
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
            if len(hunks) < 20:
                hunks.append(line)

    flush()
    return summaries


def get_repo_diff(repo_path: str) -> str:
    """Get the current working tree diff."""
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD", "--no-color"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return proc.stdout
        # fallback: unstaged only
        proc2 = subprocess.run(
            ["git", "diff", "--no-color"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc2.stdout
    except Exception as exc:
        return f"# diff unavailable: {exc}"


# ---------------------------------------------------------------------------
# DiffReviewStore
# ---------------------------------------------------------------------------


class DiffReviewStore:
    """SQLite-backed store for DiffReview records."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS diff_reviews (
                review_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_id TEXT NOT NULL DEFAULT '',
                repo_path TEXT NOT NULL DEFAULT '.',
                raw_diff TEXT NOT NULL DEFAULT '',
                changed_files_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'pending',
                reject_reason TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                approval_note TEXT NOT NULL DEFAULT '',
                dry_run INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_dr_session ON diff_reviews (session_id);
            CREATE INDEX IF NOT EXISTS idx_dr_status ON diff_reviews (status);
        """)
        self._conn.commit()

    def create(
        self,
        *,
        session_id: str,
        task_id: str = "",
        repo_path: str = ".",
        raw_diff: str = "",
        dry_run: bool = True,
    ) -> DiffReview:
        if not raw_diff:
            raw_diff = get_repo_diff(repo_path)
        changed_files = _parse_diff(raw_diff)
        review_id = uuid.uuid4().hex[:16]
        now = time.time()
        self._conn.execute(
            """INSERT INTO diff_reviews
               (review_id, session_id, task_id, repo_path, raw_diff,
                changed_files_json, status, reject_reason, approved_by,
                approval_note, dry_run, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                review_id,
                session_id,
                task_id,
                repo_path,
                raw_diff[:50000],
                json.dumps([f.to_dict() for f in changed_files]),
                STATUS_PENDING,
                "",
                "",
                "",
                int(dry_run),
                now,
                now,
            ),
        )
        self._conn.commit()
        return DiffReview(
            review_id=review_id,
            session_id=session_id,
            task_id=task_id,
            repo_path=repo_path,
            raw_diff=raw_diff,
            changed_files=changed_files,
            status=STATUS_PENDING,
            reject_reason="",
            approved_by="",
            approval_note="",
            created_at=now,
            updated_at=now,
            dry_run=dry_run,
        )

    def get(self, review_id: str) -> Optional[DiffReview]:
        row = self._conn.execute(
            "SELECT * FROM diff_reviews WHERE review_id=?", (review_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_review(row)

    def _row_to_review(self, row: sqlite3.Row) -> DiffReview:
        try:
            files_raw = json.loads(row["changed_files_json"])
        except Exception:
            files_raw = []
        changed_files = [
            FileSummary(
                path=f.get("path", ""),
                change_type=f.get("change_type", "modified"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                preview=f.get("preview", ""),
            )
            for f in files_raw
        ]
        return DiffReview(
            review_id=row["review_id"],
            session_id=row["session_id"],
            task_id=row["task_id"],
            repo_path=row["repo_path"],
            raw_diff=row["raw_diff"],
            changed_files=changed_files,
            status=row["status"],
            reject_reason=row["reject_reason"],
            approved_by=row["approved_by"],
            approval_note=row["approval_note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            dry_run=bool(row["dry_run"]),
        )

    def _update_status(
        self,
        review_id: str,
        status: str,
        *,
        reject_reason: str = "",
        approved_by: str = "",
        approval_note: str = "",
    ) -> Optional[DiffReview]:
        now = time.time()
        cur = self._conn.execute(
            """UPDATE diff_reviews SET
               status=?, reject_reason=?, approved_by=?, approval_note=?, updated_at=?
               WHERE review_id=?""",
            (status, reject_reason, approved_by, approval_note, now, review_id),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            return None
        return self.get(review_id)

    def approve(
        self,
        review_id: str,
        *,
        approved_by: str = "manager",
        note: str = "",
    ) -> Optional[DiffReview]:
        """Approve a diff review. Records approval in the store."""
        review = self.get(review_id)
        if review is None:
            return None
        if review.status not in (STATUS_PENDING, STATUS_MANUAL_REVIEW):
            return review  # Already decided
        return self._update_status(
            review_id,
            STATUS_APPROVED,
            approved_by=approved_by,
            approval_note=note or "Manager approved",
        )

    def reject(
        self,
        review_id: str,
        *,
        reason: str = "Rejected by reviewer",
    ) -> Optional[DiffReview]:
        """Reject a diff review. Changes are NOT applied."""
        review = self.get(review_id)
        if review is None:
            return None
        if review.status not in (STATUS_PENDING, STATUS_MANUAL_REVIEW):
            return review  # Already decided
        return self._update_status(
            review_id,
            STATUS_REJECTED,
            reject_reason=reason,
        )

    def mark_manual_review(
        self,
        review_id: str,
        *,
        note: str = "",
    ) -> Optional[DiffReview]:
        """Park diff for manual review."""
        return self._update_status(
            review_id,
            STATUS_MANUAL_REVIEW,
            approval_note=note or "Parked for manual review",
        )

    def list_by_session(self, session_id: str, limit: int = 20) -> List[DiffReview]:
        rows = self._conn.execute(
            "SELECT * FROM diff_reviews WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [self._row_to_review(r) for r in rows]

    def list_pending(self, limit: int = 50) -> List[DiffReview]:
        rows = self._conn.execute(
            "SELECT * FROM diff_reviews WHERE status=? ORDER BY created_at DESC LIMIT ?",
            (STATUS_PENDING, limit),
        ).fetchall()
        return [self._row_to_review(r) for r in rows]

    def list_recent(self, limit: int = 50) -> List[DiffReview]:
        rows = self._conn.execute(
            "SELECT * FROM diff_reviews ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_review(r) for r in rows]


__all__ = [
    "DiffReview",
    "DiffReviewStore",
    "FileSummary",
    "STATUS_PENDING",
    "STATUS_APPROVED",
    "STATUS_REJECTED",
    "STATUS_MANUAL_REVIEW",
    "STATUS_EXPIRED",
    "get_repo_diff",
]
