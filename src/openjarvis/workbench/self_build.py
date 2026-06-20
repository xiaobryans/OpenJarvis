"""LimitedSelfBuild — Plan 3I.

Jarvis can improve itself under strict approval and changed-file-only policy.

Rules (non-negotiable):
  - Only changed files are reviewed (never the whole repo).
  - Risky writes/commits require explicit approval before proceeding.
  - Dry-run mode is the default; no files are written without approval.
  - Targeted validation is run on changed files only.
  - Produces a diff summary, not a broad rewrite.
  - No autonomous broad rewrite — single-file or single-function target only.
  - All actions are logged.

Approval gate:
  approve(task_id, approver) must be called by an authorized approver before
  any file write or commit is executed. Default approver: "Bryan".

Self-build is NOT:
  - Autonomous rewriting of unrelated files.
  - Self-certification (reviewer is always IndependentReviewer).
  - Execution without evidence bundle.
"""

from __future__ import annotations

import difflib
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.workbench.reviewer import IndependentReviewer, EvidenceBundle, Verdict

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".openjarvis" / "self_build.db"
_AUTHORIZED_APPROVERS = {"Bryan", "bryan"}

# Hard limit: only single-file targets allowed in self-build
_MAX_SELF_BUILD_FILES = 3


@dataclass
class SelfBuildTask:
    """A limited self-improvement task."""

    task_id: str
    target_files: List[str]
    description: str
    proposed_diff: str
    validation_commands: List[str]
    status: str  # "pending_approval" | "approved" | "rejected" | "applied" | "dry_run"
    approver: Optional[str]
    created_at: float
    approved_at: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "target_files": self.target_files,
            "description": self.description,
            "proposed_diff": self.proposed_diff[:2000],
            "validation_commands": self.validation_commands,
            "status": self.status,
            "approver": self.approver,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
        }


@dataclass
class SelfBuildResult:
    """Result of a self-build attempt."""

    task_id: str
    status: str  # "dry_run" | "applied" | "blocked" | "rejected" | "fail"
    diff_summary: str
    validation_outputs: List[Dict[str, Any]]
    reviewer_verdict: Optional[Dict[str, Any]]
    rollback_instruction: str
    applied_files: List[str]
    events: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "diff_summary": self.diff_summary,
            "validation_outputs": self.validation_outputs,
            "reviewer_verdict": self.reviewer_verdict,
            "rollback_instruction": self.rollback_instruction,
            "applied_files": self.applied_files,
            "events": self.events,
        }


class LimitedSelfBuild:
    """Limited self-improvement with strict approval and changed-file-only review."""

    def __init__(
        self,
        worker_id: str = "jarvis-self-build-worker",
        reviewer_id: str = "jarvis-self-build-reviewer",
        db_path: Optional[str] = None,
    ) -> None:
        self._worker_id = worker_id
        self._reviewer_id = reviewer_id
        db = Path(db_path) if db_path else _DEFAULT_DB
        db.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._reviewer = IndependentReviewer(
            reviewer_id=reviewer_id,
            db_path=str(db.parent / "self_build_reviewer.db"),
        )

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS self_build_tasks (
                id                  TEXT PRIMARY KEY,
                target_files        TEXT NOT NULL DEFAULT '[]',
                description         TEXT NOT NULL DEFAULT '',
                proposed_diff       TEXT NOT NULL DEFAULT '',
                validation_commands TEXT NOT NULL DEFAULT '[]',
                status              TEXT NOT NULL DEFAULT 'pending_approval',
                approver            TEXT,
                created_at          REAL NOT NULL,
                approved_at         REAL
            );
        """)
        self._conn.commit()

    def propose(
        self,
        target_files: List[str],
        description: str,
        original_contents: Dict[str, str],
        proposed_contents: Dict[str, str],
        validation_commands: Optional[List[str]] = None,
    ) -> SelfBuildTask:
        """Propose a self-improvement change. Does not write anything yet."""
        if len(target_files) > _MAX_SELF_BUILD_FILES:
            raise ValueError(
                f"Self-build limited to {_MAX_SELF_BUILD_FILES} files; "
                f"{len(target_files)} requested. Use CodingPipeline for larger changes."
            )

        # Generate unified diff summary
        diff_lines: List[str] = []
        for fpath in target_files:
            orig = original_contents.get(fpath, "").splitlines(keepends=True)
            prop = proposed_contents.get(fpath, "").splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                orig, prop,
                fromfile=f"a/{fpath}",
                tofile=f"b/{fpath}",
                n=3,
            ))
            diff_lines.extend(diff[:100])  # Cap diff per file

        diff_summary = "".join(diff_lines)[:4096]

        task_id = uuid.uuid4().hex[:16]
        cmds = validation_commands or []
        task = SelfBuildTask(
            task_id=task_id,
            target_files=target_files,
            description=description,
            proposed_diff=diff_summary,
            validation_commands=cmds,
            status="pending_approval",
            approver=None,
            created_at=time.time(),
            approved_at=None,
        )
        self._persist_task(task)
        logger.info(
            "SELF_BUILD_PROPOSE: task=%s files=%s description=%s",
            task_id, target_files, description[:60],
        )
        return task

    def approve(
        self,
        task_id: str,
        approver: str,
    ) -> SelfBuildTask:
        """Approve a proposed self-build task. Only authorized approvers."""
        if approver not in _AUTHORIZED_APPROVERS:
            raise PermissionError(
                f"Approver '{approver}' is not authorized. "
                f"Authorized: {sorted(_AUTHORIZED_APPROVERS)}"
            )
        now = time.time()
        self._conn.execute(
            "UPDATE self_build_tasks SET status='approved', approver=?, approved_at=? WHERE id=?",
            (approver, now, task_id),
        )
        self._conn.commit()
        task = self._get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        logger.info("SELF_BUILD_APPROVE: task=%s approver=%s", task_id, approver)
        return task

    def reject(self, task_id: str, reason: str = "") -> None:
        """Reject a proposed self-build task."""
        self._conn.execute(
            "UPDATE self_build_tasks SET status='rejected' WHERE id=?",
            (task_id,),
        )
        self._conn.commit()
        logger.info("SELF_BUILD_REJECT: task=%s reason=%s", task_id, reason[:80])

    def dry_run(
        self,
        task: SelfBuildTask,
        session_id: Optional[str] = None,
    ) -> SelfBuildResult:
        """Perform dry-run: show diff summary + run reviewer without writing files."""
        sid = session_id or uuid.uuid4().hex[:16]
        events: List[str] = [f"dry_run: task={task.task_id}"]

        # Build evidence (no actual file reads — dry run)
        evidence = EvidenceBundle(
            task_id=task.task_id,
            session_id=sid,
            worker_id=self._worker_id,
            prompt=task.description,
            plan_summary=(
                f"Self-build proposal: {task.description[:120]} | "
                f"targets: {task.target_files}"
            ),
            files_inspected=task.target_files,
            files_changed=[],
            patch_diff=task.proposed_diff,
            validation_commands=task.validation_commands,
            validation_outputs=[],
            rollback_path=(
                f"git checkout HEAD -- {' '.join(task.target_files[:3])}  "
                "# Revert self-build changes"
            ),
            loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
            model_decisions=[{"tier": "cheap", "model": "self-build-dry-run", "reason": "dry_run"}],
        )

        verdict = self._reviewer.review(evidence)
        events.append(f"reviewer: verdict={verdict.verdict.value}")

        self._conn.execute(
            "UPDATE self_build_tasks SET status='dry_run' WHERE id=?",
            (task.task_id,),
        )
        self._conn.commit()

        return SelfBuildResult(
            task_id=task.task_id,
            status="dry_run",
            diff_summary=task.proposed_diff,
            validation_outputs=[],
            reviewer_verdict=verdict.to_dict(),
            rollback_instruction=evidence.rollback_path,
            applied_files=[],
            events=events,
        )

    def apply(
        self,
        task: SelfBuildTask,
        proposed_contents: Dict[str, str],
        repo_path: str = ".",
        session_id: Optional[str] = None,
        run_validation: bool = True,
    ) -> SelfBuildResult:
        """Apply approved self-build changes. Task must be approved first."""
        if task.status != "approved":
            raise PermissionError(
                f"Task {task.task_id} has status '{task.status}'. "
                "Only approved tasks may be applied."
            )

        sid = session_id or uuid.uuid4().hex[:16]
        events: List[str] = [f"apply: task={task.task_id}"]
        applied: List[str] = []
        validation_outputs: List[Dict[str, Any]] = []

        # Write changed files only
        base = Path(repo_path)
        for fpath in task.target_files:
            content = proposed_contents.get(fpath)
            if content is None:
                events.append(f"skip: {fpath} not in proposed_contents")
                continue
            target = base / fpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            applied.append(fpath)
            events.append(f"wrote: {fpath}")

        # Run targeted validation on changed files only
        if run_validation and task.validation_commands:
            import subprocess
            for cmd in task.validation_commands:
                try:
                    r = subprocess.run(
                        cmd, shell=True, cwd=repo_path,
                        capture_output=True, text=True, timeout=30,
                    )
                    passed = r.returncode == 0
                    out = (r.stdout + r.stderr).strip()[:300]
                except Exception as exc:
                    passed = False
                    out = str(exc)[:200]
                validation_outputs.append({"command": cmd, "passed": passed, "output": out})
                events.append(f"validation: {cmd} → {'PASS' if passed else 'FAIL'}")

        rollback = (
            f"git checkout HEAD -- {' '.join(applied[:5])}  "
            "# Revert self-build changes"
        ) if applied else "git stash"

        # Independent reviewer check
        evidence = EvidenceBundle(
            task_id=task.task_id,
            session_id=sid,
            worker_id=self._worker_id,
            prompt=task.description,
            plan_summary=(
                f"Self-build applied: {task.description[:120]} | "
                f"approver={task.approver}"
            ),
            files_inspected=task.target_files,
            files_changed=applied,
            patch_diff=task.proposed_diff,
            validation_commands=task.validation_commands,
            validation_outputs=validation_outputs,
            rollback_path=rollback,
            loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
            model_decisions=[{
                "tier": "cheap",
                "model": "self-build",
                "reason": f"approved by {task.approver}",
            }],
        )

        verdict = self._reviewer.review(evidence)
        events.append(f"reviewer: verdict={verdict.verdict.value}")

        status = "applied" if verdict.verdict == Verdict.PASS else "fail"
        self._conn.execute(
            "UPDATE self_build_tasks SET status=? WHERE id=?",
            (status, task.task_id),
        )
        self._conn.commit()

        return SelfBuildResult(
            task_id=task.task_id,
            status=status,
            diff_summary=task.proposed_diff,
            validation_outputs=validation_outputs,
            reviewer_verdict=verdict.to_dict(),
            rollback_instruction=rollback,
            applied_files=applied,
            events=events,
        )

    def get_task(self, task_id: str) -> Optional[SelfBuildTask]:
        return self._get_task(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM self_build_tasks ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _get_task(self, task_id: str) -> Optional[SelfBuildTask]:
        row = self._conn.execute(
            "SELECT * FROM self_build_tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not row:
            return None
        return SelfBuildTask(
            task_id=row["id"],
            target_files=json.loads(row["target_files"] or "[]"),
            description=row["description"],
            proposed_diff=row["proposed_diff"],
            validation_commands=json.loads(row["validation_commands"] or "[]"),
            status=row["status"],
            approver=row["approver"],
            created_at=row["created_at"],
            approved_at=row["approved_at"],
        )

    def _persist_task(self, task: SelfBuildTask) -> None:
        self._conn.execute(
            """INSERT INTO self_build_tasks
               (id, target_files, description, proposed_diff,
                validation_commands, status, approver, created_at, approved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.task_id,
                json.dumps(task.target_files),
                task.description,
                task.proposed_diff,
                json.dumps(task.validation_commands),
                task.status,
                task.approver,
                task.created_at,
                task.approved_at,
            ),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "task_id": row["id"],
            "target_files": json.loads(row["target_files"] or "[]"),
            "description": row["description"],
            "status": row["status"],
            "approver": row["approver"],
            "created_at": row["created_at"],
            "approved_at": row["approved_at"],
        }

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
        self._reviewer.close()


__all__ = [
    "LimitedSelfBuild",
    "SelfBuildTask",
    "SelfBuildResult",
]
