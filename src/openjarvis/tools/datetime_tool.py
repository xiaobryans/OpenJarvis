"""Current date/time tool — answers "what time / day / date is it" from the
system clock.

This is a foundational real-time-awareness capability. Large language models
have no inherent access to the current moment, so without a tool like this the
model is forced to guess or deflect ("I can't access the current time"). This
tool reads the host's system clock directly via :mod:`datetime` /
:mod:`zoneinfo`, so it:

- works fully offline (no API call that can fail),
- never raises to the caller (always returns a populated ``ToolResult``),
- reports local time, date, weekday, and the resolved timezone.

It is intentionally argument-light: an optional ``timezone`` lets the model ask
for a specific zone (e.g. ``"UTC"``, ``"America/New_York"``); omitting it uses
the host's local timezone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def current_datetime_snapshot(tz_name: str = "") -> dict[str, str]:
    """Return a structured snapshot of the current date/time.

    When *tz_name* is provided and resolvable via :mod:`zoneinfo`, the snapshot
    is rendered in that zone; otherwise the host's local timezone is used. This
    helper is deliberately exception-safe — an unknown timezone falls back to
    local time rather than failing.
    """
    now: datetime
    resolved_tz = ""
    if tz_name:
        try:
            from zoneinfo import ZoneInfo

            if tz_name.upper() == "UTC":
                now = datetime.now(timezone.utc)
                resolved_tz = "UTC"
            else:
                zi = ZoneInfo(tz_name)
                now = datetime.now(zi)
                resolved_tz = tz_name
        except Exception:
            now = datetime.now().astimezone()
            resolved_tz = ""  # fell back to local
    else:
        now = datetime.now().astimezone()

    if not resolved_tz:
        # Render the host's local zone name/abbreviation + UTC offset.
        resolved_tz = now.tzname() or "local"

    offset = now.strftime("%z") or ""
    if offset and len(offset) == 5:
        offset = f"{offset[:3]}:{offset[3:]}"  # +0800 -> +08:00

    return {
        "iso": now.isoformat(),
        "time_12h": now.strftime("%I:%M %p").lstrip("0"),
        "time_24h": now.strftime("%H:%M"),
        "date": now.strftime("%B %d, %Y"),
        "weekday": now.strftime("%A"),
        "timezone": resolved_tz,
        "utc_offset": offset,
    }


def format_datetime_reply(snap: dict[str, str]) -> str:
    """Render a snapshot as a single natural-language line."""
    tz = (snap.get("timezone", "") or "").strip()
    offset = (snap.get("utc_offset", "") or "").strip()
    # Build a clean timezone label without doubling the offset. Named zones
    # ("America/New_York", "UTC") show name + offset; offset-only zone names
    # ("+08") show just the UTC offset.
    if tz and tz.upper() == "UTC":
        tz_str = "UTC"
    elif tz and tz[0] not in "+-":
        tz_str = f"{tz}, UTC{offset}" if offset else tz
    elif offset:
        tz_str = f"UTC{offset}"
    else:
        tz_str = tz
    base = f"It is {snap['time_12h']} on {snap['weekday']}, {snap['date']}"
    return f"{base} ({tz_str})." if tz_str else f"{base}."


@ToolRegistry.register("current_time")
class CurrentDateTimeTool(BaseTool):
    """Report the current local date, time, weekday, and timezone.

    Use this whenever the user asks what time/day/date it is, or whenever an
    action needs the current moment (scheduling, "today", "now", relative
    dates). Reads the system clock — always available, never network-bound.
    """

    tool_id = "current_time"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="current_time",
            description=(
                "Get the current real-world date and time from the system "
                "clock: local time, today's date, day of the week, and "
                "timezone. Use for any 'what time/day/date is it', 'now', or "
                "'today' question. Optionally pass a timezone (e.g. 'UTC', "
                "'America/New_York')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": (
                            "Optional IANA timezone name (e.g. 'UTC', "
                            "'America/New_York'). Omit for local time."
                        ),
                    },
                },
                "required": [],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        tz_name = (params.get("timezone") or "").strip()
        try:
            snap = current_datetime_snapshot(tz_name)
            return ToolResult(
                tool_name="current_time",
                content=format_datetime_reply(snap),
                success=True,
                metadata=snap,
            )
        except Exception as exc:  # pragma: no cover - defensive, clock is local
            # Last-resort fallback: even if formatting fails, return raw now().
            return ToolResult(
                tool_name="current_time",
                content=f"The current system time is {datetime.now().isoformat()}.",
                success=True,
                metadata={"error": str(exc)},
            )


__all__ = [
    "CurrentDateTimeTool",
    "current_datetime_snapshot",
    "format_datetime_reply",
]
