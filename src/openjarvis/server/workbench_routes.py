"""Workbench REST API — US14A Jarvis Coding Workbench endpoints.

Routes:
  POST /v1/workbench/plan         — create a task plan from a prompt
  POST /v1/workbench/execute      — execute a task plan
  POST /v1/workbench/approve      — approve a pending subtask
  GET  /v1/workbench/status/{sid} — get plan status by session_id
  GET  /v1/workbench/diff         — generate diff preview
  POST /v1/workbench/validate     — run validation command
  GET  /v1/workbench/jobs         — list recent jobs
  GET  /v1/workbench/cost/{sid}   — get cost summary for a session
  GET  /v1/workbench/checkpoints/{sid} — list checkpoints for session
  GET  /v1/workbench/repo/status  — git status for a repo path
  GET  /v1/workbench/doctor       — US14A readiness checks

Governance:
  - dry_run defaults to true
  - commit/push always require approval
  - no secrets in any response
  - stop_on_blocker enforced by CodingManager
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for workbench routes")

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    prompt: str
    repo_path: str = Field(default=".")
    dry_run: bool = Field(default=True)
    stop_on_blocker: bool = Field(default=True)


class ExecuteRequest(BaseModel):
    session_id: str
    task_id: str
    prompt: str
    repo_path: str = Field(default=".")
    dry_run: bool = Field(default=True)
    stop_on_blocker: bool = Field(default=True)
    approved_subtask_ids: List[str] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    session_id: str
    task_id: str
    subtask_id: str
    prompt: str
    repo_path: str = Field(default=".")


class DiffRequest(BaseModel):
    repo_path: str = Field(default=".")


class ValidateRequest(BaseModel):
    repo_path: str = Field(default=".")
    command: str = Field(
        default="python -m pytest tests/ -x -q --tb=short 2>&1 | head -80 || echo 'No tests'"
    )
    timeout: int = Field(default=60)


# ---------------------------------------------------------------------------
# Singleton manager helpers
# ---------------------------------------------------------------------------

_managers: Dict[str, Any] = {}


def _get_manager(repo_path: str) -> Any:
    """Return a CodingManager for the given repo path."""
    from openjarvis.workbench.coding_manager import CodingManager

    key = str(repo_path)
    if key not in _managers:
        _managers[key] = CodingManager(repo_path=repo_path)
    return _managers[key]


# In-memory plan store (keyed by session_id).
# For production this would be persisted; for US14A SQLite checkpoints cover it.
_plans: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/v1/workbench/plan")
async def create_plan(req: PlanRequest) -> Dict[str, Any]:
    """Create a task plan from a prompt.

    Does NOT execute — returns the plan for review before execution.
    dry_run defaults to true.
    """
    manager = _get_manager(req.repo_path)
    plan = manager.plan(
        prompt=req.prompt,
        dry_run=req.dry_run,
        stop_on_blocker=req.stop_on_blocker,
        repo_path=req.repo_path,
    )
    _plans[plan.session_id] = (plan, manager)
    logger.info("Workbench plan created: session=%s", plan.session_id)
    return {"ok": True, "plan": plan.to_dict()}


@router.post("/v1/workbench/execute")
async def execute_plan(req: ExecuteRequest) -> Dict[str, Any]:
    """Plan then execute a coding task.

    Creates a new plan and executes it in one step.
    Commit/push are skipped if dry_run=true (default).
    """
    manager = _get_manager(req.repo_path)
    plan = manager.plan(
        prompt=req.prompt,
        dry_run=req.dry_run,
        stop_on_blocker=req.stop_on_blocker,
        repo_path=req.repo_path,
    )
    _plans[plan.session_id] = (plan, manager)

    plan = manager.execute(plan, approved_subtask_ids=req.approved_subtask_ids)
    _plans[plan.session_id] = (plan, manager)

    logger.info(
        "Workbench execute: session=%s status=%s cost=$%.6f",
        plan.session_id, plan.status, plan.total_cost_usd,
    )
    return {"ok": True, "plan": plan.to_dict()}


@router.post("/v1/workbench/approve")
async def approve_subtask(req: ApproveRequest) -> Dict[str, Any]:
    """Approve a pending subtask and resume execution.

    Only commit/push/delete subtasks require approval.
    This represents the Manager approval gate.
    """
    entry = _plans.get(req.session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {req.session_id}")

    plan, manager = entry
    if plan.task_id != req.task_id:
        raise HTTPException(status_code=400, detail="task_id mismatch")

    plan = manager.approve_subtask(plan, req.subtask_id)
    _plans[plan.session_id] = (plan, manager)
    return {"ok": True, "plan": plan.to_dict()}


@router.get("/v1/workbench/status/{session_id}")
async def get_plan_status(session_id: str) -> Dict[str, Any]:
    """Get the current status of a plan by session_id."""
    entry = _plans.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    plan, _ = entry
    return {"ok": True, "plan": plan.to_dict()}


@router.post("/v1/workbench/diff")
async def generate_diff(req: DiffRequest) -> Dict[str, Any]:
    """Generate a diff preview of the current working tree."""
    manager = _get_manager(req.repo_path)
    diff = manager.generate_diff(repo_path=req.repo_path)
    return {"ok": True, "diff": diff, "repo_path": req.repo_path}


@router.post("/v1/workbench/validate")
async def run_validation(req: ValidateRequest) -> Dict[str, Any]:
    """Run a validation command and capture output."""
    manager = _get_manager(req.repo_path)
    output = manager.run_validation(
        command=req.command,
        repo_path=req.repo_path,
        timeout=req.timeout,
    )
    return {"ok": True, "output": output, "command": req.command}


@router.get("/v1/workbench/jobs")
async def list_jobs(repo_path: str = ".") -> Dict[str, Any]:
    """List recent workbench jobs."""
    manager = _get_manager(repo_path)
    jobs = manager._jobs.list_recent(limit=50)
    return {"ok": True, "jobs": [j.to_dict() for j in jobs], "count": len(jobs)}


@router.get("/v1/workbench/cost/{session_id}")
async def get_cost_summary(session_id: str) -> Dict[str, Any]:
    """Get the cost summary for a workbench session."""
    entry = _plans.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    plan, manager = entry
    summary = manager.get_cost_summary(plan.session_id)
    return {"ok": True, "cost": summary}


@router.get("/v1/workbench/checkpoints/{session_id}")
async def get_checkpoints(session_id: str) -> Dict[str, Any]:
    """List accepted checkpoints for a workbench session."""
    entry = _plans.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    plan, manager = entry
    checkpoints = manager.get_checkpoints(plan.session_id)
    return {"ok": True, "checkpoints": checkpoints}


@router.get("/v1/workbench/repo/status")
async def get_repo_status(repo_path: str = ".") -> Dict[str, Any]:
    """Get git status for a repo path."""
    manager = _get_manager(repo_path)
    result = manager._call_tool("git_status", {"repo_path": repo_path})
    branch_result = manager._call_tool("git_branch", {
        "repo_path": repo_path, "action": "current"
    })
    log_result = manager._call_tool("git_log", {
        "repo_path": repo_path, "count": 5, "oneline": True
    })
    return {
        "ok": True,
        "repo_path": repo_path,
        "status": result.get("content", ""),
        "branch": (branch_result.get("content") or "").strip(),
        "recent_commits": log_result.get("content", ""),
    }


@router.get("/v1/workbench/doctor")
async def workbench_doctor(repo_path: str = ".") -> Dict[str, Any]:
    """US14A readiness checks for the Coding Workbench."""
    import shutil
    from pathlib import Path

    checks: List[Dict[str, Any]] = []

    def chk(name: str, status: str, evidence: str) -> Dict[str, Any]:
        return {"check": name, "status": status, "evidence": evidence}

    # Check 1: git available
    git_ok = shutil.which("git") is not None
    checks.append(chk("git_binary", "pass" if git_ok else "fail",
                       "git found on PATH" if git_ok else "git not found"))

    # Check 2: rg/grep available
    rg_ok = shutil.which("rg") is not None
    grep_ok = shutil.which("grep") is not None
    search_ok = rg_ok or grep_ok
    checks.append(chk("search_tool", "pass" if search_ok else "fail",
                       f"rg={'yes' if rg_ok else 'no'}, grep={'yes' if grep_ok else 'no'}"))

    # Check 3: repo path exists
    rp = Path(repo_path)
    repo_exists = rp.exists() and (rp / ".git").exists()
    checks.append(chk("repo_path", "pass" if repo_exists else "warn",
                       f"repo_path={repo_path}, is_git_repo={repo_exists}"))

    # Check 4: CodingManager can be instantiated
    try:
        from openjarvis.workbench.coding_manager import CodingManager
        CodingManager(repo_path=repo_path)
        checks.append(chk("coding_manager", "pass", "CodingManager instantiated"))
    except Exception as exc:
        checks.append(chk("coding_manager", "fail", str(exc)))

    # Check 5: JobQueue works
    try:
        from openjarvis.workbench.job_queue import JobQueue
        q = JobQueue()
        q.list_recent(limit=1)
        checks.append(chk("job_queue", "pass", "JobQueue SQLite accessible"))
    except Exception as exc:
        checks.append(chk("job_queue", "fail", str(exc)))

    # Check 6: CostLedger works
    try:
        from openjarvis.workbench.cost_ledger import CostLedger
        ledger = CostLedger()
        ledger.list_recent(limit=1)
        checks.append(chk("cost_ledger", "pass", "CostLedger SQLite accessible"))
    except Exception as exc:
        checks.append(chk("cost_ledger", "fail", str(exc)))

    # Check 7: CheckpointStore works
    try:
        from openjarvis.workbench.checkpoint import CheckpointStore
        store = CheckpointStore()
        store.list_checkpoints("_probe_")
        checks.append(chk("checkpoint_store", "pass", "CheckpointStore SQLite accessible"))
    except Exception as exc:
        checks.append(chk("checkpoint_store", "fail", str(exc)))

    # Check 8: file_search tool instantiable
    try:
        from openjarvis.tools.file_search import FileSearchTool
        t = FileSearchTool()
        checks.append(chk("tool_file_search", "pass",
                           "FileSearchTool instantiated, tool_id=%s" % t.tool_id))
    except Exception as exc:
        checks.append(chk("tool_file_search", "fail", str(exc)))

    # Check 9: git_push tool instantiable
    try:
        from openjarvis.tools.git_tool import GitPushTool
        t = GitPushTool()
        checks.append(chk("tool_git_push", "pass",
                           "GitPushTool instantiated, tool_id=%s" % t.tool_id))
    except Exception as exc:
        checks.append(chk("tool_git_push", "fail", str(exc)))

    # Check 10: Governance constitution accessible
    try:
        from openjarvis.governance.constitution import Verdict
        checks.append(chk("governance", "pass", f"Verdict enum: {[v.value for v in Verdict]}"))
    except Exception as exc:
        checks.append(chk("governance", "fail", str(exc)))

    # Check 11: ModelRouter accessible with mock adapter
    try:
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter
        router = ModelRouter(adapter_override=MockModelAdapter())
        cfg = router.get_provider_config_summary()
        checks.append(chk("model_router", "pass",
                           f"ModelRouter ready, adapter={cfg['adapter']}, key_masked={cfg['openrouter_key_value']=='MASKED'}"))
    except Exception as exc:
        checks.append(chk("model_router", "fail", str(exc)))

    # Check 12: Tiered routing policy accessible
    try:
        from openjarvis.workbench.model_router import _TOOL_TIER_POLICY, _TASK_CATEGORY_TIERS
        checks.append(chk("routing_policy", "pass",
                           f"{len(_TOOL_TIER_POLICY)} tool rules, {len(_TASK_CATEGORY_TIERS)} category rules"))
    except Exception as exc:
        checks.append(chk("routing_policy", "fail", str(exc)))

    by_status: Dict[str, int] = {}
    for c in checks:
        s = c["status"]
        by_status[s] = by_status.get(s, 0) + 1

    all_pass = by_status.get("fail", 0) == 0
    return {
        "ok": all_pass,
        "total": len(checks),
        "by_status": by_status,
        "checks": checks,
        "verdict": "ACCEPT" if all_pass else "HOLD",
    }


@router.get("/v1/workbench/events/{session_id}")
async def get_workbench_events(session_id: str, limit: int = 50) -> Dict[str, Any]:
    """Return Workbench lifecycle events for a session (local audit log only).

    Events are purely informational local records.
    No external Slack/Telegram sends occur from this endpoint.
    """
    entry = _plans.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _, manager = entry
    events = manager.get_events(session_id, limit=limit)
    return {
        "ok": True,
        "session_id": session_id,
        "events": events,
        "count": len(events),
    }


@router.get("/v1/workbench/routing-log")
async def get_routing_log(session_id: str, repo_path: str = ".") -> Dict[str, Any]:
    """Return routing decisions for a session."""
    try:
        mgr = _get_manager(repo_path)
        log = mgr.get_routing_log(session_id)
        return {"ok": True, "session_id": session_id, "routing_log": log, "count": len(log)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/workbench/provider-config")
async def get_provider_config(repo_path: str = ".") -> Dict[str, Any]:
    """Return model provider config summary (key masked)."""
    try:
        mgr = _get_manager(repo_path)
        return {"ok": True, "config": mgr.get_provider_config()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


__all__ = ["router"]


@router.get("/autopilot/guard")
def workbench_autopilot_guard() -> dict:
    """Read-only Workbench autopilot guard policy.

    This endpoint exposes policy state for UI visibility only.
    It does not execute tasks, approve actions, bypass approval gates,
    send notifications, commit, push, delete, deploy, or access secrets.
    """
    protected_actions = [
        "shell_exec",
        "git_commit",
        "git_push",
        "file_delete",
        "deploy",
        "external_notify_slack",
        "external_notify_telegram",
        "secrets_access",
        "paid_model_escalation",
    ]
    return {
        "ok": True,
        "mode": "guarded_preview",
        "autopilot_runtime_enabled": False,
        "disabled_by_default": True,
        "can_execute_without_approval": False,
        "approval_bypass_allowed": False,
        "protected_actions": protected_actions,
        "allowed_without_approval": [
            "read_only_inspection",
            "planning",
            "status_check",
            "local_ui_update",
        ],
        "notes": [
            "Autopilot controls are visible but runtime execution is disabled.",
            "Manager approval gates still apply.",
            "No Slack/Telegram sends are triggered by this endpoint.",
            "No commit, push, shell execution, deploy, delete, or secrets access is allowed here.",
        ],
    }
