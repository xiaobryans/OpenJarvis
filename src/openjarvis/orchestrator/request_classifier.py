"""Option A — Stage 1: request tier classifier.

Classifies an incoming chat request into one of four latency tiers so the
orchestrator can route appropriately (see docs/ORCHESTRATOR.md):

- INSTANT  (< 3s)      — Jarvis answers directly, no hierarchy
                         (greetings, time/date, simple recall, short factual Q).
- FAST     (< 15s)     — one manager / a single tool action
                         (weather, calendar, email lookup, one quick task).
- STANDARD (15s–2min)  — full hierarchy, sequential
                         (multi-part but bounded: summarize + analyze, research).
- COMPLEX  (2min+)     — full hierarchy, parallel workers + live status
                         (build/implement/create something substantial).

Deterministic, local, and fast (no LLM call): combines keyword/intent signals
with the existing complexity scorer. Returns a structured result usable by the
audit trail. This stage only CLASSIFIES; routing on the classification is wired
in later Option-A stages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict

INSTANT = "instant"
FAST = "fast"
STANDARD = "standard"
COMPLEX = "complex"

# Substantial build/creation work → COMPLEX.
_COMPLEX_PATTERNS = re.compile(
    r"\b(build|implement|create|develop|refactor|design|architect|"
    r"write\s+(me\s+)?(a|an|the|some)?\s*(code|script|program|app|application|"
    r"website|landing\s*page|function|module|test|feature)|"
    r"landing\s*page|web\s*app|full\s*stack|end[-\s]?to[-\s]?end|"
    r"set\s*up\s+a|migrate|deploy|integrate\s+\w+\s+(with|into)|"
    r"fix\s+(the\s+)?bug|add\s+a\s+feature|generate\s+a\s+(report|deck|plan))\b",
    re.IGNORECASE,
)

# Single bounded action / lookup → FAST.
_FAST_PATTERNS = re.compile(
    r"\b(weather|forecast|temperature|"
    r"calendar|schedule|agenda|"
    r"emails?|inbox|unread|messages?|slack|"
    r"remind|reminder|"
    r"briefing|"
    r"look\s*up|search\s+for|find\s+(me\s+)?the|check\s+(the|my))\b",
    re.IGNORECASE,
)

# Trivial / direct → INSTANT.
_INSTANT_PATTERNS = re.compile(
    r"^\s*(hi|hii|hey|yo|hello|sup|thanks|thank\s*you|thx|ok|okay|cool|"
    r"good\s*(morning|night|evening)|gm|gn)\b|"
    r"\bwhat('?s| is)\s+(the\s+)?(time|date|day)\b|"
    r"\bwhat\s+time\s+is\s+it\b|"
    r"\bwhat\s+day\s+is\s+it\b|"
    r"\bwhat('?s| is)\s+my\s+name\b|"
    r"\bwho\s+are\s+you\b|"
    r"\bwhat\s+timezone\b",
    re.IGNORECASE,
)

# Multi-step conjunction signals → push toward STANDARD/COMPLEX.
_MULTISTEP = re.compile(r"\b(and then|after that|then\b|;|\bplus\b|also\b)", re.IGNORECASE)


@dataclass(frozen=True)
class ClassifiedRequest:
    """Result of tier classification (also feeds the audit trail)."""

    tier: str
    reason: str
    score: float  # underlying 0-1 complexity score
    signals: Dict[str, object] = field(default_factory=dict)


def classify_request(text: str) -> ClassifiedRequest:
    """Classify *text* into a latency tier. Pure function, no side effects."""
    q = (text or "").strip()
    signals: Dict[str, object] = {}

    if not q:
        return ClassifiedRequest(INSTANT, "empty input", 0.0, {"empty": True})

    words = q.split()
    n_words = len(words)
    signals["n_words"] = n_words

    # Complexity score (best-effort; never fail classification on its absence).
    try:
        from openjarvis.learning.routing.complexity import score_complexity

        cr = score_complexity(q)
        score = float(cr.score)
        signals["complexity_tier"] = cr.tier
    except Exception:
        score = min(1.0, n_words / 60.0)
    signals["score"] = round(score, 3)

    is_complex = bool(_COMPLEX_PATTERNS.search(q))
    is_fast = bool(_FAST_PATTERNS.search(q))
    is_instant = bool(_INSTANT_PATTERNS.search(q))
    multistep = bool(_MULTISTEP.search(q))
    signals.update(
        complex_kw=is_complex, fast_kw=is_fast,
        instant_kw=is_instant, multistep=multistep,
    )

    # 1. Substantial build/creation work, or very high complexity → COMPLEX.
    if is_complex or score >= 0.8:
        return ClassifiedRequest(
            COMPLEX,
            "build/creation intent" if is_complex else "very high complexity",
            score, signals,
        )

    # 2. Trivial/direct (and not a build) → INSTANT. Short with no multi-step.
    if is_instant and not multistep and n_words <= 12:
        return ClassifiedRequest(INSTANT, "trivial/direct intent", score, signals)

    # 3. Multi-step OR clearly elevated complexity → STANDARD.
    if multistep or score >= 0.55:
        return ClassifiedRequest(
            STANDARD,
            "multi-step request" if multistep else "elevated complexity",
            score, signals,
        )

    # 4. Single bounded lookup/action → FAST.
    if is_fast:
        return ClassifiedRequest(FAST, "single bounded action/lookup", score, signals)

    # 5. Default: very short → INSTANT, otherwise FAST.
    if n_words <= 8 and score < 0.4:
        return ClassifiedRequest(INSTANT, "short, low-complexity", score, signals)
    return ClassifiedRequest(FAST, "default single-turn", score, signals)


__all__ = ["ClassifiedRequest", "classify_request",
           "INSTANT", "FAST", "STANDARD", "COMPLEX"]
