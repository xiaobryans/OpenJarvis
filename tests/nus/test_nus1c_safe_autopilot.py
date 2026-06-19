"""NUS 1C — Safe Autopilot Learning test suite.

Tests:
  - queue append/load/list/status
  - queue deduplication
  - queue superseding
  - unsafe queue path rejection
  - redaction before queue persistence
  - safe_autopilot active for safe local analysis/dry-run
  - safe_autopilot blocks dangerous actions
  - safe_autopilot gates medium-risk actions
  - kill-switch behavior
  - cross-session failure learning
  - persisted failure pattern summary
  - telemetry ingestion from operator/agent records
  - telemetry to signals/patterns/recommendations
  - learned model-routing recommendations
  - routing recommendation does not execute model switch
  - capability status
  - doctor check
  - event logging
  - NUS 1A/1B integration
  - Wave 1–4 awareness (via imports)
  - US13 remains parked
  - no self-modification
  - no auto-commit/push/merge/deploy

Hard safety constraints enforced by tests:
  - All dangerous actions must return 'blocked' or 'kill_switch_disabled'.
  - Medium-risk actions must return 'needs_approval'.
  - Safe actions must return 'auto_allowed'.
  - Kill-switch must override all auto-allows.
  - No real execution: dry_run=True in all results.
  - Tests must use temp dirs for persistence.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. Recommendation Queue — append / load / list / status
# ---------------------------------------------------------------------------


class TestRecommendationQueueBasics:
    def test_enqueue_returns_item(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        item = q.enqueue(
            source="test",
            category="test_cat",
            title="Test recommendation",
            summary="A test recommendation item",
            required_action_type="local_analysis",
        )
        assert item.queue_id
        assert item.status in ("ready", "needs_approval", "blocked")
        assert item.title == "Test recommendation"

    def test_list_all_returns_enqueued(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        q.enqueue(source="t", category="c", title="T1", summary="S1", required_action_type="local_analysis")
        q.enqueue(source="t", category="c", title="T2", summary="S2", required_action_type="local_read")
        assert q.total_count == 2
        all_items = q.list_all()
        assert len(all_items) == 2

    def test_list_pending_excludes_terminal(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue, STATUS_REJECTED
        q = RecommendationQueue(store_dir=tmp_path)
        item = q.enqueue(source="t", category="c", title="T", summary="S", required_action_type="local_analysis")
        q.update_status(item.queue_id, STATUS_REJECTED, reason="test")
        pending = q.list_pending()
        assert all(i.queue_id != item.queue_id for i in pending)

    def test_load_after_restart(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        item = q.enqueue(source="t", category="c", title="T", summary="S", required_action_type="local_analysis")
        item_id = item.queue_id

        # Reload from disk
        q2 = RecommendationQueue(store_dir=tmp_path)
        assert q2.total_count >= 1
        loaded_item = q2.get(item_id)
        assert loaded_item is not None
        assert loaded_item.title == "T"

    def test_update_status(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue, STATUS_APPROVED
        q = RecommendationQueue(store_dir=tmp_path)
        item = q.enqueue(source="t", category="c", title="T", summary="S", required_action_type="local_analysis")
        result = q.update_status(item.queue_id, STATUS_APPROVED)
        assert result["ok"] is True
        assert q.get(item.queue_id).status == STATUS_APPROVED

    def test_summarize(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        q.enqueue(source="t", category="c", title="T", summary="S", required_action_type="local_analysis")
        s = q.summarize()
        assert s["total"] >= 1
        assert "by_status" in s
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        assert s["safety_gates_active"] is True


# ---------------------------------------------------------------------------
# 2. Queue deduplication
# ---------------------------------------------------------------------------


class TestQueueDeduplication:
    def test_dedup_key_supersedes_existing(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue, STATUS_SUPERSEDED
        q = RecommendationQueue(store_dir=tmp_path)
        item1 = q.enqueue(
            source="t", category="c", title="T1", summary="S1",
            required_action_type="local_analysis", dedup_key="dup:local_analysis:v1",
        )
        # Same dedup_key → supersedes item1
        item2 = q.enqueue(
            source="t", category="c", title="T2", summary="S2",
            required_action_type="local_analysis", dedup_key="dup:local_analysis:v1",
        )
        # item1 should be superseded in memory
        updated = q.get(item1.queue_id)
        assert updated.status == STATUS_SUPERSEDED

    def test_different_dedup_keys_no_supersede(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue, STATUS_SUPERSEDED
        q = RecommendationQueue(store_dir=tmp_path)
        item1 = q.enqueue(
            source="t", category="c", title="T1", summary="S1",
            required_action_type="local_analysis", dedup_key="dup:A",
        )
        item2 = q.enqueue(
            source="t", category="c", title="T2", summary="S2",
            required_action_type="local_analysis", dedup_key="dup:B",
        )
        assert q.get(item1.queue_id).status != STATUS_SUPERSEDED


# ---------------------------------------------------------------------------
# 3. Queue superseding
# ---------------------------------------------------------------------------


class TestQueueSupersede:
    def test_explicit_supersede(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue, STATUS_SUPERSEDED
        q = RecommendationQueue(store_dir=tmp_path)
        item1 = q.enqueue(source="t", category="c", title="T1", summary="S1", required_action_type="local_read")
        item2 = q.enqueue(source="t", category="c", title="T2", summary="S2", required_action_type="local_read")
        result = q.supersede(item1.queue_id, item2.queue_id)
        assert result["ok"] is True
        assert q.get(item1.queue_id).status == STATUS_SUPERSEDED
        assert q.get(item1.queue_id).superseded_by == item2.queue_id

    def test_supersede_unknown_id(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        result = q.supersede("nonexistent_id", "other_id")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# 4. Unsafe queue path rejection
# ---------------------------------------------------------------------------


class TestQueueUnsafePathRejection:
    def test_rejects_env_path(self):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        from openjarvis.nus.learning_store import _assert_safe_path
        import pytest
        with pytest.raises(ValueError, match="unsafe"):
            RecommendationQueue(store_dir=Path("/Users/user/.env"))

    def test_rejects_credentials_path(self):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        with pytest.raises(ValueError, match="unsafe"):
            RecommendationQueue(store_dir=Path("/Users/user/.aws/credentials"))

    def test_accepts_tmp_path(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        assert q is not None


# ---------------------------------------------------------------------------
# 5. Redaction before queue persistence
# ---------------------------------------------------------------------------


class TestQueueRedaction:
    def test_secret_values_redacted_in_queue_file(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        q.enqueue(
            source="t", category="c", title="T", summary="S",
            required_action_type="local_analysis",
            evidence={"api_key": "sk-abcdef1234567890abcdef1234567890", "note": "test"},
        )
        queue_file = tmp_path / "recommendation_queue.jsonl"
        content = queue_file.read_text()
        assert "sk-abcdef" not in content
        assert "[REDACTED]" in content or "REDACTED" in content


# ---------------------------------------------------------------------------
# 6. Safe autopilot — active for safe local analysis/dry-run
# ---------------------------------------------------------------------------


class TestSafeAutopilotSafeActions:
    def test_local_analysis_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("local_analysis")
        assert dec.decision == "auto_allowed"

    def test_local_read_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("local_read")
        assert dec.decision == "auto_allowed"

    def test_scorecard_generation_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("scorecard_generation")
        assert dec.decision == "auto_allowed"

    def test_telemetry_normalization_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("telemetry_normalization")
        assert dec.decision == "auto_allowed"

    def test_failure_pattern_summarization_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("failure_pattern_summarization")
        assert dec.decision == "auto_allowed"

    def test_dry_run_recommendation_execution_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("dry_run_recommendation_execution")
        assert dec.decision == "auto_allowed"

    def test_validation_planning_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("validation_planning")
        assert dec.decision == "auto_allowed"

    def test_dry_run_result_is_dry_run(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("local_analysis")
        assert dec.dry_run_result is not None
        assert dec.dry_run_result.get("dry_run") is True


# ---------------------------------------------------------------------------
# 7. Safe autopilot blocks dangerous actions
# ---------------------------------------------------------------------------


class TestSafeAutopilotDangerousBlocked:
    @pytest.mark.parametrize("action", [
        "self_modification",
        "code_edit",
        "auto_commit",
        "auto_push",
        "auto_merge",
        "deploy",
        "secret_access",
        "safety_policy_change",
        "destructive_delete",
        "production_action",
        "payment_action",
        "financial_action",
    ])
    def test_dangerous_action_blocked(self, action):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate(action)
        assert dec.decision == "blocked", f"Expected blocked for {action}, got {dec.decision}"

    def test_no_self_modification(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot()
        dec = ap.evaluate("self_modification")
        assert dec.decision == "blocked"

    def test_no_auto_commit(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot()
        dec = ap.evaluate("auto_commit")
        assert dec.decision == "blocked"

    def test_no_deploy(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot()
        dec = ap.evaluate("deploy")
        assert dec.decision == "blocked"

    def test_no_secret_access(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot()
        dec = ap.evaluate("secret_access")
        assert dec.decision == "blocked"


# ---------------------------------------------------------------------------
# 8. Safe autopilot gates medium-risk actions (needs_approval)
# ---------------------------------------------------------------------------


class TestSafeAutopilotMediumRisk:
    @pytest.mark.parametrize("action", [
        "file_write",
        "external_provider_setup",
        "browser_automation",
        "external_send",
        "connector_setup",
        "account_auth_change",
    ])
    def test_medium_risk_needs_approval(self, action):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate(action)
        assert dec.decision == "needs_approval", f"Expected needs_approval for {action}, got {dec.decision}"


# ---------------------------------------------------------------------------
# 9. Kill-switch behavior
# ---------------------------------------------------------------------------


class TestKillSwitch:
    def test_kill_switch_disables_safe_actions(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=True)
        dec = ap.evaluate("local_analysis")
        assert dec.decision == "kill_switch_disabled"
        assert dec.kill_switch_active is True

    def test_kill_switch_overrides_auto_allowed(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot, SAFE_AUTO_ACTIONS
        ap = SafeAutopilot(kill_switch=True)
        for action in SAFE_AUTO_ACTIONS:
            dec = ap.evaluate(action)
            assert dec.decision == "kill_switch_disabled", f"Kill switch should disable {action}"

    def test_kill_switch_also_returns_disabled_for_dangerous(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=True)
        # With kill switch, dangerous also returns kill_switch_disabled (not blocked)
        dec = ap.evaluate("self_modification")
        assert dec.decision == "kill_switch_disabled"

    def test_kill_switch_toggle(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        dec = ap.evaluate("local_analysis")
        assert dec.decision == "auto_allowed"

        ap.kill_switch = True
        dec2 = ap.evaluate("local_analysis")
        assert dec2.decision == "kill_switch_disabled"

    def test_status_reflects_kill_switch(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=True)
        status = ap.get_status()
        assert status["kill_switch"] is True


# ---------------------------------------------------------------------------
# 10. Cross-session failure learning
# ---------------------------------------------------------------------------


class TestCrossSessionFailureLearning:
    def test_analyze_returns_list(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner
        learner = FailureLearner(store_dir=tmp_path)
        result = learner.analyze()
        assert isinstance(result, list)

    def test_analyze_from_persisted_outcomes(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner, PATTERN_VALIDATION_FAILURE
        from openjarvis.nus.learning_store import LearningStore

        # Pre-populate store with validation failures
        store = LearningStore(store_dir=tmp_path)
        for i in range(3):
            store.append_outcome({
                "task_id": f"task_{i}",
                "session_id": f"session_{i}",
                "status": "failure",
                "task_type": "validation_failed",
                "failure_category": "validation",
                "recorded_at": time.time() - i * 100,
            })

        learner = FailureLearner(store_dir=tmp_path)
        patterns = learner.analyze()
        cats = [p.category for p in patterns]
        assert PATTERN_VALIDATION_FAILURE in cats

    def test_failure_pattern_has_prevention(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner
        from openjarvis.nus.learning_store import LearningStore

        store = LearningStore(store_dir=tmp_path)
        for i in range(3):
            store.append_outcome({
                "task_id": f"t{i}", "session_id": "s1",
                "status": "failure", "task_type": "validation_failed",
                "recorded_at": time.time(),
            })

        learner = FailureLearner(store_dir=tmp_path)
        patterns = learner.analyze()
        for p in patterns:
            assert p.recommended_prevention  # must have prevention guidance

    def test_no_auto_execution_in_failure_learning(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner
        learner = FailureLearner(store_dir=tmp_path)
        # analyze must return patterns — never execute any fix
        patterns = learner.analyze()
        # No execution attribute should be present in patterns
        for p in patterns:
            d = p.to_dict()
            assert "auto_executed" not in d
            assert "fix_applied" not in d

    def test_get_summary_structure(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner
        learner = FailureLearner(store_dir=tmp_path)
        learner.analyze()
        s = learner.get_summary()
        assert "pattern_count" in s
        assert "us13_voice_status" in s
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        assert s["safety_gates_active"] is True
        assert s["no_auto_execution"] is True

    def test_escalation_recommended_at_threshold(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner, ESCALATION_THRESHOLD
        from openjarvis.nus.learning_store import LearningStore

        store = LearningStore(store_dir=tmp_path)
        for i in range(ESCALATION_THRESHOLD + 1):
            store.append_outcome({
                "task_id": f"t{i}", "session_id": "s1",
                "status": "failure", "task_type": "validation_failed",
                "recorded_at": time.time(),
            })

        learner = FailureLearner(store_dir=tmp_path)
        patterns = learner.analyze()
        escalated = [p for p in patterns if p.escalation_recommended]
        assert len(escalated) >= 1


# ---------------------------------------------------------------------------
# 11. Telemetry ingestion from operator/agent records
# ---------------------------------------------------------------------------


class TestTelemetryOperatorIngestion:
    def test_ingest_operator_record(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        rec = tn.ingest_operator_record({
            "agent_name": "test_agent",
            "task_id": "t001",
            "action_type": "local_analysis",
            "result": "success",
            "model_used": "sonnet-4.6",
            "estimated_cost_usd": 0.002,
            "risk_level": "low",
        })
        assert rec.source_event_type == "operator_agent_record"
        assert rec.model_used == "sonnet-4.6"
        assert rec.estimated_cost_usd == 0.002
        assert rec.is_failure is False
        assert rec.is_blocked is False

    def test_ingest_operator_record_blocked(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        rec = tn.ingest_operator_record({
            "agent_name": "agent_b",
            "action_type": "deploy",
            "result": "blocked",
            "blocked_reason": "deploy is permanently blocked",
        })
        assert rec.is_blocked is True

    def test_ingest_operator_record_failure(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        rec = tn.ingest_operator_record({
            "agent_name": "agent_c",
            "action_type": "validation_run",
            "result": "failure",
            "validation_status": False,
        })
        assert rec.is_failure is True

    def test_ingest_operator_record_tolerates_missing_fields(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        rec = tn.ingest_operator_record({})
        assert rec.source_event_type == "operator_agent_record"
        assert rec.is_blocked is False

    def test_operator_record_redacts_secrets(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        rec = tn.ingest_operator_record({
            "agent_name": "agent_x",
            "api_key": "sk-supersecretkey1234567890abcdef",
            "action_type": "local_read",
            "result": "success",
        })
        # The secret should not appear in metadata
        meta_str = str(rec.metadata)
        assert "sk-supersecret" not in meta_str

    def test_ingest_operator_batch(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        records = [
            {"agent_name": "a1", "action_type": "local_read", "result": "success"},
            {"agent_name": "a2", "action_type": "local_analysis", "result": "success"},
            {"agent_name": "a3", "action_type": "deploy", "result": "blocked"},
        ]
        count = tn.ingest_operator_batch(records)
        assert count == 3

    def test_to_routing_observations(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        tn.ingest_operator_record({
            "agent_name": "a1", "action_type": "local_analysis",
            "result": "success", "model_used": "sonnet-4.6", "estimated_cost_usd": 0.003,
        })
        obs = tn.to_routing_observations()
        assert len(obs) >= 1
        assert obs[0]["model_used"] == "sonnet-4.6"

    def test_telemetry_maps_to_signals(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        tn.ingest_operator_batch([
            {"agent_name": "a1", "action_type": "local_analysis", "result": "failure"},
            {"agent_name": "a2", "action_type": "local_analysis", "result": "failure"},
        ])
        signals = tn.to_signals()
        assert len(signals) >= 2

    def test_telemetry_maps_to_recommendations(self, tmp_path):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        tn = TelemetryNormalizer()
        for _ in range(3):
            tn.ingest_operator_record({
                "agent_name": "a", "action_type": "deploy",
                "result": "blocked", "blocked_reason": "deploy blocked",
            })
        recs = tn.to_recommendations()
        assert isinstance(recs, list)


# ---------------------------------------------------------------------------
# 12. Learned model-routing recommendations
# ---------------------------------------------------------------------------


class TestLearnedRouting:
    def test_recommend_for_docs_low_risk(self):
        from openjarvis.nus.learned_routing import LearnedRouter, TIER_CHEAP_FAST, TASK_DOCS_ONLY
        router = LearnedRouter()
        rec = router.recommend_for_task(
            task_category=TASK_DOCS_ONLY,
            risk_level="low",
            complexity_level="simple",
        )
        assert rec.recommended_tier == TIER_CHEAP_FAST

    def test_recommend_strong_for_architecture(self):
        from openjarvis.nus.learned_routing import LearnedRouter, TIER_STRONG, TASK_ARCHITECTURE
        router = LearnedRouter()
        rec = router.recommend_for_task(
            task_category=TASK_ARCHITECTURE,
            risk_level="high",
            complexity_level="complex",
        )
        assert rec.recommended_tier == TIER_STRONG

    def test_recommend_strong_for_security(self):
        from openjarvis.nus.learned_routing import LearnedRouter, TIER_STRONG, TASK_SECURITY
        router = LearnedRouter()
        rec = router.recommend_for_task(task_category=TASK_SECURITY, risk_level="high")
        assert rec.recommended_tier == TIER_STRONG

    def test_recommend_strong_for_governance(self):
        from openjarvis.nus.learned_routing import LearnedRouter, TIER_STRONG, TASK_GOVERNANCE
        router = LearnedRouter()
        rec = router.recommend_for_task(task_category=TASK_GOVERNANCE, risk_level="medium")
        assert rec.recommended_tier == TIER_STRONG

    def test_escalate_after_validation_failures(self):
        from openjarvis.nus.learned_routing import LearnedRouter, TIER_STRONG
        router = LearnedRouter()
        rec = router.recommend_for_task(
            task_category="code_moderate",
            risk_level="medium",
            validation_failures=3,
        )
        assert rec.recommended_tier == TIER_STRONG

    def test_recommendation_does_not_execute_model_switch(self):
        from openjarvis.nus.learned_routing import LearnedRouter
        router = LearnedRouter()
        rec = router.recommend_for_task(task_category="docs_only", risk_level="low")
        # Enforcement note must clarify this is advisory only
        assert "recommendation" in rec.enforcement_note.lower() or "advisory" in rec.enforcement_note.lower()

    def test_recommend_from_scorecard(self):
        from openjarvis.nus.learned_routing import LearnedRouter
        router = LearnedRouter()
        scorecard = {
            "risk_level": "low",
            "confidence_level": "high",
            "failure_count": 0,
            "blocked_count": 0,
            "validation_fail_count": 0,
            "total_count": 10,
            "model_routing_observations": ["sonnet-4.6: 10"],
        }
        rec = router.recommend_from_scorecard(scorecard, task_category="code_simple")
        assert rec.recommended_tier in ("cheap_fast", "balanced", "strong", "stop")

    def test_recommend_stop_on_high_failure_rate(self):
        from openjarvis.nus.learned_routing import LearnedRouter, TIER_STOP
        router = LearnedRouter()
        scorecard = {
            "risk_level": "high",
            "confidence_level": "high",
            "failure_count": 8,
            "blocked_count": 2,
            "validation_fail_count": 5,
            "total_count": 10,
            "model_routing_observations": [],
        }
        rec = router.recommend_from_scorecard(scorecard)
        assert rec.recommended_tier == TIER_STOP

    def test_recommend_from_telemetry(self):
        from openjarvis.nus.learned_routing import LearnedRouter
        router = LearnedRouter()
        telemetry = [
            {"is_failure": False, "is_blocked": False, "model_used": "sonnet-4.6", "estimated_cost_usd": 0.001},
            {"is_failure": False, "is_blocked": False, "model_used": "sonnet-4.6", "estimated_cost_usd": 0.002},
        ]
        rec = router.recommend_from_telemetry(telemetry)
        assert rec is not None
        assert rec.recommended_tier in ("cheap_fast", "balanced", "strong", "stop")

    def test_get_status(self):
        from openjarvis.nus.learned_routing import LearnedRouter
        router = LearnedRouter()
        router.recommend_for_task("docs_only", "low", "simple")
        status = router.get_status()
        assert status["recommendation_count"] >= 1
        assert "enforcement_note" in status
        assert status["us13_voice_status"] == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 13. Capability status
# ---------------------------------------------------------------------------


class TestCapabilityStatus:
    def test_nus1c_capability_present(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        ids = [c.capability_id for c in caps]
        assert "nus1c_safe_autopilot_learning" in ids

    def test_nus1c_capability_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        nus1c = caps.get("nus1c_safe_autopilot_learning")
        assert nus1c is not None
        assert nus1c.status == STATUS_READY

    def test_nus1a_1b_still_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        assert caps["nus1a_learning_foundation"].status == STATUS_READY
        assert caps["nus1b_recommendation_workflow"].status == STATUS_READY

    def test_nus_status_summary(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        s = get_capabilities_summary()
        assert s["nus1c_status"] == "ready"
        assert s["nus1d_plus_status"] == "not_started"


# ---------------------------------------------------------------------------
# 14. Doctor check
# ---------------------------------------------------------------------------


class TestDoctorCheck:
    def test_nus1c_doctor_check_passes(self):
        from openjarvis.doctor.checks import check_nus1c_safe_autopilot, CheckStatus
        result = check_nus1c_safe_autopilot()
        assert result.check_id == "nus1c_safe_autopilot"
        assert result.status == CheckStatus.PASS, f"Doctor check failed: {result.summary}"

    def test_doctor_check_in_all_checks(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        fn_names = [fn.__name__ for fn in _ALL_CHECK_FNS]
        assert "check_nus1c_safe_autopilot" in fn_names


# ---------------------------------------------------------------------------
# 15. Event logging (smoke test — not strict assertion on content)
# ---------------------------------------------------------------------------


class TestEventLogging:
    def test_queue_enqueue_logs_event(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        # Should not raise — even if WorkbenchEventLog is unavailable
        q.enqueue(source="t", category="c", title="T", summary="S", required_action_type="local_analysis")

    def test_autopilot_evaluate_logs_event(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        ap.evaluate("local_analysis")  # Should not raise

    def test_failure_learner_logs_event(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner
        learner = FailureLearner(store_dir=tmp_path)
        learner.analyze()  # Should not raise

    def test_routing_logs_event(self):
        from openjarvis.nus.learned_routing import LearnedRouter
        router = LearnedRouter()
        router.recommend_for_task("docs_only", "low")  # Should not raise


# ---------------------------------------------------------------------------
# 16. NUS 1A/1B integration
# ---------------------------------------------------------------------------


class TestNUS1A1BIntegration:
    def test_nus1c_imports_do_not_break_1a(self):
        from openjarvis.nus.learning_foundation import LearningFoundation
        f = LearningFoundation()
        assert f.record_count == 0

    def test_nus1c_imports_do_not_break_1b(self):
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        r = RecommendationRegistry()
        assert r.list_all() == []

    def test_nus1c_queue_uses_1b_statuses(self):
        from openjarvis.nus.recommendation_queue import (
            STATUS_DRAFT, STATUS_READY, STATUS_NEEDS_APPROVAL,
            STATUS_APPROVED, STATUS_REJECTED, STATUS_BLOCKED,
            STATUS_EXECUTED_DRY_RUN, STATUS_SUPERSEDED,
        )
        from openjarvis.nus.recommendation_registry import (
            STATUS_DRAFT as D, STATUS_READY as R, STATUS_NEEDS_APPROVAL as NA,
            STATUS_APPROVED as A, STATUS_REJECTED as RE, STATUS_BLOCKED as BL,
            STATUS_EXECUTED_DRY_RUN as ED, STATUS_SUPERSEDED as SU,
        )
        assert STATUS_DRAFT == D
        assert STATUS_READY == R
        assert STATUS_NEEDS_APPROVAL == NA
        assert STATUS_APPROVED == A
        assert STATUS_REJECTED == RE
        assert STATUS_BLOCKED == BL
        assert STATUS_EXECUTED_DRY_RUN == ED
        assert STATUS_SUPERSEDED == SU

    def test_learning_store_usable_by_failure_learner(self, tmp_path):
        from openjarvis.nus.learning_store import LearningStore
        from openjarvis.nus.failure_learning import FailureLearner
        store = LearningStore(store_dir=tmp_path)
        store.append_outcome({"task_id": "t1", "status": "failure", "task_type": "validation_failed"})
        learner = FailureLearner(store_dir=tmp_path)
        patterns = learner.analyze()
        assert isinstance(patterns, list)


# ---------------------------------------------------------------------------
# 17. Wave 1–4 awareness (import smoke test)
# ---------------------------------------------------------------------------


class TestWaveAwareness:
    def test_nus1c_snapshot_includes_wave_summaries(self, tmp_path):
        from openjarvis.nus.learning_foundation import get_learning_foundation
        f = get_learning_foundation()
        snap = f.get_snapshot()
        d = snap.to_dict()
        assert "wave1_summary" in d
        assert "wave2_summary" in d
        assert "wave3_summary" in d
        assert "wave4_summary" in d


# ---------------------------------------------------------------------------
# 18. US13 voice remains HOLD/UNSAFE/PARKED
# ---------------------------------------------------------------------------


class TestUS13Parked:
    def test_autopilot_status_us13_parked(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot()
        status = ap.get_status()
        assert status["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_queue_summary_us13_parked(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        q = RecommendationQueue(store_dir=tmp_path)
        s = q.summarize()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_routing_status_us13_parked(self):
        from openjarvis.nus.learned_routing import LearnedRouter
        router = LearnedRouter()
        status = router.get_status()
        assert status["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_failure_learning_summary_us13_parked(self, tmp_path):
        from openjarvis.nus.failure_learning import FailureLearner
        learner = FailureLearner(store_dir=tmp_path)
        learner.analyze()
        s = learner.get_summary()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_autonomy_policy_us13_parked(self):
        from openjarvis.nus.autonomy_policy import get_policy_status
        s = get_policy_status()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 19. No self-modification, no auto-commit/push/merge/deploy (explicit proof)
# ---------------------------------------------------------------------------


class TestSafetyProof:
    def test_no_self_modification_blocked(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        assert ap.evaluate("self_modification").decision == "blocked"

    def test_no_auto_commit_blocked(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        assert ap.evaluate("auto_commit").decision == "blocked"

    def test_no_auto_push_blocked(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        assert ap.evaluate("auto_push").decision == "blocked"

    def test_no_auto_merge_blocked(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        assert ap.evaluate("auto_merge").decision == "blocked"

    def test_no_deploy_blocked(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        assert ap.evaluate("deploy").decision == "blocked"

    def test_no_external_send_needs_approval(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        assert ap.evaluate("external_send").decision == "needs_approval"

    def test_no_source_code_edit_blocked(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot(kill_switch=False)
        assert ap.evaluate("code_edit").decision == "blocked"

    def test_safety_gates_active_in_status(self):
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        ap = SafeAutopilot()
        s = ap.get_status()
        assert s["safety_gates_active"] is True
        assert s["no_self_modification"] is True
        assert s["no_auto_commit"] is True
        assert s["no_auto_push"] is True
        assert s["no_auto_merge"] is True
        assert s["no_deploy"] is True
        assert s["no_external_sends"] is True
        assert s["no_secret_access"] is True

    def test_queue_blocked_action_cannot_be_approved(self, tmp_path):
        from openjarvis.nus.recommendation_queue import RecommendationQueue, STATUS_BLOCKED, STATUS_APPROVED
        q = RecommendationQueue(store_dir=tmp_path)
        item = q.enqueue(
            source="t", category="c", title="T", summary="S",
            required_action_type="self_modification",  # → blocked
        )
        assert item.status == STATUS_BLOCKED
        result = q.update_status(item.queue_id, STATUS_APPROVED)
        assert result["ok"] is False
        assert q.get(item.queue_id).status == STATUS_BLOCKED

    def test_routing_recommendation_advisory_only(self):
        from openjarvis.nus.learned_routing import LearnedRouter
        router = LearnedRouter()
        rec = router.recommend_for_task("architecture", "high", "complex")
        # No model is actually switched
        d = rec.to_dict()
        assert "enforcement_note" in d
        note = d["enforcement_note"].lower()
        assert "recommendation" in note or "advisory" in note


# ---------------------------------------------------------------------------
# 20. Autonomy profile status
# ---------------------------------------------------------------------------


class TestAutonomyProfileStatus:
    def test_safe_autopilot_active_in_profile_status(self):
        from openjarvis.nus.safe_autopilot import get_autonomy_profile_status
        s = get_autonomy_profile_status()
        assert s["profiles"]["safe_autopilot"]["status"] == "active"

    def test_power_autopilot_not_activated(self):
        from openjarvis.nus.safe_autopilot import get_autonomy_profile_status
        s = get_autonomy_profile_status()
        assert "not_activated" in s["profiles"]["power_autopilot"]["status"]

    def test_founder_override_not_activated(self):
        from openjarvis.nus.safe_autopilot import get_autonomy_profile_status
        s = get_autonomy_profile_status()
        assert "not_activated" in s["profiles"]["founder_override_session"]["status"]

    def test_production_restricted_not_activated(self):
        from openjarvis.nus.safe_autopilot import get_autonomy_profile_status
        s = get_autonomy_profile_status()
        assert "not_activated" in s["profiles"]["production_restricted"]["status"]

    def test_kill_switch_behavior_documented(self):
        from openjarvis.nus.safe_autopilot import get_autonomy_profile_status
        s = get_autonomy_profile_status()
        assert "kill_switch_behavior" in s
        assert "kill_switch" in s["kill_switch_behavior"].lower()

    def test_autonomy_policy_catalog_safe_autopilot_active(self):
        from openjarvis.nus.autonomy_policy import get_policy_catalog, PROFILE_SAFE_AUTOPILOT
        catalog = get_policy_catalog()
        safe = catalog[PROFILE_SAFE_AUTOPILOT]
        assert safe.activation_status == "active"
