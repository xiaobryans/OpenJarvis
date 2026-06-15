"""MissionRunner — real execution loop for mission tasks.

Responsibilities:
- Load queued/assigned tasks for a mission.
- Respect task dependencies and approval gates.
- Execute runnable tasks via registered AgentExecutors.
- Persist all status changes to MissionStore.
- Emit MissionEvents for every lifecycle transition.
- Update mission status based on task outcomes.

Safety rules (non-negotiable):
- Tasks are never marked completed unless an executor returned TaskStatus.COMPLETED
  with a real non-empty output.
- Approval-required tasks are never auto-executed.
- Max-steps guard prevents runaway loops.
- No task that is already running/completed/cancelled/failed is re-executed.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.core.events import EventType, get_event_bus
from openjarvis.mission.executor import ExecutionResult, ExecutorRegistry
from openjarvis.mission.models import (
    Mission,
    MissionEvent,
    MissionStatus,
    Task,
    TaskStatus,
)
from openjarvis.mission.notifier import SlackNotifier, TelegramNotifier
from openjarvis.mission.store import MissionStore

logger = logging.getLogger(__name__)

_RUNNABLE_STATUSES = frozenset({TaskStatus.ASSIGNED, TaskStatus.PENDING})
_TERMINAL_STATUSES = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.BLOCKED,
})
_DEFAULT_MAX_STEPS = 20


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """Summary of one mission runner pass."""

    mission_id: str
    status: str
    tasks_started: int = 0
    tasks_completed: int = 0
    tasks_blocked: int = 0
    tasks_failed: int = 0
    approvals_required: int = 0
    events_emitted: int = 0
    no_progress: bool = False
    no_progress_reason: str = ""
    ok: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "status": self.status,
            "tasks_started": self.tasks_started,
            "tasks_completed": self.tasks_completed,
            "tasks_blocked": self.tasks_blocked,
            "tasks_failed": self.tasks_failed,
            "approvals_required": self.approvals_required,
            "events_emitted": self.events_emitted,
            "no_progress": self.no_progress,
            "no_progress_reason": self.no_progress_reason,
            "ok": self.ok,
        }


# ---------------------------------------------------------------------------
# MissionRunner
# ---------------------------------------------------------------------------


class MissionRunner:
    """Executes one controlled pass of runnable tasks for a mission.

    One "pass" iterates through all tasks, executing each runnable task
    exactly once, up to max_steps.  Call run_mission_pass() again to
    continue execution after resolving approvals/blockers.
    """

    def __init__(
        self,
        store: Optional[MissionStore] = None,
        *,
        emit_to_bus: bool = True,
    ) -> None:
        self._store = store or MissionStore()
        self._emit_to_bus = emit_to_bus

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def start_task(self, task_id: str) -> Optional[Task]:
        """Transition task to RUNNING and emit task_started event.

        Returns updated task or None if not found.
        """
        task = self._store.get_task(task_id)
        if task is None:
            return None
        task.status = TaskStatus.RUNNING
        task.updated_at = time.time()
        self._store.save_task(task)
        self._emit_event(
            EventType.TASK_STARTED,
            mission_id=task.mission_id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            message=f"Task started: {task.title}",
            payload={"agent_id": task.assigned_agent_id},
        )
        return task

    def complete_task(self, task_id: str, result: ExecutionResult) -> Optional[Task]:
        """Persist a completed result and emit task_completed."""
        task = self._store.get_task(task_id)
        if task is None:
            return None
        task.status = TaskStatus.COMPLETED
        task.result = result.output
        task.summary = result.summary
        task.updated_at = time.time()
        self._store.save_task(task)
        self._emit_event(
            EventType.TASK_COMPLETED,
            mission_id=task.mission_id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            message=f"Task completed: {task.title}",
            payload={
                "summary": result.summary,
                "artifact_metadata": result.artifact_metadata,
            },
        )
        return task

    def block_task(self, task_id: str, reason: str, result: Optional[ExecutionResult] = None) -> Optional[Task]:
        """Persist blocked status and emit task_blocked."""
        task = self._store.get_task(task_id)
        if task is None:
            return None
        task.status = TaskStatus.BLOCKED
        task.result = reason
        task.summary = result.summary if result else reason
        task.updated_at = time.time()
        self._store.save_task(task)
        self._emit_event(
            EventType.TASK_BLOCKED,
            mission_id=task.mission_id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            severity="warning",
            message=f"Task blocked: {task.title} — {reason}",
            payload={"blocked_reason": reason},
        )
        return task

    def fail_task(self, task_id: str, error: str) -> Optional[Task]:
        """Persist failed status and emit task_failed."""
        task = self._store.get_task(task_id)
        if task is None:
            return None
        task.status = TaskStatus.FAILED
        task.result = error
        task.updated_at = time.time()
        self._store.save_task(task)
        self._emit_event(
            EventType.TASK_FAILED,
            mission_id=task.mission_id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            severity="error",
            message=f"Task failed: {task.title} — {error}",
            payload={"error": error},
        )
        return task

    def require_approval(self, task_id: str, reason: str, result: Optional[ExecutionResult] = None) -> Optional[Task]:
        """Set task to awaiting_approval and emit the event."""
        task = self._store.get_task(task_id)
        if task is None:
            return None
        task.status = TaskStatus.AWAITING_APPROVAL
        task.summary = result.summary if result else reason
        task.updated_at = time.time()
        self._store.save_task(task)
        self._emit_event(
            EventType.TASK_AWAITING_APPROVAL,
            mission_id=task.mission_id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            severity="warning",
            message=f"Task requires approval: {task.title} — {reason}",
            payload={"reason": reason, "requires_approval": True},
        )
        return task

    # ------------------------------------------------------------------
    # Run a single task directly
    # ------------------------------------------------------------------

    def execute_task(self, task_id: str) -> Optional[ExecutionResult]:
        """Execute a single task if it is in a runnable state.

        Returns the ExecutionResult or None if the task cannot be run.
        """
        task = self._store.get_task(task_id)
        if task is None:
            return None

        if task.status not in _RUNNABLE_STATUSES:
            return ExecutionResult(
                task_id=task_id,
                agent_id=task.assigned_agent_id,
                status=task.status,
                summary=f"Task is not in a runnable state (current: {task.status.value})",
                blocked_reason=f"task status is {task.status.value}, not assigned/pending",
            )

        return self._run_one_task(task)

    # ------------------------------------------------------------------
    # Mission run pass
    # ------------------------------------------------------------------

    def run_mission_pass(
        self,
        mission_id: str,
        *,
        max_steps: int = _DEFAULT_MAX_STEPS,
    ) -> RunResult:
        """Execute one controlled pass for the mission.

        Iterates runnable tasks in priority order, executes each via its
        executor, persists results, and emits events.  Respects
        dependencies and approval gates.  Does not loop infinitely.
        """
        effective_max = max(1, min(max_steps, 100))

        mission = self._store.get_mission(mission_id)
        if mission is None:
            return RunResult(
                mission_id=mission_id,
                status="not_found",
                ok=False,
                no_progress=True,
                no_progress_reason="Mission not found",
            )

        # Emit runner started
        self._emit_event(
            EventType.MISSION_RUNNER_STARTED,
            mission_id=mission_id,
            message=f"Mission runner started for: {mission.title}",
            payload={"max_steps": effective_max},
        )
        events_emitted = 1

        tasks = self._store.list_tasks(mission_id)

        # Identify completed task ids for dependency resolution
        completed_ids = {t.id for t in tasks if t.status == TaskStatus.COMPLETED}

        result = RunResult(mission_id=mission_id, status=mission.status.value)
        steps_used = 0

        for task in tasks:
            if steps_used >= effective_max:
                break

            # Skip non-runnable states
            if task.status not in _RUNNABLE_STATUSES:
                if task.status == TaskStatus.AWAITING_APPROVAL:
                    result.approvals_required += 1
                continue

            # Respect dependencies — skip if any dependency not yet completed
            if task.dependencies:
                unmet = [dep for dep in task.dependencies if dep not in completed_ids]
                if unmet:
                    logger.debug("Task %s waiting on deps: %s", task.id, unmet)
                    continue

            # Execute
            exec_result = self._run_one_task(task)
            steps_used += 1
            events_emitted += 2  # start + outcome

            if exec_result.status == TaskStatus.COMPLETED:
                completed_ids.add(task.id)
                result.tasks_completed += 1
            elif exec_result.status == TaskStatus.BLOCKED:
                result.tasks_blocked += 1
            elif exec_result.status == TaskStatus.FAILED:
                result.tasks_failed += 1
            elif exec_result.status == TaskStatus.AWAITING_APPROVAL:
                result.approvals_required += 1

            result.tasks_started += 1

        # Recompute mission status from final task states
        all_tasks = self._store.list_tasks(mission_id)
        new_status = self._compute_mission_status(all_tasks)
        if new_status != mission.status:
            self._store.update_mission_status(mission_id, new_status)
            self._emit_event(
                EventType.MISSION_STATUS_CHANGED,
                mission_id=mission_id,
                message=f"Mission status → {new_status.value}",
                payload={"status": new_status.value, "previous": mission.status.value},
            )
            events_emitted += 1

        result.status = new_status.value
        result.events_emitted = events_emitted

        if result.tasks_started == 0:
            result.no_progress = True
            if result.approvals_required > 0:
                result.no_progress_reason = (
                    f"{result.approvals_required} task(s) awaiting approval; "
                    "approve via /v1/tasks/{id}/approve before re-running"
                )
            elif new_status == MissionStatus.BLOCKED:
                result.no_progress_reason = (
                    "All runnable tasks are blocked — check blocked_reason on each task"
                )
            elif new_status == MissionStatus.COMPLETED:
                result.no_progress_reason = "Mission already completed"
            else:
                result.no_progress_reason = "No runnable tasks found for this mission"
            result.ok = False
        else:
            result.ok = True

        # Optional auto-notify
        self._maybe_auto_notify(mission_id, result)

        return result

    # ------------------------------------------------------------------
    # Run-state query
    # ------------------------------------------------------------------

    def get_run_state(self, mission_id: str) -> Dict[str, Any]:
        """Return current task counts, blocked reasons, approvals, and last events."""
        mission = self._store.get_mission(mission_id)
        if mission is None:
            return {"error": "Mission not found", "mission_id": mission_id}

        tasks = self._store.list_tasks(mission_id)
        counts: Dict[str, int] = {}
        blocked_reasons: List[Dict[str, str]] = []
        approval_tasks: List[Dict[str, str]] = []

        for t in tasks:
            counts[t.status.value] = counts.get(t.status.value, 0) + 1
            if t.status == TaskStatus.BLOCKED and t.result:
                blocked_reasons.append({"task_id": t.id, "title": t.title, "reason": t.result})
            if t.status == TaskStatus.AWAITING_APPROVAL:
                approval_tasks.append({"task_id": t.id, "title": t.title, "agent_id": t.assigned_agent_id})

        events = self._store.list_events(mission_id, limit=10)
        last_events = [e.to_dict() for e in reversed(events[-10:])]

        return {
            "mission_id": mission_id,
            "mission_status": mission.status.value,
            "task_counts": counts,
            "blocked_reasons": blocked_reasons,
            "approvals_required": approval_tasks,
            "last_events": last_events,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_one_task(self, task: Task) -> ExecutionResult:
        """Start → execute → persist result for a single task."""
        # Mark running
        self.start_task(task.id)

        executor = ExecutorRegistry.get(task.assigned_agent_id)
        if executor is None:
            return self._persist_result(
                task,
                ExecutionResult(
                    task_id=task.id,
                    agent_id=task.assigned_agent_id,
                    status=TaskStatus.BLOCKED,
                    summary=f"No executor registered for agent '{task.assigned_agent_id}'",
                    blocked_reason=(
                        f"No executor found for agent_id='{task.assigned_agent_id}'. "
                        "Register an executor in ExecutorRegistry to unblock."
                    ),
                ),
            )

        try:
            exec_result = executor.execute(task)
        except Exception as exc:
            logger.warning("Executor %s raised: %s", task.assigned_agent_id, exc)
            exec_result = ExecutionResult(
                task_id=task.id,
                agent_id=task.assigned_agent_id,
                status=TaskStatus.FAILED,
                error=str(exc),
                summary=f"Executor raised unexpected exception: {type(exc).__name__}",
            )

        return self._persist_result(task, exec_result)

    def _persist_result(self, task: Task, result: ExecutionResult) -> ExecutionResult:
        """Persist the execution result using the appropriate lifecycle method."""
        if result.status == TaskStatus.COMPLETED:
            if not result.output:
                # Refuse to mark completed with no real output
                result.status = TaskStatus.BLOCKED
                result.blocked_reason = (
                    "Executor returned COMPLETED but produced no output — "
                    "refusing to mark completed (no fake work)"
                )
                self.block_task(task.id, result.blocked_reason, result)
            else:
                self.complete_task(task.id, result)
        elif result.status == TaskStatus.BLOCKED:
            self.block_task(task.id, result.blocked_reason or "unknown reason", result)
        elif result.status == TaskStatus.FAILED:
            self.fail_task(task.id, result.error or "unknown error")
        elif result.status == TaskStatus.AWAITING_APPROVAL:
            self.require_approval(task.id, result.blocked_reason or "approval required", result)
        else:
            # Unexpected status — mark blocked
            self.block_task(task.id, f"Unexpected executor status: {result.status.value}", result)

        return result

    def _compute_mission_status(self, tasks: List[Task]) -> MissionStatus:
        """Derive mission status from the current task states."""
        if not tasks:
            return MissionStatus.RUNNING

        statuses = [t.status for t in tasks]

        all_done = all(s in _TERMINAL_STATUSES for s in statuses)
        has_failed = any(s == TaskStatus.FAILED for s in statuses)
        has_approval = any(s == TaskStatus.AWAITING_APPROVAL for s in statuses)
        has_blocked = any(s == TaskStatus.BLOCKED for s in statuses)
        has_running_or_assigned = any(s in _RUNNABLE_STATUSES or s == TaskStatus.RUNNING for s in statuses)
        has_completed = any(s == TaskStatus.COMPLETED for s in statuses)
        all_completed_or_cancelled = all(
            s in (TaskStatus.COMPLETED, TaskStatus.CANCELLED) for s in statuses
        )

        if all_completed_or_cancelled:
            return MissionStatus.COMPLETED
        if has_failed and not has_running_or_assigned and not has_approval:
            return MissionStatus.FAILED
        if has_approval and not has_running_or_assigned:
            return MissionStatus.AWAITING_APPROVAL
        if has_blocked and not has_running_or_assigned and not has_approval:
            return MissionStatus.BLOCKED
        if has_running_or_assigned or has_completed:
            return MissionStatus.RUNNING

        return MissionStatus.BLOCKED

    def _emit_event(
        self,
        event_type: EventType,
        *,
        mission_id: str,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        severity: str = "info",
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> MissionEvent:
        evt = MissionEvent(
            mission_id=mission_id,
            task_id=task_id,
            agent_id=agent_id,
            event_type=event_type.value,
            severity=severity,
            message=message,
            payload=payload or {},
        )
        self._store.save_event(evt)
        if self._emit_to_bus:
            try:
                bus = get_event_bus()
                bus.publish(
                    event_type,
                    data={
                        "mission_id": mission_id,
                        "task_id": task_id,
                        "agent_id": agent_id,
                        "message": message,
                    },
                )
            except Exception as exc:
                logger.debug("Event bus publish skipped: %s", exc)
        return evt

    def _maybe_auto_notify(self, mission_id: str, result: RunResult) -> None:
        """Send auto-notifications only if env flag is set and event is important."""
        slack_auto = os.environ.get("JARVIS_SLACK_MISSION_AUTONOTIFY", "").strip().lower() == "true"
        tg_auto = os.environ.get("JARVIS_TELEGRAM_MISSION_AUTONOTIFY", "").strip().lower() == "true"

        if not slack_auto and not tg_auto:
            return

        # Only notify on major state transitions (not every run)
        important_statuses = {"completed", "failed", "blocked", "awaiting_approval"}
        if result.status not in important_statuses and not result.no_progress:
            return

        mission = self._store.get_mission(mission_id)
        msg = _build_mission_notify_message(mission, result)

        if slack_auto:
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(SlackNotifier().send(msg))
            except Exception as exc:
                logger.debug("Slack auto-notify skipped: %s", exc)

        if tg_auto:
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(TelegramNotifier().send(msg))
            except Exception as exc:
                logger.debug("Telegram auto-notify skipped: %s", exc)


# ---------------------------------------------------------------------------
# Shared message builder (used by runner auto-notify AND route explicit notify)
# ---------------------------------------------------------------------------


def _build_mission_notify_message(
    mission: Optional[Mission],
    result: Optional[RunResult] = None,
    *,
    tasks: Optional[List[Task]] = None,
) -> str:
    """Build a human-readable mission notification message.

    Never includes secret values.
    """
    if mission is None:
        return "[Jarvis] Mission not found"

    lines = [
        f"[Jarvis Mission Control]",
        f"Mission: {mission.title or mission.objective}",
        f"ID: {mission.id}",
        f"Status: {mission.status.value}",
        f"Risk: {mission.risk_level.value}",
    ]

    if result is not None:
        lines += [
            f"Tasks started: {result.tasks_started}",
            f"Tasks completed: {result.tasks_completed}",
            f"Tasks blocked: {result.tasks_blocked}",
            f"Tasks failed: {result.tasks_failed}",
            f"Approvals required: {result.approvals_required}",
        ]
        if result.no_progress and result.no_progress_reason:
            lines.append(f"No progress: {result.no_progress_reason}")

    if tasks is not None:
        blocked = [t for t in tasks if t.status.value == "blocked"]
        approval = [t for t in tasks if t.status.value == "awaiting_approval"]
        if blocked:
            lines.append(f"Blocked tasks: {', '.join(t.title for t in blocked)}")
        if approval:
            lines.append(f"Awaiting approval: {', '.join(t.title for t in approval)}")

    return "\n".join(lines)


__all__ = [
    "MissionRunner",
    "RunResult",
    "_build_mission_notify_message",
]
