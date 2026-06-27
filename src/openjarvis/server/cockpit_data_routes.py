"""Live read-only data endpoints for the VANTA cockpit panels.

These feed the Neural Command Center panels with *real* data, polled on the
client (Task A intervals). All endpoints are read-only and never raise — on any
error they return ``ok: false`` (and ``connected: false`` where relevant) so the
UI degrades to an honest "unavailable" state rather than fabricating values.

  - GET /v1/weather            — live weather (default Singapore), no API key
  - GET /v1/comms/recent       — Gmail unread count + recent message summaries
  - GET /v1/calendar/today     — today's Google Calendar events (SGT) + next up
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import quote

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# Singapore is UTC+8 with no DST.
_SGT = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# Weather — live via the no-key current_weather tool (wttr.in).
# ---------------------------------------------------------------------------
@router.get("/v1/weather")
async def weather(location: str = "Singapore") -> Dict[str, Any]:
    """Return current weather for *location* (default Singapore)."""
    try:
        from openjarvis.tools.personal_tools import WeatherTool

        res = WeatherTool().execute(location=location)
        return {
            "ok": bool(res.success),
            "location": location,
            "text": res.content,
            "source": (res.metadata or {}).get("source", "wttr.in"),
        }
    except Exception as exc:  # never break the UI
        logger.warning("weather endpoint failed: %s", exc)
        return {"ok": False, "location": location, "text": "", "source": None,
                "error": str(exc)}


# ---------------------------------------------------------------------------
# Communications — Gmail unread count + recent message summaries.
# ---------------------------------------------------------------------------
@router.get("/v1/comms/recent")
async def comms_recent(limit: int = 6) -> Dict[str, Any]:
    """Return Gmail unread count and recent message summaries (from/subject/date).

    Never exposes message bodies — only header summaries for the panel.
    """
    limit = max(1, min(limit, 20))
    try:
        from openjarvis.connectors.gmail import (
            GmailConnector,
            _call_with_refresh,
            _extract_header,
            _gmail_api_get_message,
            _gmail_api_list_messages,
        )

        conn = GmailConnector()
        if not conn.is_connected():
            return {"ok": True, "connected": False, "unread_count": 0,
                    "messages": []}
        cred = conn._credentials_path

        # Unread inbox count (estimate from messages.list).
        unread_resp = _call_with_refresh(
            _gmail_api_list_messages, cred, query="is:unread in:inbox"
        )
        unread_count = int(unread_resp.get("resultSizeEstimate", 0) or 0)

        # Recent inbox messages (most recent first).
        recent_resp = _call_with_refresh(
            _gmail_api_list_messages, cred, query="in:inbox"
        )
        stubs: List[Dict[str, Any]] = (recent_resp.get("messages") or [])[:limit]

        messages: List[Dict[str, Any]] = []
        for stub in stubs:
            mid = stub.get("id", "")
            if not mid:
                continue
            try:
                msg = _call_with_refresh(_gmail_api_get_message, cred, mid)
            except Exception:
                continue
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            labels = msg.get("labelIds", [])
            messages.append({
                "from": _extract_header(headers, "From"),
                "subject": _extract_header(headers, "Subject") or "(no subject)",
                "date": _extract_header(headers, "Date"),
                "unread": "UNREAD" in labels,
                "snippet": (msg.get("snippet") or "")[:120],
            })
        return {"ok": True, "connected": True, "unread_count": unread_count,
                "messages": messages}
    except Exception as exc:
        logger.warning("comms/recent endpoint failed: %s", exc)
        return {"ok": False, "connected": False, "unread_count": 0,
                "messages": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Calendar — today's events (SGT) + next upcoming.
# ---------------------------------------------------------------------------
def _fmt_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    start = ev.get("start", {})
    end = ev.get("end", {})
    return {
        "id": ev.get("id"),
        "summary": ev.get("summary", "(no title)"),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "all_day": "date" in start and "dateTime" not in start,
        "location": ev.get("location"),
    }


@router.get("/v1/calendar/today")
async def calendar_today() -> Dict[str, Any]:
    """Return today's primary-calendar events (Singapore time) + next upcoming."""
    try:
        from openjarvis.connectors.gcalendar import GCalendarConnector
        from openjarvis.tools.action_tools import _gcal_call

        conn = GCalendarConnector()
        if not conn.is_connected():
            return {"ok": True, "connected": False, "date": None,
                    "events": [], "next_upcoming": None}

        now_sgt = datetime.now(_SGT)
        day_start = now_sgt.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        # URL-encode the RFC3339 bounds: the '+' in the +08:00 offset would
        # otherwise be decoded as a space and the API rejects it (400).
        params = (
            f"?singleEvents=true&orderBy=startTime"
            f"&timeMin={quote(day_start.isoformat())}"
            f"&timeMax={quote(day_end.isoformat())}"
            f"&maxResults=20"
        )
        data = _gcal_call("GET", f"/calendars/primary/events{params}")
        events = [_fmt_event(ev) for ev in data.get("items", [])]

        # Next upcoming event today that hasn't started yet.
        next_upcoming = None
        for ev in events:
            start = ev.get("start")
            if start and not ev.get("all_day"):
                try:
                    when = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    if when >= now_sgt:
                        next_upcoming = ev
                        break
                except ValueError:
                    continue
        return {"ok": True, "connected": True,
                "date": day_start.date().isoformat(), "events": events,
                "next_upcoming": next_upcoming}
    except Exception as exc:
        logger.warning("calendar/today endpoint failed: %s", exc)
        return {"ok": False, "connected": False, "date": None,
                "events": [], "next_upcoming": None, "error": str(exc)}
