"""Specialist agent registry — configuration records for all 12 specialist agents.

These are NOT running workers or BaseAgent subclass registrations.
They are config records the MissionRouter uses to assign tasks and enforce
permission / escalation policy.

Default agents:
    manager, architect, coding, research, testing_bug, qa,
    docs_report, security_risk, deployment, browser, email, reminders
"""

from __future__ import annotations

from typing import Dict, List, Optional

from openjarvis.mission.models import AgentStatus, SpecialistAgentSpec

# ---------------------------------------------------------------------------
# Default specialist agent definitions
# ---------------------------------------------------------------------------

_DEFAULTS: List[SpecialistAgentSpec] = [
    SpecialistAgentSpec(
        agent_id="manager",
        display_name="Manager Agent",
        role="manager",
        capabilities=["plan", "decompose", "coordinate", "delegate", "supervise"],
        permission_level="elevated",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "high", "notify_owner": True},
    ),
    SpecialistAgentSpec(
        agent_id="architect",
        display_name="Architect Agent",
        role="architect",
        capabilities=[
            "design",
            "architecture",
            "system_design",
            "technical_planning",
            "review_plan",
        ],
        permission_level="standard",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "high"},
    ),
    SpecialistAgentSpec(
        agent_id="coding",
        display_name="Coding Agent",
        role="coding",
        capabilities=["code", "implement", "refactor", "fix", "debug", "build", "develop"],
        allowed_tools=["read_file", "write_file", "run_command", "git"],
        permission_level="standard",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "high", "require_review": True},
    ),
    SpecialistAgentSpec(
        agent_id="research",
        display_name="Research Agent",
        role="research",
        capabilities=[
            "research",
            "investigate",
            "search",
            "analyze",
            "summarize",
            "gather_information",
        ],
        allowed_tools=["web_search", "read_url", "read_file"],
        permission_level="minimal",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "medium"},
    ),
    SpecialistAgentSpec(
        agent_id="testing_bug",
        display_name="Testing & Bug Agent",
        role="testing_bug",
        capabilities=[
            "test",
            "verify",
            "validate",
            "bug_report",
            "reproduce_bug",
            "write_tests",
        ],
        allowed_tools=["run_command", "read_file", "write_file"],
        permission_level="standard",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "high"},
    ),
    SpecialistAgentSpec(
        agent_id="qa",
        display_name="QA Agent",
        role="qa",
        capabilities=[
            "qa",
            "quality_assurance",
            "review",
            "acceptance_criteria",
            "sign_off",
        ],
        permission_level="standard",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "high"},
    ),
    SpecialistAgentSpec(
        agent_id="docs_report",
        display_name="Docs & Report Agent",
        role="docs_report",
        capabilities=[
            "document",
            "report",
            "write_docs",
            "summarize",
            "changelog",
            "handoff",
        ],
        allowed_tools=["read_file", "write_file"],
        permission_level="minimal",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "medium"},
    ),
    SpecialistAgentSpec(
        agent_id="security_risk",
        display_name="Security & Risk Agent",
        role="security_risk",
        capabilities=[
            "security",
            "vulnerability",
            "risk_assessment",
            "audit",
            "compliance",
        ],
        permission_level="elevated",
        can_auto_execute_low_risk=False,
        escalation_rules={"risk_threshold": "low", "notify_owner": True},
    ),
    SpecialistAgentSpec(
        agent_id="deployment",
        display_name="Deployment Agent",
        role="deployment",
        capabilities=["deploy", "release", "publish", "rollout", "infrastructure"],
        allowed_tools=["run_command"],
        permission_level="privileged",
        can_auto_execute_low_risk=False,
        escalation_rules={
            "risk_threshold": "low",
            "always_require_approval": True,
            "notify_owner": True,
        },
    ),
    SpecialistAgentSpec(
        agent_id="browser",
        display_name="Browser Agent",
        role="browser",
        capabilities=["browser", "web_automation", "scrape", "navigate", "click"],
        permission_level="standard",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "medium"},
    ),
    SpecialistAgentSpec(
        agent_id="email",
        display_name="Email Agent",
        role="email",
        capabilities=["email", "send_email", "reply_email", "draft_email"],
        permission_level="elevated",
        can_auto_execute_low_risk=False,
        escalation_rules={
            "risk_threshold": "low",
            "always_require_approval": True,
            "notify_owner": True,
        },
    ),
    SpecialistAgentSpec(
        agent_id="reminders",
        display_name="Reminders Agent",
        role="reminders",
        capabilities=["reminder", "schedule", "remind", "calendar", "notification"],
        permission_level="standard",
        can_auto_execute_low_risk=True,
        escalation_rules={"risk_threshold": "medium"},
    ),
]


class SpecialistRegistry:
    """In-memory registry of specialist agent config records.

    Initialized lazily with the 12 default specialists.  Additional specs
    can be registered at runtime via ``register()``.
    """

    _agents: Dict[str, SpecialistAgentSpec] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        if not cls._initialized:
            for spec in _DEFAULTS:
                cls._agents[spec.agent_id] = spec
            cls._initialized = True

    @classmethod
    def get(cls, agent_id: str) -> Optional[SpecialistAgentSpec]:
        cls._ensure_initialized()
        return cls._agents.get(agent_id)

    @classmethod
    def all(cls) -> List[SpecialistAgentSpec]:
        cls._ensure_initialized()
        return list(cls._agents.values())

    @classmethod
    def register(cls, spec: SpecialistAgentSpec) -> None:
        cls._ensure_initialized()
        cls._agents[spec.agent_id] = spec

    @classmethod
    def find_by_capability(cls, capability: str) -> List[SpecialistAgentSpec]:
        """Return agents whose capabilities contain *capability* (case-insensitive)."""
        cls._ensure_initialized()
        cap_lower = capability.lower()
        return [
            spec
            for spec in cls._agents.values()
            if any(cap_lower in c.lower() for c in spec.capabilities)
            and spec.status != AgentStatus.DISABLED
        ]

    @classmethod
    def clear(cls) -> None:
        """Reset to empty (for tests — resets to defaults on next access)."""
        cls._agents.clear()
        cls._initialized = False


_EXPECTED_AGENT_IDS = {
    "manager",
    "architect",
    "coding",
    "research",
    "testing_bug",
    "qa",
    "docs_report",
    "security_risk",
    "deployment",
    "browser",
    "email",
    "reminders",
}

__all__ = [
    "SpecialistRegistry",
    "SpecialistAgentSpec",
    "_EXPECTED_AGENT_IDS",
]
