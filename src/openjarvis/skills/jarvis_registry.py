"""Jarvis Skill Registry — SkillSpec model + SkillRegistry.

A skill is a compound capability composed of one or more tools.
A skill is REAL only if:
  - It has a skill_id, description, required_tool_ids all resolvable in ToolRegistry
  - Its status is computed from actual tool availability
  - It has validation proving it resolves or blocks honestly

Status computation:
  - available   → all required tools are available
  - degraded    → optional tools missing, required tools available
  - blocked     → at least one required tool is blocked/not_configured
  - not_configured → at least one required tool is not_configured
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Skill status
# ---------------------------------------------------------------------------


class SkillStatus:
    AVAILABLE = "available"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_CONFIGURED = "not_configured"
    PLANNED = "planned"


# ---------------------------------------------------------------------------
# SkillSpec — canonical contract
# ---------------------------------------------------------------------------


@dataclass
class SkillSpec:
    """Contract definition for a single Jarvis skill.

    Fields
    ------
    skill_id                 Unique identifier (e.g. 'mission_oversight')
    display_name             Human-readable name
    description              What the skill does
    compatible_agent_ids     Which agents can use this skill
    required_tool_ids        Tools that MUST be available
    optional_tool_ids        Tools that enhance but are not mandatory
    project_scopes           Project IDs this applies to; [] = all projects
    memory_namespaces        Memory namespaces this skill reads/writes
    risk_level               'low' | 'medium' | 'high' | 'critical'
    approval_policy          'auto' | 'requires_approval' | 'hard_gate'
    examples                 Example invocations
    status                   Computed: available/degraded/blocked/not_configured/planned
    blocker                  Reason string if not available
    created_at               Unix timestamp
    """

    skill_id: str
    display_name: str
    description: str
    compatible_agent_ids: List[str]
    required_tool_ids: List[str]
    optional_tool_ids: List[str]
    project_scopes: List[str]
    memory_namespaces: List[str]
    risk_level: str
    approval_policy: str
    examples: List[str]
    status: str = SkillStatus.PLANNED
    blocker: str = ""
    created_at: float = field(default_factory=time.time)

    def is_available(self) -> bool:
        return self.status == SkillStatus.AVAILABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "display_name": self.display_name,
            "description": self.description,
            "compatible_agent_ids": list(self.compatible_agent_ids),
            "required_tool_ids": list(self.required_tool_ids),
            "optional_tool_ids": list(self.optional_tool_ids),
            "project_scopes": list(self.project_scopes),
            "memory_namespaces": list(self.memory_namespaces),
            "risk_level": self.risk_level,
            "approval_policy": self.approval_policy,
            "examples": list(self.examples),
            "status": self.status,
            "is_available": self.is_available(),
            "blocker": self.blocker,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------


class SkillRegistry:
    """Registry of all Jarvis skills.

    Status of each skill is computed from real ToolRegistry state.
    Skills with missing required tools are automatically blocked/not_configured.
    """

    _skills: Dict[str, SkillSpec] = {}

    @classmethod
    def register(cls, spec: SkillSpec) -> None:
        """Register a skill. Status is computed from ToolRegistry at query time."""
        cls._skills[spec.skill_id] = spec

    @classmethod
    def get(cls, skill_id: str) -> Optional[SkillSpec]:
        spec = cls._skills.get(skill_id)
        if spec is None:
            return None
        return cls._compute_status(spec)

    @classmethod
    def list_all(cls) -> List[SkillSpec]:
        """All skills with freshly computed statuses."""
        return [cls._compute_status(s) for s in sorted(cls._skills.values(), key=lambda s: s.skill_id)]

    @classmethod
    def list_available(cls) -> List[SkillSpec]:
        return [s for s in cls.list_all() if s.is_available()]

    @classmethod
    def list_for_agent(cls, agent_id: str) -> List[SkillSpec]:
        """Return all skills (with computed status) compatible with agent_id."""
        return [
            s for s in cls.list_all()
            if not s.compatible_agent_ids or agent_id in s.compatible_agent_ids
        ]

    @classmethod
    def _compute_status(cls, spec: SkillSpec) -> SkillSpec:
        """Derive status from real ToolRegistry tool availability.

        Mutates a copy — original spec is unchanged.
        """
        from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus

        if spec.status == SkillStatus.PLANNED:
            return spec

        missing_required: List[str] = []
        not_configured_required: List[str] = []

        for tool_id in spec.required_tool_ids:
            tool = ToolRegistry.get(tool_id)
            if tool is None:
                missing_required.append(tool_id)
            elif tool.implementation_status == ToolStatus.NOT_CONFIGURED:
                not_configured_required.append(tool_id)
            elif not tool.is_available():
                missing_required.append(tool_id)

        if missing_required:
            import copy
            updated = copy.copy(spec)
            updated.status = SkillStatus.BLOCKED
            updated.blocker = f"Required tools missing/blocked: {missing_required}"
            return updated

        if not_configured_required:
            import copy
            updated = copy.copy(spec)
            updated.status = SkillStatus.NOT_CONFIGURED
            updated.blocker = f"Required tools not configured: {not_configured_required}"
            return updated

        missing_optional: List[str] = []
        for tool_id in spec.optional_tool_ids:
            tool = ToolRegistry.get(tool_id)
            if tool is None or not tool.is_available():
                missing_optional.append(tool_id)

        import copy
        updated = copy.copy(spec)
        if missing_optional:
            updated.status = SkillStatus.DEGRADED
            updated.blocker = f"Optional tools missing: {missing_optional}"
        else:
            updated.status = SkillStatus.AVAILABLE
            updated.blocker = ""
        return updated

    @classmethod
    def stats(cls) -> Dict[str, Any]:
        all_skills = cls.list_all()
        available = [s for s in all_skills if s.status == SkillStatus.AVAILABLE]
        return {
            "total_registered": len(all_skills),
            "available": len(available),
            "by_status": {
                status: sum(1 for s in all_skills if s.status == status)
                for status in [
                    SkillStatus.AVAILABLE,
                    SkillStatus.DEGRADED,
                    SkillStatus.BLOCKED,
                    SkillStatus.NOT_CONFIGURED,
                    SkillStatus.PLANNED,
                ]
            },
        }

    @classmethod
    def clear(cls) -> None:
        """Reset — for tests only."""
        cls._skills.clear()


__all__ = [
    "SkillRegistry",
    "SkillSpec",
    "SkillStatus",
]
