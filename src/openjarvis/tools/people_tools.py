"""People awareness, memory recall and milestone celebrations (2H / 2J / 2I).

- people_remember: save a fact about family/partner/anyone to memory, tagged
  with the person, so VANTA can surface it meaningfully later (2H).
- memory_recall: "what do you remember about X" voice/text memory search (2J).
- milestone: deliver a personal, non-generic acknowledgement for a milestone,
  referencing Bryan's journey (2I / Milestone Celebrations).
"""

from __future__ import annotations

from typing import Any, Dict, List

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _memory_backend():
    try:
        from openjarvis.speech import voice_bus
        return voice_bus._MEM.get("backend")
    except Exception:
        return None


# ── 2H — people / relationship context ───────────────────────────────────────
@ToolRegistry.register("people_remember")
class PeopleRememberTool(BaseTool):
    tool_id = "people_remember"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="people_remember",
            description="Save context about a person (family, partner, friend, client) to memory so "
                        "VANTA can recall it later. Call automatically when Bryan mentions someone in his life.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Who this is about, e.g. 'brother', 'partner', 'mum'."},
                    "fact": {"type": "string", "description": "The context to remember."},
                },
                "required": ["person", "fact"],
            },
            category="memory",
        )

    def execute(self, **p: Any) -> ToolResult:
        person = (p.get("person") or "").strip()
        fact = (p.get("fact") or "").strip()
        if not person or not fact:
            return ToolResult(tool_name=self.tool_id, content="Need a person and a fact.", success=False, metadata={})
        backend = _memory_backend()
        if backend is not None:
            try:
                backend.store(f"{person}: {fact}", source="people",
                              metadata={"person": person.lower(), "kind": "people"})
            except Exception:
                pass
        return ToolResult(tool_name=self.tool_id, content=f"Noted about {person}.", success=True,
                          metadata={"person": person, "fact": fact})


# ── 2J — memory recall ───────────────────────────────────────────────────────
@ToolRegistry.register("memory_recall")
class MemoryRecallTool(BaseTool):
    tool_id = "memory_recall"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory_recall",
            description="Search memory for what VANTA knows about a topic or person. "
                        "Use for 'what do you remember about X', 'remind me what I said about Y'.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            category="memory",
        )

    def execute(self, **p: Any) -> ToolResult:
        query = (p.get("query") or "").strip()
        if not query:
            return ToolResult(tool_name=self.tool_id, content="What should I recall?", success=False, metadata={})
        backend = _memory_backend()
        if backend is None:
            return ToolResult(tool_name=self.tool_id, content="Memory isn't wired up right now.", success=False, metadata={})
        try:
            results = backend.search(query, top_k=5)
            rows: List[str] = []
            for r in (results or []):
                txt = getattr(r, "content", None) or (r.get("content") if isinstance(r, dict) else str(r))
                if txt:
                    rows.append(str(txt))
            if not rows:
                return ToolResult(tool_name=self.tool_id, content=f"I don't have anything saved about {query}.", success=True, metadata={"hits": 0})
            return ToolResult(tool_name=self.tool_id, content="\n".join(f"- {r}" for r in rows[:5]), success=True, metadata={"hits": len(rows)})
        except Exception as exc:
            return ToolResult(tool_name=self.tool_id, content=f"Memory search failed: {exc}", success=False, metadata={})


# ── 2I — milestone celebrations (personal, never generic) ────────────────────
MILESTONE_RESPONSES: Dict[str, str] = {
    "first_omnix_user": "First OMNIX paid user. That's the line crossing from building to a real business — the thing you've been grinding nights for. Big one.",
    "revenue": "Revenue milestone hit. Every dollar here is proof the model works. Keep the receipts — this is the start of the curve.",
    "sprint_complete": "Sprint done. That's another block of VANTA shipped while most people were asleep. Momentum's yours.",
    "first_overnight_fix": "First autonomous overnight fix landed — you woke up to work already done. That's the whole point of VANTA, and it just happened.",
    "first_no_price_check": "You bought without checking the price. Small moment, but that's the freedom you've been building toward.",
    "family_freedom": "Family financial freedom — that's the real finish line behind all of this. Acknowledged, properly.",
}


def milestone_message(kind: str) -> str:
    return MILESTONE_RESPONSES.get(kind, "")


@ToolRegistry.register("milestone")
class MilestoneTool(BaseTool):
    tool_id = "milestone"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="milestone",
            description="Acknowledge a meaningful milestone personally. kinds: first_omnix_user, revenue, "
                        "sprint_complete, first_overnight_fix, first_no_price_check, family_freedom.",
            parameters={
                "type": "object",
                "properties": {"kind": {"type": "string"}, "detail": {"type": "string"}},
                "required": ["kind"],
            },
            category="personal",
        )

    def execute(self, **p: Any) -> ToolResult:
        kind = (p.get("kind") or "").strip()
        msg = milestone_message(kind)
        if not msg:
            return ToolResult(tool_name=self.tool_id, content="", success=False, metadata={"unknown_kind": kind})
        detail = (p.get("detail") or "").strip()
        if detail:
            msg = f"{msg} ({detail})"
        return ToolResult(tool_name=self.tool_id, content=msg, success=True, metadata={"kind": kind})


__all__ = ["PeopleRememberTool", "MemoryRecallTool", "MilestoneTool", "milestone_message", "MILESTONE_RESPONSES"]
