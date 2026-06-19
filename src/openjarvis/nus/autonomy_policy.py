"""NUS 1B — Autonomy Policy Scaffold.

Defines the structure for future automation profiles without broadly enabling them yet.

Profiles defined:
  - manual              → all actions require human approval (default/safe)
  - safe_autopilot      → local read/analysis/validation auto-allowed; everything else gated
  - power_autopilot     → local ops + file writes auto-allowed with audit; sends/browser/secrets gated
  - founder_override_session → expanded session-level permissions for founder; still gated for risky ops
  - production_restricted   → read-only; all mutations blocked; for production safety audits

For NUS 1B:
  - Default profile: manual (conservative)
  - Only local read/analysis/dry-run can be auto-allowed (safe_autopilot defines these)
  - File writes, sends, browser, deploy, secrets, self-modification, auto-commit,
    auto-push remain gated or blocked in all profiles
  - Kill-switch field: autonomy_kill_switch (disables all auto actions when True)
  - Audit-required flag: audit_required
  - Rollback-required flag: rollback_required (for any mutation-class action)

NUS 1C+ will activate safe_autopilot / power_autopilot profiles under explicit owner approval.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional

logger = logging.getLogger(__name__)

NUS1B_POLICY_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Profile names
# ---------------------------------------------------------------------------

PROFILE_MANUAL = "manual"
PROFILE_SAFE_AUTOPILOT = "safe_autopilot"
PROFILE_POWER_AUTOPILOT = "power_autopilot"
PROFILE_FOUNDER_OVERRIDE = "founder_override_session"
PROFILE_PRODUCTION_RESTRICTED = "production_restricted"

_ALL_PROFILES = frozenset({
    PROFILE_MANUAL,
    PROFILE_SAFE_AUTOPILOT,
    PROFILE_POWER_AUTOPILOT,
    PROFILE_FOUNDER_OVERRIDE,
    PROFILE_PRODUCTION_RESTRICTED,
})

# ---------------------------------------------------------------------------
# Auto-allowed action types per profile
# ---------------------------------------------------------------------------

# Actions that are ALWAYS blocked regardless of profile
_ALWAYS_BLOCKED: FrozenSet[str] = frozenset({
    "self_modification",
    "code_edit",
    "secret_access",
    "auto_push",
    "deploy",
    "safety_policy_change",
})

# Actions that require approval in every profile (never auto)
_ALWAYS_NEEDS_APPROVAL: FrozenSet[str] = frozenset({
    "external_send",
    "browser_automation",
    "external_provider_setup",
})

_PROFILE_AUTO_ALLOWED: Dict[str, FrozenSet[str]] = {
    PROFILE_MANUAL: frozenset(),
    PROFILE_SAFE_AUTOPILOT: frozenset({
        "local_read", "local_analysis", "local_validation",
    }),
    PROFILE_POWER_AUTOPILOT: frozenset({
        "local_read", "local_analysis", "local_validation",
        # file_write allowed with audit in power_autopilot — but blocked in NUS 1B
        # (included here as structure for NUS 1C+, gated via activation_status)
    }),
    PROFILE_FOUNDER_OVERRIDE: frozenset({
        "local_read", "local_analysis", "local_validation",
    }),
    PROFILE_PRODUCTION_RESTRICTED: frozenset({
        "local_read",
    }),
}

# auto_commit is blocked in every profile (including founder override)
_PROFILE_BLOCKED: Dict[str, FrozenSet[str]] = {
    PROFILE_MANUAL: frozenset({
        "file_write", "code_edit", "self_modification", "auto_commit",
        "auto_push", "deploy", "secret_access", "external_send",
        "browser_automation", "external_provider_setup", "safety_policy_change",
    }),
    PROFILE_SAFE_AUTOPILOT: frozenset({
        "file_write", "code_edit", "self_modification", "auto_commit",
        "auto_push", "deploy", "secret_access", "safety_policy_change",
    }),
    PROFILE_POWER_AUTOPILOT: frozenset({
        "code_edit", "self_modification", "auto_commit",
        "auto_push", "deploy", "secret_access", "safety_policy_change",
    }),
    PROFILE_FOUNDER_OVERRIDE: frozenset({
        "code_edit", "self_modification", "auto_commit",
        "auto_push", "deploy", "secret_access", "safety_policy_change",
    }),
    PROFILE_PRODUCTION_RESTRICTED: frozenset({
        "file_write", "code_edit", "self_modification", "auto_commit",
        "auto_push", "deploy", "secret_access", "external_send",
        "browser_automation", "external_provider_setup", "safety_policy_change",
    }),
}

# ---------------------------------------------------------------------------
# AutonomyPolicy dataclass
# ---------------------------------------------------------------------------


@dataclass
class AutonomyPolicy:
    """Autonomy policy instance for a session or global default."""

    profile: str = PROFILE_MANUAL
    activation_status: str = "defined_not_activated"
    autonomy_kill_switch: bool = False
    audit_required: bool = True
    rollback_required: bool = True
    created_at: float = field(default_factory=time.time)
    notes: str = ""
    version: str = NUS1B_POLICY_VERSION

    # NUS 1B: only manual and safe_autopilot are fully activated
    # power_autopilot / founder_override require NUS 1C+ activation
    _ACTIVATED_PROFILES: FrozenSet[str] = field(
        default=frozenset({PROFILE_MANUAL}), init=False, repr=False, compare=False
    )

    def is_activated(self) -> bool:
        """Return True if this profile is currently activated (not just defined)."""
        if self.autonomy_kill_switch:
            return False
        return self.profile in (PROFILE_MANUAL, PROFILE_SAFE_AUTOPILOT)

    def is_action_auto_allowed(self, action_type: str) -> bool:
        """Return True if the action type is auto-allowed under this policy."""
        if self.autonomy_kill_switch:
            return False
        if action_type in _ALWAYS_BLOCKED:
            return False
        if action_type in _ALWAYS_NEEDS_APPROVAL:
            return False
        allowed = _PROFILE_AUTO_ALLOWED.get(self.profile, frozenset())
        return action_type in allowed

    def is_action_blocked(self, action_type: str) -> bool:
        """Return True if the action type is hard-blocked under this policy."""
        if self.autonomy_kill_switch:
            return True
        if action_type in _ALWAYS_BLOCKED:
            return True
        blocked = _PROFILE_BLOCKED.get(self.profile, frozenset())
        return action_type in blocked

    def evaluate(self, action_type: str) -> Dict[str, Any]:
        """Evaluate an action type against this policy. Returns decision dict."""
        result: Dict[str, Any] = {
            "action_type": action_type,
            "profile": self.profile,
            "kill_switch": self.autonomy_kill_switch,
            "evaluated_at": time.time(),
        }
        if self.autonomy_kill_switch:
            result["decision"] = "blocked"
            result["reason"] = "autonomy_kill_switch is active"
            self._log_event("autonomy_action_blocked", f"Kill switch active — blocked: {action_type}")
            return result

        if self.is_action_blocked(action_type):
            result["decision"] = "blocked"
            result["reason"] = f"action_type={action_type} blocked under profile={self.profile}"
            self._log_event("autonomy_action_blocked", f"Blocked: {action_type} policy={self.profile}")
            return result

        if action_type in _ALWAYS_NEEDS_APPROVAL:
            result["decision"] = "needs_approval"
            result["reason"] = "action type always requires approval"
            self._log_event("autonomy_policy_evaluated", f"Needs approval: {action_type}")
            return result

        if self.is_action_auto_allowed(action_type):
            result["decision"] = "auto_allowed"
            result["reason"] = f"auto_allowed under profile={self.profile}"
            result["audit_required"] = self.audit_required
            self._log_event("autonomy_policy_evaluated", f"Auto-allowed: {action_type}")
            return result

        # Default: needs_approval
        result["decision"] = "needs_approval"
        result["reason"] = f"not explicitly auto_allowed under profile={self.profile}"
        self._log_event("autonomy_policy_evaluated", f"Needs approval (default): {action_type}")
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile,
            "activation_status": self.activation_status,
            "autonomy_kill_switch": self.autonomy_kill_switch,
            "audit_required": self.audit_required,
            "rollback_required": self.rollback_required,
            "created_at": self.created_at,
            "notes": self.notes,
            "version": self.version,
            "is_activated": self.is_activated(),
            "auto_allowed_actions": sorted(_PROFILE_AUTO_ALLOWED.get(self.profile, frozenset())),
            "blocked_actions": sorted(_PROFILE_BLOCKED.get(self.profile, frozenset())),
            "always_blocked": sorted(_ALWAYS_BLOCKED),
            "always_needs_approval": sorted(_ALWAYS_NEEDS_APPROVAL),
        }

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1b",
                task_id="autonomy_policy",
                event_type=event_type,
                title=f"NUS 1B: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1B policy event log skipped: %s", exc)


# ---------------------------------------------------------------------------
# Profile catalog — all profiles defined for NUS 1C+ reference
# ---------------------------------------------------------------------------


def get_policy_catalog() -> Dict[str, AutonomyPolicy]:
    """Return all defined autonomy policies. Only manual/safe_autopilot are activated in NUS 1B."""
    return {
        PROFILE_MANUAL: AutonomyPolicy(
            profile=PROFILE_MANUAL,
            activation_status="active",
            autonomy_kill_switch=False,
            audit_required=True,
            rollback_required=True,
            notes="Default conservative policy. All actions require human approval.",
        ),
        PROFILE_SAFE_AUTOPILOT: AutonomyPolicy(
            profile=PROFILE_SAFE_AUTOPILOT,
            activation_status="defined_not_activated",
            autonomy_kill_switch=False,
            audit_required=True,
            rollback_required=True,
            notes=(
                "Safe autopilot: local read/analysis/validation auto-allowed. "
                "All file writes, sends, browser, deploy, secrets remain gated. "
                "Activation requires NUS 1C+ approval."
            ),
        ),
        PROFILE_POWER_AUTOPILOT: AutonomyPolicy(
            profile=PROFILE_POWER_AUTOPILOT,
            activation_status="defined_not_activated",
            autonomy_kill_switch=True,
            audit_required=True,
            rollback_required=True,
            notes=(
                "Power autopilot: local ops + audited file writes. "
                "Sends/browser/deploy/secrets still gated. "
                "Kill switch enabled by default — requires explicit NUS 1C+ activation."
            ),
        ),
        PROFILE_FOUNDER_OVERRIDE: AutonomyPolicy(
            profile=PROFILE_FOUNDER_OVERRIDE,
            activation_status="defined_not_activated",
            autonomy_kill_switch=True,
            audit_required=True,
            rollback_required=True,
            notes=(
                "Founder override session: expanded local permissions. "
                "Auto-commit/push/deploy/secrets remain blocked. "
                "Requires explicit session activation."
            ),
        ),
        PROFILE_PRODUCTION_RESTRICTED: AutonomyPolicy(
            profile=PROFILE_PRODUCTION_RESTRICTED,
            activation_status="defined_not_activated",
            autonomy_kill_switch=False,
            audit_required=True,
            rollback_required=True,
            notes=(
                "Production restricted: read-only. All mutations blocked. "
                "For production safety audits only."
            ),
        ),
    }


def get_default_policy() -> AutonomyPolicy:
    """Return the default (conservative) autonomy policy for NUS 1B."""
    return get_policy_catalog()[PROFILE_MANUAL]


def get_policy_status() -> Dict[str, Any]:
    """Return a summary of all defined policies and their activation status."""
    catalog = get_policy_catalog()
    return {
        "version": NUS1B_POLICY_VERSION,
        "default_profile": PROFILE_MANUAL,
        "nus1b_active_profiles": [PROFILE_MANUAL],
        "nus1c_profiles_defined_not_activated": [
            PROFILE_SAFE_AUTOPILOT, PROFILE_POWER_AUTOPILOT,
            PROFILE_FOUNDER_OVERRIDE, PROFILE_PRODUCTION_RESTRICTED,
        ],
        "always_blocked": sorted(_ALWAYS_BLOCKED),
        "always_needs_approval": sorted(_ALWAYS_NEEDS_APPROVAL),
        "profiles": {name: p.to_dict() for name, p in catalog.items()},
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "safety_gates_active": True,
    }
