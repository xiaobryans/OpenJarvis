"""NUS 1A — Learning Foundation.

Purpose:
  Collect and expose structured learning signals from task outcomes, validation
  results, blocked actions, approval-required actions, repeated failures,
  capability readiness, model routing decisions, cost/performance metadata,
  Wave 1–4 events, and Workbench/coding outcomes.

Hard safety constraints (permanent — no exceptions):
  - NO code self-modification.
  - NO file writes beyond approved safe internal status/evidence paths.
  - NO auto-commit, auto-push, auto-merge, or auto-deploy.
  - NO external sends (Slack, email, HTTP outbound).
  - NO secret access.
  - NO browser / account setup.
  - Recommendations ONLY — no execution.
  - Any recommendation implying writes, deploys, external providers, browser
    actions, account access, secrets, external sends, or self-modification is
    classified as needs_approval or blocked.
  - US13 voice remains HOLD / UNSAFE / PARKED.
  - NUS 1B/1C (full self-improvement autonomy) remains NOT STARTED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUS1A_VERSION = "1.0.0"

# Failure pattern categories
FAILURE_REPEATED_VALIDATION = "repeated_validation_failure"
FAILURE_REPEATED_APPROVAL_GATE = "repeated_approval_gate"
FAILURE_REPEATED_BLOCKED_UNSAFE = "repeated_blocked_unsafe"
FAILURE_REPEATED_MISSING_SETUP = "repeated_missing_setup"
FAILURE_REPEATED_CAPABILITY_NOT_READY = "repeated_capability_not_ready"
FAILURE_REPEATED_ROUTING_COST = "repeated_routing_cost_inefficiency"

# Signal types
SIGNAL_POSITIVE = "positive_signal"
SIGNAL_NEGATIVE = "negative_signal"
SIGNAL_RISK = "risk_signal"
SIGNAL_COST = "cost_signal"
SIGNAL_VALIDATION = "validation_signal"
SIGNAL_CAPABILITY = "capability_signal"
SIGNAL_APPROVAL = "approval_signal"

# Risk levels
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

# Confidence levels
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_INSUFFICIENT = "insufficient"

# Recommendation actions
ACTION_NONE = "none"
ACTION_REVIEW_FAILURES = "review_failures"
ACTION_REVIEW_BLOCKED = "review_blocked"
ACTION_REVIEW_COSTS = "review_costs"
ACTION_IMPROVE_VALIDATION = "improve_validation"
ACTION_REVIEW_CAPABILITIES = "review_capabilities"
ACTION_ESCALATE = "escalate"

# ---------------------------------------------------------------------------
# TaskOutcomeRecord
# ---------------------------------------------------------------------------


class OutcomeStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class TaskOutcomeRecord:
    """Structured record of a single task execution outcome."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_id: str = ""
    session_id: str = ""
    task_type: str = ""
    status: str = OutcomeStatus.SUCCESS
    validation_passed: Optional[bool] = None
    blocked_reason: Optional[str] = None
    approval_required_reason: Optional[str] = None
    failure_category: Optional[str] = None
    model_used: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    duration_seconds: Optional[float] = None
    wave: Optional[str] = None
    source: str = "workbench"
    metadata: Dict[str, Any] = field(default_factory=dict)
    recorded_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "task_type": self.task_type,
            "status": self.status,
            "validation_passed": self.validation_passed,
            "blocked_reason": self.blocked_reason,
            "approval_required_reason": self.approval_required_reason,
            "failure_category": self.failure_category,
            "model_used": self.model_used,
            "estimated_cost_usd": self.estimated_cost_usd,
            "duration_seconds": self.duration_seconds,
            "wave": self.wave,
            "source": self.source,
            "metadata": self.metadata,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_workbench_event(cls, event_dict: Dict[str, Any]) -> "TaskOutcomeRecord":
        """Construct a TaskOutcomeRecord from a WorkbenchEvent dict."""
        event_type = event_dict.get("event_type", "")
        status = OutcomeStatus.SUCCESS
        if event_type in ("subtask_failed", "validation_failed", "budget_exceeded"):
            status = OutcomeStatus.FAILURE
        elif event_type in ("safety_blocked", "skill_blocked", "automation_blocked",
                            "knowledge_blocked", "research_blocked",
                            "expansion_proposal_blocked", "learning_action_blocked"):
            status = OutcomeStatus.BLOCKED
        elif event_type in ("approval_required", "dry_run_gate",
                            "artifact_write_requires_approval",
                            "expansion_approval_required", "learning_approval_required"):
            status = OutcomeStatus.APPROVAL_REQUIRED

        return cls(
            task_id=event_dict.get("task_id", ""),
            session_id=event_dict.get("session_id", ""),
            task_type=event_type,
            status=status,
            blocked_reason=event_dict.get("detail") if status == OutcomeStatus.BLOCKED else None,
            approval_required_reason=event_dict.get("detail") if status == OutcomeStatus.APPROVAL_REQUIRED else None,
            source="workbench_event",
            metadata={"title": event_dict.get("title", ""), "tone": event_dict.get("tone", "")},
            recorded_at=event_dict.get("created_at", time.time()),
        )


# ---------------------------------------------------------------------------
# FailurePatternRecord
# ---------------------------------------------------------------------------


@dataclass
class FailurePatternRecord:
    """A detected pattern of repeated failures."""

    pattern_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    category: str = ""
    count: int = 0
    examples: List[str] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    severity: str = RISK_LOW
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "category": self.category,
            "count": self.count,
            "examples": self.examples[:5],
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "severity": self.severity,
            "recommendation": self.recommendation,
        }


# ---------------------------------------------------------------------------
# LearningSignal
# ---------------------------------------------------------------------------


@dataclass
class LearningSignal:
    """A structured learning signal extracted from outcomes."""

    signal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    signal_type: str = SIGNAL_POSITIVE
    source: str = ""
    description: str = ""
    value: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source": self.source,
            "description": self.description,
            "value": self.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# CapabilitySignal (alias used in tests/reporting)
# ---------------------------------------------------------------------------

CapabilitySignal = LearningSignal  # type alias


# ---------------------------------------------------------------------------
# AgentScorecard
# ---------------------------------------------------------------------------


@dataclass
class AgentScorecard:
    """Summary scorecard aggregated from task outcome records."""

    scorecard_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    period_label: str = "recent"
    success_count: int = 0
    failure_count: int = 0
    blocked_count: int = 0
    approval_required_count: int = 0
    partial_count: int = 0
    validation_pass_count: int = 0
    validation_fail_count: int = 0
    repeated_failure_categories: List[str] = field(default_factory=list)
    avg_cost_usd: Optional[float] = None
    total_cost_usd: Optional[float] = None
    model_routing_observations: List[str] = field(default_factory=list)
    risk_level: str = RISK_LOW
    confidence_level: str = CONFIDENCE_MEDIUM
    recommended_action: str = ACTION_NONE
    generated_at: float = field(default_factory=time.time)
    wave_summary: Dict[str, int] = field(default_factory=dict)
    source_event_count: int = 0

    @property
    def total_count(self) -> int:
        return self.success_count + self.failure_count + self.blocked_count + self.approval_required_count + self.partial_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scorecard_id": self.scorecard_id,
            "period_label": self.period_label,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "blocked_count": self.blocked_count,
            "approval_required_count": self.approval_required_count,
            "partial_count": self.partial_count,
            "total_count": self.total_count,
            "validation_pass_count": self.validation_pass_count,
            "validation_fail_count": self.validation_fail_count,
            "repeated_failure_categories": self.repeated_failure_categories,
            "avg_cost_usd": self.avg_cost_usd,
            "total_cost_usd": self.total_cost_usd,
            "model_routing_observations": self.model_routing_observations,
            "risk_level": self.risk_level,
            "confidence_level": self.confidence_level,
            "recommended_action": self.recommended_action,
            "generated_at": self.generated_at,
            "wave_summary": self.wave_summary,
            "source_event_count": self.source_event_count,
        }


# ---------------------------------------------------------------------------
# LearningSnapshot
# ---------------------------------------------------------------------------


@dataclass
class LearningSnapshot:
    """Full learning state snapshot — no external services required."""

    snapshot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    scorecard: Optional[AgentScorecard] = None
    failure_patterns: List[FailurePatternRecord] = field(default_factory=list)
    signals: List[LearningSignal] = field(default_factory=list)
    wave1_summary: Dict[str, Any] = field(default_factory=dict)
    wave2_summary: Dict[str, Any] = field(default_factory=dict)
    wave3_summary: Dict[str, Any] = field(default_factory=dict)
    wave4_summary: Dict[str, Any] = field(default_factory=dict)
    capabilities_summary: Dict[str, Any] = field(default_factory=dict)
    doctor_summary: Dict[str, Any] = field(default_factory=dict)
    us13_voice_status: str = "HOLD/UNSAFE/PARKED"
    nus1a_version: str = NUS1A_VERSION
    safety_gates_active: bool = True
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "scorecard": self.scorecard.to_dict() if self.scorecard else None,
            "failure_patterns": [p.to_dict() for p in self.failure_patterns],
            "signals": [s.to_dict() for s in self.signals],
            "wave1_summary": self.wave1_summary,
            "wave2_summary": self.wave2_summary,
            "wave3_summary": self.wave3_summary,
            "wave4_summary": self.wave4_summary,
            "capabilities_summary": self.capabilities_summary,
            "doctor_summary": self.doctor_summary,
            "us13_voice_status": self.us13_voice_status,
            "nus1a_version": self.nus1a_version,
            "safety_gates_active": self.safety_gates_active,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_wave1_status() -> Dict[str, Any]:
    try:
        from openjarvis.wave.automation_platform import get_automation_platform_status
        return get_automation_platform_status()
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _safe_wave2_status() -> Dict[str, Any]:
    try:
        from openjarvis.wave.optimization_platform import get_optimization_platform_status
        return get_optimization_platform_status()
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _safe_wave3_status() -> Dict[str, Any]:
    try:
        from openjarvis.wave.content_media_studio import get_content_studio_status
        return get_content_studio_status()
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _safe_wave4_status() -> Dict[str, Any]:
    try:
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        return get_expansion_status()
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _safe_capabilities_summary() -> Dict[str, Any]:
    try:
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        by_status: Dict[str, int] = {}
        for c in caps:
            s = c.status if hasattr(c, "status") else c.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        return {"total": len(caps), "by_status": by_status}
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _safe_doctor_summary() -> Dict[str, Any]:
    try:
        from openjarvis.doctor.checks import (
            check_backend_health,
            check_strict_operating_rules_present,
        )
        backend = check_backend_health()
        rules = check_strict_operating_rules_present()
        return {
            "backend_health": backend.status,
            "strict_rules_present": rules.status,
        }
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _safe_recent_events(limit: int = 200) -> List[Dict[str, Any]]:
    """Pull recent WorkbenchEventLog records for analysis."""
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log = WorkbenchEventLog()
        events = log.list_recent(limit=limit)
        return [e.to_dict() for e in events]
    except Exception as exc:
        logger.debug("Could not read workbench events: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Failure pattern detection
# ---------------------------------------------------------------------------


def detect_failure_patterns(records: List[TaskOutcomeRecord]) -> List[FailurePatternRecord]:
    """Detect repeated failure patterns from a list of outcome records."""
    from collections import defaultdict

    category_counts: Dict[str, List[TaskOutcomeRecord]] = defaultdict(list)

    for r in records:
        if r.status == OutcomeStatus.FAILURE and r.task_type in (
            "validation_failed", "subtask_failed",
        ):
            category_counts[FAILURE_REPEATED_VALIDATION].append(r)

        if r.status == OutcomeStatus.APPROVAL_REQUIRED:
            category_counts[FAILURE_REPEATED_APPROVAL_GATE].append(r)

        if r.status == OutcomeStatus.BLOCKED:
            category_counts[FAILURE_REPEATED_BLOCKED_UNSAFE].append(r)

        if r.task_type in ("provider_unavailable", "media_provider_requires_setup"):
            category_counts[FAILURE_REPEATED_MISSING_SETUP].append(r)

        if r.task_type in ("capability_denied",):
            category_counts[FAILURE_REPEATED_CAPABILITY_NOT_READY].append(r)

        if r.task_type in ("optimization_blocked", "budget_exceeded"):
            category_counts[FAILURE_REPEATED_ROUTING_COST].append(r)

    patterns: List[FailurePatternRecord] = []
    _severity_map = {
        FAILURE_REPEATED_VALIDATION: (2, RISK_MEDIUM, "Review validation profiles and failure cases."),
        FAILURE_REPEATED_APPROVAL_GATE: (3, RISK_LOW, "Consider batching approval requests."),
        FAILURE_REPEATED_BLOCKED_UNSAFE: (2, RISK_HIGH, "Unsafe action pattern detected — review blocked categories."),
        FAILURE_REPEATED_MISSING_SETUP: (2, RISK_MEDIUM, "Setup/config gaps detected — check provider readiness."),
        FAILURE_REPEATED_CAPABILITY_NOT_READY: (3, RISK_MEDIUM, "Capability readiness issues — run doctor check."),
        FAILURE_REPEATED_ROUTING_COST: (3, RISK_MEDIUM, "Cost/routing inefficiency — review model routing policy."),
    }

    for category, bucket in category_counts.items():
        threshold, severity, recommendation = _severity_map.get(category, (2, RISK_LOW, ""))
        if len(bucket) >= threshold:
            examples = [r.task_id or r.record_id for r in bucket[:5]]
            first_seen = min(r.recorded_at for r in bucket)
            last_seen = max(r.recorded_at for r in bucket)
            patterns.append(FailurePatternRecord(
                category=category,
                count=len(bucket),
                examples=examples,
                first_seen=first_seen,
                last_seen=last_seen,
                severity=severity,
                recommendation=recommendation,
            ))

    return patterns


# ---------------------------------------------------------------------------
# Signal classification
# ---------------------------------------------------------------------------


def classify_signals(records: List[TaskOutcomeRecord]) -> List[LearningSignal]:
    """Classify task outcomes into typed learning signals."""
    signals: List[LearningSignal] = []

    successes = [r for r in records if r.status == OutcomeStatus.SUCCESS]
    failures = [r for r in records if r.status == OutcomeStatus.FAILURE]
    blocked = [r for r in records if r.status == OutcomeStatus.BLOCKED]
    approvals = [r for r in records if r.status == OutcomeStatus.APPROVAL_REQUIRED]
    validation_fails = [r for r in records if r.validation_passed is False]
    validation_passes = [r for r in records if r.validation_passed is True]
    cost_records = [r for r in records if r.estimated_cost_usd is not None]
    model_records = [r for r in records if r.model_used]

    if successes:
        signals.append(LearningSignal(
            signal_type=SIGNAL_POSITIVE,
            source="task_outcomes",
            description=f"{len(successes)} successful task(s) recorded.",
            value=float(len(successes)),
            metadata={"task_types": list({r.task_type for r in successes})},
        ))

    if failures:
        signals.append(LearningSignal(
            signal_type=SIGNAL_NEGATIVE,
            source="task_outcomes",
            description=f"{len(failures)} failure(s) recorded.",
            value=float(len(failures)),
            metadata={"failure_categories": list({r.failure_category for r in failures if r.failure_category})},
        ))

    if blocked:
        signals.append(LearningSignal(
            signal_type=SIGNAL_RISK,
            source="task_outcomes",
            description=f"{len(blocked)} blocked action(s) — safety gates active.",
            value=float(len(blocked)),
            metadata={"blocked_reasons": list({r.blocked_reason for r in blocked if r.blocked_reason})[:5]},
        ))

    if approvals:
        signals.append(LearningSignal(
            signal_type=SIGNAL_APPROVAL,
            source="task_outcomes",
            description=f"{len(approvals)} approval-required action(s) recorded.",
            value=float(len(approvals)),
            metadata={},
        ))

    if validation_fails:
        signals.append(LearningSignal(
            signal_type=SIGNAL_VALIDATION,
            source="task_outcomes",
            description=f"{len(validation_fails)} validation failure(s); {len(validation_passes)} pass(es).",
            value=float(len(validation_fails)),
            metadata={"pass_count": len(validation_passes)},
        ))
    elif validation_passes:
        signals.append(LearningSignal(
            signal_type=SIGNAL_VALIDATION,
            source="task_outcomes",
            description=f"{len(validation_passes)} validation pass(es), 0 failures.",
            value=0.0,
            metadata={"pass_count": len(validation_passes)},
        ))

    if cost_records:
        total_cost = sum(r.estimated_cost_usd for r in cost_records if r.estimated_cost_usd)
        avg_cost = total_cost / len(cost_records) if cost_records else 0.0
        signals.append(LearningSignal(
            signal_type=SIGNAL_COST,
            source="task_outcomes",
            description=f"Avg cost: ${avg_cost:.4f}/task over {len(cost_records)} costed task(s).",
            value=avg_cost,
            metadata={"total_cost_usd": total_cost, "sample_count": len(cost_records)},
        ))

    if model_records:
        models_used = {}
        for r in model_records:
            models_used[r.model_used] = models_used.get(r.model_used, 0) + 1
        signals.append(LearningSignal(
            signal_type=SIGNAL_CAPABILITY,
            source="model_routing",
            description=f"Model routing observed: {dict(list(models_used.items())[:5])}",
            value=float(len(model_records)),
            metadata={"models": models_used},
        ))

    return signals


# ---------------------------------------------------------------------------
# Scorecard generation
# ---------------------------------------------------------------------------


def generate_scorecard(
    records: List[TaskOutcomeRecord],
    period_label: str = "recent",
    patterns: Optional[List[FailurePatternRecord]] = None,
    signals: Optional[List[LearningSignal]] = None,
) -> AgentScorecard:
    """Generate an AgentScorecard from task outcome records."""
    sc = AgentScorecard(period_label=period_label, source_event_count=len(records))

    for r in records:
        if r.status == OutcomeStatus.SUCCESS:
            sc.success_count += 1
        elif r.status == OutcomeStatus.FAILURE:
            sc.failure_count += 1
        elif r.status == OutcomeStatus.BLOCKED:
            sc.blocked_count += 1
        elif r.status == OutcomeStatus.APPROVAL_REQUIRED:
            sc.approval_required_count += 1
        elif r.status == OutcomeStatus.PARTIAL:
            sc.partial_count += 1

        if r.validation_passed is True:
            sc.validation_pass_count += 1
        elif r.validation_passed is False:
            sc.validation_fail_count += 1

        if r.wave:
            sc.wave_summary[r.wave] = sc.wave_summary.get(r.wave, 0) + 1

    # Cost aggregation
    cost_records = [r for r in records if r.estimated_cost_usd is not None]
    if cost_records:
        sc.total_cost_usd = sum(r.estimated_cost_usd for r in cost_records)
        sc.avg_cost_usd = sc.total_cost_usd / len(cost_records)

    # Model routing observations
    model_counts: Dict[str, int] = {}
    for r in records:
        if r.model_used:
            model_counts[r.model_used] = model_counts.get(r.model_used, 0) + 1
    sc.model_routing_observations = [f"{m}: {c}" for m, c in model_counts.items()]

    # Failure patterns
    if patterns is None:
        patterns = detect_failure_patterns(records)
    sc.repeated_failure_categories = [p.category for p in patterns]

    # Risk / confidence
    total = sc.total_count or 1
    failure_rate = (sc.failure_count + sc.blocked_count) / total
    if failure_rate > 0.5 or sc.blocked_count >= 5:
        sc.risk_level = RISK_HIGH
        sc.confidence_level = CONFIDENCE_HIGH
        sc.recommended_action = ACTION_REVIEW_BLOCKED
    elif failure_rate > 0.25 or sc.validation_fail_count >= 3:
        sc.risk_level = RISK_MEDIUM
        sc.confidence_level = CONFIDENCE_MEDIUM
        sc.recommended_action = ACTION_REVIEW_FAILURES
    elif sc.approval_required_count >= 5:
        sc.risk_level = RISK_LOW
        sc.confidence_level = CONFIDENCE_MEDIUM
        sc.recommended_action = ACTION_REVIEW_BLOCKED
    elif sc.total_count == 0:
        sc.risk_level = RISK_LOW
        sc.confidence_level = CONFIDENCE_INSUFFICIENT
        sc.recommended_action = ACTION_NONE
    else:
        sc.risk_level = RISK_LOW
        sc.confidence_level = CONFIDENCE_HIGH
        sc.recommended_action = ACTION_NONE

    return sc


# ---------------------------------------------------------------------------
# LearningFoundation — main interface
# ---------------------------------------------------------------------------


class LearningFoundation:
    """NUS 1A Learning Foundation — aggregates and exposes learning signals.

    Safety: read/aggregate only. No writes, deploys, external sends, or
    self-modification allowed from this class.
    """

    def __init__(self) -> None:
        self._records: List[TaskOutcomeRecord] = []
        self._log_event_safe("learning_foundation_initialized", "NUS 1A LearningFoundation initialized.")

    # ------------------------------------------------------------------ #
    # Ingestion                                                             #
    # ------------------------------------------------------------------ #

    def ingest_outcome(self, record: TaskOutcomeRecord) -> None:
        """Ingest a single TaskOutcomeRecord."""
        self._records.append(record)
        self._log_event_safe(
            "task_outcome_ingested",
            f"Ingested outcome: {record.task_id} status={record.status}",
        )

    def ingest_from_workbench_events(self, limit: int = 200) -> int:
        """Pull recent workbench events and convert to TaskOutcomeRecords."""
        events = _safe_recent_events(limit=limit)
        ingested = 0
        for ev in events:
            try:
                rec = TaskOutcomeRecord.from_workbench_event(ev)
                self._records.append(rec)
                ingested += 1
            except Exception as exc:
                logger.debug("Skipping event: %s", exc)
        if ingested:
            self._log_event_safe(
                "task_outcomes_ingested_batch",
                f"Ingested {ingested} outcomes from workbench events.",
            )
        return ingested

    # ------------------------------------------------------------------ #
    # Analysis                                                              #
    # ------------------------------------------------------------------ #

    def get_failure_patterns(self) -> List[FailurePatternRecord]:
        """Detect and return failure patterns from ingested records."""
        patterns = detect_failure_patterns(self._records)
        if patterns:
            for p in patterns:
                self._log_event_safe(
                    "failure_pattern_detected",
                    f"Pattern detected: {p.category} (count={p.count})",
                )
        return patterns

    def get_signals(self) -> List[LearningSignal]:
        """Classify and return learning signals from ingested records."""
        return classify_signals(self._records)

    def get_scorecard(self, period_label: str = "recent") -> AgentScorecard:
        """Generate and return an AgentScorecard."""
        patterns = self.get_failure_patterns()
        signals = self.get_signals()
        sc = generate_scorecard(self._records, period_label=period_label, patterns=patterns, signals=signals)
        self._log_event_safe(
            "agent_scorecard_generated",
            f"Scorecard generated: risk={sc.risk_level} confidence={sc.confidence_level} action={sc.recommended_action}",
        )
        return sc

    def get_snapshot(self) -> LearningSnapshot:
        """Generate a full LearningSnapshot from all available sources."""
        scorecard = self.get_scorecard()
        patterns = self.get_failure_patterns()
        signals = self.get_signals()

        snap = LearningSnapshot(
            scorecard=scorecard,
            failure_patterns=patterns,
            signals=signals,
            wave1_summary=_safe_wave1_status(),
            wave2_summary=_safe_wave2_status(),
            wave3_summary=_safe_wave3_status(),
            wave4_summary=_safe_wave4_status(),
            capabilities_summary=_safe_capabilities_summary(),
            doctor_summary=_safe_doctor_summary(),
            us13_voice_status="HOLD/UNSAFE/PARKED",
            safety_gates_active=True,
        )
        self._log_event_safe(
            "learning_snapshot_created",
            f"Snapshot {snap.snapshot_id} created with {len(self._records)} records.",
        )
        return snap

    def make_recommendation(self, action: str, description: str) -> Dict[str, Any]:
        """Create a learning recommendation — never executes, requires approval for any action."""
        _BLOCKED_ACTIONS = frozenset({
            "file_write", "code_edit", "self_modification", "auto_commit",
            "auto_push", "deploy", "external_send", "secret_access",
            "browser_automation", "account_setup",
        })
        if action in _BLOCKED_ACTIONS:
            self._log_event_safe("learning_action_blocked", f"Blocked recommendation action: {action}")
            return {
                "status": "blocked",
                "action": action,
                "reason": "NUS 1A safety gate: this action class is permanently blocked without explicit approval.",
                "description": description,
            }

        _APPROVAL_ACTIONS = frozenset({
            "external_provider_setup", "capability_enable", "schema_migration",
            "production_config_change",
        })
        if action in _APPROVAL_ACTIONS:
            self._log_event_safe("learning_approval_required", f"Approval required for action: {action}")
            return {
                "status": "needs_approval",
                "action": action,
                "description": description,
                "reason": "NUS 1A: this action requires explicit owner approval before execution.",
            }

        self._log_event_safe("learning_recommendation_created", f"Recommendation: action={action}")
        return {
            "status": "recommendation",
            "action": action,
            "description": description,
            "execution": "none — recommendations only in NUS 1A",
        }

    @property
    def record_count(self) -> int:
        return len(self._records)

    # ------------------------------------------------------------------ #
    # Internal event logging                                                #
    # ------------------------------------------------------------------ #

    def _log_event_safe(self, event_type: str, detail: str) -> None:
        """Log a NUS learning event to WorkbenchEventLog (best-effort)."""
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1a",
                task_id="learning_foundation",
                event_type=event_type,
                title=f"NUS 1A: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS event log skipped: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_foundation: Optional[LearningFoundation] = None


def get_learning_foundation() -> LearningFoundation:
    """Return the module-level LearningFoundation singleton."""
    global _foundation
    if _foundation is None:
        _foundation = LearningFoundation()
    return _foundation
