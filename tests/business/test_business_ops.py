"""Unit tests for the universal business store (Sprint 3, 3A–3D)."""

from __future__ import annotations

import time

import pytest

from openjarvis.business.store import BusinessStore, from_cents, to_cents


@pytest.fixture
def store(tmp_path):
    return BusinessStore(db_path=tmp_path / "biz.db")


def test_cents_roundtrip():
    assert to_cents(450) == 45000
    assert to_cents("$1,200.50") == 120050
    assert from_cents(45000) == "$450.00"


# 3A — quotes
def test_create_and_list_quote(store):
    q = store.create_quote("Replace kitchen tap", 180, client="Mrs Tan", timeline="2 days")
    assert q["amount"] == "$180.00"
    rows = store.list_quotes()
    assert len(rows) == 1 and rows[0]["description"] == "Replace kitchen tap"
    rendered = store.render_quote(q, contact="bryan@vanta")
    assert "QUOTE" in rendered and "$180.00" in rendered and "Mrs Tan" in rendered


# 3B — jobs
def test_job_lifecycle_and_snapshot(store):
    j = store.log_job("Sleeve tattoo", client="Alex", price=600)
    assert j["status"] == "pending"
    assert store.set_job_status(j["id"], "in_progress") is True
    assert store.set_job_status("Sleeve tattoo", "done") is True  # by description
    snap = store.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_this_week"] == 1


def test_set_status_rejects_invalid(store):
    store.log_job("X")
    assert store.set_job_status("X", "banana") is False


def test_list_jobs_by_status(store):
    store.log_job("A", status="pending")
    store.log_job("B", status="in_progress")
    assert len(store.list_jobs(status="pending")) == 1
    assert len(store.list_jobs()) == 2


# 3C — clients
def test_client_add_note_history(store):
    store.add_client("OMNIX Pilot", contact="pilot@omnix")
    assert store.add_note("OMNIX Pilot", "Wants weekly digest") is True
    assert store.add_note("Nobody", "x") is False
    store.log_job("Integration", client="OMNIX Pilot", price=2000)
    h = store.client_history("OMNIX Pilot")
    assert h["client"]["contact"] == "pilot@omnix"
    assert len(h["jobs"]) == 1
    assert "Wants weekly digest" in h["client"]["notes"]


# 3D — invoices / payments
def test_owed_paid_and_who_owes(store):
    store.record_owed("Acme", 1000, description="Build")
    store.record_owed("Beta", 500)
    owes = store.who_owes()
    by = {r["client"]: r for r in owes}
    assert by["Acme"]["owed"] == "$1,000.00"
    # Partial payment.
    assert store.mark_paid("Acme", 400) is True
    assert {r["client"]: r["owed"] for r in store.who_owes()}["Acme"] == "$600.00"
    # Full payment clears it.
    assert store.mark_paid("Acme") is True
    assert "Acme" not in {r["client"] for r in store.who_owes()}


def test_mark_paid_no_balance(store):
    assert store.mark_paid("Ghost") is False


def test_overdue_flag(store):
    store.record_owed("Late", 300, due_days=0)
    # Backdate the row so it is > OVERDUE_DAYS old.
    with store._conn() as c:
        c.execute("UPDATE payments SET created_at=?, due_at=? WHERE client='Late'",
                  (time.time() - 30 * 86400, time.time() - 20 * 86400))
    assert store.who_owes()[0]["overdue"] is True


# tool registration smoke test
def test_business_tools_registered():
    # The shared autouse conftest clears ToolRegistry between tests, so reload
    # the module to re-run its @ToolRegistry.register decorators here.
    import importlib
    import openjarvis.tools.business_tools as bt
    importlib.reload(bt)
    from openjarvis.core.registry import ToolRegistry
    for t in ("business_quote", "business_job", "business_client", "business_invoice", "business_snapshot"):
        assert t in ToolRegistry.keys()
