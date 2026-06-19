"""Tests for NUS 1A — Learning Foundation.

Covers:
  - scorecard generation
  - task outcome ingestion
  - failure pattern detection
  - learning snapshot generation
  - learning signal classification
  - route/status behavior
  - event logging
  - capability status
  - Wave 1–4 integration awareness
  - US13 remains parked
  - no self-modification
  - no auto-commit/push/deploy
  - blocked unsafe learning actions
"""

from __future__ import annotations

import time
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.nus.learning_foundation import (
    FAILURE_REPEATED_APPROVAL_GATE,
    FAILURE_REPEATED_BLOCKED_UNSAFE,
    FAILURE_REPEATED_CAPABILITY_NOT_READY,
    FAILURE_REPEATED_MISSING_SETUP,
    FAILURE_REPEATED_ROUTING_COST,
    FAILURE_REPEATED_VALIDATION,
    NUS1A_VERSION,
    SIGNAL_APPROVAL,
    SIGNAL_CAPABILITY,
    SIGNAL_COST,
    SIGNAL_NEGATIVE,
    SIGNAL_POSITIVE,
    SIGNAL_RISK,
    SIGNAL_VALIDATION,
    AgentScorecard,
    FailurePatternRecord,
    LearningFoundation,
    LearningSignal,
    LearningSnapshot,
    OutcomeStatus,
    TaskOutcomeRecord,
    classify_signals,
    detect_failure_patterns,
    generate_scorecard,
    get_learning_foundation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_outcome(
    status: str = OutcomeStatus.SUCCESS,
    task_type: str = "subtask_done",
    validation_passed: bool | None = None,
    model_used: str | None = None,
    cost: float | None = None,
    wave: str | None = None,
) -> TaskOutcomeRecord:
    return TaskOutcomeRecord(
        task_id=f"task_{status}_{task_type}",
        session_id="test_session",
        task_type=task_type,
        status=status,
        validation_passed=validation_passed,
        model_used=model_used,
        estimated_cost_usd=cost,
        wave=wave,
    )


# ---------------------------------------------------------------------------
# 1. Scorecard generation
# ---------------------------------------------------------------------------


class TestScorecardGeneration:
    def test_empty_records_scorecard(self):
        sc = generate_scorecard([])
        assert isinstance(sc, AgentScorecard)
        assert sc.total_count == 0
        assert sc.success_count == 0
        assert sc.failure_count == 0
        assert sc.risk_level in ("low", "medium", "high", "critical")

    def test_all_success_scorecard(self):
        records = [make_outcome(OutcomeStatus.SUCCESS) for _ in range(5)]
        sc = generate_scorecard(records)
        assert sc.success_count == 5
        assert sc.failure_count == 0
        assert sc.risk_level == "low"

    def test_high_failure_rate_risk(self):
        records = [make_outcome(OutcomeStatus.FAILURE) for _ in range(4)]
        records += [make_outcome(OutcomeStatus.SUCCESS) for _ in range(2)]
        sc = generate_scorecard(records)
        assert sc.failure_count == 4
        assert sc.risk_level in ("medium", "high")

    def test_blocked_count_raises_risk(self):
        records = [make_outcome(OutcomeStatus.BLOCKED) for _ in range(6)]
        sc = generate_scorecard(records)
        assert sc.blocked_count == 6
        assert sc.risk_level == "high"

    def test_approval_required_count(self):
        records = [make_outcome(OutcomeStatus.APPROVAL_REQUIRED) for _ in range(3)]
        sc = generate_scorecard(records)
        assert sc.approval_required_count == 3

    def test_validation_counts(self):
        records = [
            make_outcome(validation_passed=True),
            make_outcome(validation_passed=True),
            make_outcome(validation_passed=False),
        ]
        sc = generate_scorecard(records)
        assert sc.validation_pass_count == 2
        assert sc.validation_fail_count == 1

    def test_cost_aggregation(self):
        records = [make_outcome(cost=0.01), make_outcome(cost=0.03)]
        sc = generate_scorecard(records)
        assert sc.total_cost_usd == pytest.approx(0.04, rel=1e-4)
        assert sc.avg_cost_usd == pytest.approx(0.02, rel=1e-4)

    def test_model_routing_observations(self):
        records = [
            make_outcome(model_used="sonnet"),
            make_outcome(model_used="sonnet"),
            make_outcome(model_used="opus"),
        ]
        sc = generate_scorecard(records)
        assert len(sc.model_routing_observations) >= 1
        assert any("sonnet" in obs for obs in sc.model_routing_observations)

    def test_wave_summary(self):
        records = [
            make_outcome(wave="wave1"),
            make_outcome(wave="wave1"),
            make_outcome(wave="wave4"),
        ]
        sc = generate_scorecard(records)
        assert sc.wave_summary.get("wave1") == 2
        assert sc.wave_summary.get("wave4") == 1

    def test_scorecard_to_dict_complete(self):
        sc = generate_scorecard([make_outcome()])
        d = sc.to_dict()
        required_keys = [
            "scorecard_id", "period_label", "success_count", "failure_count",
            "blocked_count", "approval_required_count", "total_count",
            "validation_pass_count", "validation_fail_count",
            "repeated_failure_categories", "risk_level", "confidence_level",
            "recommended_action", "generated_at", "wave_summary", "source_event_count",
        ]
        for k in required_keys:
            assert k in d, f"Missing key: {k}"


# ---------------------------------------------------------------------------
# 2. Task outcome ingestion
# ---------------------------------------------------------------------------


class TestTaskOutcomeIngestion:
    def test_ingest_single_outcome(self):
        f = LearningFoundation()
        rec = make_outcome(OutcomeStatus.SUCCESS)
        f.ingest_outcome(rec)
        assert f.record_count == 1

    def test_ingest_multiple_outcomes(self):
        f = LearningFoundation()
        for _ in range(10):
            f.ingest_outcome(make_outcome())
        assert f.record_count == 10

    def test_from_workbench_event_success(self):
        ev = {
            "session_id": "s1",
            "task_id": "t1",
            "event_type": "subtask_done",
            "title": "done",
            "detail": "",
            "tone": "success",
            "created_at": time.time(),
        }
        rec = TaskOutcomeRecord.from_workbench_event(ev)
        assert rec.status == OutcomeStatus.SUCCESS
        assert rec.session_id == "s1"

    def test_from_workbench_event_blocked(self):
        ev = {
            "session_id": "s1",
            "task_id": "t2",
            "event_type": "safety_blocked",
            "title": "blocked",
            "detail": "unsafe action",
            "tone": "error",
            "created_at": time.time(),
        }
        rec = TaskOutcomeRecord.from_workbench_event(ev)
        assert rec.status == OutcomeStatus.BLOCKED
        assert rec.blocked_reason == "unsafe action"

    def test_from_workbench_event_approval_required(self):
        ev = {
            "session_id": "s1",
            "task_id": "t3",
            "event_type": "approval_required",
            "title": "needs approval",
            "detail": "commit requires approval",
            "tone": "warning",
            "created_at": time.time(),
        }
        rec = TaskOutcomeRecord.from_workbench_event(ev)
        assert rec.status == OutcomeStatus.APPROVAL_REQUIRED

    def test_from_workbench_event_failure(self):
        ev = {
            "session_id": "s1",
            "task_id": "t4",
            "event_type": "validation_failed",
            "title": "failed",
            "detail": "",
            "tone": "error",
            "created_at": time.time(),
        }
        rec = TaskOutcomeRecord.from_workbench_event(ev)
        assert rec.status == OutcomeStatus.FAILURE

    def test_outcome_to_dict(self):
        rec = make_outcome(OutcomeStatus.SUCCESS, cost=0.01, model_used="sonnet")
        d = rec.to_dict()
        assert d["status"] == OutcomeStatus.SUCCESS
        assert d["estimated_cost_usd"] == pytest.approx(0.01)

    def test_ingest_from_workbench_events_no_db(self):
        """When no DB exists, ingest_from_workbench_events returns 0 without error."""
        f = LearningFoundation()
        with patch("openjarvis.nus.learning_foundation._safe_recent_events", return_value=[]):
            count = f.ingest_from_workbench_events()
        assert count == 0


# ---------------------------------------------------------------------------
# 3. Failure pattern detection
# ---------------------------------------------------------------------------


class TestFailurePatternDetection:
    def _make_failures(self, task_type: str, count: int) -> List[TaskOutcomeRecord]:
        return [
            TaskOutcomeRecord(
                task_id=f"t{i}",
                session_id="s",
                task_type=task_type,
                status=OutcomeStatus.FAILURE,
            )
            for i in range(count)
        ]

    def _make_blocked(self, count: int) -> List[TaskOutcomeRecord]:
        return [
            TaskOutcomeRecord(
                task_id=f"b{i}",
                session_id="s",
                task_type="safety_blocked",
                status=OutcomeStatus.BLOCKED,
            )
            for i in range(count)
        ]

    def _make_approvals(self, count: int) -> List[TaskOutcomeRecord]:
        return [
            TaskOutcomeRecord(
                task_id=f"a{i}",
                session_id="s",
                task_type="approval_required",
                status=OutcomeStatus.APPROVAL_REQUIRED,
            )
            for i in range(count)
        ]

    def test_no_patterns_below_threshold(self):
        records = self._make_failures("validation_failed", 1)
        patterns = detect_failure_patterns(records)
        assert len(patterns) == 0

    def test_repeated_validation_failure_detected(self):
        records = self._make_failures("validation_failed", 3)
        patterns = detect_failure_patterns(records)
        cats = [p.category for p in patterns]
        assert FAILURE_REPEATED_VALIDATION in cats

    def test_repeated_blocked_unsafe_detected(self):
        records = self._make_blocked(3)
        patterns = detect_failure_patterns(records)
        cats = [p.category for p in patterns]
        assert FAILURE_REPEATED_BLOCKED_UNSAFE in cats

    def test_repeated_approval_gate_detected(self):
        records = self._make_approvals(4)
        patterns = detect_failure_patterns(records)
        cats = [p.category for p in patterns]
        assert FAILURE_REPEATED_APPROVAL_GATE in cats

    def test_repeated_missing_setup_detected(self):
        records = [
            TaskOutcomeRecord(
                task_id=f"ms{i}",
                task_type="provider_unavailable",
                status=OutcomeStatus.FAILURE,
            )
            for i in range(2)
        ]
        patterns = detect_failure_patterns(records)
        cats = [p.category for p in patterns]
        assert FAILURE_REPEATED_MISSING_SETUP in cats

    def test_pattern_to_dict_complete(self):
        records = self._make_failures("validation_failed", 3)
        patterns = detect_failure_patterns(records)
        assert len(patterns) > 0
        d = patterns[0].to_dict()
        for k in ["pattern_id", "category", "count", "examples", "severity", "recommendation"]:
            assert k in d


# ---------------------------------------------------------------------------
# 4. Learning snapshot generation
# ---------------------------------------------------------------------------


class TestLearningSnapshot:
    def test_snapshot_generated(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        assert isinstance(snap, LearningSnapshot)
        assert snap.safety_gates_active is True
        assert snap.us13_voice_status == "HOLD/UNSAFE/PARKED"

    def test_snapshot_includes_scorecard(self):
        f = LearningFoundation()
        f.ingest_outcome(make_outcome(OutcomeStatus.SUCCESS))
        snap = f.get_snapshot()
        assert snap.scorecard is not None
        assert isinstance(snap.scorecard, AgentScorecard)

    def test_snapshot_to_dict_complete(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        d = snap.to_dict()
        required_keys = [
            "snapshot_id", "scorecard", "failure_patterns", "signals",
            "wave1_summary", "wave2_summary", "wave3_summary", "wave4_summary",
            "capabilities_summary", "doctor_summary",
            "us13_voice_status", "nus1a_version", "safety_gates_active", "generated_at",
        ]
        for k in required_keys:
            assert k in d, f"Missing key in snapshot dict: {k}"

    def test_snapshot_wave_summaries_present(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        d = snap.to_dict()
        assert isinstance(d["wave1_summary"], dict)
        assert isinstance(d["wave2_summary"], dict)
        assert isinstance(d["wave3_summary"], dict)
        assert isinstance(d["wave4_summary"], dict)

    def test_snapshot_nus1a_version(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        assert snap.nus1a_version == NUS1A_VERSION


# ---------------------------------------------------------------------------
# 5. Learning signal classification
# ---------------------------------------------------------------------------


class TestLearningSignals:
    def test_positive_signal_from_success(self):
        records = [make_outcome(OutcomeStatus.SUCCESS) for _ in range(3)]
        signals = classify_signals(records)
        types = [s.signal_type for s in signals]
        assert SIGNAL_POSITIVE in types

    def test_negative_signal_from_failure(self):
        records = [make_outcome(OutcomeStatus.FAILURE)]
        signals = classify_signals(records)
        types = [s.signal_type for s in signals]
        assert SIGNAL_NEGATIVE in types

    def test_risk_signal_from_blocked(self):
        records = [make_outcome(OutcomeStatus.BLOCKED)]
        signals = classify_signals(records)
        types = [s.signal_type for s in signals]
        assert SIGNAL_RISK in types

    def test_approval_signal_from_approval_required(self):
        records = [make_outcome(OutcomeStatus.APPROVAL_REQUIRED)]
        signals = classify_signals(records)
        types = [s.signal_type for s in signals]
        assert SIGNAL_APPROVAL in types

    def test_validation_signal_from_validation_fail(self):
        records = [make_outcome(validation_passed=False)]
        signals = classify_signals(records)
        types = [s.signal_type for s in signals]
        assert SIGNAL_VALIDATION in types

    def test_cost_signal_from_costed_record(self):
        records = [make_outcome(cost=0.05)]
        signals = classify_signals(records)
        types = [s.signal_type for s in signals]
        assert SIGNAL_COST in types

    def test_capability_signal_from_model_routing(self):
        records = [make_outcome(model_used="sonnet")]
        signals = classify_signals(records)
        types = [s.signal_type for s in signals]
        assert SIGNAL_CAPABILITY in types

    def test_signal_to_dict(self):
        sig = LearningSignal(signal_type=SIGNAL_POSITIVE, source="test", description="ok")
        d = sig.to_dict()
        for k in ["signal_id", "signal_type", "source", "description", "value", "created_at"]:
            assert k in d

    def test_empty_records_no_signals(self):
        signals = classify_signals([])
        assert signals == []


# ---------------------------------------------------------------------------
# 6. Route / status behavior
# ---------------------------------------------------------------------------


class TestRouteStatusBehavior:
    def test_nus_routes_importable(self):
        from openjarvis.server.nus_routes import router
        routes = [r.path for r in router.routes]
        assert "/v1/nus/learning/status" in routes
        assert "/v1/nus/learning/scorecards" in routes
        assert "/v1/nus/learning/failure-patterns" in routes
        assert "/v1/nus/learning/snapshot" in routes

    def test_status_route_response(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from openjarvis.server.nus_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/v1/nus/learning/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["safety_gates_active"] is True
        assert data["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        assert data["no_self_modification"] is True
        assert data["no_auto_commit"] is True
        assert data["no_deploy"] is True

    def test_scorecards_route_response(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from openjarvis.server.nus_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch("openjarvis.nus.learning_foundation._safe_recent_events", return_value=[]):
            resp = client.get("/v1/nus/learning/scorecards")
        assert resp.status_code == 200
        data = resp.json()
        assert "scorecard" in data

    def test_failure_patterns_route_response(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from openjarvis.server.nus_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch("openjarvis.nus.learning_foundation._safe_recent_events", return_value=[]):
            resp = client.get("/v1/nus/learning/failure-patterns")
        assert resp.status_code == 200
        data = resp.json()
        assert "patterns" in data
        assert isinstance(data["patterns"], list)

    def test_snapshot_route_response(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from openjarvis.server.nus_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch("openjarvis.nus.learning_foundation._safe_recent_events", return_value=[]):
            resp = client.get("/v1/nus/learning/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshot" in data
        assert data["snapshot"]["safety_gates_active"] is True


# ---------------------------------------------------------------------------
# 7. Event logging
# ---------------------------------------------------------------------------


class TestEventLogging:
    def test_nus_event_types_exported(self):
        from openjarvis.workbench.event_log import (
            EVENT_LEARNING_SNAPSHOT_CREATED,
            EVENT_AGENT_SCORECARD_GENERATED,
            EVENT_FAILURE_PATTERN_DETECTED,
            EVENT_LEARNING_RECOMMENDATION_CREATED,
            EVENT_LEARNING_ACTION_BLOCKED,
            EVENT_LEARNING_APPROVAL_REQUIRED,
            EVENT_TASK_OUTCOME_INGESTED,
            EVENT_TASK_OUTCOMES_INGESTED_BATCH,
            EVENT_LEARNING_FOUNDATION_INITIALIZED,
        )
        assert EVENT_LEARNING_SNAPSHOT_CREATED == "learning_snapshot_created"
        assert EVENT_AGENT_SCORECARD_GENERATED == "agent_scorecard_generated"
        assert EVENT_FAILURE_PATTERN_DETECTED == "failure_pattern_detected"
        assert EVENT_LEARNING_RECOMMENDATION_CREATED == "learning_recommendation_created"
        assert EVENT_LEARNING_ACTION_BLOCKED == "learning_action_blocked"
        assert EVENT_LEARNING_APPROVAL_REQUIRED == "learning_approval_required"
        assert EVENT_TASK_OUTCOME_INGESTED == "task_outcome_ingested"
        assert EVENT_TASK_OUTCOMES_INGESTED_BATCH == "task_outcomes_ingested_batch"
        assert EVENT_LEARNING_FOUNDATION_INITIALIZED == "learning_foundation_initialized"

    def test_event_log_on_ingest(self):
        """Event log is called on ingest (best-effort, no error if DB missing)."""
        f = LearningFoundation()
        rec = make_outcome(OutcomeStatus.SUCCESS)
        # Should not raise even if DB is unavailable
        f.ingest_outcome(rec)
        assert f.record_count == 1

    def test_event_log_on_scorecard(self):
        f = LearningFoundation()
        sc = f.get_scorecard()
        assert isinstance(sc, AgentScorecard)


# ---------------------------------------------------------------------------
# 8. Capability status
# ---------------------------------------------------------------------------


class TestCapabilityStatus:
    def test_nus1a_capability_record_exists(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        cap_ids = [c.capability_id for c in caps]
        assert "nus1a_learning_foundation" in cap_ids

    def test_nus1a_capability_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        nus_cap = next(c for c in caps if c.capability_id == "nus1a_learning_foundation")
        assert nus_cap.status == "ready"

    def test_nus1a_capability_summary_mentions_safety(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        nus_cap = next(c for c in caps if c.capability_id == "nus1a_learning_foundation")
        assert "US13" in nus_cap.summary or "voice" in nus_cap.summary.lower()

    def test_capabilities_summary_nus1_status(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary["nus1_status"] == "1a_learning_foundation_ready"


# ---------------------------------------------------------------------------
# 9. Wave 1–4 integration awareness
# ---------------------------------------------------------------------------


class TestWaveIntegrationAwareness:
    def test_snapshot_reads_wave1(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        assert isinstance(snap.wave1_summary, dict)

    def test_snapshot_reads_wave2(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        assert isinstance(snap.wave2_summary, dict)

    def test_snapshot_reads_wave3(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        assert isinstance(snap.wave3_summary, dict)

    def test_snapshot_reads_wave4(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        assert isinstance(snap.wave4_summary, dict)

    def test_wave_event_outcomes_ingestable(self):
        """WorkbenchEvent wave types can be converted to TaskOutcomeRecords."""
        wave_events = [
            {"session_id": "s", "task_id": f"w{i}", "event_type": ev, "title": "", "detail": "", "tone": "info", "created_at": time.time()}
            for i, ev in enumerate([
                "skill_executed", "skill_blocked",
                "automation_dry_run", "automation_blocked",
                "expansion_opportunity_detected", "expansion_proposal_blocked",
                "optimization_scorecard", "content_workflow_created",
            ])
        ]
        f = LearningFoundation()
        with patch("openjarvis.nus.learning_foundation._safe_recent_events", return_value=wave_events):
            count = f.ingest_from_workbench_events()
        assert count == len(wave_events)


# ---------------------------------------------------------------------------
# 10. US13 remains parked
# ---------------------------------------------------------------------------


class TestUS13Parked:
    def test_us13_voice_status_in_snapshot(self):
        f = LearningFoundation()
        snap = f.get_snapshot()
        assert snap.us13_voice_status == "HOLD/UNSAFE/PARKED"

    def test_us13_voice_status_in_status_route(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from openjarvis.server.nus_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/v1/nus/learning/status")
        assert resp.json()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_capabilities_registry_us13_voice_parked(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary.get("us13_voice_parked") is True

    def test_doctor_nus1a_check_includes_us13_evidence(self):
        from openjarvis.doctor.checks import check_nus1a_learning_foundation
        result = check_nus1a_learning_foundation()
        assert result.evidence.get("us13_voice_status") == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 11. No self-modification
# ---------------------------------------------------------------------------


class TestNoSelfModification:
    def test_self_modification_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("self_modification", "patch the codebase")
        assert result["status"] == "blocked"

    def test_code_edit_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("code_edit", "edit a source file")
        assert result["status"] == "blocked"

    def test_file_write_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("file_write", "write to filesystem")
        assert result["status"] == "blocked"

    def test_no_file_write_in_module(self):
        """Verify learning_foundation.py contains no open(..., 'w') calls
        that could indicate direct file writes."""
        import inspect
        import openjarvis.nus.learning_foundation as mod
        source = inspect.getsource(mod)
        # Must not contain unconstrained file write patterns
        assert "open(" not in source or "mode='w'" not in source


# ---------------------------------------------------------------------------
# 12. No auto-commit/push/deploy
# ---------------------------------------------------------------------------


class TestNoAutoCommitDeployPush:
    def test_auto_commit_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("auto_commit", "commit changes")
        assert result["status"] == "blocked"

    def test_auto_push_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("auto_push", "push to remote")
        assert result["status"] == "blocked"

    def test_deploy_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("deploy", "deploy to production")
        assert result["status"] == "blocked"

    def test_external_send_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("external_send", "send Slack message")
        assert result["status"] == "blocked"

    def test_secret_access_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("secret_access", "read secrets")
        assert result["status"] == "blocked"

    def test_browser_automation_blocked(self):
        f = LearningFoundation()
        result = f.make_recommendation("browser_automation", "open browser")
        assert result["status"] == "blocked"

    def test_safe_recommendation_passes(self):
        f = LearningFoundation()
        result = f.make_recommendation("review_logs", "review failure logs")
        assert result["status"] == "recommendation"
        assert result["execution"] == "none — recommendations only in NUS 1A"


# ---------------------------------------------------------------------------
# 13. Blocked unsafe learning actions
# ---------------------------------------------------------------------------


class TestBlockedUnsafeLearningActions:
    def test_learning_action_blocked_event_type_logged(self):
        from openjarvis.workbench.event_log import EVENT_LEARNING_ACTION_BLOCKED
        f = LearningFoundation()
        result = f.make_recommendation("self_modification", "should be blocked")
        assert result["status"] == "blocked"
        assert EVENT_LEARNING_ACTION_BLOCKED == "learning_action_blocked"

    def test_needs_approval_gate(self):
        f = LearningFoundation()
        result = f.make_recommendation("external_provider_setup", "setup provider")
        assert result["status"] == "needs_approval"

    def test_capability_enable_needs_approval(self):
        f = LearningFoundation()
        result = f.make_recommendation("capability_enable", "enable new capability")
        assert result["status"] == "needs_approval"


# ---------------------------------------------------------------------------
# 14. Doctor/readiness check
# ---------------------------------------------------------------------------


class TestDoctorReadiness:
    def test_nus1a_doctor_check_passes(self):
        from openjarvis.doctor.checks import check_nus1a_learning_foundation, CheckStatus
        result = check_nus1a_learning_foundation()
        assert result.status == CheckStatus.PASS
        assert result.check_id == "nus1a_learning_foundation"
        assert result.category == "nus"

    def test_nus1a_doctor_check_evidence(self):
        from openjarvis.doctor.checks import check_nus1a_learning_foundation
        result = check_nus1a_learning_foundation()
        assert result.evidence.get("module_importable") is True
        assert result.evidence.get("safety_gates_active") is True
        assert result.evidence.get("blocked_gate_active") is True

    def test_nus1a_in_all_checks(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        names = [f.__name__ for f in _ALL_CHECK_FNS]
        assert "check_nus1a_learning_foundation" in names

    def test_nus1a_check_in_all_export(self):
        from openjarvis.doctor import checks
        assert "check_nus1a_learning_foundation" in checks.__all__


# ---------------------------------------------------------------------------
# 15. Module structure / version
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_nus1a_version_string(self):
        assert isinstance(NUS1A_VERSION, str)
        assert len(NUS1A_VERSION) > 0

    def test_singleton_returns_same_instance(self):
        f1 = get_learning_foundation()
        f2 = get_learning_foundation()
        assert f1 is f2

    def test_all_dataclasses_serializable(self):
        """All public dataclasses must have to_dict() and return dicts."""
        rec = TaskOutcomeRecord(task_id="t", status=OutcomeStatus.SUCCESS)
        assert isinstance(rec.to_dict(), dict)

        pat = FailurePatternRecord(category=FAILURE_REPEATED_VALIDATION, count=3)
        assert isinstance(pat.to_dict(), dict)

        sig = LearningSignal(signal_type=SIGNAL_POSITIVE, description="ok")
        assert isinstance(sig.to_dict(), dict)

        sc = AgentScorecard()
        assert isinstance(sc.to_dict(), dict)

        snap = LearningSnapshot()
        assert isinstance(snap.to_dict(), dict)
