"""Tests for the Sprint 4 proactive scheduler (SGT job timing + job functions)."""

from __future__ import annotations

from datetime import datetime

from openjarvis.proactive import scheduler as sch
from openjarvis.proactive.stores import ResearchStore


def _spy(monkeypatch):
    calls = []
    for name in ("run_email_triage", "run_research_queue", "run_news",
                 "run_morning_briefing", "run_weekly_summary"):
        monkeypatch.setattr(sch, name, (lambda n: (lambda: calls.append(n) or {"ran": True}))(name))
    return calls


def test_email_triage_runs_every_30_min(monkeypatch):
    calls = _spy(monkeypatch)
    s = sch.ProactiveScheduler()
    s._tick(now=datetime(2026, 6, 29, 10, 0))   # Monday 10:00
    assert "run_email_triage" in calls
    calls.clear()
    # Immediately after, the 30-min gate suppresses it.
    s._tick(now=datetime(2026, 6, 29, 10, 5))
    assert "run_email_triage" not in calls


def test_night_jobs_at_2am_once(monkeypatch):
    calls = _spy(monkeypatch)
    s = sch.ProactiveScheduler()
    s._last_triage = 1e18  # suppress triage to isolate night jobs
    s._tick(now=datetime(2026, 6, 29, 2, 0))
    assert "run_research_queue" in calls and "run_news" in calls
    calls.clear()
    s._tick(now=datetime(2026, 6, 29, 2, 30))   # same day -> not again
    assert "run_research_queue" not in calls


def test_morning_briefing_at_8am(monkeypatch):
    calls = _spy(monkeypatch)
    s = sch.ProactiveScheduler()
    s._last_triage = 1e18
    s._tick(now=datetime(2026, 6, 29, 8, 0))
    assert "run_morning_briefing" in calls


def test_weekly_summary_sunday_8pm(monkeypatch):
    calls = _spy(monkeypatch)
    s = sch.ProactiveScheduler()
    s._last_triage = 1e18
    s._tick(now=datetime(2026, 6, 28, 20, 0))   # Sunday 20:00
    assert "run_weekly_summary" in calls
    calls.clear()
    s._tick(now=datetime(2026, 6, 29, 20, 0))   # Monday 20:00 -> no
    assert "run_weekly_summary" not in calls


def test_run_research_queue_processes(monkeypatch, tmp_path):
    store = ResearchStore(db_path=tmp_path / "r.db")
    store.enqueue("test topic")
    monkeypatch.setattr(sch, "_web_search", lambda q, max_results=3: "finding for " + q)
    # Point the job's store at our temp db.
    monkeypatch.setattr(sch, "ResearchStore", lambda: store, raising=False)
    import openjarvis.proactive.stores as st
    monkeypatch.setattr(st, "ResearchStore", lambda *a, **k: store)
    out = sch.run_research_queue()
    assert out["processed"] == 1
    assert store.queue() == []                  # cleared
    assert store.overnight()[0]["summary"].startswith("finding for")
