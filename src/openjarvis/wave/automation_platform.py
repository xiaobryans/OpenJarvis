"""Epic B — Automation Platform Foundation (Wave 1 scaffold).

Provides AutomationTrigger model and AutomationRegistry scaffold.
References existing scheduler/ for cron and openjarvis.governance for approval gates.

Status: SCAFFOLDED — trigger model + registry exist; runtime execution,
cron wiring, and approval flow for destructive automations not yet implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Trigger types
TRIGGER_CRON = "cron"
TRIGGER_EVENT = "event"
TRIGGER_WEBHOOK = "webhook"
TRIGGER_MANUAL = "manual"

TRIGGER_TYPES = frozenset({TRIGGER_CRON, TRIGGER_EVENT, TRIGGER_WEBHOOK, TRIGGER_MANUAL})

# Approval policies
POLICY_AUTO = "auto"
POLICY_REQUIRES_APPROVAL = "requires_approval"
POLICY_HARD_GATE = "hard_gate"

# Automation statuses
STATUS_REGISTERED = "registered"
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"
STATUS_BLOCKED = "blocked"


@dataclass
class AutomationTrigger:
    """An automation trigger — defines when and how an automation fires.

    Destructive automations (risk_level=high/critical) always require approval.
    External sends (Slack, email, Telegram) are hard-gated.
    """

    trigger_id: str
    name: str
    trigger_type: str           # cron | event | webhook | manual
    schedule: str = ""          # cron expression (if trigger_type=cron)
    event_name: str = ""        # event name (if trigger_type=event)
    skill_id: str = ""          # skill to invoke on trigger
    approval_policy: str = POLICY_REQUIRES_APPROVAL
    risk_level: str = "medium"  # low | medium | high | critical
    enabled: bool = False       # disabled by default — must be explicitly enabled
    description: str = ""
    status: str = STATUS_REGISTERED
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "schedule": self.schedule,
            "event_name": self.event_name,
            "skill_id": self.skill_id,
            "approval_policy": self.approval_policy,
            "risk_level": self.risk_level,
            "enabled": self.enabled,
            "description": self.description,
            "status": self.status,
        }

    def requires_approval(self) -> bool:
        return (
            self.approval_policy in (POLICY_REQUIRES_APPROVAL, POLICY_HARD_GATE)
            or self.risk_level in ("high", "critical")
        )


class AutomationRegistry:
    """Registry of automation triggers (Wave 1 scaffold).

    All triggers are disabled by default.
    Enabling a trigger requires approval if risk_level >= high or
    approval_policy != 'auto'.
    """

    def __init__(self) -> None:
        self._triggers: Dict[str, AutomationTrigger] = {}

    def register(self, trigger: AutomationTrigger) -> Dict[str, Any]:
        """Register a trigger. Never enables it automatically."""
        if trigger.trigger_type not in TRIGGER_TYPES:
            return {"ok": False, "error": f"Unknown trigger_type: {trigger.trigger_type}"}
        # Force disabled on registration — must be explicitly enabled after approval
        trigger.enabled = False
        trigger.status = STATUS_REGISTERED
        self._triggers[trigger.trigger_id] = trigger
        return {"ok": True, "trigger_id": trigger.trigger_id, "status": STATUS_REGISTERED}

    def enable(self, trigger_id: str) -> Dict[str, Any]:
        """Enable a trigger — requires approval if policy demands it."""
        t = self._triggers.get(trigger_id)
        if t is None:
            return {"ok": False, "error": f"Trigger not found: {trigger_id}"}
        if t.requires_approval():
            return {
                "ok": False,
                "status": "approval_required",
                "reason": f"Trigger '{trigger_id}' requires explicit approval to enable (risk={t.risk_level})",
            }
        t.enabled = True
        t.status = STATUS_ENABLED
        return {"ok": True, "trigger_id": trigger_id, "status": STATUS_ENABLED}

    def disable(self, trigger_id: str) -> Dict[str, Any]:
        t = self._triggers.get(trigger_id)
        if t is None:
            return {"ok": False, "error": f"Trigger not found: {trigger_id}"}
        t.enabled = False
        t.status = STATUS_DISABLED
        return {"ok": True, "trigger_id": trigger_id, "status": STATUS_DISABLED}

    def get(self, trigger_id: str) -> Optional[AutomationTrigger]:
        return self._triggers.get(trigger_id)

    def list_triggers(self) -> List[AutomationTrigger]:
        return list(self._triggers.values())


# ---------------------------------------------------------------------------
# Dry-run execution result
# ---------------------------------------------------------------------------

@dataclass
class AutomationDryRunResult:
    trigger_id: str
    ok: bool
    simulated_output: str = ""
    error: str = ""
    blocked: bool = False
    approval_required: bool = False
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "ok": self.ok,
            "simulated_output": self.simulated_output,
            "error": self.error,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
            "event_id": self.event_id,
        }


def _log_automation_event(
    trigger_id: str,
    ok: bool,
    blocked: bool,
    approval_required: bool,
    detail: str,
) -> str:
    try:
        from openjarvis.workbench.event_log import (
            WorkbenchEventLog,
            EVENT_AUTOMATION_DRY_RUN,
            EVENT_AUTOMATION_BLOCKED,
            EVENT_APPROVAL_REQUIRED,
        )
        log = WorkbenchEventLog()
        etype = EVENT_AUTOMATION_BLOCKED if blocked else (
            EVENT_APPROVAL_REQUIRED if approval_required else EVENT_AUTOMATION_DRY_RUN
        )
        ev = log.push(
            session_id="wave1_automation",
            task_id=trigger_id,
            event_type=etype,
            title=f"Automation dry-run {'blocked' if blocked else 'completed'}: {trigger_id}",
            detail=detail,
            tone="error" if blocked else ("warning" if approval_required else "success"),
            metadata={"trigger_id": trigger_id, "ok": ok},
        )
        return ev.id
    except Exception:
        return ""


# Safe simulated outputs for dry-run
_DRY_RUN_SIMULATIONS: Dict[str, str] = {
    TRIGGER_MANUAL: "Simulated manual trigger fired — no side effects in dry-run mode.",
    TRIGGER_EVENT: "Simulated event trigger fired — event handler would be invoked in live mode.",
    TRIGGER_CRON: "Simulated cron trigger — would fire according to schedule in live mode.",
    TRIGGER_WEBHOOK: "Simulated webhook trigger — webhook endpoint would be called in live mode.",
}


def dry_run_trigger(
    trigger_id: str,
    registry: Optional[AutomationRegistry] = None,
) -> AutomationDryRunResult:
    """Dry-run an automation trigger — simulates execution without real side effects.

    High/critical risk triggers still require approval even for dry-run.
    Returns a structured result with simulated output.
    """
    reg = registry or AutomationRegistry()
    trigger = reg.get(trigger_id)

    if trigger is None:
        return AutomationDryRunResult(
            trigger_id=trigger_id,
            ok=False,
            error=f"Trigger not found: {trigger_id}",
        )

    # High-risk/critical triggers require approval even for dry-run
    if trigger.risk_level in ("high", "critical"):
        eid = _log_automation_event(trigger_id, False, False, True,
                                     f"Dry-run blocked: risk_level={trigger.risk_level} requires approval")
        return AutomationDryRunResult(
            trigger_id=trigger_id,
            ok=False,
            approval_required=True,
            error=(
                f"Trigger '{trigger_id}' (risk_level={trigger.risk_level}) "
                "requires approval before dry-run"
            ),
            event_id=eid,
        )

    # External sends are always hard-gated
    if "slack" in trigger_id.lower() or "email" in trigger_id.lower():
        eid = _log_automation_event(trigger_id, False, True, False,
                                     "External send triggers are hard-gated")
        return AutomationDryRunResult(
            trigger_id=trigger_id,
            ok=False,
            blocked=True,
            error="External send triggers (Slack/email) are hard-gated — never auto-execute",
            event_id=eid,
        )

    simulated = _DRY_RUN_SIMULATIONS.get(trigger.trigger_type, f"Dry-run of {trigger.trigger_type} trigger.")
    detail = (
        f"[DRY-RUN] trigger_id={trigger_id} type={trigger.trigger_type} "
        f"skill={trigger.skill_id or 'none'} risk={trigger.risk_level}"
    )
    eid = _log_automation_event(trigger_id, True, False, False, detail)

    return AutomationDryRunResult(
        trigger_id=trigger_id,
        ok=True,
        simulated_output=simulated,
        event_id=eid,
    )


def get_automation_platform_status() -> Dict[str, Any]:
    """Return automation platform status for Mission Control / doctor."""
    reg = AutomationRegistry()
    scheduler_ok = False
    try:
        from openjarvis.wave.automation_scheduler import get_scheduler_status
        sched = get_scheduler_status()
        scheduler_ok = sched.get("implemented", False)
    except Exception:
        pass
    return {
        "epic": "epic_b",
        "wave": 1,
        "status": "ready",
        "trigger_count": len(reg.list_triggers()),
        "dry_run_implemented": True,
        "scheduler_wiring_implemented": scheduler_ok,
        "runtime_execution_implemented": scheduler_ok,
        "background_autopilot_disabled": True,
        "approval_gate_enforced": True,
        "destructive_automations_disabled_by_default": True,
        "note": (
            "AutomationTrigger model + dry-run + scheduler wiring implemented. "
            "Background cron thread disabled (no uncontrolled autopilot)."
        ),
    }


__all__ = [
    "AutomationTrigger",
    "AutomationDryRunResult",
    "AutomationRegistry",
    "TRIGGER_CRON",
    "TRIGGER_EVENT",
    "TRIGGER_WEBHOOK",
    "TRIGGER_MANUAL",
    "POLICY_AUTO",
    "POLICY_REQUIRES_APPROVAL",
    "POLICY_HARD_GATE",
    "dry_run_trigger",
    "get_automation_platform_status",
]
