"""Personality / Policy Drift Guard — detects and prevents Jarvis OS policy violations.

Ensures stable, policy-compliant behavior across all agents, devices, and turns.

Guards against:
  1. Fake readiness — claiming ACCEPT without evidence
  2. Hidden blockers — silently deferring required work
  3. Over-acceptance — accepting incomplete work as done
  4. Validation skipping — running fewer checks than required
  5. Tone/personality drift — soft language that conceals real status
  6. Cross-device inconsistency — different status on different devices

Verifier and Sentinel can call DriftGuard to flag violations.
Drift guard is callable in the runtime flow.

Sprint: Full No-Gap Jarvis — Combined Sprint 3 FINAL HOLD Correction
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Drift types
# ---------------------------------------------------------------------------

class DriftType(str, Enum):
    FAKE_READINESS = "FAKE_READINESS"
    HIDDEN_BLOCKER = "HIDDEN_BLOCKER"
    OVER_ACCEPTANCE = "OVER_ACCEPTANCE"
    VALIDATION_SKIP = "VALIDATION_SKIP"
    TONE_DRIFT = "TONE_DRIFT"
    CROSS_DEVICE_INCONSISTENCY = "CROSS_DEVICE_INCONSISTENCY"
    POLICY_VIOLATION = "POLICY_VIOLATION"


# ---------------------------------------------------------------------------
# Policy spec — ground truth
# ---------------------------------------------------------------------------

JARVIS_POLICY_SPEC = {
    "no_fake_readiness": True,
    "no_hidden_blockers": True,
    "no_over_acceptance": True,
    "validation_always_required": True,
    "stable_tone_across_devices": True,
    "forbidden_claims": [
        "FULL_NO_GAP_JARVIS_COMPLETE",
        "NO_GAP_JARVIS_CERTIFIED",
        "VOICE_DAILY_DRIVER_ACCEPT",
        "NATIVE_APP_ACCEPT",
        "PUBLIC_RELEASE_ACCEPT",
    ],
    "required_hold_when": [
        "mobile_macbook_off_continuity not verified",
        "voice sprint not completed",
        "native app not built and tested",
        "no-gap certification not run",
    ],
    "manager_behavior_boundaries": {
        "manager-coding": "No deploy ops. No external API sends. Code/test/build only.",
        "manager-research": "No writes to production. Read/search/summarize only.",
        "manager-memory": "No secrets. Cache/memory ops only within allowed scopes.",
        "manager-connector": "No send unless gated. Read connectors freely.",
        "manager-ops-safety": "Gate all writes. Escalate all sensitive ops.",
    },
    "worker_behavior_boundaries": "Workers cannot access secrets or unrelated private state. "
                                  "All worker output must be verified by manager.",
    "verifier_behavior_boundaries": "Verifier cannot verify its own work. "
                                    "Must inspect evidence, not trust claims.",
}

# Drift signal words in agent output
_FAKE_READINESS_SIGNALS = [
    "looks good", "should be fine", "probably works", "assuming it works",
    "good enough", "mostly done", "almost ready", "essentially complete",
]

_TONE_DRIFT_SIGNALS = [
    "great job", "excellent work", "amazing", "fantastic", "wonderful",
    "perfect", "we're all set", "we're done here",
]

_HIDDEN_BLOCKER_SIGNALS = [
    "not needed for now", "can be done later", "optional",
    "skipped for brevity", "deferred", "out of scope for this sprint",
]


# ---------------------------------------------------------------------------
# Drift finding
# ---------------------------------------------------------------------------

@dataclass
class DriftFinding:
    finding_id: str
    drift_type: DriftType
    description: str
    evidence_snippet: str
    fix: str
    severity: str = "HIGH"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "drift_type": self.drift_type.value,
            "description": self.description,
            "evidence_snippet": self.evidence_snippet,
            "fix": self.fix,
            "severity": self.severity,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Drift Guard
# ---------------------------------------------------------------------------

class DriftGuard:
    """Policy/personality drift guard.

    Callable by verifier, sentinel, or company runtime.
    Records all drift findings for audit.
    """

    def __init__(self) -> None:
        self._findings: List[DriftFinding] = []

    def _add(
        self,
        drift_type: DriftType,
        description: str,
        evidence: str,
        fix: str,
        severity: str = "HIGH",
    ) -> DriftFinding:
        f = DriftFinding(
            finding_id=str(uuid.uuid4())[:8],
            drift_type=drift_type,
            description=description,
            evidence_snippet=evidence[:200],
            fix=fix,
            severity=severity,
        )
        self._findings.append(f)
        return f

    def check_fake_readiness(self, text: str) -> List[DriftFinding]:
        """Detect language that implies readiness without evidence."""
        findings = []
        text_lower = text.lower()
        for signal in _FAKE_READINESS_SIGNALS:
            if signal in text_lower:
                f = self._add(
                    DriftType.FAKE_READINESS,
                    f"Fake readiness signal: '{signal}'",
                    signal,
                    f"Replace '{signal}' with exact verification output or HOLD verdict.",
                )
                findings.append(f)
        return findings

    def check_hidden_blockers(self, text: str) -> List[DriftFinding]:
        """Detect language that hides or defers blockers."""
        findings = []
        text_lower = text.lower()
        for signal in _HIDDEN_BLOCKER_SIGNALS:
            if signal in text_lower:
                f = self._add(
                    DriftType.HIDDEN_BLOCKER,
                    f"Potential hidden blocker signal: '{signal}'",
                    signal,
                    f"If '{signal}' conceals a required item, classify it explicitly as HOLD with exact fix list.",
                )
                findings.append(f)
        return findings

    def check_forbidden_claims(self, text: str) -> List[DriftFinding]:
        """Detect forbidden acceptance claims."""
        findings = []
        for claim in JARVIS_POLICY_SPEC["forbidden_claims"]:
            if claim in text:
                f = self._add(
                    DriftType.OVER_ACCEPTANCE,
                    f"Forbidden claim '{claim}' — requires verified evidence that does not exist",
                    claim,
                    f"Remove '{claim}'. Downgrade to HOLD until evidence exists.",
                    severity="CRITICAL",
                )
                findings.append(f)
        return findings

    def check_tone_drift(self, text: str) -> List[DriftFinding]:
        """Detect personality tone drift away from brutal honesty."""
        findings = []
        text_lower = text.lower()
        hits = [s for s in _TONE_DRIFT_SIGNALS if s in text_lower]
        if hits:
            f = self._add(
                DriftType.TONE_DRIFT,
                f"Tone drift detected: {hits}",
                str(hits),
                "Replace with factual status output. No motivational filler.",
                severity="MEDIUM",
            )
            findings.append(f)
        return findings

    def check_validation_skip(
        self,
        claimed_validations: List[str],
        actual_commands_run: List[str],
    ) -> Optional[DriftFinding]:
        """Detect validation commands claimed but not run."""
        missed = [v for v in claimed_validations if v not in actual_commands_run]
        if missed:
            return self._add(
                DriftType.VALIDATION_SKIP,
                f"Validation skip detected: claimed {claimed_validations}, ran {actual_commands_run}",
                str(missed),
                f"Run missing validations: {missed}. Do not claim validated without running.",
                severity="HIGH",
            )
        return None

    def check_cross_device_consistency(
        self,
        macbook_status: str,
        mobile_status: str,
    ) -> Optional[DriftFinding]:
        """Detect inconsistent status between MacBook and mobile."""
        if macbook_status != mobile_status:
            return self._add(
                DriftType.CROSS_DEVICE_INCONSISTENCY,
                f"Cross-device status mismatch: MacBook='{macbook_status}' vs Mobile='{mobile_status}'",
                f"MacBook={macbook_status}, Mobile={mobile_status}",
                "Sync state via always-available continuity backend. "
                "Both devices must report identical status from same source of truth.",
                severity="HIGH",
            )
        return None

    def run_full_guard(
        self,
        text: str,
        claimed_validations: Optional[List[str]] = None,
        actual_commands_run: Optional[List[str]] = None,
        macbook_status: Optional[str] = None,
        mobile_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run all drift checks. Returns findings and verdict."""
        pre_count = len(self._findings)

        self.check_fake_readiness(text)
        self.check_hidden_blockers(text)
        self.check_forbidden_claims(text)
        self.check_tone_drift(text)

        if claimed_validations is not None and actual_commands_run is not None:
            self.check_validation_skip(claimed_validations, actual_commands_run)

        if macbook_status is not None and mobile_status is not None:
            self.check_cross_device_consistency(macbook_status, mobile_status)

        new_findings = self._findings[pre_count:]
        critical = [f for f in new_findings if f.severity == "CRITICAL"]
        verdict = "PASS" if not new_findings else ("CRITICAL" if critical else "DRIFT_DETECTED")

        return {
            "verdict": verdict,
            "new_findings": len(new_findings),
            "critical_findings": len(critical),
            "findings": [f.to_dict() for f in new_findings],
            "policy_spec": JARVIS_POLICY_SPEC,
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_findings": len(self._findings),
            "by_type": {
                dt.value: sum(1 for f in self._findings if f.drift_type == dt)
                for dt in DriftType
            },
            "recent_findings": [f.to_dict() for f in self._findings[-5:]],
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_GUARD: Optional[DriftGuard] = None


def get_drift_guard() -> DriftGuard:
    global _GUARD
    if _GUARD is None:
        _GUARD = DriftGuard()
    return _GUARD


__all__ = [
    "DriftType",
    "JARVIS_POLICY_SPEC",
    "DriftFinding",
    "DriftGuard",
    "get_drift_guard",
]
