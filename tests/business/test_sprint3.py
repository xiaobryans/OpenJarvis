"""Tests for Sprint 3 — reminders (3F), improvement log, computer-control builders."""

from __future__ import annotations

import importlib

import pytest

from openjarvis.business.improvement_log import ImprovementLog
from openjarvis.business.reminders import ReminderStore, parse_when
from openjarvis.tools import computer_tools as ct


# 3F — relative-time parsing
def test_parse_when_relative():
    assert parse_when("in 2 hours", now=1000.0) == 1000.0 + 2 * 3600
    assert parse_when("in 30 minutes", now=1000.0) == 1000.0 + 30 * 60
    assert parse_when("remind me tomorrow", now=1000.0) == 1000.0 + 86400
    assert parse_when("no time here", now=1000.0) is None


def test_reminder_store_due_and_pending(tmp_path):
    s = ReminderStore(db_path=tmp_path / "r.db")
    s.add("call plumber", when="in 2 hours", now=1000.0)
    s.add("buy milk", when="in 30 minutes", now=1000.0)
    # At t=1000+45min, only the 30-min reminder is due.
    due = s.due(now=1000.0 + 45 * 60)
    assert len(due) == 1 and due[0]["text"] == "buy milk"
    assert len(s.pending()) == 2
    assert s.complete(due[0]["id"]) is True
    assert len(s.pending()) == 1


# Self-improvement log
def test_improvement_log_counts_and_pending(tmp_path):
    log = ImprovementLog(db_path=tmp_path / "i.db")
    log.add("improvement", "ported orb", now=1_000_000.0)
    log.add("bug_fix", "fixed 422 chat", now=1_000_000.0)
    log.add("research", "looked into Deepgram", now=1_000_000.0)
    log.add("pending", "wire WhatsApp", now=1_000_000.0)
    counts = log.weekly_counts(now=1_000_000.0 + 3600)
    assert counts["improvement"] == 1 and counts["bug_fix"] == 1
    assert counts["research"] == 1 and counts["pending"] == 1
    assert len(log.recent(20)) == 4
    assert len(log.pending()) == 1
    # Entry older than 7 days drops out of weekly counts.
    assert log.weekly_counts(now=1_000_000.0 + 8 * 86400)["improvement"] == 0


# 3E — command builders (no execution)
def test_computer_control_command_builders():
    assert ct.open_app_cmd("Safari") == ["open", "-a", "Safari"]
    assert ct.quit_app_cmd("Mail")[0] == "osascript"
    assert "quit" in ct.quit_app_cmd("Mail")[-1]
    assert ct.activate_app_cmd("Notes")[-1].endswith("activate")


@pytest.mark.parametrize("mod,tools", [
    ("openjarvis.tools.computer_tools", ["computer_control"]),
    ("openjarvis.tools.sprint3_tools", ["reminder", "improvement_log"]),
])
def test_sprint3_tools_registered(mod, tools):
    m = importlib.import_module(mod)
    importlib.reload(m)
    from openjarvis.core.registry import ToolRegistry
    for t in tools:
        assert t in ToolRegistry.keys()


def test_improvement_route_shape(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from openjarvis.server import improvement_routes
    paths = {getattr(r, "path", "") for r in improvement_routes.router.routes}
    assert "/v1/improvement-log" in paths
