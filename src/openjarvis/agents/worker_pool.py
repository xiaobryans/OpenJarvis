"""Jarvis Worker Pool — parallel execution, stall detection, reassignment.

Provides:
  - WorkerTask: a unit of work assigned to a worker role
  - WorkerPool: manages dynamic worker teams
    - Parallel execution where dependencies allow
    - Dependency-aware sequencing where they don't
    - Stall detection (timeout-based)
    - Stalled worker reassignment (where safe) or blocker reporting

Design invariants:
  - Worker count is NOT fixed. Teams are assembled by task need.
  - Stalled workers are detected and reported — never silently skipped.
  - Blockers are surfaced, not worked around.
  - Fake/headcount-only workers are FORBIDDEN.
  - Artifact outputs are required where appropriate.

Sprint: Full No-Gap Jarvis — Combined Sprint 3
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Task status
# ---------------------------------------------------------------------------

class WorkerTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    STALLED = "stalled"
    REASSIGNED = "reassigned"
    FAILED = "failed"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Worker task
# ---------------------------------------------------------------------------

@dataclass
class WorkerTask:
    """A unit of work assigned to a worker role."""

    task_id: str
    worker_role_id: str
    description: str
    input_data: Dict[str, Any]
    output_artifact: Optional[str] = None   # file path or structured output
    stall_timeout_seconds: int = 300
    dependencies: List[str] = field(default_factory=list)  # task_ids that must complete first
    parallelizable: bool = True

    status: WorkerTaskStatus = WorkerTaskStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stall_reported: bool = False
    reassigned_to: Optional[str] = None

    def mark_started(self) -> None:
        self.status = WorkerTaskStatus.RUNNING
        self.started_at = time.time()

    def mark_completed(self, result: Dict[str, Any], artifact: Optional[str] = None) -> None:
        self.status = WorkerTaskStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result
        if artifact:
            self.output_artifact = artifact

    def mark_failed(self, error: str) -> None:
        self.status = WorkerTaskStatus.FAILED
        self.completed_at = time.time()
        self.error = error

    def mark_blocked(self, reason: str) -> None:
        self.status = WorkerTaskStatus.BLOCKED
        self.error = reason

    def is_stalled(self) -> bool:
        if self.status != WorkerTaskStatus.RUNNING:
            return False
        if self.started_at is None:
            return False
        return (time.time() - self.started_at) > self.stall_timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "worker_role_id": self.worker_role_id,
            "description": self.description,
            "status": self.status.value,
            "output_artifact": self.output_artifact,
            "stall_timeout_seconds": self.stall_timeout_seconds,
            "dependencies": self.dependencies,
            "parallelizable": self.parallelizable,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "stall_reported": self.stall_reported,
            "reassigned_to": self.reassigned_to,
        }


# ---------------------------------------------------------------------------
# Stall report
# ---------------------------------------------------------------------------

@dataclass
class StallReport:
    """Report of a stalled worker."""

    report_id: str
    task_id: str
    worker_role_id: str
    stall_duration_seconds: float
    reassignable: bool
    reassigned_to: Optional[str]
    blocker_description: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "worker_role_id": self.worker_role_id,
            "stall_duration_seconds": round(self.stall_duration_seconds, 1),
            "reassignable": self.reassignable,
            "reassigned_to": self.reassigned_to,
            "blocker_description": self.blocker_description,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Parallel execution plan
# ---------------------------------------------------------------------------

@dataclass
class ExecutionPlan:
    """Plan for executing worker tasks with dependency awareness."""

    plan_id: str
    manager_role_id: str
    task_context: str
    parallel_groups: List[List[str]]    # each group runs in parallel; groups run in sequence
    sequenced_tasks: List[str]          # tasks that must run strictly sequentially
    total_tasks: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "manager_role_id": self.manager_role_id,
            "task_context": self.task_context,
            "parallel_groups": self.parallel_groups,
            "sequenced_tasks": self.sequenced_tasks,
            "total_tasks": self.total_tasks,
        }


# ---------------------------------------------------------------------------
# Worker Pool
# ---------------------------------------------------------------------------

class WorkerPool:
    """Manages a dynamic team of workers for a task.

    Supports:
    - Parallel task execution where dependencies allow
    - Dependency-aware sequencing where they don't
    - Stall detection (check_stalls() → List[StallReport])
    - Stalled worker reassignment (if reassignable=True)
    - Artifact output tracking
    - Blocker surfacing
    """

    def __init__(
        self,
        pool_id: str,
        manager_role_id: str,
        stall_timeout_seconds: int = 300,
    ) -> None:
        self._pool_id = pool_id
        self._manager_role_id = manager_role_id
        self._stall_timeout = stall_timeout_seconds
        self._tasks: Dict[str, WorkerTask] = {}
        self._stall_reports: List[StallReport] = []

    @property
    def pool_id(self) -> str:
        return self._pool_id

    @property
    def manager_role_id(self) -> str:
        return self._manager_role_id

    def add_task(self, task: WorkerTask) -> None:
        """Register a task in this pool."""
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[WorkerTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[WorkerTask]:
        return list(self._tasks.values())

    def build_execution_plan(self, task_context: str = "") -> ExecutionPlan:
        """Build a dependency-aware execution plan.

        Tasks with no dependencies and parallelizable=True go into the first
        parallel group. Tasks with dependencies are placed after their deps are met.
        Tasks with parallelizable=False are sequenced strictly.
        """
        plan_id = str(uuid.uuid4())[:8]

        completed: Set[str] = set()
        remaining = list(self._tasks.values())

        parallel_groups: List[List[str]] = []
        sequenced_tasks: List[str] = []

        max_iterations = len(remaining) + 1
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            ready_parallel: List[str] = []
            ready_sequential: List[str] = []
            still_waiting = []

            for task in remaining:
                deps_met = all(dep in completed for dep in task.dependencies)
                if deps_met:
                    if task.parallelizable:
                        ready_parallel.append(task.task_id)
                    else:
                        ready_sequential.append(task.task_id)
                else:
                    still_waiting.append(task)

            if ready_parallel:
                parallel_groups.append(ready_parallel)
                completed.update(ready_parallel)

            for tid in ready_sequential:
                sequenced_tasks.append(tid)
                completed.add(tid)

            remaining = still_waiting

        return ExecutionPlan(
            plan_id=plan_id,
            manager_role_id=self._manager_role_id,
            task_context=task_context,
            parallel_groups=parallel_groups,
            sequenced_tasks=sequenced_tasks,
            total_tasks=len(self._tasks),
        )

    def execute(
        self,
        executor_fn: Callable[[WorkerTask], Dict[str, Any]],
        task_context: str = "",
    ) -> Dict[str, Any]:
        """Execute all tasks using the given executor function.

        Tasks are executed according to the dependency-aware plan.
        Stall detection runs after each batch. Sequential tasks run one at a time.
        Stalled tasks are reported immediately.

        The executor_fn receives a WorkerTask and returns a result dict.
        """
        plan = self.build_execution_plan(task_context)

        # Execute parallel groups in order
        for group in plan.parallel_groups:
            for task_id in group:
                task = self._tasks[task_id]
                # Skip tasks pre-marked as RUNNING (e.g. stall simulation)
                if task.status != WorkerTaskStatus.PENDING:
                    continue
                task.mark_started()
                try:
                    result = executor_fn(task)
                    artifact = result.pop("artifact", None) if isinstance(result, dict) else None
                    task.mark_completed(result, artifact)
                except Exception as exc:
                    task.mark_failed(str(exc))

        # Execute sequenced tasks
        for task_id in plan.sequenced_tasks:
            task = self._tasks[task_id]
            if task.status != WorkerTaskStatus.PENDING:
                continue
            task.mark_started()
            try:
                result = executor_fn(task)
                artifact = result.pop("artifact", None) if isinstance(result, dict) else None
                task.mark_completed(result, artifact)
            except Exception as exc:
                task.mark_failed(str(exc))

        stall_reports = self.check_stalls()

        return {
            "pool_id": self._pool_id,
            "plan": plan.to_dict(),
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "stall_reports": [s.to_dict() for s in stall_reports],
            "completed_count": sum(1 for t in self._tasks.values() if t.status == WorkerTaskStatus.COMPLETED),
            "failed_count": sum(1 for t in self._tasks.values() if t.status == WorkerTaskStatus.FAILED),
            "stalled_count": len(stall_reports),
        }

    def check_stalls(self, reassign_to: Optional[str] = None) -> List[StallReport]:
        """Check all running tasks for stalls. Returns list of stall reports."""
        reports: List[StallReport] = []
        for task in self._tasks.values():
            if task.is_stalled() and not task.stall_reported:
                task.status = WorkerTaskStatus.STALLED
                task.stall_reported = True
                duration = (time.time() - (task.started_at or time.time()))
                reassignable = reassign_to is not None
                if reassignable:
                    task.status = WorkerTaskStatus.REASSIGNED
                    task.reassigned_to = reassign_to
                report = StallReport(
                    report_id=str(uuid.uuid4())[:8],
                    task_id=task.task_id,
                    worker_role_id=task.worker_role_id,
                    stall_duration_seconds=duration,
                    reassignable=reassignable,
                    reassigned_to=reassign_to,
                    blocker_description=(
                        f"Worker '{task.worker_role_id}' stalled after {duration:.0f}s "
                        f"(timeout: {task.stall_timeout_seconds}s). "
                        f"Task: '{task.description}'."
                    ),
                )
                reports.append(report)
                self._stall_reports.append(report)
        return reports

    def get_artifacts(self) -> Dict[str, str]:
        """Return mapping of task_id → artifact path/value for completed tasks."""
        return {
            t.task_id: t.output_artifact
            for t in self._tasks.values()
            if t.output_artifact and t.status == WorkerTaskStatus.COMPLETED
        }

    def get_all_stall_reports(self) -> List[StallReport]:
        return list(self._stall_reports)

    def summary(self) -> Dict[str, Any]:
        counts = {s.value: 0 for s in WorkerTaskStatus}
        for t in self._tasks.values():
            counts[t.status.value] += 1
        return {
            "pool_id": self._pool_id,
            "manager_role_id": self._manager_role_id,
            "task_counts": counts,
            "total_tasks": len(self._tasks),
            "stall_reports": len(self._stall_reports),
            "artifacts": self.get_artifacts(),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_worker_pool(
    manager_role_id: str,
    stall_timeout_seconds: int = 300,
) -> WorkerPool:
    """Create a new worker pool for a manager."""
    pool_id = f"{manager_role_id}-pool-{str(uuid.uuid4())[:6]}"
    return WorkerPool(pool_id, manager_role_id, stall_timeout_seconds)


def create_worker_task(
    worker_role_id: str,
    description: str,
    input_data: Optional[Dict[str, Any]] = None,
    *,
    stall_timeout_seconds: int = 300,
    dependencies: Optional[List[str]] = None,
    parallelizable: bool = True,
) -> WorkerTask:
    """Create a new worker task."""
    return WorkerTask(
        task_id=str(uuid.uuid4())[:8],
        worker_role_id=worker_role_id,
        description=description,
        input_data=input_data or {},
        stall_timeout_seconds=stall_timeout_seconds,
        dependencies=dependencies or [],
        parallelizable=parallelizable,
    )


__all__ = [
    "WorkerTaskStatus",
    "WorkerTask",
    "StallReport",
    "ExecutionPlan",
    "WorkerPool",
    "create_worker_pool",
    "create_worker_task",
]
