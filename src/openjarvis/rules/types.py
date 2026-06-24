"""Rules Engine — data types for Jarvis rule definitions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RuleScope(str, Enum):
    GLOBAL = "global"       # applies to all sessions/projects
    PROJECT = "project"     # scoped to a project_id
    CONTEXT = "context"     # scoped to a specific context key
    USER = "user"           # user-defined personal rules


class RuleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CONFLICTED = "conflicted"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


class RuleType(str, Enum):
    BEHAVIORAL = "behavioral"   # governs how Jarvis responds
    FILTER = "filter"           # blocks or allows certain content/actions
    TRIGGER = "trigger"         # activates on matching conditions
    CONTEXT = "context"         # sets contextual defaults for a scope
    SAFETY = "safety"           # safety/approval constraints


class RuleSafetyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RuleCondition:
    """Activation condition for a rule.

    Fields
    ------
    match_type      all | any | none
    criteria        list of {field, operator, value} dicts
    """
    match_type: str = "all"  # all | any | none
    criteria: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"match_type": self.match_type, "criteria": self.criteria}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuleCondition":
        return cls(
            match_type=d.get("match_type", "all"),
            criteria=d.get("criteria", []),
        )


@dataclass
class Rule:
    """A single Jarvis rule entry.

    Fields
    ------
    rule_id         Unique identifier
    name            Short human-readable name
    description     What this rule does
    rule_type       behavioral | filter | trigger | context | safety
    scope           global | project | context | user
    status          active | inactive | conflicted | draft | deprecated
    priority        Higher integer = higher precedence (0–100)
    condition       Activation condition (when does the rule apply?)
    action          What the rule enforces (free-form dict, interpreted by engine)
    scope_id        project_id or context key if scope != global
    source          user | system | imported
    safety_level    low | medium | high
    created_at      Unix timestamp
    updated_at      Unix timestamp
    """
    rule_id: str
    name: str
    description: str
    rule_type: str
    scope: str
    status: str
    priority: int
    condition: Dict[str, Any]
    action: Dict[str, Any]
    scope_id: str = ""
    source: str = "user"
    safety_level: str = "low"
    tags: List[str] = field(default_factory=list)
    conflict_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "scope": self.scope,
            "status": self.status,
            "priority": self.priority,
            "condition": self.condition,
            "action": self.action,
            "scope_id": self.scope_id,
            "source": self.source,
            "safety_level": self.safety_level,
            "tags": self.tags,
            "conflict_ids": self.conflict_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Rule":
        return cls(
            rule_id=d["rule_id"],
            name=d.get("name", ""),
            description=d.get("description", ""),
            rule_type=d.get("rule_type", RuleType.BEHAVIORAL),
            scope=d.get("scope", RuleScope.GLOBAL),
            status=d.get("status", RuleStatus.ACTIVE),
            priority=d.get("priority", 50),
            condition=d.get("condition", {}),
            action=d.get("action", {}),
            scope_id=d.get("scope_id", ""),
            source=d.get("source", "user"),
            safety_level=d.get("safety_level", "low"),
            tags=d.get("tags", []),
            conflict_ids=d.get("conflict_ids", []),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )


@dataclass
class RuleContext:
    """Context passed to the rules engine during evaluation.

    Fields
    ------
    session_id      Active session ID
    project_id      Active project ID (empty string if none)
    action_type     The type of action being considered
    metadata        Additional key-value context for condition matching
    """
    session_id: str = ""
    project_id: str = ""
    action_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "action_type": self.action_type,
            "metadata": self.metadata,
        }


@dataclass
class RuleSet:
    """A named collection of rules with a shared scope."""
    name: str
    scope: str
    rules: List[Rule] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope,
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules],
        }


def make_rule_id() -> str:
    return f"rule_{uuid.uuid4().hex[:12]}"
