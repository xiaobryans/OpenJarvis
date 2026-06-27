"""Sprint 2 voice/text tools: financial snapshot (2C), web research (2D),
draft-and-send with confirmation (2E).

These wrap capabilities that already exist (web_search, gmail_send/slack_send)
and add the VANTA-specific behaviour (memory tagging, confirm-before-send).
Sends are NEVER performed automatically — the draft tool only prepares the
message and asks for confirmation; the actual send runs through the existing
approval-gated gmail_send / slack_send tools after Bryan says yes.
"""

from __future__ import annotations

from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


# ── 2C — financial snapshot (placeholder until Stripe connects) ──────────────
@ToolRegistry.register("financial_snapshot")
class FinancialSnapshotTool(BaseTool):
    tool_id = "financial_snapshot"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="financial_snapshot",
            description="Report revenue / spend / balance snapshot. "
                        "Use for 'financial snapshot', 'what's my balance', 'how much did I spend'.",
            parameters={"type": "object", "properties": {}, "required": []},
            category="business",
        )

    def execute(self, **_p: Any) -> ToolResult:
        msg = ("Stripe and your bank aren't connected yet, so I can't pull live "
               "numbers. Once OMNIX billing goes live on Stripe, this will show "
               "MRR, revenue this week, balance and runway.")
        return ToolResult(tool_name=self.tool_id, content=msg, success=True,
                          metadata={"stripe_connected": False, "ready_for": ["mrr", "revenue", "balance", "runway"]})


# ── 2D — web research by voice (wraps web_search + saves to memory) ──────────
@ToolRegistry.register("web_research")
class WebResearchTool(BaseTool):
    tool_id = "web_research"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="web_research",
            description="Research a topic on the web and save the findings to memory with a topic tag. "
                        "Use for 'research X', 'find me X', 'look up X'.",
            parameters={
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
            category="research",
        )

    def execute(self, **p: Any) -> ToolResult:
        topic = (p.get("topic") or "").strip()
        if not topic:
            return ToolResult(tool_name=self.tool_id, content="What should I research?", success=False, metadata={})
        # Reuse the existing web_search worker.
        from openjarvis.core.registry import ToolRegistry as TR
        findings = ""
        if "web_search" in TR.keys():
            try:
                r = TR.get("web_search")().execute(query=topic)
                findings = getattr(r, "content", "") or ""
            except Exception as exc:
                findings = f"(search failed: {exc})"
        # Save to memory tagged with the topic (best-effort).
        try:
            from openjarvis.speech import voice_bus
            backend = voice_bus._MEM.get("backend")
            if backend is not None and findings:
                backend.store(findings, source="research", metadata={"topic": topic, "kind": "research"})
        except Exception:
            pass
        content = findings or f"Couldn't find much on {topic}."
        return ToolResult(tool_name=self.tool_id, content=content, success=bool(findings),
                          metadata={"topic": topic, "saved_to_memory": bool(findings)})


# ── 2E — draft & send (prepare + confirm; never auto-send) ───────────────────
def confirmation_line(channel: str, recipient: str, body: str) -> str:
    summary = body if len(body) <= 80 else body[:77] + "…"
    return f'I\'ll send "{summary}" to {recipient} on {channel}. Confirm?'


@ToolRegistry.register("draft_message")
class DraftMessageTool(BaseTool):
    """Prepare an email/Slack message and ask for confirmation (2E). Does NOT send."""

    tool_id = "draft_message"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="draft_message",
            description="Draft an email or Slack message and ask Bryan to confirm before sending. "
                        "Returns a confirmation prompt; the actual send runs via gmail_send/slack_send "
                        "ONLY after Bryan confirms. Use for 'email X saying Y', 'Slack vanta-hq saying Y'.",
            parameters={
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["email", "slack"]},
                    "recipient": {"type": "string", "description": "Email address / name, or Slack channel."},
                    "body": {"type": "string"},
                },
                "required": ["channel", "recipient", "body"],
            },
            category="communication",
        )

    def execute(self, **p: Any) -> ToolResult:
        channel = (p.get("channel") or "").lower().strip()
        recipient = (p.get("recipient") or "").strip()
        body = (p.get("body") or "").strip()
        if channel not in ("email", "slack") or not recipient or not body:
            return ToolResult(tool_name=self.tool_id, content="Need channel, recipient and message.", success=False, metadata={})
        send_tool = "gmail_send" if channel == "email" else "slack_send"
        return ToolResult(
            tool_name=self.tool_id,
            content=confirmation_line(channel, recipient, body),
            success=True,
            metadata={
                "requires_confirmation": True,
                "send_tool": send_tool,
                "channel": channel, "recipient": recipient, "body": body,
                "real_send_allowed": False,
            },
        )


__all__ = ["FinancialSnapshotTool", "WebResearchTool", "DraftMessageTool", "confirmation_line"]
