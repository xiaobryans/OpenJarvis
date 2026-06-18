"""Epic F — Professional Skill Packs (Wave 2).

Built on top of Wave 1 skill manifests and the induction pipeline.

Skill packs group related skills into cohesive workflows.
Each pack has: id, name, purpose, included skill ids, risk level,
approval policy, required capabilities, status, version, test metadata.

Rules:
- External/account/browser/send/deploy workflows remain approval-gated or blocked.
- Risky packs (risk_level=high/critical or approval_policy=requires_approval) require approval.
- Safe packs can run locally without approval.
- No approval bypass.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Pack status constants
# ---------------------------------------------------------------------------

PACK_STATUS_REGISTERED = "registered"
PACK_STATUS_VALIDATED = "validated"
PACK_STATUS_ENABLED = "enabled"
PACK_STATUS_DISABLED = "disabled"
PACK_STATUS_PENDING_APPROVAL = "pending_approval"
PACK_STATUS_BLOCKED = "blocked"

PACK_POLICY_AUTO = "auto"
PACK_POLICY_REQUIRES_APPROVAL = "requires_approval"
PACK_POLICY_HARD_GATE = "hard_gate"

# These tags trigger approval requirement
_APPROVAL_REQUIRED_TAGS = frozenset({
    "browser", "terminal", "deploy", "release", "git_push",
    "external_send", "write_files", "high_risk",
})

_HARD_GATE_TAGS = frozenset({
    "production_deploy", "slack_send", "email_send", "secrets_access",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SkillPackManifest:
    pack_id: str
    name: str
    version: str
    purpose: str
    included_skill_ids: List[str] = field(default_factory=list)
    risk_level: str = "low"
    approval_policy: str = PACK_POLICY_AUTO
    required_capabilities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    status: str = PACK_STATUS_REGISTERED
    description: str = ""
    eval_metadata: Dict[str, Any] = field(default_factory=dict)

    def requires_approval(self) -> bool:
        tags = set(self.tags)
        if tags & _HARD_GATE_TAGS:
            return True
        if tags & _APPROVAL_REQUIRED_TAGS:
            return True
        if self.approval_policy in (PACK_POLICY_REQUIRES_APPROVAL, PACK_POLICY_HARD_GATE):
            return True
        if self.risk_level in ("high", "critical"):
            return True
        return False

    def is_hard_gate(self) -> bool:
        return (
            bool(set(self.tags) & _HARD_GATE_TAGS)
            or self.approval_policy == PACK_POLICY_HARD_GATE
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "version": self.version,
            "purpose": self.purpose,
            "included_skill_ids": self.included_skill_ids,
            "risk_level": self.risk_level,
            "approval_policy": self.approval_policy,
            "required_capabilities": self.required_capabilities,
            "tags": self.tags,
            "status": self.status,
            "description": self.description,
            "requires_approval": self.requires_approval(),
            "is_hard_gate": self.is_hard_gate(),
        }


@dataclass
class PackExecutionResult:
    pack_id: str
    ok: bool
    output: Any = None
    error: str = ""
    blocked: bool = False
    approval_required: bool = False
    skills_run: List[str] = field(default_factory=list)
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
            "skills_run": self.skills_run,
            "event_id": self.event_id,
        }


# ---------------------------------------------------------------------------
# Built-in skill packs (founder V1)
# ---------------------------------------------------------------------------

def _make_coding_pack() -> SkillPackManifest:
    return SkillPackManifest(
        pack_id="coding_workflow",
        name="Coding Workflow Pack",
        version="1.0.0",
        purpose="Local coding assistance: list skills, check platform status, inspect capabilities",
        included_skill_ids=["list_skills", "platform_status", "list_capabilities"],
        risk_level="low",
        approval_policy=PACK_POLICY_AUTO,
        required_capabilities=["wave1_skill_platform"],
        tags=[],
        status=PACK_STATUS_ENABLED,
        description="Safe local coding workflow. Read-only built-in skills only.",
        eval_metadata={"test_coverage": "unit", "wave": 1},
    )


def _make_research_pack() -> SkillPackManifest:
    return SkillPackManifest(
        pack_id="research_workflow",
        name="Research Workflow Pack",
        version="1.0.0",
        purpose="Local knowledge research: query ingested docs, run local research",
        included_skill_ids=["list_skills", "platform_status"],
        risk_level="low",
        approval_policy=PACK_POLICY_AUTO,
        required_capabilities=["wave1_knowledge_platform", "wave1_research_platform"],
        tags=[],
        status=PACK_STATUS_ENABLED,
        description="Safe local research workflow using Wave 1 knowledge and research platforms.",
        eval_metadata={"test_coverage": "unit", "wave": 1},
    )


def _make_project_ops_pack() -> SkillPackManifest:
    return SkillPackManifest(
        pack_id="project_operations",
        name="Project Operations Pack",
        version="1.0.0",
        purpose="Project status and readiness checks: capabilities, doctor, optimization",
        included_skill_ids=["list_skills", "platform_status", "list_capabilities"],
        risk_level="low",
        approval_policy=PACK_POLICY_AUTO,
        required_capabilities=["wave1_skill_platform", "wave2_optimization_platform"],
        tags=[],
        status=PACK_STATUS_ENABLED,
        description="Local project health checks and optimization scorecard.",
        eval_metadata={"test_coverage": "unit", "wave": 2},
    )


def _make_release_readiness_pack() -> SkillPackManifest:
    return SkillPackManifest(
        pack_id="package_release_readiness",
        name="Package / Release Readiness Pack",
        version="1.0.0",
        purpose="Release readiness checks — read-only, no deploy actions",
        included_skill_ids=["platform_status", "list_capabilities"],
        risk_level="medium",
        approval_policy=PACK_POLICY_AUTO,
        required_capabilities=["wave1_skill_platform"],
        tags=[],
        status=PACK_STATUS_ENABLED,
        description=(
            "Reads platform/capability status for release readiness. "
            "Deploy actions require approval separately."
        ),
        eval_metadata={"test_coverage": "unit", "wave": 2},
    )


def _make_safety_review_pack() -> SkillPackManifest:
    return SkillPackManifest(
        pack_id="safety_review",
        name="Safety / Review Pack",
        version="1.0.0",
        purpose="Safety review workflow: adversarial safety checks, validation profiles",
        included_skill_ids=["list_skills", "platform_status"],
        risk_level="low",
        approval_policy=PACK_POLICY_AUTO,
        required_capabilities=["wave1_skill_platform"],
        tags=[],
        status=PACK_STATUS_ENABLED,
        description="Read-only safety review and validation checks.",
        eval_metadata={"test_coverage": "unit", "wave": 2},
    )


def _make_deploy_pack() -> SkillPackManifest:
    """Deploy pack — hard-gated by policy. Exists for registry completeness."""
    return SkillPackManifest(
        pack_id="deploy_release",
        name="Deploy / Release Pack",
        version="1.0.0",
        purpose="Production deployment — hard-gated, requires explicit owner approval",
        included_skill_ids=[],
        risk_level="critical",
        approval_policy=PACK_POLICY_HARD_GATE,
        required_capabilities=[],
        tags=["production_deploy", "deploy"],
        status=PACK_STATUS_DISABLED,
        description="Hard-gated. Deploy and release actions require explicit owner approval.",
        eval_metadata={"test_coverage": "approval_gate"},
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class SkillPackRegistry:
    """In-memory registry of professional skill packs."""

    def __init__(self) -> None:
        self._packs: Dict[str, SkillPackManifest] = {}
        self._load_builtin_packs()

    def _load_builtin_packs(self) -> None:
        for pack in [
            _make_coding_pack(),
            _make_research_pack(),
            _make_project_ops_pack(),
            _make_release_readiness_pack(),
            _make_safety_review_pack(),
            _make_deploy_pack(),
        ]:
            self._packs[pack.pack_id] = pack

    def register(self, pack: SkillPackManifest) -> Dict[str, Any]:
        if not pack.pack_id:
            return {"ok": False, "error": "pack_id required"}
        self._packs[pack.pack_id] = pack
        return {"ok": True, "pack_id": pack.pack_id, "status": pack.status}

    def get(self, pack_id: str) -> Optional[SkillPackManifest]:
        return self._packs.get(pack_id)

    def list_packs(self) -> List[SkillPackManifest]:
        return list(self._packs.values())

    def list_enabled(self) -> List[SkillPackManifest]:
        return [p for p in self._packs.values() if p.status == PACK_STATUS_ENABLED]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class PackValidationResult:
    pack_id: str
    valid: bool
    approval_required: bool = False
    hard_gate: bool = False
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "valid": self.valid,
            "approval_required": self.approval_required,
            "hard_gate": self.hard_gate,
            "issues": self.issues,
            "warnings": self.warnings,
        }


def validate_skill_pack(pack: SkillPackManifest) -> PackValidationResult:
    """Validate a skill pack manifest for safety and completeness."""
    issues: List[str] = []
    warnings: List[str] = []

    if not pack.pack_id:
        issues.append("pack_id is required")
    if not pack.name:
        issues.append("name is required")
    if not pack.purpose:
        issues.append("purpose is required")

    hard_gate = pack.is_hard_gate()
    if hard_gate:
        issues.append(f"Pack has hard-gate tags/policy: {pack.tags} / {pack.approval_policy}")

    approval_required = pack.requires_approval()
    if approval_required and not hard_gate:
        warnings.append(f"Pack risk_level={pack.risk_level} or tags require approval")

    # Validate included skills exist in Wave 1 registry
    try:
        from openjarvis.wave.skill_platform import get_skill_registry
        reg = get_skill_registry()
        _BUILTIN_SKILLS = {"list_skills", "platform_status", "list_capabilities"}
        for sid in pack.included_skill_ids:
            if sid not in _BUILTIN_SKILLS and reg.get(sid) is None:
                warnings.append(f"Skill '{sid}' not found in registry — will need to be inducted first")
    except Exception:
        pass

    valid = len(issues) == 0
    return PackValidationResult(
        pack_id=pack.pack_id,
        valid=valid,
        approval_required=approval_required,
        hard_gate=hard_gate,
        issues=issues,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Safe local execution
# ---------------------------------------------------------------------------

# Map skill IDs to local handlers (reuse Wave 1 skill_platform handlers)
_SAFE_PACK_SKILL_HANDLERS: Dict[str, Any] = {
    "list_skills": lambda ctx: _exec_list_skills(ctx),
    "platform_status": lambda ctx: _exec_platform_status(ctx),
    "list_capabilities": lambda ctx: _exec_list_capabilities(ctx),
}


def _exec_list_skills(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.wave.skill_platform import list_wave_skills
    skills = list_wave_skills()
    return {"skills": skills, "count": len(skills)}


def _exec_platform_status(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.wave.platform_registry import get_wave_platform_summary
    return get_wave_platform_summary()


def _exec_list_capabilities(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.workbench.capabilities_registry import get_capabilities_summary
    return get_capabilities_summary()


def _log_pack_event(pack_id: str, ok: bool, event_type: str, detail: str) -> str:
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log = WorkbenchEventLog()
        ev = log.push(
            session_id="wave2_skill_packs",
            task_id=pack_id,
            event_type=event_type,
            title=f"Skill pack {event_type}: {pack_id}",
            detail=detail,
            tone="success" if ok else ("error" if "blocked" in event_type else "warning"),
            metadata={"pack_id": pack_id, "ok": ok},
        )
        return ev.id
    except Exception:
        return ""


def run_skill_pack(
    pack_id: str,
    registry: Optional[SkillPackRegistry] = None,
    context: Optional[Dict[str, Any]] = None,
) -> PackExecutionResult:
    """Execute a safe skill pack workflow locally.

    Rules:
    - Hard-gate packs: always blocked.
    - Approval-required packs: blocked until approved.
    - Safe enabled packs: run via local skill handlers.
    """
    reg = registry or SkillPackRegistry()
    pack = reg.get(pack_id)

    if pack is None:
        return PackExecutionResult(
            pack_id=pack_id, ok=False,
            error=f"Skill pack not found: {pack_id}",
        )

    # Hard-gate: always blocked
    if pack.is_hard_gate():
        eid = _log_pack_event(pack_id, False, "skill_pack_blocked",
                               "Hard-gate pack blocked from execution")
        return PackExecutionResult(
            pack_id=pack_id, ok=False, blocked=True,
            error=f"Pack '{pack_id}' is hard-gated — requires explicit owner approval",
            event_id=eid,
        )

    # Requires approval: blocked without explicit approval
    if pack.requires_approval():
        eid = _log_pack_event(pack_id, False, "skill_pack_blocked",
                               f"risk={pack.risk_level} requires approval")
        return PackExecutionResult(
            pack_id=pack_id, ok=False, approval_required=True,
            error=f"Pack '{pack_id}' requires approval (risk={pack.risk_level})",
            event_id=eid,
        )

    # Disabled
    if pack.status in (PACK_STATUS_DISABLED, PACK_STATUS_BLOCKED):
        eid = _log_pack_event(pack_id, False, "skill_pack_blocked",
                               f"Pack status={pack.status}")
        return PackExecutionResult(
            pack_id=pack_id, ok=False, blocked=True,
            error=f"Pack '{pack_id}' is {pack.status}",
            event_id=eid,
        )

    # Execute safe skills
    ctx = context or {}
    outputs: Dict[str, Any] = {}
    skills_run: List[str] = []

    for sid in pack.included_skill_ids:
        handler = _SAFE_PACK_SKILL_HANDLERS.get(sid)
        if handler:
            try:
                outputs[sid] = handler(ctx)
                skills_run.append(sid)
            except Exception as exc:
                outputs[sid] = {"error": str(exc)}
        else:
            # Try Wave 1 run_skill
            try:
                from openjarvis.wave.skill_platform import run_skill
                result = run_skill(sid, ctx)
                outputs[sid] = result.output if result.ok else {"error": result.error}
                if result.ok:
                    skills_run.append(sid)
            except Exception as exc:
                outputs[sid] = {"error": str(exc)}

    eid = _log_pack_event(
        pack_id, True, "skill_pack_executed",
        f"Pack '{pack_id}' ran {len(skills_run)}/{len(pack.included_skill_ids)} skills"
    )

    return PackExecutionResult(
        pack_id=pack_id,
        ok=True,
        output=outputs,
        skills_run=skills_run,
        event_id=eid,
    )


def enable_skill_pack(
    pack_id: str,
    registry: Optional[SkillPackRegistry] = None,
) -> Dict[str, Any]:
    """Enable a skill pack after validation. Hard-gate and risky packs are gated."""
    reg = registry or SkillPackRegistry()
    pack = reg.get(pack_id)

    if pack is None:
        return {"ok": False, "error": f"Pack not found: {pack_id}"}

    validation = validate_skill_pack(pack)
    if not validation.valid:
        eid = _log_pack_event(pack_id, False, "skill_pack_blocked",
                               f"Validation failed: {validation.issues}")
        return {
            "ok": False,
            "blocked": validation.hard_gate,
            "approval_required": validation.approval_required and not validation.hard_gate,
            "error": f"Pack validation failed: {validation.issues}",
            "validation": validation.to_dict(),
            "event_id": eid,
        }

    if validation.hard_gate:
        eid = _log_pack_event(pack_id, False, "skill_pack_blocked", "Hard-gate cannot be enabled")
        return {
            "ok": False,
            "blocked": True,
            "error": "Hard-gate pack cannot be enabled without explicit owner approval",
            "event_id": eid,
        }

    if validation.approval_required:
        eid = _log_pack_event(pack_id, False, "skill_pack_blocked", "Requires approval to enable")
        return {
            "ok": False,
            "approval_required": True,
            "error": f"Pack '{pack_id}' requires approval before enabling",
            "event_id": eid,
        }

    pack.status = PACK_STATUS_ENABLED
    eid = _log_pack_event(pack_id, True, "skill_pack_executed", f"Pack '{pack_id}' enabled")
    return {
        "ok": True,
        "pack_id": pack_id,
        "status": PACK_STATUS_ENABLED,
        "event_id": eid,
    }


def get_professional_skill_packs_status() -> Dict[str, Any]:
    reg = SkillPackRegistry()
    packs = reg.list_packs()
    enabled = reg.list_enabled()
    by_risk = {}
    for p in packs:
        by_risk[p.risk_level] = by_risk.get(p.risk_level, 0) + 1

    return {
        "epic": "epic_f",
        "wave": 2,
        "status": "ready",
        "implemented": True,
        "pack_count": len(packs),
        "enabled_count": len(enabled),
        "by_risk_level": by_risk,
        "approval_gate_enforced": True,
        "hard_gate_enforced": True,
        "wave1_integration": True,
        "builtin_packs": [p.pack_id for p in packs],
        "note": (
            "Wave 2 Epic F: Professional skill packs built on Wave 1 skill platform. "
            "Risky/deploy packs are hard-gated. Safe local packs run immediately."
        ),
    }


__all__ = [
    "SkillPackManifest",
    "SkillPackRegistry",
    "PackValidationResult",
    "PackExecutionResult",
    "validate_skill_pack",
    "run_skill_pack",
    "enable_skill_pack",
    "get_professional_skill_packs_status",
    "PACK_STATUS_REGISTERED",
    "PACK_STATUS_ENABLED",
    "PACK_STATUS_DISABLED",
    "PACK_STATUS_PENDING_APPROVAL",
    "PACK_POLICY_AUTO",
    "PACK_POLICY_REQUIRES_APPROVAL",
    "PACK_POLICY_HARD_GATE",
]
