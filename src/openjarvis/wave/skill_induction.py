"""Epic A — Skill Induction Pipeline (Wave 1).

Validates skill manifests before registration/execution.
Rejects unsafe manifests. Safe manifests are registered into WaveSkillRegistry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Unsafe pattern detection
# ---------------------------------------------------------------------------

_UNSAFE_COMMAND_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?i)\brm\s+-rf\b"),
    re.compile(r"(?i)\bdrop\s+table\b"),
    re.compile(r"(?i)\bformat\s+c:\b"),
    re.compile(r"(?i)\bmkfs\b"),
    re.compile(r"(?i)\bdd\s+if="),
    re.compile(r"(?i)\bsudo\s+rm\b"),
    re.compile(r"(?i)\bgit\s+push\s+--force\b"),
    re.compile(r"(?i)\bkill\s+-9\b"),
]

_UNSAFE_CAPABILITY_PATTERNS: List[str] = [
    "secret",
    "credential",
    "password",
    "api_key",
    "token",
    "slack_send",
    "email_send",
    "telegram_send",
    "deploy",
    "release",
    "approval_bypass",
    "captcha_bypass",
    "browser_uncontrolled",
]

_APPROVAL_REQUIRED_TAGS: frozenset = frozenset({
    "terminal",
    "shell",
    "browser",
    "write",
    "destructive",
    "git_push",
    "deploy",
    "high_risk",
})

_HARD_GATE_TAGS: frozenset = frozenset({
    "external_send",
    "slack",
    "email",
    "telegram",
    "production_deploy",
    "secrets_access",
})


@dataclass
class InductionViolation:
    kind: str
    detail: str


@dataclass
class InductionValidationResult:
    valid: bool
    violations: List[InductionViolation] = field(default_factory=list)
    approval_required: bool = False
    hard_gate: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "violations": [{"kind": v.kind, "detail": v.detail} for v in self.violations],
            "approval_required": self.approval_required,
            "hard_gate": self.hard_gate,
            "warnings": self.warnings,
        }


def validate_skill_manifest(manifest_dict: Dict[str, Any]) -> InductionValidationResult:
    """Validate a skill manifest dict before induction.

    Checks:
    - Required fields present
    - No unsafe capability names
    - No destructive command patterns in description/steps
    - Tags that require approval or hard-gate
    """
    violations: List[InductionViolation] = []
    warnings: List[str] = []
    approval_required = False
    hard_gate = False

    # Required fields
    if not manifest_dict.get("skill_id"):
        violations.append(InductionViolation("missing_field", "skill_id is required"))
    if not manifest_dict.get("name"):
        violations.append(InductionViolation("missing_field", "name is required"))

    # Check unsafe capability patterns
    combined_text = " ".join([
        str(manifest_dict.get("skill_id", "")),
        str(manifest_dict.get("name", "")),
        str(manifest_dict.get("description", "")),
        " ".join(str(t) for t in manifest_dict.get("required_tool_ids", [])),
        " ".join(str(t) for t in manifest_dict.get("tags", [])),
    ]).lower()

    for pattern in _UNSAFE_CAPABILITY_PATTERNS:
        if pattern in combined_text:
            violations.append(InductionViolation(
                "unsafe_capability",
                f"Manifest references unsafe capability: '{pattern}'",
            ))

    # Check destructive command patterns
    for pat in _UNSAFE_COMMAND_PATTERNS:
        if pat.search(combined_text):
            violations.append(InductionViolation(
                "destructive_command",
                f"Manifest contains destructive command pattern: {pat.pattern}",
            ))

    # Check tags for approval requirements
    tags = set(str(t).lower() for t in manifest_dict.get("tags", []))
    if tags & _HARD_GATE_TAGS:
        hard_gate = True
        violations.append(InductionViolation(
            "hard_gate_tag",
            f"Manifest has hard-gate tags: {tags & _HARD_GATE_TAGS}",
        ))
    elif tags & _APPROVAL_REQUIRED_TAGS:
        approval_required = True
        warnings.append(f"Manifest has approval-required tags: {tags & _APPROVAL_REQUIRED_TAGS}")

    # Check explicit approval_policy field
    policy = manifest_dict.get("approval_policy", "")
    if policy == "hard_gate":
        hard_gate = True
    elif policy == "requires_approval":
        approval_required = True

    # Risk level check
    risk = manifest_dict.get("risk_level", "medium")
    if risk in ("high", "critical"):
        approval_required = True
        warnings.append(f"Manifest has risk_level={risk} — approval required for execution")

    valid = len(violations) == 0
    return InductionValidationResult(
        valid=valid,
        violations=violations,
        approval_required=approval_required,
        hard_gate=hard_gate,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Induction result + pipeline
# ---------------------------------------------------------------------------

@dataclass
class InductionResult:
    skill_id: str
    ok: bool
    status: str  # accepted | rejected | pending_approval | hard_gate_blocked
    validation: Optional[InductionValidationResult] = None
    error: str = ""
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "ok": self.ok,
            "status": self.status,
            "validation": self.validation.to_dict() if self.validation else None,
            "error": self.error,
            "event_id": self.event_id,
        }


def _log_induction_event(skill_id: str, ok: bool, status: str, detail: str) -> str:
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log = WorkbenchEventLog()
        etype = "skill_inducted" if ok else "skill_induction_blocked"
        ev = log.push(
            session_id="wave1_induction",
            task_id=skill_id,
            event_type=etype,
            title=f"Skill induction {status}: {skill_id}",
            detail=detail,
            tone="success" if ok else ("error" if status == "hard_gate_blocked" else "warning"),
            metadata={"skill_id": skill_id, "status": status},
        )
        return ev.id
    except Exception:
        return ""


def induce_skill(manifest_dict: Dict[str, Any]) -> InductionResult:
    """Validate and register a skill manifest.

    Pipeline:
    1. Validate manifest for safety violations
    2. If hard-gate: reject immediately
    3. If approval_required: register as pending_approval
    4. If valid + no approval needed: register as ready
    """
    skill_id = manifest_dict.get("skill_id", "<unknown>")
    validation = validate_skill_manifest(manifest_dict)

    if not validation.valid:
        eid = _log_induction_event(
            skill_id, False, "rejected",
            f"{len(validation.violations)} violation(s): {validation.violations[0].detail if validation.violations else ''}"
        )
        return InductionResult(
            skill_id=skill_id,
            ok=False,
            status="rejected" if not validation.hard_gate else "hard_gate_blocked",
            validation=validation,
            error=f"Validation failed: {validation.violations[0].detail if validation.violations else 'unknown'}",
            event_id=eid,
        )

    if validation.hard_gate:
        eid = _log_induction_event(skill_id, False, "hard_gate_blocked",
                                    "Hard-gate skill blocked from induction")
        return InductionResult(
            skill_id=skill_id,
            ok=False,
            status="hard_gate_blocked",
            validation=validation,
            error="Hard-gate skill requires explicit owner approval — not inductible via pipeline",
            event_id=eid,
        )

    # Register into WaveSkillRegistry
    from openjarvis.wave.skill_platform import WaveSkillManifest, get_skill_registry
    from openjarvis.wave.skill_platform import (
        APPROVAL_POLICY_REQUIRES_APPROVAL, APPROVAL_POLICY_AUTO, APPROVAL_POLICY_HARD_GATE
    )

    policy = manifest_dict.get("approval_policy", APPROVAL_POLICY_REQUIRES_APPROVAL)
    induction_approved = not validation.approval_required

    wave_manifest = WaveSkillManifest(
        skill_id=skill_id,
        name=manifest_dict.get("name", skill_id),
        version=manifest_dict.get("version", "0.1.0"),
        description=manifest_dict.get("description", ""),
        author=manifest_dict.get("author", "jarvis"),
        tags=manifest_dict.get("tags", []),
        required_tool_ids=manifest_dict.get("required_tool_ids", []),
        approval_policy=policy,
        risk_level=manifest_dict.get("risk_level", "medium"),
        induction_approved=induction_approved,
        evidence={"inducted_via": "skill_induction_pipeline", "validation": validation.to_dict()},
    )

    reg = get_skill_registry()
    reg_result = reg.register(wave_manifest, bypass_approval_check=True)

    if validation.approval_required:
        status = "pending_approval"
        eid = _log_induction_event(skill_id, False, status,
                                    f"Requires approval: {validation.warnings}")
        return InductionResult(
            skill_id=skill_id,
            ok=False,
            status=status,
            validation=validation,
            error=f"Skill inducted as pending_approval — requires explicit owner approval before execution",
            event_id=eid,
        )

    eid = _log_induction_event(skill_id, True, "accepted", "Skill inducted successfully")
    return InductionResult(
        skill_id=skill_id,
        ok=True,
        status="accepted",
        validation=validation,
        event_id=eid,
    )


def get_induction_pipeline_status() -> Dict[str, Any]:
    return {
        "implemented": True,
        "validation_checks": [
            "required_fields",
            "unsafe_capability_patterns",
            "destructive_command_patterns",
            "hard_gate_tags",
            "approval_required_tags",
            "risk_level",
        ],
        "hard_gate_tags": sorted(_HARD_GATE_TAGS),
        "approval_required_tags": sorted(_APPROVAL_REQUIRED_TAGS),
    }


__all__ = [
    "InductionViolation",
    "InductionValidationResult",
    "InductionResult",
    "validate_skill_manifest",
    "induce_skill",
    "get_induction_pipeline_status",
]
