"""Jarvis Governance — constitution, policies, and project registry.

This package encodes Bryan's operating rules so that future Jarvis behavior
is governed by code, not only by external prompts.

Quick reference:
  - constitution.py  : identity, honesty rules, verdict types, project registry
  - policies.py      : enforcement helpers (gate_check, classify_verdict, etc.)

Usage:
  from openjarvis.governance.constitution import ProjectRegistry, Verdict
  from openjarvis.governance.policies import gate_check, requires_approval
"""

from openjarvis.governance.constitution import (
    ALWAYS_APPROVAL_AGENTS,
    APPROVAL_REQUIRED_RISK_LEVELS,
    CONSTITUTION,
    HARD_GATE_ACTIONS,
    JARVIS_IDENTITY,
    OMNIX_PROJECT,
    STRICT_OPERATING_RULES,
    STRICT_OPERATING_RULES_PLATFORMS,
    ActionCategory,
    Blocker,
    Evidence,
    EvidenceStatus,
    ProjectProfile,
    ProjectRegistry,
    Verdict,
)
from openjarvis.governance.policies import (
    audit_log,
    build_blocker,
    check_action_category,
    classify_verdict,
    completion_refusal_reason,
    gate_check,
    insufficient_data_message,
    is_hard_gate,
    is_sufficient_evidence,
    project_gate_check,
    requires_approval,
    validate_completion,
)

__all__ = [
    "ALWAYS_APPROVAL_AGENTS",
    "APPROVAL_REQUIRED_RISK_LEVELS",
    "CONSTITUTION",
    "HARD_GATE_ACTIONS",
    "JARVIS_IDENTITY",
    "OMNIX_PROJECT",
    "STRICT_OPERATING_RULES",
    "STRICT_OPERATING_RULES_PLATFORMS",
    "ActionCategory",
    "Blocker",
    "Evidence",
    "EvidenceStatus",
    "ProjectProfile",
    "ProjectRegistry",
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
