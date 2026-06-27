"""Proactive scheduler (Sprint 4 Task 1) — runs the Stage-4 jobs automatically.

A lightweight daemon thread (same pattern as voice_supervisor / SyncScheduler)
that wakes once a minute and runs jobs on an SGT schedule:

  * every 30 min   — email triage (Gmail unread -> classify -> store)
  * 02:00 SGT      — process the research queue + news intelligence
  * 08:00 SGT      — compose + persist the morning briefing
  * Sun 20:00 SGT  — weekly summary

Each job is an idempotent, independently-guarded function that is ALSO callable
directly (for manual triggering / verification). Disable with VANTA_SCHEDULER=off.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("openjarvis.proactive.scheduler")

try:
    from zoneinfo import ZoneInfo
    _SGT = ZoneInfo("Asia/Singapore")
except Exception:  # pragma: no cover
    _SGT = None

_BRIEFING_PATH = Path.home() / ".openjarvis" / "briefings" / "latest.md"
NEWS_QUERIES = [
    ("AI", "AI news today Singapore"),
    ("Singapore", "Singapore tech business news"),
    ("Tool", "AI tools productivity 2026"),
]


def _now_sgt(now: Optional[datetime] = None) -> datetime:
    if now is not None:
        return now
    return datetime.now(_SGT) if _SGT is not None else datetime.now()


def _web_search(query: str, max_results: int = 3) -> str:
    """Run the existing web_search tool; return its text content ('' on failure)."""
    try:
        import openjarvis.tools  # noqa: F401 ensure registration
        from openjarvis.core.registry import ToolRegistry
        if "web_search" not in ToolRegistry.keys():
            return ""
        r = ToolRegistry.get("web_search")().execute(query=query, max_results=max_results)
        return (getattr(r, "content", "") or "").strip()
    except Exception as exc:
        logger.warning("web_search failed for %r: %s", query, exc)
        return ""


# ── jobs (each callable directly for manual trigger / verification) ───────────
def run_email_triage() -> Dict[str, Any]:
    """Fetch unread Gmail, classify, save URGENT/IMPORTANT (noise filtered)."""
    from openjarvis.proactive.stores import EmailTriageStore
    store = EmailTriageStore()
    saved = 0
    try:
        from openjarvis.connectors.gmail import (
            GmailConnector, _call_with_refresh, _extract_header,
            _gmail_api_get_message, _gmail_api_list_messages,
        )
        conn = GmailConnector()
        if not conn.is_connected():
            return {"ran": True, "connected": False, "saved": 0}
        cred = conn._credentials_path
        resp = _call_with_refresh(_gmail_api_list_messages, cred, query="is:unread in:inbox")
        for stub in (resp.get("messages") or [])[:25]:
            mid = stub.get("id", "")
            if not mid:
                continue
            try:
                msg = _call_with_refresh(_gmail_api_get_message, cred, mid)
            except Exception:
                continue
            headers = msg.get("payload", {}).get("headers", [])
            store.record(
                _extract_header(headers, "Subject") or "(no subject)",
                _extract_header(headers, "From"),
                (msg.get("snippet") or "")[:120],
                msg_id=mid,
            )
            saved += 1
        return {"ran": True, "connected": True, "saved": saved}
    except Exception as exc:
        logger.warning("email triage failed: %s", exc)
        return {"ran": True, "connected": False, "saved": saved, "error": str(exc)}


def run_research_queue() -> Dict[str, Any]:
    """Process queued research topics via web_search -> findings; clear queue."""
    from openjarvis.proactive.stores import ResearchStore
    store = ResearchStore()
    processed = 0
    for item in store.queue():
        summary = _web_search(item["topic"]) or f"(no results for {item['topic']})"
        store.add_finding(item["topic"], summary[:500], tag="Queue")
        store.mark_processed(item["id"])
        processed += 1
    return {"ran": True, "processed": processed}


def run_news() -> Dict[str, Any]:
    """Nightly news intelligence — top finding per category."""
    from openjarvis.proactive.stores import ResearchStore
    store = ResearchStore()
    added = 0
    for tag, query in NEWS_QUERIES:
        summary = _web_search(query)
        if summary:
            store.add_finding(query, summary[:500], tag=tag)
            added += 1
    return {"ran": True, "added": added}


def run_morning_briefing() -> Dict[str, Any]:
    """Compose the full briefing (base digest + Sprint 4 data) and persist it."""
    from openjarvis.speech.proactive import compose_full_briefing, compose_morning_digest
    base = ""
    try:
        # Best-effort weather/calendar/mail context for the base line.
        import httpx
        port = os.environ.get("JARVIS_PORT", "8000")
        b = f"http://127.0.0.1:{port}"
        weather = httpx.get(f"{b}/v1/weather", timeout=5).json().get("text", "")
        comms = httpx.get(f"{b}/v1/comms/recent", timeout=5).json()
        cal = httpx.get(f"{b}/v1/calendar/today", timeout=5).json()
        evs = cal.get("events", [])
        base = compose_morning_digest(
            weather_text=weather, event_count=len(evs),
            first_event=(evs[0].get("summary", "") if evs else ""),
            unread=comms.get("unread_count", 0),
        )
    except Exception:
        base = compose_morning_digest()
    full = compose_full_briefing(base)
    try:
        _BRIEFING_PATH.parent.mkdir(parents=True, exist_ok=True)
        _BRIEFING_PATH.write_text(f"# Morning Briefing\n\n{full}\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("briefing write failed: %s", exc)
    return {"ran": True, "briefing": full}


def run_weekly_summary() -> Dict[str, Any]:
    """Generate + store the week-in-review from local business + proactive data."""
    from openjarvis.business.store import BusinessStore
    from openjarvis.business.improvement_log import ImprovementLog
    from openjarvis.proactive.stores import AnomalyStore, WeeklySummaryStore
    snap = BusinessStore().snapshot()
    imp = ImprovementLog().weekly_counts()
    anomalies = len(AnomalyStore().recent(100))
    dt = _now_sgt()
    week_of = f"{dt.year}-W{dt.isocalendar().week:02d}"
    text = (
        f"This week: {snap['completed_this_week']} jobs completed, "
        f"{snap['pending_payment']} pending payment, {snap['active_jobs']} active jobs. "
        f"VANTA logged {imp['improvement']} improvements, {imp['bug_fix']} fixes, "
        f"{imp['research']} research items; {anomalies} anomalies tracked. "
        f"Next week: keep momentum."
    )
    WeeklySummaryStore().save(week_of, text)
    return {"ran": True, "week_of": week_of, "text": text}


# ── daemon scheduler ─────────────────────────────────────────────────────────
class ProactiveScheduler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_triage = 0.0
        self._last_daily: Dict[str, str] = {}   # job -> YYYY-MM-DD it last ran

    def _ran_today(self, job: str, dt: datetime) -> bool:
        return self._last_daily.get(job) == dt.date().isoformat()

    def _mark(self, job: str, dt: datetime) -> None:
        self._last_daily[job] = dt.date().isoformat()

    def _tick(self, now: Optional[datetime] = None) -> List[str]:
        """Run whichever jobs are due. Returns the names that ran (testable)."""
        dt = _now_sgt(now)
        ran: List[str] = []
        wall = time.time()
        # Every 30 minutes — email triage.
        if wall - self._last_triage >= 1800:
            self._last_triage = wall
            run_email_triage(); ran.append("email_triage")
        # 02:00 — research queue + news.
        if dt.hour == 2 and not self._ran_today("night", dt):
            self._mark("night", dt)
            run_research_queue(); run_news(); ran.append("night_research")
        # 08:00 — morning briefing.
        if dt.hour == 8 and not self._ran_today("briefing", dt):
            self._mark("briefing", dt)
            run_morning_briefing(); ran.append("morning_briefing")
        # Sunday 20:00 — weekly summary.
        if dt.weekday() == 6 and dt.hour == 20 and not self._ran_today("weekly", dt):
            self._mark("weekly", dt)
            run_weekly_summary(); ran.append("weekly_summary")
        return ran

    def _loop(self) -> None:  # pragma: no cover - timing loop
        logger.info("proactive scheduler online (SGT jobs).")
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.warning("proactive tick failed: %s", exc)
            self._stop.wait(60)

    def start(self) -> bool:
        if (os.environ.get("VANTA_SCHEDULER") or "").strip().lower() == "off":
            return False
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="vanta-proactive", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()


_SCHED = ProactiveScheduler()


def start_proactive_scheduler() -> bool:
    """Start the proactive scheduler daemon. Never raises into server startup."""
    try:
        return _SCHED.start()
    except Exception as exc:  # pragma: no cover
        logger.warning("could not start proactive scheduler: %s", exc)
        return False


__all__ = [
    "ProactiveScheduler", "start_proactive_scheduler",
    "run_email_triage", "run_research_queue", "run_news",
    "run_morning_briefing", "run_weekly_summary", "NEWS_QUERIES",
]
