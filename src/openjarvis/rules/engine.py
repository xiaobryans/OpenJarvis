"""Rules Engine — evaluates active rules against a runtime context.

The engine does NOT execute actions itself; it returns a list of
matching Rule objects for the caller to act on.

Priority order: higher priority rules are returned first.
Conflict detection flags rules whose actions contradict each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.rules.registry import RuleRegistry
from openjarvis.rules.types import Rule, RuleContext, RuleStatus


@dataclass
class EvaluationResult:
    """Result of evaluating rules against a context.

    Fields
    ------
    context         The input context
    matched_rules   Rules that matched and are active (priority-sorted)
    skipped_rules   Rules that did not match
    conflict_pairs  Pairs of conflicting matched rules
    effective_rules Rules after conflict resolution (highest-priority wins)
    """
    context: RuleContext
    matched_rules: List[Rule] = field(default_factory=list)
    skipped_rules: List[Rule] = field(default_factory=list)
    conflict_pairs: List[tuple] = field(default_factory=list)
    effective_rules: List[Rule] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": self.context.to_dict(),
            "matched_count": len(self.matched_rules),
            "skipped_count": len(self.skipped_rules),
            "conflict_count": len(self.conflict_pairs),
            "effective_count": len(self.effective_rules),
            "matched_rules": [r.to_dict() for r in self.matched_rules],
            "effective_rules": [r.to_dict() for r in self.effective_rules],
            "conflict_pairs": [
                {"rule_a": a.rule_id, "rule_b": b.rule_id}
                for a, b in self.conflict_pairs
            ],
        }


class RulesEngine:
    """Evaluates rules against a given runtime context.

    Parameters
    ----------
    registry:
        The rule registry to read rules from.  Defaults to the shared
        RuleRegistry singleton.
    """

    def __init__(self, registry: Optional[RuleRegistry] = None) -> None:
        self._registry = registry or RuleRegistry.get_instance()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, context: RuleContext) -> EvaluationResult:
        """Evaluate all active rules against the given context.

        Returns an EvaluationResult with matched rules, conflicts,
        and effective rules (conflicts resolved by priority).
        """
        candidates = self._registry.list_for_context(
            project_id=context.project_id,
            action_type=context.action_type,
        )

        matched: List[Rule] = []
        skipped: List[Rule] = []
        for rule in candidates:
            if self._matches(rule, context):
                matched.append(rule)
            else:
                skipped.append(rule)

        conflict_pairs = self._detect_conflicts(matched)
        effective = self._resolve_conflicts(matched, conflict_pairs)

        return EvaluationResult(
            context=context,
            matched_rules=matched,
            skipped_rules=skipped,
            conflict_pairs=conflict_pairs,
            effective_rules=effective,
        )

    # ------------------------------------------------------------------
    # Condition matching
    # ------------------------------------------------------------------

    def _matches(self, rule: Rule, context: RuleContext) -> bool:
        condition = rule.condition
        if not condition:
            return True

        match_type = condition.get("match_type", "all")
        criteria = condition.get("criteria", [])

        if not criteria:
            return True

        results = [self._eval_criterion(c, context) for c in criteria]

        if match_type == "all":
            return all(results)
        elif match_type == "any":
            return any(results)
        elif match_type == "none":
            return not any(results)
        return True

    def _eval_criterion(self, criterion: Dict[str, Any], context: RuleContext) -> bool:
        field_name = criterion.get("field", "")
        operator = criterion.get("operator", "eq")
        value = criterion.get("value")

        # Resolve field value from context
        actual = self._resolve_field(field_name, context)

        if operator == "eq":
            return actual == value
        elif operator == "neq":
            return actual != value
        elif operator == "contains":
            return value in str(actual) if actual is not None else False
        elif operator == "startswith":
            return str(actual).startswith(str(value)) if actual is not None else False
        elif operator == "in":
            return actual in (value if isinstance(value, list) else [value])
        elif operator == "exists":
            return actual is not None
        elif operator == "absent":
            return actual is None
        elif operator == "gt":
            return float(actual) > float(value) if actual is not None else False
        elif operator == "lt":
            return float(actual) < float(value) if actual is not None else False
        return False

    def _resolve_field(self, field_name: str, context: RuleContext) -> Any:
        if field_name == "project_id":
            return context.project_id or None
        elif field_name == "action_type":
            return context.action_type or None
        elif field_name == "session_id":
            return context.session_id or None
        else:
            return context.metadata.get(field_name)

    # ------------------------------------------------------------------
    # Conflict detection + resolution
    # ------------------------------------------------------------------

    def _detect_conflicts(self, rules: List[Rule]) -> List[tuple]:
        """Identify pairs of rules whose actions conflict."""
        conflicts: List[tuple] = []
        for i, rule_a in enumerate(rules):
            for rule_b in rules[i + 1:]:
                if self._rules_conflict(rule_a, rule_b):
                    conflicts.append((rule_a, rule_b))
        return conflicts

    def _rules_conflict(self, a: Rule, b: Rule) -> bool:
        if a.rule_type != b.rule_type:
            return False
        a_effect = a.action.get("effect")
        b_effect = b.action.get("effect")
        a_target = a.action.get("target")
        b_target = b.action.get("target")
        if a_target != b_target:
            return False
        contradictions = {("allow", "block"), ("block", "allow"), ("enable", "disable"), ("disable", "enable")}
        return (a_effect, b_effect) in contradictions

    def _resolve_conflicts(self, rules: List[Rule], conflicts: List[tuple]) -> List[Rule]:
        """Return rules after dropping lower-priority conflicting rules."""
        losers: set = set()
        for rule_a, rule_b in conflicts:
            loser = rule_b if rule_a.priority >= rule_b.priority else rule_a
            losers.add(loser.rule_id)
        return [r for r in rules if r.rule_id not in losers]
