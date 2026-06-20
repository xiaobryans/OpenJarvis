"""Independent Reviewer — Plan 3B.

Role contract:
  - Receives evidence bundle from worker (never from itself).
  - Produces exactly one of: PASS / HOLD / BLOCKED / FAIL.
  - Cannot self-certify: worker identity is tracked and rejected as reviewer.
  - Does not modify any files; read-only.
  - All verdicts are persisted to SQLite for audit.

Verdict semantics:
  PASS    — evidence is complete, validation passed, rollback path documented.
  HOLD    — evidence present but incomplete; human or higher-tier review needed.
  BLOCKED — critical gate missing (approval not granted, loop cap exceeded, etc.).
  FAIL    — validation failed, evidence contradicts claimed result.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".openjarvis" / "workbench_reviewer.db"


class Verdict(str, Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"
    FAIL = "FAIL"


@dataclass
class EvidenceBundle:
    """Evidence produced by a worker and submitted to the reviewer."""

    task_id: str
    session_id: str
    worker_id: str
    prompt: str
    plan_summary: str
    files_inspected: List[str]
    files_changed: List[str]
    patch_diff: str
    validation_commands: List[str]
    validation_outputs: List[Dict[str, Any]]
    rollback_path: str
    loop_state: Dict[str, Any]
    model_decisions: List[Dict[str, Any]]
    submitted_at: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "worker_id": self.worker_id,
            "prompt": self.prompt,
            "plan_summary": self.plan_summary,
            "files_inspected": self.files_inspected,
            "files_changed": self.files_changed,
            "patch_diff": self.patch_diff,
            "validation_commands": self.validation_commands,
            "validation_outputs": self.validation_outputs,
            "rollback_path": self.rollback_path,
            "loop_state": self.loop_state,
            "model_decisions": self.model_decisions,
            "submitted_at": self.submitted_at,
            "extra": self.extra,
        }


@dataclass
class ReviewVerdict:
    """Reviewer output — immutable once produced."""

    review_id: str
    task_id: str
    session_id: str
    reviewer_id: str
    verdict: Verdict
    reasons: List[str]
    rollback_instruction: str
    evidence_ref: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "reviewer_id": self.reviewer_id,
            "verdict": self.verdict.value,
            "reasons": self.reasons,
            "rollback_instruction": self.rollback_instruction,
            "evidence_ref": self.evidence_ref,
            "created_at": self.created_at,
        }


class IndependentReviewer:
    """Independent post-execution reviewer.

    Workers cannot instantiate this class with their own identity as reviewer_id.
    The caller is responsible for ensuring reviewer_id != worker_id at the
    pipeline level; this class enforces it at review() time.
    """

    def __init__(
        self,
        reviewer_id: str = "jarvis-reviewer-v1",
        db_path: Optional[str] = None,
    ) -> None:
        self._reviewer_id = reviewer_id
        db = Path(db_path) if db_path else _DEFAULT_DB
        db.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS reviewer_verdicts (
                id          TEXT PRIMARY KEY,
                task_id     TEXT NOT NULL,
                session_id  TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                verdict     TEXT NOT NULL,
                reasons     TEXT NOT NULL DEFAULT '[]',
                rollback    TEXT NOT NULL DEFAULT '',
                evidence    TEXT NOT NULL DEFAULT '{}',
                created_at  REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rev_task
                ON reviewer_verdicts (task_id);
            CREATE INDEX IF NOT EXISTS idx_rev_session
                ON reviewer_verdicts (session_id);
        """)
        self._conn.commit()

    def review(
        self,
        evidence: EvidenceBundle,
        *,
        reviewer_id: Optional[str] = None,
    ) -> ReviewVerdict:
        """Review evidence and produce a verdict.

        Raises ValueError if reviewer_id == worker_id (self-certification guard).
        """
        rid = reviewer_id or self._reviewer_id

        # Self-certification guard
        if rid == evidence.worker_id:
            raise ValueError(
                f"Self-certification blocked: reviewer_id '{rid}' == worker_id "
                f"'{evidence.worker_id}'. Worker cannot certify its own work."
            )

        reasons: List[str] = []
        verdict = self._evaluate(evidence, reasons)
        rollback = self._build_rollback_instruction(evidence)

        review_id = uuid.uuid4().hex[:16]
        rv = ReviewVerdict(
            review_id=review_id,
            task_id=evidence.task_id,
            session_id=evidence.session_id,
            reviewer_id=rid,
            verdict=verdict,
            reasons=reasons,
            rollback_instruction=rollback,
            evidence_ref=json.dumps(evidence.to_dict())[:512],
        )
        self._persist(rv, evidence)
        logger.info(
            "REVIEW: task=%s verdict=%s reviewer=%s reasons=%s",
            evidence.task_id[:8],
            verdict.value,
            rid,
            reasons,
        )
        return rv

    def _evaluate(
        self, evidence: EvidenceBundle, reasons: List[str]
    ) -> Verdict:
        """Apply review checklist and return verdict."""
        issues: List[str] = []
        passes: List[str] = []

        # 1. Rollback path must be present
        if not evidence.rollback_path.strip():
            issues.append("MISSING: rollback_path is empty — cannot accept without revert guidance")
        else:
            passes.append("rollback_path present")

        # 2. Validation must have run
        if not evidence.validation_outputs:
            issues.append("MISSING: no validation_outputs — targeted validation was not run")
        else:
            failed_validations = [
                v for v in evidence.validation_outputs
                if not v.get("passed", True)
            ]
            if failed_validations:
                for fv in failed_validations:
                    issues.append(
                        f"FAIL: validation '{fv.get('command', '?')}' did not pass: "
                        f"{fv.get('output', '')[:120]}"
                    )
            else:
                passes.append(f"{len(evidence.validation_outputs)} validation(s) passed")

        # 3. Loop cap — if worker exceeded loop cap, BLOCKED
        loop = evidence.loop_state
        if loop.get("stopped") and loop.get("stop_reason") == "max_attempts_exceeded":
            issues.append(
                f"BLOCKED: worker hit max_attempts ({loop.get('max_attempts')}) — "
                "loop cap enforced, cannot accept"
            )

        # 4. Files inspected must not be a broad audit
        n_inspected = len(evidence.files_inspected)
        if n_inspected > 50:
            issues.append(
                f"HOLD: {n_inspected} files inspected — broad audit detected; "
                "review required"
            )
        elif n_inspected == 0 and evidence.files_changed:
            issues.append("HOLD: files changed but none listed as inspected — evidence incomplete")
        else:
            passes.append(f"{n_inspected} file(s) inspected (targeted)")

        # 5. Model decisions must be logged
        if not evidence.model_decisions:
            issues.append("HOLD: no model_decisions logged — cost governance evidence missing")
        else:
            passes.append(f"{len(evidence.model_decisions)} model decision(s) logged")

        # 6. Plan summary must be present
        if not evidence.plan_summary.strip():
            issues.append("HOLD: plan_summary missing — structured plan was not produced")
        else:
            passes.append("plan_summary present")

        reasons.extend(passes)
        reasons.extend(issues)

        if not issues:
            return Verdict.PASS

        # Classify severity of issues
        has_fail = any(i.startswith("FAIL:") for i in issues)
        has_blocked = any(i.startswith("BLOCKED:") for i in issues)
        has_missing = any(i.startswith("MISSING:") for i in issues)

        if has_fail or has_missing:
            return Verdict.FAIL
        if has_blocked:
            return Verdict.BLOCKED
        return Verdict.HOLD

    def _build_rollback_instruction(self, evidence: EvidenceBundle) -> str:
        """Surface rollback/revert guidance from evidence."""
        if evidence.rollback_path:
            return evidence.rollback_path
        if evidence.files_changed:
            files = " ".join(evidence.files_changed[:5])
            return (
                f"git checkout HEAD -- {files} && git stash  "
                "# Revert changed files to last commit"
            )
        return "git stash  # No specific files identified — stash all uncommitted changes"

    def _persist(self, rv: ReviewVerdict, evidence: EvidenceBundle) -> None:
        self._conn.execute(
            """INSERT INTO reviewer_verdicts
               (id, task_id, session_id, reviewer_id, verdict,
                reasons, rollback, evidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rv.review_id,
                rv.task_id,
                rv.session_id,
                rv.reviewer_id,
                rv.verdict.value,
                json.dumps(rv.reasons),
                rv.rollback_instruction,
                json.dumps(evidence.to_dict())[:4096],
                rv.created_at,
            ),
        )
        self._conn.commit()

    def get_verdict(self, task_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM reviewer_verdicts WHERE task_id=? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "review_id": row["id"],
            "task_id": row["task_id"],
            "session_id": row["session_id"],
            "reviewer_id": row["reviewer_id"],
            "verdict": row["verdict"],
            "reasons": json.loads(row["reasons"] or "[]"),
            "rollback_instruction": row["rollback"],
            "created_at": row["created_at"],
        }

    def list_verdicts(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM reviewer_verdicts WHERE session_id=? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
        return [
            {
                "review_id": r["id"],
                "task_id": r["task_id"],
                "verdict": r["verdict"],
                "reasons": json.loads(r["reasons"] or "[]"),
                "rollback_instruction": r["rollback"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


__all__ = [
    "IndependentReviewer",
    "EvidenceBundle",
    "ReviewVerdict",
    "Verdict",
]
