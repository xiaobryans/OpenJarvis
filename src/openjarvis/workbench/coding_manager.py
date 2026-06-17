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
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.workbench.job_queue import Job, JobQueue, JobStatus
from openjarvis.workbench.cost_ledger import CostLedger
from openjarvis.workbench.checkpoint import CheckpointStore
from openjarvis.workbench.model_router import (
    ModelRouter,
    ModelTier,
    EscalationAction,
    MockModelAdapter,
)

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


# ---------------------------------------------------------------------------
# Prompt classification
# ---------------------------------------------------------------------------

_PLAN_ONLY_PHRASES = (
    "plan only", "do not edit", "do not write", "no edit files",
    "planning only", "plan-only", "don't edit", "don't write",
)
_COMPLEX_IMPL_KEYWORDS = frozenset({
    "implement", "feature", "sprint", "notification", "autopilot",
    "bridge", "us14a.1", "us14b", "us15", "remediation", "planner",
    "pa chat", "workbench route", "prompt classification",
    "task decomposition", "implementation plan",
})
_BUG_FIX_KEYWORDS = frozenset({
    "fix", "bug", "broken", "regression", "incorrect", "wrong",
    "failing", "defect", "crash",
})
_TINY_MARKER_KEYWORDS = frozenset({"fixture", "self-test", "marker", "e2e proof"})
_DOCUMENTATION_KEYWORDS = frozenset({"readme", "changelog", "documentation"})
_RESEARCH_KEYWORDS = frozenset({"investigate", "research", "explore", "audit", "survey"})

# Bounded search directories — ordered by specificity; avoids scanning the full repo tree.
# Used by _bounded_search_dir() to prevent file_search timeouts on large repos.
_SEARCH_TARGETED_DIRS: tuple = (
    "src/openjarvis/server",
    "src/openjarvis/workbench",
    "src/openjarvis/channels",
    "src/openjarvis/tools",
    "src/openjarvis/autonomy",
    "src/openjarvis/governance",
    "frontend/src",
    "src",
)

# Heavy/generated directories always excluded from file_search scans.
_SEARCH_EXCLUDE_DIRS: List[str] = [
    "!.git",
    "!.venv",
    "!node_modules",
    "!frontend/node_modules",
    "!frontend/src-tauri/target",
    "!target",
    "!dist",
    "!build",
    "!__pycache__",
    "!.pytest_cache",
]


def _bounded_search_dir(repo_path: str) -> str:
    """Return the most targeted existing search directory for the repo.

    Prefers src/openjarvis subdirectories over the full repo root to avoid
    scanning .venv, node_modules, and other heavy generated directories that
    cause file_search timeouts.
    """
    repo = Path(repo_path)
    for subdir in _SEARCH_TARGETED_DIRS:
        candidate = repo / subdir
        if candidate.is_dir():
            return str(candidate)
    return repo_path


_FILE_HINTS = {
    # ---- Workbench core ----
    "coding_manager": "src/openjarvis/workbench/coding_manager.py",
    "workbench_routes": "src/openjarvis/server/workbench_routes.py",
    "workbench route": "src/openjarvis/server/workbench_routes.py",
    "model_router": "src/openjarvis/workbench/model_router.py",
    "workbenchpage": "frontend/src/pages/WorkbenchPage.tsx",
    "planner": "src/openjarvis/workbench/coding_manager.py",
    "job_queue": "src/openjarvis/workbench/job_queue.py",
    "checkpoint": "src/openjarvis/workbench/checkpoint.py",
    "cost_ledger": "src/openjarvis/workbench/cost_ledger.py",
    "constitution": "src/openjarvis/governance/constitution.py",
    "test_us14a": "tests/workbench/test_us14a.py",
    # ---- PA Chat / chat message handling ----
    "pa chat": "src/openjarvis/server/routes.py",
    "chat-to-workbench": "src/openjarvis/server/workbench_routes.py",
    "chat to workbench": "src/openjarvis/server/workbench_routes.py",
    "chat completion": "src/openjarvis/server/routes.py",
    "chat route": "src/openjarvis/server/routes.py",
    "chat area": "frontend/src/components/Chat/ChatArea.tsx",
    "chatarea": "frontend/src/components/Chat/ChatArea.tsx",
    "input area": "frontend/src/components/Chat/InputArea.tsx",
    # ---- Bridge ----
    "bridge": "src/openjarvis/server/channel_bridge.py",
    "channel_bridge": "src/openjarvis/server/channel_bridge.py",
    "stream_bridge": "src/openjarvis/server/stream_bridge.py",
    "ws_bridge": "src/openjarvis/server/ws_bridge.py",
    # ---- Notifications ----
    "notification": "src/openjarvis/server/notify_routes.py",
    "notifier": "src/openjarvis/mission/notifier.py",
    "notify_routes": "src/openjarvis/server/notify_routes.py",
    "chat notification": "src/openjarvis/cli/_chat_notifications.py",
    # ---- Approval queue ----
    "approval": "src/openjarvis/tools/approval_store.py",
    "approval_store": "src/openjarvis/tools/approval_store.py",
    "approval_routes": "src/openjarvis/server/approval_routes.py",
    "approval route": "src/openjarvis/server/approval_routes.py",
    "approval bell": "frontend/src/components/ApprovalBell.tsx",
    # ---- Slack notifications ----
    "slack": "src/openjarvis/channels/slack.py",
    "slack_daemon": "src/openjarvis/channels/slack_daemon.py",
    "slack_connector": "src/openjarvis/connectors/slack_connector.py",
    "slack connector": "src/openjarvis/connectors/slack_connector.py",
    # ---- Telegram notifications ----
    "telegram": "src/openjarvis/channels/telegram.py",
    # ---- macOS/Tauri notifications ----
    "tauri notification": "frontend/src/components/ApprovalBell.tsx",
    "macos notification": "frontend/src/components/ApprovalBell.tsx",
    # ---- Guarded autopilot / approval policy ----
    "autopilot": "src/openjarvis/autonomy/automation_policy.py",
    "automation_policy": "src/openjarvis/autonomy/automation_policy.py",
    "guarded": "src/openjarvis/governance/constitution.py",
    "governance": "src/openjarvis/governance/constitution.py",
    "policies": "src/openjarvis/governance/policies.py",
    # ---- Model routing / provider / cost ----
    "routing": "src/openjarvis/workbench/model_router.py",
    "model routing": "src/openjarvis/workbench/model_router.py",
    "model router": "src/openjarvis/workbench/model_router.py",
    "ledger": "src/openjarvis/workbench/cost_ledger.py",
    "cost ledger": "src/openjarvis/workbench/cost_ledger.py",
    "cost_calculator": "src/openjarvis/server/cost_calculator.py",
    "cost calculator": "src/openjarvis/server/cost_calculator.py",
    "model catalog": "src/openjarvis/intelligence/model_catalog.py",
    "model_catalog": "src/openjarvis/intelligence/model_catalog.py",
    "provider": "src/openjarvis/intelligence/model_catalog.py",
}

_SUBSYSTEM_LABELS: Dict[str, str] = {
    "routes.py": "PA Chat / API Routes",
    "workbench_routes": "Workbench Routes",
    "coding_manager": "Workbench Manager",
    "notify_routes": "Notification Routes / Events",
    "notifier.py": "Notifier",
    "approval_store": "Approval Store",
    "approval_routes": "Approval Routes",
    "ApprovalBell": "Frontend Approval UI (macOS/Tauri)",
    "slack": "Slack Channel / Notifier",
    "telegram": "Telegram Channel / Notifier",
    "WorkbenchPage": "Frontend Workbench UI",
    "ChatArea": "Frontend Chat UI",
    "model_router": "Model Router",
    "cost_ledger": "Cost Ledger",
    "automation_policy": "Guarded Autopilot",
    "constitution": "Governance / Constitution",
    "test_us14a": "Tests",
}

_PLANNING_NEXT_FILES: List[str] = [
    "src/openjarvis/server/routes.py",
    "src/openjarvis/server/workbench_routes.py",
    "src/openjarvis/workbench/coding_manager.py",
    "src/openjarvis/server/notify_routes.py",
    "src/openjarvis/mission/notifier.py",
    "src/openjarvis/tools/approval_store.py",
    "src/openjarvis/server/approval_routes.py",
    "src/openjarvis/channels/slack.py",
    "src/openjarvis/channels/telegram.py",
    "frontend/src/components/ApprovalBell.tsx",
    "src/openjarvis/workbench/model_router.py",
    "src/openjarvis/workbench/cost_ledger.py",
    "src/openjarvis/autonomy/automation_policy.py",
    "src/openjarvis/governance/constitution.py",
    "frontend/src/pages/WorkbenchPage.tsx",
    "tests/workbench/test_us14a.py",
    "tests/workbench/test_us14a_planner.py",
]


def _get_subsystem_label(fpath: str) -> str:
    """Map a file path fragment to a human-readable subsystem label."""
    for key, label in _SUBSYSTEM_LABELS.items():
        if key.lower() in fpath.lower():
            return label
    return "Other"


_FILE_EXTENSIONS: frozenset = frozenset({
    "py", "ts", "tsx", "js", "jsx", "json", "yaml", "yml", "toml", "md",
    "txt", "sh", "cfg", "ini", "db", "sql", "lock", "env", "html", "css",
    "rs", "go", "rb", "swift", "java", "kt", "c", "h", "cpp", "hpp",
})

# Matches backtick-quoted paths that contain no whitespace and have a file extension
_EXPLICIT_BACKTICK_RE = re.compile(r'`([^\s`\n]+\.[a-zA-Z0-9]{1,8})`')
# Matches plain bullet-listed paths (dash or asterisk) not in backticks.
# Uses lookahead for line-end so consecutive bullets are all matched.
_EXPLICIT_BULLET_RE = re.compile(
    r'(?:^|\n)[ \t]*[-*]\s+([^\s`\n\[\](){}]+\.[a-zA-Z0-9]{1,8})[ \t]*(?=\n|$)'
)


def _is_safe_repo_relative(fpath: str) -> bool:
    """Return True only if fpath is a safe repo-relative file path.

    Rejects absolute paths, tilde paths, traversal attempts, and strings
    that look like code identifiers rather than file paths.
    """
    if not fpath or fpath.startswith("/") or fpath.startswith("~") or fpath.startswith("\\"):
        return False
    parts = fpath.replace("\\", "/").split("/")
    if ".." in parts:
        return False
    last = parts[-1]
    if "." not in last:
        return False
    ext = last.rsplit(".", 1)[-1].lower()
    if "/" not in fpath and ext not in _FILE_EXTENSIONS:
        return False
    return True


def _extract_explicit_files(prompt: str) -> List[str]:
    """Extract explicit repo-relative file paths from a prompt.

    Recognises backtick-quoted paths (``path/to/file.py``) and plain
    bullet-listed paths (``- path/to/file.py``).  Returns a deduplicated
    list of safe repo-relative paths in order of first appearance.
    """
    seen: set = set()
    results: List[str] = []

    for match in _EXPLICIT_BACKTICK_RE.finditer(prompt):
        fpath = match.group(1).strip()
        if _is_safe_repo_relative(fpath) and fpath not in seen:
            seen.add(fpath)
            results.append(fpath)

    for match in _EXPLICIT_BULLET_RE.finditer(prompt):
        fpath = match.group(1).strip()
        if _is_safe_repo_relative(fpath) and fpath not in seen:
            seen.add(fpath)
            results.append(fpath)

    return results


def classify_prompt(prompt: str) -> str:
    """Classify a prompt into one of six task types.

    Returns one of: planning_only, tiny_marker, documentation,
    bug_fix, complex_implementation, research.
    """
    p = prompt.lower()
    if any(phrase in p for phrase in _PLAN_ONLY_PHRASES):
        return "planning_only"
    if any(k in p for k in _TINY_MARKER_KEYWORDS) and not any(k in p for k in _COMPLEX_IMPL_KEYWORDS):
        return "tiny_marker"
    if any(k in p for k in _RESEARCH_KEYWORDS) and not any(k in p for k in _COMPLEX_IMPL_KEYWORDS):
        return "research"
    if any(k in p for k in _DOCUMENTATION_KEYWORDS) and not any(k in p for k in _COMPLEX_IMPL_KEYWORDS):
        return "documentation"
    if any(k in p for k in _BUG_FIX_KEYWORDS):
        return "bug_fix"
    if any(k in p for k in _COMPLEX_IMPL_KEYWORDS):
        return "complex_implementation"
    return "tiny_marker"


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
    task_type: str = "tiny_marker"
    final_report: Optional[str] = None
    diff_preview: Optional[str] = None
    validation_output: Optional[str] = None
    likely_files: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    validation_commands: List[str] = field(default_factory=list)
    approval_gates: List[str] = field(default_factory=list)
    explicit_files: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
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
            "task_type": self.task_type,
            "likely_files": self.likely_files,
            "risks": self.risks,
            "validation_commands": self.validation_commands,
            "approval_gates": self.approval_gates,
            "explicit_files": self.explicit_files,
            "missing_files": self.missing_files,
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
        model_router: Optional[ModelRouter] = None,
    ) -> None:
        self._repo_path = Path(repo_path).resolve()
        db_dir_path = Path(db_dir) if db_dir else Path.home() / ".openjarvis"
        db_dir_path.mkdir(parents=True, exist_ok=True)

        self._jobs = JobQueue(str(db_dir_path / "workbench_jobs.db"))
        self._costs = CostLedger(str(db_dir_path / "workbench_cost.db"))
        self._checkpoints = CheckpointStore(str(db_dir_path / "workbench_checkpoints.db"))
        # Use MockModelAdapter by default (no real paid calls unless explicitly configured)
        self._router = model_router or ModelRouter(
            db_path=str(db_dir_path / "model_routing.db"),
            adapter_override=MockModelAdapter(),
        )

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

        task_type = classify_prompt(prompt)
        subtasks = self._decompose(prompt, task_id, str(effective_repo), session_id=session_id, task_type=task_type)

        # Compute explicit files listed in the prompt and which are missing on disk
        _explicit_files = _extract_explicit_files(prompt)
        _repo_base = Path(str(effective_repo)).resolve()
        _missing_files: List[str] = []
        for _fpath in _explicit_files:
            _full = (_repo_base / _fpath).resolve()
            try:
                _full.relative_to(_repo_base)
            except ValueError:
                continue  # outside repo — skip silently
            if not _full.exists():
                _missing_files.append(_fpath)

        plan = TaskPlan(
            session_id=session_id,
            task_id=task_id,
            prompt=prompt,
            repo_path=str(effective_repo),
            subtasks=subtasks,
            dry_run=dry_run,
            stop_on_blocker=stop_on_blocker,
            task_type=task_type,
            likely_files=self._extract_likely_files(prompt, str(effective_repo)),
            risks=self._assess_risks(prompt, task_type),
            validation_commands=self._suggest_validation(prompt, task_type, str(effective_repo)),
            approval_gates=self._identify_gates(task_type),
            explicit_files=_explicit_files,
            missing_files=_missing_files,
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
        session_id: str = "",
        task_type: Optional[str] = None,
    ) -> List[Subtask]:
        """Decompose a prompt into a list of subtasks.

        Uses rule-based decomposition (no LLM call needed for the planner
        itself — the planner is deterministic to keep costs at zero).
        LLM calls happen only during worker execution of each subtask.
        """
        if task_type is None:
            task_type = classify_prompt(prompt)
        if task_type == "planning_only":
            return self._decompose_planning_only(prompt, task_id, repo_path, session_id)
        if task_type == "complex_implementation":
            return self._decompose_complex(prompt, task_id, repo_path, session_id)
        if task_type == "bug_fix":
            return self._decompose_bug_fix(prompt, task_id, repo_path, session_id)
        if task_type in ("research", "documentation"):
            return self._decompose_discovery_only(prompt, task_id, repo_path, session_id)
        subtasks: List[Subtask] = []
        idx = 0

        # Step 1: Always inspect repo state first (read-only, local tier)
        st = self._make_subtask(
            idx=idx,
            task_id=task_id,
            description="Inspect repository status and branch",
            tool_id="git_status",
            params={"repo_path": repo_path},
            session_id=session_id,
        )
        subtasks.append(st)
        idx += 1

        # Step 2: Search for relevant files if prompt mentions patterns
        search_terms = self._extract_search_terms(prompt)
        if search_terms:
            search_dir = _bounded_search_dir(repo_path)
            st = self._make_subtask(
                idx=idx,
                task_id=task_id,
                description=f"Search codebase for: {', '.join(search_terms[:3])}",
                tool_id="file_search",
                params={
                    "pattern": "|".join(search_terms[:3]),
                    "directory": search_dir,
                    "exclude_dirs": _SEARCH_EXCLUDE_DIRS,
                },
                session_id=session_id,
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
            session_id=session_id,
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
                    session_id=session_id,
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
                "command": "( .venv/bin/python3 -m pytest tests/workbench/ -x -q --tb=short 2>&1 || python3 -m pytest tests/workbench/ -x -q --tb=short 2>&1 || echo 'No pytest found' ) | head -50",
                "working_dir": repo_path,
                "timeout": 60,
            },
            session_id=session_id,
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
            session_id=session_id,
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
            session_id=session_id,
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
            session_id=session_id,
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
        session_id: str = "",
    ) -> Subtask:
        tier = _route_worker_tier(tool_id, is_risky)
        requires_approval = tool_id in _APPROVAL_REQUIRED_TOOLS
        subtask_id = uuid.uuid4().hex[:12]
        # Log routing decision via ModelRouter
        if session_id and task_id:
            self._router.route(
                subtask_id=subtask_id,
                tool_id=tool_id,
                description=description,
                session_id=session_id,
                task_id=task_id,
                high_trust=tool_id in _HIGH_TRUST_TOOLS,
            )
        return Subtask(
            id=subtask_id,
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

    def _decompose_planning_only(
        self, prompt: str, task_id: str, repo_path: str, session_id: str = ""
    ) -> List[Subtask]:
        """Planning-only: discovery only, no file_write/git_commit/git_push.

        When the prompt contains explicit repo-relative file paths (backtick-
        quoted or bullet-listed), creates file_read subtasks for every existing
        file.  Falls back to auto-inferred likely files when no explicit paths
        are found.  Never adds file_search to avoid full-repo scan timeouts.
        """
        subtasks: List[Subtask] = []
        idx = 0
        subtasks.append(self._make_subtask(
            idx, task_id, "Inspect repository status and branch",
            "git_status", {"repo_path": repo_path}, session_id=session_id)); idx += 1
        subtasks.append(self._make_subtask(
            idx, task_id, "Generate diff preview of working tree",
            "git_diff", {"repo_path": repo_path}, session_id=session_id)); idx += 1

        explicit = _extract_explicit_files(prompt)
        if explicit:
            repo_base = Path(repo_path).resolve()
            for fpath in explicit:
                full = (repo_base / fpath).resolve()
                try:
                    full.relative_to(repo_base)
                except ValueError:
                    continue  # outside repo — skip
                if full.exists():
                    subtasks.append(self._make_subtask(
                        idx, task_id, f"Read explicit file: {fpath}",
                        "file_read", {"path": str(full)},
                        session_id=session_id)); idx += 1
        else:
            for fpath in self._extract_likely_files(prompt, repo_path)[:3]:
                subtasks.append(self._make_subtask(
                    idx, task_id, f"Read likely file: {fpath}",
                    "file_read", {"path": str(Path(repo_path) / fpath)},
                    session_id=session_id)); idx += 1
        return subtasks

    def _decompose_complex(
        self, prompt: str, task_id: str, repo_path: str, session_id: str = ""
    ) -> List[Subtask]:
        """Complex implementation: discovery subtasks first, no default writes.

        Uses file_read of likely files instead of broad file_search to avoid
        scanning the full repo tree and causing timeouts.
        """
        subtasks: List[Subtask] = []
        idx = 0
        subtasks.append(self._make_subtask(
            idx, task_id, "Inspect repository status and branch",
            "git_status", {"repo_path": repo_path}, session_id=session_id)); idx += 1
        subtasks.append(self._make_subtask(
            idx, task_id, "Generate diff preview of working tree",
            "git_diff", {"repo_path": repo_path}, session_id=session_id)); idx += 1
        for fpath in self._extract_likely_files(prompt, repo_path)[:4]:
            subtasks.append(self._make_subtask(
                idx, task_id, f"Discover: read {fpath}",
                "file_read", {"path": str(Path(repo_path) / fpath)},
                session_id=session_id)); idx += 1
        return subtasks

    def _decompose_bug_fix(
        self, prompt: str, task_id: str, repo_path: str, session_id: str = ""
    ) -> List[Subtask]:
        """Bug fix: targeted discovery + validation, no default writes."""
        subtasks: List[Subtask] = []
        idx = 0
        subtasks.append(self._make_subtask(
            idx, task_id, "Inspect repository status and branch",
            "git_status", {"repo_path": repo_path}, session_id=session_id)); idx += 1
        subtasks.append(self._make_subtask(
            idx, task_id, "Generate diff preview of working tree",
            "git_diff", {"repo_path": repo_path}, session_id=session_id)); idx += 1
        search_terms = self._extract_search_terms(prompt)
        if search_terms:
            bounded_dir = _bounded_search_dir(repo_path)
            subtasks.append(self._make_subtask(
                idx, task_id, f"Search for bug-relevant patterns: {', '.join(search_terms[:3])}",
                "file_search", {
                    "pattern": "|".join(search_terms[:3]),
                    "directory": bounded_dir,
                    "exclude_dirs": _SEARCH_EXCLUDE_DIRS,
                },
                session_id=session_id)); idx += 1
        for fpath in self._extract_likely_files(prompt, repo_path)[:3]:
            subtasks.append(self._make_subtask(
                idx, task_id, f"Read likely buggy file: {fpath}",
                "file_read", {"path": str(Path(repo_path) / fpath)},
                session_id=session_id)); idx += 1
        subtasks.append(self._make_subtask(
            idx, task_id, "Run validation / tests",
            "shell_exec", {
                "command": "( .venv/bin/python3 -m pytest tests/workbench/ -x -q --tb=short 2>&1 || python3 -m pytest tests/workbench/ -x -q --tb=short 2>&1 || echo 'No pytest found' ) | head -50",
                "working_dir": repo_path, "timeout": 60,
            }, session_id=session_id)); idx += 1
        return subtasks

    def _decompose_discovery_only(
        self, prompt: str, task_id: str, repo_path: str, session_id: str = ""
    ) -> List[Subtask]:
        """Research/documentation: read-only discovery, no writes or validation."""
        subtasks: List[Subtask] = []
        idx = 0
        subtasks.append(self._make_subtask(
            idx, task_id, "Inspect repository status and branch",
            "git_status", {"repo_path": repo_path}, session_id=session_id)); idx += 1
        subtasks.append(self._make_subtask(
            idx, task_id, "Generate diff preview of working tree",
            "git_diff", {"repo_path": repo_path}, session_id=session_id)); idx += 1
        search_terms = self._extract_search_terms(prompt)
        if search_terms:
            bounded_dir = _bounded_search_dir(repo_path)
            subtasks.append(self._make_subtask(
                idx, task_id, f"Search codebase for: {', '.join(search_terms[:3])}",
                "file_search", {
                    "pattern": "|".join(search_terms[:3]),
                    "directory": bounded_dir,
                    "exclude_dirs": _SEARCH_EXCLUDE_DIRS,
                },
                session_id=session_id)); idx += 1
        for fpath in self._extract_likely_files(prompt, repo_path)[:3]:
            subtasks.append(self._make_subtask(
                idx, task_id, f"Read: {fpath}",
                "file_read", {"path": str(Path(repo_path) / fpath)},
                session_id=session_id)); idx += 1
        return subtasks

    def _extract_likely_files(self, prompt: str, repo_path: str) -> List[str]:
        """Return likely relevant file paths from keyword hints in the prompt."""
        p = prompt.lower()
        files = []
        for keyword, fpath in _FILE_HINTS.items():
            if keyword in p:
                files.append(fpath)
        return list(dict.fromkeys(files))

    def _assess_risks(self, prompt: str, task_type: str) -> List[str]:
        """Identify risks for the task."""
        p = prompt.lower()
        risks: List[str] = []
        if task_type == "planning_only":
            risks.append("Insufficient data to verify — discovery phase not yet run; files not fully inspected")
            p2 = prompt.lower()
            if any(w in p2 for w in ("slack", "telegram", "notification")):
                risks.append("Risk: notification channels must not send messages during dry-run or Plan Only")
            if any(w in p2 for w in ("autopilot", "guarded")):
                risks.append("Risk: Guarded Autopilot must enforce approval gates; kill-switch policy must be verified")
            if any(w in p2 for w in ("chat-to-workbench", "chat to workbench")):
                risks.append("Risk: Chat-to-Workbench bridge requires idempotent message routing")
            if any(w in p2 for w in ("model", "router", "routing")):
                risks.append("Risk: model routing changes may trigger unexpected paid provider calls")
            return risks
        if task_type in ("complex_implementation", "bug_fix"):
            risks.append("Insufficient data to verify — likely affected files not yet read")
            risks.append("Risk: unintended side effects in adjacent modules")
            if any(w in p for w in ("route", "api", "endpoint")):
                risks.append("Risk: API contract change may break frontend")
            if any(w in p for w in ("planner", "decompose", "classify")):
                risks.append("Risk: planner change may break existing test_us14a tests")
            if any(w in p for w in ("notification", "autopilot", "bridge")):
                risks.append("Risk: new async subsystems require integration tests")
        return risks

    def _suggest_validation(self, prompt: str, task_type: str, repo_path: str) -> List[str]:
        """Suggest validation commands for the task."""
        if task_type == "planning_only":
            return ["(no execution — plan only)"]
        base = "python -m pytest tests/workbench/ -x -q --tb=short"
        if task_type in ("complex_implementation", "bug_fix"):
            return [
                "python -m pytest tests/workbench/test_us14a_planner.py -x -q --tb=short",
                "python -m pytest tests/workbench/test_us14a.py -x -q --tb=short",
                base,
            ]
        return [base]

    def _identify_gates(self, task_type: str) -> List[str]:
        """Identify approval gates required for the task."""
        if task_type == "planning_only":
            return [
                "Gate 0: No writes until explicit approval after plan review",
                "Gate 1: Implementation plan must reach READY_FOR_IMPLEMENTATION_APPROVAL before any file_write",
                "Gate 2: Each implementation phase requires Discovery review before proceeding",
                "Gate 3: Manager approval required for git_commit",
                "Gate 4: Manager approval required for git_push",
                "Gate 5: No Slack/Telegram test sends without explicit approval",
            ]
        if task_type in ("complex_implementation", "bug_fix"):
            return [
                "Gate 1: Discovery review — approve before any file writes",
                "Gate 2: Implementation plan review — approve before execution",
                "Gate 3: Manager approval required for git_commit",
                "Gate 4: Manager approval required for git_push",
            ]
        return [
            "Gate 1: Manager approval required for git_commit",
            "Gate 2: Manager approval required for git_push",
        ]

    def _suggests_file_change(self, prompt: str) -> bool:
        keywords = ["add", "create", "write", "edit", "modify", "update", "insert", "fixture", "test"]
        return any(k in prompt.lower() for k in keywords)

    def _infer_file_change(self, prompt: str, repo_path: str) -> tuple[str, str]:
        """Infer a file path and content from the prompt (heuristic fallback)."""
        import time as _time
        _ts = _time.strftime("%Y%m%dT%H%M%S")
        prompt_lower = prompt.lower()
        if "fixture" in prompt_lower or "self-test" in prompt_lower or "marker" in prompt_lower:
            file_path = str(Path(repo_path) / "tests" / "workbench" / "test_us14a_fixture.py")
            content = (
                '"""US14A self-test fixture — added by Jarvis Coding Workbench."""\n\n'
                f"US14A_MARKER = \"Jarvis Coding Workbench E2E proof {_ts}\"\n\n\n"
                "def test_us14a_marker():\n"
                '    """Verify US14A marker is present."""\n'
                "    assert US14A_MARKER.startswith(\"Jarvis Coding Workbench E2E proof\")\n"
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
                if subtask.tool_id in ("git_commit", "git_push", "file_write", "file_delete") and subtask.status == "pending":
                    subtask.status = "skipped_dry_run"
                    subtask.output = f"[DRY-RUN] Skipped {subtask.tool_id} — dry-run mode active."

        for subtask in plan.subtasks:
            if subtask.status in ("done", "skipped", "skipped_dry_run"):
                continue

            # Dry-run gate: block writes, commit, push, delete
            if plan.dry_run and subtask.tool_id in ("git_commit", "git_push", "file_write", "file_delete"):
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

        hold_reasons = self._implementation_hold_reasons(plan)
        if hold_reasons and plan.status in ("done", "done_dry_run"):
            plan.status = "blocked"

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

    @staticmethod
    def _non_empty_diff_output(content: Optional[str]) -> bool:
        """Return True when a git diff-like output contains real changes."""
        if not content:
            return False
        stripped = content.strip()
        if not stripped:
            return False
        return stripped not in {"(no output)", "No changes", "No changes."}

    @staticmethod
    def _validation_blocker_reason(output: Optional[str]) -> Optional[str]:
        """Return a HOLD reason when validation did not actually run."""
        if not output:
            return None
        lower = output.lower()
        markers = (
            "no pytest found",
            "no module named pytest",
            "missing test runner",
            "pytest: command not found",
            "fatal python error",
            "bad file descriptor",
            "can't initialize sys standard streams",
        )
        for marker in markers:
            if marker in lower:
                return marker
        return None

    @staticmethod
    def _validation_status(output: Optional[str]) -> str:
        """Summarize validation state for final reports."""
        if not output:
            return "not_run"
        blocker = CodingManager._validation_blocker_reason(output)
        if blocker:
            return f"blocked: {blocker}"
        lower = output.lower()
        if " passed" in lower and " failed" not in lower and "error" not in lower:
            return "passed"
        if " failed" in lower or " error" in lower or "traceback" in lower:
            return "failed"
        return "completed"

    @staticmethod
    def _git_changed_files(repo_path: str) -> str:
        """Return current working-tree changed files, best-effort/read-only."""
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-status"],
                cwd=repo_path,
                text=True,
                capture_output=True,
                timeout=10,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            pass
        return ""

    def _implementation_evidence(self, plan: TaskPlan) -> Dict[str, Any]:
        """Collect implementation evidence for non-planning task reports."""
        file_write_done = any(
            st.tool_id == "file_write" and st.status == "done"
            for st in plan.subtasks
        )
        file_write_count = sum(1 for st in plan.subtasks if st.tool_id == "file_write")
        git_changed_files = self._git_changed_files(plan.repo_path)
        diff_preview_has_changes = self._non_empty_diff_output(plan.diff_preview)
        git_diff_has_changes = bool(git_changed_files.strip())
        validation_status = self._validation_status(plan.validation_output)

        return {
            "file_write_subtasks": file_write_count,
            "file_write_done": file_write_done,
            "git_diff_has_changes": git_diff_has_changes,
            "diff_preview_has_changes": diff_preview_has_changes,
            "changed_files": git_changed_files,
            "validation_status": validation_status,
        }

    def _implementation_hold_reasons(self, plan: TaskPlan) -> List[str]:
        """Return reasons a non-planning task must be HOLD despite done subtasks."""
        reasons: List[str] = []

        validation_blocker = self._validation_blocker_reason(plan.validation_output)
        if validation_blocker:
            reasons.append(f"validation unavailable: {validation_blocker}")

        if plan.task_type in ("bug_fix", "complex_implementation") and not plan.dry_run:
            evidence = self._implementation_evidence(plan)
            has_implementation = (
                evidence["file_write_done"]
                or evidence["git_diff_has_changes"]
                or evidence["diff_preview_has_changes"]
            )
            if not has_implementation:
                reasons.append("implementation did not run; no files were edited")

        return reasons

    def _generate_report(
        self,
        plan: TaskPlan,
        blocked_at: Optional[Subtask] = None,
    ) -> str:
        """Generate a final markdown report for the task."""
        if plan.task_type == "planning_only":
            return self._generate_planning_report(plan, blocked_at=blocked_at)
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
            f"- **Task Type**: `{plan.task_type}`",
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

        implementation_evidence = self._implementation_evidence(plan)
        hold_reasons = self._implementation_hold_reasons(plan)
        final_verdict = (
            "ACCEPT"
            if plan.status in ("done", "done_dry_run") and not hold_reasons
            else "HOLD"
        )

        lines.extend([
            f"## Implementation Evidence",
            f"",
            f"- file_write subtasks: **{implementation_evidence['file_write_subtasks']}**",
            f"- file_write completed: **{implementation_evidence['file_write_done']}**",
            f"- git diff has changes: **{implementation_evidence['git_diff_has_changes']}**",
            f"- diff preview has changes: **{implementation_evidence['diff_preview_has_changes']}**",
            f"- changed files: `{implementation_evidence['changed_files'] or '(none)'}`",
            f"- validation status: **{implementation_evidence['validation_status']}**",
            f"",
        ])

        if hold_reasons:
            lines.extend([
                f"## Hold Reasons",
                f"",
            ])
            for reason in hold_reasons:
                lines.append(f"- {reason}")
            lines.append("")

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
            final_verdict,
        ])

        return "\n".join(lines)

    def _generate_planning_report(
        self,
        plan: TaskPlan,
        blocked_at: Optional[Subtask] = None,
    ) -> str:
        """Generate a structured planning artifact for planning_only tasks.

        Produces: implementation phases, likely files by subsystem, files read,
        recommended next files, risks, validation commands, approval gates,
        acceptance tests, model routing plan, Slack/Telegram gating,
        known unknowns, and a final verdict of exactly one of
        READY_FOR_IMPLEMENTATION_APPROVAL, HOLD_FOR_MORE_DISCOVERY, or UNSAFE.
        """
        # Collect files actually read in this session
        files_read: List[str] = []
        for st in plan.subtasks:
            if st.tool_id == "file_read" and st.status == "done":
                raw = st.params.get("path", "")
                rel = raw.replace(plan.repo_path + "/", "")
                files_read.append(rel if rel != raw else raw)
        files_read_set = set(files_read)

        # Recommended next = likely_files not yet read + standard planning files
        seen_next: set = set(files_read_set) | set(plan.likely_files)
        recommended_next: List[str] = [f for f in plan.likely_files if f not in files_read_set]
        for fpath in _PLANNING_NEXT_FILES:
            if fpath not in seen_next:
                recommended_next.append(fpath)
                seen_next.add(fpath)

        # Group files by subsystem — include both auto-inferred likely_files AND
        # explicit files that were actually read (union so no reads are marked unread)
        subsystem_all: List[str] = list(plan.likely_files)
        for fpath in files_read:
            if fpath not in set(plan.likely_files):
                subsystem_all.append(fpath)
        subsystem_files: Dict[str, List[str]] = {}
        for fpath in subsystem_all:
            label = _get_subsystem_label(fpath)
            subsystem_files.setdefault(label, []).append(fpath)

        # Determine recommendation
        files_read_count = len(files_read)
        any_failed = any(s.status == "failed" for s in plan.subtasks)
        explicit_requested = getattr(plan, "explicit_files", [])
        missing = getattr(plan, "missing_files", [])
        missing_set = set(missing)

        if explicit_requested:
            existing_explicit = [f for f in explicit_requested if f not in missing_set]
            unread_existing = [f for f in existing_explicit if f not in files_read_set]
            if unread_existing or missing:
                recommendation = "HOLD_FOR_MORE_DISCOVERY"
                if unread_existing:
                    rec_note = (
                        f"Insufficient data to verify — {len(unread_existing)} of "
                        f"{len(existing_explicit)} requested existing files were not read."
                    )
                else:
                    rec_note = (
                        f"Insufficient data to verify — {len(missing)} of "
                        f"{len(explicit_requested)} requested files were not found on disk."
                    )
            else:
                recommendation = "READY_FOR_IMPLEMENTATION_APPROVAL"
                rec_note = "Explicit discovery complete. Review this plan before implementing."
        elif files_read_count >= 2 and not any_failed and blocked_at is None:
            recommendation = "READY_FOR_IMPLEMENTATION_APPROVAL"
            rec_note = "Initial discovery complete. Review this plan before implementing."
        else:
            recommendation = "HOLD_FOR_MORE_DISCOVERY"
            rec_note = (
                "Insufficient data to verify — read more subsystem files before "
                "implementation begins."
            )

        lines: List[str] = []
        lines += ["# Jarvis Workbench — Implementation Plan", ""]
        lines += [f"**Status**: `{recommendation}`", f"*{rec_note}*", ""]

        lines += ["## Task", ""]
        lines += [
            f"- **Prompt**: {plan.prompt}",
            f"- **Task Type**: `{plan.task_type}`",
            f"- **Dry-Run**: `{plan.dry_run}`",
            f"- **Session**: `{plan.session_id}`",
            f"- **Task ID**: `{plan.task_id}`",
            f"- **Repo**: `{plan.repo_path}`",
            "",
        ]

        if blocked_at:
            lines += [
                "## Blocker",
                "",
                f"Stopped at subtask [{blocked_at.index}]: `{blocked_at.description}`",
                f"Error: `{blocked_at.error}`",
                "",
            ]

        lines += ["## Files Read in This Session", ""]
        if files_read:
            for f in files_read:
                lines.append(f"- `{f}`")
        else:
            lines.append("- Insufficient data to verify — no files read yet")
        lines.append("")

        if missing:
            lines += ["## Missing Files (Requested But Not Found on Disk)", ""]
            for f in missing:
                lines.append(f"- Insufficient data to verify — file not found: `{f}`")
            lines.append("")

        lines += ["## Likely Files by Subsystem", ""]
        if subsystem_files:
            for subsystem in sorted(subsystem_files.keys()):
                lines.append(f"**{subsystem}**")
                for f in subsystem_files[subsystem]:
                    marker = "✅" if f in files_read_set else "⬜"
                    lines.append(f"  - {marker} `{f}`")
                lines.append("")
        else:
            lines += ["Insufficient data to verify — no likely files identified from prompt.", ""]

        lines += ["## Recommended Next Files to Inspect", ""]
        if recommended_next:
            for f in recommended_next[:16]:
                lines.append(f"- `{f}`")
        else:
            lines.append("- All identified files have been read in this session.")
        lines.append("")

        # ----------------------------------------------------------------
        # Source-derived sections — built from actual file_read outputs
        # ----------------------------------------------------------------
        arch = self._synthesize_arch_map(plan, files_read_set)
        files_to_change = self._derive_files_to_change(files_read, plan.prompt)
        new_files_needed = self._derive_new_files_needed(
            files_read, missing, plan.prompt
        )

        # Compute per-subsystem read flags once; reused across multiple sections
        _approval_read = any("approval" in f for f in files_read_set)
        _automation_read = any("automation" in f or "constitution" in f for f in files_read_set)
        _notify_read = any("notify" in f or "notifier" in f for f in files_read_set)
        _slack_read = any("slack" in f for f in files_read_set)
        _telegram_read = any("telegram" in f for f in files_read_set)
        _model_router_read = any("model_router" in f for f in files_read_set)
        _cost_ledger_read = any("cost_ledger" in f for f in files_read_set)
        _workbench_page_read = any(
            "WorkbenchPage" in f or "workbench_page" in f.lower() for f in files_read_set
        )
        _approval_bell_read = any("ApprovalBell" in f for f in files_read_set)

        lines += ["## Current Architecture Map", ""]
        if arch["components"]:
            for fpath, info in sorted(arch["components"].items()):
                role = info["role"]
                classes = info["classes"]
                routes = info["routes"]
                functions = info["functions"]
                lc = info["line_count"]
                tag = f" ({lc} lines)" if lc else " (dry-run — content not available)"
                lines.append(f"**`{fpath}`** — {role}{tag}")
                if classes:
                    lines.append(f"  - Classes: {', '.join(f'`{c}`' for c in classes)}")
                if routes:
                    lines.append(f"  - Routes: {', '.join(f'`{r}`' for r in routes)}")
                if functions:
                    lines.append(f"  - Key functions: {', '.join(f'`{fn}`' for fn in functions[:5])}")
                lines.append("")
        else:
            lines += ["- Insufficient data to verify — no files were read this session", ""]

        lines += ["## Files Likely to Change", ""]
        if files_to_change["backend"]:
            lines.append("**Backend**")
            for f in files_to_change["backend"]:
                lines.append(f"- `{f}`")
            lines.append("")
        if files_to_change["frontend"]:
            lines.append("**Frontend**")
            for f in files_to_change["frontend"]:
                lines.append(f"- `{f}`")
            lines.append("")
        if files_to_change["tests"]:
            lines.append("**Tests**")
            for f in files_to_change["tests"]:
                lines.append(f"- `{f}`")
            lines.append("")
        if not any(files_to_change.values()):
            lines += ["- Insufficient data to verify — no source files inspected", ""]

        lines += ["## New Files Likely Needed", ""]
        if new_files_needed:
            for nf in new_files_needed:
                lines.append(f"- `{nf}`")
        else:
            lines.append("- None")
        lines.append("")

        lines += ["## Backend / API Implementation Plan", ""]
        lines += [
            "- Add/update server routes in `src/openjarvis/server/` for workbench job status "
            "and notification endpoints",
            "- Extend `CodingManager.plan()` and `CodingManager.execute()` for new task types",
            "- Wire notification events from `Notifier` through `channel_bridge` to Slack/Telegram",
            "- Gate all write/commit/push actions behind approval store checks",
        ]
        if not _approval_read:
            lines.append(
                "- Insufficient data to verify — `approval_store.py` / `approval_routes.py` "
                "not inspected; exact gate implementation unknown"
            )
        lines.append("")

        lines += ["## Frontend Implementation Plan", ""]
        lines += [
            "- Update `WorkbenchPage.tsx` to display job status, report output, and dry-run badge",
            "- Integrate `ApprovalBell` notification badge for pending approvals",
            "- Add Chat-to-Workbench status indicator in the Chat area",
            "- Poll or subscribe to workbench job state changes",
        ]
        if not _workbench_page_read:
            lines.append(
                "- Insufficient data to verify — `WorkbenchPage.tsx` not inspected; "
                "exact component structure unknown"
            )
        if not _approval_bell_read:
            lines.append(
                "- Insufficient data to verify — `ApprovalBell.tsx` not inspected; "
                "exact approval bell API unknown"
            )
        lines.append("")

        lines += ["## Notification / Event Implementation Plan", ""]
        lines += [
            "- Define unified event schema: `{event_type, payload, timestamp, source}`",
            "- In-app: emit events via `Notifier` to frontend SSE/WebSocket",
            "- Slack path: `Notifier` \u2192 `channel_bridge` \u2192 `slack.py` (gated, dry-run safe)",
            "- Telegram path: `Notifier` \u2192 `channel_bridge` \u2192 `telegram.py` (gated, dry-run safe)",
            "- Dedupe: hash-based deduplication per `(event_type, payload_hash)` with TTL",
            "- Rate-limit: max 1 send per minute per channel per event type",
            "- Dry-run: all send paths must no-op when `dry_run=True`",
        ]
        if not _notify_read:
            lines.append(
                "- Insufficient data to verify — `notifier.py` / `notify_routes.py` "
                "not inspected; exact event schema unknown"
            )
        lines.append("")

        lines += ["## Approval / Autopilot Policy Plan", ""]
        lines += [
            "- Plan Only: no file_write/commit/push — enforced in `CodingManager`",
            "- Dry Run: all subtasks execute but writes are no-ops — enforced by dry_run flag",
            "- Live Guarded: each write/commit gated by `ApprovalStore.require_approval()`",
            "- Live Autopilot: bundled approval allowed only for pre-certified low-risk tasks",
            "- High-risk gate: `git_push` always requires explicit Manager approval",
        ]
        if not _automation_read:
            lines.append(
                "- Insufficient data to verify — `automation_policy.py` / `constitution.py` "
                "not inspected; exact policy gate thresholds unknown"
            )
        lines.append("")

        lines += ["## Tests to Add / Update", ""]
        lines += [
            "- `test_us14a_planner.py`: add tests for each new report section",
            "- `test_us14a.py`: verify dry-run mode suppresses writes and external sends",
            "- `test_notification_dry_run_no_send`: assert `Notifier.send()` not called in dry_run",
            "- `test_chat_to_workbench_bridge`: assert chat message creates workbench task",
            "- `test_slack_telegram_mock`: mock channels; assert no live sends in tests",
            "- `test_approval_gate`: assert `file_write` blocked when approval pending",
            "- `test_model_routing_cost_ledger`: assert `$0.00` cost in Plan-Only sessions",
            "- Frontend: `npm run build` must exit 0 after any frontend changes",
        ]
        lines.append("")

        lines += ["## Implementation Phases", ""]
        for ph in self._extract_implementation_phases(plan.prompt):
            lines.append(f"- {ph}")
        lines.append("")

        lines += ["## Risks", ""]
        for r in plan.risks:
            lines.append(f"- {r}")
        lines.append("")

        lines += ["## Validation Commands", ""]
        for v in self._suggest_planning_validation():
            lines.append(f"- `{v}`")
        lines.append("")

        lines += ["## Approval Gates", ""]
        for g in plan.approval_gates:
            lines.append(f"- {g}")
        lines.append("")

        lines += ["## Acceptance Tests", ""]
        for t in self._identify_acceptance_tests(plan.prompt):
            lines.append(f"- {t}")
        lines.append("")

        lines += ["## Model Routing / Provider Verification Plan", ""]
        lines += [
            "- Verify `MockModelAdapter` is active for all dry-run/Plan-Only runs (zero paid calls)",
            "- Check `ModelRouter` DB for routing decisions after each subtask",
            "- Confirm read-only tools route to `local` tier; LLM subtasks to `cloud-cheap`",
            "- Verify cost ledger records `$0.000000` for Plan-Only sessions",
        ]
        if not _model_router_read:
            lines.append(
                "- Insufficient data to verify — `model_router.py` not inspected this session"
            )
        if not _cost_ledger_read:
            lines.append(
                "- Insufficient data to verify — `cost_ledger.py` not inspected this session"
            )
        lines.append("")

        lines += ["## Slack / Telegram Notification Gating Plan", ""]
        lines += [
            "- No Slack/Telegram messages must be sent during Plan Only or Dry-Run",
            "- Dry-run test: run workbench with `dry_run=True`; assert no `channel_bridge.send()` calls",
            "- Live test: requires explicit Manager approval; scope to a sandbox channel only",
            "- Integration test: mock `Notifier`; assert `send()` not called in dry-run mode",
            "- Acceptance gate: Slack/Telegram test sends require Manager approval before execution",
        ]
        _gating_gaps = []
        if not _notify_read:
            _gating_gaps.append("`notify_routes.py` / `notifier.py`")
        if not _slack_read:
            _gating_gaps.append("`slack.py`")
        if not _telegram_read:
            _gating_gaps.append("`telegram.py`")
        if _gating_gaps:
            lines.append(
                "- Insufficient data to verify — " + ", ".join(_gating_gaps)
                + " not inspected this session"
            )
        lines.append("")

        lines += ["## Known Unknowns", ""]
        for u in self._identify_known_unknowns(plan.prompt, list(files_read_set)):
            lines.append(f"- Insufficient data to verify — {u}")
        lines.append("")

        lines += [
            "## Final Recommendation",
            "",
            f"**`{recommendation}`**",
            "",
            rec_note,
            "",
            "Do not start implementation until this plan has been reviewed and approved.",
            "",
            "---",
            "",
            f"*Jarvis Coding Workbench | dry_run={plan.dry_run} | {plan.task_type} | session={plan.session_id}*",
        ]

        return "\n".join(lines)

    def _extract_implementation_phases(self, prompt: str) -> List[str]:
        """Derive implementation phases from prompt keywords."""
        p = prompt.lower()
        phases = [
            "Phase 1: Discovery & Architecture Review — read all relevant source files, "
            "map current system state, identify integration points",
        ]
        n = 2
        if any(w in p for w in ("chat-to-workbench", "chat to workbench", "pa chat", "bridge")):
            phases.append(
                f"Phase {n}: PA Chat \u2192 Workbench Bridge \u2014 implement chat message routing "
                "to workbench task queue"
            )
            n += 1
        if any(w in p for w in ("notification", "notify", "unified")):
            phases.append(
                f"Phase {n}: Unified Notifications \u2014 implement cross-channel notification "
                "delivery (macOS, Slack, Telegram)"
            )
            n += 1
        if any(w in p for w in ("autopilot", "guarded")):
            phases.append(
                f"Phase {n}: Guarded Autopilot \u2014 implement approval gate enforcement "
                "with kill-switch policy per governance constitution"
            )
            n += 1
        phases.append(
            f"Phase {n}: Integration Tests \u2014 add/update targeted tests for each new subsystem"
        )
        n += 1
        phases.append(
            f"Phase {n}: Frontend Wiring \u2014 update UI (status indicators, approval bells, "
            "Workbench/Chat bridge status)"
        )
        n += 1
        phases.append(
            f"Phase {n}: Acceptance & Governance \u2014 run full validation, review against "
            "constitution, commit + push on Manager approval"
        )
        return phases

    def _suggest_planning_validation(self) -> List[str]:
        """Return validation commands shown in the planning report."""
        return [
            ".venv/bin/python -m pytest tests/workbench/test_us14a_planner.py -x -q --tb=short",
            ".venv/bin/python -m pytest tests/workbench/test_us14a.py -x -q --tb=short",
            ".venv/bin/python -m pytest tests/workbench/ -q --tb=short",
            "cd frontend && npm run build",
        ]

    def _identify_acceptance_tests(self, prompt: str) -> List[str]:
        """Identify acceptance tests needed for the task."""
        p = prompt.lower()
        tests = [
            ".venv/bin/python -m pytest tests/workbench/test_us14a_planner.py -x -q --tb=short",
            ".venv/bin/python -m pytest tests/workbench/test_us14a.py -x -q --tb=short",
        ]
        if any(w in p for w in ("notification", "notify", "slack", "telegram")):
            tests.append(
                "test_notification_dry_run_no_send: assert Notifier.send() not called in dry_run"
            )
        if any(w in p for w in ("autopilot", "guarded")):
            tests.append(
                "test_guarded_autopilot_approval_gate: assert file_write blocked without approval"
            )
        if any(w in p for w in ("chat-to-workbench", "chat to workbench")):
            tests.append(
                "test_chat_to_workbench_bridge: assert chat message creates workbench task"
            )
        tests.append("E2E dry-run: plan + execute with dry_run=True \u2192 status=done_dry_run, zero writes")
        tests.append("Frontend build: npm run build \u2192 exit 0")
        return tests

    def _synthesize_arch_map(
        self, plan: "TaskPlan", files_read_set: set
    ) -> Dict[str, Any]:
        """Build a source-derived architecture map from file_read subtask outputs.

        Parses actual file content to extract classes, routes, and top-level
        functions.  Falls back gracefully when content is empty/unavailable
        (e.g. dry_run mode where reads are simulated with empty output).
        """
        arch: Dict[str, Any] = {
            "components": {},
            "files_with_content": [],
            "files_dry_run_only": [],
        }
        for st in plan.subtasks:
            if st.tool_id != "file_read" or st.status != "done":
                continue
            raw_path = st.params.get("path", "")
            rel = raw_path.replace(plan.repo_path + "/", "")
            fpath = rel if rel != raw_path else raw_path
            content = st.output or ""
            role = _get_subsystem_label(fpath)

            classes = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
            routes = re.findall(
                r'@(?:app|router|bp|api)\.(?:get|post|put|delete|patch|route)\s*\(\s*["\']([^"\']+)',
                content, re.MULTILINE,
            )
            functions = re.findall(r"^(?:async\s+)?def\s+(\w+)", content, re.MULTILINE)
            has_content = bool(content.strip())
            arch["components"][fpath] = {
                "role": role,
                "classes": classes[:6],
                "routes": routes[:6],
                "functions": functions[:8],
                "line_count": len(content.splitlines()) if has_content else 0,
                "has_content": has_content,
            }
            if has_content:
                arch["files_with_content"].append(fpath)
            else:
                arch["files_dry_run_only"].append(fpath)
        return arch

    def _derive_files_to_change(
        self, files_read: List[str], prompt: str
    ) -> Dict[str, List[str]]:
        """Derive exact files likely to change based on inspected architecture + prompt."""
        p = prompt.lower()
        backend: List[str] = []
        frontend: List[str] = []
        tests: List[str] = []
        for fpath in files_read:
            f = fpath.lower()
            if fpath.startswith("frontend/") or fpath.endswith(".tsx") or fpath.endswith(".ts"):
                frontend.append(fpath)
            elif fpath.startswith("tests/"):
                tests.append(fpath)
            else:
                if any(kw in f for kw in (
                    "routes", "manager", "notifier", "slack", "telegram",
                    "approval", "automation", "constitution", "model_router",
                    "cost_ledger", "coding_manager", "channel_bridge", "notif",
                )):
                    backend.append(fpath)
        if not tests:
            for fpath in files_read:
                if "test_" in fpath.lower():
                    tests.append(fpath)
        return {"backend": backend, "frontend": frontend, "tests": tests}

    def _derive_new_files_needed(
        self, files_read: List[str], missing_files: List[str], prompt: str
    ) -> List[str]:
        """Derive new files likely needed from missing explicit files + architecture gaps."""
        new_files: List[str] = []
        for fpath in missing_files:
            new_files.append(f"{fpath} \u2014 required but not yet created")
        return new_files

    def _identify_known_unknowns(self, prompt: str, files_read: List[str]) -> List[str]:
        """Identify known unknowns from unread subsystem files implied by the prompt.

        Only reports a file as unknown if it was NOT present in files_read.
        Never contradicts a completed file_read by claiming the file was not inspected.
        """
        p = prompt.lower()
        fr_lower = [f.lower() for f in files_read]
        unknowns: List[str] = []

        notify_read = any("notify" in f or "notifier" in f for f in fr_lower)
        slack_read = any("slack" in f for f in fr_lower)
        telegram_read = any("telegram" in f for f in fr_lower)
        automation_read = any("automation" in f or "constitution" in f for f in fr_lower)
        model_router_read = any("model_router" in f for f in fr_lower)
        routes_read = any("routes.py" in f or "chatarea" in f for f in fr_lower)

        if any(w in p for w in ("notification", "notify")) and not notify_read:
            unknowns.append(
                "notify_routes.py / notifier.py not inspected \u2014 notification API surface unknown"
            )
        if "slack" in p and not slack_read:
            unknowns.append("slack.py not inspected \u2014 Slack message format / rate-limits unknown")
        if "telegram" in p and not telegram_read:
            unknowns.append("telegram.py not inspected \u2014 Telegram bot API / polling config unknown")
        if any(w in p for w in ("autopilot", "guarded")) and not automation_read:
            unknowns.append(
                "automation_policy.py / constitution.py not inspected \u2014 "
                "Guarded Autopilot approval gate behavior unknown"
            )
        if any(w in p for w in ("model", "router", "routing")) and not model_router_read:
            unknowns.append(
                "model_router.py not inspected \u2014 provider routing / cost behavior unknown"
            )
        if "chat" in p and not routes_read:
            unknowns.append("routes.py / ChatArea.tsx not inspected \u2014 PA chat message flow unknown")
        if not unknowns:
            unknowns.append("No critical unknowns identified at this discovery depth")
        return unknowns

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
        cost = self._costs.session_total(session_id)
        routing = self._router.session_cost_summary(session_id)
        cost["routing"] = routing
        return cost

    def get_routing_log(self, session_id: str) -> List[Dict[str, Any]]:
        return self._router.get_routing_log(session_id)

    def get_provider_config(self) -> Dict[str, Any]:
        return self._router.get_provider_config_summary()

    def get_jobs(self, task_id: str) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.list_by_task(task_id)]


__all__ = [
    "CodingManager",
    "TaskPlan",
    "Subtask",
    "classify_prompt",
    "_bounded_search_dir",
    "_get_subsystem_label",
    "_extract_explicit_files",
    "_is_safe_repo_relative",
    "_SEARCH_TARGETED_DIRS",
    "_SEARCH_EXCLUDE_DIRS",
    "_PLANNING_NEXT_FILES",
    "_SUBSYSTEM_LABELS",
    "_FILE_EXTENSIONS",
]
