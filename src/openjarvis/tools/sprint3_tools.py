"""Sprint 3 tools: smart reminders (3F) + self-improvement log access.

Voice/text reachable via the orchestrator. Stores are local SQLite (see
openjarvis.business.reminders / improvement_log).
"""

from __future__ import annotations

import time
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _reminders():
    from openjarvis.business.reminders import ReminderStore
    return ReminderStore()


def _improvements():
    from openjarvis.business.improvement_log import ImprovementLog
    return ImprovementLog()


def _fmt_due(due_at) -> str:
    if not due_at:
        return "no time set"
    try:
        return time.strftime("%a %d %b %H:%M", time.localtime(due_at))
    except Exception:
        return "soon"


@ToolRegistry.register("reminder")
class ReminderTool(BaseTool):
    """Set and check reminders (3F)."""

    tool_id = "reminder"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="reminder",
            description="Set or check reminders. action=set (with 'text' and 'when' like 'tomorrow', "
                        "'in 2 hours'), due (list due now), pending (list all open).",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["set", "due", "pending"]},
                    "text": {"type": "string"},
                    "when": {"type": "string"},
                },
                "required": ["action"],
            },
            category="productivity",
        )

    def execute(self, **p: Any) -> ToolResult:
        s = _reminders()
        action = (p.get("action") or "pending").lower()
        if action == "set":
            text = (p.get("text") or "").strip()
            if not text:
                return ToolResult(tool_name=self.tool_id, content="What should I remind you about?", success=False, metadata={})
            r = s.add(text, when=p.get("when", ""))
            when = _fmt_due(r["due_at"])
            return ToolResult(tool_name=self.tool_id, content=f"Reminder set: {text} ({when}).", success=True, metadata=r)
        rows = s.due() if action == "due" else s.pending()
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="No reminders." if action == "pending" else "Nothing due.", success=True, metadata={})
        lines = [f"- {r['text']} ({_fmt_due(r['due_at'])})" for r in rows]
        return ToolResult(tool_name=self.tool_id, content="\n".join(lines), success=True, metadata={"count": len(rows)})


@ToolRegistry.register("improvement_log")
class ImprovementLogTool(BaseTool):
    """Record + report VANTA's own improvements / fixes / research / pending."""

    tool_id = "improvement_log"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="improvement_log",
            description="VANTA's self-improvement log. action=log (category+description), "
                        "week ('what did you improve this week'), changelog ('show change log'), "
                        "pending ('what's pending'). categories: improvement, bug_fix, research, pending.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["log", "week", "changelog", "pending"]},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "outcome": {"type": "string"},
                    "initiator": {"type": "string"},
                },
                "required": ["action"],
            },
            category="system",
        )

    def execute(self, **p: Any) -> ToolResult:
        log = _improvements()
        action = (p.get("action") or "week").lower()
        if action == "log":
            e = log.add(p.get("category", "improvement"), p.get("description", ""),
                        outcome=p.get("outcome", ""), initiator=p.get("initiator", "vanta"))
            return ToolResult(tool_name=self.tool_id, content=f"Logged ({e['category']}): {e['description']}", success=True, metadata=e)
        if action == "week":
            counts = log.weekly_counts()
            txt = (f"This week: {counts['improvement']} improvements, {counts['bug_fix']} bugs fixed, "
                   f"{counts['research']} research items, {counts['pending']} pending.")
            return ToolResult(tool_name=self.tool_id, content=txt, success=True, metadata=counts)
        if action == "pending":
            rows = log.pending()
            if not rows:
                return ToolResult(tool_name=self.tool_id, content="Nothing pending.", success=True, metadata={})
            return ToolResult(tool_name=self.tool_id, content="\n".join(f"- {r['description']}" for r in rows), success=True, metadata={"count": len(rows)})
        rows = log.recent(20)
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="Change log is empty.", success=True, metadata={})
        return ToolResult(tool_name=self.tool_id, content="\n".join(f"- [{r['category']}] {r['description']}" for r in rows), success=True, metadata={"count": len(rows)})


__all__ = ["ReminderTool", "ImprovementLogTool"]
