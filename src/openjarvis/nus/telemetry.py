"""NUS 1B — Telemetry Ingestion and Normalization.

Ingests and normalizes telemetry from:
  - Workbench event records
  - Validation outputs
  - Capability status summaries
  - Model routing / cost metadata
  - Wave 1–4 event summaries
  - NUS 1A learning records
  - Blocked / approval-required actions

Produces normalized telemetry records for learning and recommendation generation.

Safety:
  - Tolerates missing fields
  - Redacts suspicious secret-looking values
  - Categorizes event types
  - Maps events to learning signals
  - Maps events to recommendations where useful
  - No external sends, no secret access, no writes except safe persistence
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.nus.learning_store import redact_suspicious

logger = logging.getLogger(__name__)

NUS1B_TELEMETRY_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Telemetry event categories
# ---------------------------------------------------------------------------

TELEM_CATEGORY_TASK = "task"
TELEM_CATEGORY_VALIDATION = "validation"
TELEM_CATEGORY_BLOCKED = "blocked"
TELEM_CATEGORY_APPROVAL = "approval"
TELEM_CATEGORY_COST = "cost"
TELEM_CATEGORY_ROUTING = "routing"
TELEM_CATEGORY_CAPABILITY = "capability"
TELEM_CATEGORY_WAVE = "wave"
TELEM_CATEGORY_LEARNING = "learning"
TELEM_CATEGORY_UNKNOWN = "unknown"

# Event type → category mapping
_EVENT_CATEGORY_MAP: Dict[str, str] = {
    # Task outcomes
    "subtask_done": TELEM_CATEGORY_TASK,
    "subtask_failed": TELEM_CATEGORY_TASK,
    "execution_complete": TELEM_CATEGORY_TASK,
    "execution_started": TELEM_CATEGORY_TASK,
    "plan_created": TELEM_CATEGORY_TASK,
    # Validation
    "validation_failed": TELEM_CATEGORY_VALIDATION,
    "validation_passed": TELEM_CATEGORY_VALIDATION,
    # Blocked
    "safety_blocked": TELEM_CATEGORY_BLOCKED,
    "skill_blocked": TELEM_CATEGORY_BLOCKED,
    "automation_blocked": TELEM_CATEGORY_BLOCKED,
    "knowledge_blocked": TELEM_CATEGORY_BLOCKED,
    "research_blocked": TELEM_CATEGORY_BLOCKED,
    "expansion_proposal_blocked": TELEM_CATEGORY_BLOCKED,
    "learning_action_blocked": TELEM_CATEGORY_BLOCKED,
    "recommendation_blocked": TELEM_CATEGORY_BLOCKED,
    "autonomy_action_blocked": TELEM_CATEGORY_BLOCKED,
    # Approval
    "approval_required": TELEM_CATEGORY_APPROVAL,
    "dry_run_gate": TELEM_CATEGORY_APPROVAL,
    "artifact_write_requires_approval": TELEM_CATEGORY_APPROVAL,
    "expansion_approval_required": TELEM_CATEGORY_APPROVAL,
    "learning_approval_required": TELEM_CATEGORY_APPROVAL,
    "recommendation_approved": TELEM_CATEGORY_APPROVAL,
    "recommendation_rejected": TELEM_CATEGORY_APPROVAL,
    # Cost
    "budget_exceeded": TELEM_CATEGORY_COST,
    "optimization_blocked": TELEM_CATEGORY_COST,
    "optimization_scorecard": TELEM_CATEGORY_COST,
    # Wave
    "skill_executed": TELEM_CATEGORY_WAVE,
    "automation_dry_run": TELEM_CATEGORY_WAVE,
    "knowledge_ingested": TELEM_CATEGORY_WAVE,
    "research_queried": TELEM_CATEGORY_WAVE,
    "optimization_recommendation": TELEM_CATEGORY_WAVE,
    "skill_pack_executed": TELEM_CATEGORY_WAVE,
    "content_workflow_created": TELEM_CATEGORY_WAVE,
    "artifact_drafted": TELEM_CATEGORY_WAVE,
    "expansion_opportunity_detected": TELEM_CATEGORY_WAVE,
    "expansion_proposal_created": TELEM_CATEGORY_WAVE,
    # Learning
    "learning_snapshot_created": TELEM_CATEGORY_LEARNING,
    "agent_scorecard_generated": TELEM_CATEGORY_LEARNING,
    "failure_pattern_detected": TELEM_CATEGORY_LEARNING,
    "learning_recommendation_created": TELEM_CATEGORY_LEARNING,
    "task_outcome_ingested": TELEM_CATEGORY_LEARNING,
    "recommendation_created": TELEM_CATEGORY_LEARNING,
    "recommendation_dry_run_executed": TELEM_CATEGORY_LEARNING,
    "learning_record_persisted": TELEM_CATEGORY_LEARNING,
    "telemetry_ingested": TELEM_CATEGORY_LEARNING,
    "autonomy_policy_evaluated": TELEM_CATEGORY_LEARNING,
    # Routing
    "optimize_run_start": TELEM_CATEGORY_ROUTING,
    "optimize_trial_end": TELEM_CATEGORY_ROUTING,
    "feedback_received": TELEM_CATEGORY_ROUTING,
}

# Category → NUS 1A signal type mapping
_CATEGORY_TO_SIGNAL: Dict[str, str] = {
    TELEM_CATEGORY_TASK: "positive_signal",
    TELEM_CATEGORY_VALIDATION: "validation_signal",
    TELEM_CATEGORY_BLOCKED: "risk_signal",
    TELEM_CATEGORY_APPROVAL: "approval_signal",
    TELEM_CATEGORY_COST: "cost_signal",
    TELEM_CATEGORY_ROUTING: "capability_signal",
    TELEM_CATEGORY_CAPABILITY: "capability_signal",
    TELEM_CATEGORY_WAVE: "positive_signal",
    TELEM_CATEGORY_LEARNING: "positive_signal",
    TELEM_CATEGORY_UNKNOWN: "negative_signal",
}


# ---------------------------------------------------------------------------
# NormalizedTelemetryRecord
# ---------------------------------------------------------------------------


@dataclass
class NormalizedTelemetryRecord:
    """A normalized telemetry record ready for NUS learning."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_event_type: str = ""
    category: str = TELEM_CATEGORY_UNKNOWN
    signal_type: str = "positive_signal"
    is_blocked: bool = False
    is_approval_required: bool = False
    is_failure: bool = False
    model_used: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    session_id: str = ""
    task_id: str = ""
    title: str = ""
    detail: str = ""
    wave: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    normalized_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source_event_type": self.source_event_type,
            "category": self.category,
            "signal_type": self.signal_type,
            "is_blocked": self.is_blocked,
            "is_approval_required": self.is_approval_required,
            "is_failure": self.is_failure,
            "model_used": self.model_used,
            "estimated_cost_usd": self.estimated_cost_usd,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "title": self.title,
            "detail": self.detail,
            "wave": self.wave,
            "metadata": self.metadata,
            "normalized_at": self.normalized_at,
        }


# ---------------------------------------------------------------------------
# TelemetryNormalizer
# ---------------------------------------------------------------------------


class TelemetryNormalizer:
    """Ingests diverse event sources and produces NormalizedTelemetryRecord objects.

    Safety: tolerates missing fields, redacts suspicious values, never sends externally.
    """

    def __init__(self) -> None:
        self._records: List[NormalizedTelemetryRecord] = []

    def ingest_workbench_event(self, event: Dict[str, Any]) -> NormalizedTelemetryRecord:
        """Normalize a single workbench event dict."""
        event = redact_suspicious(event)
        event_type = event.get("event_type", "")
        category = _EVENT_CATEGORY_MAP.get(event_type, TELEM_CATEGORY_UNKNOWN)
        signal_type = _CATEGORY_TO_SIGNAL.get(category, "negative_signal")

        is_blocked = category == TELEM_CATEGORY_BLOCKED
        is_approval = category == TELEM_CATEGORY_APPROVAL
        is_failure = event_type in ("subtask_failed", "validation_failed", "budget_exceeded")

        # Adjust signal for failures
        if is_failure:
            signal_type = "negative_signal"

        rec = NormalizedTelemetryRecord(
            source_event_type=event_type,
            category=category,
            signal_type=signal_type,
            is_blocked=is_blocked,
            is_approval_required=is_approval,
            is_failure=is_failure,
            session_id=str(event.get("session_id", "")),
            task_id=str(event.get("task_id", "")),
            title=str(event.get("title", "")),
            detail=str(event.get("detail", "")),
            metadata={
                "tone": event.get("tone", ""),
                "dry_run": event.get("dry_run", False),
            },
        )
        self._records.append(rec)
        return rec

    def ingest_validation_output(self, output: Dict[str, Any]) -> NormalizedTelemetryRecord:
        """Normalize a validation output dict."""
        output = redact_suspicious(output)
        passed = output.get("passed", output.get("success", False))
        signal_type = "validation_signal"

        rec = NormalizedTelemetryRecord(
            source_event_type="validation_output",
            category=TELEM_CATEGORY_VALIDATION,
            signal_type=signal_type,
            is_failure=not passed,
            metadata={"passed": passed, "output": output.get("output", "")},
        )
        self._records.append(rec)
        return rec

    def ingest_capability_summary(self, summary: Dict[str, Any]) -> NormalizedTelemetryRecord:
        """Normalize a capability status summary."""
        summary = redact_suspicious(summary)
        by_status = summary.get("by_status", {})
        total = summary.get("total", 0)
        ready = by_status.get("ready", 0)
        rec = NormalizedTelemetryRecord(
            source_event_type="capability_summary",
            category=TELEM_CATEGORY_CAPABILITY,
            signal_type="capability_signal",
            metadata={"total": total, "ready": ready, "by_status": by_status},
        )
        self._records.append(rec)
        return rec

    def ingest_routing_cost_metadata(self, metadata: Dict[str, Any]) -> NormalizedTelemetryRecord:
        """Normalize model routing / cost metadata."""
        metadata = redact_suspicious(metadata)
        rec = NormalizedTelemetryRecord(
            source_event_type="routing_cost_metadata",
            category=TELEM_CATEGORY_ROUTING,
            signal_type="cost_signal",
            model_used=metadata.get("model_used"),
            estimated_cost_usd=metadata.get("estimated_cost_usd"),
            metadata=metadata,
        )
        self._records.append(rec)
        return rec

    def ingest_wave_summary(self, wave: str, summary: Dict[str, Any]) -> NormalizedTelemetryRecord:
        """Normalize a Wave 1–4 status summary."""
        summary = redact_suspicious(summary)
        status = summary.get("status", "unknown")
        rec = NormalizedTelemetryRecord(
            source_event_type=f"wave_{wave}_summary",
            category=TELEM_CATEGORY_WAVE,
            signal_type="positive_signal" if status not in ("unavailable", "error") else "negative_signal",
            wave=wave,
            metadata={"status": status},
        )
        self._records.append(rec)
        return rec

    def ingest_nus1a_record(self, learning_record: Dict[str, Any]) -> NormalizedTelemetryRecord:
        """Normalize a NUS 1A learning record (signal, outcome, etc.)."""
        learning_record = redact_suspicious(learning_record)
        signal_type = learning_record.get("signal_type", "positive_signal")
        rec = NormalizedTelemetryRecord(
            source_event_type="nus1a_learning_record",
            category=TELEM_CATEGORY_LEARNING,
            signal_type=signal_type,
            metadata=learning_record,
        )
        self._records.append(rec)
        return rec

    def ingest_blocked_action(
        self, action: str, reason: str, session_id: str = ""
    ) -> NormalizedTelemetryRecord:
        """Normalize a blocked/approval-required action."""
        rec = NormalizedTelemetryRecord(
            source_event_type="blocked_action",
            category=TELEM_CATEGORY_BLOCKED,
            signal_type="risk_signal",
            is_blocked=True,
            session_id=session_id,
            title=f"Blocked action: {action}",
            detail=reason,
            metadata={"action": action, "reason": reason},
        )
        self._records.append(rec)
        return rec

    def ingest_batch(self, events: List[Dict[str, Any]]) -> int:
        """Ingest a batch of workbench events. Returns count ingested."""
        count = 0
        for ev in events:
            try:
                self.ingest_workbench_event(ev)
                count += 1
            except Exception as exc:
                logger.debug("Telemetry ingest skip: %s", exc)
        self._log_event("telemetry_ingested", f"Batch ingested {count} events.")
        return count

    def to_signals(self) -> List[Dict[str, Any]]:
        """Convert normalized records to signal-like dicts for NUS 1A compatibility."""
        out = []
        for r in self._records:
            out.append({
                "signal_type": r.signal_type,
                "source": r.source_event_type,
                "category": r.category,
                "is_blocked": r.is_blocked,
                "is_failure": r.is_failure,
                "metadata": r.metadata,
            })
        return out

    def to_recommendations(self, store: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Convert high-signal normalized records to recommendation hints."""
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry,
            ACTION_LOCAL_ANALYSIS,
            RISK_MEDIUM,
            RISK_HIGH,
        )
        registry = RecommendationRegistry(store=store)
        recs = []

        blocked = [r for r in self._records if r.is_blocked]
        if len(blocked) >= 2:
            rec = registry.create(
                source="telemetry_normalizer",
                category="blocked_actions",
                title=f"{len(blocked)} blocked action(s) detected — review safety gate pattern",
                summary="Multiple blocked actions observed in telemetry. Review is recommended.",
                rationale=f"{len(blocked)} blocked events across {len(set(r.session_id for r in blocked))} session(s).",
                risk_level=RISK_HIGH,
                required_action_type=ACTION_LOCAL_ANALYSIS,
                evidence={"blocked_count": len(blocked)},
            )
            recs.append(rec.to_dict())

        failures = [r for r in self._records if r.is_failure]
        if len(failures) >= 2:
            rec = registry.create(
                source="telemetry_normalizer",
                category="repeated_failures",
                title=f"{len(failures)} failure event(s) detected — review validation/failure patterns",
                summary="Repeated failures observed in telemetry. Review failure patterns.",
                rationale=f"{len(failures)} failure events observed.",
                risk_level=RISK_MEDIUM,
                required_action_type=ACTION_LOCAL_ANALYSIS,
                evidence={"failure_count": len(failures)},
            )
            recs.append(rec.to_dict())

        return recs

    @property
    def record_count(self) -> int:
        return len(self._records)

    def get_records(self) -> List[NormalizedTelemetryRecord]:
        return list(self._records)

    def get_status(self) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        for r in self._records:
            by_category[r.category] = by_category.get(r.category, 0) + 1
        return {
            "version": NUS1B_TELEMETRY_VERSION,
            "record_count": len(self._records),
            "by_category": by_category,
            "blocked_count": sum(1 for r in self._records if r.is_blocked),
            "failure_count": sum(1 for r in self._records if r.is_failure),
            "approval_required_count": sum(1 for r in self._records if r.is_approval_required),
        }

    def ingest_operator_record(self, record: Dict[str, Any]) -> "NormalizedTelemetryRecord":
        """Normalize an operator/agent telemetry record (NUS 1C).

        Tolerates missing fields. Redacts suspicious secret-looking values.
        Maps to learning signals, failure pattern updates, recommendations,
        and routing observations.

        Expected fields (all optional):
          agent_name / source, task_id, action_type, result,
          validation_status, model_used, estimated_cost_usd, risk_level,
          elapsed_time_seconds, blocked_reason, approval_required_reason,
          related_files, test_command
        """
        record = redact_suspicious(record)

        agent_name = str(record.get("agent_name") or record.get("source") or "unknown_operator")
        task_id = str(record.get("task_id") or "")
        action_type = str(record.get("action_type") or "unknown")
        result = str(record.get("result") or "unknown")
        validation_status = record.get("validation_status")
        model_used = record.get("model_used")
        cost = record.get("estimated_cost_usd")
        risk_level = str(record.get("risk_level") or "low")
        elapsed = record.get("elapsed_time_seconds")
        blocked_reason = record.get("blocked_reason")
        approval_reason = record.get("approval_required_reason")
        related_files = record.get("related_files", [])
        test_command = record.get("test_command")

        # Determine flags
        is_blocked = bool(blocked_reason) or result in ("blocked", "denied")
        is_approval = bool(approval_reason) or result == "needs_approval"
        is_failure = result in ("failure", "failed", "error") or validation_status is False

        # Category
        if is_blocked:
            category = TELEM_CATEGORY_BLOCKED
            signal_type = "risk_signal"
        elif is_approval:
            category = TELEM_CATEGORY_APPROVAL
            signal_type = "approval_signal"
        elif is_failure:
            category = TELEM_CATEGORY_TASK
            signal_type = "negative_signal"
        elif validation_status is True:
            category = TELEM_CATEGORY_VALIDATION
            signal_type = "validation_signal"
        elif cost is not None:
            category = TELEM_CATEGORY_COST
            signal_type = "cost_signal"
        else:
            category = TELEM_CATEGORY_TASK
            signal_type = "positive_signal"

        normalized = NormalizedTelemetryRecord(
            source_event_type="operator_agent_record",
            category=category,
            signal_type=signal_type,
            is_blocked=is_blocked,
            is_approval_required=is_approval,
            is_failure=is_failure,
            model_used=str(model_used) if model_used else None,
            estimated_cost_usd=float(cost) if cost is not None else None,
            session_id="",
            task_id=task_id,
            title=f"Operator [{agent_name}]: {action_type} → {result}",
            detail=str(blocked_reason or approval_reason or ""),
            metadata={
                "agent_name": agent_name,
                "action_type": action_type,
                "result": result,
                "validation_status": validation_status,
                "risk_level": risk_level,
                "elapsed_time_seconds": elapsed,
                "related_files": related_files[:5] if related_files else [],
                "test_command": test_command,
            },
        )
        self._records.append(normalized)
        self._log_event(
            "operator_telemetry_ingested",
            f"Operator [{agent_name}] action={action_type} result={result} risk={risk_level}",
        )
        return normalized

    def ingest_operator_batch(self, records: List[Dict[str, Any]]) -> int:
        """Ingest a batch of operator/agent telemetry records. Returns count ingested."""
        count = 0
        for rec in records:
            try:
                self.ingest_operator_record(rec)
                count += 1
            except Exception as exc:
                logger.debug("Operator telemetry ingest skip: %s", exc)
        if count:
            self._log_event("operator_telemetry_ingested", f"Batch ingested {count} operator records.")
        return count

    def to_routing_observations(self) -> List[Dict[str, Any]]:
        """Extract routing-relevant observations from telemetry records (NUS 1C)."""
        observations = []
        for r in self._records:
            if r.model_used or r.estimated_cost_usd is not None:
                observations.append({
                    "model_used": r.model_used,
                    "estimated_cost_usd": r.estimated_cost_usd,
                    "is_failure": r.is_failure,
                    "is_blocked": r.is_blocked,
                    "category": r.category,
                    "source_event_type": r.source_event_type,
                })
        return observations

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1b",
                task_id="telemetry_normalizer",
                event_type=event_type,
                title=f"NUS 1B: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1B telemetry event log skipped: %s", exc)
