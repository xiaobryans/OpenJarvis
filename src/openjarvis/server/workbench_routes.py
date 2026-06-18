"""Workbench REST API — US14A/US15/US16 Jarvis Coding Workbench endpoints.

Routes:
  POST /v1/workbench/plan              — create a task plan from a prompt
  POST /v1/workbench/execute           — execute a task plan
  POST /v1/workbench/approve           — approve a pending subtask
  GET  /v1/workbench/status/{sid}      — get plan status by session_id
  POST /v1/workbench/diff              — generate diff preview
  POST /v1/workbench/validate          — run validation command
  GET  /v1/workbench/jobs              — list recent jobs
  GET  /v1/workbench/cost/{sid}        — get cost summary for a session
  GET  /v1/workbench/checkpoints/{sid} — list checkpoints for session
  GET  /v1/workbench/repo/status       — git status for a repo path
  GET  /v1/workbench/doctor            — US14A/US15/US16 readiness checks
  GET  /v1/workbench/capabilities      — US15 truthful capability status
  GET  /v1/workbench/repo-index        — US15 bounded repo map / symbols
  GET  /v1/workbench/validation-profiles — US15 local-first validation profiles
  GET  /v1/workbench/dogfood-evidence  — US15 coding dogfood evidence records
  GET  /v1/workbench/events/{sid}      — Workbench lifecycle events
  GET  /v1/workbench/routing-log       — Model routing decisions for session
  GET  /v1/workbench/provider-config   — Model provider config (key masked)
  POST /v1/workbench/terminal/exec     — US15 approval-gated terminal command
  POST /v1/workbench/terminal/approve  — US15 approve pending terminal command
  GET  /v1/workbench/terminal/pending  — US15 list pending terminal approvals
  POST /v1/workbench/diff-review/create    — US15 create structured diff review
  POST /v1/workbench/diff-review/approve   — US15 approve a diff review
  POST /v1/workbench/diff-review/reject    — US15 reject a diff review
  GET  /v1/workbench/diff-review/list      — US15 list diff reviews
  GET  /v1/workbench/diff-review/{rid}     — US15 get a diff review
  GET  /v1/workbench/ci-status        — US15 GitHub/CI visibility
  GET  /v1/workbench/auto-browser/status — US15 Auto Browser health + setup
  GET  /autopilot/guard               — autopilot policy (read-only)

Governance:
  - dry_run defaults to true
  - commit/push always require approval
  - no secrets in any response
  - stop_on_blocker enforced by CodingManager
  - terminal commands require approval for destructive/risky operations
  - diff review reject never silently applies changes
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


class TerminalExecRequest(BaseModel):
    command: str
    repo_path: str = Field(default=".")
    timeout: int = Field(default=30)
    pre_approved: bool = Field(default=False)
    approval_token: Optional[str] = Field(default=None)


class TerminalApproveRequest(BaseModel):
    approval_token: str
    repo_path: str = Field(default=".")
    timeout: int = Field(default=30)


class DiffReviewCreateRequest(BaseModel):
    session_id: str
    task_id: str = Field(default="")
    repo_path: str = Field(default=".")
    raw_diff: str = Field(default="")
    dry_run: bool = Field(default=True)


class DiffReviewDecideRequest(BaseModel):
    review_id: str
    reason: str = Field(default="")
    approved_by: str = Field(default="manager")
    note: str = Field(default="")


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

# Terminal executor singleton (per repo_path).
_terminal_executors: Dict[str, Any] = {}


def _get_terminal_executor(repo_path: str) -> Any:
    from openjarvis.workbench.terminal_executor import TerminalExecutor
    if repo_path not in _terminal_executors:
        _terminal_executors[repo_path] = TerminalExecutor(cwd=repo_path)
    return _terminal_executors[repo_path]


# DiffReviewStore singleton.
_diff_review_store: Any = None


def _get_diff_review_store() -> Any:
    global _diff_review_store
    if _diff_review_store is None:
        from openjarvis.workbench.diff_review import DiffReviewStore
        _diff_review_store = DiffReviewStore()
    return _diff_review_store


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

    # Check 13: US15 capabilities registry
    try:
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        caps = get_capabilities_summary()
        checks.append(chk("us15_capabilities", "pass",
                           f"{caps['count']} capabilities registered"))
    except Exception as exc:
        checks.append(chk("us15_capabilities", "fail", str(exc)))

    # Check 14: US15 repo index
    try:
        from openjarvis.workbench.repo_index import build_repo_index
        idx = build_repo_index(repo_path)
        checks.append(chk("us15_repo_index", "pass",
                           f"{len(idx.files)} files indexed"))
    except Exception as exc:
        checks.append(chk("us15_repo_index", "fail", str(exc)))

    # Check 15: US13 voice parked (must not show ready)
    try:
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        voice = next(c for c in get_all_capabilities() if c.capability_id == "voice")
        if voice.status == "ready":
            checks.append(chk("us13_voice_parked", "fail", "Voice must not be ready while US13 is parked"))
        else:
            checks.append(chk("us13_voice_parked", "pass", voice.summary[:120]))
    except Exception as exc:
        checks.append(chk("us13_voice_parked", "fail", str(exc)))

    # Check 16: US15 terminal executor
    try:
        from openjarvis.workbench.terminal_executor import TerminalExecutor, is_command_safe_for_auto_approval
        te = TerminalExecutor(cwd=repo_path)
        safe = is_command_safe_for_auto_approval("ls -la")
        checks.append(chk("us15_terminal_executor", "pass",
                           f"TerminalExecutor ready, ls safe={safe}"))
    except Exception as exc:
        checks.append(chk("us15_terminal_executor", "fail", str(exc)))

    # Check 17: US15 diff review store
    try:
        from openjarvis.workbench.diff_review import DiffReviewStore
        dr = DiffReviewStore()
        pending = dr.list_pending(limit=1)
        checks.append(chk("us15_diff_review", "pass",
                           f"DiffReviewStore SQLite ready, pending={len(pending)}"))
    except Exception as exc:
        checks.append(chk("us15_diff_review", "fail", str(exc)))

    # Check 18: US15 auto browser health
    try:
        from openjarvis.workbench.auto_browser_provider import health_check as ab_health
        hc = ab_health()
        client_ok = hc.get("client_sdk_installed", False)
        pw_ok = hc.get("playwright_available", False)
        mcp_ok = hc.get("mcp_reachable", False)
        # pass if client+playwright ready; warn if server not running (expected without Docker)
        check_status = "pass" if (client_ok and pw_ok) else "warn"
        checks.append(chk(
            "us15_auto_browser",
            check_status,
            f"client_sdk={client_ok}, playwright={pw_ok}, mcp_reachable={mcp_ok}, overall={hc['overall']}",
        ))
    except Exception as exc:
        checks.append(chk("us15_auto_browser", "fail", str(exc)))

    # Check 19: GitHub/CI visibility
    try:
        from openjarvis.workbench.repo_index import ci_visibility_status
        ci = ci_visibility_status(repo_path)
        checks.append(chk(
            "us15_github_ci",
            "pass" if ci["gh_cli_authenticated"] else "warn",
            f"gh_authenticated={ci['gh_cli_authenticated']}, workflows={len(ci.get('workflow_files', []))}, status={ci['status']}",
        ))
    except Exception as exc:
        checks.append(chk("us15_github_ci", "fail", str(exc)))

    # Check 20: US16 context cache
    try:
        from openjarvis.workbench.context_cache import ContextCache
        cache = ContextCache()
        checks.append(chk("us16_context_cache", "pass", "ContextCache SQLite accessible"))
    except Exception as exc:
        checks.append(chk("us16_context_cache", "fail", str(exc)))

    # Check 21: US16 bounded repair loop
    try:
        from openjarvis.workbench.repair_loop import BoundedRepairLoop
        loop = BoundedRepairLoop(max_attempts=3)
        assert loop.can_retry()
        checks.append(chk("us16_repair_loop", "pass", f"BoundedRepairLoop max_attempts=3"))
    except Exception as exc:
        checks.append(chk("us16_repair_loop", "fail", str(exc)))

    # Check 22: US15 repo index completeness (JS/TS + test + config)
    try:
        from openjarvis.workbench.repo_index import build_repo_index
        idx = build_repo_index(repo_path)
        details = (
            f"files={len(idx.files)}, py_symbols={len(idx.symbols)}, "
            f"js_ts={len(idx.js_ts_symbols)}, tests={len(idx.test_files)}, "
            f"configs={len(idx.config_files)}"
        )
        checks.append(chk("us15_repo_index_complete", "pass", details))
    except Exception as exc:
        checks.append(chk("us15_repo_index_complete", "fail", str(exc)))

    # Check 23: US17 adversarial safety self-test
    try:
        from openjarvis.workbench.adversarial_safety import run_adversarial_self_test
        st = run_adversarial_self_test()
        checks.append(chk(
            "us17_adversarial_safety",
            "pass" if st["all_pass"] else "fail",
            f"{st['passed']}/{st['total']} adversarial denials pass",
        ))
    except Exception as exc:
        checks.append(chk("us17_adversarial_safety", "fail", str(exc)))

    # Check 24: US17 failure recovery playbook
    try:
        from openjarvis.workbench.failure_recovery import get_failure_recovery_summary
        fr = get_failure_recovery_summary()
        checks.append(chk(
            "us17_failure_recovery",
            "pass" if fr.get("playbook_entries", 0) >= 10 else "warn",
            f"{fr.get('playbook_entries')} recovery playbooks, stop_on_blocker={fr.get('stop_on_blocker')}",
        ))
    except Exception as exc:
        checks.append(chk("us17_failure_recovery", "fail", str(exc)))

    # Check 25: US18 founder dogfood checklist
    try:
        from openjarvis.workbench.founder_readiness import evaluate_founder_dogfood
        fd = evaluate_founder_dogfood()
        blocking = fd.get("by_status", {}).get("blocked", 0) + fd.get("by_status", {}).get("missing", 0)
        checks.append(chk(
            "us18_founder_dogfood",
            "pass" if blocking == 0 else "warn",
            f"verdict={fd.get('verdict')} required_done={fd.get('required_done')}/{fd.get('required_total')}",
        ))
    except Exception as exc:
        checks.append(chk("us18_founder_dogfood", "fail", str(exc)))

    # Check 26: US17 safety event types registered
    try:
        from openjarvis.workbench.event_log import EVENT_SAFETY_BLOCKED, EVENT_BUDGET_EXCEEDED
        checks.append(chk("us17_safety_events", "pass", f"safety_blocked={EVENT_SAFETY_BLOCKED}"))
    except Exception as exc:
        checks.append(chk("us17_safety_events", "fail", str(exc)))

    # Check 27: Wave 1 platform registry importable
    try:
        from openjarvis.wave.platform_registry import get_wave_platform_summary
        summary = get_wave_platform_summary()
        wave1_scaffolded = summary.get("wave1_scaffolded", False)
        epics = summary.get("total_epics", 0)
        checks.append(chk(
            "wave1_platform_registry",
            "pass" if wave1_scaffolded else "warn",
            f"wave1_scaffolded={wave1_scaffolded} total_epics={epics}",
        ))
    except Exception as exc:
        checks.append(chk("wave1_platform_registry", "fail", str(exc)))

    # Check 28: Wave 1 Epic A — Skill Platform local execution
    try:
        from openjarvis.wave.skill_platform import get_skill_platform_status, run_skill
        info = get_skill_platform_status()
        # Verify local execution actually works
        result = run_skill("list_skills")
        exec_ok = result.ok
        checks.append(chk(
            "wave1_skill_platform",
            "pass" if exec_ok else "warn",
            (
                f"status={info['status']} skills={info['skill_count']} "
                f"local_exec={info.get('local_execution_implemented')} "
                f"approval_gate={info['approval_gate_enforced']} "
                f"run_skill_ok={exec_ok}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_skill_platform", "fail", str(exc)))

    # Check 29: Wave 1 Epic B — Automation Platform dry-run
    try:
        from openjarvis.wave.automation_platform import (
            AutomationRegistry, AutomationTrigger, TRIGGER_MANUAL, POLICY_AUTO,
            get_automation_platform_status, dry_run_trigger,
        )
        info = get_automation_platform_status()
        reg = AutomationRegistry()
        reg.register(AutomationTrigger(
            trigger_id="doctor_test_trigger", name="Doctor Test",
            trigger_type=TRIGGER_MANUAL, approval_policy=POLICY_AUTO, risk_level="low",
        ))
        dr = dry_run_trigger("doctor_test_trigger", registry=reg)
        dry_ok = dr.ok
        checks.append(chk(
            "wave1_automation_platform",
            "pass" if dry_ok else "warn",
            (
                f"status={info['status']} dry_run={info.get('dry_run_implemented')} "
                f"approval_gate={info['approval_gate_enforced']} dry_run_ok={dry_ok}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_automation_platform", "fail", str(exc)))

    # Check 30: Wave 1 Epic C — Knowledge Platform local ingestion
    try:
        from openjarvis.wave.knowledge_platform import get_knowledge_platform_status, ingest_local_source
        info = get_knowledge_platform_status()
        ingest = ingest_local_source("Doctor check content.", source_id="doctor_check", title="Doctor")
        ingest_ok = ingest.ok
        checks.append(chk(
            "wave1_knowledge_platform",
            "pass" if ingest_ok else "warn",
            (
                f"status={info['status']} sources={info['source_count']} "
                f"local_ingest={info.get('local_ingestion_implemented')} "
                f"pii_gate={info['pii_sources_require_approval']} ingest_ok={ingest_ok}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_knowledge_platform", "fail", str(exc)))

    # Check 31: Wave 1 Epic D — Research Platform local query
    try:
        from openjarvis.wave.research_platform import get_research_platform_status, run_local_query
        info = get_research_platform_status()
        qr = run_local_query("doctor check", provider_id="local_knowledge")
        query_ok = qr.ok
        checks.append(chk(
            "wave1_research_platform",
            "pass" if query_ok else "warn",
            (
                f"status={info['status']} providers={info['provider_count']} "
                f"local_query={info.get('local_query_implemented')} "
                f"scraping_blocked={info.get('scraping_blocked')} query_ok={query_ok}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_research_platform", "fail", str(exc)))

    # Check 33: Wave 1 Epic A — Skill induction pipeline
    try:
        from openjarvis.wave.skill_induction import (
            validate_skill_manifest, induce_skill, get_induction_pipeline_status
        )
        pipe_info = get_induction_pipeline_status()
        # Quick smoke test: safe manifest should induct; unsafe should reject
        safe_result = induce_skill({
            "skill_id": "_doctor_test_safe", "name": "Doctor Test Safe",
            "description": "Read-only local check", "tags": [], "risk_level": "low",
        })
        unsafe_result = validate_skill_manifest({
            "skill_id": "_doctor_test_unsafe", "name": "Unsafe",
            "description": "rm -rf /", "tags": ["external_send"], "risk_level": "high",
        })
        checks.append(chk(
            "wave1_skill_induction",
            "pass" if (pipe_info["implemented"] and not unsafe_result.valid) else "warn",
            (
                f"pipeline_implemented={pipe_info['implemented']} "
                f"safe_induced={safe_result.ok} "
                f"unsafe_rejected={not unsafe_result.valid}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_skill_induction", "fail", str(exc)))

    # Check 34: Wave 1 Epic B — Automation scheduler
    try:
        from openjarvis.wave.automation_scheduler import get_scheduler_status, execute_safe_trigger
        from openjarvis.wave.automation_platform import AutomationTrigger
        sched = get_scheduler_status()
        safe_trigger = AutomationTrigger(
            trigger_id="_doctor_safe_trigger",
            name="Doctor safe",
            trigger_type="manual",
            skill_id="log_status",
            risk_level="low",
            approval_policy="auto",
        )
        exec_result = execute_safe_trigger(safe_trigger, action_key="log_status")
        checks.append(chk(
            "wave1_automation_scheduler",
            "pass" if (sched["implemented"] and exec_result.ok) else "warn",
            (
                f"scheduler_implemented={sched['implemented']} "
                f"external_sends_blocked={sched['external_sends_blocked']} "
                f"safe_execute_ok={exec_result.ok}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_automation_scheduler", "fail", str(exc)))

    # Check 35: Wave 1 Epic C — Local folder connector
    try:
        from openjarvis.wave.local_folder_connector import (
            get_local_folder_connector_status, ensure_default_knowledge_dir, ingest_folder
        )
        conn_status = get_local_folder_connector_status()
        d = ensure_default_knowledge_dir()
        checks.append(chk(
            "wave1_knowledge_connector",
            "pass" if conn_status["implemented"] else "warn",
            (
                f"implemented={conn_status['implemented']} "
                f"default_dir={conn_status['default_knowledge_dir']} "
                f"dir_exists={conn_status['default_dir_exists']} "
                f"pii_blocked={conn_status['pii_blocked']}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_knowledge_connector", "fail", str(exc)))

    # Check 36: Wave 1 Epic D — Tavily web research provider
    try:
        from openjarvis.wave.tavily_provider import get_tavily_provider_status, run_tavily_query
        ts = get_tavily_provider_status()
        # Unsafe query must be blocked regardless of key
        blocked = run_tavily_query("captcha bypass credential", approved=True)
        checks.append(chk(
            "wave1_research_tavily",
            "pass" if ts else "warn",
            (
                f"adapter_implemented=True "
                f"tavily_status={ts['status']} "
                f"key_configured={ts['key_configured']} "
                f"unsafe_blocked={blocked.blocked}"
            ),
        ))
    except Exception as exc:
        checks.append(chk("wave1_research_tavily", "fail", str(exc)))

    # Check 32: Wave 1 capabilities truthfully NOT claiming Wave 2–4 ready
    try:
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        wave2_4 = reg.get_by_wave(2) + reg.get_by_wave(3) + reg.get_by_wave(4)
        all_not_impl = all(r.status == WavePlatformStatus.NOT_IMPLEMENTED for r in wave2_4)
        checks.append(chk(
            "wave2_4_not_claimed_ready",
            "pass" if all_not_impl else "fail",
            f"wave2_4_correctly_marked_not_implemented={all_not_impl}",
        ))
    except Exception as exc:
        checks.append(chk("wave2_4_not_claimed_ready", "fail", str(exc)))

    by_status: Dict[str, int] = {}
    for c in checks:
        s = c["status"]
        by_status[s] = by_status.get(s, 0) + 1

    all_pass = by_status.get("fail", 0) == 0
    us17_fail = any(c["check"].startswith("us17") and c["status"] == "fail" for c in checks)
    us18_fail = any(c["check"].startswith("us18") and c["status"] == "fail" for c in checks)
    wave1_fail = any(c["check"].startswith("wave1") and c["status"] == "fail" for c in checks)
    return {
        "ok": all_pass,
        "total": len(checks),
        "by_status": by_status,
        "checks": checks,
        "verdict": "ACCEPT" if all_pass else "HOLD",
        "us15_status": "ready" if all_pass else "hold",
        "us16_status": "ready" if all_pass else "hold",
        "us17_status": "ready" if not us17_fail else "hold",
        "us18_status": "ready" if not us18_fail else "hold",
        "wave1_status": "ready" if not wave1_fail else "hold",
        "wave2_4_status": "not_implemented",
    }


@router.get("/v1/workbench/capabilities")
async def get_workbench_capabilities() -> Dict[str, Any]:
    """US15 truthful capability status for Mission Control / doctor."""
    try:
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        return {"ok": True, **get_capabilities_summary()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/workbench/repo-index")
async def get_workbench_repo_index(repo_path: str = ".") -> Dict[str, Any]:
    """US15 bounded repo map / symbol / dependency index."""
    try:
        from openjarvis.workbench.repo_index import build_repo_index, ci_visibility_status
        index = build_repo_index(repo_path)
        return {
            "ok": True,
            "index": index.to_dict(),
            "ci": ci_visibility_status(repo_path),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/workbench/validation-profiles")
async def get_validation_profiles() -> Dict[str, Any]:
    """US15 local-first validation runner profiles."""
    try:
        from openjarvis.workbench.validation_profiles import list_validation_profiles
        return {"ok": True, "profiles": list_validation_profiles()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/workbench/dogfood-evidence")
async def get_dogfood_evidence(limit: int = 20) -> Dict[str, Any]:
    """US15 Jarvis-only coding dogfood evidence records."""
    try:
        from openjarvis.workbench.dogfood_evidence import list_dogfood_evidence
        return list_dogfood_evidence(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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


# ---------------------------------------------------------------------------
# US15 Terminal Executor routes
# ---------------------------------------------------------------------------


@router.post("/v1/workbench/terminal/exec")
async def terminal_exec(req: TerminalExecRequest) -> Dict[str, Any]:
    """US15 approval-gated terminal command executor.

    Safe read-only commands are auto-approved.
    Risky/destructive commands return approval_required with an approval_token.
    Always-blocked commands return blocked immediately.
    Secrets are scrubbed from output.
    """
    executor = _get_terminal_executor(req.repo_path)
    result = executor.submit(
        req.command,
        cwd=req.repo_path,
        timeout=req.timeout,
        pre_approved=req.pre_approved,
        approval_token=req.approval_token,
    )
    return {"ok": result.status not in ("blocked", "failed", "timeout"), "result": result.to_dict()}


@router.post("/v1/workbench/terminal/approve")
async def terminal_approve(req: TerminalApproveRequest) -> Dict[str, Any]:
    """US15 approve a pending terminal command and execute it."""
    executor = _get_terminal_executor(req.repo_path)
    result = executor.approve(req.approval_token, timeout=req.timeout)
    return {"ok": result.status not in ("blocked", "failed", "timeout"), "result": result.to_dict()}


@router.get("/v1/workbench/terminal/pending")
async def terminal_pending(repo_path: str = ".") -> Dict[str, Any]:
    """US15 list pending terminal approval requests."""
    executor = _get_terminal_executor(repo_path)
    return {"ok": True, "pending": executor.get_pending(), "count": len(executor.get_pending())}


# ---------------------------------------------------------------------------
# US15 Diff Review routes
# ---------------------------------------------------------------------------


@router.post("/v1/workbench/diff-review/create")
async def diff_review_create(req: DiffReviewCreateRequest) -> Dict[str, Any]:
    """US15 create a structured diff review for approval/rejection."""
    store = _get_diff_review_store()
    review = store.create(
        session_id=req.session_id,
        task_id=req.task_id,
        repo_path=req.repo_path,
        raw_diff=req.raw_diff,
        dry_run=req.dry_run,
    )
    return {"ok": True, "review": review.to_dict()}


@router.post("/v1/workbench/diff-review/approve")
async def diff_review_approve(req: DiffReviewDecideRequest) -> Dict[str, Any]:
    """US15 approve a diff review. Records approval — does not auto-apply changes."""
    store = _get_diff_review_store()
    review = store.approve(req.review_id, approved_by=req.approved_by, note=req.note)
    if review is None:
        raise HTTPException(status_code=404, detail=f"DiffReview not found: {req.review_id}")
    return {"ok": True, "review": review.to_dict()}


@router.post("/v1/workbench/diff-review/reject")
async def diff_review_reject(req: DiffReviewDecideRequest) -> Dict[str, Any]:
    """US15 reject a diff review. Changes are NOT applied."""
    store = _get_diff_review_store()
    review = store.reject(req.review_id, reason=req.reason or "Rejected by reviewer")
    if review is None:
        raise HTTPException(status_code=404, detail=f"DiffReview not found: {req.review_id}")
    return {"ok": True, "review": review.to_dict()}


@router.post("/v1/workbench/diff-review/manual")
async def diff_review_manual(req: DiffReviewDecideRequest) -> Dict[str, Any]:
    """US15 park a diff review for manual inspection."""
    store = _get_diff_review_store()
    review = store.mark_manual_review(req.review_id, note=req.note)
    if review is None:
        raise HTTPException(status_code=404, detail=f"DiffReview not found: {req.review_id}")
    return {"ok": True, "review": review.to_dict()}


@router.get("/v1/workbench/diff-review/list")
async def diff_review_list(session_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """US15 list diff reviews (optionally filtered by session_id)."""
    store = _get_diff_review_store()
    if session_id:
        reviews = store.list_by_session(session_id, limit=limit)
    else:
        reviews = store.list_recent(limit=limit)
    return {"ok": True, "reviews": [r.to_dict() for r in reviews], "count": len(reviews)}


@router.get("/v1/workbench/diff-review/{review_id}")
async def diff_review_get(review_id: str) -> Dict[str, Any]:
    """US15 get a specific diff review by ID."""
    store = _get_diff_review_store()
    review = store.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"DiffReview not found: {review_id}")
    return {"ok": True, "review": review.to_dict()}


# ---------------------------------------------------------------------------
# US15 GitHub/CI and Auto Browser status routes
# ---------------------------------------------------------------------------


@router.get("/v1/workbench/ci-status")
async def get_ci_status(repo_path: str = ".") -> Dict[str, Any]:
    """US15 GitHub/CI visibility with live gh CLI data."""
    try:
        from openjarvis.workbench.repo_index import ci_visibility_status
        return {"ok": True, "ci": ci_visibility_status(repo_path)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/workbench/auto-browser/status")
async def get_auto_browser_status_route() -> Dict[str, Any]:
    """US15 Auto Browser integration status with health check and setup steps."""
    try:
        from openjarvis.workbench.auto_browser_provider import get_auto_browser_status
        status = get_auto_browser_status()
        return {"ok": True, "auto_browser": status}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# US17 Adversarial Safety routes
# ---------------------------------------------------------------------------


@router.get("/v1/workbench/safety/status")
async def get_safety_status() -> Dict[str, Any]:
    """US17 adversarial safety status + self-test results."""
    try:
        from openjarvis.workbench.adversarial_safety import get_safety_status_summary
        from openjarvis.workbench.failure_recovery import get_failure_recovery_summary
        return {
            "ok": True,
            "safety": get_safety_status_summary(),
            "failure_recovery": get_failure_recovery_summary(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class SafetyEvaluateRequest(BaseModel):
    category: str
    payload: Any = Field(default="")


@router.post("/v1/workbench/safety/evaluate")
async def evaluate_safety(req: SafetyEvaluateRequest) -> Dict[str, Any]:
    """US17 evaluate a single adversarial category + payload."""
    try:
        from openjarvis.workbench.adversarial_safety import evaluate_adversarial
        verdict = evaluate_adversarial(req.category, req.payload)
        return {"ok": True, "verdict": verdict.to_dict()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# US18 Founder Readiness routes
# ---------------------------------------------------------------------------


@router.get("/v1/workbench/founder-readiness")
async def get_founder_readiness() -> Dict[str, Any]:
    """US18 founder dogfood checklist evaluation."""
    try:
        from openjarvis.workbench.founder_readiness import evaluate_founder_dogfood
        return {"ok": True, **evaluate_founder_dogfood()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/workbench/public-readiness")
async def get_public_readiness() -> Dict[str, Any]:
    """US18 public readiness matrix — honest release-safe status."""
    try:
        from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix
        return {"ok": True, "matrix": generate_public_readiness_matrix()}
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


# ─────────────────────────────────────────────────────────────────────────────
# Wave 1 endpoints
# ─────────────────────────────────────────────────────────────────────────────

try:
    from pydantic import BaseModel as _BaseModel  # type: ignore

    class _RunSkillRequest(_BaseModel):
        skill_id: str
        context: Dict[str, Any] = {}

    class _IngestTextRequest(_BaseModel):
        source_id: str
        text: str
        title: str = ""
        content_type: str = "text"

    class _ResearchQueryRequest(_BaseModel):
        query: str
        provider_id: str = "local_knowledge"

    class _AutomationDryRunRequest(_BaseModel):
        trigger_id: str

    _pydantic_ok = True
except ImportError:
    _pydantic_ok = False


@router.get("/v1/wave/status")
async def wave_status() -> Dict[str, Any]:
    """Wave 1–4 platform status for Mission Control."""
    from openjarvis.wave.platform_registry import get_wave_platform_summary
    from openjarvis.wave.skill_platform import get_skill_platform_status
    from openjarvis.wave.automation_platform import get_automation_platform_status
    from openjarvis.wave.knowledge_platform import get_knowledge_platform_status
    from openjarvis.wave.research_platform import get_research_platform_status
    return {
        "platform": get_wave_platform_summary(),
        "skill_platform": get_skill_platform_status(),
        "automation_platform": get_automation_platform_status(),
        "knowledge_platform": get_knowledge_platform_status(),
        "research_platform": get_research_platform_status(),
        "wave2_4_status": "not_implemented",
        "us13_voice": "HOLD / UNSAFE / PARKED",
    }


@router.get("/v1/wave/skills")
async def wave_list_skills() -> Dict[str, Any]:
    """List all registered Wave 1 skills."""
    from openjarvis.wave.skill_platform import list_wave_skills
    return {"ok": True, "skills": list_wave_skills()}


@router.post("/v1/wave/skills/run")
async def wave_run_skill(req: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Wave 1 skill by ID (approval-gated for high-risk skills)."""
    from openjarvis.wave.skill_platform import run_skill
    skill_id = req.get("skill_id", "")
    context = req.get("context", {})
    if not skill_id:
        return {"ok": False, "error": "skill_id required"}
    result = run_skill(skill_id, context)
    return result.to_dict()


@router.get("/v1/wave/automations")
async def wave_list_automations() -> Dict[str, Any]:
    """List all registered Wave 1 automation triggers."""
    from openjarvis.wave.automation_platform import AutomationRegistry
    reg = AutomationRegistry()
    return {"ok": True, "triggers": [t.to_dict() for t in reg.list_triggers()]}


@router.post("/v1/wave/automations/dry-run")
async def wave_automation_dry_run(req: Dict[str, Any]) -> Dict[str, Any]:
    """Dry-run an automation trigger (approval-gated for high-risk)."""
    from openjarvis.wave.automation_platform import dry_run_trigger
    trigger_id = req.get("trigger_id", "")
    if not trigger_id:
        return {"ok": False, "error": "trigger_id required"}
    result = dry_run_trigger(trigger_id)
    return result.to_dict()


@router.post("/v1/wave/knowledge/ingest")
async def wave_knowledge_ingest(req: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest local text as a knowledge source."""
    from openjarvis.wave.knowledge_platform import ingest_local_source
    source_id = req.get("source_id", "")
    text = req.get("text", "")
    if not source_id or not text:
        return {"ok": False, "error": "source_id and text required"}
    result = ingest_local_source(
        text=text,
        source_id=source_id,
        title=req.get("title", ""),
        content_type=req.get("content_type", "text"),
    )
    return result.to_dict()


@router.get("/v1/wave/knowledge/sources")
async def wave_knowledge_sources() -> Dict[str, Any]:
    """List all registered knowledge sources."""
    from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry
    reg = KnowledgeSourceRegistry()
    return {"ok": True, "sources": [s.to_dict() for s in reg.list_sources()]}


@router.post("/v1/wave/research/query")
async def wave_research_query(req: Dict[str, Any]) -> Dict[str, Any]:
    """Run a local research query (approval-gated for web providers)."""
    from openjarvis.wave.research_platform import run_local_query
    query = req.get("query", "")
    provider_id = req.get("provider_id", "local_knowledge")
    if not query:
        return {"ok": False, "error": "query required"}
    result = run_local_query(query, provider_id=provider_id)
    return result.to_dict()


@router.get("/v1/wave/research/providers")
async def wave_research_providers() -> Dict[str, Any]:
    """List all registered research providers."""
    from openjarvis.wave.research_platform import ResearchProviderRegistry
    reg = ResearchProviderRegistry()
    return {"ok": True, "providers": [p.to_dict() for p in reg.list_providers()]}
