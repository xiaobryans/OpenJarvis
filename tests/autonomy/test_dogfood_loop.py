"""Tests for Real Dogfood Loop (US9 Phase 11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openjarvis.autonomy.dogfood_loop import (
    get_dogfood_status,
    get_latest_dogfood_report,
    run_dogfood_snapshot,
)


@pytest.fixture(autouse=True)
def tmp_report_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("openjarvis.autonomy.dogfood_loop._REPORT_DIR", tmp_path)
    yield tmp_path


class TestDogfoodSnapshot:
    def test_snapshot_returns_dict(self):
        report = run_dogfood_snapshot(save_report=False)
        assert isinstance(report, dict)

    def test_snapshot_has_required_sections(self):
        report = run_dogfood_snapshot(save_report=False)
        assert "readiness" in report
        assert "connectors" in report
        assert "queue" in report
        assert "memory" in report
        assert "budget" in report
        assert "approvals" in report
        assert "blockers" in report

    def test_snapshot_no_external_posting(self):
        report = run_dogfood_snapshot(save_report=False)
        assert "external_posting" in report
        assert "disabled" in report["external_posting"].lower()

    def test_snapshot_saves_report_file(self, tmp_report_dir):
        run_dogfood_snapshot(save_report=True)
        reports = list(tmp_report_dir.glob("dogfood_report_*.json"))
        assert len(reports) == 1

    def test_snapshot_report_is_valid_json(self, tmp_report_dir):
        run_dogfood_snapshot(save_report=True)
        reports = list(tmp_report_dir.glob("dogfood_report_*.json"))
        content = reports[0].read_text(encoding="utf-8")
        data = json.loads(content)
        assert "project_id" in data

    def test_snapshot_blockers_is_list(self):
        report = run_dogfood_snapshot(save_report=False)
        assert isinstance(report["blockers"], list)
        assert isinstance(report["blocker_count"], int)

    def test_snapshot_no_secret_values(self):
        import os
        report = run_dogfood_snapshot(save_report=False)
        report_str = json.dumps(report)
        for key in ("JARVIS_SLACK_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN", "TAVILY_API_KEY"):
            val = os.environ.get(key, "")
            if val and len(val) > 4:
                assert val not in report_str, f"Secret {key} leaked in dogfood report"

    def test_snapshot_elapsed_seconds_present(self):
        report = run_dogfood_snapshot(save_report=False)
        assert "elapsed_seconds" in report
        assert report["elapsed_seconds"] >= 0


class TestDogfoodStatus:
    def test_status_active(self):
        s = get_dogfood_status()
        assert s["active"] is True
        assert s["external_posting_disabled"] is True

    def test_status_no_report_initially(self, tmp_report_dir):
        s = get_dogfood_status()
        assert s["latest_report_date"] is None

    def test_status_shows_report_after_snapshot(self, tmp_report_dir):
        run_dogfood_snapshot(save_report=True)
        s = get_dogfood_status()
        assert s["latest_report_date"] is not None

    def test_get_latest_report_none_initially(self, tmp_report_dir):
        report = get_latest_dogfood_report()
        assert report is None

    def test_get_latest_report_after_snapshot(self, tmp_report_dir):
        run_dogfood_snapshot(save_report=True)
        report = get_latest_dogfood_report()
        assert report is not None
        assert "project_id" in report
