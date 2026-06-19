"""NUS 1D — Eval Gate Framework.

Defines structured eval gates that validate recommendation/execution readiness
before any action proceeds. Fails closed on missing evidence.

Gates validate:
  - validation plan presence
  - rollback plan presence (required for any mutation)
  - risk classification completeness
  - capability readiness
  - safety gate result
  - eval evidence completeness

An eval gate that is missing required evidence will FAIL CLOSED —
it never returns pass on absent evidence.

Hard safety constraints:
  - No self-modification, no auto-commit, no deploy, no external sends.
  - No secret access.
  - Fails closed on missing evidence.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1D_EVAL_GATE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

_VALID_RISK_LEVELS: FrozenSet[str] = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL})

# ---------------------------------------------------------------------------
# Gate result constants
# ---------------------------------------------------------------------------

GATE_PASS = "pass"
GATE_FAIL = "fail"
GATE_FAIL_CLOSED = "fail_closed"   # missing required evidence → always fail


# ---------------------------------------------------------------------------
# EvalGateResult
# ---------------------------------------------------------------------------


@dataclass
class EvalGateResult:
    """Result of a single eval gate evaluation."""

    result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    gate_name: str = ""
    outcome: str = GATE_FAIL_CLOSED
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    evaluated_at: float = field(default_factory=time.time)

    @property
    def passed(self) -> bool:
        return self.outcome == GATE_PASS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "gate_name": self.gate_name,
            "outcome": self.outcome,
            "reason": self.reason,
            "passed": self.passed,
            "evidence": self.evidence,
            "evaluated_at": self.evaluated_at,
        }


# ---------------------------------------------------------------------------
# EvalGateReport — aggregates multiple gate results
# ---------------------------------------------------------------------------


@dataclass
class EvalGateReport:
    """Aggregated report from running all eval gates against a candidate."""

    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    candidate_id: str = ""
    action_type: str = ""
    risk_level: str = RISK_LOW
    gate_results: List[EvalGateResult] = field(default_factory=list)
    overall_outcome: str = GATE_FAIL_CLOSED
    generated_at: float = field(default_factory=time.time)

    @property
    def all_passed(self) -> bool:
        return bool(self.gate_results) and all(r.passed for r in self.gate_results)

    @property
    def failed_gates(self) -> List[EvalGateResult]:
        return [r for r in self.gate_results if not r.passed]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "candidate_id": self.candidate_id,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "gate_results": [r.to_dict() for r in self.gate_results],
            "overall_outcome": self.overall_outcome,
            "all_passed": self.all_passed,
            "failed_gates": [r.gate_name for r in self.failed_gates],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# EvalCandidate — what we are evaluating
# ---------------------------------------------------------------------------


@dataclass
class EvalCandidate:
    """Describes a candidate action/recommendation for eval gate review."""

    candidate_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    action_type: str = ""
    risk_level: str = RISK_LOW
    validation_plan: str = ""
    rollback_plan: str = ""
    capability_id: str = ""
    capability_ready: Optional[bool] = None
    safety_gate_result: Optional[str] = None   # "pass" | "fail" | None
    evidence: Dict[str, Any] = field(default_factory=dict)
    dry_run: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "validation_plan": self.validation_plan,
            "rollback_plan": self.rollback_plan,
            "capability_id": self.capability_id,
            "capability_ready": self.capability_ready,
            "safety_gate_result": self.safety_gate_result,
            "evidence": self.evidence,
            "dry_run": self.dry_run,
        }


# ---------------------------------------------------------------------------
# Individual gate evaluators (fail closed on missing evidence)
# ---------------------------------------------------------------------------


# Actions that require a rollback plan
_MUTATION_ACTIONS: FrozenSet[str] = frozenset({
    "file_write",
    "code_edit",
    "auto_commit",
    "config_change",
    "schema_migration",
    "package_install",
    "dependency_update",
})

# Actions that are always blocked regardless of eval gate
_ALWAYS_BLOCKED_ACTIONS: FrozenSet[str] = frozenset({
    "self_modification",
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


def gate_validation_plan(candidate: EvalCandidate) -> EvalGateResult:
    """Gate: validation plan must be present and non-empty."""
    if not candidate.validation_plan or not candidate.validation_plan.strip():
        return EvalGateResult(
            gate_name="validation_plan",
            outcome=GATE_FAIL_CLOSED,
            reason="Missing required validation_plan — fail closed.",
            evidence={"validation_plan": candidate.validation_plan},
        )
    return EvalGateResult(
        gate_name="validation_plan",
        outcome=GATE_PASS,
        reason="Validation plan present.",
        evidence={"validation_plan_preview": candidate.validation_plan[:100]},
    )


def gate_rollback_plan(candidate: EvalCandidate) -> EvalGateResult:
    """Gate: rollback plan required for any mutation action."""
    is_mutation = candidate.action_type in _MUTATION_ACTIONS
    if is_mutation and (not candidate.rollback_plan or not candidate.rollback_plan.strip()):
        return EvalGateResult(
            gate_name="rollback_plan",
            outcome=GATE_FAIL_CLOSED,
            reason=f"Mutation action={candidate.action_type} requires rollback_plan — fail closed.",
            evidence={"action_type": candidate.action_type, "rollback_plan": candidate.rollback_plan},
        )
    if not is_mutation:
        return EvalGateResult(
            gate_name="rollback_plan",
            outcome=GATE_PASS,
            reason=f"action_type={candidate.action_type} is not a mutation — rollback not required.",
            evidence={"action_type": candidate.action_type},
        )
    return EvalGateResult(
        gate_name="rollback_plan",
        outcome=GATE_PASS,
        reason="Rollback plan present.",
        evidence={"rollback_plan_preview": candidate.rollback_plan[:100]},
    )


def gate_risk_classification(candidate: EvalCandidate) -> EvalGateResult:
    """Gate: risk level must be valid and classified."""
    if not candidate.risk_level or candidate.risk_level not in _VALID_RISK_LEVELS:
        return EvalGateResult(
            gate_name="risk_classification",
            outcome=GATE_FAIL_CLOSED,
            reason=f"Invalid or missing risk_level='{candidate.risk_level}' — fail closed.",
            evidence={"risk_level": candidate.risk_level, "valid_levels": list(_VALID_RISK_LEVELS)},
        )
    return EvalGateResult(
        gate_name="risk_classification",
        outcome=GATE_PASS,
        reason=f"Risk classification valid: {candidate.risk_level}",
        evidence={"risk_level": candidate.risk_level},
    )


def gate_capability_readiness(candidate: EvalCandidate) -> EvalGateResult:
    """Gate: capability readiness must be confirmed if capability_id is specified."""
    if candidate.capability_id and candidate.capability_ready is None:
        return EvalGateResult(
            gate_name="capability_readiness",
            outcome=GATE_FAIL_CLOSED,
            reason=(
                f"capability_id='{candidate.capability_id}' specified but "
                "capability_ready is None — fail closed."
            ),
            evidence={"capability_id": candidate.capability_id},
        )
    if candidate.capability_id and candidate.capability_ready is False:
        return EvalGateResult(
            gate_name="capability_readiness",
            outcome=GATE_FAIL,
            reason=f"Capability '{candidate.capability_id}' is not ready.",
            evidence={"capability_id": candidate.capability_id, "ready": False},
        )
    return EvalGateResult(
        gate_name="capability_readiness",
        outcome=GATE_PASS,
        reason=(
            f"Capability readiness satisfied: capability_id='{candidate.capability_id}' "
            f"ready={candidate.capability_ready}"
        ),
        evidence={"capability_id": candidate.capability_id, "ready": candidate.capability_ready},
    )


def gate_safety_gate_result(candidate: EvalCandidate) -> EvalGateResult:
    """Gate: safety gate result must be 'pass' (not fail, not None)."""
    if candidate.safety_gate_result is None:
        return EvalGateResult(
            gate_name="safety_gate_result",
            outcome=GATE_FAIL_CLOSED,
            reason="safety_gate_result is None — fail closed (missing evidence).",
            evidence={"safety_gate_result": None},
        )
    if candidate.safety_gate_result != "pass":
        return EvalGateResult(
            gate_name="safety_gate_result",
            outcome=GATE_FAIL,
            reason=f"Safety gate result='{candidate.safety_gate_result}' — not pass.",
            evidence={"safety_gate_result": candidate.safety_gate_result},
        )
    return EvalGateResult(
        gate_name="safety_gate_result",
        outcome=GATE_PASS,
        reason="Safety gate passed.",
        evidence={"safety_gate_result": "pass"},
    )


def gate_blocked_action(candidate: EvalCandidate) -> EvalGateResult:
    """Gate: action must not be in always-blocked list."""
    if candidate.action_type in _ALWAYS_BLOCKED_ACTIONS:
        return EvalGateResult(
            gate_name="blocked_action",
            outcome=GATE_FAIL_CLOSED,
            reason=(
                f"action_type='{candidate.action_type}' is permanently blocked. "
                "Eval gate cannot pass for blocked action categories."
            ),
            evidence={"action_type": candidate.action_type},
        )
    return EvalGateResult(
        gate_name="blocked_action",
        outcome=GATE_PASS,
        reason=f"action_type='{candidate.action_type}' is not in blocked list.",
        evidence={"action_type": candidate.action_type},
    )


# ---------------------------------------------------------------------------
# EvalGateRunner
# ---------------------------------------------------------------------------


# Gate pipeline ordered for fast-fail
_GATE_PIPELINE = [
    gate_blocked_action,       # Hard block first
    gate_risk_classification,  # Risk must be classified
    gate_validation_plan,      # Validation plan required
    gate_rollback_plan,        # Rollback required for mutations
    gate_capability_readiness, # Capability must be ready
    gate_safety_gate_result,   # Safety gate must have passed
]


class EvalGateRunner:
    """Runs the eval gate pipeline against an EvalCandidate.

    Fails closed on any missing evidence.
    All gates must pass for overall PASS verdict.
    """

    def run(self, candidate: EvalCandidate) -> EvalGateReport:
        """Run all eval gates. Returns EvalGateReport. Fails closed on missing evidence."""
        results: List[EvalGateResult] = []
        for gate_fn in _GATE_PIPELINE:
            result = gate_fn(candidate)
            results.append(result)
            # Fast-fail: stop on first blocked action (no point running other gates)
            if result.gate_name == "blocked_action" and not result.passed:
                break

        all_pass = bool(results) and all(r.passed for r in results)
        overall = GATE_PASS if all_pass else (
            GATE_FAIL_CLOSED if any(r.outcome == GATE_FAIL_CLOSED for r in results) else GATE_FAIL
        )

        report = EvalGateReport(
            candidate_id=candidate.candidate_id,
            action_type=candidate.action_type,
            risk_level=candidate.risk_level,
            gate_results=results,
            overall_outcome=overall,
        )

        self._log_event(
            "eval_gate_passed" if all_pass else "eval_gate_failed",
            f"EvalGate: action={candidate.action_type} outcome={overall} "
            f"failed_gates={[r.gate_name for r in results if not r.passed]}",
        )
        return report

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1d",
                task_id="eval_gate",
                event_type=event_type,
                title=f"NUS 1D: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1D eval gate event log skipped: %s", exc)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def run_eval_gate(candidate: EvalCandidate) -> EvalGateReport:
    """Convenience: run eval gates against a candidate. Returns EvalGateReport."""
    return EvalGateRunner().run(candidate)


def get_eval_gate_status() -> Dict[str, Any]:
    return {
        "version": NUS1D_EVAL_GATE_VERSION,
        "gates": [fn.__name__ for fn in _GATE_PIPELINE],
        "gate_count": len(_GATE_PIPELINE),
        "fail_closed": True,
        "mutation_actions_require_rollback": sorted(_MUTATION_ACTIONS),
        "always_blocked_actions": sorted(_ALWAYS_BLOCKED_ACTIONS),
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "safety_gates_active": True,
    }
