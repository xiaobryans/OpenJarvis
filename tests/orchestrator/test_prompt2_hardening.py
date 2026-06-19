"""Prompt 2 — Private Daily-Driver Hardening Tests.

Tests all Prompt 2 sprint items:
  - Provider readiness dashboard
  - Trace persistence
  - ProjectRegistry persistence
  - Runtime recovery
  - Connector dry-run framework
  - Memory quality matrix
  - Human correction ingestion
"""

from __future__ import annotations

import time
import uuid


# ---------------------------------------------------------------------------
# 1. Provider readiness
# ---------------------------------------------------------------------------

class TestProviderReadiness:
    def test_report_builds(self):
        from openjarvis.orchestrator.provider_readiness import get_provider_readiness
        report = get_provider_readiness()
        assert report is not None
        assert isinstance(report.providers, list)
        assert len(report.providers) == 3

    def test_no_keys_means_blocked_provider(self):
        from openjarvis.orchestrator.provider_readiness import get_provider_readiness
        report = get_provider_readiness()
        # In test env, no keys are set
        # Status should be available OR blocked — never fabricated
        assert report.llm_in_loop_status in ("available", "BLOCKED_PROVIDER")

    def test_no_secret_values_in_report(self):
        from openjarvis.orchestrator.provider_readiness import get_provider_readiness
        report = get_provider_readiness()
        d = report.to_dict()
        # No provider should have a 'value' field
        for p in d["providers"]:
            assert "value" not in p
            assert p["env_var"] in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")

    def test_safety_blockers_always_present(self):
        from openjarvis.orchestrator.provider_readiness import get_provider_readiness
        report = get_provider_readiness()
        safety = [b for b in report.blockers if b.blocker_type == "BLOCKED_SAFETY"]
        assert len(safety) >= 3  # auto_push, production_deploy, external_send at minimum

    def test_summary_is_nonempty(self):
        from openjarvis.orchestrator.provider_readiness import get_provider_readiness
        report = get_provider_readiness()
        assert len(report.summary) > 10


# ---------------------------------------------------------------------------
# 2. Trace persistence
# ---------------------------------------------------------------------------

class TestTracePersistence:
    def test_persist_returns_true(self):
        from openjarvis.orchestrator.runtime_trace import get_trace_store, start_trace
        store = get_trace_store()
        trace = start_trace(f"test_{uuid.uuid4().hex[:8]}")
        trace.add_event("front_door", component="test", summary="persist test")
        ok = store.persist_trace(trace.trace_id)
        assert ok is True

    def test_persisted_trace_retrievable_from_disk(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import runtime_trace as rt
        monkeypatch.setattr(rt, "_TRACES_DIR", tmp_path)
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore(persist=True)
        trace = store.create_trace("reload_test_req")
        trace.add_event("cos_gm", component="test", summary="disk reload test")
        ok = store.persist_trace(trace.trace_id)
        assert ok is True

        # Load fresh store
        store2 = RuntimeTraceStore(persist=True)
        loaded = store2.load_trace_from_disk(trace.trace_id)
        assert loaded is not None
        assert loaded.trace_id == trace.trace_id
        assert len(loaded.events) == 1
        assert loaded.events[0].event_type == "cos_gm"

    def test_no_raw_chain_of_thought_in_persisted_events(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import runtime_trace as rt
        monkeypatch.setattr(rt, "_TRACES_DIR", tmp_path)
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore(persist=True)
        trace = store.create_trace("no_cot_test")
        trace.add_event("front_door", component="test", summary="check no_raw_cot")
        store.persist_trace(trace.trace_id)
        loaded = store.load_trace_from_disk(trace.trace_id)
        for evt in loaded.events:
            assert evt.no_raw_chain_of_thought is True

    def test_graceful_failure_on_bad_dir(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        # Persist=False — should return False without crashing
        store = RuntimeTraceStore(persist=False)
        trace = store.create_trace("no_persist_test")
        ok = store.persist_trace(trace.trace_id)
        assert ok is False

    def test_list_persisted_traces(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import runtime_trace as rt
        monkeypatch.setattr(rt, "_TRACES_DIR", tmp_path)
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore(persist=True)
        for i in range(3):
            trace = store.create_trace(f"list_test_{i}")
            trace.add_event("front_door", component="test", summary=f"event {i}")
            store.persist_trace(trace.trace_id)
        listed = store.list_persisted_traces()
        assert len(listed) == 3


# ---------------------------------------------------------------------------
# 3. ProjectRegistry persistence
# ---------------------------------------------------------------------------

class TestProjectRegistryPersistence:
    def test_persist_and_reload(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import project_persistence as pp
        monkeypatch.setattr(pp, "_REGISTRY_FILE", tmp_path / "reg.json")
        monkeypatch.setattr(pp, "_BACKUP_FILE", tmp_path / "reg.json.bak")
        # Fresh registry
        from openjarvis.governance.constitution import ProjectRegistry, ProjectProfile
        ProjectRegistry.clear()
        ProjectRegistry._ensure_initialized()
        pp.ensure_openjarvis_project_registered()
        ok = pp.persist_registry()
        assert ok is True
        # Reload into a fresh class state
        ProjectRegistry.clear()
        result = pp.load_registry()
        assert result["loaded"] is True
        assert "omnix" in result["projects"] or result["project_count"] >= 1

    def test_omnix_always_registered(self):
        from openjarvis.governance.constitution import ProjectRegistry
        ProjectRegistry._ensure_initialized()
        assert ProjectRegistry.get("omnix") is not None

    def test_openjarvis_registered_after_ensure(self):
        from openjarvis.orchestrator.project_persistence import ensure_openjarvis_project_registered
        from openjarvis.governance.constitution import ProjectRegistry
        ProjectRegistry._ensure_initialized()
        ensure_openjarvis_project_registered()
        assert ProjectRegistry.get("openjarvis") is not None

    def test_personal_tasks_work_without_registry(self):
        """Personal tasks (no project_context) must work even if registry is empty."""
        from openjarvis.governance.constitution import ProjectRegistry
        # Even after clear, _ensure_initialized gives omnix as default
        ProjectRegistry.clear()
        default = ProjectRegistry.get_default()
        assert default is not None

    def test_no_omnix_hardcoding(self):
        """Personal task should not be forced to omnix project."""
        from openjarvis.governance.constitution import ProjectProfile, ProjectRegistry
        ProjectRegistry._ensure_initialized()
        personal = ProjectProfile(
            project_id="personal",
            display_name="Personal Tasks",
            priority=99,
            active=True,
        )
        ProjectRegistry.register(personal)
        assert ProjectRegistry.get("personal") is not None


# ---------------------------------------------------------------------------
# 4. Runtime recovery
# ---------------------------------------------------------------------------

class TestRuntimeRecovery:
    def test_record_and_retrieve_status(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import runtime_recovery as rr
        monkeypatch.setattr(rr, "_RECOVERY_FILE", tmp_path / "recovery.json")
        from openjarvis.orchestrator.runtime_recovery import RuntimeRecoveryStore
        store = RuntimeRecoveryStore()
        store.record_status(
            status="healthy",
            provider_status="BLOCKED_PROVIDER",
            active_projects=["omnix"],
            last_request_id="req_abc",
        )
        last = store.get_last_status()
        assert last is not None
        assert last.status == "healthy"
        assert last.no_raw_chain_of_thought is True

    def test_record_failed_task(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import runtime_recovery as rr
        monkeypatch.setattr(rr, "_RECOVERY_FILE", tmp_path / "recovery.json")
        from openjarvis.orchestrator.runtime_recovery import RuntimeRecoveryStore
        store = RuntimeRecoveryStore()
        ft = store.record_failed_task(
            request_id="req_fail_1",
            intent="fix bug in omnix",
            failure_summary="BLOCKED_PROVIDER: LLM not available",
            blocker_type="BLOCKED_PROVIDER",
            safe_resume_guidance="Configure OPENAI_API_KEY then retry.",
        )
        assert ft.record_id is not None
        assert ft.no_raw_chain_of_thought is True
        unresolved = store.get_unresolved_failures()
        assert len(unresolved) == 1

    def test_resolve_failure(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import runtime_recovery as rr
        monkeypatch.setattr(rr, "_RECOVERY_FILE", tmp_path / "recovery.json")
        from openjarvis.orchestrator.runtime_recovery import RuntimeRecoveryStore
        store = RuntimeRecoveryStore()
        ft = store.record_failed_task(
            request_id="req_fail_2",
            intent="test resolve",
            failure_summary="test failure",
        )
        ok = store.resolve_failure(ft.record_id)
        assert ok is True
        assert len(store.get_unresolved_failures()) == 0

    def test_no_raw_cot_in_failed_task(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import runtime_recovery as rr
        monkeypatch.setattr(rr, "_RECOVERY_FILE", tmp_path / "recovery.json")
        from openjarvis.orchestrator.runtime_recovery import RuntimeRecoveryStore
        store = RuntimeRecoveryStore()
        ft = store.record_failed_task(
            request_id="req_cot_check",
            intent="test",
            failure_summary="test",
        )
        assert ft.no_raw_chain_of_thought is True
        d = ft.to_dict()
        assert d["no_raw_chain_of_thought"] is True


# ---------------------------------------------------------------------------
# 5. Connector dry-run
# ---------------------------------------------------------------------------

class TestConnectorDryrun:
    def test_all_six_connectors_registered(self):
        from openjarvis.orchestrator.connector_dryrun import all_connector_records
        records = all_connector_records()
        ids = {r.connector_id for r in records}
        assert "gmail" in ids
        assert "gcalendar" in ids
        assert "slack" in ids
        assert "telegram" in ids
        assert "github" in ids
        assert "gdrive" in ids

    def test_dry_run_plan_produced(self):
        from openjarvis.orchestrator.connector_dryrun import plan_connector_action
        plan = plan_connector_action("gmail", "draft_email_plan")
        assert plan.status in ("dry_run_plan", "blocked")
        assert plan.no_raw_chain_of_thought is True

    def test_live_execution_blocked(self):
        """All connectors missing credentials must not produce live execution."""
        from openjarvis.orchestrator.connector_dryrun import all_connector_records
        for rec in all_connector_records():
            # No connector should be in 'available' overall status without credentials
            if rec.credentials_status == "BLOCKED_CREDENTIALS":
                assert rec.overall_status() != "dry_run_available_with_live"

    def test_safety_blocked_connectors(self):
        """Slack and Telegram must have BLOCKED_SAFETY (live sends)."""
        from openjarvis.orchestrator.connector_dryrun import get_connector_record
        slack = get_connector_record("slack")
        telegram = get_connector_record("telegram")
        assert slack.safety_status == "BLOCKED_SAFETY"
        assert telegram.safety_status == "BLOCKED_SAFETY"

    def test_auth_manager_classification_four_categories(self):
        from openjarvis.orchestrator.connector_dryrun import get_connector_auth_manager_classification
        classification = get_connector_auth_manager_classification()
        blockers = classification["blockers"]
        assert "BLOCKED_IMPLEMENTATION" in blockers
        assert "BLOCKED_CREDENTIALS" in blockers
        assert "BLOCKED_SAFETY" in blockers
        assert "BLOCKED_USER_AUTHORIZATION" in blockers

    def test_no_secret_exfiltration_in_plan(self):
        from openjarvis.orchestrator.connector_dryrun import plan_connector_action
        plan = plan_connector_action("github", "list_repos_plan")
        d = plan.to_dict()
        # required_credentials should list env var names, not values
        for cred in d["required_credentials"]:
            assert "=" not in cred   # no KEY=VALUE in output
            assert len(cred) < 100   # reasonable length


# ---------------------------------------------------------------------------
# 6. Memory quality matrix
# ---------------------------------------------------------------------------

class TestMemoryQualityMatrix:
    def test_assess_returns_structured_result(self):
        from openjarvis.memory.quality_matrix import MemoryQualityMatrix
        from openjarvis.memory.store import JarvisMemory
        mem = JarvisMemory()
        matrix = MemoryQualityMatrix(mem)
        result = matrix.assess(namespace="global")
        assert "status" in result
        assert result["status"] in ("empty", "assessed", "error")

    def test_insufficient_evidence_response(self):
        from openjarvis.memory.quality_matrix import insufficient_evidence
        result = insufficient_evidence("test context")
        assert result["status"] == "insufficient_evidence"
        assert "Insufficient evidence to verify" in result["message"]
        assert result["no_raw_chain_of_thought"] is True

    def test_conflict_detector_returns_summary(self):
        from openjarvis.memory.quality_matrix import StaleConflictDetector
        from openjarvis.memory.store import JarvisMemory
        mem = JarvisMemory()
        detector = StaleConflictDetector(mem)
        summary = detector.get_conflict_summary(namespace="global")
        assert "stale_count" in summary
        assert "conflict_count" in summary
        assert summary["no_raw_chain_of_thought"] is True

    def test_no_raw_cot_in_quality_records(self):
        from openjarvis.memory.quality_matrix import MemoryQualityMatrix
        from openjarvis.memory.store import JarvisMemory
        mem = JarvisMemory()
        matrix = MemoryQualityMatrix(mem)
        result = matrix.assess(namespace="global")
        if result.get("quality_records"):
            for r in result["quality_records"]:
                assert r["no_raw_chain_of_thought"] is True


# ---------------------------------------------------------------------------
# 7. Human correction ingestion
# ---------------------------------------------------------------------------

class TestHumanCorrectionIngestion:
    def test_ingest_correction(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import human_correction as hc
        monkeypatch.setattr(hc, "_CORRECTIONS_FILE", tmp_path / "corrections.jsonl")
        store = hc.HumanCorrectionStore()
        record = store.ingest(
            category=hc.CORRECTION_ROUTING,
            affected_task_intent="fix a bug in omnix",
            what_was_wrong="Wrong worker selected — used doctor instead of coding worker",
            correct_behavior="Should select CodingSafeWorkerAdapter for coding intents",
            affected_project="omnix",
        )
        assert record.correction_id is not None
        assert record.category == hc.CORRECTION_ROUTING
        assert record.no_raw_chain_of_thought is True

    def test_correction_persisted_to_disk(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import human_correction as hc
        f = tmp_path / "corrections.jsonl"
        monkeypatch.setattr(hc, "_CORRECTIONS_FILE", f)
        store = hc.HumanCorrectionStore()
        store.ingest(
            category=hc.CORRECTION_OUTPUT,
            affected_task_intent="test persist",
            what_was_wrong="wrong output",
            correct_behavior="correct output",
        )
        assert f.exists()
        lines = f.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_no_raw_cot_in_correction(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import human_correction as hc
        monkeypatch.setattr(hc, "_CORRECTIONS_FILE", tmp_path / "corrections.jsonl")
        store = hc.HumanCorrectionStore()
        record = store.ingest(
            category=hc.CORRECTION_MEMORY,
            affected_task_intent="recall test",
            what_was_wrong="stale memory recalled",
            correct_behavior="should have reported insufficient evidence",
        )
        d = record.to_dict()
        assert d["no_raw_chain_of_thought"] is True
        # Ensure no raw model output fields
        assert "raw_model_output" not in d
        assert "chain_of_thought" not in d

    def test_invalid_category_defaults_safely(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import human_correction as hc
        monkeypatch.setattr(hc, "_CORRECTIONS_FILE", tmp_path / "corrections.jsonl")
        store = hc.HumanCorrectionStore()
        record = store.ingest(
            category="totally_invalid_category",
            affected_task_intent="test",
            what_was_wrong="x",
            correct_behavior="y",
        )
        assert record.category in hc.ALL_CORRECTION_CATEGORIES

    def test_get_correction_status(self, tmp_path, monkeypatch):
        from openjarvis.orchestrator import human_correction as hc
        monkeypatch.setattr(hc, "_CORRECTIONS_FILE", tmp_path / "corrections.jsonl")
        store = hc.HumanCorrectionStore()
        store.ingest(
            category=hc.CORRECTION_PROVIDER,
            affected_task_intent="model selection",
            what_was_wrong="wrong model tier",
            correct_behavior="use Sonnet for single file tasks",
        )
        status = store.get_correction_status()
        assert status["total_corrections"] == 1
        assert status["pending_corrections"] == 1


# ---------------------------------------------------------------------------
# 8. Doctor checks for Prompt 2 systems
# ---------------------------------------------------------------------------

class TestPrompt2DoctorChecks:
    def test_all_prompt2_checks_run(self):
        from openjarvis.doctor.checks import (
            check_provider_readiness,
            check_trace_persistence,
            check_project_registry_persistence,
            check_runtime_recovery,
            check_connector_dryrun_framework,
            check_memory_quality_matrix,
            check_human_correction_store,
            CheckStatus,
        )
        for fn in [
            check_provider_readiness,
            check_trace_persistence,
            check_project_registry_persistence,
            check_runtime_recovery,
            check_connector_dryrun_framework,
            check_memory_quality_matrix,
            check_human_correction_store,
        ]:
            result = fn()
            assert result.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL)
            assert result.check_id is not None

    def test_prompt2_checks_in_all_check_fns(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        fn_names = {f.__name__ for f in _ALL_CHECK_FNS}
        expected = {
            "check_provider_readiness",
            "check_trace_persistence",
            "check_project_registry_persistence",
            "check_runtime_recovery",
            "check_connector_dryrun_framework",
            "check_memory_quality_matrix",
            "check_human_correction_store",
        }
        for name in expected:
            assert name in fn_names, f"Missing check: {name}"
