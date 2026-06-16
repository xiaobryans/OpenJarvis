"""Tests for Connector Health Monitor (US9 Phase 8)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openjarvis.autonomy.connector_health import (
    ConnectorHealthEntry,
    HealthStatus,
    check_all_connectors,
    check_connector_health,
    clear_health_cache,
    get_connector_health_report,
)


@pytest.fixture(autouse=True)
def tmp_health_store(tmp_path, monkeypatch):
    store = tmp_path / "connector_health.json"
    monkeypatch.setattr(
        "openjarvis.autonomy.connector_health._HEALTH_STORE", store
    )
    yield store
    if store.exists():
        store.unlink()


class TestCheckConnectorHealth:
    def test_returns_health_entry(self):
        entry = check_connector_health("tavily", force=True)
        assert isinstance(entry, ConnectorHealthEntry)
        assert entry.connector == "tavily"
        assert entry.status in (
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.NOT_CONFIGURED,
            HealthStatus.UNKNOWN,
        )

    def test_slack_check_returns_valid_status(self):
        entry = check_connector_health("slack", force=True)
        assert entry.status in (
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.NOT_CONFIGURED,
        )

    def test_telegram_check_does_not_leak_tokens(self):
        import os
        entry = check_connector_health("telegram", force=True)
        result_str = str(entry)
        token = os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "")
        if token and len(token) > 4:
            assert token not in result_str

    def test_unknown_connector_returns_unknown(self):
        entry = check_connector_health("nonexistent_connector_xyz", force=True)
        assert entry.status == HealthStatus.UNKNOWN

    def test_github_check_works(self):
        entry = check_connector_health("github", force=True)
        assert entry.status in (
            HealthStatus.HEALTHY,
            HealthStatus.NOT_CONFIGURED,
        )


class TestCheckAllConnectors:
    def test_returns_dict_of_entries(self):
        results = check_all_connectors(force=True)
        assert isinstance(results, dict)
        assert len(results) > 0
        for name, entry in results.items():
            assert isinstance(entry, ConnectorHealthEntry)

    def test_known_connectors_present(self):
        results = check_all_connectors(force=True)
        for expected in ("slack", "telegram", "tavily", "github", "openclaw", "omnix"):
            assert expected in results


class TestHealthReport:
    def test_report_has_required_fields(self):
        check_all_connectors(force=True)
        report = get_connector_health_report()
        assert "connectors" in report
        assert "total" in report
        assert "unhealthy_count" in report
        assert "unhealthy" in report

    def test_unhealthy_count_is_int(self):
        check_all_connectors(force=True)
        report = get_connector_health_report()
        assert isinstance(report["unhealthy_count"], int)
        assert report["unhealthy_count"] >= 0

    def test_failure_reason_no_tokens(self):
        import os
        check_all_connectors(force=True)
        report = get_connector_health_report()
        report_str = str(report)
        for key in ("JARVIS_SLACK_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN", "TAVILY_API_KEY"):
            val = os.environ.get(key, "")
            if val and len(val) > 4:
                assert val not in report_str, f"Token {key} leaked in health report"


class TestCacheRespect:
    def test_cached_result_returned_within_interval(self):
        entry1 = check_connector_health("tavily", force=True)
        # Second call without force — should return cached
        entry2 = check_connector_health("tavily", force=False)
        assert entry2.last_checked == entry1.last_checked
