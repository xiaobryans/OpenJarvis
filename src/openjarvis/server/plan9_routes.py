"""Plan 9 — Cross-Device Parity API Routes.

Routes wired in this file:

  GET  /v1/capabilities/status
       Returns Plan9CapabilityMatrix.to_list() — full cross-device capability
       matrix with classification, routing, retrieval policy, approval level,
       audit requirement, and parked/unsafe/missing status for every discovered
       manager, worker, role, and operator domain.

  GET  /v1/parity/status
       Summarizes cloud/mobile vs MacBook/local parity across all managers.
       Shows each manager's mobile_status and mac_status from the matrix.

  GET  /v1/capabilities/matrix-summary
       Single-call summary by status type (CLOUD_LIVE count, PARKED count, etc.)

  GET  /v1/coding/workspace
       Returns cloud coding workspace status and available operations.

  POST /v1/coding/files/read
       Read a file from the indexed repo (cloud-safe; allowlisted paths only).

  POST /v1/coding/diff/stage
       Stage a diff hunk. Dry-run only — does not write without approval_token.

  POST /v1/testing/run
       Run targeted tests. Captures and returns output. No deploy or side effects.

  POST /v1/testing/lint
       Run lint/type check. Returns pass/fail + issues.

  POST /v1/git/commit
       Single-executor commit workflow. Requires approval_token. Runs secret scan
       first. Does NOT commit unless dry_run=False AND approval_token is valid.
       In dry_run mode (default): returns what would be committed + secret scan result.

  POST /v1/deploy/plan
       Dry-run deploy plan only. Hard-gated. Never executes a real deploy here.
       Returns deploy plan + approval_required=True always.

  GET  /v1/mac-worker/queue
       Returns current Mac worker queue (all tasks with status).

  POST /v1/mac-worker/queue
       Submit a new Mac-only task to the queue.

  GET  /v1/mac-worker/status
       Returns Mac worker queue status summary.

  GET  /v1/model-routing/matrix
       Returns the full role-based model routing matrix (all 52 roles).

  GET  /v1/model-routing/explain
       Explain model tier for a given role/task/risk context.

  GET  /v1/orchestration/policy
       Returns orchestration policies: retrieval, parallel DAG, elastic pools,
       batch integration, and integration review.

Safety:
  - /v1/git/commit NEVER commits without valid approval_token (dry_run=False check).
  - /v1/deploy/plan NEVER deploys — dry-run only, always returns approval_required=True.
  - No secrets are returned in any response.
  - Mac worker queue tasks never contain credential values.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Body, Depends, HTTPException, Query
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for plan9_routes")

_p9_bearer = HTTPBearer(auto_error=False)

from openjarvis.plan9.capability_matrix import (
    CapabilityStatus,
    get_plan9_capability_matrix,
)
from openjarvis.plan9.model_routing import (
    ModelTier,
    get_role_routing_matrix,
    DEFAULT_ROUTING,
)
from openjarvis.plan9.pa_brain_layer import (
    get_pa_config,
    get_brain_layer_config,
    get_org_hierarchy,
)
from openjarvis.plan9.orchestration_policy import (
    RETRIEVAL_WORKER_POLICIES,
    ELASTIC_POOL_POLICIES,
    DEFAULT_ELASTIC_POOL,
    ParallelDAGPolicy,
    BatchIntegrationPolicy,
    IntegrationReviewPolicy,
)
from openjarvis.plan9.orchestration_executor import (
    batch_run_to_dict,
    dag_run_to_dict,
    get_batch_run,
    get_dag_run,
    get_last_batch_run,
    get_last_dag_run,
    run_batch_integration,
    run_controlled_dag,
)
from openjarvis.plan9.mac_worker_queue import (
    MacTaskType,
    MacWorkerTask,
    MacWorkerQueue,
    get_mac_worker_queue,
    MAC_ONLY_TASK_TYPES,
    CLOUD_NATIVE_TASK_TYPES,
)
from openjarvis.plan9.rules import PLAN9_INTERNAL_RULES
from openjarvis.plan9.skills_manifest import PLAN9_SKILLS_MANIFEST
from openjarvis.plan9.commands_manifest import PLAN9_COMMANDS_MANIFEST
from openjarvis.plan9.execution_chain import repo_root
from openjarvis.plan9.future_inheritance import PLAN9_DEFAULT_INHERITANCE

logger = logging.getLogger(__name__)

router = APIRouter(tags=["plan9"])

# Secret patterns used for scanning (patterns only — no values stored here)
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xoxp-[0-9]+-[0-9]+-"),
    re.compile(r"xoxb-[0-9]+-"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"gho_[A-Za-z0-9]{36,}"),
    re.compile(r"Bearer eyJ[A-Za-z0-9+/=]{20,}"),
]


def _secret_scan(text: str) -> Dict[str, Any]:
    """Scan text for secret patterns. Returns locations only — never values."""
    found = []
    for pattern in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            found.append({
                "pattern": pattern.pattern,
                "start": m.start(),
                "end": m.end(),
            })
    return {
        "status": "FOUND_SECRETS" if found else "CLEAN",
        "count": len(found),
        "locations": found,
        "abort_required": len(found) > 0,
    }


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class FileReadRequest(BaseModel):
    file_path: str = Field(..., description="Repo-relative file path (must be in allowlist)")
    start_line: Optional[int] = Field(None, ge=1, description="Start line (1-indexed)")
    end_line: Optional[int] = Field(None, ge=1, description="End line (inclusive)")


class DiffStageRequest(BaseModel):
    file_path: str = Field(..., description="Target file path")
    diff_hunk: str = Field(..., description="Unified diff hunk to stage")
    dry_run: bool = Field(True, description="If True (default), only validate — do not write")
    approval_token: Optional[str] = Field(None, description="Required for dry_run=False")


class TestRunRequest(BaseModel):
    test_paths: List[str] = Field(default_factory=list, description="pytest paths to run")
    extra_args: List[str] = Field(default_factory=list, description="Extra pytest args (no -k/--collect by default)")
    capture_output: bool = Field(True, description="Capture and return test output")
    timeout_seconds: int = Field(60, ge=1, le=300, description="Test timeout in seconds")


class LintRunRequest(BaseModel):
    file_paths: List[str] = Field(default_factory=list, description="Files to lint (empty = changed files)")
    linter: str = Field("ruff", description="Linter to use: ruff | mypy | both")


class GitCommitRequest(BaseModel):
    commit_message: str = Field(..., min_length=5, description="Commit message")
    files: List[str] = Field(default_factory=list, description="Files to stage (empty = git add -A)")
    dry_run: bool = Field(True, description="If True (default): diff+secret scan only, no commit")
    approval_token: Optional[str] = Field(None, description="Required for dry_run=False")
    branch: Optional[str] = Field(None, description="Target branch (defaults to current)")


class DeployPlanRequest(BaseModel):
    deploy_target: str = Field(..., description="Deploy target (e.g. ecs-fargate, vercel)")
    image_tag: Optional[str] = Field(None, description="Docker image tag to deploy")
    notes: Optional[str] = Field(None, description="Deploy notes")


class MacWorkerSubmitRequest(BaseModel):
    task_type: str = Field(..., description="Mac task type: app_reinstall | mac_app_control | unsynced_file_read | keychain_credential | mac_hardware")
    display_name: str = Field(..., description="Human-readable task name")
    description: str = Field("", description="Task description")
    submitted_from: str = Field("mobile", description="Surface submitting the task")


class ModelRouteExplainRequest(BaseModel):
    role: str = Field(..., description="Role ID (e.g. coding_manager)")
    task: str = Field("", description="Task description")
    risk: str = Field("medium", description="Risk level: low | medium | high | critical")
    complexity: str = Field("moderate", description="Complexity: simple | moderate | complex")
    failures: int = Field(0, ge=0, description="Prior failure count for this approach")


# ---------------------------------------------------------------------------
# Section 7: Capability Matrix Routes
# ---------------------------------------------------------------------------

@router.get("/v1/capabilities/status")
async def get_capabilities_status(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> Dict[str, Any]:
    """Return full Plan 9 capability matrix.

    Covers every discovered manager, worker, agent, team, and operator domain.
    Includes classification, routing, retrieval policy, approval level,
    audit requirement, and parked/unsafe/missing status.
    """
    matrix = get_plan9_capability_matrix()
    entries = matrix.to_list()

    if domain:
        entries = [e for e in entries if e.get("domain") == domain]
    if status:
        entries = [e for e in entries if e.get("status") == status]

    routing_matrix = get_role_routing_matrix()

    # Enrich entries with routing and retrieval info
    enriched = []
    for entry in entries:
        dom = entry.get("domain", "")
        routing = routing_matrix.get(dom)
        retrieval = RETRIEVAL_WORKER_POLICIES.get(dom)
        enriched.append({
            **entry,
            "routing": {
                "cheap_model": routing.cheap_model,
                "balanced_model": routing.balanced_model,
                "best_model": routing.best_model,
                "default_tier": routing.default_tier.value,
                "escalation_rule": routing.escalation_rule,
            } if routing.role_id != "__default__" else {"inherited": "DEFAULT_ROUTING"},
            "retrieval_policy": {
                "retrieval_needed": retrieval.retrieval_needed,
                "retrieval_worker": retrieval.retrieval_worker_id,
                "cheap_model_required": retrieval.cheap_model_required,
                "before_reasoning": retrieval.before_reasoning,
            } if retrieval else {"inherited": "DEFAULT_RETRIEVAL_POLICY"},
            "audit_required": True,
            "approval_level": entry.get("approval_gate") or "auto",
        })

    return {
        "total": len(enriched),
        "filtered_by": {"domain": domain, "status": status},
        "capabilities": enriched,
    }


@router.get("/v1/capabilities/matrix-summary")
async def get_capabilities_matrix_summary() -> Dict[str, Any]:
    """Return Plan 9 capability matrix counts by status."""
    matrix = get_plan9_capability_matrix()
    summary = matrix.summary()
    parked = [e.to_dict() for e in matrix.parked()]
    gaps = [e.to_dict() for e in matrix.gaps()]

    return {
        "summary": summary,
        "total": len(matrix.entries),
        "parked": parked,
        "gaps": gaps,
        "live_count": sum(
            v for k, v in summary.items()
            if k in ("CLOUD_LIVE", "LOCAL_LIVE", "CROSS_DEVICE_LIVE")
        ),
    }


@router.get("/v1/parity/status")
async def get_parity_status() -> Dict[str, Any]:
    """Summarize cross-device parity: cloud/mobile vs MacBook/local per manager."""
    matrix = get_plan9_capability_matrix()

    mobile_live = [
        e.to_dict() for e in matrix.entries
        if e.status in (CapabilityStatus.CLOUD_LIVE, CapabilityStatus.CROSS_DEVICE_LIVE)
    ]
    mac_live = [
        e.to_dict() for e in matrix.entries
        if e.status in (CapabilityStatus.LOCAL_LIVE, CapabilityStatus.CROSS_DEVICE_LIVE)
    ]
    mac_only = [
        e.to_dict() for e in matrix.entries
        if e.status == CapabilityStatus.QUEUED_MAC_ONLY
    ]
    approval_required = [
        e.to_dict() for e in matrix.entries
        if e.status == CapabilityStatus.APPROVAL_REQUIRED
    ]
    parked = [e.to_dict() for e in matrix.parked()]
    gaps = [e.to_dict() for e in matrix.gaps()]

    # PA + brain layer summary
    pa = get_pa_config()
    brain = get_brain_layer_config()

    return {
        "parity_definition": (
            "Whatever Bryan can do on MacBook, he must be able to do from mobile/cloud. "
            "Whatever Bryan can do from mobile/cloud, he must see/control from MacBook."
        ),
        "accepted_exception": "Rebuilding /Applications/OpenJarvis.app is MacBook-only (QUEUED_MAC_ONLY).",
        "mobile_cloud_live": len(mobile_live),
        "mac_local_live": len(mac_live),
        "mac_only_queued": len(mac_only),
        "approval_required": len(approval_required),
        "parked": parked,
        "gaps": gaps,
        "pa_layer": pa.to_dict(),
        "brain_layer": brain.to_dict(),
        "summary": matrix.summary(),
    }


# ---------------------------------------------------------------------------
# Section 5: Model Routing Routes
# ---------------------------------------------------------------------------

@router.get("/v1/model-routing/matrix")
async def get_model_routing_matrix() -> Dict[str, Any]:
    """Return full role-based model routing matrix for all 52 roles."""
    matrix = get_role_routing_matrix()
    errors = matrix.validate()
    return {
        "role_count": len(matrix.all_role_ids()),
        "validation_errors": errors,
        "roles": matrix.to_list(),
        "default_routing": DEFAULT_ROUTING.to_dict(),
    }


@router.post("/v1/model-routing/explain")
async def explain_model_routing(req: ModelRouteExplainRequest) -> Dict[str, Any]:
    """Explain model tier recommendation for a role/task/risk context."""
    matrix = get_role_routing_matrix()
    entry = matrix.get(req.role)
    tier = entry.tier_for_task(risk=req.risk, complexity=req.complexity, failures=req.failures)
    model_map = {
        ModelTier.CHEAP: entry.cheap_model,
        ModelTier.BALANCED: entry.balanced_model,
        ModelTier.BEST: entry.best_model,
        ModelTier.STOP: "STOP — break approach, do not escalate",
    }
    return {
        "role": req.role,
        "task": req.task,
        "risk": req.risk,
        "complexity": req.complexity,
        "failures": req.failures,
        "recommended_tier": tier.value,
        "recommended_model": model_map.get(tier, "unknown"),
        "escalation_rule": entry.escalation_rule,
        "fallback_rule": entry.fallback_rule,
        "cost_justification": entry.cost_justification,
        "is_default_inherited": entry.role_id == "__default__",
    }


# ---------------------------------------------------------------------------
# Section 8: Orchestration Policy Routes
# ---------------------------------------------------------------------------

@router.get("/v1/orchestration/policy")
async def get_orchestration_policy_summary() -> Dict[str, Any]:
    """Return all Plan 9 orchestration policies."""
    dag = ParallelDAGPolicy()
    batch = BatchIntegrationPolicy()
    review = IntegrationReviewPolicy()

    # Build parallel safety table
    safety_table = [
        {
            "action_type": rule.action_type,
            "safety": rule.safety.value,
            "reason": rule.reason,
            "lock_required": rule.lock_required,
            "approval_required": rule.approval_required,
        }
        for rule in dag.safety_rules
    ]

    # Build elastic pool summary
    pool_summary = []
    for role_id, policy in ELASTIC_POOL_POLICIES.items():
        pool_summary.append({
            "role_id": role_id,
            "scaling_allowed": policy.scaling_allowed,
            "max_workers": policy.max_workers,
            "single_executor_only": policy.single_executor_only,
            "lock_required_for_writes": policy.lock_required_for_writes,
        })

    # Build retrieval policy summary
    retrieval_summary = {
        team_id: {
            "retrieval_needed": p.retrieval_needed,
            "retrieval_worker": p.retrieval_worker_id,
            "cheap_model_required": p.cheap_model_required,
            "before_reasoning": p.before_reasoning,
        }
        for team_id, p in RETRIEVAL_WORKER_POLICIES.items()
    }

    return {
        "retrieval_worker_policies": retrieval_summary,
        "parallel_dag": {
            "policy_id": dag.policy_id,
            "safety_rules": safety_table,
        },
        "elastic_pools": {
            "default": {
                "scaling_allowed": DEFAULT_ELASTIC_POOL.scaling_allowed,
                "max_workers": DEFAULT_ELASTIC_POOL.max_workers,
                "lock_required_for_writes": DEFAULT_ELASTIC_POOL.lock_required_for_writes,
            },
            "roles": pool_summary,
        },
        "batch_integration": {
            "policy_id": batch.policy_id,
            "workers_propose_in_parallel": batch.workers_propose_in_parallel,
            "integration_is_sequential": batch.integration_is_sequential,
            "review_is_independent": batch.review_is_independent,
            "max_concurrent_master_writes": batch.max_concurrent_master_writes,
            "no_patch_may_be_dropped_silently": batch.no_patch_may_be_dropped_silently,
            "all_items_must_appear_in_final": batch.all_items_must_appear_in_final,
            "integrator_role": batch.integrator_role,
            "reviewer_role": batch.reviewer_role,
        },
        "integration_review": {
            "policy_id": review.policy_id,
            "reviewer_must_differ_from_integrator": review.reviewer_must_differ_from_integrator,
            "must_verify_all_items": review.must_verify_all_items,
            "must_verify_no_dropped_patches": review.must_verify_no_dropped_patches,
            "must_verify_no_secret": review.must_verify_no_secret,
            "must_verify_tests_pass": review.must_verify_tests_pass,
        },
    }


@router.post("/v1/orchestration/dag/run")
async def orchestration_dag_run(req: OrchestrationDagRunRequest) -> Dict[str, Any]:
    """Execute a controlled Plan 9 DAG with retrieval, parallel groups, and live task states."""
    record = run_controlled_dag(task_description=req.task_description, scope=req.scope)
    return dag_run_to_dict(record)


@router.get("/v1/orchestration/dag/status")
async def orchestration_dag_status(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Return DAG run status by id or the most recent run."""
    record = get_dag_run(run_id) if run_id else get_last_dag_run()
    if record is None:
        return {"status": "no_runs", "run_id": run_id}
    return dag_run_to_dict(record)


@router.post("/v1/orchestration/batch/run")
async def orchestration_batch_run(req: OrchestrationBatchRunRequest) -> Dict[str, Any]:
    """Run same-file batch integration on allowlisted fixture with integrator + reviewer."""
    record = run_batch_integration(
        target_file=req.target_file,
        worker_a_patch=req.worker_a_patch,
        worker_b_patch=req.worker_b_patch,
        run_tests=req.run_tests,
    )
    return batch_run_to_dict(record)


@router.get("/v1/orchestration/batch/status")
async def orchestration_batch_status(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Return batch integration run status by id or the most recent run."""
    record = get_batch_run(run_id) if run_id else get_last_batch_run()
    if record is None:
        return {"status": "no_runs", "run_id": run_id}
    return batch_run_to_dict(record)


# ---------------------------------------------------------------------------
# Section 12: Cloud Coding Workspace
# ---------------------------------------------------------------------------

@router.get("/v1/coding/workspace")
async def get_coding_workspace_status() -> Dict[str, Any]:
    """Return cloud coding workspace status and available operations."""
    from openjarvis.plan9.workspace_root import workspace_index_summary, workspace_root

    idx = workspace_index_summary()
    root = workspace_root()
    return {
        "status": "AVAILABLE",
        "description": "Cloud coding workspace — inspect/search/read/edit/diff without MacBook",
        "workspace_root": str(root),
        "indexed_file_count": idx["indexed_file_count"],
        "prefix_counts": idx["prefix_counts"],
        "pyproject_present": idx["pyproject_present"],
        "operations": [
            {"op": "read_file", "route": "POST /v1/coding/files/read", "status": "WIRED"},
            {"op": "stage_diff", "route": "POST /v1/coding/diff/stage", "status": "WIRED"},
            {"op": "search_code", "route": "POST /v1/coding/search", "status": "WIRED"},
            {"op": "create_branch", "route": "POST /v1/coding/create-branch", "status": "WIRED"},
            {"op": "push", "route": "POST /v1/git/push", "status": "WIRED"},
            {"op": "file_index", "route": "GET /v1/files/index", "status": "WIRED"},
        ],
        "requires_allowlist": True,
        "cloud_safe": True,
        "mac_required": False,
    }


@router.post("/v1/coding/files/read")
async def read_coding_file(req: FileReadRequest) -> Dict[str, Any]:
    """Read a file from the repo (cloud-safe; allowlisted paths only).

    Uses a conservative allowlist to prevent blind Mac exposure.
    Reads from OPENJARVIS_ROOT workspace (set to /app in cloud container).
    """
    from openjarvis.plan9.workspace_root import workspace_prefix_allowed, workspace_root

    raw = req.file_path
    if not workspace_prefix_allowed(raw):
        if ".." in raw or raw.startswith("/"):
            raise HTTPException(status_code=400, detail="Path traversal not allowed")
        for blocked in (".env", ".git/", "id_rsa", "id_ed25519", ".ssh/", "secrets/"):
            if blocked in raw:
                raise HTTPException(status_code=403, detail=f"Path {blocked!r} is not allowed")
        raise HTTPException(
            status_code=403,
            detail=f"Path {raw!r} is not in the cloud-safe allowlist.",
        )

    root = workspace_root()
    full_path = root / raw

    if not full_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {raw} (workspace_root={root})",
        )
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {raw}")

    content = full_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines(keepends=True)

    start = (req.start_line - 1) if req.start_line else 0
    end = req.end_line if req.end_line else len(lines)
    snippet = "".join(lines[start:end])

    # Quick secret scan on the snippet
    scan = _secret_scan(snippet)

    return {
        "file_path": raw,
        "total_lines": len(lines),
        "returned_lines": f"{start + 1}-{min(end, len(lines))}",
        "content": snippet,
        "secret_scan": {"status": scan["status"], "abort_required": scan["abort_required"]},
    }


@router.post("/v1/coding/diff/stage")
async def stage_diff(req: DiffStageRequest) -> Dict[str, Any]:
    """Stage a diff hunk. Dry-run by default — does not write without approval.

    dry_run=True (default): validates diff and returns what would be staged.
    dry_run=False: requires approval_token. Not yet wired to real git staging.
    """
    if not req.dry_run and not req.approval_token:
        raise HTTPException(
            status_code=403,
            detail="approval_token required for dry_run=False. "
                   "Submit approval request to Bryan first.",
        )

    scan = _secret_scan(req.diff_hunk)
    if scan["abort_required"]:
        raise HTTPException(
            status_code=400,
            detail="Secret scan FAILED: potential secrets detected in diff. Aborting.",
        )

    if req.dry_run:
        return {
            "mode": "DRY_RUN",
            "file_path": req.file_path,
            "diff_lines": len(req.diff_hunk.splitlines()),
            "secret_scan": "CLEAN",
            "would_stage": True,
            "approval_required_for_write": True,
            "message": "Diff validated. Submit approval_token to stage for real.",
        }

    # Non-dry-run path: approval_token present — apply hunk then stage the file.
    # Uses git apply --cached to stage the diff hunk in-index without touching the working tree.
    import subprocess
    import tempfile
    from pathlib import Path as _StagePath

    root = repo_root()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(req.diff_hunk)
            patch_path = tmp.name

        apply_result = subprocess.run(
            ["git", "apply", "--cached", "--check", patch_path],
            capture_output=True, text=True, timeout=15, cwd=str(root),
        )
        if apply_result.returncode != 0:
            return {
                "mode": "STAGED_FAILED",
                "file_path": req.file_path,
                "secret_scan": "CLEAN",
                "staged": False,
                "error": apply_result.stderr[:1000],
                "message": "git apply --cached --check failed. Patch cannot be applied cleanly.",
            }

        # Check passed — apply for real
        apply_real = subprocess.run(
            ["git", "apply", "--cached", patch_path],
            capture_output=True, text=True, timeout=15, cwd=str(root),
        )
        _StagePath(patch_path).unlink(missing_ok=True)

        if apply_real.returncode != 0:
            return {
                "mode": "STAGED_FAILED",
                "file_path": req.file_path,
                "secret_scan": "CLEAN",
                "staged": False,
                "error": apply_real.stderr[:1000],
            }

        return {
            "mode": "STAGED",
            "file_path": req.file_path,
            "secret_scan": "CLEAN",
            "staged": True,
            "message": (
                "Diff applied to index via git apply --cached. "
                "Use /v1/git/commit to commit the staged changes."
            ),
        }

    except Exception as exc:
        try:
            _StagePath(patch_path).unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Staging error: {exc}") from exc


# ---------------------------------------------------------------------------
# Section 13: Cloud Test / Build Runner
# ---------------------------------------------------------------------------

@router.post("/v1/testing/run")
async def run_tests(req: TestRunRequest) -> Dict[str, Any]:
    """Run targeted pytest tests and return output.

    Uses subprocess to run pytest. No side effects beyond test output.
    """
    import subprocess
    import sys

    if not req.test_paths:
        return {
            "status": "SKIPPED",
            "reason": "No test_paths provided. Specify paths to run targeted tests.",
            "output": "",
        }

    # Block any paths that look like shell injection
    for path in req.test_paths:
        if any(c in path for c in (";", "&", "|", "`", "$", "\n")):
            raise HTTPException(status_code=400, detail=f"Invalid test path: {path!r}")

    cmd = [sys.executable, "-m", "pytest"] + req.test_paths + ["--tb=short", "-q"]
    if req.extra_args:
        # Allow only safe extra args
        safe_args = [a for a in req.extra_args if not any(c in a for c in (";", "&", "|"))]
        cmd.extend(safe_args)

    from pathlib import Path as _Path
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=req.timeout_seconds,
            cwd=str(repo_root()),
        )
        passed = result.returncode == 0
        return {
            "status": "PASSED" if passed else "FAILED",
            "return_code": result.returncode,
            "stdout": result.stdout[-8000:] if req.capture_output else "(suppressed)",
            "stderr": result.stderr[-2000:] if req.capture_output else "(suppressed)",
            "test_paths": req.test_paths,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "return_code": -1,
            "stdout": "",
            "stderr": f"Tests timed out after {req.timeout_seconds}s",
            "test_paths": req.test_paths,
        }


@router.post("/v1/testing/lint")
async def run_lint(req: LintRunRequest) -> Dict[str, Any]:
    """Run lint/type check. Returns pass/fail + issues."""
    import subprocess
    import sys

    from pathlib import Path

    root = str(repo_root())
    results = {}

    if req.linter in ("ruff", "both"):
        targets = req.file_paths or ["."]
        cmd = [sys.executable, "-m", "ruff", "check"] + targets + ["--output-format=concise"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=root)
            results["ruff"] = {
                "passed": r.returncode == 0,
                "output": r.stdout[-4000:],
                "error": r.stderr[-1000:],
            }
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            results["ruff"] = {"passed": False, "output": "", "error": str(e)}

    if req.linter in ("mypy", "both"):
        targets = req.file_paths or ["src/"]
        cmd = [sys.executable, "-m", "mypy"] + targets + ["--ignore-missing-imports"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=root)
            results["mypy"] = {
                "passed": r.returncode == 0,
                "output": r.stdout[-4000:],
                "error": r.stderr[-1000:],
            }
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            results["mypy"] = {"passed": False, "output": "", "error": str(e)}

    all_passed = all(v.get("passed", False) for v in results.values())
    return {
        "status": "PASSED" if all_passed else "FAILED",
        "linter": req.linter,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Section 14: Mobile Commit/Push Workflow
# ---------------------------------------------------------------------------

@router.post("/v1/git/commit")
async def git_commit_workflow(req: GitCommitRequest) -> Dict[str, Any]:
    """Mobile/cloud commit workflow.

    Single-executor pattern. Requires approval_token for actual commit.
    Always runs secret scan first. dry_run=True (default) returns plan only.

    SAFETY:
    - Never commits without approval_token AND dry_run=False.
    - Secret scan abort on any secret found.
    - Single executor — no concurrent commits.
    """
    import subprocess
    import sys
    from pathlib import Path

    root = repo_root()

    # 1. Get diff for secret scan
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=10, cwd=str(root)
        )
        staged_diff = diff_result.stdout
    except Exception:
        staged_diff = ""

    # Also scan unstaged
    try:
        unstaged = subprocess.run(
            ["git", "diff"],
            capture_output=True, text=True, timeout=10, cwd=str(root)
        )
        combined_diff = staged_diff + unstaged.stdout
    except Exception:
        combined_diff = staged_diff

    # 2. Secret scan
    scan = _secret_scan(combined_diff)
    if scan["abort_required"]:
        return {
            "status": "ABORTED",
            "reason": "Secret scan FAILED: potential secrets in diff. Commit blocked.",
            "secret_scan": scan,
            "committed": False,
        }

    # 3. Get branch and status
    try:
        branch_r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(root)
        )
        current_branch = branch_r.stdout.strip()
    except Exception:
        current_branch = "unknown"

    try:
        status_r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=5, cwd=str(root)
        )
        git_status = status_r.stdout
    except Exception:
        git_status = ""

    base_response = {
        "branch": req.branch or current_branch,
        "commit_message": req.commit_message,
        "files": req.files,
        "git_status_preview": git_status[:2000],
        "secret_scan": {"status": scan["status"], "abort_required": False},
    }

    # 4. Dry-run: never commit
    if req.dry_run or not req.approval_token:
        return {
            **base_response,
            "mode": "DRY_RUN",
            "committed": False,
            "approval_required": True,
            "message": (
                "Dry-run complete. Diff reviewed, secret scan CLEAN. "
                "Submit approval_token with dry_run=False to execute commit."
            ),
        }

    # 5. Approval token present + dry_run=False: execute real commit
    try:
        from openjarvis.plan9.execution_chain import (
            assert_allowed_workflow_file,
            mark_approval_used,
            record_execution_audit,
            repo_root as _repo_root,
            rollback_instruction,
            validate_plan8_approval,
        )
        approval = validate_plan8_approval(
            req.approval_token,
            "git_commit",
            allowed_action_types=["git_commit", "git_workflow"],
        )
    except ValueError as exc:
        record_execution_audit(
            action_type="git_commit",
            actor="jarvis",
            execution_status="blocked",
            error_message=str(exc),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not req.files:
        raise HTTPException(
            status_code=400,
            detail="files list required for real commit — specify allowlisted paths explicitly",
        )

    try:
        for file_path in req.files:
            assert_allowed_workflow_file(file_path)

        add_result = subprocess.run(
            ["git", "add", "--"] + req.files,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(_repo_root()),
        )
        if add_result.returncode != 0:
            record_execution_audit(
                action_type="git_commit",
                actor=approval.requester,
                execution_status="failed",
                approval_decision="granted",
                affected_resource=",".join(req.files),
                error_message=add_result.stderr[:500],
                metadata={"approval_id": approval.approval_id},
            )
            return {
                **base_response,
                "mode": "COMMIT_FAILED",
                "committed": False,
                "error": add_result.stderr[:1000],
            }

        commit_result = subprocess.run(
            ["git", "commit", "-m", req.commit_message],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_repo_root()),
        )
        committed = commit_result.returncode == 0
        commit_hash = ""
        if committed:
            hash_r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(_repo_root()),
            )
            commit_hash = hash_r.stdout.strip() if hash_r.returncode == 0 else ""

        mark_approval_used(approval.approval_id)
        rollback = rollback_instruction(commit_hash) if committed else ""
        record_execution_audit(
            action_type="git_commit",
            actor=approval.requester,
            execution_status="success" if committed else "failed",
            approval_decision="granted",
            affected_resource=commit_hash or ",".join(req.files),
            rollback_reference=rollback,
            error_message="" if committed else commit_result.stderr[:500],
            metadata={
                "approval_id": approval.approval_id,
                "branch": req.branch or current_branch,
                "files": req.files,
            },
        )

        return {
            **base_response,
            "mode": "COMMITTED" if committed else "COMMIT_FAILED",
            "committed": committed,
            "commit_hash": commit_hash,
            "output": (commit_result.stdout + commit_result.stderr)[:2000],
            "rollback_instruction": rollback,
            "approval_id": approval.approval_id,
            "approval_required": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        record_execution_audit(
            action_type="git_commit",
            actor=approval.requester,
            execution_status="failed",
            approval_decision="granted",
            error_message=str(exc),
            metadata={"approval_id": approval.approval_id},
        )
        raise HTTPException(status_code=500, detail=f"Commit error: {exc}") from exc


# ---------------------------------------------------------------------------
# Section 15: Cloud Deploy Operator
# ---------------------------------------------------------------------------

@router.post("/v1/deploy/plan")
async def deploy_plan(req: DeployPlanRequest) -> Dict[str, Any]:
    """Dry-run deploy plan. HARD GATE — never executes a real deploy.

    Returns the deploy plan and always sets approval_required=True.
    Bryan must approve before any real deploy can proceed (separate workflow).
    """
    return {
        "mode": "DRY_RUN_PLAN_ONLY",
        "deploy_target": req.deploy_target,
        "image_tag": req.image_tag,
        "notes": req.notes,
        "approval_required": True,
        "approval_gate": "bryan_approval_required",
        "plan": {
            "step_1": "Build Docker image (if image_tag not provided)",
            "step_2": "Run pre-deploy validation tests",
            "step_3": "Deploy to ECS/cloud runtime (BLOCKED until approval)",
            "step_4": "Update health check endpoint",
            "step_5": "Verify /health returns HTTP 200",
            "step_6": "Rollback if health check fails",
        },
        "rollback_plan": {
            "step_1": "Restore previous task definition",
            "step_2": "Verify /health recovers",
            "step_3": "Report rollback completion",
        },
        "message": (
            "Deploy plan generated. No deploy was executed. "
            "Submit this plan to Bryan for approval before proceeding."
        ),
        "executed": False,
    }


# ---------------------------------------------------------------------------
# Section 19: Mac Worker Queue Routes
# ---------------------------------------------------------------------------

@router.get("/v1/mac-worker/queue")
async def get_mac_worker_queue_all() -> Dict[str, Any]:
    """Return all tasks in the Mac worker queue. Visible from mobile and MacBook."""
    q = get_mac_worker_queue()
    return q.to_api_response()


@router.post("/v1/mac-worker/queue")
async def submit_mac_worker_task(req: MacWorkerSubmitRequest) -> Dict[str, Any]:
    """Submit a new Mac-only task to the queue."""
    try:
        task_type = MacTaskType(req.task_type)
    except ValueError:
        valid = [t.value for t in MacTaskType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_type {req.task_type!r}. Valid: {valid}",
        )

    task = MacWorkerTask(
        task_type=task_type,
        display_name=req.display_name,
        description=req.description,
        submitted_from=req.submitted_from,
    )
    q = get_mac_worker_queue()
    task_id = q.submit(task)

    return {
        "task_id": task_id,
        "status": "QUEUED",
        "task_type": req.task_type,
        "display_name": req.display_name,
        "message": (
            "Task queued. Will execute when MacBook is online. "
            "Check /v1/mac-worker/status for updates."
        ),
    }


@router.get("/v1/mac-worker/status")
async def get_mac_worker_status() -> Dict[str, Any]:
    """Return Mac worker queue status summary. Visible from both surfaces."""
    q = get_mac_worker_queue()
    summary = q.status_summary()

    return {
        "queue_status": summary,
        "mac_only_task_types": [t.value for t in MAC_ONLY_TASK_TYPES],
        "cloud_native_task_types": CLOUD_NATIVE_TASK_TYPES,
        "note": (
            "Tasks in 'queued' status are waiting for MacBook to come online. "
            "Status is visible from both mobile and MacBook surfaces."
        ),
    }


# ---------------------------------------------------------------------------
# Plan 9 Org Hierarchy — canonical chain representation
# ---------------------------------------------------------------------------

@router.get("/v1/plan9/org-hierarchy")
async def get_plan9_org_hierarchy() -> Dict[str, Any]:
    """Return the canonical Jarvis org hierarchy for UI representation.

    Canonical chain:
      Bryan → Jarvis PA → COS/GM → Managers → Workers
      → Reviewer/Tester/Verifier (independent) → COS/GM → Jarvis PA → Bryan

    Approval chain:
      Worker/Manager → Domain Manager → Reviewer → COS/GM → Jarvis PA → Bryan
      → Bryan approves/denies through Jarvis PA only → COS/GM routes back down

    Design invariant: Bryan only interacts through Jarvis PA.
    Workers, managers, reviewers must not directly produce user-facing responses.
    """
    nodes = get_org_hierarchy()
    pa_config = get_pa_config()
    brain_config = get_brain_layer_config()
    return {
        "canonical_chain": (
            "Bryan → Jarvis PA → COS/GM → Domain Managers → Worker Teams "
            "→ Reviewer/Tester/Verifier (independent) → COS/GM → Jarvis PA → Bryan"
        ),
        "approval_chain": (
            "Worker/Manager → Domain Manager validates → Reviewer checks risk "
            "→ COS/GM escalates → Jarvis PA asks Bryan → Bryan approves/denies "
            "through Jarvis PA only → COS/GM routes decision back down"
        ),
        "user_facing_only": "jarvis_pa",
        "user_interacts_only_through": "jarvis_pa",
        "pa_layer": pa_config.to_dict(),
        "brain_layer": brain_config.to_dict(),
        "nodes": [
            {
                "node_id": n.node_id,
                "display_name": n.display_name,
                "layer": n.layer.value,
                "reports_to": n.reports_to,
                "ownership": n.ownership,
                "scope": n.scope,
                "acceptance_criteria": n.acceptance_criteria,
                "evidence_requirements": n.evidence_requirements,
                "model_tier_ref": n.model_tier_ref,
                "report_format": n.report_format,
                "children": n.children,
            }
            for n in nodes
        ],
        "node_count": len(nodes),
        "reviewer_independent": True,
        "reviewer_self_verify_blocked": True,
    }


# ---------------------------------------------------------------------------
# Plan 9 Rules / Skills / Commands introspection
# ---------------------------------------------------------------------------

@router.get("/v1/plan9/rules")
async def get_plan9_rules(category: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Return Plan 9 internal operating rules."""
    rules = PLAN9_INTERNAL_RULES
    if category:
        rules = [r for r in rules if r.category == category]
    return {
        "total": len(rules),
        "categories": list({r.category for r in PLAN9_INTERNAL_RULES}),
        "rules": [
            {
                "rule_id": r.rule_id,
                "category": r.category,
                "description": r.description,
                "enforcement": r.enforcement,
            }
            for r in rules
        ],
    }


@router.get("/v1/plan9/skills")
async def get_plan9_skills(status_filter: Optional[str] = Query(None, alias="status")) -> Dict[str, Any]:
    """Return Plan 9 skills manifest."""
    skills = PLAN9_SKILLS_MANIFEST
    if status_filter:
        skills = [s for s in skills if s.status.value == status_filter.upper()]
    return {
        "total": len(skills),
        "filtered_by_status": status_filter,
        "skills": [s.to_dict() for s in skills],
    }


@router.get("/v1/plan9/commands")
async def get_plan9_commands(status_filter: Optional[str] = Query(None, alias="status")) -> Dict[str, Any]:
    """Return Plan 9 commands manifest."""
    commands = PLAN9_COMMANDS_MANIFEST
    if status_filter:
        commands = [c for c in commands if c.status.value == status_filter.upper()]
    return {
        "total": len(commands),
        "filtered_by_status": status_filter,
        "commands": [c.to_dict() for c in commands],
    }


@router.get("/v1/plan9/registry")
async def get_plan9_registry() -> Dict[str, Any]:
    """Live manager/worker registry from Plan 9K role declarations."""
    from openjarvis.plan9.specialized_router import (
        get_role_declarations,
        get_specialized_router,
    )

    decls = get_role_declarations()
    router_inst = get_specialized_router()
    roles: List[Dict[str, Any]] = []
    managers = 0
    workers = 0
    for role_id in sorted(decls):
        decl = decls[role_id]
        if decl.role_type == "manager":
            managers += 1
        else:
            workers += 1
        entry = decl.to_dict()
        try:
            decision = router_inst.select(
                role_id=role_id,
                task_description="registry_status_probe",
                task_classification="normal",
            )
            entry["routed_model"] = decision.chosen_model_id
            entry["route_reason"] = decision.route_reason
        except Exception as exc:  # noqa: BLE001 — surface routing failure in registry
            entry["routed_model"] = None
            entry["route_reason"] = f"routing_error:{type(exc).__name__}"
        roles.append(entry)

    return {
        "source": "specialized_router.role_declarations",
        "total_roles": len(roles),
        "total_managers": managers,
        "total_workers": workers,
        "roles": roles,
    }


@router.get("/v1/plan9/inheritance")
async def get_plan9_inheritance() -> Dict[str, Any]:
    """Return Plan 9 default inheritance policy for future managers/workers."""
    p = PLAN9_DEFAULT_INHERITANCE
    return {
        "description": (
            "Default policy inherited by every new manager or worker. "
            "Override requires override_reason. Missing policy = validation failure."
        ),
        "default_model_tier": p.default_model_tier.value,
        "retrieval_worker_required": p.retrieval_worker_required,
        "retrieval_before_reasoning": p.retrieval_before_reasoning,
        "scaling_allowed": p.scaling_allowed,
        "max_workers_default": p.max_workers_default,
        "single_executor_for_writes": p.single_executor_for_writes,
        "audit_events_required": p.audit_events_required,
        "hard_gated_actions_blocked_by_default": p.hard_gated_actions_blocked_by_default,
        "bryan_approval_required_for_sensitive": p.bryan_approval_required_for_sensitive,
        "must_appear_in_capability_matrix": p.must_appear_in_capability_matrix,
        "mobile_parity_required": p.mobile_parity_required,
        "mac_parity_required": p.mac_parity_required,
        "report_format": p.report_format,
    }


# ---------------------------------------------------------------------------
# Phase 3 additions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# /v1/coding/search — repo code search (allowlisted, secret-safe)
# ---------------------------------------------------------------------------

class CodeSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Search query (regex or literal)")
    paths: List[str] = Field(default_factory=list, description="Repo-relative paths to search (empty = src/ + tests/ + docs/)")
    file_glob: str = Field("*.py", description="File glob pattern (e.g. '*.py', '*.md')")
    max_results: int = Field(50, ge=1, le=200, description="Max results to return")
    context_lines: int = Field(2, ge=0, le=5, description="Lines of context around each match")
    regex: bool = Field(False, description="Treat query as regex (default: literal)")


@router.post("/v1/coding/search")
async def search_code(req: CodeSearchRequest) -> Dict[str, Any]:
    """Search the repo for code matching query. Allowlisted paths only, secret-safe output.

    Uses ripgrep (rg) if available, falls back to Python grep.
    Results are scanned for secrets before returning.
    """
    import subprocess
    import sys
    from pathlib import Path as _SearchPath

    root = repo_root()

    # Allowlisted search roots
    allowed_roots = ("src/", "tests/", "docs/", "configs/")
    search_paths: List[str] = []

    if req.paths:
        for p in req.paths:
            if ".." in p or p.startswith("/"):
                raise HTTPException(status_code=400, detail=f"Path traversal not allowed: {p!r}")
            if not any(p.startswith(a) for a in allowed_roots):
                raise HTTPException(
                    status_code=403,
                    detail=f"Path {p!r} not in allowlist {allowed_roots}",
                )
            search_paths.append(p)
    else:
        search_paths = ["src/", "tests/", "docs/"]

    # Shell-injection guard on query
    if "\x00" in req.query or len(req.query) > 500:
        raise HTTPException(status_code=400, detail="Invalid query")

    # Build rg command
    rg_args = ["rg"]
    if not req.regex:
        rg_args.append("--fixed-strings")
    rg_args += [
        "--glob", req.file_glob,
        "--max-count", "1",
        f"--context={req.context_lines}",
        "--json",
        req.query,
    ]
    rg_args += search_paths

    results = []
    raw_output = ""
    try:
        proc = subprocess.run(
            rg_args,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(root),
        )
        raw_output = proc.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # rg not available or timed out — fall back to Python grep
        import re as _re
        pattern = _re.compile(req.query if req.regex else _re.escape(req.query))
        for search_path in search_paths:
            base = root / search_path
            for fpath in base.rglob(req.file_glob):
                if not fpath.is_file():
                    continue
                try:
                    lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
                    for lineno, line in enumerate(lines, 1):
                        if pattern.search(line):
                            results.append({
                                "file": str(fpath.relative_to(root)),
                                "line": lineno,
                                "text": line,
                            })
                            if len(results) >= req.max_results:
                                break
                except Exception:
                    continue
                if len(results) >= req.max_results:
                    break

    # Parse rg JSON output when available
    if raw_output:
        import json as _json
        match_count = 0
        for line in raw_output.splitlines():
            if not line.strip():
                continue
            try:
                obj = _json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "match":
                data = obj.get("data", {})
                results.append({
                    "file": data.get("path", {}).get("text", ""),
                    "line": data.get("line_number", 0),
                    "text": data.get("lines", {}).get("text", "").rstrip("\n"),
                })
                match_count += 1
                if match_count >= req.max_results:
                    break

    # Enforce hard cap before secret scan
    results = results[:req.max_results]

    # Secret-scan results before returning (scan the text portion only)
    combined_result_text = "\n".join(r.get("text", "") for r in results)
    scan = _secret_scan(combined_result_text)
    if scan["abort_required"]:
        return {
            "status": "SECRET_DETECTED",
            "message": "Search results contained a secret pattern. Results suppressed.",
            "count": 0,
            "results": [],
            "secret_scan": scan,
        }

    return {
        "status": "OK",
        "query": req.query,
        "paths_searched": search_paths,
        "file_glob": req.file_glob,
        "count": len(results),
        "truncated": len(results) >= req.max_results,
        "results": results[:req.max_results],
        "secret_scan": {"status": scan["status"]},
    }


# ---------------------------------------------------------------------------
# /v1/coding/create-branch — branch creation (dry-run default, approval-gated)
# ---------------------------------------------------------------------------

_SAFE_BRANCH_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,99}$")
_PROTECTED_BRANCHES = frozenset({"main", "master", "production", "prod", "release"})


class CreateBranchRequest(BaseModel):
    branch_name: str = Field(..., min_length=2, description="New branch name")
    base_branch: str = Field("main", description="Base branch to branch from")
    dry_run: bool = Field(True, description="If True (default), validate only — no git call")
    approval_token: Optional[str] = Field(None, description="Required for dry_run=False")


@router.post("/v1/coding/create-branch")
async def create_branch(req: CreateBranchRequest) -> Dict[str, Any]:
    """Create a new git branch. Dry-run by default.

    dry_run=True (default): validates branch name, checks base exists, returns plan.
    dry_run=False: requires approval_token, runs git checkout -b <branch> <base>.

    SAFETY:
    - Protected branches (main/master/production) cannot be used as new branch names.
    - Branch names validated against safe regex.
    - Force push to main/master is always blocked.
    """
    import subprocess
    from pathlib import Path as _BranchPath

    # Validate branch name
    if not _SAFE_BRANCH_RE.match(req.branch_name):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Branch name {req.branch_name!r} is not safe. "
                "Use only alphanumeric, dots, dashes, underscores, slashes."
            ),
        )
    if req.branch_name in _PROTECTED_BRANCHES:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot create branch named {req.branch_name!r} — it is a protected branch name.",
        )

    if not req.dry_run and not req.approval_token:
        raise HTTPException(
            status_code=403,
            detail="approval_token required for dry_run=False.",
        )

    root = repo_root()

    # Get current branches for dry-run report
    try:
        branch_list_r = subprocess.run(
            ["git", "branch", "-a"],
            capture_output=True, text=True, timeout=10, cwd=str(root),
        )
        existing = branch_list_r.stdout
    except Exception:
        existing = ""

    branch_exists = req.branch_name in existing

    if req.dry_run:
        return {
            "mode": "DRY_RUN",
            "branch_name": req.branch_name,
            "base_branch": req.base_branch,
            "branch_already_exists": branch_exists,
            "would_create": not branch_exists,
            "command_preview": f"git checkout -b {req.branch_name} {req.base_branch}",
            "approval_required_for_create": True,
            "message": (
                f"Dry-run complete. Branch {req.branch_name!r} would be created from {req.base_branch!r}. "
                "Submit approval_token with dry_run=False to create."
            ),
        }

    # Non-dry-run: approval present — create the branch
    if branch_exists:
        raise HTTPException(
            status_code=409,
            detail=f"Branch {req.branch_name!r} already exists.",
        )

    try:
        create_r = subprocess.run(
            ["git", "checkout", "-b", req.branch_name, req.base_branch],
            capture_output=True, text=True, timeout=15, cwd=str(root),
        )
        if create_r.returncode != 0:
            return {
                "mode": "CREATE_FAILED",
                "branch_name": req.branch_name,
                "error": create_r.stderr[:500],
            }
        return {
            "mode": "CREATED",
            "branch_name": req.branch_name,
            "base_branch": req.base_branch,
            "created": True,
            "message": f"Branch {req.branch_name!r} created from {req.base_branch!r}.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Branch creation error: {exc}") from exc


# ---------------------------------------------------------------------------
# /v1/git/push — push workflow (single-executor, approval-gated, dry-run default)
# ---------------------------------------------------------------------------

class GitPushRequest(BaseModel):
    branch: Optional[str] = Field(None, description="Branch to push (empty = current branch)")
    remote: str = Field("origin", description="Remote name")
    dry_run: bool = Field(True, description="If True (default), runs git push --dry-run")
    approval_token: Optional[str] = Field(None, description="Required for dry_run=False")
    force: bool = Field(False, description="Force push. Requires confirm_force=True and is blocked for protected branches.")
    confirm_force: bool = Field(False, description="Must be True to allow force=True to proceed")


class OrchestrationDagRunRequest(BaseModel):
    task_description: str = Field(..., min_length=3, description="Controlled task description")
    scope: str = Field("tests/fixtures", description="Retrieval scope (allowlisted paths only)")


class OrchestrationBatchRunRequest(BaseModel):
    target_file: str = Field(..., description="Allowlisted fixture file path")
    worker_a_patch: str = Field(..., min_length=1, description="Worker A proposed content")
    worker_b_patch: str = Field(..., min_length=1, description="Worker B proposed content")
    run_tests: bool = Field(True, description="Run pytest after integration")


class CodingWorkflowRequest(BaseModel):
    """Jarvis coding workflow — plan, edit, test, diff, approval-gated commit/push."""
    task: str = Field(..., min_length=5, description="Task description")
    target_file: str = Field(
        "tests/fixtures/plan9_workflow_status.txt",
        description="Allowlisted file to edit",
    )
    edit_line: str = Field(..., min_length=3, description="Harmless line to append")
    test_paths: List[str] = Field(
        default_factory=lambda: ["tests/core/test_env_loader.py"],
        description="pytest paths to run after edit",
    )
    commit_message: str = Field(..., min_length=8, description="Commit message if committing")
    remote: str = Field("fork", description="Git remote for push")
    branch: Optional[str] = Field(None, description="Branch to push (default: current)")
    dry_run: bool = Field(True, description="If True, stop after diff/tests (no commit/push)")
    commit_approval_token: Optional[str] = Field(None, description="Plan 8 approval_id for commit")
    push_approval_token: Optional[str] = Field(None, description="Plan 8 approval_id for push")
    workflow_id: str = Field("loop", description="Workflow identifier for audit (loop1, loop2, etc.)")


@router.post("/v1/git/push")
async def git_push_workflow(req: GitPushRequest) -> Dict[str, Any]:
    """Push workflow. Single-executor, approval-gated, secret-scan gated.

    dry_run=True (default): runs git push --dry-run, returns what would be pushed.
    dry_run=False + approval_token: actually pushes.

    SAFETY:
    - Force push to main/master is always blocked regardless of flags.
    - Force push to any branch requires both force=True AND confirm_force=True.
    - Runs git diff --cached secret scan before any push.
    - Never pushes without approval_token and dry_run=False.
    """
    import subprocess
    from pathlib import Path as _PushPath

    root = repo_root()

    # Determine current branch if not specified
    try:
        branch_r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(root),
        )
        current_branch = branch_r.stdout.strip()
    except Exception:
        current_branch = "unknown"

    target_branch = req.branch or current_branch

    # Block force push to protected branches unconditionally
    if req.force and target_branch in _PROTECTED_BRANCHES:
        raise HTTPException(
            status_code=403,
            detail=f"Force push to protected branch {target_branch!r} is permanently blocked.",
        )

    # Force push requires confirm_force
    if req.force and not req.confirm_force:
        raise HTTPException(
            status_code=400,
            detail="force=True requires confirm_force=True to prevent accidental force pushes.",
        )

    # Secret scan staged + unstaged diff
    try:
        diff_r = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True, text=True, timeout=10, cwd=str(root),
        )
        diff_text = diff_r.stdout
    except Exception:
        diff_text = ""

    scan = _secret_scan(diff_text)
    if scan["abort_required"]:
        return {
            "status": "ABORTED",
            "reason": "Secret scan FAILED on diff. Push blocked.",
            "secret_scan": scan,
            "pushed": False,
        }

    # Get push preview
    try:
        log_r = subprocess.run(
            ["git", "log", "--oneline", f"{req.remote}/{target_branch}..{target_branch}"],
            capture_output=True, text=True, timeout=10, cwd=str(root),
        )
        commits_to_push = log_r.stdout.strip()
    except Exception:
        commits_to_push = "(could not determine)"

    base = {
        "branch": target_branch,
        "remote": req.remote,
        "commits_to_push": commits_to_push or "(none — branch is up to date)",
        "force": req.force,
        "secret_scan": {"status": scan["status"]},
    }

    # Gate: no approval → dry-run regardless
    if req.dry_run or not req.approval_token:
        try:
            push_cmd = ["git", "push", "--dry-run", req.remote, target_branch]
            if req.force:
                push_cmd.insert(2, "--force")
            dry_r = subprocess.run(
                push_cmd,
                capture_output=True, text=True, timeout=20, cwd=str(root),
            )
            dry_output = (dry_r.stdout + dry_r.stderr)[:2000]
        except Exception as exc:
            dry_output = f"git push --dry-run failed: {exc}"

        return {
            **base,
            "mode": "DRY_RUN",
            "pushed": False,
            "dry_run_output": dry_output,
            "approval_required": True,
            "message": (
                "Dry-run complete. Submit approval_token with dry_run=False to push."
            ),
        }

    # Non-dry-run: approval present — validate and push for real
    from openjarvis.plan9.execution_chain import (
        mark_approval_used,
        record_execution_audit,
        rollback_instruction,
        validate_plan8_approval,
    )

    try:
        approval = validate_plan8_approval(
            req.approval_token,
            "git_push",
            allowed_action_types=["git_push", "git_workflow"],
        )
    except ValueError as exc:
        record_execution_audit(
            action_type="git_push",
            actor="jarvis",
            execution_status="blocked",
            error_message=str(exc),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    push_cmd = ["git", "push", req.remote, target_branch]
    if req.force:
        push_cmd.insert(2, "--force")

    try:
        push_r = subprocess.run(
            push_cmd,
            capture_output=True, text=True, timeout=60, cwd=str(root),
        )
        pushed = push_r.returncode == 0
        rollback = (
            f"git push {req.remote} {target_branch}~1:{target_branch}  # force rollback — owner approval required"
            if pushed
            else ""
        )
        mark_approval_used(approval.approval_id)
        record_execution_audit(
            action_type="git_push",
            actor=approval.requester,
            execution_status="success" if pushed else "failed",
            approval_decision="granted",
            affected_resource=f"{req.remote}/{target_branch}",
            rollback_reference=rollback,
            error_message="" if pushed else push_r.stderr[:500],
            metadata={"approval_id": approval.approval_id},
        )
        return {
            **base,
            "mode": "PUSHED" if pushed else "PUSH_FAILED",
            "pushed": pushed,
            "output": (push_r.stdout + push_r.stderr)[:2000],
            "rollback_instruction": rollback,
            "approval_id": approval.approval_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Push error: {exc}") from exc


# ---------------------------------------------------------------------------
# /v1/files/index — cloud-safe repo file index (metadata only, no content)
# ---------------------------------------------------------------------------

@router.get("/v1/files/index")
async def get_files_index(
    path_prefix: Optional[str] = Query(None, description="Filter by path prefix (e.g. src/openjarvis/plan9/)"),
    glob_pattern: Optional[str] = Query("**/*.py", description="Glob pattern for file types"),
    include_git_status: bool = Query(False, description="Include git status for each file"),
    max_files: int = Query(500, ge=1, le=2000, description="Max files to return"),
) -> Dict[str, Any]:
    """Return a cloud-safe index of repo files (metadata only — no file content).

    Returns: file paths, sizes, modification times, optional git status.
    No file content is returned. Allowlisted directories only.
    """
    import subprocess
    from openjarvis.plan9.workspace_root import workspace_index_summary, workspace_root

    root = workspace_root()
    allowed_roots = workspace_allowlist_roots()

    # Validate path_prefix
    if path_prefix:
        if ".." in path_prefix or path_prefix.startswith("/"):
            raise HTTPException(status_code=400, detail="Path traversal not allowed")
        if not any(path_prefix.startswith(a) for a in allowed_roots):
            raise HTTPException(
                status_code=403,
                detail=f"Path prefix {path_prefix!r} not in allowlist {allowed_roots}",
            )
        search_root = root / path_prefix
    else:
        search_root = None

    # Collect files
    files = []
    for allowed in allowed_roots:
        base = root / allowed.rstrip("/")
        if not base.exists():
            continue
        # Apply path_prefix filter
        if search_root and not str(base).startswith(str(search_root)) and not str(search_root).startswith(str(base)):
            continue

        try:
            for fpath in base.rglob(glob_pattern or "**/*.py"):
                if not fpath.is_file():
                    continue
                if search_root and not str(fpath).startswith(str(search_root)):
                    continue
                try:
                    stat = fpath.stat()
                    rel = str(fpath.relative_to(root))
                    files.append({
                        "path": rel,
                        "size_bytes": stat.st_size,
                        "modified_ts": int(stat.st_mtime),
                    })
                except Exception:
                    continue
                if len(files) >= max_files:
                    break
        except Exception:
            continue
        if len(files) >= max_files:
            break

    # Optional git status
    git_status_map: Dict[str, str] = {}
    if include_git_status and files:
        try:
            status_r = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=10, cwd=str(root),
            )
            for line in status_r.stdout.splitlines():
                if len(line) >= 3:
                    status_code = line[:2].strip()
                    fpath_str = line[3:].strip()
                    git_status_map[fpath_str] = status_code
        except Exception:
            pass

    if include_git_status:
        for f in files:
            f["git_status"] = git_status_map.get(f["path"], "")

    summary = workspace_index_summary(root)
    return {
        "total": len(files),
        "truncated": len(files) >= max_files,
        "path_prefix": path_prefix,
        "glob_pattern": glob_pattern,
        "workspace_root": summary["workspace_root"],
        "indexed_file_count": summary["indexed_file_count"],
        "files": files,
    }


# ---------------------------------------------------------------------------
# /v1/files/cloud-index — Plan 2C git-tracked file index (MacBook-off safe)
# ---------------------------------------------------------------------------

@router.get("/v1/files/cloud-index")
async def get_files_cloud_index(
    path_prefix: Optional[str] = Query(None, description="Filter by path prefix"),
    max_files: int = Query(1000, ge=1, le=2000, description="Max files to return"),
) -> Dict[str, Any]:
    """Cloud-safe index of git-tracked repo files (Plan 2C foundation).

    Uses ``git ls-files`` instead of local filesystem rglob — works in cloud
    containers where OPENJARVIS_ROOT=/app and the repo is cloned.

    Returns: path, size_bytes (if file is present), extension, git_tracked=True.
    No file content is returned. Allowlisted paths only.
    Never returns .env, .git/, or credential paths.
    """
    from openjarvis.plan9.workspace_root import (
        git_is_available,
        git_tracked_files,
        workspace_allowlist_roots,
        workspace_root,
    )

    root = workspace_root()
    allowed = workspace_allowlist_roots()

    if path_prefix:
        if ".." in path_prefix or path_prefix.startswith("/"):
            raise HTTPException(status_code=400, detail="Path traversal not allowed")
        if not any(path_prefix.startswith(a) for a in allowed):
            raise HTTPException(
                status_code=403,
                detail=f"path_prefix {path_prefix!r} is not in the cloud-safe allowlist.",
            )

    git_available = git_is_available(root)
    if not git_available:
        return {
            "status": "UNAVAILABLE",
            "reason": "git not available in this runtime — repo may not be cloned",
            "files": [],
            "total": 0,
            "git_tracked": False,
        }

    files = git_tracked_files(root, allowed_roots=allowed, max_files=max_files)

    if path_prefix:
        files = [f for f in files if f["path"].startswith(path_prefix)]

    truncated = len(files) >= max_files

    return {
        "status": "OK",
        "plan": "2C",
        "source": "git ls-files",
        "git_tracked": True,
        "workspace_root": str(root),
        "allowed_roots": list(allowed),
        "path_prefix": path_prefix,
        "total": len(files),
        "truncated": truncated,
        "macbook_off_safe": True,
        "files": files,
    }


# ---------------------------------------------------------------------------
# /v1/files/workspace/status — Plan 2C workspace sync status (auth-gated)
# ---------------------------------------------------------------------------

@router.get("/v1/files/workspace/status")
async def get_workspace_sync_status(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_p9_bearer),
) -> Dict[str, Any]:
    """Plan 2C — honest workspace sync status for mobile/MacBook-off operation.

    AUTH REQUIRED. Returns Bearer-gated workspace accounting.
    Reports git-tracked vs local-only counts; S3 artifact store presence.
    Never returns file paths, file contents, usernames, local home paths,
    credential values, env var values, or account IDs.
    """
    import os as _os
    from openjarvis.plan9.workspace_root import workspace_sync_summary

    api_key = _os.environ.get("OPENJARVIS_API_KEY", "").strip()
    if api_key:
        import secrets as _sec
        token = credentials.credentials if credentials else ""
        if not token or not _sec.compare_digest(token.strip(), api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")

    sync = workspace_sync_summary()

    provider = _os.environ.get("OMNIX_WORKBENCH_STORAGE_PROVIDER", "local").strip()
    memory_bucket_ok = bool(_os.environ.get("OMNIX_WORKBENCH_MEMORY_BUCKET", "").strip())
    artifact_bucket_ok = bool(_os.environ.get("OMNIX_WORKBENCH_ARTIFACT_BUCKET", "").strip())
    state_table_ok = bool(_os.environ.get("OMNIX_WORKBENCH_STATE_TABLE", "").strip())
    region_ok = bool(_os.environ.get("OMNIX_WORKBENCH_AWS_REGION", "").strip())

    configured_count = sum([memory_bucket_ok, artifact_bucket_ok, state_table_ok, region_ok])
    if provider == "aws" and configured_count == 4:
        s3_status = "READY"
    elif configured_count >= 2:
        s3_status = "PARTIAL"
    elif configured_count >= 1:
        s3_status = "BLOCKED"
    else:
        s3_status = "NOT_CONFIGURED"

    git_indexed = sync.get("git_tracked_count", 0)
    modified = sync.get("modified_count", 0)
    untracked = sync.get("untracked_count", 0)

    overall_status: str
    if not sync.get("git_available"):
        overall_status = "BLOCKED"
    elif s3_status in ("BLOCKED", "NOT_CONFIGURED"):
        overall_status = "PARTIAL"
    elif s3_status == "PARTIAL":
        overall_status = "PARTIAL"
    else:
        overall_status = "MACBOOK_OFF_PENDING"

    return {
        "plan": "2C",
        "status": overall_status,
        "git_available": sync.get("git_available", False),
        "cloud_indexable_files": git_indexed,
        "locally_modified_tracked": modified,
        "local_only_untracked": untracked,
        "permanent_exceptions": sync.get("permanent_exception", ""),
        "s3_artifact_store": {
            "status": s3_status,
            "memory_bucket_configured": memory_bucket_ok,
            "artifact_bucket_configured": artifact_bucket_ok,
            "state_table_configured": state_table_ok,
            "region_configured": region_ok,
            "provider_aws": provider == "aws",
            "note": "Presence-only — no values exposed, no live S3 connection attempted.",
        },
        "workspace_sync": {
            "full_sync_to_s3": "NOT_IMPLEMENTED",
            "git_tracked_read": "AVAILABLE" if sync.get("git_available") else "UNAVAILABLE",
            "cloud_index_route": "GET /v1/files/cloud-index",
            "file_read_route": "POST /v1/coding/files/read",
        },
        "blockers": (
            ["Full workspace sync to S3 not implemented — git-tracked files readable only"]
            + ([] if s3_status not in ("BLOCKED", "NOT_CONFIGURED") else
               [f"S3 artifact store: {s3_status} — bucket/table env vars not fully configured"])
        ),
        "auth": "Bearer token validated",
    }


# ---------------------------------------------------------------------------
# /v1/coding/workflow — Jarvis approval-gated coding execution chain
# ---------------------------------------------------------------------------

_LAST_WORKFLOW_STATUS: Dict[str, Any] = {}


@router.get("/v1/coding/workflow/status")
async def get_coding_workflow_status() -> Dict[str, Any]:
    """Return last Jarvis coding workflow execution status."""
    return {
        "last_workflow": _LAST_WORKFLOW_STATUS or None,
        "endpoint": "POST /v1/coding/workflow/run",
    }


@router.post("/v1/coding/workflow/run")
async def run_coding_workflow(req: CodingWorkflowRequest) -> Dict[str, Any]:
    """Execute Jarvis coding workflow: plan → edit → test → diff → optional commit/push."""
    import subprocess
    import sys
    from datetime import datetime, timezone

    from openjarvis.plan9.execution_chain import (
        assert_allowed_workflow_file,
        git_current_branch,
        record_execution_audit,
        repo_root,
    )

    global _LAST_WORKFLOW_STATUS
    root = repo_root()
    started = datetime.now(timezone.utc).isoformat()

    plan = {
        "task": req.task,
        "target_file": req.target_file,
        "steps": ["edit", "test", "diff", "approval", "commit", "push"],
        "workflow_id": req.workflow_id,
    }

    try:
        assert_allowed_workflow_file(req.target_file)
    except ValueError as exc:
        result = {
            "status": "BLOCKED",
            "workflow_id": req.workflow_id,
            "plan": plan,
            "error": str(exc),
            "started_at": started,
        }
        _LAST_WORKFLOW_STATUS = result
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = root / req.target_file
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Target file not found: {req.target_file}")

    # Edit — append harmless line
    line = req.edit_line.strip()
    if not line.startswith("#") and not line.startswith("status="):
        line = f"# {line}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    append_text = f"\n{line} workflow={req.workflow_id} at={timestamp}\n"
    scan = _secret_scan(append_text)
    if scan["abort_required"]:
        raise HTTPException(status_code=400, detail="Edit line failed secret scan")

    with target.open("a", encoding="utf-8") as fh:
        fh.write(append_text)

    record_execution_audit(
        action_type="coding_workflow_edit",
        actor="jarvis",
        execution_status="success",
        affected_resource=req.target_file,
        metadata={"workflow_id": req.workflow_id, "line": line[:120]},
    )

    # Tests
    test_cmd = [sys.executable, "-m", "pytest"] + req.test_paths + ["--tb=short", "-q"]
    test_r = subprocess.run(test_cmd, capture_output=True, text=True, timeout=120, cwd=str(root))
    tests_passed = test_r.returncode == 0

    record_execution_audit(
        action_type="coding_workflow_test",
        actor="jarvis",
        execution_status="success" if tests_passed else "failed",
        affected_resource=",".join(req.test_paths),
        error_message="" if tests_passed else test_r.stderr[:500],
        metadata={"workflow_id": req.workflow_id, "return_code": test_r.returncode},
    )

    if not tests_passed:
        diff_r = subprocess.run(
            ["git", "diff", "--", req.target_file],
            capture_output=True, text=True, timeout=10, cwd=str(root),
        )
        result = {
            "status": "TESTS_FAILED",
            "workflow_id": req.workflow_id,
            "plan": plan,
            "tests_passed": False,
            "test_output": (test_r.stdout + test_r.stderr)[-4000:],
            "diff": diff_r.stdout[:4000],
            "rollback_instruction": f"git checkout -- {req.target_file}",
            "started_at": started,
        }
        _LAST_WORKFLOW_STATUS = result
        return result

    # Diff
    diff_r = subprocess.run(
        ["git", "diff", "--", req.target_file],
        capture_output=True, text=True, timeout=10, cwd=str(root),
    )
    diff_text = diff_r.stdout

    # Stage file
    subprocess.run(["git", "add", "--", req.target_file], cwd=str(root), timeout=15, check=False)

    base_result: Dict[str, Any] = {
        "status": "READY_FOR_APPROVAL",
        "workflow_id": req.workflow_id,
        "plan": plan,
        "tests_passed": True,
        "test_output_tail": (test_r.stdout + test_r.stderr)[-2000:],
        "diff": diff_text[:8000],
        "target_file": req.target_file,
        "branch": git_current_branch(root),
        "started_at": started,
        "approval_endpoints": {
            "request": "POST /v1/authority/approvals/request",
            "grant": "POST /v1/authority/approvals/{id}/grant",
            "commit": "POST /v1/git/commit",
            "push": "POST /v1/git/push",
        },
    }

    if req.dry_run:
        base_result["status"] = "DRY_RUN_COMPLETE"
        base_result["message"] = (
            "Edit and tests complete. Request Plan 8 approval, then re-run with "
            "dry_run=False and commit_approval_token / push_approval_token."
        )
        _LAST_WORKFLOW_STATUS = base_result
        record_execution_audit(
            action_type="coding_workflow_dry_run",
            actor="jarvis",
            execution_status="success",
            affected_resource=req.target_file,
            metadata={"workflow_id": req.workflow_id},
        )
        return base_result

    # Commit (approval-gated)
    commit_result: Dict[str, Any] = {"committed": False}
    if req.commit_approval_token:
        commit_req = GitCommitRequest(
            commit_message=req.commit_message,
            files=[req.target_file],
            dry_run=False,
            approval_token=req.commit_approval_token,
            branch=req.branch,
        )
        commit_result = await git_commit_workflow(commit_req)
        if not commit_result.get("committed"):
            base_result["status"] = "COMMIT_FAILED"
            base_result["commit"] = commit_result
            _LAST_WORKFLOW_STATUS = base_result
            return base_result
    else:
        base_result["status"] = "COMMIT_APPROVAL_REQUIRED"
        _LAST_WORKFLOW_STATUS = base_result
        return base_result

    # Push (approval-gated) — only if tests passed and commit succeeded
    push_result: Dict[str, Any] = {"pushed": False}
    if req.push_approval_token:
        push_req = GitPushRequest(
            branch=req.branch,
            remote=req.remote,
            dry_run=False,
            approval_token=req.push_approval_token,
        )
        push_result = await git_push_workflow(push_req)
    else:
        base_result["status"] = "PUSH_APPROVAL_REQUIRED"
        base_result["commit"] = commit_result
        _LAST_WORKFLOW_STATUS = base_result
        return base_result

    final = {
        **base_result,
        "status": "COMPLETE" if push_result.get("pushed") else "PUSH_FAILED",
        "commit": commit_result,
        "push": push_result,
        "rollback_instruction": commit_result.get("rollback_instruction", ""),
        "audit_hint": "GET /v1/authority/audit",
    }
    record_execution_audit(
        action_type="coding_workflow_complete",
        actor="jarvis",
        execution_status="success" if push_result.get("pushed") else "failed",
        affected_resource=commit_result.get("commit_hash", req.target_file),
        rollback_reference=final.get("rollback_instruction", ""),
        metadata={"workflow_id": req.workflow_id},
    )
    _LAST_WORKFLOW_STATUS = final
    return final


# ---------------------------------------------------------------------------
# /v1/plan9/runtime-proof-checklist — Bryan iPhone verification checklist
# ---------------------------------------------------------------------------

_RUNTIME_PROOF_ITEMS = [
    {
        "id": "cap_status_mobile",
        "description": "GET /v1/capabilities/status from iPhone",
        "method": "GET",
        "route": "/v1/capabilities/status",
        "expected": "HTTP 200, JSON with 'capabilities' list, total > 0",
        "how": "Open https://<your-jarvis-api>/v1/capabilities/status in Safari on iPhone. "
               "Should return JSON with all managers/workers.",
        "verified": False,
        "category": "mobile_api",
    },
    {
        "id": "parity_status_mobile",
        "description": "GET /v1/parity/status from iPhone",
        "method": "GET",
        "route": "/v1/parity/status",
        "expected": "HTTP 200, JSON with parity_definition, summary, parked list",
        "how": "Open https://<your-jarvis-api>/v1/parity/status in Safari on iPhone.",
        "verified": False,
        "category": "mobile_api",
    },
    {
        "id": "coding_search_mobile",
        "description": "POST /v1/coding/search from iPhone",
        "method": "POST",
        "route": "/v1/coding/search",
        "expected": "HTTP 200, results list, secret_scan.status == CLEAN",
        "how": "curl -X POST https://<your-jarvis-api>/v1/coding/search "
               "-H 'Content-Type: application/json' "
               "-d '{\"query\": \"Plan9CapabilityEntry\", \"paths\": [\"src/\"]}'",
        "verified": False,
        "category": "mobile_api",
    },
    {
        "id": "cloud_memory_read",
        "description": "Cloud memory read parity (read from mobile what MacBook wrote)",
        "method": "GET",
        "route": "/v1/memory/* (existing memory routes)",
        "expected": "Memories written on MacBook are visible from mobile",
        "how": "On MacBook: create a memory via jarvis. On iPhone: GET /v1/memory/list "
               "and verify the memory appears.",
        "verified": False,
        "category": "memory_parity",
    },
    {
        "id": "cloud_memory_write",
        "description": "Cloud memory write parity (write from mobile, verify on MacBook)",
        "method": "POST",
        "route": "/v1/memory/add (existing memory routes)",
        "expected": "Memory written from iPhone is readable on MacBook",
        "how": "On iPhone: POST /v1/memory/add with a test memory. "
               "On MacBook: verify it appears in jarvis memory.",
        "verified": False,
        "category": "memory_parity",
    },
    {
        "id": "gdrive_connector",
        "description": "GDrive connector parity — list files from iPhone",
        "method": "GET",
        "route": "/v1/connectors/gdrive/* (existing connectors router)",
        "expected": "GDrive connector returns file list or CONNECTOR_NOT_CONFIGURED if not set up",
        "how": "GET /v1/connectors/gdrive/list from iPhone. "
               "If GDrive is not configured, expect 200 with not_configured status.",
        "verified": False,
        "category": "connector_parity",
        "skip_if_not_configured": True,
    },
    {
        "id": "notion_connector",
        "description": "Notion connector parity — list pages from iPhone",
        "method": "GET",
        "route": "/v1/connectors/notion/* (existing connectors router)",
        "expected": "Notion connector returns page list or CONNECTOR_NOT_CONFIGURED if not set up",
        "how": "GET /v1/connectors/notion/list from iPhone. "
               "If Notion is not configured, expect 200 with not_configured status.",
        "verified": False,
        "category": "connector_parity",
        "skip_if_not_configured": True,
    },
    {
        "id": "mac_worker_queue_mobile",
        "description": "Submit Mac-only task from iPhone, verify it appears on MacBook",
        "method": "POST",
        "route": "/v1/mac-worker/queue",
        "expected": "Task appears in queue on both surfaces",
        "how": "On iPhone: POST /v1/mac-worker/queue with task_type=app_reinstall. "
               "On MacBook: GET /v1/mac-worker/queue to verify task_id appears.",
        "verified": False,
        "category": "mac_worker_parity",
    },
]


@router.get("/v1/plan9/runtime-proof-checklist")
async def get_runtime_proof_checklist(
    category: Optional[str] = Query(None, description="Filter: mobile_api | memory_parity | connector_parity | mac_worker_parity"),
) -> Dict[str, Any]:
    """Return Bryan's iPhone/cloud runtime proof checklist.

    Lists exactly what Bryan needs to verify from iPhone to upgrade Plan 9 to ACCEPT.
    No secrets required — only human action and HTTP calls.
    """
    items = _RUNTIME_PROOF_ITEMS
    if category:
        items = [i for i in items if i["category"] == category]

    categories = list({i["category"] for i in _RUNTIME_PROOF_ITEMS})

    return {
        "description": (
            "These items require Bryan's manual verification from iPhone/mobile. "
            "No secrets should be pasted anywhere. "
            "Each item tells you exactly what URL to open and what response to expect."
        ),
        "categories": categories,
        "total_items": len(items),
        "verified_count": sum(1 for i in items if i["verified"]),
        "pending_count": sum(1 for i in items if not i["verified"]),
        "verdict_when_all_verified": "PLAN_9_ACCEPT_PENDING_REVIEW",
        "items": items,
        "note": "voice_wake_tts and apple_signing_updater are PARKED (Plan 10/11) and NOT in this checklist.",
    }
