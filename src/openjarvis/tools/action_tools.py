"""Action tools — VANTA acts in the world (send/create/delete), with a safety gate.

Real side-effecting actions wired for chat + the orchestrator:
  - slack_send        — post to a Slack channel (reversible -> auto)
  - calendar_create   — create a Google Calendar event (reversible -> auto)
  - calendar_delete   — delete an event (IRREVERSIBLE -> double-confirm)
  - gmail_send        — send an email (known contact -> auto; new contact ->
                        double-confirm)

Action policy:
  AUTO-EXECUTE  reversible / known-contact actions immediately.
  DOUBLE-CONFIRM irreversible / unknown-contact actions: the tool returns
  "CONFIRMATION REQUIRED: <exact action>" and does NOT act until called again
  with confirm=true (the user's explicit "yes" makes the model re-call it).
File/shell/git actions use the existing file_write / shell_exec / git tools.
"""

from __future__ import annotations

import base64
import json
import os
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_KNOWN_CONTACTS = Path.home() / ".openjarvis" / "known_contacts.json"


def _known_contacts() -> set[str]:
    try:
        if _KNOWN_CONTACTS.exists():
            return {e.lower() for e in json.loads(_KNOWN_CONTACTS.read_text())}
    except Exception:
        pass
    # Seed with Bryan's own address so self-sends are always "known".
    return {"xiaobryans@gmail.com"}


def _add_known(email: str) -> None:
    try:
        cur = _known_contacts()
        cur.add(email.lower())
        _KNOWN_CONTACTS.parent.mkdir(parents=True, exist_ok=True)
        _KNOWN_CONTACTS.write_text(json.dumps(sorted(cur), indent=2))
    except Exception:
        pass


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "y", "confirm")


# ---------------------------------------------------------------------------
# Slack — send (reversible -> auto)
# ---------------------------------------------------------------------------
@ToolRegistry.register("slack_send")
class SlackSendTool(BaseTool):
    tool_id = "slack_send"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="slack_send",
            description=(
                "Send a Slack message to a channel (e.g. vanta-hq, vanta-alerts, "
                "vanta-logs). Auto-executes (reversible). Use when Bryan says "
                "'send a message to <channel> saying <text>'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name (no #)."},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
            category="action",
        )

    def execute(self, **p: Any) -> ToolResult:
        channel = (p.get("channel") or "").lstrip("#").strip()
        text = (p.get("text") or "").strip()
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not (channel and text):
            return ToolResult("slack_send", "Need channel and text.", False)
        if not token:
            return ToolResult("slack_send", "Slack not configured.", False)
        try:
            with httpx.Client(timeout=15) as c:
                # Resolve channel name -> id (bot must be a member).
                lst = c.post("https://slack.com/api/conversations.list",
                             headers={"Authorization": f"Bearer {token}"},
                             data={"types": "public_channel", "limit": 200,
                                   "exclude_archived": "true"}).json()
                cid = next((ch["id"] for ch in lst.get("channels", [])
                            if ch.get("name") == channel and ch.get("is_member")), "")
                if not cid:
                    return ToolResult("slack_send",
                                      f"VANTA isn't in #{channel} (or it doesn't "
                                      "exist). Invite it: /invite @vanta", False)
                r = c.post("https://slack.com/api/chat.postMessage",
                           headers={"Authorization": f"Bearer {token}"},
                           data={"channel": cid, "text": text}).json()
            if not r.get("ok"):
                return ToolResult("slack_send", f"Slack error: {r.get('error')}", False)
            return ToolResult("slack_send", f"Sent to #{channel}: {text}", True,
                              metadata={"channel": channel, "ts": r.get("ts")})
        except Exception as exc:
            return ToolResult("slack_send", f"Slack send failed: {exc}", False)


# ---------------------------------------------------------------------------
# Calendar — create (auto) / delete (confirm)
# ---------------------------------------------------------------------------
def _gcal_call(method: str, path: str, body: dict | None = None) -> dict:
    from openjarvis.connectors.gcalendar import _DEFAULT_CREDENTIALS_PATH
    from openjarvis.connectors.google_auth import call_with_refresh

    def _do(token: str) -> dict:
        with httpx.Client(timeout=20) as c:
            r = c.request(
                method, f"https://www.googleapis.com/calendar/v3{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
            # raise_for_status() raises httpx.HTTPStatusError so call_with_refresh
            # can catch a 401 and refresh+retry with a new access token.
            r.raise_for_status()
            return r.json() if r.content else {}

    return call_with_refresh(_do, _DEFAULT_CREDENTIALS_PATH)


@ToolRegistry.register("calendar_create")
class CalendarCreateTool(BaseTool):
    tool_id = "calendar_create"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="calendar_create",
            description=(
                "Create a Google Calendar event (auto-executes; reversible). "
                "Provide summary and ISO start/end (e.g. 2026-06-28T15:00:00+08:00)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "start": {"type": "string", "description": "ISO datetime"},
                    "end": {"type": "string", "description": "ISO datetime"},
                    "description": {"type": "string"},
                },
                "required": ["summary", "start", "end"],
            },
            category="action",
        )

    def execute(self, **p: Any) -> ToolResult:
        try:
            body = {
                "summary": p.get("summary", ""),
                "description": p.get("description", ""),
                "start": {"dateTime": p["start"]},
                "end": {"dateTime": p["end"]},
            }
            ev = _gcal_call("POST", "/calendars/primary/events", body)
            return ToolResult("calendar_create",
                              f"Created '{ev.get('summary')}' ({ev.get('id')}).",
                              True, metadata={"event_id": ev.get("id")})
        except Exception as exc:
            return ToolResult("calendar_create", f"Create failed: {exc}", False)


@ToolRegistry.register("calendar_delete")
class CalendarDeleteTool(BaseTool):
    tool_id = "calendar_delete"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="calendar_delete",
            description=(
                "Delete a Google Calendar event by id. IRREVERSIBLE — requires "
                "confirm=true (ask Bryan to confirm first)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "confirm": {"type": "boolean", "description": "Must be true to delete."},
                },
                "required": ["event_id"],
            },
            category="action",
        )

    def execute(self, **p: Any) -> ToolResult:
        eid = p.get("event_id", "")
        if not _truthy(p.get("confirm")):
            return ToolResult(
                "calendar_delete",
                f"CONFIRMATION REQUIRED: permanently delete calendar event "
                f"{eid}. Reply 'yes' to proceed.", True,
                metadata={"needs_confirmation": True})
        try:
            _gcal_call("DELETE", f"/calendars/primary/events/{eid}")
            return ToolResult("calendar_delete", f"Deleted event {eid}.", True)
        except Exception as exc:
            return ToolResult("calendar_delete", f"Delete failed: {exc}", False)


# ---------------------------------------------------------------------------
# Gmail — send (known contact -> auto; new contact -> confirm)
# ---------------------------------------------------------------------------
@ToolRegistry.register("gmail_send")
class GmailSendTool(BaseTool):
    tool_id = "gmail_send"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="gmail_send",
            description=(
                "Send an email from Bryan's Gmail. Known contacts auto-send; a "
                "NEW recipient requires confirm=true (ask Bryan to confirm first)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["to", "subject", "body"],
            },
            category="action",
        )

    def execute(self, **p: Any) -> ToolResult:
        to = (p.get("to") or "").strip()
        subject = p.get("subject", "")
        body = p.get("body", "")
        if not to:
            return ToolResult("gmail_send", "Need a recipient.", False)
        known = to.lower() in _known_contacts()
        if not known and not _truthy(p.get("confirm")):
            return ToolResult(
                "gmail_send",
                f"CONFIRMATION REQUIRED: send email to NEW contact {to} — "
                f"subject '{subject}'. Reply 'yes' to send.", True,
                metadata={"needs_confirmation": True})
        try:
            from openjarvis.connectors.gcalendar import _DEFAULT_CREDENTIALS_PATH
            from openjarvis.connectors.google_auth import call_with_refresh

            msg = MIMEText(body)
            msg["to"] = to
            msg["subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

            def _do(token: str) -> dict:
                with httpx.Client(timeout=20) as c:
                    r = c.post(
                        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"raw": raw},
                    )
                    r.raise_for_status()  # 401 -> call_with_refresh refreshes+retries
                    return r.json()

            res = call_with_refresh(_do, _DEFAULT_CREDENTIALS_PATH)
            _add_known(to)
            return ToolResult("gmail_send", f"Email sent to {to} (id {res.get('id')}).",
                              True, metadata={"id": res.get("id")})
        except Exception as exc:
            return ToolResult("gmail_send", f"Send failed: {exc}", False)


__all__ = ["SlackSendTool", "CalendarCreateTool", "CalendarDeleteTool", "GmailSendTool"]
