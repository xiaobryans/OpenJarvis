"""NUS 1C — Learned Model-Routing / A-B Routing Recommendation Scaffold.

Conservative learned routing recommendation layer.

Recommends, does NOT enforce, model-routing changes.

Uses:
  - scorecards (risk, confidence, success/failure rates)
  - telemetry records (model used, cost, validation status)
  - validation outcomes (pass/fail rates)
  - cost metadata (estimated_cost_usd, avg_cost)
  - failure patterns (repeated validation failures, routing cost patterns)
  - task category (docs, architecture, security, governance, low-risk)
  - risk level (low, medium, high, critical)
  - complexity level (simple, moderate, complex)
  - context size (if available)

Recommendation examples:
  - Use cheaper model for docs-only low-risk tasks
  - Escalate to stronger model after validation failure
  - Stop after repeated validation failures
  - Use stronger model for architecture/security/deploy-risk tasks
  - Avoid cheap models for governance approval tasks
  - Prefer faster model for low-risk latency-sensitive tasks

Does NOT:
  - Directly switch providers or models
  - Require real provider keys
  - Make external calls
  - Enforce routing — recommendations only

Hard safety constraints:
  - No source-code mutation.
  - No auto-commit, auto-push, deploy, external sends.
  - No secret access.
  - Recommendation only — no execution.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1C_ROUTING_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Model tier constants (recommendation labels — no real keys)
# ---------------------------------------------------------------------------

TIER_CHEAP_FAST = "cheap_fast"        # e.g. Composer 2.5 / small models
TIER_BALANCED = "balanced"            # e.g. Sonnet 4.6
TIER_STRONG = "strong"                # e.g. Opus 4.7
TIER_STOP = "stop"                    # stop and report — too many failures

# ---------------------------------------------------------------------------
# Task categories that influence routing
# ---------------------------------------------------------------------------

TASK_DOCS_ONLY = "docs_only"
TASK_CODE_SIMPLE = "code_simple"
TASK_CODE_MODERATE = "code_moderate"
TASK_CODE_COMPLEX = "code_complex"
TASK_ARCHITECTURE = "architecture"
TASK_SECURITY = "security"
TASK_GOVERNANCE = "governance"
TASK_DEPLOY_RISK = "deploy_risk"
TASK_UNKNOWN = "unknown"

# Risk-sensitive task categories — always recommend strong model
_HIGH_STAKES_CATEGORIES: FrozenSet[str] = frozenset({
    TASK_ARCHITECTURE,
    TASK_SECURITY,
    TASK_GOVERNANCE,
    TASK_DEPLOY_RISK,
})


# ---------------------------------------------------------------------------
# RoutingRecommendation
# ---------------------------------------------------------------------------


@dataclass
class RoutingRecommendation:
    """A single learned routing recommendation."""

    rec_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)

    recommended_tier: str = TIER_BALANCED
    current_tier: Optional[str] = None
    confidence: str = "medium"
    rationale: str = ""
    evidence_summary: str = ""
    task_category: str = TASK_UNKNOWN
    risk_level: str = "low"
    complexity_level: str = "moderate"

    # What this recommendation does NOT do
    enforcement_note: str = (
        "This is a recommendation only — no model switch is enforced. "
        "No real provider keys required. No external calls made."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rec_id": self.rec_id,
            "created_at": self.created_at,
            "recommended_tier": self.recommended_tier,
            "current_tier": self.current_tier,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence_summary": self.evidence_summary,
            "task_category": self.task_category,
            "risk_level": self.risk_level,
            "complexity_level": self.complexity_level,
            "enforcement_note": self.enforcement_note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingRecommendation":
        return cls(
            rec_id=d.get("rec_id", uuid.uuid4().hex[:12]),
            created_at=d.get("created_at", time.time()),
            recommended_tier=d.get("recommended_tier", TIER_BALANCED),
            current_tier=d.get("current_tier"),
            confidence=d.get("confidence", "medium"),
            rationale=d.get("rationale", ""),
            evidence_summary=d.get("evidence_summary", ""),
            task_category=d.get("task_category", TASK_UNKNOWN),
            risk_level=d.get("risk_level", "low"),
            complexity_level=d.get("complexity_level", "moderate"),
        )


# ---------------------------------------------------------------------------
# LearnedRouter
# ---------------------------------------------------------------------------


class LearnedRouter:
    """NUS 1C learned model-routing recommendation engine.

    Analyzes scorecards, telemetry, failure patterns, task context,
    and produces routing recommendations.

    Does NOT switch models, does NOT call external providers,
    does NOT require real API keys.
    """

    def __init__(self) -> None:
        self._recommendations: List[RoutingRecommendation] = []

    # ------------------------------------------------------------------ #
    # Recommendation generation                                             #
    # ------------------------------------------------------------------ #

    def recommend_from_scorecard(
        self,
        scorecard: Dict[str, Any],
        task_category: str = TASK_UNKNOWN,
        complexity_level: str = "moderate",
    ) -> RoutingRecommendation:
        """Generate a routing recommendation from a scorecard."""
        risk = scorecard.get("risk_level", "low")
        confidence = scorecard.get("confidence_level", "medium")
        fail_count = scorecard.get("failure_count", 0)
        blocked_count = scorecard.get("blocked_count", 0)
        val_fail = scorecard.get("validation_fail_count", 0)
        total = scorecard.get("total_count", 1) or 1
        avg_cost = scorecard.get("avg_cost_usd")
        model_obs = scorecard.get("model_routing_observations", [])

        failure_rate = (fail_count + blocked_count) / total

        # Determine recommended tier
        if task_category in _HIGH_STAKES_CATEGORIES:
            tier = TIER_STRONG
            rationale = (
                f"Task category={task_category} is high-stakes "
                "(architecture/security/governance/deploy-risk). Use strong model."
            )
        elif failure_rate > 0.5 or val_fail >= 3:
            tier = TIER_STOP
            rationale = (
                f"High failure rate ({failure_rate:.0%}) or validation failures ({val_fail}). "
                "Stop and report — repeated failures suggest fundamental issue, not model issue."
            )
        elif failure_rate > 0.25 or risk in ("high", "critical"):
            tier = TIER_STRONG
            rationale = (
                f"Elevated failure rate ({failure_rate:.0%}) or risk={risk}. "
                "Escalate to stronger model."
            )
        elif risk == "low" and task_category in (TASK_DOCS_ONLY, TASK_CODE_SIMPLE):
            tier = TIER_CHEAP_FAST
            rationale = (
                f"Low-risk, simple task category={task_category}. "
                "Use cheaper/faster model to save cost."
            )
        else:
            tier = TIER_BALANCED
            rationale = f"Risk={risk}, failure_rate={failure_rate:.0%}. Balanced model appropriate."

        # Adjust confidence based on sample size
        if total < 5:
            confidence = "low"
        elif total >= 20:
            confidence = "high"

        current_tier = None
        if model_obs:
            current_tier = model_obs[0].split(":")[0].strip() if model_obs else None

        rec = RoutingRecommendation(
            recommended_tier=tier,
            current_tier=current_tier,
            confidence=confidence,
            rationale=rationale,
            evidence_summary=(
                f"total={total} fail_rate={failure_rate:.0%} "
                f"val_fail={val_fail} risk={risk} avg_cost={avg_cost}"
            ),
            task_category=task_category,
            risk_level=risk,
            complexity_level=complexity_level,
        )
        self._recommendations.append(rec)
        self._log_event(
            "learned_routing_recommendation_created",
            f"Routing rec: tier={tier} category={task_category} confidence={confidence}",
        )
        return rec

    def recommend_from_telemetry(
        self,
        telemetry_records: List[Dict[str, Any]],
        task_category: str = TASK_UNKNOWN,
    ) -> Optional[RoutingRecommendation]:
        """Generate a routing recommendation from telemetry records."""
        if not telemetry_records:
            return None

        failures = [r for r in telemetry_records if r.get("is_failure", False)]
        blocked = [r for r in telemetry_records if r.get("is_blocked", False)]
        costs = [r for r in telemetry_records if r.get("estimated_cost_usd") is not None]
        models_used = {}
        for r in telemetry_records:
            m = r.get("model_used")
            if m:
                models_used[m] = models_used.get(m, 0) + 1

        total = len(telemetry_records) or 1
        failure_rate = len(failures) / total
        block_rate = len(blocked) / total
        avg_cost = (
            sum(r["estimated_cost_usd"] for r in costs) / len(costs)
            if costs else None
        )

        if task_category in _HIGH_STAKES_CATEGORIES:
            tier = TIER_STRONG
            rationale = f"High-stakes category={task_category} observed in telemetry."
        elif failure_rate > 0.4 or block_rate > 0.3:
            tier = TIER_STOP
            rationale = (
                f"Telemetry shows high failure_rate={failure_rate:.0%} "
                f"or block_rate={block_rate:.0%}. Stop and investigate."
            )
        elif avg_cost is not None and avg_cost > 0.10:
            tier = TIER_CHEAP_FAST
            rationale = (
                f"High avg cost=${avg_cost:.4f}/task observed in telemetry. "
                "Recommend cheaper model for routine tasks."
            )
        elif failure_rate > 0.2:
            tier = TIER_STRONG
            rationale = f"Elevated failure rate={failure_rate:.0%} in telemetry. Escalate model."
        else:
            tier = TIER_BALANCED
            rationale = f"Normal telemetry — balanced model appropriate. failure_rate={failure_rate:.0%}."

        rec = RoutingRecommendation(
            recommended_tier=tier,
            confidence="medium" if len(telemetry_records) >= 5 else "low",
            rationale=rationale,
            evidence_summary=(
                f"records={total} failure_rate={failure_rate:.0%} "
                f"block_rate={block_rate:.0%} avg_cost={avg_cost} models={list(models_used.keys())[:3]}"
            ),
            task_category=task_category,
        )
        self._recommendations.append(rec)
        self._log_event(
            "learned_routing_recommendation_created",
            f"Telemetry routing rec: tier={tier} records={total}",
        )
        return rec

    def recommend_from_failure_patterns(
        self,
        patterns: List[Dict[str, Any]],
        task_category: str = TASK_UNKNOWN,
    ) -> Optional[RoutingRecommendation]:
        """Generate a routing recommendation from failure patterns."""
        if not patterns:
            return None

        high_sev = [p for p in patterns if p.get("severity") in ("high", "critical")]
        routing_cost_patterns = [p for p in patterns if p.get("category") == "recurring_routing_cost_inefficiency"]
        validation_patterns = [p for p in patterns if "validation" in p.get("category", "")]
        agent_loop = [p for p in patterns if "loop" in p.get("category", "")]

        if agent_loop:
            tier = TIER_STOP
            rationale = "Agent loop pattern detected. Stop and break down task before retrying."
        elif high_sev:
            tier = TIER_STRONG
            rationale = (
                f"{len(high_sev)} high-severity failure pattern(s) detected. "
                "Use strong model for diagnostic reasoning."
            )
        elif routing_cost_patterns:
            tier = TIER_CHEAP_FAST
            rationale = "Routing cost inefficiency pattern detected. Switch to cheaper model for eligible tasks."
        elif validation_patterns:
            tier = TIER_STRONG
            rationale = (
                f"Recurring validation failure pattern detected. "
                "Escalate to stronger model for validation-sensitive work."
            )
        else:
            tier = TIER_BALANCED
            rationale = "Patterns detected but no strong routing signal — balanced model."

        rec = RoutingRecommendation(
            recommended_tier=tier,
            confidence="medium",
            rationale=rationale,
            evidence_summary=f"patterns={len(patterns)} high_sev={len(high_sev)}",
            task_category=task_category,
        )
        self._recommendations.append(rec)
        self._log_event(
            "learned_routing_recommendation_created",
            f"Pattern routing rec: tier={tier} patterns={len(patterns)}",
        )
        return rec

    def recommend_for_task(
        self,
        task_category: str,
        risk_level: str = "low",
        complexity_level: str = "moderate",
        context_size_tokens: Optional[int] = None,
        validation_failures: int = 0,
        current_model: Optional[str] = None,
    ) -> RoutingRecommendation:
        """Generate a contextual routing recommendation for a task."""
        if task_category in _HIGH_STAKES_CATEGORIES:
            tier = TIER_STRONG
            rationale = (
                f"Task category={task_category} requires strong model "
                "(architecture/security/governance/deploy-risk). Avoid cheap models."
            )
        elif validation_failures >= 2:
            tier = TIER_STRONG
            rationale = (
                f"{validation_failures} validation failure(s) observed. "
                "Escalate to stronger model."
            )
        elif risk_level in ("high", "critical"):
            tier = TIER_STRONG
            rationale = f"risk_level={risk_level} — use strong model."
        elif (
            task_category in (TASK_DOCS_ONLY, TASK_CODE_SIMPLE)
            and risk_level == "low"
            and complexity_level == "simple"
        ):
            tier = TIER_CHEAP_FAST
            rationale = (
                f"Low-risk, simple, docs-only task. "
                "Use cheaper/faster model (save cost, adequate quality)."
            )
        elif context_size_tokens is not None and context_size_tokens > 100_000:
            tier = TIER_STRONG
            rationale = (
                f"Large context ({context_size_tokens:,} tokens). "
                "Use strong model for better long-context handling."
            )
        else:
            tier = TIER_BALANCED
            rationale = (
                f"category={task_category} risk={risk_level} complexity={complexity_level}. "
                "Balanced model appropriate."
            )

        rec = RoutingRecommendation(
            recommended_tier=tier,
            current_tier=current_model,
            confidence="high" if task_category in _HIGH_STAKES_CATEGORIES else "medium",
            rationale=rationale,
            evidence_summary=(
                f"category={task_category} risk={risk_level} "
                f"complexity={complexity_level} val_fail={validation_failures}"
            ),
            task_category=task_category,
            risk_level=risk_level,
            complexity_level=complexity_level,
        )
        self._recommendations.append(rec)
        self._log_event(
            "learned_routing_recommendation_created",
            f"Task routing rec: tier={tier} category={task_category}",
        )
        return rec

    # ------------------------------------------------------------------ #
    # Queries and status                                                    #
    # ------------------------------------------------------------------ #

    def get_recommendations(self) -> List[RoutingRecommendation]:
        return list(self._recommendations)

    def get_status(self) -> Dict[str, Any]:
        by_tier: Dict[str, int] = {}
        for r in self._recommendations:
            by_tier[r.recommended_tier] = by_tier.get(r.recommended_tier, 0) + 1

        return {
            "version": NUS1C_ROUTING_VERSION,
            "recommendation_count": len(self._recommendations),
            "by_tier": by_tier,
            "recommendations": [r.to_dict() for r in self._recommendations[-10:]],
            "enforcement_note": (
                "All routing recommendations are advisory only. "
                "No model switches are enforced. "
                "No real provider keys required. No external calls made."
            ),
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }

    # ------------------------------------------------------------------ #
    # Event logging                                                         #
    # ------------------------------------------------------------------ #

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1c",
                task_id="learned_routing",
                event_type=event_type,
                title=f"NUS 1C: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1C routing event log skipped: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_router: Optional[LearnedRouter] = None


def get_learned_router() -> LearnedRouter:
    """Return the module-level LearnedRouter singleton."""
    global _router
    if _router is None:
        _router = LearnedRouter()
    return _router
