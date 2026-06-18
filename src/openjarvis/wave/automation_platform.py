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


def get_automation_platform_status() -> Dict[str, Any]:
    """Return automation platform status for Mission Control / doctor."""
    reg = AutomationRegistry()
    return {
        "epic": "epic_b",
        "wave": 1,
        "status": "scaffolded",
        "trigger_count": len(reg.list_triggers()),
        "runtime_execution_implemented": False,
        "cron_wiring_implemented": False,
        "approval_gate_enforced": True,
        "destructive_automations_disabled_by_default": True,
        "note": "AutomationTrigger model + registry exist. Runtime execution is Wave 1 next slice.",
    }


__all__ = [
    "AutomationTrigger",
    "AutomationRegistry",
    "TRIGGER_CRON",
    "TRIGGER_EVENT",
    "TRIGGER_WEBHOOK",
    "TRIGGER_MANUAL",
    "POLICY_AUTO",
    "POLICY_REQUIRES_APPROVAL",
    "POLICY_HARD_GATE",
    "get_automation_platform_status",
]
