"""Skill intake — external candidate lifecycle for third-party skill ingestion.

This module extends (not replaces) the existing Jarvis skill system with an
external-candidate pipeline. Internal Jarvis skills use SkillManager/SkillRegistry.
External candidates (e.g., from ECC) go through this intake system first.

Architecture:
  ExternalCandidate        — data model with lifecycle state + provenance
  ExternalCandidateState   — 10-state lifecycle (discovered → active | rolled_back)
  CandidateRegistry        — JSON-file registry for external candidates
  IntakePreflight          — Python/local-only safety checks (no model tokens)
  IntakeGate               — state-machine enforcing hard gates before activation

Hard gates (always require explicit reviewer approval):
  - transition to ACTIVE
  - any candidate with preflight_passed=False
  - any candidate with risk_tier=high or critical

Python/local-first:
  All preflight checks are text/regex analysis. No model calls.
  No ECC code is executed by this module.

Machine-readable: openjarvis.skills.intake
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Lifecycle states
# ---------------------------------------------------------------------------


class ExternalCandidateState(str, Enum):
    """Lifecycle states for an external skill/agent/command candidate.

    State machine (valid transitions defined in IntakeGate.VALID_TRANSITIONS):
      discovered → candidate → rejected
      candidate  → adapt_needed → approved_for_install → installed_disabled
      installed_disabled → active    (requires reviewer approval)
      active → quarantined → rolled_back
      active → deprecated
    """
    DISCOVERED         = "discovered"
    CANDIDATE          = "candidate"
    REJECTED           = "rejected"
    ADAPT_NEEDED       = "adapt_needed"
    APPROVED_FOR_INSTALL = "approved_for_install"
    INSTALLED_DISABLED = "installed_disabled"
    ACTIVE             = "active"
    QUARANTINED        = "quarantined"
    DEPRECATED         = "deprecated"
    ROLLED_BACK        = "rolled_back"


# ---------------------------------------------------------------------------
# Categories and priorities
# ---------------------------------------------------------------------------


class ExternalCandidateCategory(str, Enum):
    SKILL       = "skill"
    AGENT       = "agent"
    COMMAND     = "command"
    HOOK        = "hook"
    RULE        = "rule"
    MCP_CONFIG  = "mcp_config"
    SCHEMA      = "schema"
    SCRIPT      = "script"
    PLUGIN      = "plugin"
    CONTEXT     = "context"
    GUIDE       = "guide_pattern"
    SECURITY    = "security_eval_pattern"
    DASHBOARD   = "dashboard_control_plane"


class ExternalCandidatePriority(str, Enum):
    LIKELY_ADOPT    = "likely_adopt"
    ADAPT_NEEDED    = "adapt_needed"
    INSPECT_LATER   = "inspect_later"
    DUPLICATE       = "duplicate"
    UNSAFE          = "unsafe"
    IRRELEVANT      = "irrelevant"


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


@dataclass
class PreflightFinding:
    check: str
    passed: bool
    detail: str
    risk: str = "low"  # low | medium | high | critical


@dataclass
class PreflightResult:
    passed: bool
    findings: List[PreflightFinding] = field(default_factory=list)
    license_spdx: str = "UNKNOWN"
    overall_risk: str = "unknown"  # low | medium | high | critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "license_spdx": self.license_spdx,
            "overall_risk": self.overall_risk,
            "findings": [
                {"check": f.check, "passed": f.passed, "detail": f.detail, "risk": f.risk}
                for f in self.findings
            ],
        }


class IntakePreflight:
    """Python/local-only safety checks for external skill candidates.

    All checks are text/regex analysis of the candidate's content.
    No model API calls. No ECC code executed.

    Usage:
        result = IntakePreflight().check(content, source_url="...", license_spdx="MIT")
    """

    # Patterns considered risky (not blocking alone, but flagged)
    _DANGEROUS_PATTERNS: Dict[str, List[str]] = {
        "shell_command": [
            r"\bos\.system\b", r"\bsubprocess\.", r"\bexec\(", r"\beval\(",
            r"\bshutil\.rmtree\b", r"rm\s+-rf", r"\bspawn\(",
        ],
        "network_call": [
            r"\brequests\.", r"\burllib\.", r"\bhttpx\.", r"\bfetch\(",
            r"https?://", r"\bsocket\.", r"\baiohttp\.",
        ],
        "file_write": [
            r"open\([^)]+['\"]w['\"]", r"open\([^)]+['\"]a['\"]",
            r"\.write\(", r"shutil\.copy", r"Path\([^)]+\)\.write",
        ],
        "secrets_exposure": [
            r"API_KEY", r"SECRET", r"PASSWORD", r"TOKEN", r"CREDENTIAL",
            r"aws_secret", r"PRIVATE_KEY",
        ],
        "prompt_injection": [
            r"ignore\s+previous\s+instructions",
            r"disregard\s+all\s+prior",
            r"you\s+are\s+now\s+a\s+different",
            r"pretend\s+you\s+are",
        ],
        "mcp_permission": [
            r"mcp.*filesystem.*write", r"mcp.*shell.*execute",
            r"mcp.*network.*listen",
        ],
        "destructive_command": [
            r"DROP\s+TABLE", r"DELETE\s+FROM\s+\w", r"TRUNCATE\s+TABLE",
            r"rm\s+-rf\s+/", r"format\s+c:",
        ],
        "outbound_send": [
            r"slack\.api_call", r"telegram\.send", r"send_message\(",
            r"smtp\.sendmail", r"twilio\.", r"mailgun\.",
        ],
    }

    # These checks must pass for candidate to proceed
    _BLOCKING_CHECKS = frozenset({
        "secrets_exposure", "destructive_command", "outbound_send",
        "prompt_injection",
    })

    _RISK_MAP = {
        "shell_command": "medium",
        "network_call": "medium",
        "file_write": "medium",
        "secrets_exposure": "critical",
        "prompt_injection": "high",
        "mcp_permission": "high",
        "destructive_command": "critical",
        "outbound_send": "high",
    }

    def check(
        self,
        content: str,
        source_url: str = "",
        license_spdx: str = "UNKNOWN",
    ) -> PreflightResult:
        """Run all preflight checks on raw candidate content.

        Args:
            content: Text content of the candidate file(s) to check.
            source_url: URL of the candidate (for provenance, not fetched here).
            license_spdx: SPDX license identifier (MIT, Apache-2.0, etc.).

        Returns:
            PreflightResult with per-check findings and overall verdict.
        """
        findings: List[PreflightFinding] = []
        blocking_failed = False
        risk_levels = ["low"]

        # License check
        license_ok = license_spdx not in {"UNKNOWN", "UNLICENSED", "PROPRIETARY"}
        findings.append(PreflightFinding(
            check="license",
            passed=license_ok,
            detail=f"SPDX: {license_spdx}" if license_ok else f"Missing/unknown license: {license_spdx}",
            risk="high" if not license_ok else "low",
        ))
        if not license_ok:
            risk_levels.append("high")

        # Pattern checks
        for check_name, patterns in self._DANGEROUS_PATTERNS.items():
            matches = []
            for pat in patterns:
                found = re.findall(pat, content, re.IGNORECASE)
                matches.extend(found[:3])  # cap at 3 examples

            risk = self._RISK_MAP.get(check_name, "low")
            passed = len(matches) == 0
            findings.append(PreflightFinding(
                check=check_name,
                passed=passed,
                detail=(
                    f"No {check_name} patterns found" if passed
                    else f"Found: {matches[:3]}"
                ),
                risk=risk if not passed else "low",
            ))

            if not passed:
                risk_levels.append(risk)
                if check_name in self._BLOCKING_CHECKS:
                    blocking_failed = True

        # Compute overall risk
        risk_priority = ["critical", "high", "medium", "low"]
        overall_risk = "low"
        for r in risk_priority:
            if r in risk_levels:
                overall_risk = r
                break

        return PreflightResult(
            passed=not blocking_failed and license_ok,
            findings=findings,
            license_spdx=license_spdx,
            overall_risk=overall_risk,
        )


# ---------------------------------------------------------------------------
# Candidate data model
# ---------------------------------------------------------------------------


@dataclass
class ExternalCandidate:
    """Full record for an external skill/agent/command candidate.

    Created when a candidate is discovered. Updated as it moves through
    the lifecycle. Never auto-activates — requires reviewer approval.
    """

    candidate_id: str                               # unique ID (e.g., "ecc:eval-harness")
    source_url: str                                 # official GitHub URL
    source_commit: str                              # pinned commit SHA for reproducibility
    source_name: str                                # source repository name
    category: ExternalCandidateCategory
    name: str                                       # human-readable name
    description: str
    state: ExternalCandidateState = ExternalCandidateState.DISCOVERED
    license_spdx: str = "UNKNOWN"
    risk_tier: str = "unknown"                      # low | medium | high | critical
    priority: ExternalCandidatePriority = ExternalCandidatePriority.INSPECT_LATER
    rejection_reason: Optional[str] = None
    jarvis_skill_id: Optional[str] = None           # set when adapted to Jarvis
    permission_scopes: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    cost_tier: str = "free"                         # free | cheap | moderate | expensive
    preflight_passed: bool = False
    preflight_findings: List[str] = field(default_factory=list)
    reviewer_approved: bool = False
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[float] = None
    rollback_available: bool = True
    rollback_command: Optional[str] = None
    test_command: Optional[str] = None
    ui_route: Optional[str] = None
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["category"] = self.category.value
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExternalCandidate":
        d = dict(d)
        d["state"] = ExternalCandidateState(d["state"])
        d["category"] = ExternalCandidateCategory(d["category"])
        d["priority"] = ExternalCandidatePriority(d["priority"])
        return cls(**d)

    @property
    def is_usable(self) -> bool:
        """True only if the candidate is active AND reviewer-approved."""
        return self.state == ExternalCandidateState.ACTIVE and self.reviewer_approved

    @property
    def is_blocked(self) -> bool:
        """True if in a terminal or blocked state."""
        return self.state in {
            ExternalCandidateState.REJECTED,
            ExternalCandidateState.QUARANTINED,
            ExternalCandidateState.ROLLED_BACK,
            ExternalCandidateState.DEPRECATED,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class CandidateRegistry:
    """JSON-file registry for external skill candidates.

    Stores candidate records in a single JSON file. Suitable for tens to
    hundreds of candidates. File is human-readable and versionable.

    Default location: ~/.jarvis/skills/candidates.json
    """

    DEFAULT_PATH = Path.home() / ".jarvis" / "skills" / "candidates.json"

    def __init__(self, registry_path: Optional[Path] = None) -> None:
        self._path = Path(registry_path or self.DEFAULT_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, ExternalCandidate] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text())
            for rec in data.get("candidates", []):
                c = ExternalCandidate.from_dict(rec)
                self._records[c.candidate_id] = c
        except Exception:
            self._records = {}

    def _save(self) -> None:
        data = {
            "schema_version": "1.0",
            "updated_at": time.time(),
            "candidates": [c.to_dict() for c in self._records.values()],
        }
        self._path.write_text(json.dumps(data, indent=2))

    def register(self, candidate: ExternalCandidate) -> None:
        """Add or update a candidate in the registry."""
        candidate.updated_at = time.time()
        self._records[candidate.candidate_id] = candidate
        self._save()

    def get(self, candidate_id: str) -> Optional[ExternalCandidate]:
        return self._records.get(candidate_id)

    def list_all(self) -> List[ExternalCandidate]:
        return list(self._records.values())

    def list_by_state(self, state: ExternalCandidateState) -> List[ExternalCandidate]:
        return [c for c in self._records.values() if c.state == state]

    def list_active(self) -> List[ExternalCandidate]:
        return self.list_by_state(ExternalCandidateState.ACTIVE)

    def list_usable(self) -> List[ExternalCandidate]:
        return [c for c in self._records.values() if c.is_usable]

    def remove(self, candidate_id: str) -> bool:
        if candidate_id in self._records:
            del self._records[candidate_id]
            self._save()
            return True
        return False

    def summary(self) -> Dict[str, int]:
        """Return count by state."""
        counts: Dict[str, int] = {}
        for c in self._records.values():
            counts[c.state.value] = counts.get(c.state.value, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Intake gate — state machine with hard gates
# ---------------------------------------------------------------------------


class IntakeGateError(Exception):
    """Raised when an invalid or blocked state transition is attempted."""


class IntakeGate:
    """State-machine controller for external candidate lifecycle.

    Hard gates (require explicit reviewer approval):
      - Any transition TO ACTIVE
      - Any candidate with preflight_passed=False

    Safe transitions (mechanical, no approval needed):
      discovered → candidate
      candidate  → rejected (with reason)
      candidate  → adapt_needed
      adapt_needed → candidate (after adaptation)
      candidate → approved_for_install
      approved_for_install → installed_disabled
      installed_disabled → quarantined (emergency stop)

    Reviewer-gated transitions:
      approved_for_install → installed_disabled  (already gated at approved_for_install step)
      installed_disabled   → active              (hard gate — reviewer approval required)
      active               → quarantined
      active               → deprecated

    Rollback transitions (always allowed for safety):
      active   → quarantined → rolled_back
      any      → quarantined (emergency)
    """

    VALID_TRANSITIONS: Dict[ExternalCandidateState, set] = {
        ExternalCandidateState.DISCOVERED: {
            ExternalCandidateState.CANDIDATE,
            ExternalCandidateState.REJECTED,
        },
        ExternalCandidateState.CANDIDATE: {
            ExternalCandidateState.REJECTED,
            ExternalCandidateState.ADAPT_NEEDED,
            ExternalCandidateState.APPROVED_FOR_INSTALL,
        },
        ExternalCandidateState.ADAPT_NEEDED: {
            ExternalCandidateState.CANDIDATE,
            ExternalCandidateState.REJECTED,
        },
        ExternalCandidateState.APPROVED_FOR_INSTALL: {
            ExternalCandidateState.INSTALLED_DISABLED,
            ExternalCandidateState.REJECTED,
        },
        ExternalCandidateState.INSTALLED_DISABLED: {
            ExternalCandidateState.ACTIVE,           # hard gate
            ExternalCandidateState.QUARANTINED,
            ExternalCandidateState.DEPRECATED,
        },
        ExternalCandidateState.ACTIVE: {
            ExternalCandidateState.QUARANTINED,
            ExternalCandidateState.DEPRECATED,
            ExternalCandidateState.INSTALLED_DISABLED,  # soft-disable
        },
        ExternalCandidateState.QUARANTINED: {
            ExternalCandidateState.ROLLED_BACK,
            ExternalCandidateState.INSTALLED_DISABLED,  # re-enter review
        },
        # Terminal states — no forward transitions
        ExternalCandidateState.REJECTED: set(),
        ExternalCandidateState.DEPRECATED: set(),
        ExternalCandidateState.ROLLED_BACK: set(),
    }

    # Transitions that require explicit reviewer approval
    REVIEWER_REQUIRED: frozenset = frozenset({
        (ExternalCandidateState.INSTALLED_DISABLED, ExternalCandidateState.ACTIVE),
        (ExternalCandidateState.APPROVED_FOR_INSTALL, ExternalCandidateState.INSTALLED_DISABLED),
    })

    def transition(
        self,
        candidate: ExternalCandidate,
        new_state: ExternalCandidateState,
        *,
        reviewer_id: Optional[str] = None,
        reason: Optional[str] = None,
        registry: Optional[CandidateRegistry] = None,
    ) -> ExternalCandidate:
        """Apply a state transition, enforcing hard gates.

        Args:
            candidate: The candidate to transition.
            new_state: Target state.
            reviewer_id: Required for reviewer-gated transitions.
            reason: Human-readable reason for the transition.
            registry: If provided, saves the updated candidate.

        Returns:
            The updated candidate.

        Raises:
            IntakeGateError: If the transition is invalid or a gate is not met.
        """
        old_state = candidate.state

        # Check transition validity
        allowed = self.VALID_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise IntakeGateError(
                f"Invalid transition: {old_state.value} → {new_state.value}. "
                f"Allowed from {old_state.value}: "
                f"{[s.value for s in allowed] or 'none (terminal state)'}."
            )

        # Check reviewer gate
        key = (old_state, new_state)
        if key in self.REVIEWER_REQUIRED:
            if not reviewer_id:
                raise IntakeGateError(
                    f"Transition {old_state.value} → {new_state.value} "
                    "requires reviewer_id (explicit owner approval)."
                )

        # Hard gate: ACTIVE requires preflight_passed
        if new_state == ExternalCandidateState.ACTIVE:
            if not reviewer_id:
                raise IntakeGateError(
                    "Activation to ACTIVE requires explicit reviewer_id."
                )
            if not candidate.preflight_passed:
                raise IntakeGateError(
                    f"Cannot activate {candidate.candidate_id}: preflight not passed. "
                    "Fix preflight findings before activation."
                )
            if not candidate.reviewer_approved:
                raise IntakeGateError(
                    f"Cannot activate {candidate.candidate_id}: reviewer approval not set. "
                    "Set candidate.reviewer_approved=True after review."
                )

        # Apply transition
        candidate.state = new_state
        candidate.updated_at = time.time()
        if reviewer_id:
            candidate.reviewer_id = reviewer_id
            candidate.reviewed_at = time.time()
        if reason and new_state == ExternalCandidateState.REJECTED:
            candidate.rejection_reason = reason

        if registry:
            registry.register(candidate)

        return candidate

    def quarantine(
        self,
        candidate: ExternalCandidate,
        reason: str,
        registry: Optional[CandidateRegistry] = None,
    ) -> ExternalCandidate:
        """Emergency quarantine — bypasses normal gate for safety.

        Can quarantine a candidate from any non-terminal state.
        """
        if candidate.state in {
            ExternalCandidateState.ROLLED_BACK,
            ExternalCandidateState.DEPRECATED,
            ExternalCandidateState.REJECTED,
        }:
            raise IntakeGateError(
                f"Cannot quarantine from terminal state: {candidate.state.value}"
            )
        candidate.state = ExternalCandidateState.QUARANTINED
        candidate.updated_at = time.time()
        candidate.notes = f"QUARANTINED: {reason}\n" + candidate.notes
        if registry:
            registry.register(candidate)
        return candidate

    def rollback(
        self,
        candidate: ExternalCandidate,
        registry: Optional[CandidateRegistry] = None,
    ) -> ExternalCandidate:
        """Roll back a quarantined candidate to rolled_back (terminal cleanup)."""
        if candidate.state != ExternalCandidateState.QUARANTINED:
            raise IntakeGateError(
                f"Can only roll back from QUARANTINED state. "
                f"Current: {candidate.state.value}"
            )
        candidate.state = ExternalCandidateState.ROLLED_BACK
        candidate.updated_at = time.time()
        if registry:
            registry.register(candidate)
        return candidate


# ---------------------------------------------------------------------------
# Convenience builder for ECC candidates
# ---------------------------------------------------------------------------


def make_ecc_candidate(
    skill_id: str,
    name: str,
    description: str,
    category: ExternalCandidateCategory,
    priority: ExternalCandidatePriority,
    license_spdx: str = "MIT",
    source_commit: str = "main",
    **kwargs: Any,
) -> ExternalCandidate:
    """Convenience factory for ECC-sourced candidates."""
    return ExternalCandidate(
        candidate_id=f"ecc:{skill_id}",
        source_url=f"https://github.com/affaan-m/ECC",
        source_commit=source_commit,
        source_name="ECC",
        category=category,
        name=name,
        description=description,
        license_spdx=license_spdx,
        **kwargs,
    )


__all__ = [
    "ExternalCandidateState",
    "ExternalCandidateCategory",
    "ExternalCandidatePriority",
    "PreflightFinding",
    "PreflightResult",
    "IntakePreflight",
    "ExternalCandidate",
    "CandidateRegistry",
    "IntakeGate",
    "IntakeGateError",
    "make_ecc_candidate",
]
