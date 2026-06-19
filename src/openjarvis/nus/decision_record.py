"""NUS 1F — Structured Decision Records.

Provides a generic, hierarchy-aware schema for all autonomy and session
decisions made by Jarvis PA, COS/GM, domain managers, workers,
validators, and governance.

Design principles:
  - No raw chain-of-thought stored. Only structured evidence.
  - Generic enough for all hierarchy levels (not just Jarvis PA).
  - Future-proof via metadata/tags/NUS learning tags.
  - Schema-stable: fields addable, never removed in compatible versions.
  - Captures: why allowed/blocked, evidence, validation, rollback, risk/cost,
    NUS learning tags for telemetry and scorecard aggregation.

Fields:
  record_id           — unique UUID
  created_at          — Unix timestamp
  schema_version      — record schema version
  decision            — "allowed" | "blocked" | "revoked" | "escalated" | "dry_run"
  reason              — short machine-readable reason code
  rationale           — human-readable summary (structured, not CoT)
  session_id          — associated session (if any)
  action_type         — what action was being evaluated
  hierarchy_level     — "jarvis_pa" | "cos_gm" | "manager" | "worker" | "validator" | "governance"
  agent_metadata      — metadata/contract fields for the agent (no hardcoded names)
  risk_level          — "low" | "medium" | "high" | "blocked"
  cost_estimate       — estimated cost impact
  token_estimate      — estimated token count
  validation_evidence — list of validation results
  rollback_evidence   — rollback plan reference or evidence
  context_evidence    — task context metadata
  nus_learning_tags   — list of NUS learning tag strings
  policy_reference    — which policy/profile governed this decision
  blocking_reason     — populated when decision == "blocked"
  escalation_target   — where to escalate if decision == "escalated"

No raw_chain_of_thought field is present by design.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

NUS1F_DECISION_RECORD_VERSION = "1.0.0"

# Decision values
DECISION_ALLOWED = "allowed"
DECISION_BLOCKED = "blocked"
DECISION_REVOKED = "revoked"
DECISION_ESCALATED = "escalated"
DECISION_DRY_RUN = "dry_run"

_VALID_DECISIONS = frozenset({
    DECISION_ALLOWED, DECISION_BLOCKED, DECISION_REVOKED,
    DECISION_ESCALATED, DECISION_DRY_RUN,
})

# Hierarchy levels
LEVEL_JARVIS_PA = "jarvis_pa"
LEVEL_COS_GM = "cos_gm"
LEVEL_MANAGER = "manager"
LEVEL_WORKER = "worker"
LEVEL_VALIDATOR = "validator"
LEVEL_GOVERNANCE = "governance"

_VALID_LEVELS = frozenset({
    LEVEL_JARVIS_PA, LEVEL_COS_GM, LEVEL_MANAGER,
    LEVEL_WORKER, LEVEL_VALIDATOR, LEVEL_GOVERNANCE,
})

# Risk levels
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_BLOCKED = "blocked"


@dataclass
class StructuredDecisionRecord:
    """A structured, evidence-based decision record.

    No raw chain-of-thought. Evidence only.
    Generic enough for all NUS hierarchy levels.
    """

    record_id: str
    created_at: float
    schema_version: str
    decision: str
    reason: str
    rationale: str
    session_id: str = ""
    action_type: str = ""
    hierarchy_level: str = LEVEL_JARVIS_PA
    agent_metadata: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = RISK_LOW
    cost_estimate: float = 0.0
    token_estimate: int = 0
    validation_evidence: List[Dict[str, Any]] = field(default_factory=list)
    rollback_evidence: Dict[str, Any] = field(default_factory=dict)
    context_evidence: Dict[str, Any] = field(default_factory=dict)
    nus_learning_tags: List[str] = field(default_factory=list)
    policy_reference: str = ""
    blocking_reason: str = ""
    escalation_target: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "decision": self.decision,
            "reason": self.reason,
            "rationale": self.rationale,
            "session_id": self.session_id,
            "action_type": self.action_type,
            "hierarchy_level": self.hierarchy_level,
            "agent_metadata": self.agent_metadata,
            "risk_level": self.risk_level,
            "cost_estimate": self.cost_estimate,
            "token_estimate": self.token_estimate,
            "validation_evidence": self.validation_evidence,
            "rollback_evidence": self.rollback_evidence,
            "context_evidence": self.context_evidence,
            "nus_learning_tags": self.nus_learning_tags,
            "policy_reference": self.policy_reference,
            "blocking_reason": self.blocking_reason,
            "escalation_target": self.escalation_target,
            # Explicit proof that no raw CoT is stored
            "no_raw_chain_of_thought": True,
        }


def build_session_decision_record(
    session_id: str,
    decision: str,
    reason: str,
    evidence: Dict[str, Any],
    action_type: str = "",
    hierarchy_level: str = LEVEL_JARVIS_PA,
    risk_level: str = RISK_LOW,
    policy_reference: str = "nus1f_session_policy",
    nus_learning_tags: Optional[List[str]] = None,
    rationale: str = "",
) -> Dict[str, Any]:
    """Build a structured decision record for a session event.

    Returns a dict (not StructuredDecisionRecord) for easy JSON serialization
    and embedding in session objects.
    """
    record = StructuredDecisionRecord(
        record_id=str(uuid.uuid4()),
        created_at=time.time(),
        schema_version=NUS1F_DECISION_RECORD_VERSION,
        decision=decision if decision in _VALID_DECISIONS else DECISION_BLOCKED,
        reason=reason,
        rationale=rationale or f"Session decision: {decision} — {reason}",
        session_id=session_id,
        action_type=action_type,
        hierarchy_level=hierarchy_level if hierarchy_level in _VALID_LEVELS else LEVEL_JARVIS_PA,
        risk_level=risk_level,
        context_evidence=evidence,
        nus_learning_tags=nus_learning_tags or ["nus1f", "session_decision"],
        policy_reference=policy_reference,
        blocking_reason=reason if decision == DECISION_BLOCKED else "",
    )
    return record.to_dict()


def build_action_decision_record(
    action_type: str,
    decision: str,
    reason: str,
    evidence: Dict[str, Any],
    session_id: str = "",
    hierarchy_level: str = LEVEL_JARVIS_PA,
    risk_level: str = RISK_LOW,
    policy_reference: str = "nus1f_action_policy",
    validation_evidence: Optional[List[Dict[str, Any]]] = None,
    rollback_evidence: Optional[Dict[str, Any]] = None,
    nus_learning_tags: Optional[List[str]] = None,
    agent_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a structured decision record for an action evaluation."""
    record = StructuredDecisionRecord(
        record_id=str(uuid.uuid4()),
        created_at=time.time(),
        schema_version=NUS1F_DECISION_RECORD_VERSION,
        decision=decision if decision in _VALID_DECISIONS else DECISION_BLOCKED,
        reason=reason,
        rationale=f"Action decision: {decision} for {action_type!r} — {reason}",
        session_id=session_id,
        action_type=action_type,
        hierarchy_level=hierarchy_level if hierarchy_level in _VALID_LEVELS else LEVEL_JARVIS_PA,
        risk_level=risk_level,
        context_evidence=evidence,
        validation_evidence=validation_evidence or [],
        rollback_evidence=rollback_evidence or {},
        agent_metadata=agent_metadata or {},
        nus_learning_tags=nus_learning_tags or ["nus1f", "action_decision"],
        policy_reference=policy_reference,
        blocking_reason=reason if decision == DECISION_BLOCKED else "",
    )
    return record.to_dict()


def get_decision_record_status() -> Dict[str, Any]:
    """Return schema status for decision records."""
    return {
        "schema_version": NUS1F_DECISION_RECORD_VERSION,
        "valid_decisions": sorted(_VALID_DECISIONS),
        "valid_hierarchy_levels": sorted(_VALID_LEVELS),
        "no_raw_chain_of_thought": True,
        "generic_for_all_levels": True,
        "nus_hierarchy_coverage": [
            LEVEL_JARVIS_PA, LEVEL_COS_GM, LEVEL_MANAGER,
            LEVEL_WORKER, LEVEL_VALIDATOR, LEVEL_GOVERNANCE,
        ],
        "future_proof": True,
        "schema_additive_only": True,
    }
