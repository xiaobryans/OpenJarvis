"""NUS 1E — Low-Risk Execution Foundation tests.

Tests:
  - low-risk execution classifier (safe local, docs, medium, blocked)
  - secret file rejection
  - deploy artifact rejection
  - metadata-driven (not fixed agent names)
  - auto-commit candidate dry-run
  - temp git repo only for real commit
  - no auto-push/merge/deploy
  - kill-switch blocks auto-commit
  - production gate blocked
  - future synthetic agent compatibility
  - doctor check passes
  - US13 remains parked
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. Execution Classifier — safe local
# ---------------------------------------------------------------------------


class TestClassifierSafeLocal:
    @pytest.mark.parametrize("action", [
        "local_read", "local_analysis", "local_validation",
        "scorecard_generation", "telemetry_normalization",
        "failure_pattern_summarization", "dry_run_recommendation_execution",
    ])
    def test_safe_local_auto_allowed(self, action):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_SAFE_LOCAL_DRY_RUN
        clf = ExecutionClassifier()
        r = clf.classify(action, risk_level="low")
        assert r.tier == TIER_SAFE_LOCAL_DRY_RUN
        assert r.auto_allowed is True
        assert r.blocked is False

    def test_safe_docs_auto_allowed(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_SAFE_DOCS_METADATA
        clf = ExecutionClassifier()
        r = clf.classify("docs_write", risk_level="low", file_targets=["docs/readme.md"])
        assert r.tier == TIER_SAFE_DOCS_METADATA
        assert r.auto_allowed is True

    def test_docs_with_non_doc_files_escalated(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_MEDIUM_FILE_WRITE
        clf = ExecutionClassifier()
        r = clf.classify(
            "docs_write",
            risk_level="low",
            file_targets=["docs/readme.md", "src/main.py"],  # non-doc file
        )
        assert r.tier == TIER_MEDIUM_FILE_WRITE
        assert r.needs_approval is True


# ---------------------------------------------------------------------------
# 2. Classifier — blocked actions
# ---------------------------------------------------------------------------


class TestClassifierBlocked:
    @pytest.mark.parametrize("action", [
        "self_modification", "deploy", "auto_push", "auto_merge",
        "secret_access", "safety_policy_change", "production_action",
    ])
    def test_blocked_actions(self, action):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_BLOCKED_DANGEROUS
        clf = ExecutionClassifier()
        r = clf.classify(action)
        assert r.tier == TIER_BLOCKED_DANGEROUS
        assert r.blocked is True

    def test_medium_risk_needs_approval(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_MEDIUM_FILE_WRITE
        clf = ExecutionClassifier()
        r = clf.classify("file_write")
        assert r.tier == TIER_MEDIUM_FILE_WRITE
        assert r.needs_approval is True


# ---------------------------------------------------------------------------
# 3. Secret file rejection
# ---------------------------------------------------------------------------


class TestSecretFileRejection:
    @pytest.mark.parametrize("secret_file", [
        ".env", ".env.local", ".ssh/id_rsa", ".aws/credentials",
        "secrets/db_password", "config/api_key.json",
    ])
    def test_secret_file_blocked(self, secret_file):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_BLOCKED_DANGEROUS
        clf = ExecutionClassifier()
        r = clf.classify("docs_write", file_targets=[secret_file, "docs/readme.md"])
        assert r.tier == TIER_BLOCKED_DANGEROUS
        assert r.blocked is True
        assert r.secret_files_detected

    def test_no_secret_files_allowed(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_SAFE_DOCS_METADATA
        clf = ExecutionClassifier()
        r = clf.classify("docs_write", file_targets=["docs/readme.md"])
        assert r.tier == TIER_SAFE_DOCS_METADATA
        assert r.secret_files_detected == []


# ---------------------------------------------------------------------------
# 4. Deploy artifact rejection
# ---------------------------------------------------------------------------


class TestDeployArtifactRejection:
    @pytest.mark.parametrize("artifact", [
        "dist/app.dmg", "build/app.pkg", "node_modules/react/index.js",
        ".next/static/main.js",
    ])
    def test_deploy_artifact_blocked(self, artifact):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_BLOCKED_DANGEROUS
        clf = ExecutionClassifier()
        r = clf.classify("file_write", file_targets=[artifact])
        assert r.tier == TIER_BLOCKED_DANGEROUS
        assert r.blocked is True


# ---------------------------------------------------------------------------
# 5. Metadata-driven / agent-name-agnostic
# ---------------------------------------------------------------------------


class TestMetadataDriven:
    def test_future_agent_classified_by_metadata(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_SAFE_LOCAL_DRY_RUN
        clf = ExecutionClassifier()
        # A future agent with a novel name — classified by metadata, not name
        r = clf.classify(
            action_type="local_analysis",
            risk_level="low",
            agent_metadata={
                "agent_name": "future_specialist_worker_v99",
                "agent_type": "autonomous_analysis_worker",
                "capabilities": ["local_analysis", "telemetry_push"],
                "contract_version": "v2",
            },
        )
        assert r.tier == TIER_SAFE_LOCAL_DRY_RUN
        assert r.auto_allowed is True

    def test_dangerous_tool_requirement_blocked(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_BLOCKED_DANGEROUS
        clf = ExecutionClassifier()
        r = clf.classify(
            action_type="local_analysis",
            tool_requirements=["git_push"],  # dangerous tool
        )
        assert r.tier == TIER_BLOCKED_DANGEROUS

    def test_safe_tool_requirements(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier, TIER_SAFE_LOCAL_DRY_RUN
        clf = ExecutionClassifier()
        r = clf.classify(
            action_type="local_analysis",
            tool_requirements=["read_file", "analyze_code"],  # safe tools
        )
        assert r.tier == TIER_SAFE_LOCAL_DRY_RUN

    def test_batch_classify(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier
        clf = ExecutionClassifier()
        candidates = [
            {"action_type": "local_analysis", "risk_level": "low"},
            {"action_type": "deploy", "risk_level": "high"},
            {"action_type": "file_write", "risk_level": "medium"},
        ]
        results = clf.classify_batch(candidates)
        assert len(results) == 3
        assert results[0].auto_allowed is True
        assert results[1].blocked is True
        assert results[2].needs_approval is True

    def test_classifier_status_agent_agnostic(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier
        clf = ExecutionClassifier()
        s = clf.get_status()
        assert s["metadata_driven"] is True
        assert s["agent_name_agnostic"] is True
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 6. Auto-commit candidate
# ---------------------------------------------------------------------------


class TestAutoCommitCandidate:
    def test_create_candidate_clean(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Update docs", ["docs/readme.md"])
        assert c.status not in ("blocked",), f"Blocked: {c.blocked_reason}"
        assert c.no_secret_files is True
        assert c.no_deploy_artifacts is True

    def test_candidate_blocked_for_secret_file(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Bad commit", [".env", "docs/readme.md"])
        assert c.status == "blocked"
        assert ".env" in c.blocked_reason or "Secret" in c.blocked_reason

    def test_candidate_blocked_for_dmg(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Bad commit", ["dist/app.dmg"])
        assert c.status == "blocked"

    def test_preconditions_pass(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Update docs", ["docs/readme.md"])
        pre = mgr.validate_preconditions(
            c.candidate_id,
            git_clean=True,
            diff_classified=True,
            validation_passed=True,
            rollback_plan_id="plan_001",
        )
        assert pre["ok"] is True

    def test_preconditions_fail_no_rollback(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Update docs", ["docs/readme.md"])
        pre = mgr.validate_preconditions(
            c.candidate_id,
            git_clean=True,
            diff_classified=True,
            validation_passed=True,
            rollback_plan_id=None,  # missing
        )
        assert pre["ok"] is False

    def test_preconditions_fail_git_dirty(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Update docs", ["docs/readme.md"])
        pre = mgr.validate_preconditions(
            c.candidate_id,
            git_clean=False,  # dirty
            diff_classified=True,
            validation_passed=True,
            rollback_plan_id="plan_001",
        )
        assert pre["ok"] is False

    def test_dry_run_ok(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Update docs", ["docs/readme.md"])
        mgr.validate_preconditions(c.candidate_id, True, True, True, "plan_001")
        dr = mgr.dry_run(c.candidate_id)
        assert dr["ok"] is True
        assert dr.get("dry_run") is True
        assert "no real git commit" in dr.get("note", "").lower() or "dry-run" in dr.get("note", "").lower()

    def test_kill_switch_blocks_preconditions(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=True)
        c = mgr.create_candidate("Update docs", ["docs/readme.md"])
        pre = mgr.validate_preconditions(c.candidate_id, True, True, True, "plan_001")
        assert pre["ok"] is False
        assert "kill_switch" in " ".join(pre.get("failures", [])).lower()


# ---------------------------------------------------------------------------
# 7. No auto-push / auto-merge / deploy
# ---------------------------------------------------------------------------


class TestNoAutoPushMergeDeploy:
    def test_no_auto_push(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager()
        s = mgr.get_status()
        assert s["no_auto_push"] is True

    def test_no_auto_merge(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager()
        assert mgr.get_status()["no_auto_merge"] is True

    def test_no_production_deploy(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager()
        assert mgr.get_status()["no_production_deploy"] is True

    @pytest.mark.parametrize("action", ["auto_push", "auto_merge", "deploy"])
    def test_production_gate_blocked(self, action):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        result = mgr.production_gate(action)
        assert result["ok"] is False
        assert result.get("blocked") is True
        assert result.get("requires_nus_1f") is True


# ---------------------------------------------------------------------------
# 8. Temp git repo commit (real commit, temp dir only)
# ---------------------------------------------------------------------------


class TestTempGitRepoCommit:
    def test_commit_in_temp_repo(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # Init temp git repo
            subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"],
                           cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"],
                           cwd=repo_path, check=True, capture_output=True)

            c = mgr.create_candidate("NUS 1E test commit", [])
            mgr.validate_preconditions(c.candidate_id, True, True, True, "plan_001")

            result = mgr.commit_to_temp_repo(c.candidate_id, repo_path)
            assert result["ok"] is True
            assert result.get("temp_repo") is True
            assert result.get("committed") is True
            assert "no push" in result.get("note", "").lower() or "no production" in result.get("note", "").lower()

    def test_commit_blocked_outside_tmp(self, tmp_path):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)
        c = mgr.create_candidate("Test", [])
        mgr.validate_preconditions(c.candidate_id, True, True, True, "plan_001")

        # Use workspace root — not a tmp dir
        result = mgr.commit_to_temp_repo(c.candidate_id, Path("/Users/user/OpenJarvis"))
        assert result["ok"] is False
        assert result.get("blocked") is True

    def test_commit_blocked_by_kill_switch(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            c = mgr.create_candidate("test", [])
            result = mgr.commit_to_temp_repo(c.candidate_id, repo)
            assert result["ok"] is False


# ---------------------------------------------------------------------------
# 9. Doctor check
# ---------------------------------------------------------------------------


class TestNUS1EDoctorCheck:
    def test_doctor_check_passes(self):
        from openjarvis.doctor.checks import check_nus1e_low_risk_execution, CheckStatus
        result = check_nus1e_low_risk_execution()
        assert result.check_id == "nus1e_low_risk_execution"
        assert result.status == CheckStatus.PASS, f"Doctor check failed: {result.summary}"

    def test_doctor_check_in_all_checks(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        names = [fn.__name__ for fn in _ALL_CHECK_FNS]
        assert "check_nus1e_low_risk_execution" in names


# ---------------------------------------------------------------------------
# 10. Capability status
# ---------------------------------------------------------------------------


class TestCapabilityStatus1E:
    def test_nus1d_capability_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        assert "nus1d_eval_rollback_gates" in caps
        assert caps["nus1d_eval_rollback_gates"].status == STATUS_READY

    def test_nus1e_capability_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        assert "nus1e_low_risk_execution_foundation" in caps
        assert caps["nus1e_low_risk_execution_foundation"].status == STATUS_READY

    def test_nus_status_summary(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        s = get_capabilities_summary()
        assert s["nus1d_status"] == "ready"
        assert s["nus1e_status"] == "ready"
        assert s["nus1f_status"] == "ready"


# ---------------------------------------------------------------------------
# 11. US13 parked
# ---------------------------------------------------------------------------


class TestUS13Parked1E:
    def test_classifier_us13_parked(self):
        from openjarvis.nus.execution_classifier import ExecutionClassifier
        s = ExecutionClassifier().get_status()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_low_risk_execution_us13_parked(self):
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        s = LowRiskExecutionManager().get_status()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
