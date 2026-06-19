"""NUS 1C — Safe Autopilot Activation.

Activates safe_autopilot profile for low-risk local actions only.

Safe autopilot MAY automatically do or dry-run ONLY these categories:
  - local_read
  - local_analysis
  - validation_planning
  - recommendation_deduplication
  - scorecard_generation
  - telemetry_normalization
  - failure_pattern_summarization
  - dry_run_recommendation_execution (safe internal only, no source-code/ext)
  - safe_local_status_snapshot

Safe autopilot MUST NOT do:
  - source-code edits
  - file writes outside approved internal state/temp paths
  - auto_commit, auto_push, auto_merge
  - deploy
  - external sends
  - browser/account/provider setup
  - secret access
  - safety/governance policy changes
  - self_modification

Medium-risk → needs_approval:
  - file_write
  - external_provider_setup
  - browser_automation
  - external_send / connector_setup / account_auth_changes

Dangerous → blocked:
  - self_modification, auto_commit, auto_push, auto_merge, deploy
  - secret_access, safety_policy_change, destructive_delete
  - production_action, payment_action, financial_action

Kill-switch: if autonomy_kill_switch is True, all auto actions return blocked/disabled.

Hard safety constraints (permanent — no exceptions):
  - No source-code mutation by autopilot.
  - No auto-commit, auto-push, auto-merge.
  - No deploy.
  - No external sends.
  - No secret access.
  - No uncontrolled browser automation.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1C_AUTOPILOT_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Action categories
# ---------------------------------------------------------------------------

# Safe auto-allowed (safe_autopilot active in NUS 1C)
SAFE_AUTO_ACTIONS: FrozenSet[str] = frozenset({
    "local_read",
    "local_analysis",
    "validation_planning",
    "recommendation_deduplication",
    "scorecard_generation",
    "telemetry_normalization",
    "failure_pattern_summarization",
    "dry_run_recommendation_execution",
    "safe_local_status_snapshot",
    # NUS 1A/1B aliases
    "local_validation",
})

# Medium risk — needs approval in all profiles
MEDIUM_RISK_ACTIONS: FrozenSet[str] = frozenset({
    "file_write",
    "external_provider_setup",
    "browser_automation",
    "external_send",
    "connector_setup",
    "account_auth_change",
})

# Dangerous — always blocked regardless of profile
DANGEROUS_ACTIONS: FrozenSet[str] = frozenset({
    "self_modification",
    "code_edit",
    "auto_commit",
    "auto_push",
    "auto_merge",
    "deploy",
    "secret_access",
    "safety_policy_change",
    "destructive_delete",
    "production_action",
    "payment_action",
    "financial_action",
})


# ---------------------------------------------------------------------------
# AutopilotDecision
# ---------------------------------------------------------------------------


@dataclass
class AutopilotDecision:
    """Result of safe autopilot evaluation for a single action."""

    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    action_type: str = ""
    decision: str = "blocked"  # auto_allowed | needs_approval | blocked | kill_switch_disabled
    reason: str = ""
    dry_run_result: Optional[Dict[str, Any]] = None
    kill_switch_active: bool = False
    evaluated_at: float = field(default_factory=time.time)
    profile: str = "safe_autopilot"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action_type": self.action_type,
            "decision": self.decision,
            "reason": self.reason,
            "dry_run_result": self.dry_run_result,
            "kill_switch_active": self.kill_switch_active,
            "evaluated_at": self.evaluated_at,
            "profile": self.profile,
        }


# ---------------------------------------------------------------------------
# SafeAutopilot
# ---------------------------------------------------------------------------


class SafeAutopilot:
    """NUS 1C Safe Autopilot.

    Evaluates actions and runs safe local dry-runs automatically.
    Blocks dangerous actions. Gates medium-risk actions (needs_approval).
    Respects kill-switch.

    Active for NUS 1C: safe local analysis, dry-runs, and status operations only.
    """

    def __init__(self, kill_switch: bool = False) -> None:
        self._kill_switch = kill_switch
        self._decisions: List[AutopilotDecision] = []
        self._log_event(
            "autonomy_profile_activated",
            f"NUS 1C SafeAutopilot initialized. kill_switch={kill_switch}",
        )

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    @kill_switch.setter
    def kill_switch(self, value: bool) -> None:
        prev = self._kill_switch
        self._kill_switch = value
        if value and not prev:
            self._log_event("autonomy_kill_switch_triggered", "Kill switch activated.")
        elif not value and prev:
            self._log_event("autonomy_kill_switch_triggered", "Kill switch deactivated.")

    # ------------------------------------------------------------------ #
    # Core evaluation                                                       #
    # ------------------------------------------------------------------ #

    def evaluate(self, action_type: str, context: Optional[Dict[str, Any]] = None) -> AutopilotDecision:
        """Evaluate an action_type. Returns an AutopilotDecision."""
        ctx = context or {}

        if self._kill_switch:
            dec = AutopilotDecision(
                action_type=action_type,
                decision="kill_switch_disabled",
                reason="autonomy_kill_switch is active — all auto actions disabled",
                kill_switch_active=True,
            )
            self._decisions.append(dec)
            self._log_event(
                "safe_autopilot_action_blocked",
                f"Kill switch active — blocked: {action_type}",
            )
            return dec

        if action_type in DANGEROUS_ACTIONS:
            dec = AutopilotDecision(
                action_type=action_type,
                decision="blocked",
                reason=f"action_type={action_type} is permanently blocked (dangerous category)",
            )
            self._decisions.append(dec)
            self._log_event(
                "safe_autopilot_action_blocked",
                f"Dangerous action blocked: {action_type}",
            )
            return dec

        if action_type in MEDIUM_RISK_ACTIONS:
            dec = AutopilotDecision(
                action_type=action_type,
                decision="needs_approval",
                reason=f"action_type={action_type} is medium-risk and requires human approval",
            )
            self._decisions.append(dec)
            return dec

        if action_type in SAFE_AUTO_ACTIONS:
            dry_run_result = self._execute_dry_run(action_type, ctx)
            dec = AutopilotDecision(
                action_type=action_type,
                decision="auto_allowed",
                reason=f"action_type={action_type} is safe local — auto-allowed under safe_autopilot",
                dry_run_result=dry_run_result,
            )
            self._decisions.append(dec)
            self._log_event(
                "safe_autopilot_dry_run_executed",
                f"Safe dry-run: {action_type}",
            )
            return dec

        # Unknown action type — default to needs_approval (conservative)
        dec = AutopilotDecision(
            action_type=action_type,
            decision="needs_approval",
            reason=f"action_type={action_type} unknown — defaulting to needs_approval (conservative)",
        )
        self._decisions.append(dec)
        return dec

    # ------------------------------------------------------------------ #
    # Batch evaluation                                                      #
    # ------------------------------------------------------------------ #

    def evaluate_batch(
        self, actions: List[str], context: Optional[Dict[str, Any]] = None
    ) -> List[AutopilotDecision]:
        """Evaluate multiple action types. Returns list of AutopilotDecision."""
        return [self.evaluate(a, context) for a in actions]

    # ------------------------------------------------------------------ #
    # Safe dry-run execution                                                #
    # ------------------------------------------------------------------ #

    def _execute_dry_run(
        self, action_type: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a safe local dry-run for an allowed action type.

        This does NOT:
          - mutate source files
          - write outside approved state/temp paths
          - access secrets
          - send externally
          - commit, push, merge, or deploy
        """
        return {
            "dry_run": True,
            "action_type": action_type,
            "executed_at": time.time(),
            "result": "simulated_ok",
            "note": (
                "NUS 1C safe autopilot dry-run — no source mutation, "
                "no commit, no deploy, no external send, no secret access"
            ),
            "context_keys": list(context.keys())[:10],
        }

    # ------------------------------------------------------------------ #
    # Status and queries                                                    #
    # ------------------------------------------------------------------ #

    def get_status(self) -> Dict[str, Any]:
        """Return safe autopilot status."""
        by_decision: Dict[str, int] = {}
        for d in self._decisions:
            by_decision[d.decision] = by_decision.get(d.decision, 0) + 1

        return {
            "version": NUS1C_AUTOPILOT_VERSION,
            "profile": "safe_autopilot",
            "activation_status": "active",
            "kill_switch": self._kill_switch,
            "decision_count": len(self._decisions),
            "by_decision": by_decision,
            "safe_auto_actions": sorted(SAFE_AUTO_ACTIONS),
            "medium_risk_actions": sorted(MEDIUM_RISK_ACTIONS),
            "dangerous_blocked_actions": sorted(DANGEROUS_ACTIONS),
            "power_autopilot": "defined_not_activated",
            "founder_override_session": "defined_not_activated",
            "production_restricted": "defined_not_activated",
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
            "no_self_modification": True,
            "no_auto_commit": True,
            "no_auto_push": True,
            "no_auto_merge": True,
            "no_deploy": True,
            "no_external_sends": True,
            "no_secret_access": True,
        }

    def get_decisions(self) -> List[AutopilotDecision]:
        return list(self._decisions)

    # ------------------------------------------------------------------ #
    # Event logging                                                         #
    # ------------------------------------------------------------------ #

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1c",
                task_id="safe_autopilot",
                event_type=event_type,
                title=f"NUS 1C: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1C autopilot event log skipped: %s", exc)


# ---------------------------------------------------------------------------
# Autonomy profile catalog (NUS 1C update)
# ---------------------------------------------------------------------------


def get_autonomy_profile_status() -> Dict[str, Any]:
    """Return NUS 1C autonomy profile status.

    NUS 1C activates safe_autopilot for safe local analysis/dry-run only.
    All other profiles remain defined but not activated.
    """
    return {
        "version": NUS1C_AUTOPILOT_VERSION,
        "profiles": {
            "manual": {
                "status": "available",
                "description": "All actions require human approval. Conservative default.",
            },
            "safe_autopilot": {
                "status": "active",
                "description": (
                    "Active in NUS 1C. Auto-allows safe local analysis, dry-runs, "
                    "scorecard generation, telemetry normalization, failure pattern "
                    "summarization, and safe local status snapshots. "
                    "All writes, sends, secrets, deploy, commit, browser remain gated or blocked."
                ),
                "auto_allowed": sorted(SAFE_AUTO_ACTIONS),
                "needs_approval": sorted(MEDIUM_RISK_ACTIONS),
                "always_blocked": sorted(DANGEROUS_ACTIONS),
            },
            "power_autopilot": {
                "status": "defined_not_activated",
                "description": "Defined for NUS 1D+. Not activated in NUS 1C.",
            },
            "founder_override_session": {
                "status": "defined_not_activated",
                "description": "Defined for NUS 1D+. Requires explicit session activation.",
            },
            "production_restricted": {
                "status": "defined_not_activated",
                "description": "Defined for future production safety audits. Not activated.",
            },
        },
        "kill_switch_behavior": (
            "When kill_switch=True, safe_autopilot performs no auto action "
            "and returns kill_switch_disabled status for all action types."
        ),
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "safety_gates_active": True,
    }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_autopilot: Optional[SafeAutopilot] = None


def get_safe_autopilot(kill_switch: bool = False) -> SafeAutopilot:
    """Return the module-level SafeAutopilot singleton."""
    global _autopilot
    if _autopilot is None:
        _autopilot = SafeAutopilot(kill_switch=kill_switch)
    return _autopilot
