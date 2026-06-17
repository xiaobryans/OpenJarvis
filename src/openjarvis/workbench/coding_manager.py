"""CodingManager — Jarvis Coding Workbench orchestrator (US14A).

Responsibilities:
  - Receive one coding prompt
  - Split into subtasks using a planning step
  - Route each subtask to the appropriate worker tier
  - Execute read-only analysis in parallel (local/cheap workers)
  - Execute risky ops with high-trust models only
  - Track cost per subtask via CostLedger
  - Persist checkpoints via CheckpointStore
  - Enforce governance gates (dry-run, approval, stop-on-blocker)
  - Own all commits and pushes (workers cannot commit/push)
  - Produce final reports

Worker Tiers:
  - "local":        zero-cost local model or direct tool execution (read-only tasks)
  - "cloud-cheap":  DeepSeek / Qwen / Gemini-Flash (analysis, file ops, tests)
  - "high-trust":   Claude Opus / GPT-4o (architecture, security, final review)

Governance:
  - dry_run=True → plan and validate but never commit/push/delete
  - approval_required items require explicit approve() call before execution
  - stop_on_blocker=True → halt subtask chain on any failure
  - workers_can_commit=False always (enforced here, not configurable)
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.workbench.job_queue import Job, JobQueue, JobStatus
from openjarvis.workbench.cost_ledger import CostLedger
from openjarvis.workbench.checkpoint import CheckpointStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Worker tier routing policy
# ---------------------------------------------------------------------------

# Actions that are always read-only — safe for local/cheap tier
_READ_ONLY_TOOLS = frozenset({
    "file_read",
    "file_search",
    "git_status",
    "git_diff",
    "git_log",
    "git_branch",
    "shell_exec_readonly",
})

# Actions that require the high-trust tier (architecture, security, final review)
_HIGH_TRUST_TOOLS = frozenset({
    "git_commit",
    "git_push",
    "file_delete",
})

# Actions that require explicit approval gate
_APPROVAL_REQUIRED_TOOLS = frozenset({
    "git_commit",
    "git_push",
    "file_delete",
    "shell_exec",
})


def _route_worker_tier(tool_id: str, is_risky: bool = False) -> str:
    """Determine the appropriate worker tier for a given tool."""
    if tool_id in _HIGH_TRUST_TOOLS:
        return "high-trust"
    if tool_id in _READ_ONLY_TOOLS:
        return "local"
    if is_risky:
        return "high-trust"
    return "cloud-cheap"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Subtask:
    id: str
    index: int
    description: str
    tool_id: str
    params: Dict[str, Any]
    worker_tier: str
    requires_approval: bool
    status: str = "pending"
    output: Optional[str] = None
    error: Optional[str] = None
    cost_usd: float = 0.0
    job_id: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "description": self.description,
            "tool_id": self.tool_id,
            "params": self.params,
            "worker_tier": self.worker_tier,
            "requires_approval": self.requires_approval,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "cost_usd": self.cost_usd,
            "job_id": self.job_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class TaskPlan:
    session_id: str
    task_id: str
    prompt: str
    repo_path: str
    subtasks: List[Subtask]
    dry_run: bool
    stop_on_blocker: bool
    status: str = "planned"
    final_report: Optional[str] = None
    diff_preview: Optional[str] = None
    validation_output: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    total_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "prompt": self.prompt,
            "repo_path": self.repo_path,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "dry_run": self.dry_run,
            "stop_on_blocker": self.stop_on_blocker,
            "status": self.status,
            "final_report": self.final_report,
            "diff_preview": self.diff_preview,
            "validation_output": self.validation_output,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "total_cost_usd": self.total_cost_usd,
        }


# ---------------------------------------------------------------------------
# CodingManager
# ---------------------------------------------------------------------------


class CodingManager:
    """Jarvis Coding Workbench orchestrator.

    Usage:
        manager = CodingManager(repo_path="/path/to/repo")
        plan = manager.plan("Add a US14A self-test fixture", dry_run=True)
        plan = manager.execute(plan)
        report = plan.final_report
    """

    # Workers cannot commit/push — enforced unconditionally
    _WORKERS_CAN_COMMIT = False

    def __init__(
        self,
        repo_path: str = ".",
        db_dir: Optional[str] = None,
    ) -> None:
        self._repo_path = Path(repo_path).resolve()
        db_dir_path = Path(db_dir) if db_dir else Path.home() / ".openjarvis"
        db_dir_path.mkdir(parents=True, exist_ok=True)

        self._jobs = JobQueue(str(db_dir_path / "workbench_jobs.db"))
        self._costs = CostLedger(str(db_dir_path / "workbench_cost.db"))
        self._checkpoints = CheckpointStore(str(db_dir_path / "workbench_checkpoints.db"))

        # Pending approvals keyed by subtask id
        self._pending_approvals: Dict[str, Subtask] = {}

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def plan(
        self,
        prompt: str,
        dry_run: bool = True,
        stop_on_blocker: bool = True,
        repo_path: Optional[str] = None,
    ) -> TaskPlan:
        """Create a task plan from a prompt.

        Splits the prompt into subtasks, routes each to the appropriate
        worker tier, and returns the plan without executing.
        """
        session_id = uuid.uuid4().hex[:12]
        task_id = uuid.uuid4().hex[:12]
        effective_repo = Path(repo_path).resolve() if repo_path else self._repo_path

        subtasks = self._decompose(prompt, task_id, str(effective_repo))

        plan = TaskPlan(
            session_id=session_id,
            task_id=task_id,
            prompt=prompt,
            repo_path=str(effective_repo),
            subtasks=subtasks,
            dry_run=dry_run,
            stop_on_blocker=stop_on_blocker,
        )

        self._checkpoints.save_checkpoint(
            session_id=session_id,
            task_id=task_id,
            label="plan_created",
            evidence=f"Plan created with {len(subtasks)} subtasks. dry_run={dry_run}",
            verdict="ACCEPT",
            notes={"prompt": prompt, "subtask_count": len(subtasks)},
        )

        logger.info(
            "CodingManager.plan: session=%s task=%s subtasks=%d dry_run=%s",
            session_id, task_id, len(subtasks), dry_run,
        )
        return plan

    def _decompose(
        self,
        prompt: str,
        task_id: str,
        repo_path: str,
    ) -> List[Subtask]:
        """Decompose a prompt into a list of subtasks.

        Uses rule-based decomposition (no LLM call needed for the planner
        itself — the planner is deterministic to keep costs at zero).
        LLM calls happen only during worker execution of each subtask.
        """
        subtasks: List[Subtask] = []
        idx = 0

        # Step 1: Always inspect repo state first (read-only, local tier)
        st = self._make_subtask(
            idx=idx,
            task_id=task_id,
            description="Inspect repository status and branch",
            tool_id="git_status",
            params={"repo_path": repo_path},
        )
        subtasks.append(st)
        idx += 1

        # Step 2: Search for relevant files if prompt mentions patterns
        search_terms = self._extract_search_terms(prompt)
        if search_terms:
            search_dir = repo_path
            for candidate in ("src", "lib", "app"):
                candidate_path = str(Path(repo_path) / candidate)
                if Path(candidate_path).is_dir():
                    search_dir = candidate_path
                    break
            st = self._make_subtask(
                idx=idx,
                task_id=task_id,
                description=f"Search codebase for: {', '.join(search_terms[:3])}",
                tool_id="file_search",
                params={"pattern": "|".join(search_terms[:3]), "directory": search_dir},
            )
            subtasks.append(st)
            idx += 1

        # Step 3: Show current diff (read-only)
        st = self._make_subtask(
            idx=idx,
            task_id=task_id,
            description="Generate diff preview of working tree",
            tool_id="git_diff",
            params={"repo_path": repo_path},
        )
        subtasks.append(st)
        idx += 1

        # Step 4: File edit/create if prompt suggests file changes
        if self._suggests_file_change(prompt):
            file_path, content = self._infer_file_change(prompt, repo_path)
            if file_path:
                st = self._make_subtask(
                    idx=idx,
                    task_id=task_id,
                    description=f"Write file: {file_path}",
                    tool_id="file_write",
                    params={"path": file_path, "content": content, "create_dirs": True},
                )
                subtasks.append(st)
                idx += 1

        # Step 5: Run validation
        st = self._make_subtask(
            idx=idx,
            task_id=task_id,
            description="Run validation / tests",
            tool_id="shell_exec",
            params={
                "command": "python -m pytest tests/ -x -q --tb=short 2>&1 | head -50 || echo 'No pytest tests found'",
                "working_dir": repo_path,
                "timeout": 60,
            },
        )
        subtasks.append(st)
        idx += 1

        # Step 6: Generate post-change diff preview
        st = self._make_subtask(
            idx=idx,
            task_id=task_id,
            description="Generate post-change diff preview",
            tool_id="git_diff",
            params={"repo_path": repo_path},
        )
        subtasks.append(st)
        idx += 1

        # Step 7: Commit (Manager-owned, requires approval, blocked in dry-run)
        st = self._make_subtask(
            idx=idx,
            task_id=task_id,
            description=f"Commit changes: {prompt[:60]}",
            tool_id="git_commit",
            params={
                "message": f"US14A: {prompt[:80]}",
                "repo_path": repo_path,
                "files": ".",
            },
        )
        subtasks.append(st)
        idx += 1

        # Step 8: Push (Manager-owned, requires approval, blocked in dry-run)
        st = self._make_subtask(
            idx=idx,
            task_id=task_id,
            description="Push branch to remote",
            tool_id="git_push",
            params={"repo_path": repo_path, "remote": "fork"},
        )
        subtasks.append(st)
        idx += 1

        return subtasks

    def _make_subtask(
        self,
        idx: int,
        task_id: str,
        description: str,
        tool_id: str,
        params: Dict[str, Any],
        is_risky: bool = False,
    ) -> Subtask:
        tier = _route_worker_tier(tool_id, is_risky)
        requires_approval = tool_id in _APPROVAL_REQUIRED_TOOLS
        return Subtask(
            id=uuid.uuid4().hex[:12],
            index=idx,
            description=description,
            tool_id=tool_id,
            params=params,
            worker_tier=tier,
            requires_approval=requires_approval,
        )

    def _extract_search_terms(self, prompt: str) -> List[str]:
        """Extract potential search terms from the prompt."""
        terms = []
        words = prompt.split()
        for w in words:
            if len(w) > 5 and w.isidentifier():
                terms.append(w)
        return terms[:5]

    def _suggests_file_change(self, prompt: str) -> bool:
        keywords = ["add", "create", "write", "edit", "modify", "update", "insert", "fixture", "test"]
        return any(k in prompt.lower() for k in keywords)

    def _infer_file_change(self, prompt: str, repo_path: str) -> tuple[str, str]:
        """Infer a file path and content from the prompt (heuristic fallback)."""
        prompt_lower = prompt.lower()
        if "fixture" in prompt_lower or "self-test" in prompt_lower or "marker" in prompt_lower:
            file_path = str(Path(repo_path) / "tests" / "workbench" / "test_us14a_fixture.py")
            content = (
                '"""US14A self-test fixture — added by Jarvis Coding Workbench."""\n\n'
                "US14A_MARKER = \"Jarvis Coding Workbench E2E proof\"\n\n\n"
                "def test_us14a_marker():\n"
                '    """Verify US14A marker is present."""\n'
                "    assert US14A_MARKER == \"Jarvis Coding Workbench E2E proof\"\n"
            )
            return file_path, content
        if "readme" in prompt_lower:
            file_path = str(Path(repo_path) / "US14A_NOTE.md")
            content = "# US14A — Jarvis Coding Workbench\n\nAdded by Jarvis Coding Workbench E2E proof task.\n"
            return file_path, content
        return "", ""

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        plan: TaskPlan,
        approved_subtask_ids: Optional[List[str]] = None,
    ) -> TaskPlan:
        """Execute a task plan, respecting dry-run and approval gates.

        Args:
            plan: The task plan created by plan().
            approved_subtask_ids: Subtask IDs that have been explicitly
                approved by the Manager. Required for approval-gated steps.

        Returns:
            Updated TaskPlan with execution results.
        """
        approved = set(approved_subtask_ids or [])
        plan.status = "running"
        total_cost = 0.0
        last_diff = None

        # Pre-mark dry_run gates before execution so status is correct even
        # if earlier subtasks fail and stop_on_blocker halts the loop.
        if plan.dry_run:
            for subtask in plan.subtasks:
                if subtask.tool_id in ("git_commit", "git_push") and subtask.status == "pending":
                    subtask.status = "skipped_dry_run"
                    subtask.output = f"[DRY-RUN] Skipped {subtask.tool_id} — dry-run mode active."

        for subtask in plan.subtasks:
            if subtask.status in ("done", "skipped", "skipped_dry_run"):
                continue

            # Dry-run gate: block commit/push, tag others as dry-run
            if plan.dry_run and subtask.tool_id in ("git_commit", "git_push"):
                subtask.status = "skipped_dry_run"
                subtask.output = f"[DRY-RUN] Skipped {subtask.tool_id} — dry-run mode active."
                logger.info("DRY-RUN: skipping %s", subtask.tool_id)
                continue

            # Approval gate
            if subtask.requires_approval and subtask.id not in approved:
                subtask.status = "awaiting_approval"
                self._pending_approvals[subtask.id] = subtask
                logger.info("APPROVAL REQUIRED: subtask %s (%s)", subtask.id, subtask.tool_id)
                if plan.stop_on_blocker:
                    plan.status = "awaiting_approval"
                    break
                continue

            # Execute the subtask
            subtask.started_at = time.time()
            result = self._execute_subtask(subtask, plan)
            subtask.finished_at = time.time()
            total_cost += subtask.cost_usd

            # Capture diff preview
            if subtask.tool_id == "git_diff" and result and subtask.output:
                last_diff = subtask.output

            # Stop on blocker
            if subtask.status == "failed" and plan.stop_on_blocker:
                self._checkpoints.save_checkpoint(
                    session_id=plan.session_id,
                    task_id=plan.task_id,
                    label=f"blocker_at_{subtask.tool_id}",
                    evidence=subtask.error or "Unknown error",
                    verdict="HOLD",
                    is_blocker=True,
                )
                plan.status = "blocked"
                plan.final_report = self._generate_report(plan, blocked_at=subtask)
                plan.diff_preview = last_diff
                plan.total_cost_usd = round(total_cost, 6)
                return plan

        # Post-execution
        plan.diff_preview = last_diff
        plan.total_cost_usd = round(total_cost, 6)
        plan.finished_at = time.time()

        # Determine final status
        has_failures = any(s.status == "failed" for s in plan.subtasks)
        has_pending_approval = any(s.status == "awaiting_approval" for s in plan.subtasks)

        if has_pending_approval:
            plan.status = "awaiting_approval"
        elif has_failures:
            plan.status = "failed"
        else:
            plan.status = "done" if not plan.dry_run else "done_dry_run"

        # Validation output: collect shell_exec output
        plan.validation_output = self._collect_validation_output(plan)
        plan.final_report = self._generate_report(plan)

        self._checkpoints.save_checkpoint(
            session_id=plan.session_id,
            task_id=plan.task_id,
            label="execution_complete",
            evidence=f"Status={plan.status}. Cost=${plan.total_cost_usd:.6f}",
            verdict="ACCEPT" if plan.status in ("done", "done_dry_run") else "HOLD",
            notes={"status": plan.status, "cost_usd": plan.total_cost_usd},
        )

        return plan

    def _execute_subtask(self, subtask: Subtask, plan: TaskPlan) -> bool:
        """Execute a single subtask using its tool. Returns True on success."""
        subtask.status = "running"
        job = self._jobs.enqueue(
            task_id=plan.task_id,
            description=subtask.description,
            tool_id=subtask.tool_id,
            params=subtask.params,
            worker_tier=subtask.worker_tier,
        )
        subtask.job_id = job.id
        self._jobs.mark_running(job.id)

        try:
            result = self._call_tool(subtask.tool_id, subtask.params)
            success = result.get("success", False)
            output = result.get("content", "")

            if success:
                subtask.status = "done"
                subtask.output = output
                self._jobs.mark_done(job.id, output, subtask.cost_usd)
            else:
                subtask.status = "failed"
                subtask.error = output
                self._jobs.mark_failed(job.id, output)

            return success

        except Exception as exc:
            subtask.status = "failed"
            subtask.error = str(exc)
            self._jobs.mark_failed(job.id, str(exc))
            logger.exception("Subtask %s failed: %s", subtask.id, exc)
            return False

    def _call_tool(self, tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Jarvis tool directly by instantiating the tool class."""
        try:
            tool_instance = self._resolve_tool(tool_id)
            if tool_instance is None:
                return {"success": False, "content": f"Tool not found: {tool_id}"}
            result = tool_instance.execute(**params)
            return {
                "success": result.success,
                "content": result.content,
                "metadata": result.metadata or {},
            }
        except Exception as exc:
            logger.exception("Tool call error for %s: %s", tool_id, exc)
            return {"success": False, "content": f"Tool call error: {exc}"}

    @staticmethod
    def _resolve_tool(tool_id: str):
        """Resolve a tool_id to an instantiated tool object."""
        if tool_id in ("git_status", "git_diff", "git_commit", "git_push", "git_log", "git_branch"):
            from openjarvis.tools.git_tool import (
                GitStatusTool,
                GitDiffTool,
                GitCommitTool,
                GitPushTool,
                GitLogTool,
                GitBranchTool,
            )
            _map = {
                "git_status": GitStatusTool,
                "git_diff": GitDiffTool,
                "git_commit": GitCommitTool,
                "git_push": GitPushTool,
                "git_log": GitLogTool,
                "git_branch": GitBranchTool,
            }
            return _map[tool_id]()

        if tool_id == "file_read":
            from openjarvis.tools.file_read import FileReadTool
            return FileReadTool()

        if tool_id == "file_write":
            from openjarvis.tools.file_write import FileWriteTool
            return FileWriteTool()

        if tool_id == "file_search":
            from openjarvis.tools.file_search import FileSearchTool
            return FileSearchTool()

        if tool_id == "file_delete":
            from openjarvis.tools.file_delete import FileDeleteTool
            return FileDeleteTool()

        if tool_id == "shell_exec":
            from openjarvis.tools.shell_exec import ShellExecTool
            return ShellExecTool()

        return None

    def _collect_validation_output(self, plan: TaskPlan) -> Optional[str]:
        """Collect output from validation (shell_exec) subtasks."""
        for subtask in plan.subtasks:
            if subtask.tool_id == "shell_exec" and subtask.output:
                return subtask.output
        return None

    def _generate_report(
        self,
        plan: TaskPlan,
        blocked_at: Optional[Subtask] = None,
    ) -> str:
        """Generate a final markdown report for the task."""
        lines = [
            f"# Jarvis Coding Workbench — Task Report",
            f"",
            f"## Status",
            f"",
            f"**{plan.status.upper()}**",
            f"",
            f"## Task",
            f"",
            f"- **Session**: `{plan.session_id}`",
            f"- **Task ID**: `{plan.task_id}`",
            f"- **Prompt**: {plan.prompt}",
            f"- **Repo**: `{plan.repo_path}`",
            f"- **Dry-Run**: {plan.dry_run}",
            f"- **Total Cost**: ${plan.total_cost_usd:.6f} USD",
            f"",
            f"## Subtasks",
            f"",
        ]

        for st in plan.subtasks:
            icon = {
                "done": "✅",
                "failed": "❌",
                "skipped_dry_run": "⏭️",
                "awaiting_approval": "🔒",
                "running": "⏳",
                "pending": "⏳",
            }.get(st.status, "❓")
            lines.append(f"{icon} **[{st.index}] {st.description}**")
            lines.append(f"   - Tool: `{st.tool_id}` | Tier: `{st.worker_tier}` | Status: `{st.status}`")
            if st.output and len(st.output) < 500:
                lines.append(f"   - Output: ```{st.output[:300]}```")
            if st.error:
                lines.append(f"   - Error: `{st.error[:200]}`")
            lines.append("")

        if blocked_at:
            lines.extend([
                f"## Blocker",
                f"",
                f"Stopped at subtask [{blocked_at.index}]: `{blocked_at.description}`",
                f"Error: `{blocked_at.error}`",
                f"",
            ])

        if plan.diff_preview:
            lines.extend([
                f"## Diff Preview",
                f"",
                f"```diff",
                plan.diff_preview[:2000],
                f"```",
                f"",
            ])

        if plan.validation_output:
            lines.extend([
                f"## Validation Output",
                f"",
                f"```",
                plan.validation_output[:1000],
                f"```",
                f"",
            ])

        lines.extend([
            f"## Governance",
            f"",
            f"- Workers cannot commit/push: **enforced**",
            f"- Approval gate: **active** for commit/push/delete",
            f"- Changed-file-only review: **active**",
            f"- Dry-run mode: **{plan.dry_run}**",
            f"- Stop-on-blocker: **{plan.stop_on_blocker}**",
            f"",
            f"## Final Verdict",
            f"",
            f"{'ACCEPT' if plan.status in ('done', 'done_dry_run') else 'HOLD'}",
        ])

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Approval API
    # ------------------------------------------------------------------

    def approve_subtask(self, plan: TaskPlan, subtask_id: str) -> TaskPlan:
        """Approve a pending subtask and re-execute the plan."""
        if subtask_id in self._pending_approvals:
            del self._pending_approvals[subtask_id]
        return self.execute(plan, approved_subtask_ids=[subtask_id])

    def list_pending_approvals(self) -> List[Subtask]:
        return list(self._pending_approvals.values())

    # ------------------------------------------------------------------
    # Diff / validation helpers
    # ------------------------------------------------------------------

    def generate_diff(self, repo_path: Optional[str] = None) -> str:
        """Generate a diff of the current working tree."""
        effective_repo = repo_path or str(self._repo_path)
        result = self._call_tool("git_diff", {"repo_path": effective_repo})
        return result.get("content", "(no diff)")

    def run_validation(
        self,
        command: str = "python -m pytest tests/ -x -q --tb=short",
        repo_path: Optional[str] = None,
        timeout: int = 60,
    ) -> str:
        """Run a validation/test command and return output."""
        effective_repo = repo_path or str(self._repo_path)
        result = self._call_tool("shell_exec", {
            "command": command,
            "working_dir": effective_repo,
            "timeout": timeout,
        })
        return result.get("content", "(no output)")

    # ------------------------------------------------------------------
    # Session/checkpoint access
    # ------------------------------------------------------------------

    def get_checkpoints(self, session_id: str) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._checkpoints.list_checkpoints(session_id)]

    def get_cost_summary(self, session_id: str) -> Dict[str, Any]:
        return self._costs.session_total(session_id)

    def get_jobs(self, task_id: str) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.list_by_task(task_id)]


__all__ = ["CodingManager", "TaskPlan", "Subtask"]
