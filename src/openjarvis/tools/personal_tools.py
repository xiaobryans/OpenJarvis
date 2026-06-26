"""Personal-life tools for Jarvis — real-data connectors exposed to the agent.

These wrap already-working connectors/services so the LLM can actually use them
in chat:

- ``current_weather``  — Singapore (or any place) weather via wttr.in (no key)
- ``calendar_today``   — today's Google Calendar events (real)
- ``gmail_important``  — recent unread Gmail messages (real)
- ``slack_recent``     — recent Slack activity (degrades gracefully on scope)

Every tool returns a real ``ToolResult``; failures are reported clearly
(``success=False`` with the reason) — never a silent success or fake data. Each
caps how much it reads so a tool call never pulls an entire inbox/calendar.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


# ---------------------------------------------------------------------------
# Weather — wttr.in, no API key required
# ---------------------------------------------------------------------------
@ToolRegistry.register("current_weather")
class WeatherTool(BaseTool):
    """Current weather + short forecast for a location (default: Singapore)."""

    tool_id = "current_weather"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="current_weather",
            description=(
                "Get current weather and today's forecast for a location using a "
                "free no-key service. Defaults to Singapore. Use for any weather "
                "question or the morning briefing."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City/place. Defaults to 'Singapore'.",
                    }
                },
                "required": [],
            },
            category="personal",
        )

    def execute(self, **params: Any) -> ToolResult:
        location = (params.get("location") or "Singapore").strip()
        try:
            loc = urllib.parse.quote(location)
            # Current line + today's hi/lo + condition.
            url = f"https://wttr.in/{loc}?format=%l:+%C,+%t+(feels+%f),+humidity+%h,+wind+%w"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=12) as r:
                now_line = r.read().decode("utf-8", "replace").strip()
            return ToolResult(
                tool_name="current_weather",
                content=now_line,
                success=True,
                metadata={"location": location, "source": "wttr.in"},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="current_weather",
                content=f"Weather lookup failed for {location!r}: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# Calendar — today's events (Google Calendar)
# ---------------------------------------------------------------------------
@ToolRegistry.register("calendar_today")
class CalendarTodayTool(BaseTool):
    """Today's Google Calendar events."""

    tool_id = "calendar_today"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="calendar_today",
            description=(
                "List the user's Google Calendar events for today (real data). "
                "Use for 'what's on my calendar / schedule today' and the morning "
                "briefing."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            category="personal",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            # Query ONLY the user's primary calendar — not the merged calendar
            # list — so auto-generated "Birthdays"/"Holidays"/contacts calendars
            # (e.g. "Aunt Maria's birthday") are excluded. These are Bryan's own
            # events.
            from openjarvis.connectors.gcalendar import (
                _DEFAULT_CREDENTIALS_PATH,
                _gcal_api_events_list,
            )
            from openjarvis.connectors.google_auth import call_with_refresh
            from openjarvis.connectors.oauth import load_tokens

            toks = load_tokens(_DEFAULT_CREDENTIALS_PATH)
            if not toks or not (toks.get("access_token") or toks.get("token")):
                return ToolResult(
                    tool_name="calendar_today",
                    content="Google Calendar is not connected. Complete the "
                    "Google OAuth flow to enable it.",
                    success=False,
                )
            now = datetime.now().astimezone()
            day = now.date()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_min = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            resp = call_with_refresh(
                _gcal_api_events_list, _DEFAULT_CREDENTIALS_PATH,
                "primary", time_min=time_min,
            )
            from datetime import date as _date

            events = []
            seen = set()
            for ev in resp.get("items", []):
                summary = ev.get("summary", "") or "(untitled event)"
                st = ev.get("start", {}) or {}
                # Parse the event's actual date directly — do NOT use a now()
                # fallback, or future all-day events (e.g. recurring birthdays
                # dated months ahead) wrongly count as "today".
                when = ""
                ev_date = None
                if st.get("dateTime"):
                    try:
                        dt = datetime.fromisoformat(st["dateTime"].replace("Z", "+00:00")).astimezone()
                        ev_date = dt.date()
                        when = dt.strftime("%I:%M %p").lstrip("0")
                    except Exception:
                        ev_date = None
                elif st.get("date"):
                    try:
                        ev_date = _date.fromisoformat(st["date"])
                        when = "all day"
                    except Exception:
                        ev_date = None
                if ev_date != day:  # only events actually on today
                    continue
                key = (summary.strip().lower(), when)
                if key in seen:
                    continue
                seen.add(key)
                events.append(f"- {summary}" + (f"  [{when}]" if when else ""))
                if len(events) >= 12:
                    break
            if not events:
                return ToolResult(
                    tool_name="calendar_today",
                    content="No events on your calendar today.",
                    success=True,
                    metadata={"count": 0, "calendar": "primary"},
                )
            return ToolResult(
                tool_name="calendar_today",
                content="Today's events (your calendar):\n" + "\n".join(events),
                success=True,
                metadata={"count": len(events), "calendar": "primary"},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="calendar_today",
                content=f"Calendar read failed: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# Gmail — recent unread / important
# ---------------------------------------------------------------------------
@ToolRegistry.register("gmail_important")
class GmailImportantTool(BaseTool):
    """Recent unread Gmail messages (subject + sender)."""

    tool_id = "gmail_important"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="gmail_important",
            description=(
                "Summarize the user's recent UNREAD Gmail messages (real data) — "
                "subject and sender only. Use for 'any important emails' and the "
                "morning briefing."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "max_messages": {
                        "type": "integer",
                        "description": "How many unread to summarize (default 5).",
                    }
                },
                "required": [],
            },
            category="personal",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            limit = int(params.get("max_messages") or 5)
        except (TypeError, ValueError):
            limit = 5
        limit = max(1, min(limit, 15))
        try:
            from openjarvis.connectors.gmail import GmailConnector

            gm = GmailConnector()
            if not gm.is_connected():
                return ToolResult(
                    tool_name="gmail_important",
                    content="Gmail is not connected. Complete the Google OAuth "
                    "flow to enable it.",
                    success=False,
                )
            rows = []
            for doc in gm.sync(query_extra="is:unread"):
                meta = getattr(doc, "metadata", {}) or {}
                subj = (getattr(doc, "title", "") or meta.get("subject", "")
                        or "(no subject)")
                sender = meta.get("from") or meta.get("sender") or ""
                rows.append(f"- {subj[:90]}" + (f"  — {sender[:60]}" if sender else ""))
                if len(rows) >= limit:
                    break
            if not rows:
                return ToolResult(
                    tool_name="gmail_important",
                    content="No unread emails.",
                    success=True,
                    metadata={"count": 0},
                )
            return ToolResult(
                tool_name="gmail_important",
                content=f"{len(rows)} unread email(s):\n" + "\n".join(rows),
                success=True,
                metadata={"count": len(rows)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="gmail_important",
                content=f"Gmail read failed: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# Slack — recent activity (graceful if the bot token lacks read scopes)
# ---------------------------------------------------------------------------
@ToolRegistry.register("slack_recent")
class SlackRecentTool(BaseTool):
    """Recent Slack messages from channels the bot can read."""

    tool_id = "slack_recent"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="slack_recent",
            description=(
                "Summarize recent Slack messages the bot can access (real data). "
                "Use for 'any important Slack messages' and the morning briefing."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            category="personal",
        )

    def _api(self, method: str, token: str, params: dict) -> dict:
        url = f"https://slack.com/api/{method}"
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def execute(self, **params: Any) -> ToolResult:
        import os

        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            return ToolResult(
                tool_name="slack_recent",
                content="Slack is not configured (no SLACK_BOT_TOKEN).",
                success=False,
            )
        try:
            auth = self._api("auth.test", token, {})
            if not auth.get("ok"):
                return ToolResult(
                    tool_name="slack_recent",
                    content=f"Slack auth failed: {auth.get('error')}",
                    success=False,
                )
            team = auth.get("team", "")
            convs = self._api(
                "conversations.list", token,
                {"types": "public_channel", "limit": 10, "exclude_archived": "true"},
            )
            if not convs.get("ok"):
                # Connectivity proven, but read scope missing — report honestly.
                return ToolResult(
                    tool_name="slack_recent",
                    content=(
                        f"Slack connected (team: {team}), but reading channels "
                        f"needs an extra scope: {convs.get('error')}. Add "
                        "'channels:read' + 'channels:history' to the bot token."
                    ),
                    success=False,
                    metadata={"team": team, "scope_error": convs.get("error")},
                )
            chans = convs.get("channels", [])[:5]
            lines = []
            for ch in chans:
                cid, cname = ch.get("id"), ch.get("name", "?")
                hist = self._api(
                    "conversations.history", token, {"channel": cid, "limit": 2}
                )
                if hist.get("ok"):
                    for m in hist.get("messages", [])[:2]:
                        txt = (m.get("text", "") or "").replace("\n", " ")[:80]
                        if txt:
                            lines.append(f"- #{cname}: {txt}")
            if not lines:
                return ToolResult(
                    tool_name="slack_recent",
                    content=f"Slack connected (team: {team}); no recent readable messages.",
                    success=True,
                    metadata={"team": team, "count": 0},
                )
            return ToolResult(
                tool_name="slack_recent",
                content=f"Recent Slack (team: {team}):\n" + "\n".join(lines[:8]),
                success=True,
                metadata={"team": team, "count": len(lines)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="slack_recent",
                content=f"Slack read failed: {exc}",
                success=False,
            )


def _notion_token() -> str:
    import os

    from openjarvis.core.env_loader import ensure_local_env_loaded

    ensure_local_env_loaded()
    return (os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_TOKEN") or "").strip()


@ToolRegistry.register("notion_search")
class NotionSearchTool(BaseTool):
    """Search the user's Notion pages (real data)."""

    tool_id = "notion_search"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="notion_search",
            description=(
                "List/search the user's Notion pages the Jarvis integration can "
                "access (real data). Optional 'query' filters by page title. Use "
                "to find a Notion page before reading it."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Filter by title (optional)."}
                },
                "required": [],
            },
            category="personal",
        )

    def execute(self, **params: Any) -> ToolResult:
        token = _notion_token()
        if not token:
            return ToolResult(
                tool_name="notion_search",
                content="Notion is not configured. Add NOTION_API_KEY to .env and "
                "share pages with the integration.",
                success=False,
            )
        q = (params.get("query") or "").strip().lower()
        try:
            from openjarvis.connectors.notion import (
                _extract_page_title,
                _notion_api_search,
            )

            resp = _notion_api_search(token)
            rows = []
            for page in resp.get("results", []):
                title = _extract_page_title(page) or "(untitled)"
                if q and q not in title.lower():
                    continue
                rows.append(f"- {title}  (id: {page.get('id','')})")
                if len(rows) >= 25:
                    break
            if not rows:
                return ToolResult(
                    tool_name="notion_search",
                    content=("No matching Notion pages." if q else
                             "No Notion pages shared with the integration yet. "
                             "Share pages with 'Jarvis' in Notion."),
                    success=True,
                    metadata={"count": 0},
                )
            return ToolResult(
                tool_name="notion_search",
                content=f"{len(rows)} Notion page(s):\n" + "\n".join(rows),
                success=True,
                metadata={"count": len(rows)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="notion_search",
                content=f"Notion search failed: {exc}",
                success=False,
            )


@ToolRegistry.register("notion_read")
class NotionReadTool(BaseTool):
    """Read a Notion page's content as markdown (real data)."""

    tool_id = "notion_read"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="notion_read",
            description=(
                "Read a Notion page's content (real data), rendered as markdown. "
                "Pass 'page_id' (from notion_search) or 'query' to find a page by "
                "title and read the first match."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Notion page id."},
                    "query": {"type": "string", "description": "Title to find + read."},
                },
                "required": [],
            },
            category="personal",
        )

    def execute(self, **params: Any) -> ToolResult:
        token = _notion_token()
        if not token:
            return ToolResult(
                tool_name="notion_read",
                content="Notion is not configured. Add NOTION_API_KEY to .env.",
                success=False,
            )
        page_id = (params.get("page_id") or "").strip()
        query = (params.get("query") or "").strip().lower()
        try:
            from openjarvis.connectors.notion import (
                _extract_page_title,
                _notion_api_get_blocks,
                _notion_api_search,
                _render_blocks_to_markdown,
            )

            title = ""
            if not page_id:
                if not query:
                    return ToolResult(
                        tool_name="notion_read",
                        content="Provide page_id or query.",
                        success=False,
                    )
                for page in _notion_api_search(token).get("results", []):
                    t = _extract_page_title(page) or ""
                    if query in t.lower():
                        page_id, title = page.get("id", ""), t
                        break
                if not page_id:
                    return ToolResult(
                        tool_name="notion_read",
                        content=f"No Notion page matching {query!r}.",
                        success=True,
                    )
            blocks = _notion_api_get_blocks(token, page_id)
            md = _render_blocks_to_markdown(blocks) or "(page is empty)"
            head = f"# {title}\n\n" if title else ""
            return ToolResult(
                tool_name="notion_read",
                content=(head + md)[:4000],
                success=True,
                metadata={"page_id": page_id},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="notion_read",
                content=f"Notion read failed: {exc}",
                success=False,
            )


@ToolRegistry.register("morning_briefing")
class MorningBriefingTool(BaseTool):
    """Generate Bryan's full morning briefing on demand (real data)."""

    tool_id = "morning_briefing"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="morning_briefing",
            description=(
                "Generate Bryan's morning briefing now: system/overnight health, "
                "today's calendar, important unread email, messages, date + "
                "Singapore weather, and top priorities. Use when he asks for his "
                "briefing / 'what's happening today'."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            category="personal",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            from openjarvis.jarvis_os.daily_ops import generate_morning_briefing

            text = generate_morning_briefing()
            return ToolResult(
                tool_name="morning_briefing", content=text, success=True
            )
        except Exception as exc:
            return ToolResult(
                tool_name="morning_briefing",
                content=f"Briefing generation failed: {exc}",
                success=False,
            )


__all__ = [
    "WeatherTool",
    "CalendarTodayTool",
    "GmailImportantTool",
    "SlackRecentTool",
    "MorningBriefingTool",
    "NotionSearchTool",
    "NotionReadTool",
]
