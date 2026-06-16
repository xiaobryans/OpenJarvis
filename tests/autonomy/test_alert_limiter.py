"""Tests for Alert Noise / Rate Limiter (US9 Phase 9)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from openjarvis.autonomy.alert_limiter import (
    AlertDecision,
    AlertLevel,
    check_alert,
    get_alert_limiter_status,
    load_alert_config,
    make_dedup_key,
    save_alert_config,
    set_freeze_mode,
    set_incident_mode,
)


_NO_QUIET_HOURS_CONFIG = {
    "channels": {
        "slack": {
            "max_per_hour": 10,
            "max_per_minute": 2,
            "cooldown_seconds": 60,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "quiet_hours_tz": "local",
        },
        "telegram": {
            "max_per_hour": 10,
            "max_per_minute": 2,
            "cooldown_seconds": 60,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "quiet_hours_tz": "local",
        },
    },
    "incident_mode": False,
    "freeze_mode": False,
    "escalation_levels": ["info", "warn", "critical", "incident"],
    "min_level_in_quiet_hours": "critical",
    "dedup_window_seconds": 300,
}


@pytest.fixture(autouse=True)
def clean_config(tmp_path, monkeypatch):
    cfg_file = tmp_path / "alert_config.json"
    log_file = tmp_path / "alert_log.jsonl"
    # Write config with quiet hours disabled so tests pass at any time of day
    cfg_file.write_text(json.dumps(_NO_QUIET_HOURS_CONFIG), encoding="utf-8")
    monkeypatch.setattr("openjarvis.autonomy.alert_limiter._ALERT_CONFIG", cfg_file)
    monkeypatch.setattr("openjarvis.autonomy.alert_limiter._ALERT_LOG", log_file)
    monkeypatch.setattr("openjarvis.autonomy.alert_limiter._CONFIG_DIR", tmp_path)
    yield


class TestDedupKey:
    def test_same_inputs_same_key(self):
        k1 = make_dedup_key("slack", "warn", "Server down")
        k2 = make_dedup_key("slack", "warn", "Server down")
        assert k1 == k2

    def test_different_message_different_key(self):
        k1 = make_dedup_key("slack", "warn", "Server down")
        k2 = make_dedup_key("slack", "warn", "Server up")
        assert k1 != k2


class TestFreezeMode:
    def test_freeze_blocks_all_alerts(self):
        set_freeze_mode(True)
        r = check_alert("slack", AlertLevel.CRITICAL, "critical alert")
        assert r.allowed is False
        assert r.suppressed_by == "freeze"
        set_freeze_mode(False)

    def test_unfreeze_allows_alerts(self):
        set_freeze_mode(False)
        r = check_alert("slack", AlertLevel.INFO, "test message")
        assert r.suppressed_by != "freeze"


class TestIncidentMode:
    def test_incident_mode_blocks_info(self):
        set_incident_mode(True)
        r = check_alert("slack", AlertLevel.INFO, "info alert")
        assert r.allowed is False
        assert r.suppressed_by == "incident_mode"
        set_incident_mode(False)

    def test_incident_mode_allows_critical(self):
        set_incident_mode(True)
        r = check_alert("slack", AlertLevel.CRITICAL, "critical!")
        assert r.suppressed_by != "incident_mode"
        set_incident_mode(False)


class TestDeduplication:
    def test_duplicate_suppressed_within_window(self):
        r1 = check_alert("slack", AlertLevel.WARN, "same message", record=True)
        assert r1.allowed is True
        r2 = check_alert("slack", AlertLevel.WARN, "same message")
        assert r2.allowed is False
        assert r2.suppressed_by == "dedup"

    def test_different_messages_both_allowed(self):
        r1 = check_alert("slack", AlertLevel.WARN, "message A", record=True)
        r2 = check_alert("slack", AlertLevel.WARN, "message B", record=True)
        assert r1.allowed is True
        assert r2.allowed is True


class TestRateLimiting:
    def test_within_rate_limit_allowed(self):
        r = check_alert("slack", AlertLevel.INFO, "unique msg 1", record=True)
        assert r.allowed is True

    def test_rate_limit_exceeded(self):
        cfg = load_alert_config()
        cfg["channels"]["slack"]["max_per_minute"] = 1
        save_alert_config(cfg)
        check_alert("slack", AlertLevel.INFO, "rate msg first", record=True)
        r2 = check_alert("slack", AlertLevel.INFO, "rate msg second", record=True)
        assert r2.allowed is False
        assert r2.suppressed_by == "rate_limit"


class TestAlertLimiterStatus:
    def test_status_active(self):
        s = get_alert_limiter_status()
        assert s["active"] is True
        assert "channels_configured" in s
        assert s["quiet_hours_enabled"] is True

    def test_status_reflects_freeze(self):
        set_freeze_mode(True)
        s = get_alert_limiter_status()
        assert s["freeze_mode"] is True
        set_freeze_mode(False)


class TestAlertDecision:
    def test_decision_has_required_fields(self):
        r = check_alert("telegram", AlertLevel.WARN, "test decision")
        assert isinstance(r, AlertDecision)
        assert isinstance(r.allowed, bool)
        assert r.channel == "telegram"
        assert r.level == AlertLevel.WARN
        assert r.dedup_key
