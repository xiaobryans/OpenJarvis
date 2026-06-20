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
# Natural coding intent detection (Python/local-first — no model call)
# ---------------------------------------------------------------------------

import re as _re

# Verbs that signal the user wants Jarvis to *act* on code
_CODING_VERBS = frozenset({
    "fix", "patch", "implement", "add", "create", "refactor", "debug",
    "test", "write", "update", "change", "modify", "build", "run",
    "execute", "commit", "push", "validate", "review", "check", "inspect",
    "lint", "format", "continue", "resume", "apply", "deploy", "revert",
    "rollback", "improve", "optimize",
})

# Objects that signal code-domain work
_CODING_OBJECTS = frozenset({
    "bug", "test", "feature", "code", "function", "method", "class",
    "module", "file", "route", "api", "endpoint", "schema", "migration",
    "sprint", "ticket", "pr", "diff", "patch", "error", "crash",
    "validation", "pipeline", "workflow", "regression", "failing",
    "build", "lint", "coverage", "null", "pointer", "exception",
    "traceback", "stack", "trace", "type", "attribute", "key",
    "import", "syntax", "assertion", "deprecation", "warning",
    "blocker", "report", "implementation", "fix",
})

# File extension pattern
_FILE_EXT_PAT = _re.compile(
    r'\b\w[\w./\-]*\.(?:py|ts|js|tsx|jsx|json|yaml|yml|toml|sh|rs|go|java|kt|rb|md)\b'
)

# Phrases that signal conceptual questions — skip pipeline routing
_CONCEPTUAL_STARTERS = (
    "what is", "what are", "what does", "what do",
    "how does", "how do", "how is", "how are",
    "why is", "why are", "why does", "why do",
    "explain", "tell me", "describe", "can you explain",
    "what's the difference", "when should", "where is",
)


def detect_coding_intent(message: str) -> bool:
    """Return True when message is a clear coding-action request.

    Uses only Python regex/keyword matching — zero model calls.
    False positives are safe (falls through to normal LLM path on error).
    Conservative: question/explanation starters always return False.

    Examples that return True:
      "fix this bug in user.py"
      "patch the failing test"
      "continue the current sprint"
      "run validation and commit"
      "review the diff and implement the fix"

    Examples that return False:
      "what is Python"
      "how does the pipeline work"
      "tell me about the project"
      "what time is it"
    """
    stripped = message.strip()
    lower = stripped.lower()

    # Conceptual question starters → never coding intent
    for starter in _CONCEPTUAL_STARTERS:
        if lower.startswith(starter):
            return False

    # Pure questions starting with interrogatives
    if _re.match(r'^(what|how|why|when|where|who|which|whose)\b', lower):
        return False

    words = set(_re.findall(r'\b[a-z]+\b', lower))
    has_verb = bool(words & _CODING_VERBS)
    has_object = bool(words & _CODING_OBJECTS)
    has_file = bool(_FILE_EXT_PAT.search(lower))

    # Strong: file reference + action verb
    if has_file and has_verb:
        return True

    # Strong: action verb + coding object
    if has_verb and has_object:
        return True

    # Continue/resume sprint or workflow
    if _re.search(r'\b(continue|resume)\b.{0,30}\b(sprint|workflow|task|coding)\b', lower):
        return True

    # Run validation and commit/push
    if _re.search(r'\brun\b.{0,20}\b(validation|test|tests)\b', lower):
        return True

    return False


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
# Multi-file patch descriptor
# ---------------------------------------------------------------------------


@dataclass
class FilePatch:
    """A minimal patch the worker proposes for a single file.

    Used with run_multi_file_patch() to describe multi-file coding tasks.
    """

    file_name: str
    original_content: str
    fixed_content: str
    rationale: str


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

    def run_task(
        self,
        prompt: str,
        file_hints: Optional[List[str]] = None,
        worker: Optional[object] = None,
        validation_pre: Optional[str] = None,
        validation_post: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> PipelineResult:
        """Autonomous task execution — worker identifies files and decides patches.

        Unlike run_with_patch() / run_multi_file_patch(), the WORKER decides:
          - which files to inspect (via identify_files() + CodingManager.plan())
          - what patch to apply (via generate_patch() on real file contents)

        The caller supplies ONLY the task prompt. No pre-baked patch content.

        Workflow:
          1. Classify task
          2. CodingManager.plan() → likely_files hint
          3. worker.identify_files() on actual repo files
          4. inspect_files() → read actual repo file contents
          5. worker.generate_patch() for each file (worker decides fix)
          6. Filter to files where worker made a decision
          7. Set up isolated temp git repo with original contents
          8. Apply worker patches
          9. Capture real git diff
          10. Pre/post validation
          11. Independent reviewer verdict
          12. Rollback + checkpoint

        Args:
            prompt: Natural-language task description (the only required input).
            file_hints: Optional explicit file paths to inspect. If not supplied,
                worker.identify_files() and CodingManager.plan() are used.
            worker: Optional TaskWorker override. Defaults to create_worker()
                (LocalPatternWorker if JARVIS_OPENROUTER_KEY not set).
            validation_pre: Shell command to run before patch (expected to fail).
            validation_post: Shell command to run after patch (expected to pass).
        """
        import tempfile
        import shutil

        t0 = time.time()
        run_id = uuid.uuid4().hex[:16]
        session_id = session_id or uuid.uuid4().hex[:16]
        task_id = task_id or uuid.uuid4().hex[:16]
        events: List[str] = []
        model_decisions: List[Dict[str, Any]] = []
        checkpoint_id: Optional[str] = None

        # ── Step 1: Classify ──────────────────────────────────────────────
        classification = classify_task(prompt)
        events.append(
            f"classify: category={classification['category']} risk={classification['risk_tier']}"
        )

        # ── Step 2: Create task worker ────────────────────────────────────
        from openjarvis.workbench.task_worker import create_worker, TaskWorker
        if worker is None:
            _worker: TaskWorker = create_worker()
        else:
            _worker = worker  # type: ignore[assignment]
        events.append(f"worker: {_worker.explain()[:80]}")

        # ── Step 3: Build task plan + identify files ──────────────────────
        plan_summary = f"Autonomous task: {prompt[:80]}"
        plan_data: Dict[str, Any] = {}
        likely_files: List[str] = list(file_hints or [])

        try:
            from openjarvis.workbench.coding_manager import CodingManager
            _cm_db = str(Path(self._cfg.db_path).parent) if self._cfg.db_path else None
            _cm = CodingManager(repo_path=self._cfg.repo_path, db_dir=_cm_db)
            _tp = _cm.plan(prompt, dry_run=True, repo_path=self._cfg.repo_path)
            plan_data = {
                "subtasks": len(_tp.subtasks),
                "likely_files": _tp.likely_files,
                "task_type": _tp.task_type,
                "approval_gates": _tp.approval_gates,
            }
            plan_summary = (
                f"Autonomous task: subtasks={len(_tp.subtasks)} type={_tp.task_type} | "
                f"{prompt[:60]}"
            )
            if _tp.likely_files:
                likely_files = (_tp.likely_files + likely_files)[:self._cfg.max_inspect_files]
            events.append(
                f"plan: subtasks={len(_tp.subtasks)} likely_files={_tp.likely_files[:3]} "
                f"type={_tp.task_type}"
            )
        except Exception as _pe:
            events.append(f"plan_skipped: {type(_pe).__name__}: {_pe!s:.80}")

        # Worker identifies additional files by analyzing the prompt
        worker_files = _worker.identify_files(prompt, self._cfg.repo_path)
        for f in worker_files:
            if f not in likely_files:
                likely_files.append(f)
        likely_files = likely_files[:self._cfg.max_inspect_files]
        events.append(f"identify_files: worker+plan={likely_files} (targeted, no broad scan)")

        # ── Step 4: Route to model tier ───────────────────────────────────
        decision = self._router.route(
            subtask_id=f"{task_id}-autonomous",
            tool_id="file_read",
            description=prompt[:120],
            session_id=session_id,
            task_id=task_id,
            category=classification["category"],
            high_trust=classification["is_risky"],
        )
        model_decisions.append(decision.to_dict())
        events.append(
            f"route: tier={decision.assigned_tier.value} model={decision.assigned_model}"
        )

        # ── Step 5: Read actual repo file contents ────────────────────────
        # file_contents: bounded preview for evidence/reporting (200 lines)
        # full_contents: complete file content for worker patch generation
        file_contents: Dict[str, str] = {}
        full_contents: Dict[str, str] = {}
        if likely_files:
            try:
                file_contents = inspect_files(
                    likely_files, repo_path=self._cfg.repo_path,
                    max_lines_per_file=200,
                )
                # Read full content for worker (needed for valid syntax-check of patch)
                _base = Path(self._cfg.repo_path)
                for fpath in likely_files:
                    _fp = _base / fpath
                    if _fp.exists():
                        try:
                            full_contents[fpath] = _fp.read_text(encoding="utf-8", errors="replace")
                        except Exception:
                            full_contents[fpath] = file_contents.get(fpath, "[READ_ERROR]")
                    else:
                        full_contents[fpath] = file_contents.get(fpath, "[FILE_NOT_FOUND]")
                readable = {k: v for k, v in file_contents.items()
                            if not v.startswith("[FILE_NOT_FOUND") and not v.startswith("[READ_ERROR")}
                events.append(
                    f"worker_read: {len(readable)}/{len(likely_files)} files read from repo"
                )
            except Exception as exc:
                events.append(f"inspect_error: {exc!s:.80}")
        else:
            events.append("identify_files: no files identified from prompt or plan")

        # ── Step 6: Worker generates patches (worker decides content) ─────
        # Worker uses full file content for accurate analysis and valid syntax.
        # file_contents (truncated) is kept for evidence reporting only.
        from openjarvis.workbench.task_worker import WorkerDecision
        worker_decisions: List[WorkerDecision] = []
        for fpath, content in full_contents.items():
            if content.startswith("[FILE_NOT_FOUND") or content.startswith("[READ_ERROR"):
                continue
            wd = _worker.generate_patch(prompt, fpath, content)
            if wd and wd.changed:
                worker_decisions.append(wd)
                events.append(
                    f"worker_patch: {fpath} — pattern={wd.pattern_used} "
                    f"confidence={wd.confidence:.2f} | {wd.rationale[:60]}"
                )
            else:
                events.append(f"worker_noop: {fpath} — no applicable pattern found")

        if not worker_decisions:
            # Worker found no applicable fix — HOLD with evidence
            self._event_log.push(
                session_id=session_id, task_id=task_id,
                event_type=EVENT_SUBTASK_DONE,
                title="Worker: no applicable pattern found",
                detail=f"Files inspected: {list(file_contents.keys())}",
                tone="warning",
            )
            return PipelineResult(
                run_id=run_id, task_id=task_id, session_id=session_id,
                verdict=PIPELINE_HOLD,
                classification=classification,
                plan_summary=f"{plan_summary} | worker: no pattern applied",
                files_inspected=likely_files,
                file_contents=file_contents,
                files_changed=[],
                patch_diff="",
                validation_outputs=[],
                reviewer_verdict=None,
                rollback_instruction="No changes made — nothing to roll back",
                model_decisions=model_decisions,
                loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
                events=events,
                duration_s=time.time() - t0,
                checkpoint_id=None,
            )

        # Build patch list from worker decisions (original = full content from repo)
        patches_to_apply = [
            (wd.file_path, wd.original_content, wd.patch_content)
            for wd in worker_decisions
        ]
        # Ensure file_contents evidence uses full content for worker-changed files
        for wd in worker_decisions:
            if wd.file_path not in file_contents or len(file_contents[wd.file_path]) < 100:
                file_contents[wd.file_path] = wd.original_content[:4096]
        files_targeted = [wd.file_path for wd in worker_decisions]

        tmp_dir = tempfile.mkdtemp(prefix="jarvis_run_task_")
        try:
            # ── Step 7: Set up isolated temp git repo ─────────────────────
            subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "jarvis@openjarvis.ai"],
                cwd=tmp_dir, capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Jarvis Worker"],
                cwd=tmp_dir, capture_output=True, check=True,
            )

            # Write ACTUAL repo file contents as originals
            for file_path_rel, original_content, _ in patches_to_apply:
                target = Path(tmp_dir) / file_path_rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(original_content, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True, check=True)
            subprocess.run(
                ["git", "commit", "-m", "original: actual repo content before worker patch"],
                cwd=tmp_dir, capture_output=True, check=True,
            )
            events.append(
                f"worker_setup: temp git repo with {len(patches_to_apply)} real file(s)"
            )

            # ── Step 8: Pre-fix validation ────────────────────────────────
            pre_validation_outputs: List[Dict[str, Any]] = []
            if validation_pre:
                pre_out = run_validation(
                    [validation_pre], cwd=tmp_dir, timeout=self._cfg.validation_timeout_s
                )
                pre_validation_outputs = pre_out
                pre_passed = all(v["passed"] for v in pre_out)
                events.append(
                    f"validation_pre: {'PASS (unexpected)' if pre_passed else 'FAIL (state confirmed)'}"
                )

            # ── Step 9: Apply worker-generated patches ────────────────────
            for file_path_rel, _, patch_content in patches_to_apply:
                target = Path(tmp_dir) / file_path_rel
                target.write_text(patch_content, encoding="utf-8")

            # ── Step 10: Capture real git diff ────────────────────────────
            diff_result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=tmp_dir, capture_output=True, text=True, timeout=10,
            )
            real_diff = diff_result.stdout.strip()
            diff_file_count = real_diff.count("diff --git")
            events.append(
                f"worker_diff: git diff captured ({len(real_diff)} chars, {diff_file_count} file(s))"
            )

            # ── Step 11: Post-fix validation + repair loop ────────────────
            post_cmds = [validation_post] if validation_post else []
            post_validation_outputs: List[Dict[str, Any]] = []
            loop = BoundedRepairLoop(max_attempts=self._cfg.max_loop_attempts)

            if post_cmds:
                while loop.can_retry():
                    vout = run_validation(
                        post_cmds, cwd=tmp_dir, timeout=self._cfg.validation_timeout_s
                    )
                    post_validation_outputs = vout
                    if all(v["passed"] for v in vout):
                        events.append(
                            f"validation_post: PASS ({len(vout)} cmd(s) — worker fix confirmed)"
                        )
                        break
                    failed = [v["command"] for v in vout if not v["passed"]]
                    events.append(
                        f"validation_post: FAIL attempt {len(loop.state.attempts)+1}: {failed}"
                    )
                    repair = loop.decide(
                        router=self._router,
                        subtask_id=f"{task_id}-post-validate",
                        tool_id="shell_exec_readonly",
                        session_id=session_id, task_id=task_id,
                        validation_failed=True, terminal_error=False,
                        error_message=str(failed),
                    )
                    if not repair.get("retry", False):
                        events.append(f"loop_cap: {repair.get('reason', 'max_attempts_exceeded')}")
                        break

            # ── Step 12: Rollback path (covers all changed files) ─────────
            rollback_cmds = " && ".join(
                f"git checkout HEAD -- {f}" for f in files_targeted
            )
            rollback = f"{rollback_cmds}  # Worker-generated patches; rollback all {len(files_targeted)} file(s)"
            events.append(f"rollback: {rollback[:100]}")

            # ── Step 13: Commit/push readiness ────────────────────────────
            commit_ready = (
                bool(real_diff) and (
                    not post_validation_outputs
                    or all(v["passed"] for v in post_validation_outputs)
                )
            )
            commit_cmd = None
            if commit_ready:
                commit_cmd = (
                    f"git add {' '.join(files_targeted)} && "
                    f"git commit -m 'worker: {prompt[:50].strip()}' && "
                    f"git push fork localhost-get-tool"
                )
                events.append(
                    f"commit_ready: YES (dry_run=True) — "
                    f"command: {commit_cmd}"
                )
            else:
                events.append("commit_ready: NO — diff empty or validation failed")

            # ── Step 14: Submit evidence to independent reviewer ──────────
            evidence = EvidenceBundle(
                task_id=task_id,
                session_id=session_id,
                worker_id=self._cfg.worker_id,
                prompt=prompt,
                plan_summary=plan_summary,
                files_inspected=likely_files,
                files_changed=files_targeted,
                patch_diff=real_diff,
                validation_commands=post_cmds,
                validation_outputs=post_validation_outputs,
                rollback_path=rollback,
                loop_state=loop.state.to_dict(),
                model_decisions=model_decisions,
                extra={
                    "pre_validation_outputs": pre_validation_outputs,
                    "worker_decisions": [
                        {
                            "file": wd.file_path,
                            "pattern": wd.pattern_used,
                            "confidence": wd.confidence,
                            "rationale": wd.rationale[:200],
                        }
                        for wd in worker_decisions
                    ],
                    "diff_file_count": diff_file_count,
                    "commit_ready": commit_ready,
                    "commit_cmd": commit_cmd,
                    "plan_data": plan_data,
                },
            )

            reviewer_verdict = None
            final_verdict = PIPELINE_HOLD

            try:
                reviewer_verdict = self._reviewer.review(evidence)
                final_verdict = reviewer_verdict.verdict.value
                events.append(
                    f"reviewer: verdict={final_verdict} reasons={reviewer_verdict.reasons[:2]}"
                )
            except ValueError as exc:
                events.append(f"reviewer_error: {exc}")
                final_verdict = PIPELINE_BLOCKED

            self._event_log.push(
                session_id=session_id, task_id=task_id,
                event_type=EVENT_EXECUTION_COMPLETE,
                title=f"Autonomous task complete: {final_verdict}",
                detail=f"run_id={run_id} files={len(patches_to_apply)} diff={len(real_diff)}",
                tone="success" if final_verdict == PIPELINE_PASS else "warning",
            )

            if final_verdict == PIPELINE_PASS:
                cp = self._checkpoint.save_checkpoint(
                    session_id=session_id,
                    task_id=task_id,
                    label=f"run-task-{run_id}",
                    evidence=json.dumps({
                        "files_changed": files_targeted,
                        "diff_chars": len(real_diff),
                        "worker_decisions": [
                            {"file": wd.file_path, "pattern": wd.pattern_used}
                            for wd in worker_decisions
                        ],
                        "commit_ready": commit_ready,
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
                files_inspected=likely_files,
                file_contents=file_contents,
                files_changed=files_targeted,
                patch_diff=real_diff,
                validation_outputs=post_validation_outputs,
                reviewer_verdict=reviewer_verdict.to_dict() if reviewer_verdict else None,
                rollback_instruction=rollback,
                model_decisions=model_decisions,
                loop_state=loop.state.to_dict(),
                events=events,
                duration_s=time.time() - t0,
                checkpoint_id=checkpoint_id if final_verdict == PIPELINE_PASS else None,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def run_multi_file_patch(
        self,
        prompt: str,
        patches: "List[FilePatch]",
        validation_pre: Optional[str] = None,
        validation_post: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> PipelineResult:
        """Multi-step/multi-file patch flow integrating CodingManager.plan().

        Full workflow — no Workbench UI required:
          1.  Classify task (classify_task)
          2.  Create real task plan (CodingManager.plan → TaskPlan)
          3.  Identify necessary files from plan + patches (targeted, no broad scan)
          4.  Set up isolated temp git repo with all original files
          5.  Worker reads all original files (file_contents)
          6.  Pre-fix validation (proves bugs existed)
          7.  Worker applies all patches (file writes)
          8.  Capture combined real git diff (all changed files)
          9.  Post-fix validation (proves all fixes work)
          10. BoundedRepairLoop guards validation attempts
          11. Rollback path covers all changed files
          12. Submit multi-file evidence to independent reviewer
          13. Return PASS/HOLD/BLOCKED/FAIL + checkpoint if PASS
          14. Isolated temp dir cleaned up — main repo never touched

        Exits without changing any production file. Commit/push is reported as
        ready when validation passes; actual commit/push is opt-in per
        PipelineConfig.dry_run and task-scoped automation rule.
        """
        import tempfile
        import shutil

        t0 = time.time()
        run_id = uuid.uuid4().hex[:16]
        session_id = session_id or uuid.uuid4().hex[:16]
        task_id = task_id or uuid.uuid4().hex[:16]
        events: List[str] = []
        model_decisions: List[Dict[str, Any]] = []
        checkpoint_id: Optional[str] = None

        # ── Step 1: Classify ──────────────────────────────────────────────
        classification = classify_task(prompt)
        events.append(
            f"classify: category={classification['category']} risk={classification['risk_tier']}"
        )

        # ── Step 2: Build task plan via CodingManager ─────────────────────
        # CodingManager.plan() provides: likely_files, subtasks, validation_commands,
        # approval_gates, risks. Used for evidence and reviewer context.
        plan_summary = f"Multi-file patch: {len(patches)} file(s) | {prompt[:80]}"
        plan_data: Dict[str, Any] = {}
        try:
            from openjarvis.workbench.coding_manager import CodingManager
            _cm_db = str(Path(self._cfg.db_path).parent) if self._cfg.db_path else None
            _cm = CodingManager(
                repo_path=self._cfg.repo_path,
                db_dir=_cm_db,
            )
            _tp = _cm.plan(prompt, dry_run=True, repo_path=self._cfg.repo_path)
            plan_data = {
                "subtasks": len(_tp.subtasks),
                "likely_files": _tp.likely_files,
                "validation_commands": _tp.validation_commands,
                "approval_gates": _tp.approval_gates,
                "risks": _tp.risks,
                "task_type": _tp.task_type,
            }
            plan_summary = (
                f"Multi-file patch: {len(patches)} file(s) | "
                f"subtasks={len(_tp.subtasks)} type={_tp.task_type} | "
                f"{prompt[:60]}"
            )
            events.append(
                f"plan: subtasks={len(_tp.subtasks)} "
                f"likely_files={_tp.likely_files[:3]} "
                f"type={_tp.task_type}"
            )
        except Exception as _plan_exc:
            events.append(f"plan_skipped: {type(_plan_exc).__name__}: {_plan_exc!s:.80}")

        # ── Step 3: Identify files (patches list + plan hints) ────────────
        files_targeted = [p.file_name for p in patches]
        events.append(f"identify_files: targeted={files_targeted} (no broad scan)")

        # ── Step 4: Route to model tier ───────────────────────────────────
        decision = self._router.route(
            subtask_id=f"{task_id}-multi-patch",
            tool_id="file_read",
            description=prompt[:120],
            session_id=session_id,
            task_id=task_id,
            category=classification["category"],
            high_trust=classification["is_risky"],
        )
        model_decisions.append(decision.to_dict())
        events.append(
            f"route: tier={decision.assigned_tier.value} model={decision.assigned_model}"
        )

        tmp_dir = tempfile.mkdtemp(prefix="jarvis_multi_patch_")
        try:
            # ── Step 5: Set up isolated temp git repo ─────────────────────
            subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "jarvis@openjarvis.ai"],
                cwd=tmp_dir, capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Jarvis Worker"],
                cwd=tmp_dir, capture_output=True, check=True,
            )

            # Write all original (buggy) files and commit them
            file_contents: Dict[str, str] = {}
            for p in patches:
                target = Path(tmp_dir) / p.file_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(p.original_content, encoding="utf-8")
                file_contents[p.file_name] = p.original_content[:4096]

            subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True, check=True)
            subprocess.run(
                ["git", "commit", "-m", "initial: original (buggy) versions"],
                cwd=tmp_dir, capture_output=True, check=True,
            )
            events.append(
                f"worker_setup: temp git repo created, {len(patches)} file(s) committed"
            )

            # ── Step 6: Worker reads original files (real file_contents) ──
            for p in patches:
                events.append(f"worker_read: {p.file_name} ({len(p.original_content)} chars)")

            # ── Step 7: Pre-fix validation ─────────────────────────────────
            pre_validation_outputs: List[Dict[str, Any]] = []
            if validation_pre:
                pre_out = run_validation(
                    [validation_pre], cwd=tmp_dir, timeout=self._cfg.validation_timeout_s
                )
                pre_validation_outputs = pre_out
                pre_passed = all(v["passed"] for v in pre_out)
                events.append(
                    f"validation_pre: {'PASS (unexpected)' if pre_passed else 'FAIL (confirms bugs exist)'}"
                )
                self._event_log.push(
                    session_id=session_id, task_id=task_id,
                    event_type=EVENT_SUBTASK_DONE,
                    title=(
                        f"Pre-fix validation: {'UNEXPECTED PASS' if pre_passed else 'FAIL confirms bugs'}"
                    ),
                    detail=(pre_out[0]["output"][:200] if pre_out else ""),
                    tone="warning" if pre_passed else "info",
                )

            # ── Step 8: Worker applies all patches ────────────────────────
            for p in patches:
                target = Path(tmp_dir) / p.file_name
                target.write_text(p.fixed_content, encoding="utf-8")
                events.append(f"worker_patch: fix applied to {p.file_name} | {p.rationale[:60]}")
                self._event_log.push(
                    session_id=session_id, task_id=task_id,
                    event_type=EVENT_EXECUTION_STARTED,
                    title=f"Worker patched {p.file_name}",
                    detail=p.rationale[:200],
                    tone="info",
                )

            # ── Step 9: Capture real multi-file git diff ──────────────────
            diff_result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=tmp_dir, capture_output=True, text=True, timeout=10,
            )
            real_diff = diff_result.stdout.strip()
            diff_file_count = real_diff.count("diff --git")
            events.append(
                f"worker_diff: git diff captured ({len(real_diff)} chars, {diff_file_count} file(s))"
            )

            # ── Step 10: Post-fix validation + repair loop ────────────────
            post_cmds = [validation_post] if validation_post else []
            post_validation_outputs: List[Dict[str, Any]] = []
            loop = BoundedRepairLoop(max_attempts=self._cfg.max_loop_attempts)

            if post_cmds:
                while loop.can_retry():
                    vout = run_validation(
                        post_cmds, cwd=tmp_dir, timeout=self._cfg.validation_timeout_s
                    )
                    post_validation_outputs = vout
                    all_passed = all(v["passed"] for v in vout)

                    if all_passed:
                        events.append(
                            f"validation_post: PASS ({len(vout)} cmd(s) — all fixes confirmed)"
                        )
                        break

                    failed = [v["command"] for v in vout if not v["passed"]]
                    events.append(
                        f"validation_post: FAIL attempt {len(loop.state.attempts)+1}: {failed}"
                    )
                    self._event_log.push(
                        session_id=session_id, task_id=task_id,
                        event_type=EVENT_VALIDATION_FAILED,
                        title="Post-fix validation failed",
                        detail=str(failed)[:200],
                        tone="error",
                    )
                    repair = loop.decide(
                        router=self._router,
                        subtask_id=f"{task_id}-post-validate",
                        tool_id="shell_exec_readonly",
                        session_id=session_id, task_id=task_id,
                        validation_failed=True, terminal_error=False,
                        error_message=str(failed),
                    )
                    if not repair.get("retry", False):
                        events.append(f"loop_cap: {repair.get('reason', 'max_attempts_exceeded')}")
                        break

            # ── Step 11: Rollback path (all changed files) ────────────────
            rollback_cmds = " && ".join(
                f"git checkout HEAD -- {p.file_name}" for p in patches
            )
            rollback = f"{rollback_cmds}  # Revert all {len(patches)} file(s) in temp repo"
            self._event_log.push(
                session_id=session_id, task_id=task_id,
                event_type=EVENT_ROLLBACK_GUIDANCE,
                title=f"Rollback covers all {len(patches)} changed files",
                detail=rollback[:200],
                tone="info",
            )
            events.append(f"rollback: {rollback[:100]}")

            # ── Step 12: Commit/push readiness ────────────────────────────
            commit_ready = (
                post_validation_outputs and all(v["passed"] for v in post_validation_outputs)
            )
            commit_cmd = (
                f"git add {' '.join(p.file_name for p in patches)} && "
                f"git commit -m 'fix: {prompt[:60].strip()}' && "
                f"git push fork {self._cfg.repo_path or 'HEAD'}"
                if commit_ready else None
            )
            if commit_ready and not self._cfg.dry_run:
                events.append("commit_ready: YES (dry_run=False — would commit + push)")
            elif commit_ready:
                events.append(f"commit_ready: YES (dry_run=True — command: {(commit_cmd or '')[:80]})")
            else:
                events.append("commit_ready: NO — validation failed or no post-validation")

            # ── Step 13: Submit evidence to independent reviewer ──────────
            evidence = EvidenceBundle(
                task_id=task_id,
                session_id=session_id,
                worker_id=self._cfg.worker_id,
                prompt=prompt,
                plan_summary=plan_summary,
                files_inspected=files_targeted,
                files_changed=files_targeted,
                patch_diff=real_diff,
                validation_commands=post_cmds,
                validation_outputs=post_validation_outputs,
                rollback_path=rollback,
                loop_state=loop.state.to_dict(),
                model_decisions=model_decisions,
                extra={
                    "pre_validation_outputs": pre_validation_outputs,
                    "bug_confirmed": (
                        any(not v["passed"] for v in pre_validation_outputs)
                        if pre_validation_outputs else None
                    ),
                    "diff_file_count": diff_file_count,
                    "diff_char_count": len(real_diff),
                    "plan_data": plan_data,
                    "commit_ready": commit_ready,
                    "commit_cmd": commit_cmd,
                },
            )

            reviewer_verdict = None
            final_verdict = PIPELINE_HOLD

            try:
                reviewer_verdict = self._reviewer.review(evidence)
                final_verdict = reviewer_verdict.verdict.value
                events.append(
                    f"reviewer: verdict={final_verdict} reasons={reviewer_verdict.reasons[:2]}"
                )
            except ValueError as exc:
                events.append(f"reviewer_error: {exc}")
                final_verdict = PIPELINE_BLOCKED

            # ── Step 14: Log and checkpoint ───────────────────────────────
            self._event_log.push(
                session_id=session_id, task_id=task_id,
                event_type=EVENT_EXECUTION_COMPLETE,
                title=f"Multi-file patch pipeline complete: {final_verdict}",
                detail=f"run_id={run_id} files={len(patches)} diff_chars={len(real_diff)}",
                tone="success" if final_verdict == PIPELINE_PASS else "warning",
            )

            if final_verdict == PIPELINE_PASS:
                cp = self._checkpoint.save_checkpoint(
                    session_id=session_id,
                    task_id=task_id,
                    label=f"multi-patch-{run_id}",
                    evidence=json.dumps({
                        "file_names": files_targeted,
                        "diff_file_count": diff_file_count,
                        "diff_chars": len(real_diff),
                        "post_validation": post_validation_outputs,
                        "commit_ready": commit_ready,
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
                files_inspected=files_targeted,
                file_contents=file_contents,
                files_changed=files_targeted,
                patch_diff=real_diff,
                validation_outputs=post_validation_outputs,
                reviewer_verdict=reviewer_verdict.to_dict() if reviewer_verdict else None,
                rollback_instruction=rollback,
                model_decisions=model_decisions,
                loop_state=loop.state.to_dict(),
                events=events,
                duration_s=time.time() - t0,
                checkpoint_id=checkpoint_id if final_verdict == PIPELINE_PASS else None,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def run_with_patch(
        self,
        prompt: str,
        file_name: str,
        original_content: str,
        fixed_content: str,
        rationale: str,
        validation_pre: Optional[str] = None,
        validation_post: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> PipelineResult:
        """Real multi-step patch flow on an isolated temp git repo.

        Steps:
          1. Classify task
          2. Create isolated temp git repo with original (buggy) file
          3. Worker reads original file (real file_contents)
          4. Worker applies fix (write corrected content)
          5. Capture real git diff
          6. Run pre-fix validation (expected to fail — proves bug exists)
          7. Run post-fix validation (expected to pass — proves fix works)
          8. Submit complete evidence bundle to independent reviewer
          9. Return verdict + rollback path

        The worker never self-certifies. The reviewer is always a separate object.
        Rollback: git checkout HEAD -- <file> in the temp repo.
        No changes are made to the real repository.
        """
        import tempfile
        import shutil

        t0 = time.time()
        run_id = uuid.uuid4().hex[:16]
        session_id = session_id or uuid.uuid4().hex[:16]
        task_id = task_id or uuid.uuid4().hex[:16]
        events: List[str] = []
        model_decisions: List[Dict[str, Any]] = []
        checkpoint_id: Optional[str] = None

        # ── Step 1: Classify ──────────────────────────────────────────────
        classification = classify_task(prompt)
        events.append(f"classify: category={classification['category']} risk={classification['risk_tier']}")

        # ── Step 2: Set up isolated temp git repo ─────────────────────────
        tmp_dir = tempfile.mkdtemp(prefix="jarvis_patch_")
        try:
            # Init git repo in temp dir
            subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "jarvis@openjarvis.ai"],
                           cwd=tmp_dir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Jarvis Worker"],
                           cwd=tmp_dir, capture_output=True, check=True)

            # Write original (buggy) file and commit it
            target = Path(tmp_dir) / file_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(original_content, encoding="utf-8")
            subprocess.run(["git", "add", file_name], cwd=tmp_dir, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "initial: original (buggy) version"],
                           cwd=tmp_dir, capture_output=True, check=True)
            events.append(f"worker_setup: temp git repo created, original committed ({len(original_content)} chars)")

            # ── Step 3: Route to model tier ──────────────────────────────
            decision = self._router.route(
                subtask_id=f"{task_id}-patch",
                tool_id="file_read",
                description=prompt[:120],
                session_id=session_id,
                task_id=task_id,
                category=classification["category"],
                high_trust=classification["is_risky"],
            )
            model_decisions.append(decision.to_dict())
            events.append(f"route: tier={decision.assigned_tier.value} model={decision.assigned_model}")

            # ── Step 4: Worker reads original file (real file_contents) ──
            file_contents = {file_name: original_content[:4096]}
            events.append(f"worker_read: {file_name} read ({len(original_content)} chars)")

            # ── Step 5: Pre-fix validation (should fail — proves bug) ─────
            pre_validation_outputs: List[Dict[str, Any]] = []
            if validation_pre:
                pre_out = run_validation([validation_pre], cwd=tmp_dir, timeout=self._cfg.validation_timeout_s)
                pre_validation_outputs = pre_out
                pre_passed = all(v["passed"] for v in pre_out)
                events.append(
                    f"validation_pre: {'PASS (unexpected)' if pre_passed else 'FAIL (confirms bug exists)'}"
                )
                self._event_log.push(
                    session_id=session_id, task_id=task_id,
                    event_type=EVENT_SUBTASK_DONE if not pre_passed else EVENT_VALIDATION_FAILED,
                    title=f"Pre-fix validation: {'bug confirmed' if not pre_passed else 'WARNING: pre-fix passed'}",
                    detail=pre_out[0]["output"][:200] if pre_out else "",
                    tone="info" if not pre_passed else "warning",
                )

            # ── Step 6: Worker applies fix ────────────────────────────────
            target.write_text(fixed_content, encoding="utf-8")
            events.append(f"worker_patch: fix applied to {file_name}")
            self._event_log.push(
                session_id=session_id, task_id=task_id,
                event_type=EVENT_EXECUTION_STARTED,
                title=f"Worker applied patch to {file_name}",
                detail=rationale[:200],
                tone="info",
            )

            # ── Step 7: Capture real git diff ─────────────────────────────
            diff_result = subprocess.run(
                ["git", "diff", "HEAD", "--", file_name],
                cwd=tmp_dir, capture_output=True, text=True, timeout=10,
            )
            real_diff = diff_result.stdout.strip()
            events.append(f"worker_diff: git diff captured ({len(real_diff)} chars)")

            # ── Step 8: Post-fix validation (should pass — proves fix) ────
            post_cmds = [validation_post] if validation_post else []
            post_validation_outputs: List[Dict[str, Any]] = []
            loop = BoundedRepairLoop(max_attempts=self._cfg.max_loop_attempts)

            if post_cmds:
                while loop.can_retry():
                    vout = run_validation(post_cmds, cwd=tmp_dir, timeout=self._cfg.validation_timeout_s)
                    post_validation_outputs = vout
                    all_passed = all(v["passed"] for v in vout)

                    if all_passed:
                        events.append(f"validation_post: PASS ({len(vout)} cmd(s) — fix confirmed)")
                        break

                    failed = [v["command"] for v in vout if not v["passed"]]
                    events.append(f"validation_post: FAIL attempt {len(loop.state.attempts)+1}: {failed}")
                    self._event_log.push(
                        session_id=session_id, task_id=task_id,
                        event_type=EVENT_VALIDATION_FAILED,
                        title="Post-fix validation failed",
                        detail=str(failed)[:200],
                        tone="error",
                    )
                    repair = loop.decide(
                        router=self._router,
                        subtask_id=f"{task_id}-post-validate",
                        tool_id="shell_exec_readonly",
                        session_id=session_id, task_id=task_id,
                        validation_failed=True, terminal_error=False,
                        error_message=str(failed),
                    )
                    if not repair.get("retry", False):
                        events.append(f"loop_cap: {repair.get('reason', 'max_attempts_exceeded')}")
                        break

            # ── Step 9: Rollback path ─────────────────────────────────────
            rollback = (
                f"git checkout HEAD -- {file_name}  "
                f"# Revert worker patch in temp repo; original: '{original_content[:60].strip()}'"
            )
            self._event_log.push(
                session_id=session_id, task_id=task_id,
                event_type=EVENT_ROLLBACK_GUIDANCE,
                title="Rollback path surfaced",
                detail=rollback[:200],
                tone="info",
            )
            events.append(f"rollback: {rollback[:80]}")

            # ── Step 10: Submit evidence to independent reviewer ──────────
            # Reviewer sees only POST-fix validation (pass/fail of the fix itself).
            # Pre-fix validation is recorded in extra{} as proof the bug existed.
            evidence = EvidenceBundle(
                task_id=task_id,
                session_id=session_id,
                worker_id=self._cfg.worker_id,
                prompt=prompt,
                plan_summary=(
                    f"Patch task: {classification['category']} | "
                    f"file={file_name} | rationale={rationale[:100]}"
                ),
                files_inspected=[file_name],
                files_changed=[file_name],
                patch_diff=real_diff,
                validation_commands=([validation_post] if validation_post else []),
                validation_outputs=post_validation_outputs,
                rollback_path=rollback,
                loop_state=loop.state.to_dict(),
                model_decisions=model_decisions,
                extra={
                    "pre_validation_outputs": pre_validation_outputs,
                    "bug_confirmed": (
                        any(not v["passed"] for v in pre_validation_outputs)
                        if pre_validation_outputs else None
                    ),
                    "diff_char_count": len(real_diff),
                },
            )
            all_validation = pre_validation_outputs + post_validation_outputs

            reviewer_verdict: Optional[ReviewVerdict] = None
            final_verdict = PIPELINE_HOLD

            try:
                reviewer_verdict = self._reviewer.review(evidence)
                final_verdict = reviewer_verdict.verdict.value
                events.append(f"reviewer: verdict={final_verdict} reasons={reviewer_verdict.reasons[:2]}")
            except ValueError as exc:
                events.append(f"reviewer_error: {exc}")
                final_verdict = PIPELINE_BLOCKED

            # ── Step 11: Log completion ────────────────────────────────────
            self._event_log.push(
                session_id=session_id, task_id=task_id,
                event_type=EVENT_EXECUTION_COMPLETE,
                title=f"Patch pipeline complete: {final_verdict}",
                detail=f"run_id={run_id} diff_chars={len(real_diff)}",
                tone="success" if final_verdict == PIPELINE_PASS else "warning",
            )

            # ── Step 12: Checkpoint on PASS ───────────────────────────────
            if final_verdict == PIPELINE_PASS:
                cp = self._checkpoint.save_checkpoint(
                    session_id=session_id,
                    task_id=task_id,
                    label=f"patch-{run_id}",
                    evidence=json.dumps({
                        "file_name": file_name,
                        "diff_chars": len(real_diff),
                        "post_validation": post_validation_outputs,
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
                plan_summary=evidence.plan_summary,
                files_inspected=[file_name],
                file_contents=file_contents,
                files_changed=[file_name],
                patch_diff=real_diff,
                validation_outputs=all_validation,
                reviewer_verdict=reviewer_verdict.to_dict() if reviewer_verdict else None,
                rollback_instruction=rollback,
                model_decisions=model_decisions,
                loop_state=loop.state.to_dict(),
                events=events,
                duration_s=time.time() - t0,
                checkpoint_id=checkpoint_id if final_verdict == PIPELINE_PASS else None,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def close(self) -> None:
        self._router.close()
        self._checkpoint.close()
        self._event_log.close()
        self._reviewer.close()


__all__ = [
    "CodingPipeline",
    "PipelineConfig",
    "PipelineResult",
    "FilePatch",
    "classify_task",
    "detect_coding_intent",
    "inspect_files",
    "PIPELINE_PASS",
    "PIPELINE_HOLD",
    "PIPELINE_BLOCKED",
    "PIPELINE_FAIL",
]
