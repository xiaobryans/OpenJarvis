"""NUS 1D — Power Autopilot Boundary Definition.

Defines power_autopilot boundaries. In NUS 1D, power_autopilot is
controlled but NOT broadly activated. Any activation is:
  - local-only
  - dry-run / test-only (no real file writes to source code)
  - governed by eval gates, rollback plans, kill-switch, and approval scope

Power autopilot MUST NOT allow:
  - deploy
  - external sends
  - secret access
  - browser/account setup
  - auto-push
  - auto-merge
  - safety policy changes
  - self_modification

Power autopilot in NUS 1D MAY (dry-run only):
  - local_read
  - local_analysis
  - local_validation
  - validation_planning
  - scorecard_generation
  - telemetry_normalization
  - failure_pattern_summarization
  - recommendation_deduplication
  - dry_run_recommendation_execution
  - safe_local_status_snapshot
  - [future] audited_file_write — only with eval gate + rollback + approval + kill-switch off

Power autopilot requires for any action:
  1. kill_switch == False
  2. eval gate PASS
  3. rollback plan present (for mutation actions)
  4. valid approval decision (for medium/high risk)

Hard safety constraints:
  - No source-code mutation.
  - No auto-commit, auto-push, auto-merge.
  - No deploy.
  - No external sends.
  - No secret access.
  - Real file writes outside safe state path require NUS 1F activation.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1D_POWER_AUTOPILOT_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Action categories for power_autopilot NUS 1D
# ---------------------------------------------------------------------------

# Safe local actions — auto-allowed with kill-switch off + eval gate pass
_PA_SAFE_LOCAL: FrozenSet[str] = frozenset({
    "local_read",
    "local_analysis",
    "local_validation",
    "validation_planning",
    "scorecard_generation",
    "telemetry_normalization",
    "failure_pattern_summarization",
    "recommendation_deduplication",
    "dry_run_recommendation_execution",
    "safe_local_status_snapshot",
})

# Medium risk: require approval + rollback plan before proceeding
# In NUS 1D these are dry-run only
_PA_MEDIUM_RISK_DRY_RUN: FrozenSet[str] = frozenset({
    "file_write",           # safe internal state only + rollback + approval
    "config_change",        # safe internal config only + rollback + approval
    "dependency_update",    # dry-run only in NUS 1D
})

# Always blocked regardless of profile
_PA_ALWAYS_BLOCKED: FrozenSet[str] = frozenset({
    "self_modification",
    "code_edit",
    "auto_push",
    "auto_merge",
    "deploy",
    "secret_access",
    "safety_policy_change",
    "destructive_delete",
    "production_action",
    "payment_action",
    "financial_action",
    "browser_automation",
    "external_send",
    "external_provider_setup",
    "account_auth_change",
})


# ---------------------------------------------------------------------------
# PowerAutopilotDecision
# ---------------------------------------------------------------------------


@dataclass
class PowerAutopilotDecision:
    """Result of power_autopilot evaluation."""

    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    action_type: str = ""
    decision: str = "blocked"
    reason: str = ""
    dry_run_result: Optional[Dict[str, Any]] = None
    requires_eval_gate: bool = True
    requires_rollback: bool = False
    requires_approval: bool = False
    kill_switch_active: bool = False
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action_type": self.action_type,
            "decision": self.decision,
            "reason": self.reason,
            "dry_run_result": self.dry_run_result,
            "requires_eval_gate": self.requires_eval_gate,
            "requires_rollback": self.requires_rollback,
            "requires_approval": self.requires_approval,
            "kill_switch_active": self.kill_switch_active,
            "evaluated_at": self.evaluated_at,
        }


# ---------------------------------------------------------------------------
# PowerAutopilot
# ---------------------------------------------------------------------------


class PowerAutopilot:
    """NUS 1D Power Autopilot — controlled boundary definition.

    NOT broadly activated in NUS 1D. When active, it extends safe_autopilot
    with dry-run medium-risk actions, all governed by eval gates, rollback,
    kill-switch, and approval.

    Activation status: controlled_not_broadly_activated
    """

    # NUS 1D: activation_status reflects controlled/dry-run only
    ACTIVATION_STATUS = "controlled_not_broadly_activated"

    def __init__(
        self,
        kill_switch: bool = True,   # Default kill-switch ON in NUS 1D
        require_eval_gate: bool = True,
    ) -> None:
        self._kill_switch = kill_switch
        self._require_eval_gate = require_eval_gate
        self._decisions: List[PowerAutopilotDecision] = []
        self._log_event(
            "autonomy_profile_activated",
            f"NUS 1D PowerAutopilot initialized. kill_switch={kill_switch} status={self.ACTIVATION_STATUS}",
        )

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    @kill_switch.setter
    def kill_switch(self, value: bool) -> None:
        prev = self._kill_switch
        self._kill_switch = value
        if value and not prev:
            self._log_event("autonomy_kill_switch_triggered", "PowerAutopilot kill switch activated.")

    def evaluate(
        self,
        action_type: str,
        context: Optional[Dict[str, Any]] = None,
        eval_gate_result: Optional[str] = None,  # "pass" | "fail" | None
        rollback_plan_id: Optional[str] = None,
        approval_decision_id: Optional[str] = None,
    ) -> PowerAutopilotDecision:
        """Evaluate an action under power_autopilot constraints.

        Fails safely when any required precondition is missing.
        """
        ctx = context or {}

        # 1. Kill-switch
        if self._kill_switch:
            dec = PowerAutopilotDecision(
                action_type=action_type,
                decision="kill_switch_disabled",
                reason="power_autopilot kill switch is active — all actions disabled",
                kill_switch_active=True,
            )
            self._decisions.append(dec)
            self._log_event("safe_autopilot_action_blocked", f"Kill switch active — blocked: {action_type}")
            return dec

        # 2. Always blocked
        if action_type in _PA_ALWAYS_BLOCKED:
            dec = PowerAutopilotDecision(
                action_type=action_type,
                decision="blocked",
                reason=f"action_type={action_type} is permanently blocked in power_autopilot",
            )
            self._decisions.append(dec)
            self._log_event("safe_autopilot_action_blocked", f"Blocked: {action_type}")
            return dec

        # 3. Safe local — eval gate required (if configured)
        if action_type in _PA_SAFE_LOCAL:
            if self._require_eval_gate and eval_gate_result != "pass":
                dec = PowerAutopilotDecision(
                    action_type=action_type,
                    decision="needs_eval_gate",
                    reason=f"action={action_type} requires eval gate PASS. Current: eval_gate_result={eval_gate_result}",
                    requires_eval_gate=True,
                )
                self._decisions.append(dec)
                return dec

            dry = {
                "dry_run": True,
                "action_type": action_type,
                "executed_at": time.time(),
                "result": "simulated_ok",
                "note": "NUS 1D power_autopilot dry-run — no real mutation",
            }
            dec = PowerAutopilotDecision(
                action_type=action_type,
                decision="auto_allowed",
                reason=f"action={action_type} safe local — auto-allowed under power_autopilot",
                dry_run_result=dry,
                requires_eval_gate=self._require_eval_gate,
            )
            self._decisions.append(dec)
            self._log_event("safe_autopilot_dry_run_executed", f"PA dry-run: {action_type}")
            return dec

        # 4. Medium-risk dry-run — requires eval gate + rollback + approval
        if action_type in _PA_MEDIUM_RISK_DRY_RUN:
            missing = []
            if self._require_eval_gate and eval_gate_result != "pass":
                missing.append("eval_gate_pass")
            if not rollback_plan_id:
                missing.append("rollback_plan")
            if not approval_decision_id:
                missing.append("approval_decision")

            if missing:
                dec = PowerAutopilotDecision(
                    action_type=action_type,
                    decision="needs_approval",
                    reason=(
                        f"Medium-risk action={action_type} requires: {missing}. "
                        "Provide eval gate pass, rollback plan, and approval before proceeding."
                    ),
                    requires_eval_gate=True,
                    requires_rollback=True,
                    requires_approval=True,
                )
                self._decisions.append(dec)
                return dec

            dry = {
                "dry_run": True,
                "action_type": action_type,
                "executed_at": time.time(),
                "result": "simulated_ok",
                "rollback_plan_id": rollback_plan_id,
                "approval_decision_id": approval_decision_id,
                "note": (
                    "NUS 1D power_autopilot medium-risk dry-run — "
                    "no real file writes outside safe state path"
                ),
            }
            dec = PowerAutopilotDecision(
                action_type=action_type,
                decision="dry_run_allowed",
                reason=f"Medium-risk dry-run approved: {action_type} with gate+rollback+approval",
                dry_run_result=dry,
                requires_eval_gate=True,
                requires_rollback=True,
                requires_approval=True,
            )
            self._decisions.append(dec)
            self._log_event("safe_autopilot_dry_run_executed", f"PA medium-risk dry-run: {action_type}")
            return dec

        # Default: needs_approval
        dec = PowerAutopilotDecision(
            action_type=action_type,
            decision="needs_approval",
            reason=f"action_type={action_type} unknown or not in safe/medium-risk list — needs approval",
        )
        self._decisions.append(dec)
        return dec

    def get_status(self) -> Dict[str, Any]:
        by_decision: Dict[str, int] = {}
        for d in self._decisions:
            by_decision[d.decision] = by_decision.get(d.decision, 0) + 1
        return {
            "version": NUS1D_POWER_AUTOPILOT_VERSION,
            "profile": "power_autopilot",
            "activation_status": self.ACTIVATION_STATUS,
            "kill_switch": self._kill_switch,
            "require_eval_gate": self._require_eval_gate,
            "decision_count": len(self._decisions),
            "by_decision": by_decision,
            "safe_local_actions": sorted(_PA_SAFE_LOCAL),
            "medium_risk_dry_run": sorted(_PA_MEDIUM_RISK_DRY_RUN),
            "always_blocked": sorted(_PA_ALWAYS_BLOCKED),
            "notes": (
                "power_autopilot is controlled but not broadly activated in NUS 1D. "
                "Real file writes outside safe state require NUS 1F gate. "
                "deploy/push/merge/secret/self_modification/browser/sends: permanently blocked."
            ),
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1d",
                task_id="power_autopilot",
                event_type=event_type,
                title=f"NUS 1D: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1D power_autopilot event log skipped: %s", exc)
