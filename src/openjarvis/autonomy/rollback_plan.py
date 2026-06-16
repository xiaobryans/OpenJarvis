"""Jarvis Rollback / Undo Plans.

Before any risky action (file write, config edit, connector send, queue job,
desktop/browser action), a rollback plan must be generated and logged.

Rollback plan contract:
  - dry_run preview is always available
  - execution log stores rollback plan before action executes
  - rollback execution requires explicit approval (never automatic)
  - no destructive rollback without approval

Action risk classification:
  - low: read-only, no side effects → rollback trivial (no-op)
  - medium: reversible writes → rollback plan stored
  - high: irreversible or external effects → requires approval + stored plan
  - dangerous: never executes without human approval + stored plan

Storage: ~/.openjarvis/rollback_log.jsonl
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROLLBACK_LOG = Path.home() / ".openjarvis" / "rollback_log.jsonl"


class ActionRisk:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DANGEROUS = "dangerous"


# Risk classification for known action types
_ACTION_RISK_MAP: Dict[str, str] = {
    "read_file": ActionRisk.LOW,
    "run_diagnostic": ActionRisk.LOW,
    "list_jobs": ActionRisk.LOW,
    "queue_inspect": ActionRisk.LOW,
    "write_file": ActionRisk.MEDIUM,
    "edit_config": ActionRisk.MEDIUM,
    "git_commit": ActionRisk.MEDIUM,
    "queue_enqueue": ActionRisk.MEDIUM,
    "slack_send": ActionRisk.HIGH,
    "telegram_send": ActionRisk.HIGH,
    "git_push": ActionRisk.HIGH,
    "browser_form_submit": ActionRisk.DANGEROUS,
    "production_deploy": ActionRisk.DANGEROUS,
    "secrets_mutation": ActionRisk.DANGEROUS,
    "env_mutation": ActionRisk.DANGEROUS,
    "billing_change": ActionRisk.DANGEROUS,
}


@dataclass
class RollbackPlan:
    plan_id: str
    action: str
    description: str
    risk_level: str
    rollback_steps: List[str]
    is_reversible: bool
    dry_run_preview: str
    created_at: float
    executed: bool = False
    executed_at: Optional[float] = None
    rolled_back: bool = False
    approval_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_action_risk(action: str) -> str:
    """Classify risk level for an action type."""
    return _ACTION_RISK_MAP.get(action, ActionRisk.MEDIUM)


def create_rollback_plan(
    action: str,
    description: str,
    current_state: Optional[Dict[str, Any]] = None,
    target_state: Optional[Dict[str, Any]] = None,
    risk_level: Optional[str] = None,
) -> RollbackPlan:
    """Create a rollback plan for a proposed action.

    current_state: snapshot of state before action (e.g., file contents, config)
    target_state: what the action would change to
    """
    risk = risk_level or classify_action_risk(action)
    plan_id = str(uuid.uuid4())

    if risk == ActionRisk.LOW:
        rollback_steps = ["No rollback required — action is read-only"]
        is_reversible = True
        dry_run = f"[DRY RUN] {action}: {description} (read-only, no side effects)"
        approval_required = False
    elif risk == ActionRisk.MEDIUM:
        rollback_steps = _generate_medium_rollback(action, current_state)
        is_reversible = True
        dry_run = f"[DRY RUN] {action}: {description} (reversible — rollback plan stored)"
        approval_required = False
    elif risk == ActionRisk.HIGH:
        rollback_steps = _generate_high_rollback(action, current_state)
        is_reversible = False
        dry_run = (
            f"[DRY RUN] {action}: {description} "
            "(HIGH RISK — requires explicit approval before execution)"
        )
        approval_required = True
    else:  # DANGEROUS
        rollback_steps = [
            "DANGEROUS action — NOT reversible",
            "Requires explicit human approval + written justification",
            "No automatic rollback available",
        ]
        is_reversible = False
        dry_run = (
            f"[DRY RUN] {action}: {description} "
            "(DANGEROUS — BLOCKED until explicit human approval)"
        )
        approval_required = True

    return RollbackPlan(
        plan_id=plan_id,
        action=action,
        description=description,
        risk_level=risk,
        rollback_steps=rollback_steps,
        is_reversible=is_reversible,
        dry_run_preview=dry_run,
        created_at=time.time(),
        approval_required=approval_required,
    )


def _generate_medium_rollback(
    action: str, current_state: Optional[Dict[str, Any]]
) -> List[str]:
    steps = []
    if action == "write_file":
        path = (current_state or {}).get("path", "(unknown path)")
        backup = (current_state or {}).get("backup_path")
        steps.append(f"Restore original file from backup: {backup or 'create backup first'}")
        steps.append(f"Target path: {path}")
    elif action == "edit_config":
        steps.append("Restore config from backup snapshot taken before edit")
        steps.append("Config backup path stored in rollback_log.jsonl")
    elif action == "git_commit":
        steps.append("Run: git revert HEAD (creates new revert commit)")
        steps.append("Or: git reset --soft HEAD~1 (unstage, keep changes)")
    elif action == "queue_enqueue":
        job_id = (current_state or {}).get("job_id", "(unknown)")
        steps.append(f"Cancel queued job: cancel_job('{job_id}')")
    else:
        steps.append(f"Undo {action}: restore previous state from snapshot")
        if current_state:
            steps.append(f"Previous state keys: {list(current_state.keys())}")
    return steps


def _generate_high_rollback(
    action: str, current_state: Optional[Dict[str, Any]]
) -> List[str]:
    steps = []
    if action in ("slack_send", "telegram_send"):
        steps.append("Message already sent — cannot unsend from external service")
        steps.append("Notify recipient of correction if needed")
        steps.append("Audit log entry recorded")
    elif action == "git_push":
        steps.append("git push --force fork <branch> (with Bryan approval)")
        steps.append("Or coordinate with team to revert pushed commits")
    else:
        steps.append(f"HIGH RISK: {action} may not be fully reversible")
        steps.append("Audit log entry recorded before execution")
    return steps


# ---------------------------------------------------------------------------
# Log / retrieve rollback plans
# ---------------------------------------------------------------------------


def log_rollback_plan(plan: RollbackPlan) -> None:
    """Persist rollback plan to log before action executes."""
    try:
        _ROLLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _ROLLBACK_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(plan.to_dict()) + "\n")
    except Exception:
        pass


def mark_executed(plan_id: str) -> None:
    """Mark a plan as executed. Append-only log — creates new entry."""
    try:
        _ROLLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _ROLLBACK_LOG.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"event": "executed", "plan_id": plan_id, "at": time.time()}
                )
                + "\n"
            )
    except Exception:
        pass


def get_recent_plans(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent rollback plan entries from log."""
    plans: List[Dict[str, Any]] = []
    if not _ROLLBACK_LOG.exists():
        return plans
    try:
        lines = _ROLLBACK_LOG.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines[-100:]):
            if not line.strip():
                continue
            d = json.loads(line)
            if "plan_id" in d and "action" in d:
                plans.append(d)
                if len(plans) >= limit:
                    break
    except Exception:
        pass
    return plans


# ---------------------------------------------------------------------------
# Doctor/readiness
# ---------------------------------------------------------------------------


def get_rollback_policy_status() -> Dict[str, Any]:
    """Report rollback policy status for doctor/readiness."""
    log_exists = _ROLLBACK_LOG.exists()
    recent = get_recent_plans(5) if log_exists else []
    return {
        "policy_active": True,
        "log_path": str(_ROLLBACK_LOG),
        "log_exists": log_exists,
        "recent_plan_count": len(recent),
        "dry_run_available": True,
        "dangerous_actions_blocked": True,
        "approval_required_for": ["high", "dangerous"],
        "automatic_rollback_disabled": True,
        "note": (
            "Rollback execution always requires explicit approval. "
            "No destructive rollback without Bryan approval."
        ),
    }


__all__ = [
    "ActionRisk",
    "RollbackPlan",
    "classify_action_risk",
    "create_rollback_plan",
    "log_rollback_plan",
    "mark_executed",
    "get_recent_plans",
    "get_rollback_policy_status",
]
