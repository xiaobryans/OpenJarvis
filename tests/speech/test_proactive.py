"""Tests for proactive intelligence (2B/2F/2G/2H/3G) + Sprint 2 tool helpers."""

from __future__ import annotations

import importlib
from datetime import datetime

import pytest

from openjarvis.speech import proactive as pr


# 2B — first wake of day
def test_first_wake_today():
    now = datetime(2026, 6, 27, 8, 0)
    assert pr.is_first_wake_today(None, now) is True
    assert pr.is_first_wake_today("2026-06-26", now) is True   # different day
    assert pr.is_first_wake_today("2026-06-27", now) is False  # already greeted today


# 2F — build monitor dedup
def test_build_monitor_dedup():
    m = pr.BuildMonitor()
    assert m.new_commits(["a", "b"]) == ["a", "b"]
    assert m.new_commits(["b", "c"]) == ["c"]      # b already seen
    assert m.new_commits(["a", "b", "c"]) == []    # all seen
    assert "want a quick summary" in m.brief_prompt()


# 2G — late-night check-ins
def test_late_night_checkin_streak():
    t = pr.LateNightTracker()
    # Three consecutive nights active past 2am (00:30 each).
    for day in (25, 26, 27):
        t.record_active(datetime(2026, 6, day, 0, 30))
    assert t.should_check_in(datetime(2026, 6, 27, 0, 35)) is True
    # Only once per day.
    assert t.should_check_in(datetime(2026, 6, 27, 1, 0)) is False


def test_late_night_no_checkin_under_streak():
    t = pr.LateNightTracker()
    t.record_active(datetime(2026, 6, 27, 0, 30))  # one night only
    assert t.should_check_in(datetime(2026, 6, 27, 0, 35)) is False


def test_daytime_not_counted_as_late():
    t = pr.LateNightTracker()
    t.record_active(datetime(2026, 6, 27, 14, 0))  # 2pm, not late
    assert t.should_check_in(datetime(2026, 6, 27, 14, 5)) is False


# 2H — special dates
def test_special_date_on_the_day():
    out = pr.special_date_reminders(datetime(2026, 7, 22, 9, 0))
    assert any("anniversary" in s and "Today" in s for s in out)


def test_special_date_seven_days_before():
    out = pr.special_date_reminders(datetime(2026, 9, 9, 9, 0))  # 7 days before Sep 16
    assert any("partner's birthday" in s and "7 day" in s for s in out)


def test_special_date_outside_window():
    assert pr.special_date_reminders(datetime(2026, 3, 1, 9, 0)) == []


# 3G — energy profile
@pytest.mark.parametrize("mins,hour,expect", [
    (30, 14, "high"), (3, 14, "low"), (12, 14, "neutral"), (20, 3, "late_night"),
])
def test_energy_profile(mins, hour, expect):
    assert pr.energy_profile(mins, hour) == expect


# tool registration (reload to survive the autouse registry clear)
@pytest.mark.parametrize("mod,tools", [
    ("openjarvis.tools.screen_tools", ["screen_capture"]),
    ("openjarvis.tools.sprint2_tools", ["financial_snapshot", "web_research", "draft_message"]),
    ("openjarvis.tools.people_tools", ["people_remember", "memory_recall", "milestone"]),
])
def test_tools_registered(mod, tools):
    m = importlib.import_module(mod)
    importlib.reload(m)
    from openjarvis.core.registry import ToolRegistry
    for t in tools:
        assert t in ToolRegistry.keys()


def test_draft_message_never_auto_sends():
    import openjarvis.tools.sprint2_tools as s
    importlib.reload(s)
    tool = s.DraftMessageTool()
    res = tool.execute(channel="slack", recipient="vanta-hq", body="build is green")
    assert res.success is True
    assert res.metadata["requires_confirmation"] is True
    assert res.metadata["real_send_allowed"] is False
    assert "Confirm?" in res.content


def test_milestone_personal_not_generic():
    assert "OMNIX" in pr_milestone("first_omnix_user")
    assert pr_milestone("unknown_kind") == ""


def pr_milestone(kind):
    from openjarvis.tools.people_tools import milestone_message
    return milestone_message(kind)


# 2B — digest composition
def test_compose_morning_digest():
    d = pr.compose_morning_digest(
        weather_text="28°C partly cloudy", event_count=2, first_event="standup 10am",
        unread=5, flagged=1, urgent=["server alert"], now=datetime(2026, 6, 27, 8, 0),
    )
    assert "28°C" in d and "2 events" in d and "standup 10am" in d
    assert "5 unread" in d and "1 flagged" in d and "Urgent: server alert" in d


def test_compose_digest_quiet_day():
    d = pr.compose_morning_digest(now=datetime(2026, 6, 27, 8, 0))
    assert "Nothing on the calendar" in d and "0 unread" in d
