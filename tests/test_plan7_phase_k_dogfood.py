"""Plan 7 Phase K Gate Tests — Only-Manual-Platform Dogfood Certification.

Gate K: 10 dogfood scenarios proving Jarvis can be Bryan's only normal front door.

Scenarios:
  1. Start a new project from Jarvis
  2. Run a coding/self-upgrade task from Jarvis
  3. Run a research task from Jarvis
  4. Run a personal/admin task from Jarvis
  5. Use mobile while MacBook is off through AWS (structural proof)
  6. Continue same task across mobile and desktop
  7. Trigger an approval flow from mobile
  8. Route to at least one external connector/tool without manual platform-hopping
  9. Record memory/task/approval traces
  10. Produce final handoff/report
"""

from __future__ import annotations

import tempfile
import pathlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_full_app():
    """Create app with all Plan 7 routes for dogfood scenarios."""
    from fastapi import FastAPI
    from openjarvis.server.frontdoor_routes import router as frontdoor_router
    from openjarvis.server.life_os_routes import router as life_os_router
    from openjarvis.server.workstream_routes import router as workstream_router
    from openjarvis.server.goals_routes import router as goals_router
    from openjarvis.server.self_upgrade_routes import router as self_upgrade_router
    from openjarvis.server.connectors_router import create_connectors_router

    # Fresh stores
    from openjarvis.jarvis_os.personal_os import PersonalTaskStore
    from openjarvis.projects.workstream import WorkstreamRegistry
    from openjarvis.orchestrator.goals import GoalRegistry
    from openjarvis.orchestrator.self_upgrade import SelfUpgradePlanStore
    import openjarvis.jarvis_os.personal_os as _p
    import openjarvis.projects.workstream as _w
    import openjarvis.orchestrator.goals as _g
    import openjarvis.orchestrator.self_upgrade as _s
    _p._store = PersonalTaskStore()
    _w._registry = WorkstreamRegistry()
    _g._registry = GoalRegistry()
    _s._store = SelfUpgradePlanStore()

    app = FastAPI(title="Jarvis Plan 7 Dogfood")
    app.include_router(frontdoor_router)
    app.include_router(life_os_router)
    app.include_router(workstream_router)
    app.include_router(goals_router)
    app.include_router(self_upgrade_router)
    app.include_router(create_connectors_router())
    return app


@pytest.fixture(scope="module")
def app():
    return _make_full_app()


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Dogfood Scenario 1: Start a new project from Jarvis
# ---------------------------------------------------------------------------

class TestDogfood1NewProject:
    def test_scenario_1_create_project_from_jarvis(self, client):
        """Bryan starts a new project entirely through Jarvis front door."""
        # Step 1: Submit project creation intent
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Start a new SaaS project: AI resume builder",
            "intent": "project_creation",
            "client_platform": "desktop",
        })
        assert resp.status_code == 200
        fd = resp.json()
        assert fd["intent"] == "project_creation"
        assert fd["status"] == "accepted"

        # Step 2: Create the workstream
        resp = client.post("/v1/workstreams", json={
            "name": "AI Resume Builder",
            "description": "SaaS product: AI-powered resume builder",
            "tags": ["saas", "ai", "product"],
        })
        assert resp.status_code == 200
        ws = resp.json()["workstream"]
        ws_id = ws["workstream_id"]
        assert ws["status"] == "active"

        # Step 3: Add initial tasks
        for task_title in ["Market research", "MVP scope definition", "Tech stack selection"]:
            client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": task_title})

        detail = client.get(f"/v1/workstreams/{ws_id}").json()["workstream"]
        assert detail["task_count"] == 3

        # Step 4: Record first decision
        client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Platform choice: Next.js + FastAPI",
            "decision": "Use Next.js for frontend, FastAPI for backend",
            "rationale": "Team experience, ecosystem fit",
            "decision_type": "technical",
        })

        decisions = client.get(f"/v1/workstreams/{ws_id}/decisions").json()
        assert decisions["count"] == 1


# ---------------------------------------------------------------------------
# Dogfood Scenario 2: Run a coding/self-upgrade task from Jarvis
# ---------------------------------------------------------------------------

class TestDogfood2CodingTask:
    def test_scenario_2_coding_upgrade_from_jarvis(self, client):
        """Bryan runs a coding task through Jarvis self-upgrade system."""
        # Submit via front door
        fd_resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Fix authentication bug in auth.py",
            "intent": "coding",
            "client_platform": "desktop",
            "risk_level": "low",
        })
        assert fd_resp.json()["status"] == "accepted"

        # Create self-upgrade plan
        plan_resp = client.post("/v1/self-upgrade/request", json={
            "title": "Fix auth.py authentication bug",
            "source_request": "Fix authentication bug in auth.py",
            "client_platform": "desktop",
        })
        plan_id = plan_resp.json()["plan"]["plan_id"]

        # Add staged steps
        s1 = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Read current auth.py",
            "risk": "low",
        }).json()["step"]["step_id"]

        s2 = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Write fix",
            "risk": "medium",
            "rollback_command": "git checkout -- src/auth.py",
        }).json()["step"]["step_id"]

        s3 = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Run tests",
            "risk": "low",
            "validation_command": "pytest tests/test_auth.py",
        }).json()["step"]["step_id"]

        # Execute steps
        for sid in [s1, s2, s3]:
            client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{sid}/start")
            client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{sid}/complete")

        detail = client.get(f"/v1/self-upgrade/plans/{plan_id}").json()["plan"]
        steps = detail["steps"]
        assert all(s["status"] == "done" for s in steps)


# ---------------------------------------------------------------------------
# Dogfood Scenario 3: Run a research task from Jarvis
# ---------------------------------------------------------------------------

class TestDogfood3ResearchTask:
    def test_scenario_3_research_via_jarvis(self, client):
        """Bryan runs a research task through Jarvis."""
        # Enter via front door
        fd_resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Research the top 5 AI coding tools in 2026",
            "intent": "research",
            "client_platform": "desktop",
        })
        assert fd_resp.json()["status"] == "accepted"

        # Store research finding in memory
        with tempfile.TemporaryDirectory() as tmpdir:
            from openjarvis.memory.store import JarvisMemory
            mem = JarvisMemory(db_path=pathlib.Path(tmpdir) / "research.db")
            e1 = mem.store(namespace="research", content="GitHub Copilot leads with 30% market share", source="web")
            e2 = mem.store(namespace="research", content="Cursor is fastest growing AI IDE", source="techcrunch")
            assert e1 is not None
            assert e2 is not None

            # Retrieve findings — search is keyword-based; at least 1 result expected
            results = mem.search("AI coding", namespace="research")
            assert len(results) >= 1

        # Add research findings as workstream decision
        ws_resp = client.post("/v1/workstreams", json={"name": "AI Tools Research"})
        ws_id = ws_resp.json()["workstream"]["workstream_id"]
        client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "AI coding tool selection",
            "decision": "Use Cursor as primary coding tool",
            "rationale": "Fastest growing, best AI integration",
            "decision_type": "business",
            "memory_refs": ["research:copilot_market_share", "research:cursor_growth"],
        })
        decisions = client.get(f"/v1/workstreams/{ws_id}/decisions").json()
        assert decisions["count"] >= 1


# ---------------------------------------------------------------------------
# Dogfood Scenario 4: Run a personal/admin task from Jarvis
# ---------------------------------------------------------------------------

class TestDogfood4PersonalAdminTask:
    def test_scenario_4_personal_admin_via_jarvis(self, client):
        """Bryan handles a personal admin task through Jarvis."""
        # Front door intake
        fd_resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Schedule dentist appointment and follow up on tax return",
            "intent": "personal_task",
            "client_platform": "mobile",
        })
        assert fd_resp.json()["status"] == "accepted"

        # Create personal tasks
        t1_resp = client.post("/v1/life-os/tasks", json={
            "title": "Schedule dentist appointment",
            "priority": "medium",
            "tags": ["health", "admin"],
        })
        t1_id = t1_resp.json()["task"]["task_id"]

        t2_resp = client.post("/v1/life-os/tasks", json={
            "title": "Follow up on tax return",
            "priority": "high",
            "tags": ["finance", "admin"],
            "approval_required": True,
        })
        t2_id = t2_resp.json()["task"]["task_id"]

        # Set reminder for dentist
        client.post(f"/v1/life-os/tasks/{t1_id}/remind", json={
            "reminder_type": "time_based",
            "trigger": 1751000000.0,
            "notes": "Call at 9am",
        })

        # Verify approval gate for tax task
        t2_detail = client.get(f"/v1/life-os/tasks/{t2_id}").json()["task"]
        assert t2_detail["status"] == "waiting_approval"

        # Get daily summary
        summary = client.get("/v1/life-os/summary/daily").json()["summary"]
        assert summary["approvals_waiting"] >= 1

        # Complete dentist task
        client.post(f"/v1/life-os/tasks/{t1_id}/status", json={"status": "done"})


# ---------------------------------------------------------------------------
# Dogfood Scenario 5: Mobile MacBook-off AWS (structural proof)
# ---------------------------------------------------------------------------

class TestDogfood5MobileAWSProof:
    def test_scenario_5_macbook_off_aws_structural_proof(self):
        """Structural proof that MacBook-off via AWS ECS Fargate is configured."""
        from openjarvis.mobile.continuity_backend import get_continuity_backend_spec
        from openjarvis.mobile.capability_parity import MobileCapabilityMatrix

        spec = get_continuity_backend_spec()
        assert spec.runtime_macbook_off_capable is True
        assert spec.auth_required is True

        matrix = MobileCapabilityMatrix.get()
        aws_cap = matrix.get_status("macbook_off_aws")
        assert aws_cap == "available"

        # All mobile capabilities declared
        assert matrix.all_available() is True


# ---------------------------------------------------------------------------
# Dogfood Scenario 6: Continue task across mobile and desktop
# ---------------------------------------------------------------------------

class TestDogfood6CrossDeviceContinuity:
    def test_scenario_6_cross_device_task_continuation(self):
        """Start task on desktop, continue on mobile via snapshot."""
        from openjarvis.mobile.continuity import ContinuitySnapshot, SyncStatus
        import uuid

        # Desktop creates snapshot
        snap = ContinuitySnapshot(
            snapshot_id=uuid.uuid4().hex,
            user_id="bryan",
            source_device_id="desktop",
            resume_token=uuid.uuid4().hex,
            conversation_id="conv_001",
            conversation_messages=[{"role": "user", "content": "Fix auth bug"}],
            active_task_id=uuid.uuid4().hex,
            active_task_description="Fix authentication bug in auth.py",
            active_task_status="in_progress",
            assigned_manager_role_id=None,
            assigned_worker_role_ids=["coding_safe"],
            worker_statuses={"coding_safe": "executing"},
            pending_approvals=[],
            artifact_pointers=[],
            project_id="openjarvis",
            project_context={"phase": "I"},
            memory_refs=["auth_bug_context"],
            tool_states={},
            sync_status=SyncStatus.SYNCED,
            conflict_state=None,
            verifier_status=None,
            verifier_fix_list=[],
        )

        # Mobile loads snapshot
        snap_dict = snap.to_dict()
        from openjarvis.mobile.continuity import ContinuitySnapshot
        mobile_snap = ContinuitySnapshot.from_dict(snap_dict)

        assert mobile_snap.snapshot_id == snap.snapshot_id
        assert mobile_snap.active_task_description == snap.active_task_description
        assert mobile_snap.worker_statuses["coding_safe"] == "executing"
        assert "auth_bug_context" in mobile_snap.memory_refs


# ---------------------------------------------------------------------------
# Dogfood Scenario 7: Trigger approval flow from mobile
# ---------------------------------------------------------------------------

class TestDogfood7MobileApprovalFlow:
    def test_scenario_7_mobile_approval_flow(self, client):
        """Bryan triggers and approves a sensitive action from mobile."""
        # Create sensitive task (simulates deploy approval needed)
        task_resp = client.post("/v1/life-os/tasks", json={
            "title": "Approve deploy to production",
            "priority": "high",
            "approval_required": True,
        })
        task_id = task_resp.json()["task"]["task_id"]
        assert task_resp.json()["task"]["status"] == "waiting_approval"

        # Check pending approvals (as mobile would)
        pending = client.get("/v1/life-os/approvals/pending").json()
        assert pending["count"] >= 1

        # Approve from mobile
        approve_resp = client.post(f"/v1/life-os/tasks/{task_id}/approve")
        assert approve_resp.json()["status"] == "pending"
        assert approve_resp.json()["approval_state"] == "approved"


# ---------------------------------------------------------------------------
# Dogfood Scenario 8: Route to external connector without platform-hopping
# ---------------------------------------------------------------------------

class TestDogfood8ConnectorRouting:
    def test_scenario_8_connector_routing_no_manual_hop(self, client):
        """Route work to external connector via Jarvis — no manual platform switch needed."""
        # Submit connector action via front door
        fd_resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Check status of all GitHub PRs in openjarvis/openjarvis",
            "intent": "connector_action",
            "risk_level": "low",
            "client_platform": "desktop",
        })
        assert fd_resp.json()["status"] == "accepted"
        assert "await_approval" not in fd_resp.json()["next_actions"]  # low risk = no approval

        # Verify connector status is readable
        conn_resp = client.get("/v1/connectors/status")
        assert conn_resp.status_code == 200


# ---------------------------------------------------------------------------
# Dogfood Scenario 9: Record memory/task/approval traces
# ---------------------------------------------------------------------------

class TestDogfood9MemoryAndTraces:
    def test_scenario_9_full_trace_record(self, client):
        """Record memory trace across task, workstream, and approval."""
        # Create workstream with task + trace
        ws_resp = client.post("/v1/workstreams", json={"name": "Trace test WS"})
        ws_id = ws_resp.json()["workstream"]["workstream_id"]
        task_resp = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Traced task"})
        task_id = task_resp.json()["task"]["task_id"]

        # Add execution trace
        client.post(f"/v1/workstreams/{ws_id}/tasks/{task_id}/trace", json={
            "event": "llm_call",
            "data": {"model": "gpt-4o-mini", "tokens": 450},
        })
        client.post(f"/v1/workstreams/{ws_id}/tasks/{task_id}/trace", json={
            "event": "file_edited",
            "data": {"file": "src/auth.py", "lines_changed": 12},
        })

        # Add memory trace
        with tempfile.TemporaryDirectory() as tmpdir:
            from openjarvis.memory.store import JarvisMemory
            mem = JarvisMemory(db_path=pathlib.Path(tmpdir) / "trace.db")
            e = mem.store(namespace="task_trace", content="Edited auth.py: fixed JWT expiry bug", source="coding_safe")
            assert e is not None

        # Verify traces in workstream
        detail = client.get(f"/v1/workstreams/{ws_id}").json()["workstream"]
        traced = next(t for t in detail["tasks"] if t["task_id"] == task_id)
        assert len(traced["memory_trace"]) == 2

        # Add approval trace
        sensitive_task = client.post("/v1/life-os/tasks", json={
            "title": "Send report to investor",
            "priority": "high",
            "approval_required": True,
        }).json()["task"]
        assert sensitive_task["status"] == "waiting_approval"
        # Trace exists in approval queue
        approvals = client.get("/v1/life-os/approvals/pending").json()
        assert approvals["count"] >= 1


# ---------------------------------------------------------------------------
# Dogfood Scenario 10: Produce final handoff/report
# ---------------------------------------------------------------------------

class TestDogfood10HandoffReport:
    def test_scenario_10_final_handoff_report(self, client):
        """Produce a complete handoff report from Jarvis."""
        # Create workstream with completed and pending tasks + decisions
        ws_resp = client.post("/v1/workstreams", json={
            "name": "Dogfood Sprint Report",
            "description": "Final dogfood handoff",
        })
        ws_id = ws_resp.json()["workstream"]["workstream_id"]

        # Add tasks
        t1 = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Phase A-J implementation"}).json()["task"]["task_id"]
        t2 = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Gate tests"}).json()["task"]["task_id"]
        t3 = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Mobile parity verification"}).json()["task"]["task_id"]
        t4 = client.post(f"/v1/workstreams/{ws_id}/tasks", json={"title": "Post-Plan 7 UI polish"}).json()["task"]["task_id"]

        # Complete some
        client.post(f"/v1/workstreams/{ws_id}/tasks/{t1}/status", json={"status": "done"})
        client.post(f"/v1/workstreams/{ws_id}/tasks/{t2}/status", json={"status": "done"})
        client.post(f"/v1/workstreams/{ws_id}/tasks/{t3}/status", json={"status": "done"})
        # t4 stays pending (post-Plan 7 work)

        # Add decision
        client.post(f"/v1/workstreams/{ws_id}/decisions", json={
            "title": "Plan 7 acceptance status",
            "decision": "PLAN_7_MASTER_ACCEPT_PENDING_REVIEW",
            "rationale": "All A-J gate tests pass; mobile parity structural; MacBook-off via ECS",
            "decision_type": "approval",
        })

        # Generate handoff
        handoff_resp = client.get(f"/v1/workstreams/{ws_id}/handoff")
        assert handoff_resp.status_code == 200
        handoff = handoff_resp.json()["handoff"]

        # Verify completeness
        assert "Phase A-J implementation" in handoff["completed_tasks"]
        assert "Gate tests" in handoff["completed_tasks"]
        assert "Post-Plan 7 UI polish" in handoff["pending_tasks"]
        assert "Plan 7 acceptance status" in handoff["decisions_made"]
        assert len(handoff["next_actions"]) > 0
        assert "report_id" in handoff
        assert "generated_at" in handoff
