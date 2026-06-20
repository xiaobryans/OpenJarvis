"""CodingPipeline — Unified Plan 3 autonomous coding workflow (Phases 3D/3E/3F/3G).

Full chain:
  1. Classify task (category, risk tier)
  2. Manager: produce structured plan (necessary-files-only)
  3. Route to worker tier via ModelRouter
  4. Worker: inspect files, produce patch/diff
  5. Run targeted validation
  6. Reviewer: independent PASS/HOLD/BLOCKED/FAIL
  7. Checkpoint: store accepted result
  8. Return evidence bundle + verdict + rollback path

Governance rules (always enforced):
  - Broad repo scans (>20 files) → BLOCKED before worker runs.
  - Destructive actions (git_push, file_delete, shell_exec) → require explicit approval.
  - Loop cap (max_attempts=3) enforced; exceeded → BLOCKED, never retried.
  - Worker cannot produce final verdict (reviewer is always a separate object).
  - No external sends. No production deploys.
  - All actions logged to WorkbenchEventLog.
  - Accepted results stored in CheckpointStore.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.workbench.model_router import (
    ModelRouter,
    ModelTier,
    EscalationAction,
    MockModelAdapter,
    _TASK_CATEGORY_TIERS,
)
from openjarvis.workbench.repair_loop import BoundedRepairLoop
from openjarvis.workbench.checkpoint import CheckpointStore
from openjarvis.workbench.event_log import (
    WorkbenchEventLog,
    EVENT_PLAN_CREATED,
    EVENT_EXECUTION_STARTED,
    EVENT_SUBTASK_DONE,
    EVENT_SUBTASK_FAILED,
    EVENT_EXECUTION_COMPLETE,
    EVENT_APPROVAL_REQUIRED,
    EVENT_DRY_RUN_GATE,
    EVENT_VALIDATION_FAILED,
    EVENT_ROLLBACK_GUIDANCE,
    EVENT_SAFETY_BLOCKED,
)
from openjarvis.workbench.reviewer import (
    IndependentReviewer,
    EvidenceBundle,
    ReviewVerdict,
    Verdict,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

PIPELINE_PASS = "PASS"
PIPELINE_HOLD = "HOLD"
PIPELINE_BLOCKED = "BLOCKED"
PIPELINE_FAIL = "FAIL"

# ---------------------------------------------------------------------------
# Task classification
# ---------------------------------------------------------------------------

_RISKY_KEYWORDS = frozenset({
    "delete", "remove", "drop table", "git push", "deploy", "rm -rf",
    "force push", "truncate", "wipe", "production",
})

_READ_ONLY_KEYWORDS = frozenset({
    "read", "inspect", "check", "list", "show", "view", "grep",
    "search", "find", "status", "diff", "log", "branch",
})


def classify_task(prompt: str) -> Dict[str, Any]:
    """Classify a coding task prompt into category, risk tier, and flags."""
    lower = prompt.lower()
    is_risky = any(k in lower for k in _RISKY_KEYWORDS)
    is_read_only = not is_risky and any(k in lower for k in _READ_ONLY_KEYWORDS)

    if is_read_only:
        category = "read_only"
        risk_tier = "local"
    elif is_risky:
        category = "architecture"
        risk_tier = "premium"
    elif any(k in lower for k in ("fix", "bug", "patch", "regression")):
        category = "debugging"
        risk_tier = "mid"
    elif any(k in lower for k in ("implement", "feature", "add", "create")):
        category = "implementation"
        risk_tier = "mid"
    elif any(k in lower for k in ("test", "spec")):
        category = "test_writing"
        risk_tier = "mid"
    elif any(k in lower for k in ("review", "security", "audit")):
        category = "security"
        risk_tier = "premium"
    else:
        category = "implementation"
        risk_tier = "mid"

    return {
        "category": category,
        "risk_tier": risk_tier,
        "is_risky": is_risky,
        "is_read_only": is_read_only,
        "requires_approval": is_risky,
    }


# ---------------------------------------------------------------------------
# File inspection (targeted, bounded)
# ---------------------------------------------------------------------------

_MAX_INSPECT_FILES = 20  # Hard limit — more → BLOCKED (broad audit)


def inspect_files(
    file_paths: List[str],
    repo_path: str = ".",
    max_lines_per_file: int = 80,
) -> Dict[str, str]:
    """Read up to max_lines_per_file lines from each file. Bounded."""
    if len(file_paths) > _MAX_INSPECT_FILES:
        raise ValueError(
            f"Broad audit blocked: {len(file_paths)} files requested, "
            f"max is {_MAX_INSPECT_FILES}"
        )
    result: Dict[str, str] = {}
    base = Path(repo_path)
    for fpath in file_paths:
        p = base / fpath
        if not p.exists():
            result[fpath] = "[FILE_NOT_FOUND]"
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            result[fpath] = "\n".join(lines[:max_lines_per_file])
        except Exception as exc:
            result[fpath] = f"[READ_ERROR: {exc}]"
    return result


# ---------------------------------------------------------------------------
# Validation runner (targeted only)
# ---------------------------------------------------------------------------

def run_validation(
    commands: List[str],
    cwd: str = ".",
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """Run targeted validation commands. Returns list of {command, passed, output}."""
    outputs: List[Dict[str, Any]] = []
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            passed = result.returncode == 0
            output = (result.stdout + result.stderr).strip()
        except subprocess.TimeoutExpired:
            passed = False
            output = f"TIMEOUT after {timeout}s"
        except Exception as exc:
            passed = False
            output = f"ERROR: {exc}"
        outputs.append({"command": cmd, "passed": passed, "output": output[:500]})
    return outputs


# ---------------------------------------------------------------------------
# Pipeline config and result
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Pipeline configuration."""

    max_loop_attempts: int = 3
    dry_run: bool = True  # Default safe: never commit/push without explicit opt-in
    require_approval_for_risky: bool = True
    max_inspect_files: int = _MAX_INSPECT_FILES
    repo_path: str = "."
    worker_id: str = "jarvis-worker-v1"
    reviewer_id: str = "jarvis-reviewer-v1"
    validation_timeout_s: int = 30
    db_path: Optional[str] = None
    use_real_worker: bool = True  # Read real files + run git diff (not mock-only)


@dataclass
class PipelineResult:
    """Final result of a pipeline run."""

    run_id: str
    task_id: str
    session_id: str
    verdict: str  # PASS / HOLD / BLOCKED / FAIL
    classification: Dict[str, Any]
    plan_summary: str
    files_inspected: List[str]
    file_contents: Dict[str, str]  # path → first N lines of actual content
    files_changed: List[str]
    patch_diff: str
    validation_outputs: List[Dict[str, Any]]
    reviewer_verdict: Optional[Dict[str, Any]]
    rollback_instruction: str
    model_decisions: List[Dict[str, Any]]
    loop_state: Dict[str, Any]
    events: List[str]
    duration_s: float
    checkpoint_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "verdict": self.verdict,
            "classification": self.classification,
            "plan_summary": self.plan_summary,
            "files_inspected": self.files_inspected,
            "file_contents": self.file_contents,
            "files_changed": self.files_changed,
            "patch_diff": self.patch_diff,
            "validation_outputs": self.validation_outputs,
            "reviewer_verdict": self.reviewer_verdict,
            "rollback_instruction": self.rollback_instruction,
            "model_decisions": self.model_decisions,
            "loop_state": self.loop_state,
            "events": self.events,
            "duration_s": round(self.duration_s, 3),
            "checkpoint_id": self.checkpoint_id,
        }


# ---------------------------------------------------------------------------
# CodingPipeline
# ---------------------------------------------------------------------------

class CodingPipeline:
    """Integrated coding pipeline: classify → plan → route → work → validate → review.

    Workers and reviewers are always separate objects; worker_id != reviewer_id
    is enforced at the reviewer boundary.
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self._cfg = config or PipelineConfig()
        db = self._cfg.db_path
        self._router = ModelRouter(
            db_path=db or str(Path.home() / ".openjarvis" / "pipeline_routing.db"),
            adapter_override=MockModelAdapter(),
        )
        self._checkpoint = CheckpointStore(
            db_path=db or str(Path.home() / ".openjarvis" / "pipeline_checkpoints.db")
        )
        self._event_log = WorkbenchEventLog(
            db_path=db or str(Path.home() / ".openjarvis" / "pipeline_events.db")
        )
        self._reviewer = IndependentReviewer(
            reviewer_id=self._cfg.reviewer_id,
            db_path=db or str(Path.home() / ".openjarvis" / "pipeline_reviewer.db"),
        )

    def run(
        self,
        prompt: str,
        *,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        files_to_inspect: Optional[List[str]] = None,
        validation_commands: Optional[List[str]] = None,
        approval_granted: bool = False,
        patch_diff: str = "",
        files_changed: Optional[List[str]] = None,
    ) -> PipelineResult:
        """Execute the full coding pipeline for a prompt."""
        t0 = time.time()
        run_id = uuid.uuid4().hex[:16]
        session_id = session_id or uuid.uuid4().hex[:16]
        task_id = task_id or uuid.uuid4().hex[:16]
        events: List[str] = []
        model_decisions: List[Dict[str, Any]] = []
        checkpoint_id: Optional[str] = None

        # ── Step 1: Classify ─────────────────────────────────────────────
        classification = classify_task(prompt)
        events.append(f"classify: category={classification['category']} risk={classification['risk_tier']}")

        # ── Step 2: Risky approval gate ──────────────────────────────────
        if classification["requires_approval"] and not approval_granted:
            self._event_log.push(
                session_id=session_id,
                task_id=task_id,
                event_type=EVENT_APPROVAL_REQUIRED,
                title="Risky task requires approval",
                detail=f"category={classification['category']}; prompt={prompt[:80]}",
                tone="warning",
            )
            events.append("BLOCKED: risky task requires explicit approval_granted=True")
            return PipelineResult(
                run_id=run_id,
                task_id=task_id,
                session_id=session_id,
                verdict=PIPELINE_BLOCKED,
                classification=classification,
                plan_summary="",
                files_inspected=[],
                file_contents={},
                files_changed=[],
                patch_diff="",
                validation_outputs=[],
                reviewer_verdict=None,
                rollback_instruction="git stash  # No changes made — blocked before execution",
                model_decisions=[],
                loop_state={},
                events=events,
                duration_s=time.time() - t0,
                checkpoint_id=None,
            )

        # ── Step 3: Identify necessary files (real worker or explicit list) ──
        inspect_target = list(files_to_inspect or [])
        if not inspect_target and self._cfg.use_real_worker:
            inspect_target = self._identify_necessary_files(prompt)
            events.append(f"worker_identify: {len(inspect_target)} file(s) identified")

        # ── Step 4: Route to model tier ───────────────────────────────────
        decision = self._router.route(
            subtask_id=f"{task_id}-main",
            tool_id="file_read",
            description=prompt[:120],
            session_id=session_id,
            task_id=task_id,
            category=classification["category"],
            high_trust=classification["is_risky"],
        )
        model_decisions.append(decision.to_dict())
        events.append(
            f"route: tier={decision.assigned_tier.value} "
            f"model={decision.assigned_model} reason={decision.reason[:60]}"
        )

        # ── Step 5: Plan (manager produces structured plan) ──────────────
        plan_summary = self._build_plan(
            prompt=prompt,
            classification=classification,
            files=inspect_target,
        )
        events.append(f"plan: {plan_summary[:80]}")
        self._event_log.push(
            session_id=session_id,
            task_id=task_id,
            event_type=EVENT_PLAN_CREATED,
            title="Plan produced",
            detail=plan_summary[:240],
            tone="info",
        )

        # ── Step 5a: Worker — inspect files (bounded) ────────────────────
        if len(inspect_target) > self._cfg.max_inspect_files:
            events.append(
                f"BLOCKED: {len(inspect_target)} files > "
                f"max {self._cfg.max_inspect_files} — broad audit rejected"
            )
            self._event_log.push(
                session_id=session_id,
                task_id=task_id,
                event_type=EVENT_SAFETY_BLOCKED,
                title="Broad audit blocked",
                detail=f"{len(inspect_target)} files requested",
                tone="error",
            )
            return PipelineResult(
                run_id=run_id,
                task_id=task_id,
                session_id=session_id,
                verdict=PIPELINE_BLOCKED,
                classification=classification,
                plan_summary=plan_summary,
                files_inspected=[],
                file_contents={},
                files_changed=[],
                patch_diff="",
                validation_outputs=[],
                reviewer_verdict=None,
                rollback_instruction="git stash",
                model_decisions=model_decisions,
                loop_state={},
                events=events,
                duration_s=time.time() - t0,
                checkpoint_id=None,
            )

        self._event_log.push(
            session_id=session_id,
            task_id=task_id,
            event_type=EVENT_EXECUTION_STARTED,
            title="Worker started",
            detail=f"inspecting {len(inspect_target)} file(s)",
            tone="info",
        )

        # ── Step 5b: Real file inspection ─────────────────────────────────
        file_contents: Dict[str, str] = {}
        if self._cfg.use_real_worker and inspect_target:
            file_contents = inspect_files(
                inspect_target,
                repo_path=self._cfg.repo_path,
                max_lines_per_file=80,
            )
            real_reads = [p for p, c in file_contents.items() if not c.startswith("[FILE_NOT_FOUND]") and not c.startswith("[READ_ERROR")]
            events.append(f"worker_read: {len(real_reads)}/{len(inspect_target)} file(s) read successfully")
            self._event_log.push(
                session_id=session_id,
                task_id=task_id,
                event_type=EVENT_SUBTASK_DONE,
                title=f"File inspection: {len(real_reads)} file(s) read",
                detail=f"paths={inspect_target[:5]}",
                tone="info",
            )

        # ── Step 5c: Real git diff ────────────────────────────────────────
        real_git_diff = self._get_git_diff(self._cfg.repo_path)
        if real_git_diff and not patch_diff:
            patch_diff = real_git_diff
            events.append(f"worker_diff: git diff produced {len(real_git_diff)} chars")

        # ── Step 6: Loop-guarded validation ──────────────────────────────
        loop = BoundedRepairLoop(max_attempts=self._cfg.max_loop_attempts)
        validation_outputs: List[Dict[str, Any]] = []
        cmds = validation_commands or []

        while loop.can_retry():
            vout = run_validation(
                cmds,
                cwd=self._cfg.repo_path,
                timeout=self._cfg.validation_timeout_s,
            )
            validation_outputs = vout
            all_passed = all(v["passed"] for v in vout) if vout else True

            if all_passed:
                events.append(
                    f"validation: {len(vout)} command(s) passed "
                    f"(attempt {len(loop.state.attempts)+1})"
                )
                break

            # Validation failed — decide whether to retry
            failed_cmds = [v["command"] for v in vout if not v["passed"]]
            err_msg = f"validation failed: {failed_cmds}"
            events.append(f"validation_failed (attempt {len(loop.state.attempts)+1}): {err_msg}")

            self._event_log.push(
                session_id=session_id,
                task_id=task_id,
                event_type=EVENT_VALIDATION_FAILED,
                title="Validation failed",
                detail=err_msg[:200],
                tone="error",
            )

            repair = loop.decide(
                router=self._router,
                subtask_id=f"{task_id}-validate",
                tool_id="shell_exec_readonly",
                session_id=session_id,
                task_id=task_id,
                validation_failed=True,
                terminal_error=False,
                error_message=err_msg,
            )
            if not repair.get("retry", False):
                events.append(f"loop_cap: {repair.get('reason', 'max_attempts_exceeded')}")
                break

        # Check if loop stopped due to cap exceeded
        loop_stopped_at_cap = (
            loop.state.stopped
            and loop.state.stop_reason == "max_attempts_exceeded"
        )
        if loop_stopped_at_cap:
            events.append("BLOCKED: loop cap exceeded — stop-on-blocker enforced")

        # ── Step 7: Dry-run gate ──────────────────────────────────────────
        actual_patch = patch_diff
        actual_changed = files_changed or []

        if self._cfg.dry_run and actual_changed:
            self._event_log.push(
                session_id=session_id,
                task_id=task_id,
                event_type=EVENT_DRY_RUN_GATE,
                title="Dry-run gate — changes not applied",
                detail=f"files_changed={actual_changed}",
                tone="warning",
            )
            events.append(f"dry_run_gate: {len(actual_changed)} file change(s) staged but not applied")

        # ── Step 8: Build rollback instruction ────────────────────────────
        rollback = self._build_rollback(actual_changed, self._cfg.repo_path)

        self._event_log.push(
            session_id=session_id,
            task_id=task_id,
            event_type=EVENT_ROLLBACK_GUIDANCE,
            title="Rollback path surfaced",
            detail=rollback[:200],
            tone="info",
        )
        events.append(f"rollback: {rollback[:80]}")

        # ── Step 9: Submit evidence to independent reviewer ───────────────
        evidence = EvidenceBundle(
            task_id=task_id,
            session_id=session_id,
            worker_id=self._cfg.worker_id,
            prompt=prompt,
            plan_summary=plan_summary,
            files_inspected=inspect_target,
            files_changed=actual_changed,
            patch_diff=actual_patch,
            validation_commands=cmds,
            validation_outputs=validation_outputs,
            rollback_path=rollback,
            loop_state=loop.state.to_dict(),
            model_decisions=model_decisions,
        )

        reviewer_verdict: Optional[ReviewVerdict] = None
        final_verdict: str = PIPELINE_HOLD

        try:
            reviewer_verdict = self._reviewer.review(evidence)
            final_verdict = reviewer_verdict.verdict.value
            events.append(
                f"reviewer: verdict={final_verdict} "
                f"reasons={reviewer_verdict.reasons[:2]}"
            )
        except ValueError as exc:
            events.append(f"reviewer_error: {exc}")
            final_verdict = PIPELINE_BLOCKED

        # ── Step 10: Log completion ───────────────────────────────────────
        self._event_log.push(
            session_id=session_id,
            task_id=task_id,
            event_type=EVENT_EXECUTION_COMPLETE,
            title=f"Pipeline complete: {final_verdict}",
            detail=f"run_id={run_id} verdict={final_verdict}",
            tone="success" if final_verdict == PIPELINE_PASS else "warning",
        )

        # ── Step 11: Checkpoint if PASS ───────────────────────────────────
        if final_verdict == PIPELINE_PASS:
            cp = self._checkpoint.save_checkpoint(
                session_id=session_id,
                task_id=task_id,
                label=f"pipeline-{run_id}",
                evidence=json.dumps({
                    "files_changed": actual_changed,
                    "validation_outputs": validation_outputs,
                })[:1024],
                verdict="ACCEPT",
                notes={"run_id": run_id, "verdict": final_verdict},
            )
            checkpoint_id = cp.id
            events.append(f"checkpoint: accepted id={checkpoint_id}")

        return PipelineResult(
            run_id=run_id,
            task_id=task_id,
            session_id=session_id,
            verdict=final_verdict,
            classification=classification,
            plan_summary=plan_summary,
            files_inspected=inspect_target,
            file_contents=file_contents,
            files_changed=actual_changed,
            patch_diff=actual_patch,
            validation_outputs=validation_outputs,
            reviewer_verdict=reviewer_verdict.to_dict() if reviewer_verdict else None,
            rollback_instruction=rollback,
            model_decisions=model_decisions,
            loop_state=loop.state.to_dict(),
            events=events,
            duration_s=time.time() - t0,
            checkpoint_id=checkpoint_id if final_verdict == PIPELINE_PASS else None,
        )

    def _identify_necessary_files(self, prompt: str) -> List[str]:
        """Use CodingManager heuristics to identify necessary files from prompt.

        Falls back to empty list if CodingManager is unavailable.
        Capped to max_inspect_files — no broad scans.
        """
        try:
            from openjarvis.workbench.coding_manager import _extract_explicit_files
            explicit = _extract_explicit_files(prompt)
            if explicit:
                return explicit[:self._cfg.max_inspect_files]
        except Exception:
            pass

        # Fallback: extract .py/.ts/.js file mentions from prompt text
        import re
        files: List[str] = []
        for m in re.finditer(r'[\w./\-]+\.(?:py|ts|js|tsx|jsx|json|yaml|yml|toml|md)', prompt):
            candidate = m.group(0).strip("./ ")
            if candidate and "/" not in candidate or not candidate.startswith("/"):
                files.append(candidate)
        return files[:self._cfg.max_inspect_files]

    def _get_git_diff(self, repo_path: str) -> str:
        """Run git diff --cached && git diff to get actual working-tree diff.

        Returns empty string if git is unavailable or no diff.
        """
        try:
            r = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            staged = r.stdout.strip()
            r2 = subprocess.run(
                ["git", "diff", "HEAD", "--", "*.py", "*.ts", "*.js"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            full_diff = r2.stdout.strip()
            if full_diff:
                return full_diff[:4096]
            if staged:
                return f"[git diff --stat HEAD]\n{staged}"
            return ""
        except Exception:
            return ""

    def _build_plan(
        self,
        prompt: str,
        classification: Dict[str, Any],
        files: List[str],
    ) -> str:
        """Produce a structured plan summary."""
        file_section = (
            f"Files to inspect: {', '.join(files[:10])}"
            if files
            else "No specific files provided — worker will determine necessary files"
        )
        return (
            f"Task category: {classification['category']} | "
            f"Risk tier: {classification['risk_tier']} | "
            f"{file_section} | "
            f"Prompt: {prompt[:120]}"
        )

    def _build_rollback(self, files_changed: List[str], repo_path: str) -> str:
        """Build a concrete rollback instruction."""
        if not files_changed:
            return "git stash  # No files changed — nothing to revert"
        files_str = " ".join(files_changed[:10])
        return (
            f"git checkout HEAD -- {files_str}  "
            f"# Revert {len(files_changed)} changed file(s) to last commit"
        )

    def get_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Return logged events for a session."""
        events = self._event_log.list_events(session_id=session_id)
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "title": e.title,
                "detail": e.detail,
                "tone": e.tone,
                "created_at": e.created_at,
            }
            for e in events
        ]

    def get_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return most recent accepted checkpoint for a session if exists."""
        cps = self._checkpoint.list_checkpoints(session_id=session_id)
        accepted = [c for c in cps if c.verdict == "ACCEPT"]
        if not accepted:
            return None
        cp = accepted[-1]
        return cp.to_dict()

    def cost_summary(self, session_id: str) -> Dict[str, Any]:
        """Return model routing cost summary for a session."""
        return self._router.session_cost_summary(session_id)

    def close(self) -> None:
        self._router.close()
        self._checkpoint.close()
        self._event_log.close()
        self._reviewer.close()


__all__ = [
    "CodingPipeline",
    "PipelineConfig",
    "PipelineResult",
    "classify_task",
    "PIPELINE_PASS",
    "PIPELINE_HOLD",
    "PIPELINE_BLOCKED",
    "PIPELINE_FAIL",
]
