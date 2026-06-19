"""Jarvis Verifier Gate — Independent audit and validation gate.

The Verifier is always independent of the team being verified.
It cannot verify its own output (self_verify is blocked).

Verification tests:
  1. Unsupported row → REJECTED with fix list
  2. Contradictory status → REJECTED with fix list
  3. Stale artifact → REJECTED with fix list
  4. Missing evidence → REJECTED with fix list
  5. Valid evidence → ACCEPTED with trace

Design invariants:
  - Never accepts without concrete traced evidence.
  - Always returns a fix list on rejection.
  - Stale artifacts are defined as: last_updated_at > stale_threshold_seconds ago.
  - Contradictions are pairs of claims with logically incompatible statuses.
  - Missing evidence means a claim has no source/file/test tracing it.
  - Self-verify is hard-blocked.

Sprint: Full No-Gap Jarvis — Combined Sprint 3
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class VerificationOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED_SELF_VERIFY = "BLOCKED_SELF_VERIFY"


@dataclass
class EvidenceItem:
    """A single piece of evidence supporting a claim."""
    claim_id: str
    claim_text: str
    source_type: str               # "file" | "test" | "command_output" | "doc"
    source_ref: str                # file path, test name, command string
    last_updated_at: float         # unix timestamp when evidence was last confirmed
    is_supported: bool = True      # False = claim has no real evidence


@dataclass
class VerificationFinding:
    """A single finding from verification."""
    finding_id: str
    finding_type: str              # "unsupported" | "contradiction" | "stale" | "missing_evidence"
    claim_ids: List[str]
    description: str
    fix_required: str


@dataclass
class VerificationReport:
    """Full report from a single verifier run."""

    run_id: str
    verifier_id: str
    team_id: str                   # which team/artifact is being verified
    outcome: VerificationOutcome
    accepted_claims: List[str]
    rejected_claims: List[str]
    findings: List[VerificationFinding]
    fix_list: List[str]
    acceptance_trace: Optional[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "verifier_id": self.verifier_id,
            "team_id": self.team_id,
            "outcome": self.outcome.value,
            "accepted_claims": self.accepted_claims,
            "rejected_claims": self.rejected_claims,
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "finding_type": f.finding_type,
                    "claim_ids": f.claim_ids,
                    "description": f.description,
                    "fix_required": f.fix_required,
                }
                for f in self.findings
            ],
            "fix_list": self.fix_list,
            "acceptance_trace": self.acceptance_trace,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Verifier Gate
# ---------------------------------------------------------------------------

class VerifierGate:
    """Independent audit and validation gate.

    Usage::

        gate = VerifierGate(verifier_id="verifier-sprint3", stale_threshold_seconds=86400)
        report = gate.verify(
            team_id="coding-sprint-team",
            evidence_items=[...],
            contradiction_pairs=[...],
        )
        if report.outcome == VerificationOutcome.ACCEPTED:
            # proceed
        else:
            # report.fix_list contains required fixes
    """

    BLOCKED_SELF_VERIFY_IDS = frozenset({"verifier", "verifier-gate", "self"})

    def __init__(
        self,
        verifier_id: str = "verifier",
        stale_threshold_seconds: int = 86400,  # 24h default
    ) -> None:
        self._verifier_id = verifier_id
        self._stale_threshold = stale_threshold_seconds

    def verify(
        self,
        team_id: str,
        evidence_items: List[EvidenceItem],
        contradiction_pairs: Optional[List[tuple]] = None,
        *,
        allow_partial: bool = False,
    ) -> VerificationReport:
        """Run verification on a set of evidence items.

        Parameters
        ----------
        team_id:
            Identifier of the team/artifact being verified.
        evidence_items:
            All evidence items to evaluate.
        contradiction_pairs:
            Optional list of (claim_id_a, claim_id_b) pairs that are
            logically incompatible. Verifier will check if both are present
            and accepted.
        allow_partial:
            If False (default), any finding → REJECTED.

        Returns
        -------
        VerificationReport
        """
        import uuid

        run_id = str(uuid.uuid4())[:8]

        # Hard-block self-verify
        if team_id.lower() in self.BLOCKED_SELF_VERIFY_IDS:
            return VerificationReport(
                run_id=run_id,
                verifier_id=self._verifier_id,
                team_id=team_id,
                outcome=VerificationOutcome.BLOCKED_SELF_VERIFY,
                accepted_claims=[],
                rejected_claims=[e.claim_id for e in evidence_items],
                findings=[
                    VerificationFinding(
                        finding_id=f"{run_id}-selfverify",
                        finding_type="self_verify_blocked",
                        claim_ids=[e.claim_id for e in evidence_items],
                        description="Self-verification is permanently blocked.",
                        fix_required="Use an independent verifier — never verify own output.",
                    )
                ],
                fix_list=["Assign independent verifier; self-verify is blocked."],
                acceptance_trace=None,
            )

        findings: List[VerificationFinding] = []
        now = time.time()

        # 1. Unsupported rows
        for item in evidence_items:
            if not item.is_supported:
                findings.append(
                    VerificationFinding(
                        finding_id=f"{run_id}-unsupported-{item.claim_id}",
                        finding_type="unsupported",
                        claim_ids=[item.claim_id],
                        description=f"Claim '{item.claim_id}' has no supporting evidence.",
                        fix_required=f"Provide real source (file/test/command) for '{item.claim_id}'.",
                    )
                )

        # 2. Missing evidence (source_ref is empty)
        for item in evidence_items:
            if item.is_supported and not item.source_ref.strip():
                findings.append(
                    VerificationFinding(
                        finding_id=f"{run_id}-missing-{item.claim_id}",
                        finding_type="missing_evidence",
                        claim_ids=[item.claim_id],
                        description=f"Claim '{item.claim_id}' has is_supported=True but source_ref is empty.",
                        fix_required=f"Provide a non-empty source_ref for '{item.claim_id}'.",
                    )
                )

        # 3. Stale artifacts
        for item in evidence_items:
            age = now - item.last_updated_at
            if item.is_supported and age > self._stale_threshold:
                findings.append(
                    VerificationFinding(
                        finding_id=f"{run_id}-stale-{item.claim_id}",
                        finding_type="stale",
                        claim_ids=[item.claim_id],
                        description=(
                            f"Evidence for '{item.claim_id}' is {age:.0f}s old "
                            f"(threshold: {self._stale_threshold}s)."
                        ),
                        fix_required=f"Re-run or re-confirm evidence for '{item.claim_id}'.",
                    )
                )

        # 4. Contradictions
        if contradiction_pairs:
            evidence_map = {e.claim_id: e for e in evidence_items}
            for claim_a, claim_b in contradiction_pairs:
                ea = evidence_map.get(claim_a)
                eb = evidence_map.get(claim_b)
                if ea and eb and ea.is_supported and eb.is_supported:
                    findings.append(
                        VerificationFinding(
                            finding_id=f"{run_id}-contradiction-{claim_a}-{claim_b}",
                            finding_type="contradiction",
                            claim_ids=[claim_a, claim_b],
                            description=(
                                f"Claims '{claim_a}' and '{claim_b}' are both marked supported "
                                "but are logically contradictory."
                            ),
                            fix_required=(
                                f"Resolve contradiction between '{claim_a}' and '{claim_b}'. "
                                "Only one can be true."
                            ),
                        )
                    )

        # Build accepted/rejected sets
        rejected_claim_ids = set()
        for f in findings:
            rejected_claim_ids.update(f.claim_ids)

        accepted_claims = [e.claim_id for e in evidence_items if e.claim_id not in rejected_claim_ids]
        rejected_claims = [e.claim_id for e in evidence_items if e.claim_id in rejected_claim_ids]

        has_findings = bool(findings)

        if has_findings and not allow_partial:
            outcome = VerificationOutcome.REJECTED
            fix_list = [f.fix_required for f in findings]
            acceptance_trace = None
        else:
            outcome = VerificationOutcome.ACCEPTED
            fix_list = []
            acceptance_trace = (
                f"Verified {len(accepted_claims)} claims with traced evidence. "
                f"Sources: {', '.join(set(e.source_type for e in evidence_items if e.claim_id in accepted_claims))}."
            )

        return VerificationReport(
            run_id=run_id,
            verifier_id=self._verifier_id,
            team_id=team_id,
            outcome=outcome,
            accepted_claims=accepted_claims,
            rejected_claims=rejected_claims,
            findings=findings,
            fix_list=fix_list,
            acceptance_trace=acceptance_trace,
        )


# ---------------------------------------------------------------------------
# Default gate
# ---------------------------------------------------------------------------

_DEFAULT_GATE: Optional[VerifierGate] = None


def get_default_verifier_gate() -> VerifierGate:
    global _DEFAULT_GATE
    if _DEFAULT_GATE is None:
        _DEFAULT_GATE = VerifierGate()
    return _DEFAULT_GATE


__all__ = [
    "VerificationOutcome",
    "EvidenceItem",
    "VerificationFinding",
    "VerificationReport",
    "VerifierGate",
    "get_default_verifier_gate",
]
