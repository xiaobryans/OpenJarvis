"""Rules Registry — file-backed storage for Jarvis rules.

Stores rules as JSON in ~/.openjarvis/rules/rules.json.
Thread-safe via a simple lock.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.rules.types import Rule, RuleScope, RuleStatus, make_rule_id


_DEFAULT_DIR = Path("~/.openjarvis/rules/").expanduser()
_LOCK = threading.Lock()


class RuleRegistry:
    """In-process singleton registry for Jarvis rules.

    All writes persist to a JSON file; reads are served from the in-memory cache.
    """

    _instance: Optional["RuleRegistry"] = None
    _rules: Dict[str, Rule]
    _store_path: Path

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        dir_path = store_dir or _DEFAULT_DIR
        dir_path.mkdir(parents=True, exist_ok=True)
        self._store_path = dir_path / "rules.json"
        self._rules = {}
        self._load()

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, store_dir: Optional[Path] = None) -> "RuleRegistry":
        if cls._instance is None:
            cls._instance = cls(store_dir=store_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton — used in tests."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text())
            for entry in data.get("rules", []):
                rule = Rule.from_dict(entry)
                self._rules[rule.rule_id] = rule
        except Exception:
            pass

    def _save(self) -> None:
        payload = {"rules": [r.to_dict() for r in self._rules.values()]}
        self._store_path.write_text(json.dumps(payload, indent=2))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, rule: Rule) -> Rule:
        with _LOCK:
            if not rule.rule_id:
                rule.rule_id = make_rule_id()
            self._rules[rule.rule_id] = rule
            self._save()
        return rule

    def get(self, rule_id: str) -> Optional[Rule]:
        return self._rules.get(rule_id)

    def update(self, rule_id: str, updates: Dict[str, Any]) -> Optional[Rule]:
        with _LOCK:
            rule = self._rules.get(rule_id)
            if rule is None:
                return None
            for key, value in updates.items():
                if hasattr(rule, key) and key not in ("rule_id", "created_at"):
                    setattr(rule, key, value)
            rule.updated_at = time.time()
            self._save()
        return rule

    def deactivate(self, rule_id: str) -> Optional[Rule]:
        return self.update(rule_id, {"status": RuleStatus.INACTIVE})

    def activate(self, rule_id: str) -> Optional[Rule]:
        return self.update(rule_id, {"status": RuleStatus.ACTIVE})

    def delete(self, rule_id: str) -> bool:
        with _LOCK:
            if rule_id not in self._rules:
                return False
            del self._rules[rule_id]
            self._save()
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_all(self) -> List[Rule]:
        return list(self._rules.values())

    def list_active(self) -> List[Rule]:
        return [r for r in self._rules.values() if r.status == RuleStatus.ACTIVE]

    def list_by_scope(self, scope: str) -> List[Rule]:
        return [r for r in self._rules.values() if r.scope == scope]

    def list_by_scope_id(self, scope: str, scope_id: str) -> List[Rule]:
        return [
            r for r in self._rules.values()
            if r.scope == scope and r.scope_id == scope_id
        ]

    def list_for_context(self, project_id: str = "", action_type: str = "") -> List[Rule]:
        """Return active rules that could apply to the given context."""
        matching: List[Rule] = []
        for rule in self._rules.values():
            if rule.status != RuleStatus.ACTIVE:
                continue
            if rule.scope == RuleScope.GLOBAL:
                matching.append(rule)
            elif rule.scope == RuleScope.PROJECT and project_id and rule.scope_id == project_id:
                matching.append(rule)
            elif rule.scope in (RuleScope.CONTEXT, RuleScope.USER):
                matching.append(rule)
        return sorted(matching, key=lambda r: -r.priority)

    def detect_conflicts(self, new_rule: Rule) -> List[str]:
        """Return rule_ids that may conflict with new_rule (opposite effects on same target)."""
        _CONTRADICTIONS = {("allow", "block"), ("block", "allow"), ("enable", "disable"), ("disable", "enable")}
        conflicts: List[str] = []
        for existing in self._rules.values():
            if existing.rule_id == new_rule.rule_id:
                continue
            a_effect = existing.action.get("effect")
            b_effect = new_rule.action.get("effect")
            if (
                existing.status == RuleStatus.ACTIVE
                and existing.rule_type == new_rule.rule_type
                and existing.scope == new_rule.scope
                and (not existing.scope_id or existing.scope_id == new_rule.scope_id)
                and existing.action.get("target") == new_rule.action.get("target")
                and (a_effect, b_effect) in _CONTRADICTIONS
            ):
                conflicts.append(existing.rule_id)
        return conflicts

    def stats(self) -> Dict[str, int]:
        rules = list(self._rules.values())
        return {
            "total": len(rules),
            "active": sum(1 for r in rules if r.status == RuleStatus.ACTIVE),
            "inactive": sum(1 for r in rules if r.status == RuleStatus.INACTIVE),
            "conflicted": sum(1 for r in rules if r.status == RuleStatus.CONFLICTED),
            "draft": sum(1 for r in rules if r.status == RuleStatus.DRAFT),
        }
