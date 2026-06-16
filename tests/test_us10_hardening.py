"""US10 Daily-Driver Operations Hardening — scoped tests.

Covers all files touched in US10:
  - daemon/service.py          RuntimeLifecycleManager
  - autonomy/wakeword_bridge.py auto-restart fields + status
  - autonomy/connector_health.py degradation escalation
  - autonomy/job_queue.py      stalled job detection + health report
  - autonomy/alert_limiter.py  auto-escalation
  - doctor/checks.py           check_runtime_lifecycle
  - doctor/readiness.py        RUNTIME_LIFECYCLE category

Rules:
  - No real subprocesses started
  - No secrets used
  - No real external sends
  - Temp dirs / in-memory DBs used for isolation
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Task 1 — RuntimeLifecycleManager
# ---------------------------------------------------------------------------


class TestRuntimeLifecycleManager:
    def test_import(self):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        assert RuntimeLifecycleManager is not None

    def test_start_writes_pid_file(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        mgr = RuntimeLifecycleManager(pid_file=pid_file)
        result = mgr.start()
        assert pid_file.exists()
        assert int(pid_file.read_text().strip()) == os.getpid()
        mgr.stop()

    def test_stop_removes_pid_file(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        mgr = RuntimeLifecycleManager(pid_file=pid_file)
        mgr.start()
        assert pid_file.exists()
        mgr.stop()
        assert not pid_file.exists()

    def test_health_returns_dict(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        mgr = RuntimeLifecycleManager(pid_file=pid_file)
        mgr.start()
        h = mgr.health()
        assert isinstance(h, dict)
        assert "ok" in h
        assert "pid" in h
        assert "uptime_seconds" in h
        assert h["pid"] == os.getpid()
        mgr.stop()

    def test_health_pid_file_ok_true_after_start(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        mgr = RuntimeLifecycleManager(pid_file=pid_file)
        mgr.start()
        h = mgr.health()
        assert h["pid_file_ok"] is True
        mgr.stop()

    def test_on_shutdown_callback_fires(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        mgr = RuntimeLifecycleManager(pid_file=pid_file)
        fired = []
        mgr.on_shutdown(lambda: fired.append(True))
        mgr.start()
        mgr.stop()
        assert fired == [True]

    def test_stop_idempotent(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        mgr = RuntimeLifecycleManager(pid_file=pid_file)
        mgr.start()
        mgr.stop()
        mgr.stop()  # second call must not raise

    def test_read_pid_returns_none_when_no_file(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "nonexistent.pid"
        assert RuntimeLifecycleManager.read_pid(pid_file) is None

    def test_read_pid_returns_int(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        pid_file.write_text(str(os.getpid()))
        assert RuntimeLifecycleManager.read_pid(pid_file) == os.getpid()

    def test_is_running_current_process(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        pid_file.write_text(str(os.getpid()))
        assert RuntimeLifecycleManager.is_running(pid_file) is True

    def test_is_running_fake_pid(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("99999999")  # unlikely to be a real PID
        # May be True if PID exists by coincidence, just check no exception
        result = RuntimeLifecycleManager.is_running(pid_file)
        assert isinstance(result, bool)

    def test_probe_failure_reported(self, tmp_path):
        from openjarvis.daemon.service import RuntimeLifecycleManager
        pid_file = tmp_path / "test.pid"
        mgr = RuntimeLifecycleManager(
            pid_file=pid_file,
            probe_modules=["openjarvis.governance.constitution", "nonexistent_module_xyz"],
        )
        mgr.start()
        h = mgr.health()
        assert len(h["probe_failures"]) == 1
        assert "nonexistent_module_xyz" in h["probe_failures"][0]
        assert h["ok"] is False
        mgr.stop()


# ---------------------------------------------------------------------------
# Task 2 — WakeWordBridge auto-restart fields
# ---------------------------------------------------------------------------


class TestWakeWordBridgeRestartFields:
    def test_import(self):
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        assert WakeWordBridge is not None

    def test_new_bridge_has_restart_fields(self):
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        b = WakeWordBridge()
        s = b.status()
        assert "restart_count" in s
        assert "last_restart_at" in s
        assert "auto_restart" in s
        assert "max_restarts" in s

    def test_restart_count_zero_initially(self):
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        b = WakeWordBridge()
        s = b.status()
        assert s["restart_count"] == 0
        assert s["last_restart_at"] is None

    def test_auto_restart_false_initially(self):
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        b = WakeWordBridge()
        assert b.status()["auto_restart"] is False

    def test_start_unavailable_returns_error(self):
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        b = WakeWordBridge()
        # Worker venv not present in test env — should return ok=False
        with patch.object(b, "is_available", return_value=False):
            result = b.start()
        assert result["ok"] is False
        assert "error" in result

    def test_get_worker_status_importable(self):
        from openjarvis.autonomy.wakeword_bridge import get_worker_status
        s = get_worker_status()
        assert isinstance(s, dict)
        assert "worker_available" in s


# ---------------------------------------------------------------------------
# Task 3 — connector health degradation escalation
# ---------------------------------------------------------------------------


class TestConnectorHealthEscalation:
    def test_get_degraded_connectors_importable(self):
        from openjarvis.autonomy.connector_health import get_degraded_connectors
        result = get_degraded_connectors()
        assert isinstance(result, list)

    def test_get_connector_degradation_summary_importable(self):
        from openjarvis.autonomy.connector_health import get_connector_degradation_summary
        s = get_connector_degradation_summary()
        assert isinstance(s, dict)
        assert "escalation_threshold" in s
        assert s["escalation_threshold"] == 3

    def test_reset_connector_failures_returns_false_unknown(self):
        from openjarvis.autonomy.connector_health import reset_connector_failures
        result = reset_connector_failures("__nonexistent_connector__")
        assert result is False

    def test_escalation_threshold_in_summary(self):
        from openjarvis.autonomy.connector_health import get_connector_degradation_summary
        s = get_connector_degradation_summary()
        assert "escalation_threshold" in s
        assert isinstance(s["escalation_threshold"], int)

    def test_degraded_escalation_to_blocked(self, tmp_path):
        from openjarvis.autonomy.connector_health import (
            ConnectorHealthEntry,
            HealthStatus,
            _DEGRADED_ESCALATION_THRESHOLD,
            check_connector_health,
        )
        import json

        health_file = tmp_path / "connector_health.json"

        # Seed with consecutive_failures = threshold - 1 (one more → escalates)
        entry = ConnectorHealthEntry(
            connector="slack",
            status=HealthStatus.DEGRADED,
            last_checked=time.time() - 400,  # outside min_check_interval
            failure_reason="test failure",
            consecutive_failures=_DEGRADED_ESCALATION_THRESHOLD - 1,
        )
        health_file.write_text(json.dumps({"slack": entry.to_dict()}))

        # Mock the Slack checker to return DEGRADED regardless of env
        def _always_degraded():
            return HealthStatus.DEGRADED, "simulated degradation"

        import openjarvis.autonomy.connector_health as _ch_mod
        original_map = dict(_ch_mod._CHECKER_MAP)
        _ch_mod._CHECKER_MAP["slack"] = _always_degraded

        try:
            with patch("openjarvis.autonomy.connector_health._HEALTH_STORE", health_file):
                result = check_connector_health("slack", force=True)
        finally:
            _ch_mod._CHECKER_MAP["slack"] = original_map["slack"]

        # After one more DEGRADED failure, count hits threshold → escalates to BLOCKED
        assert result.consecutive_failures >= _DEGRADED_ESCALATION_THRESHOLD
        assert result.status == HealthStatus.BLOCKED

    def test_healthy_connector_not_escalated(self, tmp_path):
        from openjarvis.autonomy.connector_health import (
            ConnectorHealthEntry,
            HealthStatus,
            check_connector_health,
        )
        import json

        health_file = tmp_path / "connector_health.json"
        entry = ConnectorHealthEntry(
            connector="github",
            status=HealthStatus.HEALTHY,
            last_checked=time.time() - 400,
            consecutive_failures=0,
        )
        health_file.write_text(json.dumps({"github": entry.to_dict()}))

        with patch("openjarvis.autonomy.connector_health._HEALTH_STORE", health_file):
            result = check_connector_health("github", force=True)

        assert result.status != HealthStatus.BLOCKED


# ---------------------------------------------------------------------------
# Task 4 — job queue stalled detection + health report
# ---------------------------------------------------------------------------


class TestJobQueueUS10:
    def _db_path(self, tmp_path) -> Path:
        return tmp_path / "test_queue.db"

    def test_get_stalled_jobs_empty(self, tmp_path):
        from openjarvis.autonomy.job_queue import get_stalled_jobs
        db = self._db_path(tmp_path)
        result = get_stalled_jobs(db_path=db)
        assert result == []

    def test_get_stalled_jobs_detects_old_running(self, tmp_path):
        from openjarvis.autonomy.job_queue import (
            JobState,
            enqueue,
            get_stalled_jobs,
        )
        import sqlite3

        db = self._db_path(tmp_path)
        r = enqueue("test_action", db_path=db)
        job_id = r["job_id"]

        # Manually set state=running with started_at in the past
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        old_ts = time.time() - 400  # 400s ago > 300s threshold
        conn.execute(
            "UPDATE jobs SET state=?, started_at=? WHERE job_id=?",
            (JobState.RUNNING, old_ts, job_id),
        )
        conn.commit()
        conn.close()

        stalled = get_stalled_jobs(stale_after_seconds=300, db_path=db)
        assert len(stalled) == 1
        assert stalled[0].job_id == job_id

    def test_get_retry_stats_empty_db(self, tmp_path):
        from openjarvis.autonomy.job_queue import get_retry_stats
        db = self._db_path(tmp_path)
        s = get_retry_stats(db_path=db)
        assert s["jobs_with_retries"] == 0
        assert s["exhausted_retries"] == 0
        assert s["top_retry_jobs"] == []

    def test_get_queue_health_report_returns_dict(self, tmp_path):
        from openjarvis.autonomy.job_queue import get_queue_health_report
        db = self._db_path(tmp_path)
        r = get_queue_health_report(db_path=db)
        assert isinstance(r, dict)
        assert "stats" in r
        assert "stalled_jobs" in r
        assert "health" in r
        assert "retry_stats" in r

    def test_get_queue_health_report_ok_when_empty(self, tmp_path):
        from openjarvis.autonomy.job_queue import get_queue_health_report
        db = self._db_path(tmp_path)
        r = get_queue_health_report(db_path=db)
        assert r["health"] == "ok"
        assert r["stalled_jobs"] == 0
        assert r["recovery_action"] is None

    def test_get_queue_health_report_degraded_with_stalled(self, tmp_path):
        from openjarvis.autonomy.job_queue import (
            JobState,
            enqueue,
            get_queue_health_report,
        )
        import sqlite3

        db = self._db_path(tmp_path)
        r = enqueue("action_x", db_path=db)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "UPDATE jobs SET state=?, started_at=? WHERE job_id=?",
            (JobState.RUNNING, time.time() - 400, r["job_id"]),
        )
        conn.commit()
        conn.close()

        report = get_queue_health_report(db_path=db)
        assert report["health"] == "degraded"
        assert report["stalled_jobs"] == 1
        assert report["recovery_action"] is not None


# ---------------------------------------------------------------------------
# Task 5 — alert limiter escalation
# ---------------------------------------------------------------------------


class TestAlertLimiterUS10:
    def test_auto_escalate_importable(self):
        from openjarvis.autonomy.alert_limiter import auto_escalate_on_failures
        assert auto_escalate_on_failures is not None

    def test_get_escalation_status_importable(self):
        from openjarvis.autonomy.alert_limiter import get_escalation_status
        s = get_escalation_status()
        assert isinstance(s, dict)
        assert "incident_mode" in s
        assert "escalation_levels" in s

    def test_below_threshold_not_escalated(self, tmp_path):
        from openjarvis.autonomy.alert_limiter import auto_escalate_on_failures, load_alert_config

        cfg_file = tmp_path / "alert_config.json"
        with patch("openjarvis.autonomy.alert_limiter._ALERT_CONFIG", cfg_file):
            result = auto_escalate_on_failures(failure_count=3, escalate_threshold=5)

        assert result["escalated"] is False
        assert result["incident_mode"] is False

    def test_at_threshold_escalates(self, tmp_path):
        from openjarvis.autonomy.alert_limiter import auto_escalate_on_failures

        cfg_file = tmp_path / "alert_config.json"
        with patch("openjarvis.autonomy.alert_limiter._ALERT_CONFIG", cfg_file):
            result = auto_escalate_on_failures(failure_count=5, escalate_threshold=5, source="connector_slack")

        assert result["escalated"] is True
        assert result["incident_mode"] is True
        assert "connector_slack" in result["reason"]

    def test_already_in_incident_not_re_escalated(self, tmp_path):
        import json
        from openjarvis.autonomy.alert_limiter import auto_escalate_on_failures

        cfg_file = tmp_path / "alert_config.json"
        cfg_file.write_text(json.dumps({"incident_mode": True}))
        with patch("openjarvis.autonomy.alert_limiter._ALERT_CONFIG", cfg_file):
            result = auto_escalate_on_failures(failure_count=99, escalate_threshold=5)

        assert result["escalated"] is False
        assert result["incident_mode"] is True

    def test_escalation_status_structure(self, tmp_path):
        from openjarvis.autonomy.alert_limiter import get_escalation_status

        cfg_file = tmp_path / "alert_config.json"
        with patch("openjarvis.autonomy.alert_limiter._ALERT_CONFIG", cfg_file):
            s = get_escalation_status()

        assert isinstance(s["escalation_levels"], list)
        assert "incident_mode" in s
        assert "freeze_mode" in s
        assert "channels_with_limits" in s


# ---------------------------------------------------------------------------
# Task 6 — check_runtime_lifecycle
# ---------------------------------------------------------------------------


class TestCheckRuntimeLifecycle:
    def test_import(self):
        from openjarvis.doctor.checks import check_runtime_lifecycle
        assert check_runtime_lifecycle is not None

    def test_returns_check_result(self):
        from openjarvis.doctor.checks import CheckResult, check_runtime_lifecycle
        result = check_runtime_lifecycle()
        assert isinstance(result, CheckResult)

    def test_check_id_correct(self):
        from openjarvis.doctor.checks import check_runtime_lifecycle
        result = check_runtime_lifecycle()
        assert result.check_id == "runtime_lifecycle"

    def test_valid_status(self):
        from openjarvis.doctor.checks import CheckStatus, check_runtime_lifecycle
        result = check_runtime_lifecycle()
        assert result.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.NOT_CONFIGURED)

    def test_passes_in_normal_env(self):
        from openjarvis.doctor.checks import CheckStatus, check_runtime_lifecycle
        result = check_runtime_lifecycle()
        assert result.status == CheckStatus.PASS, f"Expected PASS, got {result.status}: {result.summary}"

    def test_evidence_populated(self):
        from openjarvis.doctor.checks import check_runtime_lifecycle
        result = check_runtime_lifecycle()
        assert "runtime_lifecycle_manager" in result.evidence
        assert "queue_crash_recovery" in result.evidence
        assert "wakeword_bridge" in result.evidence

    def test_in_run_all_checks(self):
        from openjarvis.doctor.checks import run_all_checks
        results = run_all_checks()
        ids = {r.check_id for r in results}
        assert "runtime_lifecycle" in ids

    def test_run_all_checks_returns_32(self):
        from openjarvis.doctor.checks import run_all_checks
        results = run_all_checks()
        assert len(results) == 32, f"Expected 32 checks, got {len(results)}"


# ---------------------------------------------------------------------------
# Task 7 — RUNTIME_LIFECYCLE readiness category
# ---------------------------------------------------------------------------


class TestRuntimeLifecycleReadinessCategory:
    def test_category_exists(self):
        from openjarvis.doctor.readiness import ReadinessCategory
        assert ReadinessCategory.RUNTIME_LIFECYCLE == "runtime_lifecycle"

    def test_category_in_check_map(self):
        from openjarvis.doctor.readiness import ReadinessCategory, _CATEGORY_CHECKS
        assert ReadinessCategory.RUNTIME_LIFECYCLE in _CATEGORY_CHECKS
        assert "runtime_lifecycle" in _CATEGORY_CHECKS[ReadinessCategory.RUNTIME_LIFECYCLE]

    def test_category_is_required(self):
        from openjarvis.doctor.readiness import ReadinessCategory, _REQUIRED_CATEGORIES
        assert ReadinessCategory.RUNTIME_LIFECYCLE in _REQUIRED_CATEGORIES

    def test_evaluate_readiness_includes_runtime_lifecycle(self):
        from openjarvis.doctor.readiness import ReadinessCategory, evaluate_readiness
        report = evaluate_readiness()
        cat_names = [c.category for c in report.categories]
        assert ReadinessCategory.RUNTIME_LIFECYCLE in cat_names

    def test_us10_checkpoint_in_accepted(self):
        from openjarvis.doctor.readiness import _ACCEPTED_CHECKPOINTS
        assert any("US10" in cp or "Sprint 10" in cp for cp in _ACCEPTED_CHECKPOINTS)

    def test_runtime_lifecycle_category_not_fail(self):
        from openjarvis.doctor.checks import CheckStatus
        from openjarvis.doctor.readiness import ReadinessCategory, evaluate_readiness
        report = evaluate_readiness()
        cat_map = {c.category: c for c in report.categories}
        rt = cat_map.get(ReadinessCategory.RUNTIME_LIFECYCLE)
        assert rt is not None
        assert rt.status != CheckStatus.FAIL, (
            f"RUNTIME_LIFECYCLE should not fail: {rt.summary}"
        )
