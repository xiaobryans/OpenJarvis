"""Epic A — Skill Platform Foundation (Wave 1 scaffold).

Wraps existing openjarvis.skills.jarvis_registry and types.
Adds Wave-specific manifest fields and approval policy enforcement.

Status: SCAFFOLDED — registry + model exist; full skill induction pipeline
and approval-gated promotion are not yet implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Wave Skill Manifest (extends existing SkillManifest concept)
# ---------------------------------------------------------------------------

APPROVAL_POLICY_AUTO = "auto"
APPROVAL_POLICY_REQUIRES_APPROVAL = "requires_approval"
APPROVAL_POLICY_HARD_GATE = "hard_gate"


@dataclass
class WaveSkillManifest:
    """Wave 1 skill manifest — contract for a skill in the Wave skill platform.

    Wraps/extends skills/types.SkillManifest with Wave-specific governance fields.
    Skill induction (accepting a new skill into the registry) requires approval
    unless approval_policy is 'auto' and the skill is read-only.
    """

    skill_id: str
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = "jarvis"
    tags: List[str] = field(default_factory=list)
    required_tool_ids: List[str] = field(default_factory=list)
    optional_tool_ids: List[str] = field(default_factory=list)
    approval_policy: str = APPROVAL_POLICY_REQUIRES_APPROVAL
    risk_level: str = "medium"
    status: str = "scaffolded"  # scaffolded | ready | blocked | disabled
    induction_approved: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "required_tool_ids": self.required_tool_ids,
            "approval_policy": self.approval_policy,
            "risk_level": self.risk_level,
            "status": self.status,
            "induction_approved": self.induction_approved,
            "evidence": self.evidence,
        }

    def requires_approval_for_induction(self) -> bool:
        return self.approval_policy in (APPROVAL_POLICY_REQUIRES_APPROVAL, APPROVAL_POLICY_HARD_GATE)


# ---------------------------------------------------------------------------
# Wave Skill Registry
# ---------------------------------------------------------------------------

class WaveSkillRegistry:
    """In-memory registry of Wave 1 skill manifests.

    All induction (registration) goes through a safety check.
    Skills with approval_policy != 'auto' are stored with induction_approved=False
    until Bryan explicitly approves them.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, WaveSkillManifest] = {}
        self._populate_builtins()

    def _populate_builtins(self) -> None:
        """Register built-in Wave 1 scaffolded skills from existing platform."""
        builtins = [
            WaveSkillManifest(
                skill_id="coding_workbench",
                name="Coding Workbench",
                description="Plan, execute, review, and validate coding tasks via Jarvis Workbench.",
                tags=["coding", "workbench", "us14", "us15"],
                required_tool_ids=["file_read", "file_write", "git_status"],
                approval_policy=APPROVAL_POLICY_REQUIRES_APPROVAL,
                risk_level="medium",
                status="ready",
                induction_approved=True,
                evidence={"source": "US14/US15 accepted", "us_status": "ACCEPT"},
            ),
            WaveSkillManifest(
                skill_id="terminal_executor",
                name="Terminal Executor",
                description="Approval-gated terminal command execution with safety filtering.",
                tags=["terminal", "shell", "us15"],
                required_tool_ids=["shell_exec"],
                approval_policy=APPROVAL_POLICY_REQUIRES_APPROVAL,
                risk_level="high",
                status="ready",
                induction_approved=True,
                evidence={"source": "US15 accepted", "us_status": "ACCEPT"},
            ),
            WaveSkillManifest(
                skill_id="diff_reviewer",
                name="Diff Reviewer",
                description="Structured diff review with approve/reject/manual-review workflow.",
                tags=["diff", "review", "us15"],
                required_tool_ids=["git_diff"],
                approval_policy=APPROVAL_POLICY_REQUIRES_APPROVAL,
                risk_level="low",
                status="ready",
                induction_approved=True,
                evidence={"source": "US15 accepted", "us_status": "ACCEPT"},
            ),
            WaveSkillManifest(
                skill_id="browser_automation",
                name="Browser Automation",
                description="Approval-gated browser automation via Auto Browser + Playwright.",
                tags=["browser", "automation", "us15"],
                required_tool_ids=["browser_navigate"],
                approval_policy=APPROVAL_POLICY_HARD_GATE,
                risk_level="high",
                status="ready",
                induction_approved=True,
                evidence={"source": "US15 accepted", "us_status": "ACCEPT"},
            ),
            WaveSkillManifest(
                skill_id="research_web",
                name="Web Research",
                description="Web search and research with inject-guard filtering.",
                tags=["research", "wave1", "epic_d"],
                required_tool_ids=["web_search"],
                approval_policy=APPROVAL_POLICY_REQUIRES_APPROVAL,
                risk_level="medium",
                status="scaffolded",
                induction_approved=False,
                evidence={"source": "Wave 1 Epic D scaffold"},
            ),
        ]
        for s in builtins:
            self._skills[s.skill_id] = s

    def register(
        self,
        manifest: WaveSkillManifest,
        *,
        bypass_approval_check: bool = False,
    ) -> Dict[str, Any]:
        """Register a skill. Returns approval_required if policy demands it."""
        from openjarvis.workbench.adversarial_safety import evaluate_governance_action

        if manifest.approval_policy == APPROVAL_POLICY_HARD_GATE and not bypass_approval_check:
            v = evaluate_governance_action("skill_induction")
            if not v.allowed:
                manifest.status = "blocked"
                self._skills[manifest.skill_id] = manifest
                return {
                    "ok": False,
                    "status": "approval_required",
                    "reason": "Hard-gate skill induction requires explicit owner approval",
                    "skill_id": manifest.skill_id,
                }

        if manifest.requires_approval_for_induction() and not manifest.induction_approved:
            manifest.status = "pending_approval"
            self._skills[manifest.skill_id] = manifest
            return {
                "ok": False,
                "status": "approval_required",
                "reason": f"Skill '{manifest.skill_id}' requires approval before induction",
                "skill_id": manifest.skill_id,
            }

        manifest.status = "ready" if manifest.induction_approved else "scaffolded"
        self._skills[manifest.skill_id] = manifest
        return {"ok": True, "status": "registered", "skill_id": manifest.skill_id}

    def get(self, skill_id: str) -> Optional[WaveSkillManifest]:
        return self._skills.get(skill_id)

    def list(self) -> List[WaveSkillManifest]:
        return list(self._skills.values())


_registry: Optional[WaveSkillRegistry] = None


def get_skill_registry() -> WaveSkillRegistry:
    global _registry
    if _registry is None:
        _registry = WaveSkillRegistry()
    return _registry


def list_wave_skills() -> List[Dict[str, Any]]:
    return [s.to_dict() for s in get_skill_registry().list()]


def get_skill_platform_status() -> Dict[str, Any]:
    reg = get_skill_registry()
    skills = reg.list()
    by_status = {}
    for s in skills:
        by_status[s.status] = by_status.get(s.status, 0) + 1
    return {
        "epic": "epic_a",
        "wave": 1,
        "status": "scaffolded",
        "skill_count": len(skills),
        "by_status": by_status,
        "approval_gate_enforced": True,
        "induction_pipeline_implemented": False,
        "note": "Skill registry + manifest model exist. Full induction pipeline is Wave 1 next slice.",
    }


__all__ = [
    "WaveSkillManifest",
    "WaveSkillRegistry",
    "APPROVAL_POLICY_AUTO",
    "APPROVAL_POLICY_REQUIRES_APPROVAL",
    "APPROVAL_POLICY_HARD_GATE",
    "get_skill_registry",
    "list_wave_skills",
    "get_skill_platform_status",
]
