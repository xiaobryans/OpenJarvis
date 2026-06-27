"""Proactive intelligence for VANTA — pure, testable decision logic.

Covers the time/state-driven behaviours of Sprint 2 / 3 with no I/O so they can
be unit-tested headlessly; the runtime (voice loop, schedulers) wires them to
real data:

  * first-wake-of-day tracking          -> 2B daily digest gate
  * git build-session monitor (dedup)   -> 2F auto-brief after commits
  * late-night check-in tracker         -> 2G honest check-ins
  * special-date reminders              -> 2H anniversary / birthday
  * energy profile                      -> 3G mood/energy awareness
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set

try:
    from zoneinfo import ZoneInfo
    _SGT = ZoneInfo("Asia/Singapore")
except Exception:  # pragma: no cover
    _SGT = None  # type: ignore[assignment]

# Special dates (month, day) -> label. Reminders fire 7 days before + on the day.
SPECIAL_DATES: Dict[tuple, str] = {
    (7, 22): "anniversary",
    (9, 16): "partner's birthday",
}
SPECIAL_REMIND_WINDOW = 7
LATE_NIGHT_HOUR = 2          # "past 2am" = hour in [0, 2)
LATE_NIGHT_STREAK = 3        # consecutive nights before a check-in


def now_sgt(now: Optional[datetime] = None) -> datetime:
    if now is not None:
        return now
    return datetime.now(_SGT) if _SGT is not None else datetime.now()  # pragma: no cover


# ── 2B — first wake of the (SGT) day ─────────────────────────────────────────
def is_first_wake_today(last_wake_date: Optional[str], now: Optional[datetime] = None) -> bool:
    """True if no wake has been recorded yet for the current SGT calendar day.

    ``last_wake_date`` is an ISO date string (YYYY-MM-DD) of the last digest, or
    None. Resets naturally at SGT midnight because the comparison is by date.
    """
    today = now_sgt(now).date().isoformat()
    return last_wake_date != today


# ── 2F — build-session monitor (one brief per commit hash) ───────────────────
@dataclass
class BuildMonitor:
    seen: Set[str] = field(default_factory=set)

    def new_commits(self, commit_hashes: List[str]) -> List[str]:
        """Return commit hashes not seen before (newest-first input preserved)."""
        fresh = [h for h in commit_hashes if h and h not in self.seen]
        self.seen.update(fresh)
        return fresh

    @staticmethod
    def brief_prompt() -> str:
        return "Just saw you committed — want a quick summary of what changed?"


# ── 2G — honest late-night check-ins ─────────────────────────────────────────
@dataclass
class LateNightTracker:
    nights: Set[str] = field(default_factory=set)   # SGT dates with past-2am activity
    last_checkin_date: Optional[str] = None

    @staticmethod
    def _is_late(dt: datetime) -> bool:
        return 0 <= dt.hour < LATE_NIGHT_HOUR

    def record_active(self, now: Optional[datetime] = None) -> None:
        dt = now_sgt(now)
        if self._is_late(dt):
            self.nights.add(dt.date().isoformat())

    def _consecutive_streak(self, today: date) -> int:
        streak = 0
        d = today
        while d.isoformat() in self.nights:
            streak += 1
            d = d - timedelta(days=1)
        return streak

    def should_check_in(self, now: Optional[datetime] = None) -> bool:
        """Fire at most once per day after 3+ consecutive late nights."""
        dt = now_sgt(now)
        today = dt.date()
        if self.last_checkin_date == today.isoformat():
            return False
        if self._consecutive_streak(today) >= LATE_NIGHT_STREAK:
            self.last_checkin_date = today.isoformat()
            return True
        return False

    @staticmethod
    def message() -> str:
        return "You've been up late three nights running. You good?"


# ── 2H — special-date reminders ──────────────────────────────────────────────
def _next_occurrence(month: int, day: int, today: date) -> date:
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError:  # pragma: no cover - Feb 29 etc.
        d = date(year, month, 28)
    if d < today:
        d = date(year + 1, month, day)
    return d


def special_date_reminders(now: Optional[datetime] = None) -> List[str]:
    """Return reminder lines for special dates within the 7-day window or today."""
    today = now_sgt(now).date()
    out: List[str] = []
    for (m, d), label in SPECIAL_DATES.items():
        days = (_next_occurrence(m, d, today) - today).days
        if days == 0:
            out.append(f"Today is the {label}.")
        elif 1 <= days <= SPECIAL_REMIND_WINDOW:
            out.append(f"Heads up — {label} in {days} day{'s' if days != 1 else ''}.")
    return out


# ── 3G — energy / mood profile ───────────────────────────────────────────────
def energy_profile(avg_session_minutes: float, hour: int) -> str:
    """Map activity stats to a tone hint for Ivy. Never preachy — just aware."""
    if 0 <= hour < 5:
        return "late_night"          # acknowledge the grind, calmer
    if avg_session_minutes >= 25:
        return "high"                # match the energy
    if avg_session_minutes <= 5:
        return "low"                 # keep it calm and brief
    return "neutral"


# ── 2B — morning digest composer ─────────────────────────────────────────────
def compose_morning_digest(
    weather_text: str = "",
    event_count: int = 0,
    first_event: str = "",
    unread: int = 0,
    flagged: int = 0,
    urgent: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> str:
    """Build the first-wake daily briefing line (weather, calendar, mail, urgent)."""
    parts: List[str] = ["Here's your day:"]
    if weather_text:
        parts.append(f"{weather_text} in Singapore.")
    if event_count > 0:
        ev = f"You have {event_count} event{'s' if event_count != 1 else ''}"
        parts.append(f"{ev} — first up, {first_event}." if first_event else f"{ev}.")
    else:
        parts.append("Nothing on the calendar.")
    parts.append(f"{unread} unread email{'s' if unread != 1 else ''}, {flagged} flagged.")
    for u in (urgent or []):
        parts.append(f"Urgent: {u}.")
    for r in special_date_reminders(now):
        parts.append(r)
    return " ".join(parts)


# ── Section 4.1 — morning briefing with Sprint 4 proactive data folded in ─────
def compose_full_briefing(base: str = "", now: Optional[datetime] = None) -> str:
    """Extend the base digest with Sprint 4 data: urgent emails, anomalies, top
    overnight research, overdue tasks, relationship check-ins, and (on Sunday)
    the weekly summary. Each source is independently guarded."""
    parts: List[str] = [base] if base else []
    epoch = now.timestamp() if now is not None else None
    try:
        from openjarvis.proactive.stores import (
            AnomalyStore, EmailTriageStore, RelationshipStore,
            ResearchStore, TaskStore, WeeklySummaryStore,
        )
        em = EmailTriageStore().actionable(now=epoch)
        if em:
            parts.append(f"{len(em)} email{'s' if len(em) != 1 else ''} need attention — top: {em[0]['subject']}.")
        an = AnomalyStore().recent(5, now=epoch)
        if an:
            parts.append(f"{len(an)} anomaly flag{'s' if len(an) != 1 else ''}: {an[0]['description']}.")
        rf = ResearchStore().overnight(3)
        if rf:
            parts.append(f"Overnight I found {len(rf)} thing{'s' if len(rf) != 1 else ''} worth knowing. "
                         f"{rf[0]['summary'][:80]}. Full list on screen.")
        od = TaskStore().overdue(now=epoch)
        if od:
            parts.append(f"{len(od)} overdue task{'s' if len(od) != 1 else ''}: {od[0]['text']}.")
        cu = RelationshipStore().checkups(now=epoch)
        if cu:
            parts.append(cu[0]["line"])
        if now_sgt(now).weekday() == 6:  # Sunday -> weekly summary
            wk = WeeklySummaryStore().latest()
            if wk:
                parts.append("Week in review: " + wk["text"])
    except Exception:  # pragma: no cover - defensive; a bad source never breaks the briefing
        pass
    return " ".join(p for p in parts if p)


__all__ = [
    "is_first_wake_today", "BuildMonitor", "LateNightTracker",
    "special_date_reminders", "energy_profile", "now_sgt",
    "compose_morning_digest", "compose_full_briefing",
    "SPECIAL_DATES", "LATE_NIGHT_STREAK",
]
