"""Business-ops tools (Sprint 3, 3A–3D) — quotes, jobs, clients, invoices.

Universal: works for any kind of work (plumbing, tattoo, AI clients, OMNIX).
Each tool is a thin wrapper over :class:`openjarvis.business.store.BusinessStore`
so the same capability is reachable by voice and by text through the orchestrator.
"""

from __future__ import annotations

from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _store():
    from openjarvis.business.store import BusinessStore
    return BusinessStore()


@ToolRegistry.register("business_quote")
class QuoteTool(BaseTool):
    """Generate and store a professional quote (3A)."""

    tool_id = "business_quote"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="business_quote",
            description="Generate a professional quote for a job and save it. "
                        "Use for 'generate a quote for ...' / 'show recent quotes'.",
            parameters={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Job description"},
                    "amount": {"type": "string", "description": "Estimated cost, e.g. 450 or $1,200"},
                    "client": {"type": "string"},
                    "timeline": {"type": "string"},
                    "terms": {"type": "string"},
                    "list": {"type": "boolean", "description": "If true, list recent quotes instead"},
                },
                "required": [],
            },
            category="business",
        )

    def execute(self, **p: Any) -> ToolResult:
        s = _store()
        if p.get("list") or not p.get("description"):
            rows = s.list_quotes(client=(p.get("client") or "").strip())
            if not rows:
                return ToolResult(tool_name=self.tool_id, content="No quotes yet.", success=True, metadata={})
            from openjarvis.business.store import from_cents
            lines = [f"{r['id']}  {r['description'][:40]}  {from_cents(r['amount_cents'])}  {r.get('client') or '—'}" for r in rows]
            return ToolResult(tool_name=self.tool_id, content="Recent quotes:\n" + "\n".join(lines), success=True, metadata={"count": len(rows)})
        q = s.create_quote(p["description"], p.get("amount", 0), client=p.get("client", ""),
                           timeline=p.get("timeline", ""), terms=p.get("terms", ""))
        return ToolResult(tool_name=self.tool_id, content=s.render_quote(q), success=True, metadata=q)


@ToolRegistry.register("business_job")
class JobTool(BaseTool):
    """Log / update / list jobs (3B)."""

    tool_id = "business_job"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="business_job",
            description="Track jobs. action=log (new job), done/paid/cancelled (update status), "
                        "list (show jobs, optionally by status).",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["log", "done", "paid", "cancelled", "in_progress", "list"]},
                    "description": {"type": "string"},
                    "client": {"type": "string"},
                    "price": {"type": "string"},
                    "status": {"type": "string", "description": "Filter for list"},
                },
                "required": ["action"],
            },
            category="business",
        )

    def execute(self, **p: Any) -> ToolResult:
        s = _store()
        action = (p.get("action") or "list").lower()
        if action == "log":
            j = s.log_job(p.get("description", ""), client=p.get("client", ""), price=p.get("price", 0))
            return ToolResult(tool_name=self.tool_id, content=f"Logged job {j['id']}: {j['description']} ({j['price']}) for {j['client'] or '—'}.", success=True, metadata=j)
        if action in ("done", "paid", "cancelled", "in_progress"):
            ok = s.set_job_status(p.get("description", ""), action)
            return ToolResult(tool_name=self.tool_id, content=("Marked." if ok else "No matching job."), success=ok, metadata={})
        rows = s.list_jobs(status=(p.get("status") or "").strip())
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="No jobs.", success=True, metadata={})
        from openjarvis.business.store import from_cents
        lines = [f"{r['status']:<11} {r['description'][:38]}  {from_cents(r['price_cents'])}  {r.get('client') or '—'}" for r in rows]
        return ToolResult(tool_name=self.tool_id, content="\n".join(lines), success=True, metadata={"count": len(rows)})


@ToolRegistry.register("business_client")
class ClientTool(BaseTool):
    """Add clients, notes, and view history (3C)."""

    tool_id = "business_client"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="business_client",
            description="Manage clients. action=add (new), note (append note), history (jobs+quotes).",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "note", "history"]},
                    "name": {"type": "string"},
                    "contact": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["action", "name"],
            },
            category="business",
        )

    def execute(self, **p: Any) -> ToolResult:
        s = _store()
        action = (p.get("action") or "history").lower()
        name = p.get("name", "")
        if action == "add":
            c = s.add_client(name, contact=p.get("contact", ""), notes=p.get("note", ""))
            return ToolResult(tool_name=self.tool_id, content=f"Added client {c['name']} ({c['id']}).", success=True, metadata=c)
        if action == "note":
            ok = s.add_note(name, p.get("note", ""))
            return ToolResult(tool_name=self.tool_id, content=("Noted." if ok else "Client not found."), success=ok, metadata={})
        h = s.client_history(name)
        if not h["client"]:
            return ToolResult(tool_name=self.tool_id, content="Client not found.", success=False, metadata={})
        return ToolResult(tool_name=self.tool_id,
                          content=f"{name}: {len(h['jobs'])} jobs, {len(h['quotes'])} quotes.",
                          success=True, metadata=h)


@ToolRegistry.register("business_invoice")
class InvoiceTool(BaseTool):
    """Track outstanding payments (3D)."""

    tool_id = "business_invoice"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="business_invoice",
            description="Track payments. action=owed (client owes amount), paid (client paid), "
                        "who_owes (list outstanding).",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["owed", "paid", "who_owes"]},
                    "client": {"type": "string"},
                    "amount": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["action"],
            },
            category="business",
        )

    def execute(self, **p: Any) -> ToolResult:
        s = _store()
        action = (p.get("action") or "who_owes").lower()
        if action == "owed":
            r = s.record_owed(p.get("client", ""), p.get("amount", 0), description=p.get("description", ""))
            return ToolResult(tool_name=self.tool_id, content=f"Recorded: {r['client']} owes {r['owed']}.", success=True, metadata=r)
        if action == "paid":
            ok = s.mark_paid(p.get("client", ""), p.get("amount", 0))
            return ToolResult(tool_name=self.tool_id, content=("Payment recorded." if ok else "No outstanding balance."), success=ok, metadata={})
        rows = s.who_owes()
        if not rows:
            return ToolResult(tool_name=self.tool_id, content="Nobody owes you right now.", success=True, metadata={})
        lines = [f"{r['client']}: {r['owed']}" + ("  (OVERDUE)" if r["overdue"] else "") for r in rows]
        return ToolResult(tool_name=self.tool_id, content="Outstanding:\n" + "\n".join(lines), success=True, metadata={"count": len(rows)})


@ToolRegistry.register("business_snapshot")
class SnapshotTool(BaseTool):
    """One-line business snapshot."""

    tool_id = "business_snapshot"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="business_snapshot",
            description="Business snapshot: active jobs, pending payment total, jobs done this week.",
            parameters={"type": "object", "properties": {}, "required": []},
            category="business",
        )

    def execute(self, **_p: Any) -> ToolResult:
        snap = _store().snapshot()
        content = (f"{snap['active_jobs']} active jobs, {snap['completed_this_week']} done this week, "
                   f"{snap['pending_payment']} pending payment.")
        return ToolResult(tool_name=self.tool_id, content=content, success=True, metadata=snap)


__all__ = ["QuoteTool", "JobTool", "ClientTool", "InvoiceTool", "SnapshotTool"]
