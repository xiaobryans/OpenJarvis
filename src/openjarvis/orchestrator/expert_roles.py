"""Expert Role Registry — internal expert roles for Jarvis PA orchestration.

Expert roles are used internally behind the scenes.
The user always speaks to one Jarvis PA; roles are never exposed as separate
characters in the final response.

Role types:
  coding        — code review, refactoring, implementation planning
  product       — product thinking, roadmap, UX/UI critique
  research      — deep research, fact-checking, source synthesis
  business      — business analysis, strategy, ops
  security      — security review, risk assessment
  quality       — output quality review, accuracy check
  planner       — task decomposition, sequencing, estimation
  writer        — prose, documentation, communication polish

Safety constraints:
  - No expert role can weaken auth or approval gates.
  - No expert role can print secret values.
  - No expert role can mark work as accepted.
  - Legal/medical/financial roles include mandatory disclaimers.
  - Role selection is audited.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ExpertRole:
    """Definition of a Jarvis internal expert role.

    Fields
    ------
    role_id             Unique identifier
    name                Display name (used in audit logs, not shown to user)
    domain              coding | product | research | business | security |
                        quality | planner | writer | legal | medical | finance
    description         What this role contributes
    trigger_conditions  Keywords/patterns that suggest this role is useful
    safety_level        low | medium | high
    disclaimer          Mandatory disclaimer text (for legal/medical/finance)
    status              active | inactive | deprecated
    created_at          Unix timestamp
    """
    role_id: str
    name: str
    domain: str
    description: str
    trigger_conditions: List[str]
    safety_level: str = "low"
    disclaimer: str = ""
    status: str = "active"
    created_at: float = field(default_factory=time.time)

    def is_active(self) -> bool:
        return self.status == "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "trigger_conditions": self.trigger_conditions,
            "safety_level": self.safety_level,
            "disclaimer": self.disclaimer,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExpertRole":
        return cls(
            role_id=d["role_id"],
            name=d.get("name", ""),
            domain=d.get("domain", ""),
            description=d.get("description", ""),
            trigger_conditions=d.get("trigger_conditions", []),
            safety_level=d.get("safety_level", "low"),
            disclaimer=d.get("disclaimer", ""),
            status=d.get("status", "active"),
            created_at=d.get("created_at", time.time()),
        )


@dataclass
class RoleSelectionRecord:
    """Audit record for a role selection event."""
    record_id: str
    session_id: str
    selected_roles: List[str]  # role_ids
    trigger_text: str
    action_type: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "session_id": self.session_id,
            "selected_roles": self.selected_roles,
            "trigger_text": self.trigger_text,
            "action_type": self.action_type,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Built-in role catalog
# ---------------------------------------------------------------------------

_BUILTIN_ROLES: List[Dict[str, Any]] = [
    {
        "role_id": "role_coding",
        "name": "Coding Expert",
        "domain": "coding",
        "description": "Applies software engineering expertise: code review, refactoring, architecture, debugging, implementation planning.",
        "trigger_conditions": ["code", "implement", "refactor", "debug", "bug", "function", "class", "api", "test", "build"],
        "safety_level": "low",
        "disclaimer": "",
    },
    {
        "role_id": "role_product",
        "name": "Product Expert",
        "domain": "product",
        "description": "Applies product thinking: roadmap, UX critique, feature scoping, user journey, product-market fit.",
        "trigger_conditions": ["product", "feature", "user story", "ux", "ui", "design", "roadmap", "launch", "release"],
        "safety_level": "low",
        "disclaimer": "",
    },
    {
        "role_id": "role_research",
        "name": "Research Expert",
        "domain": "research",
        "description": "Applies deep research: fact-checking, source synthesis, literature review, evidence quality assessment.",
        "trigger_conditions": ["research", "find", "search", "evidence", "study", "paper", "data", "fact", "source"],
        "safety_level": "low",
        "disclaimer": "",
    },
    {
        "role_id": "role_business",
        "name": "Business Expert",
        "domain": "business",
        "description": "Applies business analysis: strategy, operations, competitive analysis, revenue model, org design.",
        "trigger_conditions": ["business", "strategy", "revenue", "market", "customer", "growth", "operations", "competitor"],
        "safety_level": "low",
        "disclaimer": "",
    },
    {
        "role_id": "role_security",
        "name": "Security Reviewer",
        "domain": "security",
        "description": "Reviews for security risks: auth gaps, injection vulnerabilities, secret exposure, permission escalation.",
        "trigger_conditions": ["security", "auth", "token", "secret", "permission", "vulnerability", "inject", "xss", "sql"],
        "safety_level": "medium",
        "disclaimer": "",
    },
    {
        "role_id": "role_quality",
        "name": "Quality Reviewer",
        "domain": "quality",
        "description": "Reviews output quality: accuracy, completeness, logical consistency, no fake claims, hallucination check.",
        "trigger_conditions": ["review", "check", "verify", "accurate", "correct", "quality", "validate"],
        "safety_level": "low",
        "disclaimer": "",
    },
    {
        "role_id": "role_planner",
        "name": "Planning Expert",
        "domain": "planner",
        "description": "Decomposes complex tasks into safe, sequenced steps with dependencies, estimates, and rollback notes.",
        "trigger_conditions": ["plan", "breakdown", "steps", "sequence", "roadmap", "sprint", "task", "milestone"],
        "safety_level": "low",
        "disclaimer": "",
    },
    {
        "role_id": "role_writer",
        "name": "Writing Expert",
        "domain": "writer",
        "description": "Polishes prose, documentation, and communication: clarity, tone, structure, conciseness.",
        "trigger_conditions": ["write", "draft", "email", "document", "explain", "summarize", "report", "blog"],
        "safety_level": "low",
        "disclaimer": "",
    },
    {
        "role_id": "role_legal",
        "name": "Legal Context Reviewer",
        "domain": "legal",
        "description": "Flags legal considerations: contract terms, compliance risks, liability, jurisdiction notes. NOT legal advice.",
        "trigger_conditions": ["legal", "contract", "terms", "compliance", "regulation", "liability", "gdpr", "privacy"],
        "safety_level": "high",
        "disclaimer": "This is not legal advice. Consult a qualified attorney for legal decisions.",
    },
    {
        "role_id": "role_finance",
        "name": "Financial Context Reviewer",
        "domain": "finance",
        "description": "Flags financial considerations: cost models, revenue, risk, cash flow, forecasts. NOT financial advice.",
        "trigger_conditions": ["finance", "budget", "cost", "revenue", "investment", "cashflow", "forecast", "valuation"],
        "safety_level": "high",
        "disclaimer": "This is not financial advice. Consult a qualified financial advisor for investment decisions.",
    },
]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ExpertRoleRegistry:
    """In-process registry for expert roles."""

    _instance: Optional["ExpertRoleRegistry"] = None
    _roles: Dict[str, ExpertRole]

    def __init__(self) -> None:
        self._roles: Dict[str, ExpertRole] = {}
        self._load_builtins()

    @classmethod
    def get_instance(cls) -> "ExpertRoleRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def _load_builtins(self) -> None:
        for d in _BUILTIN_ROLES:
            role = ExpertRole.from_dict(d)
            self._roles[role.role_id] = role

    def get(self, role_id: str) -> Optional[ExpertRole]:
        return self._roles.get(role_id)

    def list_all(self) -> List[ExpertRole]:
        return list(self._roles.values())

    def list_active(self) -> List[ExpertRole]:
        return [r for r in self._roles.values() if r.is_active()]

    def list_by_domain(self, domain: str) -> List[ExpertRole]:
        return [r for r in self._roles.values() if r.domain == domain]

    def activate(self, role_id: str) -> Optional[ExpertRole]:
        role = self._roles.get(role_id)
        if role:
            role.status = "active"
        return role

    def deactivate(self, role_id: str) -> Optional[ExpertRole]:
        role = self._roles.get(role_id)
        if role:
            role.status = "inactive"
        return role

    def stats(self) -> Dict[str, int]:
        roles = list(self._roles.values())
        return {
            "total": len(roles),
            "active": sum(1 for r in roles if r.status == "active"),
            "inactive": sum(1 for r in roles if r.status == "inactive"),
        }


# ---------------------------------------------------------------------------
# Role selector
# ---------------------------------------------------------------------------


class RoleSelector:
    """Selects relevant expert roles based on input text and action type.

    This is an internal routing aid — it does not change the user-facing
    Jarvis identity. All role outputs must be synthesized through Jarvis PA.
    """

    def __init__(self, registry: Optional[ExpertRoleRegistry] = None) -> None:
        self._registry = registry or ExpertRoleRegistry.get_instance()

    def select(
        self,
        text: str,
        action_type: str = "",
        max_roles: int = 3,
        include_high_safety: bool = False,
    ) -> List[ExpertRole]:
        """Return up to max_roles relevant active expert roles for the input text."""
        text_lower = text.lower()
        candidates = self._registry.list_active()

        if not include_high_safety:
            candidates = [r for r in candidates if r.safety_level != "high"]

        scored: List[tuple] = []
        for role in candidates:
            score = sum(
                1 for trigger in role.trigger_conditions
                if trigger.lower() in text_lower
            )
            if score > 0:
                scored.append((score, role))

        scored.sort(key=lambda x: -x[0])
        return [role for _, role in scored[:max_roles]]

    def audit_selection(
        self,
        session_id: str,
        selected: List[ExpertRole],
        trigger_text: str,
        action_type: str = "",
    ) -> RoleSelectionRecord:
        return RoleSelectionRecord(
            record_id=f"rsr_{uuid.uuid4().hex[:10]}",
            session_id=session_id,
            selected_roles=[r.role_id for r in selected],
            trigger_text=trigger_text[:200],
            action_type=action_type,
        )
