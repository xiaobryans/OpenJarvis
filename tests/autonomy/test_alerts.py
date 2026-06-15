"""Tests for AlertStore — SQLite-backed, project-scoped alert records.

Covers:
  - AlertRecord creation with required fields
  - list() with project_id and status filters
  - acknowledge() transitions status
  - resolve() transitions status
  - draft_slack_update() always send_status=not_sent, approval_required=True
  - draft_telegram_update() always send_status=not_sent, approval_required=True
  - daily_digest() returns correct counts
  - AlertRecord.to_dict() has all required keys
  - Project isolation: project A alerts not returned for project B
  - get() returns correct record by alert_id
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openjarvis.autonomy.alerts import AlertRecord, AlertSeverity, AlertStatus, AlertStore


@pytest.fixture
def store(tmp_path):
    """Fresh AlertStore backed by a temp DB for each test."""
    db = tmp_path / "test_alerts.db"
    return AlertStore(db_path=db)


class TestAlertCreate:
    def test_create_returns_record(self, store):
        r = store.create("omnix", "Test Alert", "Evidence here")
        assert isinstance(r, AlertRecord)
        assert r.title == "Test Alert"
        assert r.evidence == "Evidence here"
        assert r.project_id == "omnix"
        assert r.status == AlertStatus.OPEN
        assert r.severity == AlertSeverity.INFO

    def test_create_with_all_fields(self, store):
        r = store.create(
            "omnix", "Critical Issue", "Disk full",
            severity=AlertSeverity.CRITICAL,
            recommendation="Free disk space",
            source_watchdog_id="backend_health_watchdog",
        )
        assert r.severity == AlertSeverity.CRITICAL
        assert r.recommendation == "Free disk space"
        assert r.source_watchdog_id == "backend_health_watchdog"

    def test_create_assigns_alert_id(self, store):
        r = store.create("omnix", "Alert", "Evidence")
        assert len(r.alert_id) > 0

    def test_create_sets_timestamps(self, store):
        r = store.create("omnix", "Alert", "Evidence")
        assert r.created_at > 0
        assert r.updated_at > 0
        assert r.acknowledged_at is None
        assert r.resolved_at is None


class TestAlertList:
    def test_list_by_project(self, store):
        store.create("omnix", "A1", "e1")
        store.create("omnix", "A2", "e2")
        store.create("other", "B1", "e3")
        results = store.list(project_id="omnix")
        assert len(results) == 2
        for r in results:
            assert r.project_id == "omnix"

    def test_list_by_status(self, store):
        a1 = store.create("omnix", "Open", "evidence")
        a2 = store.create("omnix", "ToAck", "evidence")
        store.acknowledge(a2.alert_id)
        open_results = store.list(project_id="omnix", status=AlertStatus.OPEN)
        ack_results = store.list(project_id="omnix", status=AlertStatus.ACKNOWLEDGED)
        assert len(open_results) == 1
        assert open_results[0].alert_id == a1.alert_id
        assert len(ack_results) == 1
        assert ack_results[0].alert_id == a2.alert_id

    def test_list_all_statuses(self, store):
        store.create("omnix", "A1", "e1")
        store.create("omnix", "A2", "e2")
        results = store.list(project_id="omnix")
        assert len(results) == 2

    def test_list_empty_project(self, store):
        results = store.list(project_id="no_such_project")
        assert results == []

    def test_project_isolation(self, store):
        store.create("omnix", "Omnix Alert", "evidence")
        store.create("other_project", "Other Alert", "evidence")
        omnix_results = store.list(project_id="omnix")
        other_results = store.list(project_id="other_project")
        assert len(omnix_results) == 1
        assert len(other_results) == 1
        assert omnix_results[0].title == "Omnix Alert"
        assert other_results[0].title == "Other Alert"


class TestAlertGet:
    def test_get_by_id(self, store):
        r = store.create("omnix", "Test", "evidence")
        fetched = store.get(r.alert_id)
        assert fetched is not None
        assert fetched.alert_id == r.alert_id
        assert fetched.title == "Test"

    def test_get_nonexistent_returns_none(self, store):
        assert store.get("nonexistent_id") is None


class TestAlertAcknowledge:
    def test_acknowledge_changes_status(self, store):
        r = store.create("omnix", "Alert", "Evidence")
        acked = store.acknowledge(r.alert_id)
        assert acked is not None
        assert acked.status == AlertStatus.ACKNOWLEDGED
        assert acked.acknowledged_at is not None

    def test_acknowledge_nonexistent_returns_none(self, store):
        result = store.acknowledge("nonexistent_id")
        assert result is None

    def test_acknowledged_not_resolved(self, store):
        r = store.create("omnix", "Alert", "Evidence")
        acked = store.acknowledge(r.alert_id)
        assert acked.resolved_at is None


class TestAlertResolve:
    def test_resolve_changes_status(self, store):
        r = store.create("omnix", "Alert", "Evidence")
        resolved = store.resolve(r.alert_id)
        assert resolved is not None
        assert resolved.status == AlertStatus.RESOLVED
        assert resolved.resolved_at is not None

    def test_resolve_nonexistent_returns_none(self, store):
        result = store.resolve("nonexistent_id")
        assert result is None


class TestDraftUpdates:
    def test_draft_slack_never_sends(self, store):
        draft = store.draft_slack_update("omnix")
        assert draft["send_status"] == "not_sent"
        assert draft["approval_required"] is True
        assert "draft_text" in draft
        assert isinstance(draft["draft_text"], str)
        assert len(draft["draft_text"]) > 0

    def test_draft_slack_with_alerts(self, store):
        store.create("omnix", "Alert 1", "Evidence 1", severity=AlertSeverity.ERROR)
        store.create("omnix", "Alert 2", "Evidence 2", severity=AlertSeverity.WARNING)
        draft = store.draft_slack_update("omnix")
        assert draft["alert_count"] == 2
        assert draft["send_status"] == "not_sent"
        assert "Alert 1" in draft["draft_text"] or "Alert 2" in draft["draft_text"]

    def test_draft_telegram_never_sends(self, store):
        draft = store.draft_telegram_update("omnix")
        assert draft["send_status"] == "not_sent"
        assert draft["approval_required"] is True
        assert "draft_text" in draft

    def test_draft_telegram_with_alerts(self, store):
        store.create("omnix", "Critical Alert", "Disk full", severity=AlertSeverity.CRITICAL)
        draft = store.draft_telegram_update("omnix")
        assert draft["alert_count"] == 1
        assert draft["send_status"] == "not_sent"

    def test_draft_empty_project_no_alerts(self, store):
        draft = store.draft_slack_update("empty_project")
        assert draft["alert_count"] == 0
        assert draft["send_status"] == "not_sent"


class TestDailyDigest:
    def test_digest_empty_project(self, store):
        digest = store.daily_digest("omnix")
        assert digest["open_count"] == 0
        assert digest["acknowledged_count"] == 0
        assert "digest_text" in digest
        assert "Project: omnix" in digest["digest_text"]

    def test_digest_counts_correctly(self, store):
        a1 = store.create("omnix", "Open Alert", "evidence")
        a2 = store.create("omnix", "To Ack", "evidence")
        store.acknowledge(a2.alert_id)
        store.create("omnix", "Resolved", "evidence")
        store.resolve(store.list(project_id="omnix")[-1].alert_id)

        digest = store.daily_digest("omnix")
        assert digest["open_count"] == 1
        assert digest["acknowledged_count"] == 1

    def test_digest_severity_breakdown(self, store):
        store.create("omnix", "Warn", "ev", severity=AlertSeverity.WARNING)
        store.create("omnix", "Error", "ev", severity=AlertSeverity.ERROR)
        digest = store.daily_digest("omnix")
        assert digest["severity_breakdown"].get("warning", 0) == 1
        assert digest["severity_breakdown"].get("error", 0) == 1


class TestAlertToDict:
    def test_to_dict_has_required_keys(self, store):
        r = store.create("omnix", "Test", "Evidence")
        d = r.to_dict()
        required_keys = [
            "alert_id", "project_id", "severity", "title", "evidence",
            "recommendation", "source_watchdog_id", "status",
            "created_at", "updated_at", "acknowledged_at", "resolved_at",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"
