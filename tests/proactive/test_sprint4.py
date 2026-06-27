"""Tests for Sprint 4 proactive intelligence (stores + pure logic + tools + routes)."""

from __future__ import annotations

import importlib

import pytest

from openjarvis.proactive import stores as st


# 4A — email classification
@pytest.mark.parametrize("subject,sender,expect", [
    ("URGENT: payment failed", "billing@x", "URGENT"),
    ("Your invoice for March", "client@x", "IMPORTANT"),
    ("Weekly newsletter — unsubscribe here", "news@x", "NOISE"),
    ("Lunch tomorrow?", "friend@x", "INFO"),
])
def test_classify_email(subject, sender, expect):
    assert st.classify_email(subject, sender) == expect


def test_email_triage_store_filters_noise(tmp_path):
    s = st.EmailTriageStore(db_path=tmp_path / "e.db")
    s.record("URGENT: deadline today", "boss@x")
    s.record("Invoice #12", "client@x")
    s.record("50% off sale ends soon", "promo@x")   # NOISE
    rows = s.actionable()
    cats = {r["category"] for r in rows}
    assert "NOISE" not in cats and cats == {"URGENT", "IMPORTANT"}
    assert rows[0]["category"] == "URGENT"  # urgent first


# 4F — task extraction + store
@pytest.mark.parametrize("text,n", [
    ("I need to call Ahmad", 1),
    ("remind me to send the invoice", 1),
    ("nothing actionable here", 0),
])
def test_extract_tasks(text, n):
    assert len(st.extract_tasks(text)) == n


def test_task_store_capture_pending_overdue_done(tmp_path):
    s = st.TaskStore(db_path=tmp_path / "t.db")
    got = s.capture_from_text("I need to fix the pipe and remind me to call the client", now=1000.0)
    assert len(got) == 2
    assert len(s.pending()) == 2
    # 'remind me' is urgent (24h); 2 days later it is overdue.
    overdue = s.overdue(now=1000.0 + 2 * 86400)
    assert any("call the client" in o["text"] for o in overdue)
    assert s.complete("fix the pipe") is True
    assert len(s.pending()) == 1


# 4G/4C — research queue + findings
def test_research_queue_and_findings(tmp_path):
    s = st.ResearchStore(db_path=tmp_path / "r.db")
    s.enqueue("local LLM inference")
    assert len(s.queue()) == 1
    s.add_finding("local LLM inference", "MLX is fast on Apple Silicon", tag="AI")
    assert s.overnight()[0]["tag"] == "AI"


# 4B — anomalies
def test_anomaly_store(tmp_path):
    s = st.AnomalyStore(db_path=tmp_path / "a.db")
    s.record("financial", "Spending spike in software category", severity="warn")
    assert s.recent()[0]["kind"] == "financial"


# 4E — relationship checkups with context
def test_relationship_checkups_context(tmp_path):
    s = st.RelationshipStore(db_path=tmp_path / "rel.db")
    s.mention("brother", kind="brother", context="dealing with the work situation", now=1000.0)
    # 6 days later (> 5-day brother threshold) -> surfaces with context.
    rows = s.checkups(now=1000.0 + 6 * 86400)
    assert rows and "work situation" in rows[0]["line"] and rows[0]["days"] == 6


def test_relationship_not_due(tmp_path):
    s = st.RelationshipStore(db_path=tmp_path / "rel.db")
    s.mention("partner", kind="partner", now=1000.0)
    assert s.checkups(now=1000.0 + 1 * 86400) == []  # 1 day < 3-day partner threshold


# 4H — patterns
def test_pattern_insights(tmp_path):
    s = st.PatternStore(db_path=tmp_path / "p.db")
    s.record_session(hour=23, duration_s=1800)
    s.record_session(hour=2, duration_s=600)   # late night
    s.record_session(hour=23, duration_s=1200)
    i = s.insights()
    assert i["sessions"] == 3 and i["most_active_hour"] == 23 and i["late_nights"] == 1


# 4D — weekly summary
def test_weekly_summary(tmp_path):
    s = st.WeeklySummaryStore(db_path=tmp_path / "w.db")
    s.save("2026-W26", "This week you completed 3 jobs, brought in $600.")
    assert "3 jobs" in s.latest()["text"]


# tools registered
def test_sprint4_tools_registered():
    import openjarvis.tools.sprint4_tools as t
    importlib.reload(t)
    from openjarvis.core.registry import ToolRegistry
    for name in ("tasks", "research_queue", "anomalies", "relationship_checkups",
                 "email_triage", "week_in_review", "patterns"):
        assert name in ToolRegistry.keys()


# endpoints exist
def test_sprint4_routes_exist():
    pytest.importorskip("fastapi")
    from openjarvis.server import sprint4_routes
    paths = {getattr(r, "path", "") for r in sprint4_routes.router.routes}
    for p in ("/v1/email/triage", "/v1/anomalies/recent", "/v1/research/overnight",
              "/v1/research/queue", "/v1/summaries/weekly", "/v1/relationships/checkups",
              "/v1/tasks/pending"):
        assert p in paths
