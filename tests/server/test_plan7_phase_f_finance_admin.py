"""Plan 7 Phase F Gate Tests — Finance/Admin Operator Foundation.

Gate F requirements:
  - Finance/admin planning tests
  - Payment/destructive gate tests (must block without explicit approval)
  - Audit trail tests
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# F1 — Finance/admin task types through front door
# ---------------------------------------------------------------------------

class TestFinanceAdminTaskTypes:
    def test_finance_task_enters_frontdoor(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openjarvis.server.frontdoor_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Review last month's AWS bill",
            "intent": "finance_admin",
            "risk_level": "low",
        })
        assert resp.status_code == 200
        assert resp.json()["intent"] == "finance_admin"
        assert resp.json()["status"] == "accepted"

    def test_finance_task_via_life_os(self):
        from openjarvis.jarvis_os.personal_os import PersonalTask, PersonalTaskStore
        store = PersonalTaskStore()
        task = PersonalTask.create(
            title="Pay quarterly taxes",
            description="Transfer to CRA",
            priority="high",
            tags=["finance", "admin"],
            approval_required=True,  # payments MUST require approval
        )
        store.add(task)
        assert task.approval_required is True
        assert task.status.value == "waiting_approval"

    def test_finance_admin_workstream(self):
        from openjarvis.projects.workstream import WorkstreamRegistry
        registry = WorkstreamRegistry()
        ws = registry.create("Q3 Finance Ops", description="Quarterly financial administration")
        ws.add_task("Reconcile bank statements")
        ws.add_task("Review vendor contracts")
        ws.add_task("Prepare expense report")
        assert ws.to_dict()["task_count"] == 3


# ---------------------------------------------------------------------------
# F2 — Payment/destructive gate tests
# ---------------------------------------------------------------------------

class TestPaymentGates:
    def test_payment_action_requires_approval_in_frontdoor(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openjarvis.server.frontdoor_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        # High-risk payment action
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Send $5000 payment to vendor XYZ",
            "intent": "finance_admin",
            "risk_level": "high",
        })
        data = resp.json()
        assert data["approval_required"] is True
        assert "await_approval" in data["next_actions"]

    def test_blocked_risk_level_for_destructive_finance(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openjarvis.server.frontdoor_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Delete all financial records",
            "intent": "finance_admin",
            "risk_level": "blocked",
        })
        data = resp.json()
        assert data["status"] == "blocked"
        assert data["blocked_reason"] is not None

    def test_payment_task_gated_in_life_os(self):
        from openjarvis.jarvis_os.personal_os import PersonalTask
        task = PersonalTask.create(
            title="Wire transfer to supplier",
            priority="high",
            approval_required=True,
        )
        assert task.status.value == "waiting_approval"
        # Cannot execute without approval
        # Approve it first
        task.approve()
        assert task.status.value == "pending"
        assert task.approval_state == "approved"

    def test_unapproved_payment_task_stays_blocked(self):
        from openjarvis.jarvis_os.personal_os import PersonalTask
        task = PersonalTask.create(
            title="Auto-pay subscription",
            priority="medium",
            approval_required=True,
        )
        # Without approving — still waiting
        assert task.status.value == "waiting_approval"
        assert task.approval_state == "pending_approval"

    def test_no_banking_claims_beyond_available_data(self):
        """Test that finance tasks don't fabricate banking data."""
        from openjarvis.jarvis_os.personal_os import PersonalTask
        task = PersonalTask.create(
            title="Review bank statement",
            priority="high",
            approval_required=False,
        )
        # Task is created as-is — no fabricated balance/transaction data
        assert task.description == ""  # No fabricated data
        assert task.memory_refs == []  # No hallucinated refs

    def test_approval_required_flag_enforced(self):
        from openjarvis.jarvis_os.personal_os import PersonalTask, PersonalTaskStore
        store = PersonalTaskStore()
        # Create multiple payment tasks
        for title in ["Pay rent", "Pay supplier", "Pay taxes"]:
            t = PersonalTask.create(title=title, priority="high", approval_required=True)
            store.add(t)
        # All must be in waiting_approval
        pending = store.pending_approvals()
        assert len(pending) == 3
        for t in pending:
            assert t.status.value == "waiting_approval"


# ---------------------------------------------------------------------------
# F3 — Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_workstream_decision_is_audit_trail(self):
        """Decision records in workstreams serve as an audit trail for finance/admin."""
        from openjarvis.projects.workstream import WorkstreamRegistry
        registry = WorkstreamRegistry()
        ws = registry.create("Finance audit WS")
        rec = ws.record_decision(
            title="Approved Q3 budget",
            decision="Budget of $50,000 approved",
            rationale="Board approval obtained",
            decision_type="approval",
            made_by="bryan",
        )
        assert rec.decision_type.value == "approval"
        assert rec.made_by == "bryan"
        assert "created_at" in rec.to_dict()

    def test_task_memory_trace_is_audit_trail(self):
        """Memory traces on tasks form an audit trail for executed actions."""
        from openjarvis.projects.workstream import WorkstreamRegistry
        registry = WorkstreamRegistry()
        ws = registry.create("Finance trace WS")
        task = ws.add_task("Process vendor invoice")
        task.add_memory_trace("invoice_received", {"vendor": "ACME", "amount": 1500})
        task.add_memory_trace("payment_authorized", {"authorized_by": "bryan", "method": "bank_transfer"})
        assert len(task.memory_trace) == 2
        assert task.memory_trace[1]["event"] == "payment_authorized"
        assert task.memory_trace[1]["data"]["authorized_by"] == "bryan"

    def test_personal_task_timestamps_for_audit(self):
        """Personal tasks have timestamps for audit trail."""
        from openjarvis.jarvis_os.personal_os import PersonalTask
        task = PersonalTask.create("Audit task", approval_required=True)
        d = task.to_dict()
        assert "created_at" in d
        assert "updated_at" in d
        assert d["created_at"] > 0

    def test_finance_decision_stored_in_memory(self):
        """Finance decisions can be stored in memory with source metadata."""
        import tempfile, pathlib
        from openjarvis.memory.store import JarvisMemory
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = JarvisMemory(db_path=pathlib.Path(tmpdir) / "test_finance.db")
            entry = mem.store(
                namespace="finance",
                content="Approved Q3 budget for infrastructure",
                source="approval_record",
                tags=["finance", "approval", "q3"],
            )
            assert entry is not None
            assert entry.entry_id is not None
            assert entry.namespace == "finance"
