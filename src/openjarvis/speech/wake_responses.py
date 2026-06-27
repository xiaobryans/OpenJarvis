"""Contextual wake-welcome responses for VANTA.

When VANTA wakes (voice wake word or double-clap), it speaks a short, contextual
greeting before listening for the command. ``get_wake_response()`` picks a line
based on the current Singapore time + date, avoids repeating the previous line,
and occasionally appends a day-of-week or special-date note.

Kept deliberately short — under ~10 words for most. No speeches.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import List, Optional

# ── 6 time slots × 10 variations (Singapore local time) ──────────────────────
EARLY_MORNING: List[str] = [  # 5am–9am
    "Morning, boss. What are we starting with?",
    "Early start. I'm ready when you are.",
    "Good morning. What's first?",
    "Morning. Let's get moving.",
    "Up early. What do you need?",
    "Morning, brother. What's the plan?",
    "Good morning. VANTA online.",
    "Early bird. What are we hitting first?",
    "Morning. Ready and standing by.",
    "Rise and grind. What do you need from me?",
]
MORNING: List[str] = [  # 9am–12pm
    "What do you need, boss?",
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
AFTERNOON: List[str] = [  # 12pm–5pm
    "Afternoon. What do you need?",
    "Here. What's up?",
    "VANTA online. Talk to me.",
    "What do you need from me?",
    "Ready. What are we doing?",
    "Afternoon, boss. What's the move?",
    "Online. Go ahead.",
    "Here. What do you need sorted?",
    "Standing by. What's next?",
    "What do you need, brother?",
]
EVENING: List[str] = [  # 5pm–9pm
    "Evening. How can I help?",
    "Evening, boss. What do you need?",
    "Here. What's on your mind?",
    "VANTA online. Go ahead.",
    "Evening. Talk to me.",
    "What do you need tonight?",
    "Evening, brother. What's up?",
    "Online. What do you need?",
    "Here. What are we sorting?",
    "Evening. Ready when you are.",
]
NIGHT: List[str] = [  # 9pm–1am
    "Still going. What do you need?",
    "Here. What's on?",
    "Night shift. What do you need?",
    "VANTA online. Talk to me.",
    "Late night. What's the move?",
    "Here, boss. What do you need?",
    "Online. What are we working on?",
    "Night mode. Go ahead.",
    "Still here. What do you need?",
    "What do you need, brother?",
]
LATE_NIGHT: List[str] = [  # 1am–5am — grind hours
    "Still grinding. What do you need?",
    "Late night build session. I'm here.",
    "You're up late. What do you need?",
    "VANTA online. The night crew.",
    "Still at it, boss. What's next?",
    "Late night. Talk to me.",
    "The grind doesn't stop. What do you need?",
    "Here with you. What's the move?",
    "Still running. What do you need?",
    "Late night mode. Go ahead, brother.",
]

# Special dates (month, day) → note added only ON the day itself.
_SPECIAL = {
    (7, 22): "Heads up — anniversary coming up.",
    (9, 16): "Partner's birthday coming up.",
}

# Track the last base line so we never repeat the same one twice in a row.
_last = {"text": ""}


def _slot_for_hour(hour: int) -> List[str]:
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
    return LATE_NIGHT  # 1am–5am


def _now_sgt(now: Optional[datetime]) -> datetime:
    if now is not None:
        return now
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Singapore"))
    except Exception:
        return datetime.now()


def get_wake_response(now: Optional[datetime] = None) -> str:
    """Return a short contextual wake greeting for the current SGT time/date."""
    dt = _now_sgt(now)
    hour, weekday = dt.hour, dt.weekday()  # Monday == 0

    slot = _slot_for_hour(hour)
    choices = [c for c in slot if c != _last["text"]] or list(slot)
    base = random.choice(choices)
    _last["text"] = base

    parts = [base]

    # Special date — only on the actual day (advance reminders are handled
    # separately by proactive intelligence).
    special = _SPECIAL.get((dt.month, dt.day))
    if special:
        parts.append(special)
    else:
        # Light day-of-week flavour, only sometimes (not every wake needs it).
        if weekday == 0 and random.random() < 0.5:
            parts.append("New week.")
        elif weekday == 4 and hour >= 17 and random.random() < 0.6:
            parts.append("End of the week.")

    return " ".join(parts)
