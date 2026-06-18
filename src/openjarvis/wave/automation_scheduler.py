"""Epic B — Automation Scheduler Wiring (Wave 1).

Wires AutomationTrigger objects to the existing TaskScheduler.
Provides:
  - schedule_trigger()   — persists a trigger as a ScheduledTask
  - execute_safe_trigger() — immediately executes one safe local trigger action
  - list_scheduled_triggers() — list triggers registered with scheduler

No uncontrolled background autopilot.
External sends (Slack/email) are hard-blocked.
High/critical risk triggers require approval before scheduling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default local scheduler store path (Wave 1 local/founder only)
_DEFAULT_STORE_PATH = str(Path.home() / ".cache" / "openjarvis" / "wave1_scheduler.db")

# Safe local actions that can execute immediately without a live system/LLM
_SAFE_IMMEDIATE_ACTIONS: Dict[str, Any] = {
    "log_status": lambda ctx: {"action": "log_status", "timestamp": time.time(), "context": ctx},
    "check_capabilities": lambda ctx: _run_check_capabilities(),
    "check_platform": lambda ctx: _run_check_platform(),
    "list_skills": lambda ctx: _run_list_skills(),
}


def _run_check_capabilities() -> Dict[str, Any]:
    try:
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        return get_capabilities_summary()
    except Exception as exc:
        return {"error": str(exc)}


def _run_check_platform() -> Dict[str, Any]:
    try:
        from openjarvis.wave.platform_registry import get_wave_platform_summary
        return get_wave_platform_summary()
    except Exception as exc:
        return {"error": str(exc)}


def _run_list_skills() -> Dict[str, Any]:
    try:
        from openjarvis.wave.skill_platform import list_wave_skills
        skills = list_wave_skills()
        return {"skills": skills, "count": len(skills)}
    except Exception as exc:
        return {"error": str(exc)}


@dataclass
class ScheduleResult:
    trigger_id: str
    ok: bool
    task_id: str = ""
    output: Any = None
    error: str = ""
    blocked: bool = False
    approval_required: bool = False
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "ok": self.ok,
            "task_id": self.task_id,
            "output": self.output,
            "error": self.error,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
            "event_id": self.event_id,
        }


def _log_scheduler_event(
    trigger_id: str, ok: bool, event_type: str, detail: str
) -> str:
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log = WorkbenchEventLog()
        ev = log.push(
            session_id="wave1_scheduler",
            task_id=trigger_id,
            event_type=event_type,
            title=f"Automation scheduler: {event_type} — {trigger_id}",
            detail=detail,
            tone="success" if ok else ("error" if "blocked" in event_type else "warning"),
            metadata={"trigger_id": trigger_id, "ok": ok},
        )
        return ev.id
    except Exception:
        return ""


def _is_external_send(trigger: Any) -> bool:
    tid = (trigger.trigger_id or "").lower()
    name = (trigger.name or "").lower()
    skill = (trigger.skill_id or "").lower()
    return any(
        kw in tid or kw in name or kw in skill
        for kw in ("slack", "email", "telegram", "sms", "send_")
    )


def schedule_trigger(
    trigger: Any,  # AutomationTrigger
    *,
    store_path: str = _DEFAULT_STORE_PATH,
) -> ScheduleResult:
    """Register an AutomationTrigger as a ScheduledTask in the local scheduler store.

    High/critical risk → approval_required (not scheduled).
    External sends → hard-blocked.
    Low/medium risk with auto policy → scheduled (disabled, requires manual enable).
    """
    # Hard-block external sends
    if _is_external_send(trigger):
        eid = _log_scheduler_event(trigger.trigger_id, False, "automation_blocked",
                                    "External send trigger is hard-blocked from scheduling")
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=False,
            blocked=True,
            error="External send triggers (Slack/email/Telegram) are hard-blocked",
            event_id=eid,
        )

    # High/critical risk requires approval
    if trigger.risk_level in ("high", "critical"):
        eid = _log_scheduler_event(trigger.trigger_id, False, "automation_blocked",
                                    f"risk_level={trigger.risk_level} requires approval")
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=False,
            approval_required=True,
            error=f"Trigger '{trigger.trigger_id}' (risk={trigger.risk_level}) requires approval before scheduling",
            event_id=eid,
        )

    # Wire to TaskScheduler
    try:
        from openjarvis.scheduler.store import SchedulerStore
        from openjarvis.scheduler.scheduler import TaskScheduler

        Path(store_path).parent.mkdir(parents=True, exist_ok=True)
        store = SchedulerStore(db_path=store_path)
        scheduler = TaskScheduler(store=store)

        # Determine schedule_value
        schedule_type = trigger.trigger_type
        schedule_value = trigger.schedule or "manual"
        if schedule_type == "cron" and not trigger.schedule:
            schedule_value = "0 * * * *"  # default hourly
        elif schedule_type in ("event", "webhook", "manual"):
            schedule_type = "once"
            schedule_value = "manual"

        task = scheduler.create_task(
            prompt=f"wave1_automation:{trigger.trigger_id}",
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            metadata={
                "wave1_trigger_id": trigger.trigger_id,
                "trigger_type": trigger.trigger_type,
                "skill_id": trigger.skill_id,
                "risk_level": trigger.risk_level,
                "approval_policy": trigger.approval_policy,
            },
        )

        eid = _log_scheduler_event(
            trigger.trigger_id, True, "automation_dry_run",
            f"Trigger scheduled as task_id={task.id} type={schedule_type}"
        )
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=True,
            task_id=task.id,
            event_id=eid,
        )

    except Exception as exc:
        eid = _log_scheduler_event(trigger.trigger_id, False, "automation_blocked", str(exc))
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=False,
            error=f"Scheduler wiring failed: {exc}",
            event_id=eid,
        )


def execute_safe_trigger(
    trigger: Any,  # AutomationTrigger
    action_key: Optional[str] = None,
) -> ScheduleResult:
    """Execute a safe local trigger action immediately (no background thread).

    Only _SAFE_IMMEDIATE_ACTIONS are allowed.
    High-risk or external-send triggers are blocked.
    """
    if _is_external_send(trigger):
        eid = _log_scheduler_event(trigger.trigger_id, False, "automation_blocked",
                                    "External send trigger blocked from immediate execution")
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=False,
            blocked=True,
            error="External send triggers are hard-blocked",
            event_id=eid,
        )

    if trigger.risk_level in ("high", "critical"):
        eid = _log_scheduler_event(trigger.trigger_id, False, "automation_blocked",
                                    f"risk={trigger.risk_level} blocked immediate execution")
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=False,
            approval_required=True,
            error=f"High-risk trigger '{trigger.trigger_id}' requires approval before execution",
            event_id=eid,
        )

    key = action_key or trigger.skill_id or "log_status"
    handler = _SAFE_IMMEDIATE_ACTIONS.get(key)
    if handler is None:
        key = "log_status"
        handler = _SAFE_IMMEDIATE_ACTIONS["log_status"]

    try:
        output = handler({
            "trigger_id": trigger.trigger_id,
            "trigger_type": trigger.trigger_type,
        })
        eid = _log_scheduler_event(
            trigger.trigger_id, True, "automation_dry_run",
            f"Executed safe action '{key}' for trigger '{trigger.trigger_id}'"
        )
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=True,
            output=output,
            event_id=eid,
        )
    except Exception as exc:
        eid = _log_scheduler_event(trigger.trigger_id, False, "automation_blocked", str(exc))
        return ScheduleResult(
            trigger_id=trigger.trigger_id,
            ok=False,
            error=str(exc),
            event_id=eid,
        )


def list_scheduled_triggers(store_path: str = _DEFAULT_STORE_PATH) -> List[Dict[str, Any]]:
    """List all Wave 1 automation triggers persisted in the scheduler store."""
    try:
        from openjarvis.scheduler.store import SchedulerStore
        from openjarvis.scheduler.scheduler import TaskScheduler

        if not Path(store_path).exists():
            return []

        store = SchedulerStore(db_path=store_path)
        scheduler = TaskScheduler(store=store)
        tasks = scheduler.list_tasks()
        return [
            t.to_dict() for t in tasks
            if "wave1_automation:" in (t.prompt or "")
        ]
    except Exception:
        return []


def get_scheduler_status() -> Dict[str, Any]:
    return {
        "implemented": True,
        "scheduler_backend": "openjarvis.scheduler.TaskScheduler",
        "safe_immediate_actions": list(_SAFE_IMMEDIATE_ACTIONS.keys()),
        "external_sends_blocked": True,
        "high_risk_requires_approval": True,
        "background_autopilot_disabled": True,
        "note": "Local scheduler wired. Background cron thread disabled by default (no uncontrolled autopilot).",
    }


__all__ = [
    "ScheduleResult",
    "schedule_trigger",
    "execute_safe_trigger",
    "list_scheduled_triggers",
    "get_scheduler_status",
]
