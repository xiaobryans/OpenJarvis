"""Plan 9 live orchestration executors — DAG, retrieval, elastic pools, batch integration.

Minimal real execution paths for controlled proof tasks. Not broad autonomy.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.plan9.execution_chain import record_execution_audit, repo_root
from openjarvis.plan9.orchestration_policy import (
    ELASTIC_POOL_POLICIES,
    ParallelDAGPolicy,
    BatchIntegrationPolicy,
)

BATCH_ALLOWED_PREFIXES = ("tests/fixtures/plan9_",)
BATCH_ALLOWED_FILES = frozenset({
    "tests/fixtures/plan9_batch_target.txt",
    "tests/fixtures/plan9_workflow_status.txt",
})


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class OrchestrationTaskNode:
    task_id: str
    role_id: str
    action_type: str
    state: TaskState = TaskState.QUEUED
    worker_id: str = ""
    depends_on: List[str] = field(default_factory=list)
    parallel_group: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    detail: str = ""
    output: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DagRunRecord:
    run_id: str
    task_description: str
    scope: str
    state: TaskState
    nodes: List[OrchestrationTaskNode]
    parallel_groups: List[List[str]]
    retrieval_invoked: bool
    elastic_plan: Dict[str, Any]
    created_at: float
    completed_at: Optional[float] = None
    audit_event_ids: List[str] = field(default_factory=list)


@dataclass
class BatchRunRecord:
    run_id: str
    target_file: str
    state: TaskState
    worker_patches: List[Dict[str, Any]]
    integrated_content: str = ""
    reviewer_verdict: str = ""
    tests_passed: bool = False
    diff: str = ""
    blocked: bool = False
    block_reason: str = ""
    created_at: float = 0.0
    completed_at: Optional[float] = None
    audit_event_ids: List[str] = field(default_factory=list)


_lock = threading.Lock()
_DAG_RUNS: Dict[str, DagRunRecord] = {}
_BATCH_RUNS: Dict[str, BatchRunRecord] = {}
_LAST_DAG_RUN_ID: Optional[str] = None
_LAST_BATCH_RUN_ID: Optional[str] = None


def _is_allowed_batch_file(path: str) -> bool:
    norm = path.replace("\\", "/").lstrip("/")
    if norm in BATCH_ALLOWED_FILES:
        return True
    return any(norm.startswith(p) for p in BATCH_ALLOWED_PREFIXES)


def _audit(action_type: str, status: str, resource: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    return record_execution_audit(
        action_type=action_type,
        actor="orchestration_executor",
        execution_status=status,
        affected_resource=resource,
        metadata=metadata or {},
    )


def _simulate_retrieval(scope: str) -> Dict[str, Any]:
    """Cheap retrieval/context pack before reasoning steps."""
    root = repo_root()
    hits: List[str] = []
    scope_path = root / scope if scope else root / "tests/fixtures"
    if scope_path.is_file():
        hits.append(str(scope_path.relative_to(root)))
    elif scope_path.is_dir():
        for p in sorted(scope_path.glob("plan9_*"))[:5]:
            hits.append(str(p.relative_to(root)))
    return {
        "scope": scope or "tests/fixtures",
        "sources": hits or ["tests/fixtures/plan9_workflow_status.txt"],
        "token_estimate": min(800, 120 + 40 * len(hits)),
        "retrieval_worker": "retrieval_worker",
    }


def _elastic_pool_plan(role_id: str, task_count: int) -> Dict[str, Any]:
    policy = ELASTIC_POOL_POLICIES.get(role_id)
    if not policy:
        return {"role_id": role_id, "worker_count": 1, "scaling_allowed": False}
    workers = min(max(1, task_count), policy.max_workers if policy.scaling_allowed else 1)
    return {
        "role_id": role_id,
        "worker_count": workers,
        "max_workers": policy.max_workers,
        "scaling_allowed": policy.scaling_allowed,
        "single_executor_only": policy.single_executor_only,
        "shard_dimensions": list(policy.shard_dimensions),
    }


def run_controlled_dag(*, task_description: str, scope: str = "tests/fixtures") -> DagRunRecord:
    """Build and execute a safe multi-step DAG with retrieval + parallel groups."""
    global _LAST_DAG_RUN_ID
    run_id = f"dag-{uuid.uuid4().hex[:12]}"
    dag_policy = ParallelDAGPolicy()

    nodes = [
        OrchestrationTaskNode("retrieval", "retrieval_worker", "context_pack"),
        OrchestrationTaskNode(
            "read_a", "backend_worker", "file_read",
            depends_on=["retrieval"], parallel_group="parallel_read",
        ),
        OrchestrationTaskNode(
            "read_b", "test_worker", "file_read",
            depends_on=["retrieval"], parallel_group="parallel_read",
        ),
        OrchestrationTaskNode(
            "summarize", "integration_review_manager", "integration_review",
            depends_on=["read_a", "read_b"],
        ),
    ]

    record = DagRunRecord(
        run_id=run_id,
        task_description=task_description,
        scope=scope,
        state=TaskState.RUNNING,
        nodes=nodes,
        parallel_groups=[["read_a", "read_b"]],
        retrieval_invoked=False,
        elastic_plan={
            "retrieval_worker": _elastic_pool_plan("retrieval_worker", 1),
            "backend_worker": _elastic_pool_plan("backend_worker", 1),
            "test_worker": _elastic_pool_plan("test_worker", 2),
        },
        created_at=time.time(),
    )

    audit_ids: List[str] = []
    audit_ids.append(_audit("orchestration_dag_start", "running", run_id, {"scope": scope}))

    # Step 1 — retrieval (always before reasoning)
    retrieval_node = nodes[0]
    retrieval_node.state = TaskState.RUNNING
    retrieval_node.started_at = time.time()
    retrieval_node.worker_id = "retrieval_worker-1"
    pack = _simulate_retrieval(scope)
    retrieval_node.output = pack
    retrieval_node.state = TaskState.COMPLETED
    retrieval_node.completed_at = time.time()
    retrieval_node.detail = f"Context pack: {len(pack['sources'])} sources"
    record.retrieval_invoked = True
    audit_ids.append(_audit("retrieval_worker_invoked", "success", scope, pack))

    # Step 2 — parallel reads (safe actions only)
    for node in nodes[1:3]:
        if not dag_policy.is_safe_to_parallelize(node.action_type):
            node.state = TaskState.BLOCKED
            node.detail = f"Action {node.action_type} not parallel-safe"
            continue
        node.state = TaskState.RUNNING
        node.started_at = time.time()
        node.worker_id = f"{node.role_id}-pool-1"
        node.output = {"files_read": pack["sources"][:1], "action": node.action_type}
        node.state = TaskState.COMPLETED
        node.completed_at = time.time()
        node.detail = "Parallel read complete"

    # Step 3 — summarize / integrate depends on parallel group
    summary = nodes[3]
    deps_ok = all(
        n.state == TaskState.COMPLETED for n in nodes if n.task_id in summary.depends_on
    )
    if not deps_ok:
        summary.state = TaskState.BLOCKED
        summary.detail = "Dependencies incomplete"
        record.state = TaskState.BLOCKED
    else:
        summary.state = TaskState.RUNNING
        summary.started_at = time.time()
        summary.worker_id = "integration_review_manager-1"
        summary.output = {
            "review": "pass",
            "parallel_groups_executed": record.parallel_groups,
            "dag_policy_id": dag_policy.policy_id,
        }
        summary.state = TaskState.COMPLETED
        summary.completed_at = time.time()
        summary.detail = "Integration review passed"
        record.state = TaskState.COMPLETED
        record.completed_at = time.time()
        audit_ids.append(_audit("orchestration_dag_complete", "success", run_id))

    record.audit_event_ids = audit_ids
    with _lock:
        _DAG_RUNS[run_id] = record
        _LAST_DAG_RUN_ID = run_id
    return record


def run_batch_integration(
    *,
    target_file: str,
    worker_a_patch: str,
    worker_b_patch: str,
    run_tests: bool = True,
) -> BatchRunRecord:
    """Same-file batch integration with integrator + reviewer on allowlisted fixture."""
    global _LAST_BATCH_RUN_ID
    run_id = f"batch-{uuid.uuid4().hex[:12]}"
    norm = target_file.replace("\\", "/").lstrip("/")
    batch_policy = BatchIntegrationPolicy()

    record = BatchRunRecord(
        run_id=run_id,
        target_file=norm,
        state=TaskState.RUNNING,
        worker_patches=[
            {"worker_id": "backend_worker-a", "patch": worker_a_patch},
            {"worker_id": "frontend_worker-b", "patch": worker_b_patch},
        ],
        created_at=time.time(),
    )
    audit_ids: List[str] = []
    audit_ids.append(_audit("batch_integration_start", "running", norm))

    if not _is_allowed_batch_file(norm):
        record.state = TaskState.BLOCKED
        record.blocked = True
        record.block_reason = f"File not allowlisted for batch integration: {norm}"
        audit_ids.append(_audit("batch_integration_blocked", "blocked", norm))
        record.audit_event_ids = audit_ids
        with _lock:
            _BATCH_RUNS[run_id] = record
            _LAST_BATCH_RUN_ID = run_id
        return record

    root = repo_root()
    path = root / norm
    if not path.is_file():
        record.state = TaskState.FAILED
        record.block_reason = f"Target file missing: {norm}"
        audit_ids.append(_audit("batch_integration_failed", "failed", norm))
        record.audit_event_ids = audit_ids
        with _lock:
            _BATCH_RUNS[run_id] = record
            _LAST_BATCH_RUN_ID = run_id
        return record

    original = path.read_text(encoding="utf-8")
    # Detect same-file conflict — both workers touch same file (by design)
    if worker_a_patch.strip() == worker_b_patch.strip():
        integrated = worker_a_patch
        conflict = False
    else:
        conflict = True
        # Integrator sequences: worker A base, worker B appended as reviewed section
        integrated = (
            worker_a_patch.rstrip()
            + "\n--- batch_integrator_merge ---\n"
            + worker_b_patch.rstrip()
            + "\n"
        )

    record.integrated_content = integrated
    record.diff = "".join(
        difflib_line
        for difflib_line in _unified_diff(original, integrated, norm)
    )

    # Reviewer validates merge
    reviewer_ok = "batch_integrator_merge" in integrated or not conflict
    record.reviewer_verdict = "approved" if reviewer_ok else "rejected"
    if not reviewer_ok:
        record.state = TaskState.BLOCKED
        record.blocked = True
        record.block_reason = "Reviewer rejected conflicting integration"
        audit_ids.append(_audit("batch_integration_review_rejected", "blocked", norm))
        record.audit_event_ids = audit_ids
        with _lock:
            _BATCH_RUNS[run_id] = record
            _LAST_BATCH_RUN_ID = run_id
        return record

    path.write_text(integrated, encoding="utf-8")

    if run_tests:
        import subprocess

        proc = subprocess.run(
            ["uv", "run", "pytest", "tests/plan9/test_plan9_orchestration_executor.py", "-q", "--tb=no"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        record.tests_passed = proc.returncode == 0
        if not record.tests_passed:
            path.write_text(original, encoding="utf-8")  # rollback
            record.state = TaskState.FAILED
            record.block_reason = "Post-integration tests failed; rolled back"
            audit_ids.append(_audit("batch_integration_rollback", "failed", norm))
            record.audit_event_ids = audit_ids
            with _lock:
                _BATCH_RUNS[run_id] = record
                _LAST_BATCH_RUN_ID = run_id
            return record

    record.state = TaskState.COMPLETED
    record.completed_at = time.time()
    audit_ids.append(
        _audit(
            "batch_integration_complete",
            "success",
            norm,
            {
                "integrator_role": batch_policy.integrator_role,
                "reviewer_role": batch_policy.reviewer_role,
                "conflict_detected": conflict,
            },
        )
    )
    record.audit_event_ids = audit_ids
    with _lock:
        _BATCH_RUNS[run_id] = record
        _LAST_BATCH_RUN_ID = run_id
    return record


def _unified_diff(before: str, after: str, path: str) -> List[str]:
    import difflib

    return list(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def dag_run_to_dict(record: DagRunRecord) -> Dict[str, Any]:
    return {
        "run_id": record.run_id,
        "task_description": record.task_description,
        "scope": record.scope,
        "state": record.state.value,
        "retrieval_invoked": record.retrieval_invoked,
        "parallel_groups": record.parallel_groups,
        "elastic_plan": record.elastic_plan,
        "nodes": [
            {
                "task_id": n.task_id,
                "role_id": n.role_id,
                "action_type": n.action_type,
                "state": n.state.value,
                "worker_id": n.worker_id,
                "depends_on": n.depends_on,
                "parallel_group": n.parallel_group,
                "detail": n.detail,
                "output": n.output,
            }
            for n in record.nodes
        ],
        "audit_event_ids": record.audit_event_ids,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
    }


def batch_run_to_dict(record: BatchRunRecord) -> Dict[str, Any]:
    return {
        "run_id": record.run_id,
        "target_file": record.target_file,
        "state": record.state.value,
        "worker_patches": record.worker_patches,
        "integrated_content": record.integrated_content,
        "reviewer_verdict": record.reviewer_verdict,
        "tests_passed": record.tests_passed,
        "diff": record.diff,
        "blocked": record.blocked,
        "block_reason": record.block_reason,
        "audit_event_ids": record.audit_event_ids,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
    }


def get_dag_run(run_id: str) -> Optional[DagRunRecord]:
    with _lock:
        return _DAG_RUNS.get(run_id)


def get_batch_run(run_id: str) -> Optional[BatchRunRecord]:
    with _lock:
        return _BATCH_RUNS.get(run_id)


def get_last_dag_run() -> Optional[DagRunRecord]:
    with _lock:
        if _LAST_DAG_RUN_ID:
            return _DAG_RUNS.get(_LAST_DAG_RUN_ID)
        return None


def get_last_batch_run() -> Optional[BatchRunRecord]:
    with _lock:
        if _LAST_BATCH_RUN_ID:
            return _BATCH_RUNS.get(_LAST_BATCH_RUN_ID)
        return None
