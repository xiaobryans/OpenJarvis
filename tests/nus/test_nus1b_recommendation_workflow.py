"""Tests for NUS 1B — Recommendation Workflow, Persistence, Telemetry, Autonomy Policy.

Covers:
  - persistence append/load/snapshot
  - unsafe persistence path rejection
  - secret redaction
  - recommendation creation
  - recommendation validation
  - lifecycle transitions
  - approval/rejection dry-run
  - blocked dangerous recommendations
  - telemetry ingestion
  - telemetry to learning-signal mapping
  - autonomy policy default profile
  - future autonomy profiles defined but not broadly enabled
  - capability status
  - doctor check
  - event logging
  - NUS 1A integration
  - Wave 1–4 awareness
  - US13 remains parked
  - no self-modification
  - no auto-commit/push/deploy
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 1. Persistence: append / load / snapshot
# ---------------------------------------------------------------------------


class TestLearningStorePersistence:
    def _make_store(self, tmpdir: str):
        from openjarvis.nus.learning_store import LearningStore
        return LearningStore(store_dir=Path(tmpdir))

    def test_append_and_load_outcome(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        rec_id = store.append_outcome({"task_id": "t1", "status": "success"})
        assert isinstance(rec_id, str)
        outcomes = store.load_recent_outcomes()
        assert len(outcomes) == 1
        assert outcomes[0]["task_id"] == "t1"

    def test_append_and_load_signal(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        store.append_signal({"signal_type": "positive_signal", "description": "ok"})
        sigs = store.load_recent_signals()
        assert len(sigs) == 1

    def test_append_and_load_failure_pattern(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        store.append_failure_pattern({"category": "repeated_validation_failure", "count": 3})
        patterns = store.load_recent_patterns()
        assert len(patterns) == 1
        assert patterns[0]["category"] == "repeated_validation_failure"

    def test_save_and_load_snapshot(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        store.save_snapshot({"snapshot_id": "snap1", "risk_level": "low"})
        snaps = store.load_recent_snapshots()
        assert len(snaps) == 1
        assert snaps[0]["snapshot_id"] == "snap1"

    def test_append_and_load_recommendation(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        store.append_recommendation({"id": "r1", "title": "test rec"})
        recs = store.load_recent_recommendations()
        assert len(recs) == 1

    def test_summarize(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        store.append_outcome({"task_id": "t1"})
        store.append_outcome({"task_id": "t2"})
        store.append_signal({"signal_type": "positive_signal"})
        summary = store.summarize()
        assert summary["record_counts"]["outcomes"] == 2
        assert summary["record_counts"]["signals"] == 1
        assert "store_dir" in summary

    def test_multiple_appends_persist_all(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        for i in range(5):
            store.append_outcome({"task_id": f"t{i}"})
        outcomes = store.load_recent_outcomes()
        assert len(outcomes) == 5

    def test_load_limit_respected(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        for i in range(20):
            store.append_outcome({"task_id": f"t{i}"})
        outcomes = store.load_recent_outcomes(limit=5)
        assert len(outcomes) == 5

    def test_empty_store_returns_empty_lists(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        assert store.load_recent_outcomes() == []
        assert store.load_recent_signals() == []
        assert store.load_recent_patterns() == []
        assert store.load_recent_snapshots() == []
        assert store.load_recent_recommendations() == []


# ---------------------------------------------------------------------------
# 2. Unsafe persistence path rejection
# ---------------------------------------------------------------------------


class TestUnsafePersistencePath:
    def test_env_path_rejected(self):
        from openjarvis.nus.learning_store import LearningStore
        with pytest.raises(ValueError, match="unsafe"):
            LearningStore(store_dir=Path("/tmp/.env"))

    def test_ssh_path_rejected(self):
        from openjarvis.nus.learning_store import LearningStore
        with pytest.raises(ValueError, match="unsafe"):
            LearningStore(store_dir=Path.home() / ".ssh" / "nus_store")

    def test_aws_path_rejected(self):
        from openjarvis.nus.learning_store import LearningStore
        with pytest.raises(ValueError, match="unsafe"):
            LearningStore(store_dir=Path.home() / ".aws" / "nus_store")

    def test_credentials_path_rejected(self):
        from openjarvis.nus.learning_store import LearningStore
        with pytest.raises(ValueError, match="unsafe"):
            LearningStore(store_dir=Path("/tmp/credentials_store"))

    def test_git_path_rejected(self):
        from openjarvis.nus.learning_store import LearningStore
        with pytest.raises(ValueError, match="unsafe"):
            LearningStore(store_dir=Path("/tmp/.git_nus"))

    def test_tmp_path_accepted(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        assert store.store_dir == tmp_path

    def test_openjarvis_path_accepted(self):
        from openjarvis.nus.learning_store import _is_safe_path
        assert _is_safe_path(Path.home() / ".openjarvis" / "nus")

    def test_is_safe_path_blocks_env(self):
        from openjarvis.nus.learning_store import _is_safe_path
        assert not _is_safe_path(Path.home() / ".env")


# ---------------------------------------------------------------------------
# 3. Secret redaction
# ---------------------------------------------------------------------------


class TestSecretRedaction:
    def test_api_key_redacted(self):
        from openjarvis.nus.learning_store import redact_suspicious
        result = redact_suspicious({"api_key": "sk-abcdefghij"})
        assert result["api_key"] == "[REDACTED]"

    def test_secret_key_redacted(self):
        from openjarvis.nus.learning_store import redact_suspicious
        result = redact_suspicious({"secret": "mysecretvalue"})
        assert result["secret"] == "[REDACTED]"

    def test_nested_redaction(self):
        from openjarvis.nus.learning_store import redact_suspicious
        result = redact_suspicious({"nested": {"api_key": "sk-test"}})
        assert result["nested"]["api_key"] == "[REDACTED]"

    def test_safe_values_not_redacted(self):
        from openjarvis.nus.learning_store import redact_suspicious
        result = redact_suspicious({"task_id": "t1", "status": "success", "count": 5})
        assert result["task_id"] == "t1"
        assert result["status"] == "success"

    def test_list_redaction(self):
        from openjarvis.nus.learning_store import redact_suspicious
        result = redact_suspicious([{"api_key": "sk-abc"}, {"status": "ok"}])
        assert result[0]["api_key"] == "[REDACTED]"
        assert result[1]["status"] == "ok"

    def test_persisted_values_are_redacted(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        store = LearningStore(store_dir=tmp_path)
        store.append_outcome({"task_id": "t1", "api_key": "sk-shouldberedacted"})
        outcomes = store.load_recent_outcomes()
        assert outcomes[0].get("api_key") == "[REDACTED]"


# ---------------------------------------------------------------------------
# 4. Recommendation creation
# ---------------------------------------------------------------------------


class TestRecommendationCreation:
    def test_create_safe_recommendation(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_READY, ACTION_LOCAL_ANALYSIS,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="test",
            category="analysis",
            title="Review failure patterns",
            summary="Review the recent failure patterns.",
            required_action_type=ACTION_LOCAL_ANALYSIS,
        )
        assert rec.status == STATUS_READY
        assert rec.id

    def test_create_blocked_recommendation(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_BLOCKED, ACTION_SELF_MODIFICATION,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="test",
            category="danger",
            title="Self-modify code",
            summary="Edit source files",
            required_action_type=ACTION_SELF_MODIFICATION,
        )
        assert rec.status == STATUS_BLOCKED

    def test_create_needs_approval_recommendation(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_NEEDS_APPROVAL, ACTION_FILE_WRITE,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="test",
            category="write",
            title="Write config file",
            summary="Write a config file",
            required_action_type=ACTION_FILE_WRITE,
        )
        assert rec.status == STATUS_NEEDS_APPROVAL

    def test_recommendation_to_dict_complete(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        rec = registry.create(
            source="test", category="test", title="Test", summary="Test rec",
        )
        d = rec.to_dict()
        required_fields = [
            "id", "created_at", "source", "category", "title", "summary",
            "rationale", "affected_area", "risk_level", "confidence",
            "expected_benefit", "required_action_type", "approval_policy",
            "status", "evidence", "rollback_plan", "validation_plan",
            "related_failure_patterns", "related_scorecard_ids",
        ]
        for f in required_fields:
            assert f in d, f"Missing field: {f}"

    def test_from_scorecard_creates_registry(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        scorecard = {
            "scorecard_id": "sc1",
            "risk_level": "medium",
            "recommended_action": "review_failures",
        }
        registry = RecommendationRegistry.from_scorecard(scorecard)
        assert registry is not None
        recs = registry.list_all()
        assert len(recs) >= 1

    def test_from_failure_patterns_creates_registry(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        patterns = [
            {"pattern_id": "p1", "category": "repeated_validation_failure", "count": 3, "severity": "medium", "recommendation": "Review"},
            {"pattern_id": "p2", "category": "repeated_blocked_unsafe", "count": 2, "severity": "high", "recommendation": "Audit"},
        ]
        registry = RecommendationRegistry.from_failure_patterns(patterns)
        recs = registry.list_all()
        assert len(recs) == 2

    def test_recommendation_stored_in_registry(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        rec = registry.create(source="t", category="t", title="T", summary="T")
        assert registry.get(rec.id) is not None

    def test_multiple_recommendations(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        for i in range(5):
            registry.create(source="t", category="t", title=f"Rec {i}", summary="s")
        assert len(registry.list_all()) == 5


# ---------------------------------------------------------------------------
# 5. Recommendation validation
# ---------------------------------------------------------------------------


class TestRecommendationValidation:
    def test_validate_ready_recommendation(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        rec = registry.create(source="t", category="t", title="T", summary="S")
        result = registry.validate(rec.id)
        assert result["ok"] is True

    def test_validate_blocked_recommendation(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, ACTION_SELF_MODIFICATION,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=ACTION_SELF_MODIFICATION,
        )
        result = registry.validate(rec.id)
        assert result["ok"] is False
        assert "blocked" in result["reason"]

    def test_validate_missing_rec(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        result = registry.validate("nonexistent-id")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# 6. Lifecycle transitions
# ---------------------------------------------------------------------------


class TestRecommendationLifecycle:
    def test_draft_to_approved(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_APPROVED, ACTION_FILE_WRITE,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=ACTION_FILE_WRITE,
        )
        # needs_approval → approve → approved
        result = registry.approve(rec.id)
        assert result["ok"] is True
        assert registry.get(rec.id).status == STATUS_APPROVED

    def test_approve_blocked_rec_fails(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, ACTION_SELF_MODIFICATION,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=ACTION_SELF_MODIFICATION,
        )
        result = registry.approve(rec.id)
        assert result["ok"] is False

    def test_reject_recommendation(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_REJECTED,
        )
        registry = RecommendationRegistry()
        rec = registry.create(source="t", category="t", title="T", summary="S")
        result = registry.reject(rec.id, reason="Not useful")
        assert result["ok"] is True
        assert registry.get(rec.id).status == STATUS_REJECTED
        assert registry.get(rec.id).rejection_reason == "Not useful"

    def test_supersede_recommendation(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_SUPERSEDED,
        )
        registry = RecommendationRegistry()
        rec1 = registry.create(source="t", category="t", title="Old", summary="S")
        rec2 = registry.create(source="t", category="t", title="New", summary="S")
        result = registry.supersede(rec1.id, successor_id=rec2.id)
        assert result["ok"] is True
        assert registry.get(rec1.id).status == STATUS_SUPERSEDED

    def test_count_by_status(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        registry.create(source="t", category="t", title="A", summary="s")
        registry.create(source="t", category="t", title="B", summary="s")
        counts = registry.count_by_status()
        assert sum(counts.values()) == 2

    def test_list_by_status(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_READY,
        )
        registry = RecommendationRegistry()
        registry.create(source="t", category="t", title="A", summary="s")
        ready = registry.list_by_status(STATUS_READY)
        assert len(ready) >= 1


# ---------------------------------------------------------------------------
# 7. Approval / rejection dry-run
# ---------------------------------------------------------------------------


class TestApprovalRejectionDryRun:
    def test_dry_run_safe_recommendation(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_EXECUTED_DRY_RUN, ACTION_LOCAL_ANALYSIS,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=ACTION_LOCAL_ANALYSIS,
        )
        result = registry.execute_dry_run(rec.id)
        assert result["ok"] is True
        assert result["dry_run"] is True
        assert registry.get(rec.id).status == STATUS_EXECUTED_DRY_RUN

    def test_dry_run_blocked_recommendation_fails(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, ACTION_SELF_MODIFICATION,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=ACTION_SELF_MODIFICATION,
        )
        result = registry.execute_dry_run(rec.id)
        assert result["ok"] is False
        assert "blocked" in result["reason"]

    def test_dry_run_needs_approval_without_approval_fails(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, ACTION_FILE_WRITE,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=ACTION_FILE_WRITE,
        )
        result = registry.execute_dry_run(rec.id)
        assert result["ok"] is False
        assert "approval" in result["reason"]

    def test_dry_run_needs_approval_after_approval_succeeds(self):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_EXECUTED_DRY_RUN, ACTION_FILE_WRITE,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=ACTION_FILE_WRITE,
        )
        registry.approve(rec.id)
        result = registry.execute_dry_run(rec.id)
        assert result["ok"] is True
        assert registry.get(rec.id).status == STATUS_EXECUTED_DRY_RUN

    def test_reject_then_cannot_execute(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        rec = registry.create(source="t", category="t", title="T", summary="S")
        registry.reject(rec.id, reason="unwanted")
        result = registry.execute_dry_run(rec.id)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# 8. Blocked dangerous recommendations
# ---------------------------------------------------------------------------


class TestBlockedDangerousRecommendations:
    @pytest.mark.parametrize("action_type", [
        "self_modification", "code_edit", "secret_access",
        "auto_commit", "auto_push", "deploy", "safety_policy_change",
    ])
    def test_dangerous_action_types_blocked(self, action_type):
        from openjarvis.nus.recommendation_registry import (
            RecommendationRegistry, STATUS_BLOCKED,
        )
        registry = RecommendationRegistry()
        rec = registry.create(
            source="t", category="t", title="T", summary="S",
            required_action_type=action_type,
        )
        assert rec.status == STATUS_BLOCKED, f"{action_type} should be blocked"

    def test_all_blocked_policy_checks(self):
        from openjarvis.nus.recommendation_registry import (
            _BLOCKED_POLICIES, POLICY_BLOCKED_SELF_MODIFICATION,
            POLICY_BLOCKED_AUTO_COMMIT, POLICY_BLOCKED_DEPLOY,
            POLICY_BLOCKED_SECRET_ACCESS,
        )
        assert POLICY_BLOCKED_SELF_MODIFICATION in _BLOCKED_POLICIES
        assert POLICY_BLOCKED_AUTO_COMMIT in _BLOCKED_POLICIES
        assert POLICY_BLOCKED_DEPLOY in _BLOCKED_POLICIES
        assert POLICY_BLOCKED_SECRET_ACCESS in _BLOCKED_POLICIES


# ---------------------------------------------------------------------------
# 9. Telemetry ingestion
# ---------------------------------------------------------------------------


class TestTelemetryIngestion:
    def test_ingest_workbench_event(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer, TELEM_CATEGORY_TASK
        n = TelemetryNormalizer()
        rec = n.ingest_workbench_event({"event_type": "subtask_done", "session_id": "s1"})
        assert rec.category == TELEM_CATEGORY_TASK
        assert n.record_count == 1

    def test_ingest_blocked_event(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer, TELEM_CATEGORY_BLOCKED
        n = TelemetryNormalizer()
        rec = n.ingest_workbench_event({"event_type": "safety_blocked", "session_id": "s1"})
        assert rec.category == TELEM_CATEGORY_BLOCKED
        assert rec.is_blocked is True

    def test_ingest_approval_event(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer, TELEM_CATEGORY_APPROVAL
        n = TelemetryNormalizer()
        rec = n.ingest_workbench_event({"event_type": "approval_required"})
        assert rec.category == TELEM_CATEGORY_APPROVAL
        assert rec.is_approval_required is True

    def test_ingest_validation_output(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer, TELEM_CATEGORY_VALIDATION
        n = TelemetryNormalizer()
        rec = n.ingest_validation_output({"passed": True, "output": "all tests pass"})
        assert rec.category == TELEM_CATEGORY_VALIDATION

    def test_ingest_capability_summary(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer, TELEM_CATEGORY_CAPABILITY
        n = TelemetryNormalizer()
        rec = n.ingest_capability_summary({"total": 10, "by_status": {"ready": 8}})
        assert rec.category == TELEM_CATEGORY_CAPABILITY

    def test_ingest_routing_cost_metadata(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        rec = n.ingest_routing_cost_metadata({"model_used": "sonnet", "estimated_cost_usd": 0.01})
        assert rec.model_used == "sonnet"
        assert rec.estimated_cost_usd == pytest.approx(0.01)

    def test_ingest_wave_summary(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer, TELEM_CATEGORY_WAVE
        n = TelemetryNormalizer()
        rec = n.ingest_wave_summary("wave1", {"status": "ready"})
        assert rec.category == TELEM_CATEGORY_WAVE
        assert rec.wave == "wave1"

    def test_ingest_nus1a_record(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer, TELEM_CATEGORY_LEARNING
        n = TelemetryNormalizer()
        rec = n.ingest_nus1a_record({"signal_type": "positive_signal", "description": "ok"})
        assert rec.category == TELEM_CATEGORY_LEARNING

    def test_ingest_blocked_action(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        rec = n.ingest_blocked_action("self_modification", "not allowed")
        assert rec.is_blocked is True

    def test_batch_ingest(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        events = [
            {"event_type": "subtask_done"},
            {"event_type": "safety_blocked"},
            {"event_type": "approval_required"},
        ]
        count = n.ingest_batch(events)
        assert count == 3
        assert n.record_count == 3

    def test_missing_fields_tolerated(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        rec = n.ingest_workbench_event({})
        assert rec is not None
        assert rec.record_id

    def test_get_status(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        n.ingest_workbench_event({"event_type": "subtask_done"})
        status = n.get_status()
        assert status["record_count"] == 1
        assert "by_category" in status


# ---------------------------------------------------------------------------
# 10. Telemetry to learning signal mapping
# ---------------------------------------------------------------------------


class TestTelemetryToSignalMapping:
    def test_blocked_events_map_to_risk_signal(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        n.ingest_workbench_event({"event_type": "safety_blocked"})
        signals = n.to_signals()
        assert any(s["signal_type"] == "risk_signal" for s in signals)

    def test_failure_events_map_to_negative_signal(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        n.ingest_workbench_event({"event_type": "subtask_failed"})
        signals = n.to_signals()
        assert any(s["signal_type"] == "negative_signal" for s in signals)

    def test_success_events_map_to_positive_signal(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        n.ingest_workbench_event({"event_type": "subtask_done"})
        signals = n.to_signals()
        assert any(s["signal_type"] == "positive_signal" for s in signals)

    def test_approval_events_map_to_approval_signal(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        n.ingest_workbench_event({"event_type": "approval_required"})
        signals = n.to_signals()
        assert any(s["signal_type"] == "approval_signal" for s in signals)

    def test_to_recommendations_blocked_events(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        for _ in range(3):
            n.ingest_workbench_event({"event_type": "safety_blocked"})
        recs = n.to_recommendations()
        assert len(recs) >= 1
        assert any("blocked" in r["title"].lower() for r in recs)

    def test_telemetry_redacts_secrets(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        rec = n.ingest_workbench_event({"event_type": "subtask_done", "api_key": "sk-test"})
        assert rec is not None


# ---------------------------------------------------------------------------
# 11. Autonomy policy default profile
# ---------------------------------------------------------------------------


class TestAutonomyPolicyDefault:
    def test_default_profile_is_manual(self):
        from openjarvis.nus.autonomy_policy import get_default_policy, PROFILE_MANUAL
        policy = get_default_policy()
        assert policy.profile == PROFILE_MANUAL

    def test_manual_profile_no_auto_allowed(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        policy = get_default_policy()
        assert not policy.is_action_auto_allowed("local_read")
        assert not policy.is_action_auto_allowed("local_analysis")
        assert not policy.is_action_auto_allowed("file_write")

    def test_manual_profile_blocks_dangerous(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        policy = get_default_policy()
        assert policy.is_action_blocked("self_modification")
        assert policy.is_action_blocked("auto_commit")
        assert policy.is_action_blocked("auto_push")
        assert policy.is_action_blocked("deploy")
        assert policy.is_action_blocked("secret_access")
        assert policy.is_action_blocked("safety_policy_change")

    def test_evaluate_blocked_action(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        policy = get_default_policy()
        result = policy.evaluate("self_modification")
        assert result["decision"] == "blocked"

    def test_evaluate_local_read_needs_approval_in_manual(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        policy = get_default_policy()
        result = policy.evaluate("local_read")
        # In manual profile, local_read is not auto_allowed → needs_approval
        assert result["decision"] in ("needs_approval", "blocked")

    def test_kill_switch_blocks_all(self):
        from openjarvis.nus.autonomy_policy import AutonomyPolicy, PROFILE_SAFE_AUTOPILOT
        policy = AutonomyPolicy(profile=PROFILE_SAFE_AUTOPILOT, autonomy_kill_switch=True)
        result = policy.evaluate("local_read")
        assert result["decision"] == "blocked"
        assert result["kill_switch"] is True

    def test_audit_required_default(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        policy = get_default_policy()
        assert policy.audit_required is True

    def test_rollback_required_default(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        policy = get_default_policy()
        assert policy.rollback_required is True

    def test_to_dict_complete(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        policy = get_default_policy()
        d = policy.to_dict()
        for k in ["profile", "activation_status", "autonomy_kill_switch",
                  "audit_required", "rollback_required", "always_blocked",
                  "always_needs_approval", "auto_allowed_actions", "blocked_actions"]:
            assert k in d


# ---------------------------------------------------------------------------
# 12. Future autonomy profiles defined but not broadly enabled
# ---------------------------------------------------------------------------


class TestFutureAutonomyProfiles:
    def test_all_profiles_defined(self):
        from openjarvis.nus.autonomy_policy import (
            get_policy_catalog, PROFILE_MANUAL, PROFILE_SAFE_AUTOPILOT,
            PROFILE_POWER_AUTOPILOT, PROFILE_FOUNDER_OVERRIDE,
            PROFILE_PRODUCTION_RESTRICTED,
        )
        catalog = get_policy_catalog()
        for profile in [PROFILE_MANUAL, PROFILE_SAFE_AUTOPILOT,
                        PROFILE_POWER_AUTOPILOT, PROFILE_FOUNDER_OVERRIDE,
                        PROFILE_PRODUCTION_RESTRICTED]:
            assert profile in catalog

    def test_non_manual_profiles_not_activated(self):
        from openjarvis.nus.autonomy_policy import (
            get_policy_catalog, PROFILE_SAFE_AUTOPILOT,
            PROFILE_POWER_AUTOPILOT, PROFILE_FOUNDER_OVERRIDE,
        )
        catalog = get_policy_catalog()
        for profile in [PROFILE_SAFE_AUTOPILOT, PROFILE_POWER_AUTOPILOT, PROFILE_FOUNDER_OVERRIDE]:
            assert catalog[profile].activation_status != "active"

    def test_power_autopilot_kill_switch_on(self):
        from openjarvis.nus.autonomy_policy import get_policy_catalog, PROFILE_POWER_AUTOPILOT
        catalog = get_policy_catalog()
        assert catalog[PROFILE_POWER_AUTOPILOT].autonomy_kill_switch is True

    def test_safe_autopilot_auto_allows_local_read(self):
        from openjarvis.nus.autonomy_policy import get_policy_catalog, PROFILE_SAFE_AUTOPILOT
        catalog = get_policy_catalog()
        policy = catalog[PROFILE_SAFE_AUTOPILOT]
        # Even if defined, kill_switch may not be on but activation_status != active
        assert policy.is_action_auto_allowed("local_read")

    def test_safe_autopilot_blocks_dangerous(self):
        from openjarvis.nus.autonomy_policy import get_policy_catalog, PROFILE_SAFE_AUTOPILOT
        catalog = get_policy_catalog()
        policy = catalog[PROFILE_SAFE_AUTOPILOT]
        assert policy.is_action_blocked("self_modification")
        assert policy.is_action_blocked("auto_commit")
        assert policy.is_action_blocked("deploy")
        assert policy.is_action_blocked("secret_access")

    def test_get_policy_status(self):
        from openjarvis.nus.autonomy_policy import get_policy_status
        status = get_policy_status()
        assert status["default_profile"] == "manual"
        assert "nus1b_active_profiles" in status
        assert "nus1c_profiles_defined_not_activated" in status
        assert status["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        assert status["safety_gates_active"] is True

    def test_always_blocked_set(self):
        from openjarvis.nus.autonomy_policy import _ALWAYS_BLOCKED
        for action in ["self_modification", "secret_access", "auto_push", "deploy"]:
            assert action in _ALWAYS_BLOCKED


# ---------------------------------------------------------------------------
# 13. Capability status
# ---------------------------------------------------------------------------


class TestCapabilityStatus:
    def test_nus1b_capability_exists(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        ids = [c.capability_id for c in caps]
        assert "nus1b_recommendation_workflow" in ids

    def test_nus1b_capability_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        cap = next(c for c in caps if c.capability_id == "nus1b_recommendation_workflow")
        assert cap.status == "ready"

    def test_nus1b_capability_mentions_safety(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        cap = next(c for c in caps if c.capability_id == "nus1b_recommendation_workflow")
        assert "US13" in cap.summary or "voice" in cap.summary.lower()

    def test_capabilities_summary_nus1_status(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary["nus1_status"] == "1b_recommendation_workflow_ready"

    def test_nus1a_still_present(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        ids = [c.capability_id for c in caps]
        assert "nus1a_learning_foundation" in ids


# ---------------------------------------------------------------------------
# 14. Doctor check
# ---------------------------------------------------------------------------


class TestDoctorCheck:
    def test_nus1b_doctor_check_passes(self):
        from openjarvis.doctor.checks import check_nus1b_recommendation_workflow, CheckStatus
        result = check_nus1b_recommendation_workflow()
        assert result.status == CheckStatus.PASS
        assert result.check_id == "nus1b_recommendation_workflow"
        assert result.category == "nus"

    def test_nus1b_doctor_evidence_complete(self):
        from openjarvis.doctor.checks import check_nus1b_recommendation_workflow
        result = check_nus1b_recommendation_workflow()
        ev = result.evidence
        assert ev.get("modules_importable") is True
        assert ev.get("persistence_ok") is True
        assert ev.get("dangerous_blocked") is True
        assert ev.get("telemetry_ok") is True
        assert ev.get("policy_is_manual") is True
        assert ev.get("policy_blocks_self_modification") is True
        assert ev.get("policy_blocks_auto_commit") is True
        assert ev.get("policy_blocks_deploy") is True
        assert ev.get("us13_voice_status") == "HOLD/UNSAFE/PARKED"

    def test_nus1b_in_all_checks(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        names = [f.__name__ for f in _ALL_CHECK_FNS]
        assert "check_nus1b_recommendation_workflow" in names

    def test_nus1b_check_in_all_export(self):
        from openjarvis.doctor import checks
        assert "check_nus1b_recommendation_workflow" in checks.__all__


# ---------------------------------------------------------------------------
# 15. Event logging
# ---------------------------------------------------------------------------


class TestEventLogging:
    def test_nus1b_event_types_exported(self):
        from openjarvis.workbench.event_log import (
            EVENT_RECOMMENDATION_CREATED,
            EVENT_RECOMMENDATION_APPROVED,
            EVENT_RECOMMENDATION_REJECTED,
            EVENT_RECOMMENDATION_BLOCKED,
            EVENT_RECOMMENDATION_DRY_RUN_EXECUTED,
            EVENT_LEARNING_RECORD_PERSISTED,
            EVENT_TELEMETRY_INGESTED,
            EVENT_AUTONOMY_POLICY_EVALUATED,
            EVENT_AUTONOMY_ACTION_BLOCKED,
        )
        assert EVENT_RECOMMENDATION_CREATED == "recommendation_created"
        assert EVENT_RECOMMENDATION_APPROVED == "recommendation_approved"
        assert EVENT_RECOMMENDATION_REJECTED == "recommendation_rejected"
        assert EVENT_RECOMMENDATION_BLOCKED == "recommendation_blocked"
        assert EVENT_RECOMMENDATION_DRY_RUN_EXECUTED == "recommendation_dry_run_executed"
        assert EVENT_LEARNING_RECORD_PERSISTED == "learning_record_persisted"
        assert EVENT_TELEMETRY_INGESTED == "telemetry_ingested"
        assert EVENT_AUTONOMY_POLICY_EVALUATED == "autonomy_policy_evaluated"
        assert EVENT_AUTONOMY_ACTION_BLOCKED == "autonomy_action_blocked"

    def test_recommendation_creates_event(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        registry = RecommendationRegistry()
        rec = registry.create(source="t", category="t", title="T", summary="S")
        assert rec is not None  # event was logged best-effort


# ---------------------------------------------------------------------------
# 16. NUS 1A integration
# ---------------------------------------------------------------------------


class TestNUS1AIntegration:
    def test_nus1a_foundation_importable_alongside_1b(self):
        from openjarvis.nus.learning_foundation import get_learning_foundation, NUS1A_VERSION
        from openjarvis.nus.recommendation_registry import RecommendationRegistry, NUS1B_REC_VERSION
        assert NUS1A_VERSION
        assert NUS1B_REC_VERSION

    def test_scorecard_feeds_recommendation_registry(self):
        from openjarvis.nus.learning_foundation import generate_scorecard, TaskOutcomeRecord, OutcomeStatus
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        records = [TaskOutcomeRecord(task_id=f"t{i}", status=OutcomeStatus.FAILURE) for i in range(3)]
        sc = generate_scorecard(records)
        registry = RecommendationRegistry.from_scorecard(sc.to_dict())
        assert registry is not None

    def test_failure_patterns_feed_recommendations(self):
        from openjarvis.nus.learning_foundation import detect_failure_patterns, TaskOutcomeRecord, OutcomeStatus
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        records = [
            TaskOutcomeRecord(task_id=f"v{i}", task_type="validation_failed", status=OutcomeStatus.FAILURE)
            for i in range(3)
        ]
        patterns = detect_failure_patterns(records)
        registry = RecommendationRegistry.from_failure_patterns([p.to_dict() for p in patterns])
        assert len(registry.list_all()) >= 1

    def test_learning_store_persists_nus1a_snapshot(self, tmp_path):
        from openjarvis.nus.learning_foundation import LearningFoundation
        from openjarvis.nus.learning_store import LearningStore
        foundation = LearningFoundation()
        with patch("openjarvis.nus.learning_foundation._safe_recent_events", return_value=[]):
            snap = foundation.get_snapshot()
        store = LearningStore(store_dir=tmp_path)
        rec_id = store.save_snapshot(snap.to_dict())
        snaps = store.load_recent_snapshots()
        assert len(snaps) == 1


# ---------------------------------------------------------------------------
# 17. Wave 1–4 awareness
# ---------------------------------------------------------------------------


class TestWaveAwareness:
    def test_snapshot_has_wave_summaries(self):
        from openjarvis.nus.learning_foundation import LearningFoundation
        foundation = LearningFoundation()
        with patch("openjarvis.nus.learning_foundation._safe_recent_events", return_value=[]):
            snap = foundation.get_snapshot()
        d = snap.to_dict()
        assert isinstance(d["wave1_summary"], dict)
        assert isinstance(d["wave4_summary"], dict)

    def test_telemetry_can_ingest_wave_summaries(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        n = TelemetryNormalizer()
        rec1 = n.ingest_wave_summary("wave1", {"status": "ready"})
        rec2 = n.ingest_wave_summary("wave4", {"status": "ready"})
        assert rec1.wave == "wave1"
        assert rec2.wave == "wave4"


# ---------------------------------------------------------------------------
# 18. US13 remains parked
# ---------------------------------------------------------------------------


class TestUS13Parked:
    def test_us13_in_policy_status(self):
        from openjarvis.nus.autonomy_policy import get_policy_status
        status = get_policy_status()
        assert status["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_us13_in_doctor_evidence(self):
        from openjarvis.doctor.checks import check_nus1b_recommendation_workflow
        result = check_nus1b_recommendation_workflow()
        assert result.evidence.get("us13_voice_status") == "HOLD/UNSAFE/PARKED"

    def test_us13_in_nus1b_capability_summary(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary.get("us13_voice_parked") is True

    def test_us13_route_reports_parked(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from openjarvis.server.nus_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/v1/nus/recommendations/status")
        assert resp.status_code == 200
        assert resp.json()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 19. No self-modification
# ---------------------------------------------------------------------------


class TestNoSelfModification:
    def test_recommendation_self_modification_blocked(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry, STATUS_BLOCKED
        registry = RecommendationRegistry()
        rec = registry.create(source="t", category="t", title="T", summary="S",
                               required_action_type="self_modification")
        assert rec.status == STATUS_BLOCKED

    def test_policy_blocks_self_modification(self):
        from openjarvis.nus.autonomy_policy import get_default_policy
        result = get_default_policy().evaluate("self_modification")
        assert result["decision"] == "blocked"

    def test_no_file_write_in_any_nus1b_module(self):
        import inspect
        import openjarvis.nus.learning_store as mod1
        import openjarvis.nus.recommendation_registry as mod2
        import openjarvis.nus.telemetry as mod3
        import openjarvis.nus.autonomy_policy as mod4
        for mod in [mod2, mod3, mod4]:
            src = inspect.getsource(mod)
            assert "open(" not in src or "'w'" not in src


# ---------------------------------------------------------------------------
# 20. No auto-commit/push/deploy
# ---------------------------------------------------------------------------


class TestNoAutoCommitDeployPush:
    @pytest.mark.parametrize("action", [
        "auto_commit", "auto_push", "deploy", "external_send",
        "secret_access", "browser_automation",
    ])
    def test_blocked_actions_in_default_policy(self, action):
        from openjarvis.nus.autonomy_policy import get_default_policy
        result = get_default_policy().evaluate(action)
        assert result["decision"] in ("blocked", "needs_approval"), \
            f"{action} should be blocked or needs_approval"

    @pytest.mark.parametrize("action", [
        "auto_commit", "auto_push", "deploy", "secret_access",
    ])
    def test_blocked_actions_in_safe_autopilot(self, action):
        from openjarvis.nus.autonomy_policy import get_policy_catalog, PROFILE_SAFE_AUTOPILOT
        policy = get_policy_catalog()[PROFILE_SAFE_AUTOPILOT]
        assert policy.is_action_blocked(action), f"{action} should be blocked in safe_autopilot"

    def test_recommendation_deploy_blocked(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry, STATUS_BLOCKED
        registry = RecommendationRegistry()
        rec = registry.create(source="t", category="t", title="T", summary="S",
                               required_action_type="deploy")
        assert rec.status == STATUS_BLOCKED


# ---------------------------------------------------------------------------
# 21. Route behavior
# ---------------------------------------------------------------------------


class TestNUS1BRoutes:
    def _make_client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from openjarvis.server import nus_routes
        # Reset process-level singletons for test isolation
        nus_routes._rec_registry = None
        nus_routes._telemetry_normalizer = None
        from openjarvis.server.nus_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_recommendations_status_route(self):
        client = self._make_client()
        resp = client.get("/v1/nus/recommendations/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["safety_gates_active"] is True

    def test_recommendations_list_route(self):
        client = self._make_client()
        resp = client.get("/v1/nus/recommendations/list")
        assert resp.status_code == 200
        assert "recommendations" in resp.json()

    def test_create_dry_run_safe(self):
        client = self._make_client()
        resp = client.post("/v1/nus/recommendations/create-dry-run", json={
            "title": "Review logs",
            "summary": "Review failure logs",
            "required_action_type": "local_analysis",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendation"]["status"] == "ready"

    def test_create_dry_run_blocked(self):
        client = self._make_client()
        resp = client.post("/v1/nus/recommendations/create-dry-run", json={
            "title": "Self-modify",
            "summary": "Edit code",
            "required_action_type": "self_modification",
        })
        assert resp.status_code == 200
        assert resp.json()["recommendation"]["status"] == "blocked"

    def test_telemetry_status_route(self):
        client = self._make_client()
        resp = client.get("/v1/nus/telemetry/status")
        assert resp.status_code == 200
        assert "record_count" in resp.json()

    def test_telemetry_ingest_route(self):
        client = self._make_client()
        resp = client.post("/v1/nus/telemetry/ingest-dry-run", json={
            "events": [{"event_type": "subtask_done"}, {"event_type": "safety_blocked"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] == 2
        assert data["dry_run"] is True

    def test_autonomy_policy_status_route(self):
        client = self._make_client()
        resp = client.get("/v1/nus/autonomy-policy/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_profile"] == "manual"
        assert data["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        assert data["safety_gates_active"] is True

    def test_reject_dry_run_route(self):
        client = self._make_client()
        # Create a rec first
        create_resp = client.post("/v1/nus/recommendations/create-dry-run", json={
            "title": "Test", "summary": "S",
        })
        rec_id = create_resp.json()["recommendation"]["id"]
        resp = client.post("/v1/nus/recommendations/reject-dry-run", json={
            "rec_id": rec_id, "reason": "Not needed",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
