"""Tests for the Jarvis Rules Engine — types, registry, engine."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from openjarvis.rules.types import (
    Rule,
    RuleContext,
    RuleScope,
    RuleStatus,
    RuleType,
    make_rule_id,
)
from openjarvis.rules.registry import RuleRegistry
from openjarvis.rules.engine import RulesEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry(tmp_path: Path) -> RuleRegistry:
    """Return a fresh registry backed by tmp_path."""
    RuleRegistry.reset_instance()
    reg = RuleRegistry(store_dir=tmp_path / "rules")
    return reg


def _rule(
    priority: int = 50,
    scope: str = RuleScope.GLOBAL,
    rule_type: str = RuleType.BEHAVIORAL,
    status: str = RuleStatus.ACTIVE,
    condition: dict = None,
    action: dict = None,
    scope_id: str = "",
    source: str = "user",
) -> Rule:
    return Rule(
        rule_id=make_rule_id(),
        name="test rule",
        description="test",
        rule_type=rule_type,
        scope=scope,
        status=status,
        priority=priority,
        condition=condition or {},
        action=action or {"effect": "allow", "target": "responses"},
        scope_id=scope_id,
        source=source,
        created_at=time.time(),
        updated_at=time.time(),
    )


# ---------------------------------------------------------------------------
# Types tests
# ---------------------------------------------------------------------------


class TestRuleTypes:
    def test_make_rule_id_is_unique(self):
        ids = {make_rule_id() for _ in range(100)}
        assert len(ids) == 100

    def test_rule_to_dict_roundtrip(self):
        rule = _rule()
        d = rule.to_dict()
        restored = Rule.from_dict(d)
        assert restored.rule_id == rule.rule_id
        assert restored.name == rule.name
        assert restored.rule_type == rule.rule_type

    def test_rule_context_to_dict(self):
        ctx = RuleContext(session_id="s1", project_id="p1", action_type="chat")
        d = ctx.to_dict()
        assert d["session_id"] == "s1"
        assert d["project_id"] == "p1"
        assert d["action_type"] == "chat"


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRuleRegistry:
    def test_create_and_get(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule()
        reg.create(rule)
        fetched = reg.get(rule.rule_id)
        assert fetched is not None
        assert fetched.rule_id == rule.rule_id

    def test_create_assigns_id_if_empty(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule()
        rule.rule_id = ""
        reg.create(rule)
        assert rule.rule_id.startswith("rule_")

    def test_list_all(self, tmp_path):
        reg = _registry(tmp_path)
        for _ in range(3):
            reg.create(_rule())
        assert len(reg.list_all()) == 3

    def test_list_active(self, tmp_path):
        reg = _registry(tmp_path)
        reg.create(_rule(status=RuleStatus.ACTIVE))
        reg.create(_rule(status=RuleStatus.INACTIVE))
        reg.create(_rule(status=RuleStatus.DRAFT))
        assert len(reg.list_active()) == 1

    def test_deactivate_and_activate(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule()
        reg.create(rule)
        reg.deactivate(rule.rule_id)
        assert reg.get(rule.rule_id).status == RuleStatus.INACTIVE
        reg.activate(rule.rule_id)
        assert reg.get(rule.rule_id).status == RuleStatus.ACTIVE

    def test_delete(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule()
        reg.create(rule)
        assert reg.delete(rule.rule_id) is True
        assert reg.get(rule.rule_id) is None
        assert reg.delete(rule.rule_id) is False

    def test_update(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule()
        reg.create(rule)
        updated = reg.update(rule.rule_id, {"name": "updated name", "priority": 80})
        assert updated.name == "updated name"
        assert updated.priority == 80

    def test_update_returns_none_for_missing(self, tmp_path):
        reg = _registry(tmp_path)
        assert reg.update("nonexistent", {"name": "x"}) is None

    def test_persistence_roundtrip(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule()
        reg.create(rule)
        # Load fresh registry from same path
        reg2 = RuleRegistry(store_dir=tmp_path / "rules")
        fetched = reg2.get(rule.rule_id)
        assert fetched is not None
        assert fetched.name == rule.name

    def test_list_by_scope(self, tmp_path):
        reg = _registry(tmp_path)
        reg.create(_rule(scope=RuleScope.GLOBAL))
        reg.create(_rule(scope=RuleScope.PROJECT))
        reg.create(_rule(scope=RuleScope.USER))
        assert len(reg.list_by_scope(RuleScope.GLOBAL)) == 1
        assert len(reg.list_by_scope(RuleScope.PROJECT)) == 1

    def test_conflict_detection_same_effect_and_target(self, tmp_path):
        reg = _registry(tmp_path)
        rule_a = _rule(action={"effect": "block", "target": "code_execution"})
        rule_b = _rule(action={"effect": "allow", "target": "code_execution"})
        reg.create(rule_a)
        conflicts = reg.detect_conflicts(rule_b)
        assert rule_a.rule_id in conflicts

    def test_no_conflict_different_targets(self, tmp_path):
        reg = _registry(tmp_path)
        rule_a = _rule(action={"effect": "block", "target": "emails"})
        rule_b = _rule(action={"effect": "allow", "target": "code_execution"})
        reg.create(rule_a)
        conflicts = reg.detect_conflicts(rule_b)
        assert len(conflicts) == 0

    def test_stats(self, tmp_path):
        reg = _registry(tmp_path)
        reg.create(_rule(status=RuleStatus.ACTIVE))
        reg.create(_rule(status=RuleStatus.INACTIVE))
        stats = reg.stats()
        assert stats["total"] == 2
        assert stats["active"] == 1
        assert stats["inactive"] == 1


# ---------------------------------------------------------------------------
# Engine tests
# ---------------------------------------------------------------------------


class TestRulesEngine:
    def test_evaluate_empty_registry(self, tmp_path):
        reg = _registry(tmp_path)
        engine = RulesEngine(registry=reg)
        ctx = RuleContext(action_type="chat")
        result = engine.evaluate(ctx)
        assert len(result.matched_rules) == 0
        assert len(result.effective_rules) == 0

    def test_global_rule_always_matches(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule(scope=RuleScope.GLOBAL)
        reg.create(rule)
        engine = RulesEngine(registry=reg)
        ctx = RuleContext(action_type="chat")
        result = engine.evaluate(ctx)
        assert len(result.matched_rules) == 1
        assert result.matched_rules[0].rule_id == rule.rule_id

    def test_project_rule_matches_by_project_id(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule(scope=RuleScope.PROJECT, scope_id="proj_123")
        reg.create(rule)
        engine = RulesEngine(registry=reg)
        # matching project
        ctx = RuleContext(project_id="proj_123")
        assert len(engine.evaluate(ctx).matched_rules) == 1
        # non-matching project
        ctx2 = RuleContext(project_id="proj_999")
        assert len(engine.evaluate(ctx2).matched_rules) == 0

    def test_inactive_rule_not_matched(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule(status=RuleStatus.INACTIVE)
        reg.create(rule)
        engine = RulesEngine(registry=reg)
        result = engine.evaluate(RuleContext())
        assert len(result.matched_rules) == 0

    def test_condition_eq_match(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule(condition={
            "match_type": "all",
            "criteria": [{"field": "action_type", "operator": "eq", "value": "code_review"}],
        })
        reg.create(rule)
        engine = RulesEngine(registry=reg)
        assert len(engine.evaluate(RuleContext(action_type="code_review")).matched_rules) == 1
        assert len(engine.evaluate(RuleContext(action_type="chat")).matched_rules) == 0

    def test_condition_contains_match(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule(condition={
            "match_type": "all",
            "criteria": [{"field": "topic", "operator": "contains", "value": "security"}],
        })
        reg.create(rule)
        engine = RulesEngine(registry=reg)
        ctx = RuleContext(metadata={"topic": "security review"})
        assert len(engine.evaluate(ctx).matched_rules) == 1

    def test_condition_any_match(self, tmp_path):
        reg = _registry(tmp_path)
        rule = _rule(condition={
            "match_type": "any",
            "criteria": [
                {"field": "action_type", "operator": "eq", "value": "code_review"},
                {"field": "action_type", "operator": "eq", "value": "chat"},
            ],
        })
        reg.create(rule)
        engine = RulesEngine(registry=reg)
        assert len(engine.evaluate(RuleContext(action_type="chat")).matched_rules) == 1
        assert len(engine.evaluate(RuleContext(action_type="code_review")).matched_rules) == 1
        assert len(engine.evaluate(RuleContext(action_type="other")).matched_rules) == 0

    def test_conflict_resolution_higher_priority_wins(self, tmp_path):
        reg = _registry(tmp_path)
        rule_high = _rule(
            priority=80,
            action={"effect": "allow", "target": "emails"},
            rule_type=RuleType.FILTER,
        )
        rule_low = _rule(
            priority=20,
            action={"effect": "block", "target": "emails"},
            rule_type=RuleType.FILTER,
        )
        reg.create(rule_high)
        reg.create(rule_low)
        engine = RulesEngine(registry=reg)
        result = engine.evaluate(RuleContext())
        # Both matched, but conflict resolved — only high priority survives
        assert len(result.conflict_pairs) == 1
        eff_ids = {r.rule_id for r in result.effective_rules}
        assert rule_high.rule_id in eff_ids
        assert rule_low.rule_id not in eff_ids

    def test_result_to_dict(self, tmp_path):
        reg = _registry(tmp_path)
        engine = RulesEngine(registry=reg)
        result = engine.evaluate(RuleContext(action_type="chat"))
        d = result.to_dict()
        assert "matched_count" in d
        assert "effective_rules" in d
        assert "context" in d

    def test_priority_ordering_in_matched(self, tmp_path):
        reg = _registry(tmp_path)
        rule_low = _rule(priority=10)
        rule_high = _rule(priority=90)
        rule_mid = _rule(priority=50)
        for r in [rule_low, rule_high, rule_mid]:
            reg.create(r)
        engine = RulesEngine(registry=reg)
        result = engine.evaluate(RuleContext())
        priorities = [r.priority for r in result.matched_rules]
        assert priorities == sorted(priorities, reverse=True)
