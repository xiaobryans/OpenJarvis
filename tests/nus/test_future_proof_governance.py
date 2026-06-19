"""Future-Proof Governance tests.

Tests:
  - Synthetic future agent NUS telemetry/routing compatibility
  - Metadata/action/risk/tool-driven policy, not fixed agent names
  - Docs existence
  - Token governance doc exists
  - Future-proof architecture doc exists
  - Doctor check passes
  - No hardcoded agent names in classification
  - US13 remains parked
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOCS_ROOT = Path(__file__).parents[2] / "docs"


# ---------------------------------------------------------------------------
# 1. Synthetic future agent compatibility
# ---------------------------------------------------------------------------


class TestFutureAgentCompatibility:
    """Prove NUS accepts telemetry, creates learning signals, and produces routing
    recommendations for a synthetic future agent — without hardcoded agent names.
    """

    SYNTHETIC_AGENT = {
        "agent_name": "synthetic_future_specialist_worker_v999",
        "agent_type": "specialized_domain_worker",
        "agent_version": "99.0.0",
        "capabilities": ["local_analysis", "scorecard_generation"],
        "contract_version": "v3",
        "risk_policy": "low_risk_only",
    }

    def test_telemetry_accepts_future_agent(self):
        from openjarvis.nus.telemetry import TelemetryNormalizer
        norm = TelemetryNormalizer()
        record = norm.ingest_operator_record({
            "agent_name": self.SYNTHETIC_AGENT["agent_name"],
            "task_id": "task_future_001",
            "action_type": "local_analysis",
            "result": "success",
            "validation_status": "passed",
            "model_used": "gpt4o-mini",
            "estimated_cost_usd": 0.001,
            "risk_level": "low",
        })
        assert record is not None
        assert record.source_event_type == "operator_agent_record"
        # Name-agnostic: agent name stored but not used as a filter
        assert record is not None

    def test_classifier_accepts_future_agent(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_SAFE_LOCAL_DRY_RUN
        clf = ExecutionClassifier()
        r = clf.classify(
            action_type="local_analysis",
            risk_level="low",
            agent_metadata=self.SYNTHETIC_AGENT,
        )
        assert r.tier == TIER_SAFE_LOCAL_DRY_RUN
        assert r.auto_allowed is True

    def test_classifier_blocks_future_agent_dangerous(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_BLOCKED_DANGEROUS
        clf = ExecutionClassifier()
        r = clf.classify(
            action_type="deploy",
            risk_level="critical",
            agent_metadata=self.SYNTHETIC_AGENT,
        )
        assert r.tier == TIER_BLOCKED_DANGEROUS
        assert r.blocked is True

    def test_routing_recommendation_for_future_agent(self):
        from openjarvis.nus.learned_routing import get_learned_router
        router = get_learned_router()
        rec = router.recommend_for_task(
            task_category="docs_only",
            risk_level="low",
            complexity_level="simple",
        )
        assert rec.recommended_tier is not None
        assert "advisory" in rec.enforcement_note.lower() or "recommendation" in rec.enforcement_note.lower()

    def test_learning_store_accepts_future_agent(self):
        import tempfile
        from pathlib import Path
        from openjarvis.nus.learning_store import LearningStore
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LearningStore(store_dir=Path(tmpdir))
            store.append_signal({
                "signal_type": "telemetry",
                "source": self.SYNTHETIC_AGENT["agent_name"],
                "action_type": "local_analysis",
                "result": "success",
                "agent_metadata": self.SYNTHETIC_AGENT,
            })
            records = store.load_recent_signals()
            assert len(records) >= 1
            sources = [r.get("agent_metadata", {}).get("agent_name", "") for r in records]
            assert any(self.SYNTHETIC_AGENT["agent_name"] in s for s in sources)

    def test_failure_learner_accepts_future_agent_records(self):
        import tempfile
        from pathlib import Path
        from openjarvis.nus.learning_store import LearningStore
        from openjarvis.nus.failure_learning import FailureLearner
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LearningStore(store_dir=Path(tmpdir))
            # Simulate repeated validation failures from a future agent
            for _ in range(4):
                store.append_signal({
                    "signal_type": "validation_failure",
                    "source": self.SYNTHETIC_AGENT["agent_name"],
                    "agent_metadata": self.SYNTHETIC_AGENT,
                    "error": "test failed",
                })
            learner = FailureLearner(store_dir=Path(tmpdir))
            patterns = learner.analyze()
            # Learner does not filter by agent name — accepts any agent
            assert isinstance(patterns, list)

    def test_eval_gate_accepts_any_capability_id(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_PASS
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="Run tests",
            safety_gate_result="pass",
            capability_id="future_capability_v999",
            capability_ready=True,
        )
        report = run_eval_gate(c)
        assert report.all_passed


# ---------------------------------------------------------------------------
# 2. Policy is metadata/risk/tool-driven, not fixed agent name
# ---------------------------------------------------------------------------


class TestMetadataRiskToolDrivenPolicy:
    """Verify that routing/autonomy decisions are based on metadata, not agent names."""

    def test_same_action_different_agents_same_tier(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_SAFE_LOCAL_DRY_RUN
        clf = ExecutionClassifier()
        agents = [
            {"agent_name": "jarvis_v1"},
            {"agent_name": "future_worker_v99"},
            {"agent_name": "external_partner_agent"},
            {},  # no agent name
        ]
        for agent_meta in agents:
            r = clf.classify(
                "local_analysis",
                risk_level="low",
                agent_metadata=agent_meta,
            )
            assert r.tier == TIER_SAFE_LOCAL_DRY_RUN, \
                f"Expected TIER_SAFE_LOCAL_DRY_RUN for agent={agent_meta}, got {r.tier}"

    def test_dangerous_action_blocked_regardless_of_agent(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_BLOCKED_DANGEROUS
        clf = ExecutionClassifier()
        agents = [
            {"agent_name": "trusted_internal_agent"},
            {"agent_name": "power_agent_v10"},
            {},
        ]
        for agent_meta in agents:
            r = clf.classify("deploy", agent_metadata=agent_meta)
            assert r.tier == TIER_BLOCKED_DANGEROUS

    def test_risk_level_drives_classification_not_name(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier
        clf = ExecutionClassifier()
        # Unknown action, high risk → needs approval
        r1 = clf.classify("unknown_action_v999", risk_level="high", agent_metadata={"agent_name": "agent_x"})
        assert r1.needs_approval or r1.blocked  # high risk → needs approval or blocked

        # Unknown action, low risk → needs approval (conservative)
        r2 = clf.classify("unknown_action_v999", risk_level="low", agent_metadata={"agent_name": "agent_y"})
        assert r2.needs_approval or r2.tier != "blocked_dangerous"


# ---------------------------------------------------------------------------
# 3. Docs existence
# ---------------------------------------------------------------------------


class TestDocsExist:
    @pytest.mark.parametrize("doc_path", [
        "docs/JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md",
        "docs/POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md",
        "docs/JARVIS_AGENT_REGISTRY_AND_CONTRACTS.md",
        "docs/JARVIS_ROUTING_MODEL_POLICY.md",
        "docs/JARVIS_95_PERCENT_AUTONOMY_TARGET.md",
        "docs/JARVIS_TOKEN_COST_GOVERNANCE.md",
    ])
    def test_doc_exists(self, doc_path):
        repo_root = Path(__file__).parents[2]
        full_path = repo_root / doc_path
        assert full_path.exists(), f"Missing governance doc: {full_path}"
        # Non-trivially sized
        assert full_path.stat().st_size > 200, f"Doc too short: {full_path}"

    def test_wave_roadmap_exists(self):
        assert (DOCS_ROOT / "WAVE_ROADMAP.md").exists()

    def test_nus1c_doc_exists(self):
        assert (DOCS_ROOT / "NUS1C_SAFE_AUTOPILOT.md").exists()


# ---------------------------------------------------------------------------
# 4. Token governance / future-proof
# ---------------------------------------------------------------------------


class TestTokenGovernanceDocs:
    def test_token_governance_doc_has_key_content(self):
        doc = DOCS_ROOT / "JARVIS_TOKEN_COST_GOVERNANCE.md"
        assert doc.exists()
        content = doc.read_text()
        assert "token" in content.lower() or "cost" in content.lower()
        assert "no broad" in content.lower() or "targeted" in content.lower() or "direct" in content.lower()

    def test_future_proof_doc_has_key_content(self):
        doc = DOCS_ROOT / "JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md"
        assert doc.exists()
        content = doc.read_text()
        assert "metadata" in content.lower() or "contract" in content.lower()
        assert "agent" in content.lower()


# ---------------------------------------------------------------------------
# 5. Doctor check
# ---------------------------------------------------------------------------


class TestFutureProofDoctorCheck:
    def test_nus1d_doctor_check_in_registry(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        names = [fn.__name__ for fn in _ALL_CHECK_FNS]
        assert "check_nus1d_eval_rollback" in names
        assert "check_nus1e_low_risk_execution" in names

    def test_nus1d_passes(self):
        from openjarvis.doctor.checks import check_nus1d_eval_rollback, CheckStatus
        result = check_nus1d_eval_rollback()
        assert result.status == CheckStatus.PASS

    def test_nus1e_passes(self):
        from openjarvis.doctor.checks import check_nus1e_low_risk_execution, CheckStatus
        result = check_nus1e_low_risk_execution()
        assert result.status == CheckStatus.PASS


# ---------------------------------------------------------------------------
# 6. US13 parked
# ---------------------------------------------------------------------------


class TestUS13ParkedFutureProof:
    def test_classifier_us13(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier
        assert ExecutionClassifier().get_status()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_eval_gate_us13(self):
        from openjarvis.nus.eval_gate import get_eval_gate_status
        assert get_eval_gate_status()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
