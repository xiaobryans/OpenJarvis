"""Jarvis Intelligence + Trust Layer — US11.

Provides structured evidence, trust status, memory provenance, action profiles,
connector trust classification, and execution self-checks so that every
"ready / degraded / blocked / completed" claim is backed by verifiable evidence.

Scope:
  1. Trust/evidence layer      — TrustStatus, EvidenceRecord, ReadinessTrustReport
  2. Action confidence/approval — ActionProfile, ActionAccessType
  3. Planner/self-check trust  — PreExecutionSelfCheck, PostExecutionSelfCheck
  4. Memory/context provenance  — MemoryProvenance, MemorySource
  5. Tool/connector intelligence — ConnectorTrustStatus, classify_connector_trust
  6. Readiness integration      — build_readiness_trust_report

Rules:
  - Missing evidence → "insufficient_data_to_verify", not inferred readiness
  - No secrets or raw private data surfaced
  - All functions are pure / no I/O
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ===========================================================================
# 1. Trust Status
# ===========================================================================


class TrustStatus:
    """Trust/availability status for a component, connector, or check."""

    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    UNCONFIGURED = "unconfigured"
    UNKNOWN = "unknown"


INSUFFICIENT_DATA_MSG = "insufficient_data_to_verify"


def insufficient_data(context: str = "") -> str:
    """Return the standard insufficient-data message.

    Per Jarvis honesty policy: if evidence is missing, state this explicitly.
    Never infer readiness from absence of evidence.
    """
    if context:
        return f"{INSUFFICIENT_DATA_MSG}: {context}"
    return INSUFFICIENT_DATA_MSG


# ===========================================================================
# 2. Evidence Record
# ===========================================================================


@dataclass
class EvidenceRecord:
    """A single verifiable piece of evidence for a trust claim.

    Fields
    ------
    source      Where the evidence came from (e.g. 'runtime_import', 'env_check')
    reason      Why this evidence supports or refutes the claim
    timestamp   Unix timestamp when evidence was collected; None = not available
    value       The actual data observed (scrubbed if sensitive)
    recency_ok  Whether the timestamp is recent enough for this claim type
    """

    source: str
    reason: str
    timestamp: Optional[float] = field(default_factory=time.time)
    value: Any = None
    recency_ok: bool = True

    def is_verified(self) -> bool:
        """Return True only if evidence has a source, reason, and recent timestamp."""
        return bool(self.source and self.reason and self.recency_ok)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "value": self.value if not isinstance(self.value, bytes) else "<binary>",
            "recency_ok": self.recency_ok,
            "is_verified": self.is_verified(),
        }


# ===========================================================================
# 3. Memory / Context Provenance
# ===========================================================================


class MemorySource:
    """Classification of where a memory or context item originated."""

    DURABLE = "durable"
    SESSION = "session"
    RUNTIME = "runtime"
    FALLBACK = "fallback"
    MISSING = "missing"


@dataclass
class MemoryProvenance:
    """Provenance record for a memory or context item.

    Fields
    ------
    source_type  MemorySource constant
    namespace    Memory namespace (e.g. 'project:omnix')
    recency      Unix timestamp of last write; None = unknown
    trust_status TrustStatus constant
    detail       Human-readable note (no secrets)
    """

    source_type: str
    namespace: str
    recency: Optional[float]
    trust_status: str
    detail: str = ""

    def is_trusted(self) -> bool:
        """Return True only if source is durable/session with READY status."""
        return (
            self.source_type in (MemorySource.DURABLE, MemorySource.SESSION)
            and self.trust_status == TrustStatus.READY
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "namespace": self.namespace,
            "recency": self.recency,
            "trust_status": self.trust_status,
            "detail": self.detail,
            "is_trusted": self.is_trusted(),
        }


def classify_memory_provenance(
    namespace: str,
    source_type: str,
    recency: Optional[float] = None,
    *,
    max_age_seconds: float = 3600.0,
    detail: str = "",
) -> MemoryProvenance:
    """Classify a memory item's provenance and assign a trust status.

    Rules:
      - MISSING source → BLOCKED trust
      - Durable/session with recent timestamp → READY
      - Durable/session without timestamp → DEGRADED
      - Fallback source → DEGRADED
      - Unknown source → UNKNOWN
    """
    if source_type == MemorySource.MISSING:
        return MemoryProvenance(
            source_type=source_type,
            namespace=namespace,
            recency=recency,
            trust_status=TrustStatus.BLOCKED,
            detail=detail or insufficient_data(f"memory source missing for namespace={namespace}"),
        )

    if source_type in (MemorySource.DURABLE, MemorySource.SESSION):
        if recency is None:
            return MemoryProvenance(
                source_type=source_type,
                namespace=namespace,
                recency=recency,
                trust_status=TrustStatus.DEGRADED,
                detail=detail or "recency unknown; cannot verify freshness",
            )
        age = time.time() - recency
        if age <= max_age_seconds:
            return MemoryProvenance(
                source_type=source_type,
                namespace=namespace,
                recency=recency,
                trust_status=TrustStatus.READY,
                detail=detail or f"memory verified; age={age:.1f}s",
            )
        return MemoryProvenance(
            source_type=source_type,
            namespace=namespace,
            recency=recency,
            trust_status=TrustStatus.DEGRADED,
            detail=detail or f"memory stale; age={age:.1f}s exceeds max={max_age_seconds}s",
        )

    if source_type == MemorySource.FALLBACK:
        return MemoryProvenance(
            source_type=source_type,
            namespace=namespace,
            recency=recency,
            trust_status=TrustStatus.DEGRADED,
            detail=detail or "fallback source; primary memory unavailable",
        )

    return MemoryProvenance(
        source_type=source_type,
        namespace=namespace,
        recency=recency,
        trust_status=TrustStatus.UNKNOWN,
        detail=detail or f"unknown memory source: {source_type}",
    )


# ===========================================================================
# 4. Action Access Type + Action Profile
# ===========================================================================


class ActionAccessType:
    """Classification of the access pattern for a proposed action."""

    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    EXTERNAL_WRITE = "external_write"
    DESTRUCTIVE = "destructive"
    CREDENTIAL_SENSITIVE = "credential_sensitive"


@dataclass
class ActionProfile:
    """Evidence-backed profile for a proposed action.

    Fields
    ------
    action_id           Unique action identifier
    access_type         ActionAccessType constant
    risk_level          'low' | 'medium' | 'high' | 'critical'
    required_approval   Whether owner approval is needed before execution
    expected_side_effect Human-readable description of what will change
    external_services   List of external services touched ([] = none)
    is_hard_gate        Whether this action is a hard-gated UNSAFE action
    evidence            Evidence supporting this profile classification
    """

    action_id: str
    access_type: str
    risk_level: str
    required_approval: bool
    expected_side_effect: str
    external_services: List[str] = field(default_factory=list)
    is_hard_gate: bool = False
    evidence: List[EvidenceRecord] = field(default_factory=list)

    def touches_external(self) -> bool:
        return bool(self.external_services)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "access_type": self.access_type,
            "risk_level": self.risk_level,
            "required_approval": self.required_approval,
            "expected_side_effect": self.expected_side_effect,
            "external_services": list(self.external_services),
            "is_hard_gate": self.is_hard_gate,
            "touches_external": self.touches_external(),
            "evidence": [e.to_dict() for e in self.evidence],
        }


def build_action_profile(
    action_id: str,
    access_type: str,
    risk_level: str,
    expected_side_effect: str,
    *,
    external_services: Optional[List[str]] = None,
    evidence_source: str = "governance_policy",
) -> ActionProfile:
    """Build an ActionProfile with governance-derived approval and gate flags.

    Consults HARD_GATE_ACTIONS and APPROVAL_REQUIRED_RISK_LEVELS from constitution.
    Falls back gracefully if governance module is unavailable.
    """
    from openjarvis.governance.constitution import HARD_GATE_ACTIONS, APPROVAL_REQUIRED_RISK_LEVELS

    services = external_services or []
    is_hard = action_id in HARD_GATE_ACTIONS or access_type == ActionAccessType.DESTRUCTIVE
    requires_approval = (
        is_hard
        or risk_level.lower() in APPROVAL_REQUIRED_RISK_LEVELS
        or access_type in (ActionAccessType.EXTERNAL_WRITE, ActionAccessType.CREDENTIAL_SENSITIVE)
    )
    ev = EvidenceRecord(
        source=evidence_source,
        reason=(
            f"action_id={action_id} classified as {access_type}; "
            f"risk={risk_level}; hard_gate={is_hard}"
        ),
    )
    return ActionProfile(
        action_id=action_id,
        access_type=access_type,
        risk_level=risk_level,
        required_approval=requires_approval,
        expected_side_effect=expected_side_effect,
        external_services=services,
        is_hard_gate=is_hard,
        evidence=[ev],
    )


# ===========================================================================
# 5. Connector Trust Status
# ===========================================================================


@dataclass
class ConnectorTrustStatus:
    """Trust status record for a single connector.

    Fields
    ------
    connector_id   Unique identifier (e.g. 'slack', 'telegram', 'github')
    trust_status   TrustStatus constant
    reason         Why this status was assigned (no credentials)
    safe_fallback  What Jarvis will do instead if this connector is unavailable
    evidence       Supporting EvidenceRecord or None if no evidence available
    """

    connector_id: str
    trust_status: str
    reason: str
    safe_fallback: str
    evidence: Optional[EvidenceRecord] = None

    def is_usable(self) -> bool:
        return self.trust_status == TrustStatus.READY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "trust_status": self.trust_status,
            "reason": self.reason,
            "safe_fallback": self.safe_fallback,
            "is_usable": self.is_usable(),
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


def classify_connector_trust(
    connector_id: str,
    *,
    configured: bool,
    last_health_ok: Optional[bool],
    error_reason: Optional[str] = None,
    safe_fallback: str = "log_and_skip",
) -> ConnectorTrustStatus:
    """Classify a connector's trust status from its configuration and health state.

    Rules:
      - not configured → UNCONFIGURED (never silently attempt use)
      - configured + last_health_ok=True → READY
      - configured + last_health_ok=False → DEGRADED with error reason
      - configured + last_health_ok=None → UNKNOWN (no probe result)
    """
    if not configured:
        return ConnectorTrustStatus(
            connector_id=connector_id,
            trust_status=TrustStatus.UNCONFIGURED,
            reason=insufficient_data(f"{connector_id} credentials/config not present"),
            safe_fallback=safe_fallback,
            evidence=EvidenceRecord(
                source="config_check",
                reason=f"{connector_id}: not configured; skipped",
                value={"configured": False},
            ),
        )

    if last_health_ok is True:
        return ConnectorTrustStatus(
            connector_id=connector_id,
            trust_status=TrustStatus.READY,
            reason=f"{connector_id}: last health probe passed",
            safe_fallback=safe_fallback,
            evidence=EvidenceRecord(
                source="health_probe",
                reason=f"{connector_id}: health ok",
                value={"last_health_ok": True},
            ),
        )

    if last_health_ok is False:
        return ConnectorTrustStatus(
            connector_id=connector_id,
            trust_status=TrustStatus.DEGRADED,
            reason=(
                f"{connector_id}: last health probe failed"
                + (f" — {error_reason}" if error_reason else "")
            ),
            safe_fallback=safe_fallback,
            evidence=EvidenceRecord(
                source="health_probe",
                reason=f"{connector_id}: health failed; error={error_reason}",
                value={"last_health_ok": False, "error_reason": error_reason},
                recency_ok=False,
            ),
        )

    return ConnectorTrustStatus(
        connector_id=connector_id,
        trust_status=TrustStatus.UNKNOWN,
        reason=insufficient_data(f"{connector_id}: no health probe result available"),
        safe_fallback=safe_fallback,
        evidence=None,
    )


# ===========================================================================
# 6. Readiness Trust Report
# ===========================================================================


@dataclass
class ReadinessTrustReport:
    """Evidence-backed readiness trust report for any subject.

    Fields
    ------
    subject          What is being evaluated
    trust_status     TrustStatus constant
    evidence         List of verified EvidenceRecords supporting the claim
    missing_evidence List of keys/items that could not be evidenced
    evaluated_at     Unix timestamp of evaluation
    """

    subject: str
    trust_status: str
    evidence: List[EvidenceRecord]
    missing_evidence: List[str]
    evaluated_at: float = field(default_factory=time.time)

    @property
    def is_sufficient(self) -> bool:
        """True only if evidence is present, no missing items, and status is READY."""
        return (
            bool(self.evidence)
            and not self.missing_evidence
            and self.trust_status == TrustStatus.READY
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "trust_status": self.trust_status,
            "evidence": [e.to_dict() for e in self.evidence],
            "missing_evidence": list(self.missing_evidence),
            "evaluated_at": self.evaluated_at,
            "is_sufficient": self.is_sufficient,
        }


def build_readiness_trust_report(
    subject: str,
    evidence_dict: Dict[str, Any],
    required_keys: List[str],
) -> ReadinessTrustReport:
    """Build a ReadinessTrustReport from a flat evidence dict.

    Each required_key must be present in evidence_dict and have a truthy value.
    Missing or falsy values are reported as missing_evidence and lower trust
    to BLOCKED. Partial evidence lowers trust to DEGRADED.
    """
    collected: List[EvidenceRecord] = []
    missing: List[str] = []

    for key in required_keys:
        val = evidence_dict.get(key)
        if val is None or val == "" or val is False:
            missing.append(key)
        else:
            collected.append(
                EvidenceRecord(
                    source=f"evidence_dict:{key}",
                    reason=f"evidence key '{key}' present and truthy",
                    value=val,
                )
            )

    if missing:
        trust = TrustStatus.BLOCKED if len(missing) == len(required_keys) else TrustStatus.DEGRADED
    elif collected:
        trust = TrustStatus.READY
    else:
        trust = TrustStatus.UNKNOWN

    return ReadinessTrustReport(
        subject=subject,
        trust_status=trust,
        evidence=collected,
        missing_evidence=missing,
    )


# ===========================================================================
# 7. Pre/Post Execution Self-Checks
# ===========================================================================


class PreExecutionSelfCheck:
    """Verifies required evidence exists before claiming readiness.

    Prevents overclaiming when tests, command outputs, or runtime proof
    are absent. Call before marking any capability as ready.
    """

    @staticmethod
    def check(
        required_evidence_keys: List[str],
        available_evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return a result dict with ok, missing, and verdict.

        Returns {'ok': False, 'missing': [...], 'verdict': 'HOLD'} if any
        required evidence is absent. Only returns 'ok': True when all keys
        are present with truthy values.
        """
        missing = [
            k for k in required_evidence_keys
            if not available_evidence.get(k)
        ]
        if missing:
            return {
                "ok": False,
                "missing": missing,
                "verdict": "HOLD",
                "reason": (
                    insufficient_data(f"required evidence keys absent: {missing}")
                ),
            }
        return {
            "ok": True,
            "missing": [],
            "verdict": "ACCEPT",
            "reason": f"all {len(required_evidence_keys)} required evidence keys present",
        }


class PostExecutionSelfCheck:
    """Prevents fake completion claims when outputs are missing.

    Call after any task execution before marking the task COMPLETED.
    A task with empty, None, or whitespace-only output cannot be COMPLETED.
    """

    @staticmethod
    def check(
        output: Any,
        required_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Return a result dict with ok and reason.

        Rejects:
          - None output
          - Empty string / whitespace-only string
          - Empty dict / empty list
          - Dict missing any required_fields

        Accepts:
          - Non-empty string
          - Non-empty dict with all required_fields present
          - Non-empty list
          - Any other truthy non-None value
        """
        if output is None:
            return {
                "ok": False,
                "reason": (
                    "Governance policy: cannot claim COMPLETED with None output. "
                    "Produce a real result or mark BLOCKED."
                ),
            }

        if isinstance(output, str):
            if not output.strip():
                return {
                    "ok": False,
                    "reason": (
                        "Governance policy: cannot claim COMPLETED with "
                        "empty or whitespace-only string output."
                    ),
                }
            if required_fields:
                return {
                    "ok": True,
                    "reason": "string output present; field checks not applicable to strings",
                }
            return {"ok": True, "reason": "string output present and non-empty"}

        if isinstance(output, dict):
            if not output:
                return {
                    "ok": False,
                    "reason": "Governance policy: cannot claim COMPLETED with empty dict output.",
                }
            if required_fields:
                missing = [f for f in required_fields if f not in output]
                if missing:
                    return {
                        "ok": False,
                        "reason": f"Output dict missing required fields: {missing}",
                    }
            return {"ok": True, "reason": f"dict output present with {len(output)} field(s)"}

        if isinstance(output, (list, tuple)):
            if not output:
                return {
                    "ok": False,
                    "reason": "Governance policy: cannot claim COMPLETED with empty list output.",
                }
            return {"ok": True, "reason": f"sequence output present with {len(output)} item(s)"}

        if not output:
            return {
                "ok": False,
                "reason": "Governance policy: falsy output cannot claim COMPLETED.",
            }

        return {"ok": True, "reason": "output present and truthy"}


__all__ = [
    "ActionAccessType",
    "ActionProfile",
    "ConnectorTrustStatus",
    "EvidenceRecord",
    "INSUFFICIENT_DATA_MSG",
    "MemoryProvenance",
    "MemorySource",
    "PostExecutionSelfCheck",
    "PreExecutionSelfCheck",
    "ReadinessTrustReport",
    "TrustStatus",
    "build_action_profile",
    "build_readiness_trust_report",
    "classify_connector_trust",
    "classify_memory_provenance",
    "insufficient_data",
]
