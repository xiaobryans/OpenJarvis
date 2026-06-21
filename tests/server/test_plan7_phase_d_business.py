"""Plan 7 Phase D Gate Tests — Business/Operator System.

Gate D requirements:
  - Business project creation → task planning → execution state → memory trace
  - Connector-gated operation tests
  - Handoff/report generation tests
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from openjarvis.server.workstream_routes import router
    from openjarvis.projects.workstream import get_workstream_registry, WorkstreamRegistry
    import openjarvis.projects.workstream as _m
    _m._registry = WorkstreamRegistry()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# D1 — Business project creation → task planning → execution state → memory trace
# ---------------------------------------------------------------------------

class TestBusinessProjectLifecycle:
    def test_create_workstream(self, client):
        resp = client.post("/v1/workstreams", json={
            "name": "Q3 Product Launch",
            "description": "Full product launch for Q3",
            "tags": ["product", "launch"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] is True
        ws = data["workstream"]
        assert ws["name"] == "Q3 Product Launch"
        assert ws["status"] == "active"
        assert "workstream_id" in ws
        assert ws["memory_namespace"].startswith("workstream:")

    def test_add_task_to_workstream(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "WS for tasks"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        resp = client.post(f"/v1/workstreams/{ws_id}/tasks", json={
            "title": "Write product spec",
            "description": "Draft the product requirements",
            "assignee": "bryan",
        })
        assert resp.status_code == 200
        task = resp.json()["task"]
        assert task["title"] == "Write product spec"
        assert task["status"] == "pending"
        assert task["assignee"] == "bryan"

    def test_task_planning_multiple_tasks(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Multi-task WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        for title in ["Design UI", "Build backend", "QA testing", "Deploy"]:
            client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": title})
        detail_resp = client.get(f"/v1/workstreams/{ws_id}")
        ws = detail_resp.json()["workstream"]
        assert ws["task_count"] == 4

    def test_task_execution_state_transitions(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Execution WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        task_resp = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Execute me"})
        task_id = task_resp.json()["task"]["task_id"]

        # pending → in_progress
        resp = client.post(f"/v1/workstreams/{ws_id}/tasks/{task_id}/status", json={"status": "in_progress"})
        assert resp.json()["status"] == "in_progress"

        # in_progress → done
        resp = client.post(f"/v1/workstreams/{ws_id}/tasks/{task_id}/status", json={"status": "done"})
        assert resp.json()["status"] == "done"

    def test_memory_trace_on_task(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Memory trace WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        task_resp = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Traced task"})
        task_id = task_resp.json()["task"]["task_id"]

        # Add memory trace
        resp = client.post(f"/v1/workstreams/{ws_id}/tasks/{task_id}/trace", json={
            "event": "design_decision",
            "data": {"decision": "Use PostgreSQL", "reason": "Need ACID"},
        })
        assert resp.status_code == 200
        assert resp.json()["trace_count"] == 1

        # Add second trace
        client.post(f"/v1/workstreams/{ws_id}/tasks/{task_id}/trace", json={
            "event": "code_review",
            "data": {"reviewer": "ai", "result": "approved"},
        })
        # Get workstream detail and verify traces
        detail_resp = client.get(f"/v1/workstreams/{ws_id}")
        tasks = detail_resp.json()["workstream"]["tasks"]
        traced_task = next(t for t in tasks if t["task_id"] == task_id)
        assert len(traced_task["memory_trace"]) == 2
        assert traced_task["memory_trace"][0]["event"] == "design_decision"


# ---------------------------------------------------------------------------
# D2 — Decision log
# ---------------------------------------------------------------------------

class TestDecisionLog:
    def test_record_decision(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Decision WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        resp = client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Use React for frontend",
            "decision": "We will use React",
            "rationale": "Team expertise, ecosystem",
            "decision_type": "technical",
            "made_by": "bryan",
        })
        assert resp.status_code == 200
        dec = resp.json()["decision"]
        assert dec["title"] == "Use React for frontend"
        assert dec["decision_type"] == "technical"
        assert dec["made_by"] == "bryan"
        assert "decision_id" in dec

    def test_list_decisions(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Decision list WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Dec 1", "decision": "Go with A", "rationale": "Better", "decision_type": "business",
        })
        client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Dec 2", "decision": "Use B", "rationale": "Cheaper", "decision_type": "operational",
        })
        resp = client.get(f"/v1/workstreams/{ws_id}/decisions")
        assert resp.json()["count"] == 2

    def test_decision_with_memory_refs(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Memory dec WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        resp = client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Architecture choice",
            "decision": "Microservices",
            "rationale": "Scalability",
            "decision_type": "architectural",
            "memory_refs": ["mem_arch_research", "mem_competitor_analysis"],
        })
        dec = resp.json()["decision"]
        assert "mem_arch_research" in dec["memory_refs"]

    def test_invalid_decision_type_rejected(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Invalid dec WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        resp = client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Bad", "decision": "X", "rationale": "Y", "decision_type": "magic",
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# D3 — Handoff/report generation
# ---------------------------------------------------------------------------

class TestHandoffGeneration:
    def test_generate_handoff_empty_workstream(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Handoff WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        resp = client.get(f"/v1/workstreams/{ws_id}/handoff")
        assert resp.status_code == 200
        handoff = resp.json()["handoff"]
        assert "report_id" in handoff
        assert "workstream_id" in handoff
        assert "summary" in handoff

    def test_handoff_reflects_completed_tasks(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Completed WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        t1 = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Done task"}).json()["task"]["task_id"]
        t2 = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Pending task"}).json()["task"]["task_id"]
        client.post(f"/v1/workstreams/{ws_id}/tasks/{t1}/status", json={"status": "done"})
        resp = client.get(f"/v1/workstreams/{ws_id}/handoff")
        handoff = resp.json()["handoff"]
        assert "Done task" in handoff["completed_tasks"]
        assert "Pending task" in handoff["pending_tasks"]

    def test_handoff_includes_decisions(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Decision handoff WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Key decision", "decision": "Go", "rationale": "Because", "decision_type": "business",
        })
        resp = client.get(f"/v1/workstreams/{ws_id}/handoff")
        handoff = resp.json()["handoff"]
        assert "Key decision" in handoff["decisions_made"]

    def test_handoff_has_next_actions(self, client):
        create_resp = client.post("/v1/workstreams", json={"name": "Next actions WS"})
        ws_id = create_resp.json()["workstream"]["workstream_id"]
        for t in ["Task A", "Task B", "Task C", "Task D"]:
            client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": t})
        resp = client.get(f"/v1/workstreams/{ws_id}/handoff")
        handoff = resp.json()["handoff"]
        assert len(handoff["next_actions"]) > 0

    def test_list_workstreams(self, client):
        client.post("/v1/workstreams", json={"name": "WS One"})
        client.post("/v1/workstreams", json={"name": "WS Two"})
        resp = client.get("/v1/workstreams")
        assert resp.json()["count"] >= 2

    def test_nonexistent_workstream_404(self, client):
        resp = client.get("/v1/workstreams/does_not_exist")
        assert resp.status_code == 404
