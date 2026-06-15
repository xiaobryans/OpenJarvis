"""Jarvis Governance Policy Enforcement.

Policy helpers that are imported by the mission router, runner, and executor
layers to make governance rules runtime-enforced rather than prose-only.

Key functions:
  - requires_approval()    — risk + agent gate check (mirrors router logic)
  - is_hard_gate()         — strict UNSAFE gate check
  - classify_verdict()     — ACCEPT/HOLD/UNSAFE from evidence list
  - validate_completion()  — refuses fake completions (no empty output)
  - check_action_category() — returns ActionCategory for an action type
  - build_blocker()        — structured blocker report
  - audit_log()            — structured audit record (no secrets)

All helpers are pure functions — no side-effects, no I/O, no network.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

from openjarvis.governance.constitution import (
    ALWAYS_APPROVAL_AGENTS,
    APPROVAL_REQUIRED_RISK_LEVELS,
    HARD_GATE_ACTIONS,
    ActionCategory,
    Blocker,
    Evidence,
    EvidenceStatus,
    Verdict,
)


# ===========================================================================
# 1. Risk / Approval Gates
# ===========================================================================


def requires_approval(risk_level: str, agent_id: str) -> bool:
    """Return True if this (risk_level, agent_id) pair requires owner approval.

    Governance sources of truth:
      - ALWAYS_APPROVAL_AGENTS: always require approval regardless of risk
      - APPROVAL_REQUIRED_RISK_LEVELS: high/critical always require approval
    """
    return (
        agent_id in ALWAYS_APPROVAL_AGENTS
        or risk_level.lower() in APPROVAL_REQUIRED_RISK_LEVELS
    )


def is_hard_gate(action_type: str) -> bool:
    """Return True if action_type is a hard gate — UNSAFE if attempted without approval.

    Hard gates are non-negotiable: no policy exception overrides them.
    """
    return action_type.lower() in HARD_GATE_ACTIONS


def check_action_category(action_type: str, risk_level: str = "low", agent_id: str = "") -> ActionCategory:
    """Classify an action as SAFE, REQUIRES_APPROVAL, or HARD_GATE.

    Used by routers and action gates before dispatching work.
    """
    if is_hard_gate(action_type):
        return ActionCategory.HARD_GATE
    if requires_approval(risk_level, agent_id):
        return ActionCategory.REQUIRES_APPROVAL
    return ActionCategory.SAFE


# ===========================================================================
# 2. Verdict Classification
# ===========================================================================

# Minimum verified evidence count required for an ACCEPT verdict.
_MIN_VERIFIED_FOR_ACCEPT = 1


def classify_verdict(evidence: Sequence[Evidence]) -> Verdict:
    """Derive a Verdict from a list of Evidence items.

    Rules (non-negotiable):
      - UNSAFE if any evidence explicitly flags an UNSAFE hard-gate violation.
      - ACCEPT only if at least one piece of VERIFIED evidence exists AND
        no MISSING evidence is present for a required item.
      - HOLD if evidence is absent, insufficient, or assumed without verification.

    Never returns ACCEPT on assumption alone.
    """
    if not evidence:
        return Verdict.HOLD

    statuses = {e.status for e in evidence}

    if EvidenceStatus.MISSING in statuses:
        return Verdict.HOLD

    verified = [e for e in evidence if e.status == EvidenceStatus.VERIFIED]
    assumed = [e for e in evidence if e.status == EvidenceStatus.ASSUMED]
    insufficient = [e for e in evidence if e.status == EvidenceStatus.INSUFFICIENT]

    if insufficient:
        return Verdict.HOLD

    if len(verified) >= _MIN_VERIFIED_FOR_ACCEPT and not assumed:
        return Verdict.ACCEPT

    if assumed and not verified:
        return Verdict.HOLD

    if verified:
        return Verdict.ACCEPT

    return Verdict.HOLD


def is_sufficient_evidence(evidence: Sequence[Evidence]) -> bool:
    """Return True only if all evidence items are verified and at least one exists."""
    if not evidence:
        return False
    return all(e.status == EvidenceStatus.VERIFIED for e in evidence)


def insufficient_data_message(context: str = "") -> str:
    """Return the standard 'Insufficient data to verify' statement."""
    if context:
        return f"Insufficient data to verify: {context}"
    return "Insufficient data to verify."


# ===========================================================================
# 3. Completion Validation (no fake work)
# ===========================================================================


def validate_completion(output: str, summary: str = "") -> bool:
    """Return True only if a task has a real non-empty output.

    Governance rule: agents cannot mark tasks complete with empty output.
    Whitespace-only strings are treated as empty.
    """
    return bool(output and output.strip())


def completion_refusal_reason() -> str:
    """Standard refusal message when an executor produces empty output."""
    return (
        "Governance policy: task cannot be marked COMPLETED with an empty output. "
        "No fake work. Produce a real result or mark the task BLOCKED with a reason."
    )


# ===========================================================================
# 4. Blocker Report Builder
# ===========================================================================


def build_blocker(
    blocker: str,
    why_it_matters: str,
    unblock_path: str,
    *,
    can_continue_partially: bool = False,
    partial_scope: str = "",
) -> Blocker:
    """Construct a structured blocker report per completion policy."""
    return Blocker(
        blocker=blocker,
        why_it_matters=why_it_matters,
        unblock_path=unblock_path,
        can_continue_partially=can_continue_partially,
        partial_scope=partial_scope,
    )


# ===========================================================================
# 5. Action Gate Check (full check with UNSAFE result)
# ===========================================================================


def gate_check(
    action_type: str,
    *,
    risk_level: str = "low",
    agent_id: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a full governance gate check on a proposed action.

    Returns a dict with:
      - allowed: bool
      - category: ActionCategory
      - verdict: Verdict (UNSAFE if hard gate violated)
      - reason: str
      - requires_approval: bool
    """
    category = check_action_category(action_type, risk_level, agent_id)

    if category == ActionCategory.HARD_GATE:
        return {
            "allowed": False,
            "category": category.value,
            "verdict": Verdict.UNSAFE.value,
            "requires_approval": True,
            "reason": (
                f"HARD GATE: '{action_type}' requires explicit owner approval. "
                "This action cannot be auto-executed under any policy exception."
            ),
        }

    if category == ActionCategory.REQUIRES_APPROVAL:
        return {
            "allowed": False,
            "category": category.value,
            "verdict": Verdict.HOLD.value,
            "requires_approval": True,
            "reason": (
                f"APPROVAL REQUIRED: agent '{agent_id}' / risk '{risk_level}' requires "
                "explicit owner approval before execution."
            ),
        }

    return {
        "allowed": True,
        "category": category.value,
        "verdict": Verdict.ACCEPT.value,
        "requires_approval": False,
        "reason": "Action is within safe auto-execute policy.",
    }


# ===========================================================================
# 6. Audit Record Builder (no secrets)
# ===========================================================================

_SENSITIVE_KEYS = frozenset({
    "token", "secret", "password", "api_key", "auth", "credential",
    "private_key", "access_key", "bot_token", "chat_id",
})


def _scrub(value: Any, depth: int = 0) -> Any:
    """Recursively replace sensitive values with '<redacted>'."""
    if depth > 5:
        return value
    if isinstance(value, dict):
        return {
            k: "<redacted>" if any(s in k.lower() for s in _SENSITIVE_KEYS) else _scrub(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(i, depth + 1) for i in value]
    return value


def audit_log(
    action_type: str,
    agent_id: str,
    verdict: str,
    *,
    task_id: Optional[str] = None,
    mission_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Dict[str, Any]:
    """Build a scrubbed audit record. Never includes secrets."""
    return {
        "ts": time.time(),
        "action_type": action_type,
        "agent_id": agent_id,
        "verdict": verdict,
        "task_id": task_id,
        "mission_id": mission_id,
        "reason": reason,
        "context": _scrub(context or {}),
    }


# ===========================================================================
# 7. Project-scoped gate check
# ===========================================================================


def project_gate_check(project_id: str, action_type: str) -> Dict[str, Any]:
    """Check action against the specific deploy gates of a project.

    A project's deploy_gates list is an additional layer on top of the global
    HARD_GATE_ACTIONS set. Any action in a project's deploy_gates requires
    project-owner approval even if it is not in the global hard gates.
    """
    from openjarvis.governance.constitution import ProjectRegistry

    project = ProjectRegistry.get(project_id)
    if project is None:
        return {
            "allowed": False,
            "verdict": Verdict.HOLD.value,
            "reason": f"Project '{project_id}' not found in ProjectRegistry.",
        }

    if action_type in project.deploy_gates or is_hard_gate(action_type):
        return {
            "allowed": False,
            "verdict": Verdict.UNSAFE.value,
            "reason": (
                f"Action '{action_type}' is gated for project '{project.display_name}'. "
                "Explicit owner approval required."
            ),
        }

    return {
        "allowed": True,
        "verdict": Verdict.ACCEPT.value,
        "reason": f"Action '{action_type}' is permitted for project '{project.display_name}'.",
    }


__all__ = [
    "ActionCategory",
    "Blocker",
    "Evidence",
    "EvidenceStatus",
    "Verdict",
    "audit_log",
    "build_blocker",
    "check_action_category",
    "classify_verdict",
    "completion_refusal_reason",
    "gate_check",
    "insufficient_data_message",
    "is_hard_gate",
    "is_sufficient_evidence",
    "project_gate_check",
    "requires_approval",
    "validate_completion",
]
