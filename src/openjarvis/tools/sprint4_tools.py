"""Sprint 4 proactive-intelligence tools (voice + text via the orchestrator)."""

from __future__ import annotations

from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("tasks")
class TasksTool(BaseTool):
    """Capture / list / complete proactively-captured tasks (4F)."""

    tool_id = "tasks"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="tasks",
            description="Manage tasks. action=capture (auto-extract 'I need to…' etc. from text), "
                        "pending (list with urgency), done (mark complete). "
                        "Use for 'what tasks do I have', 'mark X as done'.",
            parameters={"type": "object", "properties": {
                "action": {"type": "string", "enum": ["capture", "pending", "done"]},
                "text": {"type": "string"},
            }, "required": ["action"]},
            category="productivity",
        )

    def execute(self, **p: Any) -> ToolResult:
        from openjarvis.proactive.stores import TaskStore
        s = TaskStore()
        action = (p.get("action") or "pending").lower()
        if action == "capture":
            got = s.capture_from_text(p.get("text", ""))
            return ToolResult(tool_name=self.tool_id, content=f"Captured {len(got)} task(s).", success=True, metadata={"tasks": got})
        if action == "done":
            ok = s.complete(p.get("text", ""))
            return ToolResult(tool_name=self.tool_id, content=("Marked done." if ok else "No matching task."), success=ok, metadata={})
        rows = s.pending()
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="No pending tasks.", success=True, metadata={})
        lines = [f"[{r['urgency']}] {r['text']}" for r in rows]
        return ToolResult(tool_name=self.tool_id, content="\n".join(lines), success=True, metadata={"count": len(rows)})


@ToolRegistry.register("research_queue")
class ResearchQueueTool(BaseTool):
    """Add to / view the overnight research queue (4G) + overnight findings (4C)."""

    tool_id = "research_queue"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="research_queue",
            description="Overnight research. action=add (queue a topic), queue (list pending), "
                        "overnight (what was found overnight). Use for 'add X to research', "
                        "'what's in my research queue', 'what did you find overnight'.",
            parameters={"type": "object", "properties": {
                "action": {"type": "string", "enum": ["add", "queue", "overnight"]},
                "topic": {"type": "string"},
            }, "required": ["action"]},
            category="research",
        )

    def execute(self, **p: Any) -> ToolResult:
        from openjarvis.proactive.stores import ResearchStore
        s = ResearchStore()
        action = (p.get("action") or "queue").lower()
        if action == "add":
            r = s.enqueue(p.get("topic", ""))
            return ToolResult(tool_name=self.tool_id, content=f"Added to overnight research: {r['topic']}.", success=True, metadata=r)
        if action == "overnight":
            rows = s.overnight()
            if not rows:
                return ToolResult(tool_name=self.tool_id, content="Nothing from overnight yet.", success=True, metadata={})
            lines = [f"[{r['tag']}] {r['topic']}: {r['summary'][:80]}" for r in rows[:3]]
            return ToolResult(tool_name=self.tool_id, content="Top overnight findings:\n" + "\n".join(lines), success=True, metadata={"count": len(rows)})
        rows = s.queue()
        return ToolResult(tool_name=self.tool_id, content=("Queue: " + ", ".join(r["topic"] for r in rows)) if rows else "Research queue is empty.", success=True, metadata={"count": len(rows)})


@ToolRegistry.register("anomalies")
class AnomaliesTool(BaseTool):
    tool_id = "anomalies"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="anomalies",
            description="Report detected anomalies (financial/communication/system) (4B). Use for 'any anomalies'.",
            parameters={"type": "object", "properties": {}, "required": []},
            category="system",
        )

    def execute(self, **_p: Any) -> ToolResult:
        from openjarvis.proactive.stores import AnomalyStore
        rows = AnomalyStore().recent()
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="No anomalies detected.", success=True, metadata={})
        lines = [f"[{r['severity']}] {r['kind']}: {r['description']}" for r in rows[:5]]
        return ToolResult(tool_name=self.tool_id, content="\n".join(lines), success=True, metadata={"count": len(rows)})


@ToolRegistry.register("relationship_checkups")
class RelationshipCheckupsTool(BaseTool):
    tool_id = "relationship_checkups"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="relationship_checkups",
            description="Who Bryan should check in with, with last-known context (4E). Use for 'who should I check in with'.",
            parameters={"type": "object", "properties": {}, "required": []},
            category="personal",
        )

    def execute(self, **_p: Any) -> ToolResult:
        from openjarvis.proactive.stores import RelationshipStore
        rows = RelationshipStore().checkups()
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="You're up to date with everyone.", success=True, metadata={})
        return ToolResult(tool_name=self.tool_id, content="\n".join(r["line"] for r in rows[:5]), success=True, metadata={"count": len(rows)})


@ToolRegistry.register("email_triage")
class EmailTriageTool(BaseTool):
    tool_id = "email_triage"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="email_triage",
            description="Urgent/important emails only (noise filtered) (4A). Use for 'any urgent emails'.",
            parameters={"type": "object", "properties": {}, "required": []},
            category="communication",
        )

    def execute(self, **_p: Any) -> ToolResult:
        from openjarvis.proactive.stores import EmailTriageStore
        rows = EmailTriageStore().actionable()
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="No urgent or important emails right now.", success=True, metadata={})
        lines = [f"[{r['category']}] {r['subject']}" for r in rows[:5]]
        return ToolResult(tool_name=self.tool_id, content=f"{len(rows)} need attention:\n" + "\n".join(lines), success=True, metadata={"count": len(rows)})


@ToolRegistry.register("week_in_review")
class WeekInReviewTool(BaseTool):
    tool_id = "week_in_review"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="week_in_review",
            description="Latest weekly summary (4D). Use for 'week in review'.",
            parameters={"type": "object", "properties": {}, "required": []},
            category="business",
        )

    def execute(self, **_p: Any) -> ToolResult:
        from openjarvis.proactive.stores import WeeklySummaryStore
        s = WeeklySummaryStore().latest()
        if not s:
            return ToolResult(tool_name=self.tool_id, content="No weekly summary generated yet (runs Sunday 8pm).", success=True, metadata={})
        return ToolResult(tool_name=self.tool_id, content=s["text"], success=True, metadata={"week_of": s["week_of"]})


@ToolRegistry.register("patterns")
class PatternsTool(BaseTool):
    tool_id = "patterns"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="patterns",
            description="Bryan's behaviour patterns/insights (4H). Use for 'what are my patterns'.",
            parameters={"type": "object", "properties": {}, "required": []},
            category="personal",
        )

    def execute(self, **_p: Any) -> ToolResult:
        from openjarvis.proactive.stores import PatternStore
        i = PatternStore().insights()
        if not i["sessions"]:
            return ToolResult(tool_name=self.tool_id, content="Not enough data yet to spot patterns.", success=True, metadata=i)
        txt = (f"{i['sessions']} sessions tracked. Most active around {i['most_active_hour']}:00, "
               f"avg {i['avg_minutes']} min, {i['late_nights']} late nights.")
        return ToolResult(tool_name=self.tool_id, content=txt, success=True, metadata=i)


__all__ = ["TasksTool", "ResearchQueueTool", "AnomaliesTool", "RelationshipCheckupsTool",
           "EmailTriageTool", "WeekInReviewTool", "PatternsTool"]
