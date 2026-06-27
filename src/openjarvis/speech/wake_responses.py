"""VANTA wake responses — contextual greetings + short acknowledgements.

Rebuilt for the voice pipeline (Task 1). Pure data + logic, no I/O, so it is
fully unit-testable without a microphone or network.

Public API:
    get_wake_response(now=None, last_wake_ts=None, *, force_full=None) -> str

Behaviour (per spec):
  * First wake of the day, or after 2+ hours of inactivity → full contextual
    greeting chosen from the time-slot pool (10 variations x 6 SGT slots).
  * Subsequent wakes in the same session -> a short acknowledgement.
  * Day awareness: Monday adds a "New week." prefix; Friday after 17:00 adds
    "End of the week."; weekends keep a relaxed tone (handled by the slots).
  * Special dates (on the day only, SGT): Jul 22 anniversary, Sep 16 birthday.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import List, Optional

try:  # zoneinfo is stdlib on 3.9+
    from zoneinfo import ZoneInfo
    _SGT = ZoneInfo("Asia/Singapore")
except Exception:  # pragma: no cover
    _SGT = None  # type: ignore[assignment]

# Gap of inactivity after which a wake counts as "fresh" -> full greeting.
FULL_GREETING_GAP = timedelta(hours=2)

# ── Short acknowledgements (subsequent wakes in a session) ───────────────────
SHORT_ACKS: List[str] = [
    "Yeah?", "Go ahead.", "Here.", "What's up?", "Talk to me.",
    "Ready.", "What do you need?", "I'm here.", "Go on.", "Mm?",
]

# ── Full greetings — 6 SGT time slots, 10 variations each ─────────────────────
EARLY_MORNING: List[str] = [  # 05:00–09:00
    "Morning boss. What are we starting with?",
    "Early start. I'm ready when you are.",
    "Good morning. What's first?",
    "Morning. Let's get moving.",
    "Up early. What do you need?",
    "Morning brother. What's the plan?",
    "Good morning. VANTA online.",
    "Early bird. What are we hitting first?",
    "Morning. Ready and standing by.",
    "Rise and grind. What do you need from me?",
]
MORNING: List[str] = [  # 09:00–12:00
    "What do you need boss?",
    "Morning's moving. What's on?",
    "VANTA online. Go ahead.",
    "Ready. What are we working on?",
    "What's the move?",
    "Online and listening. What do you need?",
    "Good morning. Talk to me.",
    "Here. What do you need?",
    "Standing by. What's next?",
    "Ready when you are. Go ahead.",
]
AFTERNOON: List[str] = [  # 12:00–17:00
    "Afternoon. What do you need?",
    "Here. What's up?",
    "VANTA online. Talk to me.",
    "What do you need from me?",
    "Ready. What are we doing?",
    "Afternoon boss. What's the move?",
    "Online. Go ahead.",
    "Here. What do you need sorted?",
    "Standing by. What's next?",
    "What do you need brother?",
]
EVENING: List[str] = [  # 17:00–21:00
    "Evening. How can I help?",
    "Evening boss. What do you need?",
    "Here. What's on your mind?",
    "VANTA online. Go ahead.",
    "Evening. Talk to me.",
    "What do you need tonight?",
    "Evening brother. What's up?",
    "Online. What do you need?",
    "Here. What are we sorting?",
    "Evening. Ready when you are.",
]
NIGHT: List[str] = [  # 21:00–01:00
    "Still going. What do you need?",
    "Here. What's on?",
    "Night shift. What do you need?",
    "VANTA online. Talk to me.",
    "Late night. What's the move?",
    "Here boss. What do you need?",
    "Online. What are we working on?",
    "Night mode. Go ahead.",
    "Still here. What do you need?",
    "What do you need brother?",
]
LATE_NIGHT: List[str] = [  # 01:00–05:00
    "Still grinding. What do you need?",
    "Late night build session. I'm here.",
    "You're up late. What do you need?",
    "VANTA online. The night crew.",
    "Still at it boss. What's next?",
    "Late night. Talk to me.",
    "The grind doesn't stop. What do you need?",
    "Here with you. What's the move?",
    "Still running. What do you need?",
    "Late night mode. Go ahead brother.",
]


def _now_sgt(now: Optional[datetime]) -> datetime:
    """Return *now* in SGT; default to current time."""
    if now is not None:
        return now
    if _SGT is not None:
        return datetime.now(_SGT)
    return datetime.now()  # pragma: no cover


def slot_for_hour(hour: int) -> List[str]:
    """Return the greeting pool for an hour-of-day (0–23), SGT."""
    if 5 <= hour < 9:
        return EARLY_MORNING
    if 9 <= hour < 12:
        return MORNING
    if 12 <= hour < 17:
        return AFTERNOON
    if 17 <= hour < 21:
        return EVENING
    if hour >= 21 or hour < 1:
        return NIGHT
    return LATE_NIGHT  # 01:00–05:00


def _day_prefix(dt: datetime) -> str:
    """Day-awareness prefix: Monday / Friday-evening flavour."""
    wd = dt.weekday()  # Mon=0 … Sun=6
    if wd == 0:
        return "New week. "
    if wd == 4 and dt.hour >= 17:
        return "End of the week. "
    return ""


def _special_suffix(dt: datetime) -> str:
    """Special-date heads-up appended on the day only (SGT)."""
    if dt.month == 7 and dt.day == 22:
        return " Heads up — anniversary today."
    if dt.month == 9 and dt.day == 16:
        return " Partner's birthday today."
    return ""


def is_full_greeting(last_wake_ts: Optional[float], now: Optional[datetime] = None) -> bool:
    """True when this wake deserves the full greeting (first today / 2h+ gap)."""
    if last_wake_ts is None:
        return True
    dt = _now_sgt(now)
    try:
        last = datetime.fromtimestamp(last_wake_ts, tz=dt.tzinfo)
    except Exception:
        return True
    # Different calendar day, or a 2h+ gap, both qualify as a fresh wake.
    if last.date() != dt.date():
        return True
    return (dt - last) >= FULL_GREETING_GAP


def get_wake_response(
    now: Optional[datetime] = None,
    last_wake_ts: Optional[float] = None,
    *,
    force_full: Optional[bool] = None,
    rng: Optional[random.Random] = None,
) -> str:
    """Return the spoken wake response for the current SGT context.

    force_full overrides the first-of-day / 2h-gap heuristic when set.
    rng allows deterministic selection in tests.
    """
    dt = _now_sgt(now)
    pick = (rng or random).choice
    full = force_full if force_full is not None else is_full_greeting(last_wake_ts, dt)
    if not full:
        return pick(SHORT_ACKS)
    base = pick(slot_for_hour(dt.hour))
    return f"{_day_prefix(dt)}{base}{_special_suffix(dt)}"


__all__ = [
    "get_wake_response", "is_full_greeting", "slot_for_hour",
    "SHORT_ACKS", "EARLY_MORNING", "MORNING", "AFTERNOON", "EVENING",
    "NIGHT", "LATE_NIGHT", "FULL_GREETING_GAP",
]
