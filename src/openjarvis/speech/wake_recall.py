"""History recall for VANTA.

Detects "what did we talk about" / "remind me what I said about X" style
questions and answers them from the unified voice/chat history (the JSONL store
written by voice_bus). Never invents past conversations — if nothing matches it
says so directly. Usable from both the voice loop and (optionally) typed chat.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from openjarvis.speech import voice_bus

_SGT = timezone(timedelta(hours=8))

_RECALL_RE = re.compile(
    r"\b(what did (we|i|you)|what was that|remind me|do you remember|"
    r"\brecall\b|talked about|talk about|tell me about|what.*say about|"
    r"earlier (you|we|i)|previously|last (week|time|night)|yesterday)\b"
)

# Words to drop when extracting search keywords from a recall question.
_STOP = set(
    "what did we i you that thing about the a an to me my mine remind do does "
    "you your remember recall was were tell told say said earlier last week time "
    "night yesterday today previously talked talk discuss discussed of on in for "
    "hey vanta please can could would is are it this with and or but".split()
)


def is_recall_query(text: str) -> bool:
    """True if *text* looks like a question about a previous conversation."""
    return bool(_RECALL_RE.search((text or "").lower()))


def _keywords(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if w not in _STOP and len(w) > 2]


def _date_window(text: str, now: datetime) -> Optional[tuple]:
    t = text.lower()
    if "yesterday" in t:
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), (start + timedelta(days=1)).timestamp()
    if "today" in t:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), (start + timedelta(days=1)).timestamp()
    if "last week" in t:
        return (now - timedelta(days=7)).timestamp(), now.timestamp() + 1
    if "last night" in t:
        start = (now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        return start.timestamp(), now.replace(hour=6, minute=0, second=0, microsecond=0).timestamp()
    return None


def recall_answer(text: str, *, limit: int = 400, now: Optional[datetime] = None) -> str:
    """Search unified history for *text* and return a natural-language summary."""
    rows = voice_bus.read_history(limit=limit)  # newest first
    now = now or datetime.now(_SGT)

    window = _date_window(text, now)
    if window:
        lo, hi = window
        rows = [r for r in rows if lo <= float(r.get("ts", 0)) < hi]

    kws = _keywords(text)
    if kws:
        rows = [r for r in rows if any(k in str(r.get("text", "")).lower() for k in kws)]

    if not rows:
        return "I don't have anything on that in our history yet."

    # Read oldest→newest of the top matches so it summarises naturally.
    picked = rows[:6][::-1]
    parts = []
    for r in picked:
        who = "you" if r.get("speaker") in ("bryan", "you") else "I"
        parts.append(f"{who} said \"{str(r.get('text', '')).strip()[:160]}\"")
    return "From our history: " + "; ".join(parts) + "."
