"""NUS 1C — Cross-Session Failure Pattern Learning.

Builds on NUS 1A/1B records to learn across persisted sessions.

Detects:
  - recurring validation failures
  - recurring test suite failures
  - recurring approval gate hits
  - recurring unsafe blocked actions
  - recurring missing setup/config
  - recurring cost/model-routing inefficiency
  - recurring context overrun / too-large task
  - recurring agent loop / repeated failed repair

Produces:
  - failure pattern summary
  - confidence score
  - recommended prevention
  - affected area
  - related recommendation IDs
  - escalation recommendation if repeated threshold exceeded

Does NOT execute fixes automatically.

Hard safety constraints:
  - No self-modification.
  - No auto-commit, auto-push, deploy.
  - No external sends.
  - No secret access.
  - Recommendations only — no execution.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NUS1C_FAILURE_LEARNING_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Extended failure pattern categories (NUS 1C superset of NUS 1A)
# ---------------------------------------------------------------------------

PATTERN_VALIDATION_FAILURE = "recurring_validation_failure"
PATTERN_TEST_SUITE_FAILURE = "recurring_test_suite_failure"
PATTERN_APPROVAL_GATE = "recurring_approval_gate"
PATTERN_BLOCKED_UNSAFE = "recurring_blocked_unsafe"
PATTERN_MISSING_SETUP = "recurring_missing_setup"
PATTERN_ROUTING_COST = "recurring_routing_cost_inefficiency"
PATTERN_CONTEXT_OVERRUN = "recurring_context_overrun"
PATTERN_AGENT_LOOP = "recurring_agent_loop"

# Threshold: how many occurrences before a pattern is flagged
_THRESHOLDS: Dict[str, int] = {
    PATTERN_VALIDATION_FAILURE: 2,
    PATTERN_TEST_SUITE_FAILURE: 2,
    PATTERN_APPROVAL_GATE: 3,
    PATTERN_BLOCKED_UNSAFE: 2,
    PATTERN_MISSING_SETUP: 2,
    PATTERN_ROUTING_COST: 3,
    PATTERN_CONTEXT_OVERRUN: 2,
    PATTERN_AGENT_LOOP: 2,
}

# Threshold for escalation recommendation
ESCALATION_THRESHOLD = 5

# Confidence levels
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_INSUFFICIENT = "insufficient"

# Severity levels
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"


# ---------------------------------------------------------------------------
# CrossSessionPattern
# ---------------------------------------------------------------------------


@dataclass
class CrossSessionPattern:
    """A cross-session failure pattern detected from persisted learning records."""

    pattern_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    category: str = ""
    count: int = 0
    session_count: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    severity: str = SEVERITY_LOW
    confidence: str = CONFIDENCE_MEDIUM
    affected_area: str = ""
    recommended_prevention: str = ""
    related_recommendation_ids: List[str] = field(default_factory=list)
    escalation_recommended: bool = False
    escalation_reason: str = ""
    examples: List[str] = field(default_factory=list)
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "category": self.category,
            "count": self.count,
            "session_count": self.session_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "severity": self.severity,
            "confidence": self.confidence,
            "affected_area": self.affected_area,
            "recommended_prevention": self.recommended_prevention,
            "related_recommendation_ids": self.related_recommendation_ids,
            "escalation_recommended": self.escalation_recommended,
            "escalation_reason": self.escalation_reason,
            "examples": self.examples[:5],
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CrossSessionPattern":
        return cls(
            pattern_id=d.get("pattern_id", uuid.uuid4().hex[:12]),
            category=d.get("category", ""),
            count=d.get("count", 0),
            session_count=d.get("session_count", 0),
            first_seen=d.get("first_seen", time.time()),
            last_seen=d.get("last_seen", time.time()),
            severity=d.get("severity", SEVERITY_LOW),
            confidence=d.get("confidence", CONFIDENCE_MEDIUM),
            affected_area=d.get("affected_area", ""),
            recommended_prevention=d.get("recommended_prevention", ""),
            related_recommendation_ids=d.get("related_recommendation_ids", []),
            escalation_recommended=d.get("escalation_recommended", False),
            escalation_reason=d.get("escalation_reason", ""),
            examples=d.get("examples", []),
            detected_at=d.get("detected_at", time.time()),
        )


# ---------------------------------------------------------------------------
# FailureLearner
# ---------------------------------------------------------------------------


class FailureLearner:
    """Cross-session failure pattern learner.

    Loads persisted records from LearningStore and detects patterns
    across sessions. Produces structured patterns with prevention recommendations.

    Safety: does NOT execute fixes. Recommendations only.
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        from openjarvis.nus.learning_store import LearningStore
        self._store = LearningStore(store_dir=store_dir)
        self._patterns: List[CrossSessionPattern] = []

    # ------------------------------------------------------------------ #
    # Learning                                                              #
    # ------------------------------------------------------------------ #

    def analyze(self) -> List[CrossSessionPattern]:
        """Load persisted records and detect cross-session failure patterns.

        Returns list of CrossSessionPattern objects.
        Does NOT execute any fixes.
        """
        outcomes = self._store.load_recent_outcomes(limit=500)
        signals = self._store.load_recent_signals(limit=500)
        patterns_raw = self._store.load_recent_patterns(limit=200)

        self._patterns = self._detect_patterns(outcomes, signals, patterns_raw)

        # Persist detected patterns
        for p in self._patterns:
            try:
                self._store.append_failure_pattern(p.to_dict())
            except Exception as exc:
                logger.debug("FailureLearner: persist pattern failed: %s", exc)

        if self._patterns:
            self._log_event(
                "cross_session_failure_pattern_learned",
                f"Detected {len(self._patterns)} cross-session patterns.",
            )

        return self._patterns

    def _detect_patterns(
        self,
        outcomes: List[Dict[str, Any]],
        signals: List[Dict[str, Any]],
        prior_patterns: List[Dict[str, Any]],
    ) -> List[CrossSessionPattern]:
        """Detect patterns from persisted records."""
        from collections import defaultdict

        # Buckets: category → list of records matching that pattern
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for o in outcomes:
            status = o.get("status", "")
            task_type = o.get("task_type", "")
            failure_cat = o.get("failure_category", "")

            # Validation failures
            if status == "failure" and task_type in (
                "validation_failed", "subtask_failed"
            ):
                buckets[PATTERN_VALIDATION_FAILURE].append(o)

            # Test suite failures
            if status == "failure" and (
                "test" in task_type.lower() or failure_cat in ("test_failure", "test_suite_failure")
            ):
                buckets[PATTERN_TEST_SUITE_FAILURE].append(o)

            # Approval gate hits
            if status == "approval_required":
                buckets[PATTERN_APPROVAL_GATE].append(o)

            # Blocked unsafe
            if status == "blocked":
                buckets[PATTERN_BLOCKED_UNSAFE].append(o)

            # Missing setup / config
            if task_type in (
                "provider_unavailable", "media_provider_requires_setup",
                "capability_denied", "missing_config",
            ):
                buckets[PATTERN_MISSING_SETUP].append(o)

            # Cost / routing inefficiency
            if task_type in ("budget_exceeded", "optimization_blocked", "routing_cost_high"):
                buckets[PATTERN_ROUTING_COST].append(o)

        # Context overrun and agent loop from signals
        for s in signals:
            desc = s.get("description", "").lower()
            sig_type = s.get("signal_type", "")
            meta = s.get("metadata", {})

            if "context" in desc and ("overrun" in desc or "too large" in desc or "overflowed" in desc):
                buckets[PATTERN_CONTEXT_OVERRUN].append({"signal": s})

            if "loop" in desc or "repeated" in desc and "repair" in desc:
                buckets[PATTERN_AGENT_LOOP].append({"signal": s})

            if sig_type == "negative_signal" and meta.get("failure_count", 0) >= 3:
                buckets[PATTERN_AGENT_LOOP].append({"signal": s})

        # Also pull agent_loop indicators from prior patterns
        for pp in prior_patterns:
            cat = pp.get("category", "")
            if cat == "recurring_agent_loop":
                buckets[PATTERN_AGENT_LOOP].append({"prior_pattern": pp})
            elif cat == "recurring_context_overrun":
                buckets[PATTERN_CONTEXT_OVERRUN].append({"prior_pattern": pp})

        # Build CrossSessionPattern objects
        _meta: Dict[str, tuple] = {
            PATTERN_VALIDATION_FAILURE: (
                SEVERITY_MEDIUM, CONFIDENCE_HIGH,
                "validation",
                "Review validation profiles and test coverage. Add targeted validation for failing paths.",
            ),
            PATTERN_TEST_SUITE_FAILURE: (
                SEVERITY_MEDIUM, CONFIDENCE_HIGH,
                "test_suite",
                "Identify root cause of test failures. Run isolated test for failing module before full suite.",
            ),
            PATTERN_APPROVAL_GATE: (
                SEVERITY_LOW, CONFIDENCE_MEDIUM,
                "approval_workflow",
                "Batch approval-required actions to reduce gate friction.",
            ),
            PATTERN_BLOCKED_UNSAFE: (
                SEVERITY_HIGH, CONFIDENCE_HIGH,
                "safety_gates",
                "Review blocked action categories. Do not attempt to bypass safety gates.",
            ),
            PATTERN_MISSING_SETUP: (
                SEVERITY_MEDIUM, CONFIDENCE_MEDIUM,
                "provider_setup",
                "Run doctor check to identify missing setup. Address provider/config gaps before retrying.",
            ),
            PATTERN_ROUTING_COST: (
                SEVERITY_MEDIUM, CONFIDENCE_MEDIUM,
                "model_routing",
                "Review model routing policy. Use cheaper models for low-risk tasks.",
            ),
            PATTERN_CONTEXT_OVERRUN: (
                SEVERITY_MEDIUM, CONFIDENCE_LOW,
                "context_management",
                "Break large tasks into smaller sub-tasks. Avoid passing full file contents unnecessarily.",
            ),
            PATTERN_AGENT_LOOP: (
                SEVERITY_HIGH, CONFIDENCE_LOW,
                "agent_loop",
                "Detect loop after 3 identical approach failures. Break down task. Stop on persistent blocker.",
            ),
        }

        patterns: List[CrossSessionPattern] = []
        for category, bucket in buckets.items():
            threshold = _THRESHOLDS.get(category, 2)
            if len(bucket) < threshold:
                continue

            severity, confidence, affected_area, prevention = _meta.get(
                category, (SEVERITY_LOW, CONFIDENCE_LOW, "unknown", "Review and address the pattern.")
            )

            sessions = set()
            examples = []
            first_seen = time.time()
            last_seen = 0.0

            for record in bucket:
                if isinstance(record, dict):
                    sess = record.get("session_id", "")
                    if sess:
                        sessions.add(sess)
                    task_id = record.get("task_id", "") or record.get("record_id", "")
                    if task_id:
                        examples.append(task_id)
                    ts = record.get("recorded_at", 0.0)
                    if ts and ts < first_seen:
                        first_seen = ts
                    if ts and ts > last_seen:
                        last_seen = ts

            escalation = len(bucket) >= ESCALATION_THRESHOLD
            escalation_reason = (
                f"Pattern {category} occurred {len(bucket)} times — exceeds escalation threshold ({ESCALATION_THRESHOLD})."
                if escalation else ""
            )

            p = CrossSessionPattern(
                category=category,
                count=len(bucket),
                session_count=len(sessions) if sessions else 1,
                first_seen=first_seen if first_seen < time.time() else time.time() - 3600,
                last_seen=last_seen if last_seen > 0 else time.time(),
                severity=severity,
                confidence=confidence,
                affected_area=affected_area,
                recommended_prevention=prevention,
                escalation_recommended=escalation,
                escalation_reason=escalation_reason,
                examples=examples[:5],
            )
            patterns.append(p)

        return patterns

    # ------------------------------------------------------------------ #
    # Queries                                                               #
    # ------------------------------------------------------------------ #

    def get_patterns(self) -> List[CrossSessionPattern]:
        return list(self._patterns)

    def get_summary(self) -> Dict[str, Any]:
        """Return a failure learning summary."""
        return {
            "version": NUS1C_FAILURE_LEARNING_VERSION,
            "pattern_count": len(self._patterns),
            "patterns": [p.to_dict() for p in self._patterns],
            "escalation_count": sum(1 for p in self._patterns if p.escalation_recommended),
            "high_severity_count": sum(1 for p in self._patterns if p.severity in (SEVERITY_HIGH, SEVERITY_CRITICAL)),
            "store_summary": self._store.summarize(),
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
            "no_auto_execution": True,
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
                task_id="failure_learning",
                event_type=event_type,
                title=f"NUS 1C: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1C failure learning event log skipped: %s", exc)
