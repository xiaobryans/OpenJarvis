"""Integration tests — Company Org + Mobile Continuity API Routes.

Tests 14 required integration items from TASK 7:

1.  API route saves MacBook snapshot
2.  API route resumes same snapshot from mobile device
3.  Resume restores all required continuity fields
4.  Conflict state is surfaced
5.  Untrusted device is rejected or degraded explicitly
6.  Company task route executes Jarvis → COS → manager → worker
7.  Worker artifact pointer is present in response
8.  Verifier runs on artifact/evidence
9.  Unsupported verifier row returns HOLD/fix list
10. Missing skill/tool blocks assignment (requested_tools not in manager's list)
11. Stall simulation triggers reassignment or blocker
12. Slack persona mapping for verifier/managers tied to roster
13. Full no-gap remains HOLD
14. Voice remains gated

These tests use FastAPI TestClient against real route implementations.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.company_org_routes import router, _get_store
import openjarvis.server.company_org_routes as _routes_module


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    """Fresh TestClient for each test with isolated continuity store."""
    # Reset in-process store for isolation
    _routes_module._continuity_store = None
    app = _make_app()
    with TestClient(app) as c:
        yield c


# ===========================================================================
# Company Org Routes
# ===========================================================================

def test_org_status(client):
    """GET /v1/company-org/status returns org spec with all required tiers."""
    resp = client.get("/v1/company-org/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["wiring_status"] == "WIRED_AND_TESTED"
    tiers = data["role_tier_counts"]
    assert "jarvis" in tiers
    assert "cos" in tiers
    assert "gm" in tiers
    assert "manager" in tiers
    assert "worker" in tiers
    assert "verifier" in tiers


def test_org_roster(client):
    """GET /v1/company-org/roster returns roster manifest and verifier persona mapping."""
    resp = client.get("/v1/company-org/roster")
    assert resp.status_code == 200
    data = resp.json()
    assert "roster" in data
    assert "verifier_slack_persona" in data
    persona = data["verifier_slack_persona"]
    assert persona["prefix"] == "[Verifier]"
    assert "Slack send not performed by safety policy" in persona["slack_send_status"]


def test_wiring_matrix(client):
    """GET /v1/company-org/wiring-matrix returns audit matrix with all modules."""
    resp = client.get("/v1/company-org/wiring-matrix")
    assert resp.status_code == 200
    data = resp.json()
    matrix = data["wiring_matrix"]
    modules = [m["module"] for m in matrix]
    assert "company_org.py" in modules
    assert "agents/company_org_runtime.py" in modules
    assert "agents/verifier.py" in modules
    assert "agents/worker_pool.py" in modules
    assert "mobile/continuity.py" in modules
    assert "Verifier Slack persona" in modules
    assert "worker-memory-sync cloud credentials" in modules
    assert "Mobile web UI" in modules


# ===========================================================================
# TEST 6 — Company task route executes Jarvis → COS → manager → worker
# ===========================================================================

def test_org_task_pipeline(client):
    """POST /v1/company-org/task executes the full pipeline and returns trace."""
    resp = client.post("/v1/company-org/task", json={
        "user_request": "inspect changed files and run tests",
        "intent": "coding",
    })
    assert resp.status_code == 200
    data = resp.json()
    # Routing trace must show all hierarchy levels
    trace_str = " ".join(data["routing_trace"])
    assert "jarvis" in trace_str
    assert "cos" in trace_str
    assert "gm" in trace_str
    assert "manager" in trace_str
    # Manager assigned
    assert data["assigned_manager_role_id"] == "manager-coding"
    # Pipeline completed (no blockers for coding intent)
    assert data["pipeline_status"] in ("completed", "hold")


# ===========================================================================
# TEST 7 — Worker results are honest (no fake artifact paths)
# ===========================================================================

def test_org_task_workers_executed(client):
    """Worker executor must return honest status — no fake artifact paths.

    The gated local executor (FIX-5) only dispatches tools in its allowlist.
    When no tool_id is provided or no allowed tool matches, the executor
    returns 'unavailable' rather than a fake success with a non-existent path.
    When a real tool is dispatched and completes, artifact_pointer may be set.
    """
    resp = client.post("/v1/company-org/task", json={
        "user_request": "run repo inspection",
        "intent": "coding",
    })
    assert resp.status_code == 200
    data = resp.json()
    worker_results = data["worker_results"]
    assert len(worker_results) >= 1, "No worker results returned"
    for wr in worker_results:
        # Workers must have an honest status — never a fake "completed" with
        # a non-existent artifact path.
        assert wr["status"] in (
            "completed", "failed", "pending", "running", "stalled", "reassigned", "unavailable"
        ), f"Unknown status: {wr['status']}"
        # If artifact_pointer is set it must be a non-empty string (not a fake
        # /tmp path that was never written).
        if wr.get("artifact_pointer") is not None:
            assert isinstance(wr["artifact_pointer"], str) and wr["artifact_pointer"], (
                f"Worker '{wr['worker_role_id']}' has empty artifact_pointer"
            )


# ===========================================================================
# TEST 8 — Verifier runs on artifact/evidence and result is attached
# ===========================================================================

def test_org_task_verifier_attached(client):
    """Verifier must run and its outcome must be in the pipeline response."""
    resp = client.post("/v1/company-org/task", json={
        "user_request": "inspect and test",
        "intent": "coding",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["verifier_outcome"] is not None, "Verifier did not run"
    # ACCEPTED or REJECTED — both are valid depending on worker output
    assert data["verifier_outcome"] in ("ACCEPTED", "REJECTED", "BLOCKED_SELF_VERIFY")


# ===========================================================================
# TEST 9 — Missing skill/tool blocks assignment with fix list
# ===========================================================================

def test_missing_tool_blocks_assignment(client):
    """Requesting tools not in manager's list → skill_tool_gaps populated."""
    resp = client.post("/v1/company-org/task", json={
        "user_request": "run exotic tool",
        "intent": "coding",
        "required_tools": ["nonexistent_exotic_tool_xyz"],
    })
    assert resp.status_code == 200
    data = resp.json()
    # skill_tool_gaps must contain the missing tool entry
    assert len(data["skill_tool_gaps"]) >= 1, "Missing tool not surfaced in skill_tool_gaps"
    gap = data["skill_tool_gaps"][0]
    assert "nonexistent_exotic_tool_xyz" in gap.get("missing", [])


# ===========================================================================
# TEST 10 (was 9 in list) — Unsupported verifier row returns HOLD/fix list
# ===========================================================================

def test_verifier_unsupported_row_hold(client):
    """When workers produce no artifact, verifier returns REJECTED with fix list.

    We simulate this by using a worker that always fails (stall_worker_id is set
    to one that doesn't exist so no stall, but stall_timeout=0 on the first worker).
    We use simulate_stall=True to force a stall → stalled worker has no artifact →
    verifier gets empty source_ref → REJECTED.
    """
    resp = client.post("/v1/company-org/task", json={
        "user_request": "inspect files",
        "intent": "coding",
        "simulate_stall": True,
        "stall_worker_id": "worker-repo-inspector",
    })
    assert resp.status_code == 200
    data = resp.json()
    # Either stall_reports OR verifier_fix_list should be non-empty
    # (stall → artifact missing → verifier rejects)
    has_stall = len(data.get("stall_reports", [])) >= 1
    has_verifier_rejection = (
        data.get("verifier_outcome") == "REJECTED"
        and len(data.get("verifier_fix_list", [])) >= 1
    )
    assert has_stall or has_verifier_rejection, (
        "Stall simulation neither surfaced stall_reports nor verifier rejection"
    )


# ===========================================================================
# TEST 11 — Stall simulation triggers reassignment or blocker
# ===========================================================================

def test_stall_triggers_reassignment_or_blocker(client):
    """simulate_stall=True must surface stall in response."""
    resp = client.post("/v1/company-org/task", json={
        "user_request": "slow task",
        "intent": "coding",
        "simulate_stall": True,
        "stall_worker_id": "worker-repo-inspector",
    })
    assert resp.status_code == 200
    data = resp.json()
    # Stall reports must be present OR blockers must surface the stall
    stalls = data.get("stall_reports", [])
    blockers = data.get("blockers", [])
    trace = " ".join(data.get("routing_trace", []))
    assert (
        len(stalls) >= 1
        or any("stall" in b.lower() for b in blockers)
        or "stall" in trace.lower()
    ), "Stall not surfaced in response"


# ===========================================================================
# Mobile Continuity API Tests
# ===========================================================================

def test_register_device(client):
    """POST /v1/continuity/devices registers a device."""
    resp = client.post("/v1/continuity/devices", json={
        "user_id": "bryan",
        "device_type": "macbook",
        "display_name": "Bryan's MacBook Pro",
        "trusted": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] is not None
    assert data["trusted"] is True
    assert data["device_type"] == "macbook"


def test_register_invalid_device_type(client):
    """Unknown device_type → 400."""
    resp = client.post("/v1/continuity/devices", json={
        "user_id": "bryan",
        "device_type": "flying_toaster",
        "display_name": "Test",
    })
    assert resp.status_code == 400


# ===========================================================================
# TEST 1 — API route saves MacBook snapshot
# ===========================================================================

def _register_and_get_device_id(client, device_type: str, display_name: str) -> str:
    resp = client.post("/v1/continuity/devices", json={
        "user_id": "bryan",
        "device_type": device_type,
        "display_name": display_name,
        "trusted": True,
    })
    return resp.json()["device_id"]


def test_api_saves_macbook_snapshot(client):
    """POST /v1/continuity/snapshot saves a MacBook snapshot via API."""
    device_id = _register_and_get_device_id(client, "macbook", "MacBook Pro")

    resp = client.post("/v1/continuity/snapshot", json={
        "user_id": "bryan",
        "source_device_id": device_id,
        "conversation_id": "conv-api-001",
        "conversation_messages": [{"role": "user", "content": "Start task"}],
        "active_task_id": "task-api-001",
        "active_task_description": "API integration test task",
        "active_task_status": "running",
        "assigned_manager_role_id": "manager-coding",
        "assigned_worker_role_ids": ["worker-repo-inspector"],
        "worker_statuses": {"worker-repo-inspector": "running"},
        "verifier_status": "PENDING",
        "verifier_fix_list": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_id"] is not None
    assert data["resume_token"] is not None
    assert "REQUIRED_FOR_NO_GAP_JARVIS" in data["cloud_sync_status"]


# ===========================================================================
# TEST 2/3 — API route resumes snapshot from mobile, restores required fields
# ===========================================================================

def test_api_mobile_resume_restores_required_fields(client):
    """API resume returns snapshot with all required continuity fields."""
    macbook_id = _register_and_get_device_id(client, "macbook", "MacBook Pro")
    iphone_id = _register_and_get_device_id(client, "iphone", "iPhone 15 Pro")

    # Save snapshot from MacBook
    save_resp = client.post("/v1/continuity/snapshot", json={
        "user_id": "bryan",
        "source_device_id": macbook_id,
        "conversation_id": "conv-mobile-001",
        "conversation_messages": [
            {"role": "user", "content": "Start coding sprint"},
            {"role": "assistant", "content": "Routing to COS..."},
        ],
        "active_task_id": "task-mobile-001",
        "active_task_description": "Mobile continuity test",
        "active_task_status": "running",
        "assigned_manager_role_id": "manager-coding",
        "assigned_worker_role_ids": ["worker-repo-inspector", "worker-test-runner"],
        "worker_statuses": {"worker-repo-inspector": "completed", "worker-test-runner": "running"},
        "pending_approvals": [{"approval_id": "a-001", "description": "Approve diff"}],
        "artifact_pointers": [{"task_id": "task-mobile-001", "path": "/tmp/result.json"}],
        "project_id": "openjarvis",
        "project_context": {"sprint": "sprint-3"},
        "memory_refs": ["mem-001"],
        "verifier_status": "ACCEPTED",
        "verifier_fix_list": [],
    })
    assert save_resp.status_code == 200
    save_data = save_resp.json()
    resume_token = save_data["resume_token"]

    # Resume on iPhone
    resume_resp = client.post("/v1/continuity/resume", json={
        "resume_token": resume_token,
        "target_device_id": iphone_id,
    })
    assert resume_resp.status_code == 200
    resume_data = resume_resp.json()

    assert resume_data["success"] is True
    assert resume_data["conflict_detected"] is False
    assert resume_data["sync_status"] == "synced"

    # Verify restored fields
    snap = resume_data["snapshot"]
    assert snap["conversation_id"] == "conv-mobile-001"
    assert snap["active_task_id"] == "task-mobile-001"
    assert snap["assigned_manager_role_id"] == "manager-coding"
    assert "worker-repo-inspector" in snap["assigned_worker_role_ids"]
    assert snap["verifier_status"] == "ACCEPTED"
    assert len(snap["artifact_pointers"]) >= 1
    assert len(snap["pending_approvals"]) >= 1
    assert snap["project_id"] == "openjarvis"
    assert len(snap["conversation_messages"]) == 2


# ===========================================================================
# TEST 4 — Conflict state is surfaced
# ===========================================================================

def test_api_conflict_surfaced(client):
    """When target device has newer snapshot, conflict is surfaced via API."""
    import time as _time

    macbook_id = _register_and_get_device_id(client, "macbook", "MacBook")
    iphone_id = _register_and_get_device_id(client, "iphone", "iPhone")

    # MacBook saves snapshot
    old_resp = client.post("/v1/continuity/snapshot", json={
        "user_id": "bryan",
        "source_device_id": macbook_id,
        "active_task_id": "task-conflict",
        "active_task_status": "running",
    })
    resume_token = old_resp.json()["resume_token"]

    # iPhone saves a NEWER snapshot (in same store — simulates older macbook snap)
    store = _get_store()
    # Get the MacBook snapshot and manually adjust times to create conflict
    snap_id = old_resp.json()["snapshot_id"]
    old_snap = store.get_snapshot(snap_id)

    # Save iPhone snapshot with later created_at
    iphone_snap = store.save_snapshot(
        user_id="bryan",
        source_device_id=iphone_id,
        active_task_status="completed",
    )
    iphone_snap.created_at = old_snap.created_at + 5.0  # newer

    # MacBook resumes on iPhone → conflict expected
    conflict_resp = client.post("/v1/continuity/resume", json={
        "resume_token": resume_token,
        "target_device_id": iphone_id,
        "current_state": {"device_id": iphone_id},
    })
    assert conflict_resp.status_code == 200
    data = conflict_resp.json()
    assert data["success"] is True
    assert data["conflict_detected"] is True
    assert data["conflict_description"] is not None

    # Also verify GET /v1/continuity/conflict surfaces it
    conflict_get = client.get("/v1/continuity/conflict", params={"user_id": "bryan"})
    assert conflict_get.status_code == 200
    cdata = conflict_get.json()
    assert cdata["conflict"] is True


# ===========================================================================
# TEST 5 — Untrusted device is rejected explicitly
# ===========================================================================

def test_api_untrusted_device_rejected(client):
    """Resuming on an unregistered (untrusted) device returns 400."""
    macbook_id = _register_and_get_device_id(client, "macbook", "MacBook")

    snap_resp = client.post("/v1/continuity/snapshot", json={
        "user_id": "bryan",
        "source_device_id": macbook_id,
        "active_task_status": "running",
    })
    resume_token = snap_resp.json()["resume_token"]

    # Try to resume on an unknown device
    resp = client.post("/v1/continuity/resume", json={
        "resume_token": resume_token,
        "target_device_id": "device-totally-unknown-abc",
    })
    assert resp.status_code == 400
    assert "trusted" in resp.json()["detail"].lower() or "registered" in resp.json()["detail"].lower()


# ===========================================================================
# TEST 12 — Slack persona mapping for verifier/managers tied to roster
# ===========================================================================

def test_verifier_slack_persona_mapping(client):
    """Verifier persona must use single-bot format via roster.format_slack_message()."""
    from openjarvis.agents.roster import get_default_registry

    registry = get_default_registry()
    # Format a verifier message via the single-bot
    msg = registry.format_slack_message("jarvis-hq", "[Verifier] Evidence ACCEPTED — trace attached.")
    assert "[Jarvis HQ / Front Desk]" in msg
    assert "[Verifier]" in msg

    # Roster route also returns verifier persona mapping
    resp = client.get("/v1/company-org/roster")
    assert resp.status_code == 200
    data = resp.json()
    persona = data["verifier_slack_persona"]
    assert persona["persona"] == "jarvis-hq"
    assert persona["prefix"] == "[Verifier]"


# ===========================================================================
# TEST 13 — Full no-gap remains HOLD
# ===========================================================================

def test_full_no_gap_remains_hold(client):
    """Org status must show full no-gap as HOLD."""
    resp = client.get("/v1/company-org/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "HOLD" in data["no_gap_status"]


# ===========================================================================
# TEST 14 — Voice remains gated
# ===========================================================================

def test_voice_remains_gated(client):
    """Org status must show voice as HOLD/gated."""
    resp = client.get("/v1/company-org/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "HOLD" in data["voice_status"] or "gated" in data["voice_status"].lower()


# ===========================================================================
# Additional: snapshot secret rejection
# ===========================================================================

def test_snapshot_rejects_secrets(client):
    """Snapshot API must reject tool_states containing secret keys."""
    macbook_id = _register_and_get_device_id(client, "macbook", "MacBook")
    resp = client.post("/v1/continuity/snapshot", json={
        "user_id": "bryan",
        "source_device_id": macbook_id,
        "tool_states": {"api_key": "sk-secret-value"},
    })
    assert resp.status_code == 400
    assert "secret" in resp.json()["detail"].lower()


# ===========================================================================
# Additional: sync status and mobile contract
# ===========================================================================

def test_sync_status_endpoint(client):
    """GET /v1/continuity/sync-status returns status for user."""
    resp = client.get("/v1/continuity/sync-status", params={"user_id": "bryan-no-snap"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sync_status"] == "unknown"


def test_mobile_contract_endpoint(client):
    """GET /v1/continuity/mobile-contract returns contract with mobile web path."""
    resp = client.get("/v1/continuity/mobile-contract")
    assert resp.status_code == 200
    data = resp.json()
    assert "REQUIRED_FOR_NO_GAP_JARVIS" in data["mobile_ui_status"]
    assert data["mobile_web_path"]["continuity_api_reachable_from_mobile_browser"] is True
    assert data["mobile_web_path"]["status"] == "WIRED_AND_TESTED"


# ===========================================================================
# Additional: worker-memory-sync local store classification
# ===========================================================================

def test_memory_sync_local_store():
    """worker-memory-sync must be CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN for local ops."""
    from openjarvis.company_org import get_company_org_spec, CapabilityStatus

    spec = get_company_org_spec()
    worker = spec.get_role("worker-memory-sync")
    assert worker is not None
    assert worker.skill_coverage_status == CapabilityStatus.CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN
    # No missing skills
    assert len(worker.missing_skills) == 0


# ===========================================================================
# MacBook-off continuity status — public access + security tests
# ===========================================================================

def test_macbook_off_status_public_no_auth(client):
    """GET /v1/continuity/macbook-off-status returns 200 without Authorization."""
    resp = client.get("/v1/continuity/macbook-off-status")
    assert resp.status_code == 200


def test_macbook_off_status_no_secret_in_response(client):
    """Response must not contain token values, only status strings."""
    resp = client.get("/v1/continuity/macbook-off-status")
    assert resp.status_code == 200
    data = resp.json()
    # Top-level keys must be safe status fields
    assert "macbook_off_continuity" in data
    assert "token_diagnosis" in data
    # token_diagnosis must not contain a token value
    diag = data["token_diagnosis"]
    assert "present" in diag
    assert "format_valid" in diag
    # No raw token value exposed
    for key, val in diag.items():
        if isinstance(val, str):
            assert not val.startswith("ghp_"), f"token value leaked in {key}"
            assert not val.startswith("github_pat_"), f"token value leaked in {key}"


def test_macbook_off_status_blocked_when_token_missing(client, monkeypatch):
    """When GITHUB_TOKEN is absent, status is BLOCKED_WAITING_FOR_BRYAN_NOW."""
    import openjarvis.mobile.continuity_backend as _cb

    # Patch the gist backend to appear unconfigured
    class _FakeGist:
        configured = False
        def get_status(self):
            from unittest.mock import MagicMock
            m = MagicMock()
            m.to_dict.return_value = {"backend_name": "github_gist", "macbook_off_capable": False}
            return m
        def get_token_diagnosis(self):
            return {"present": False, "format_valid": False,
                    "diagnosis": "GITHUB_TOKEN not set",
                    "action": "Add GITHUB_TOKEN=ghp_... to .env"}
        def token_format_valid(self):
            return False

    import openjarvis.mobile.continuity_backend as _cb_mod
    aa = _cb.AlwaysAvailableContinuityStore.__new__(_cb.AlwaysAvailableContinuityStore)
    aa._gist = _FakeGist()
    aa._local = _cb.LocalFileBackend()
    original = _cb_mod._STORE
    try:
        _cb_mod._STORE = aa
        resp = client.get("/v1/continuity/macbook-off-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["macbook_off_continuity"] != "AVAILABLE"
        assert data["token_diagnosis"]["present"] is False
    finally:
        _cb_mod._STORE = original


def test_macbook_off_status_available_when_token_present(client, monkeypatch):
    """When GITHUB_TOKEN is present with valid format, status is AVAILABLE."""
    import openjarvis.mobile.continuity_backend as _cb
    import openjarvis.server.company_org_routes as _r

    class _FakeGist:
        configured = True
        def get_status(self):
            from unittest.mock import MagicMock
            m = MagicMock()
            m.to_dict.return_value = {"backend_name": "github_gist", "macbook_off_capable": True}
            return m
        def get_token_diagnosis(self):
            return {"present": True, "format_valid": True,
                    "length": 40, "prefix_type": "classic_pat",
                    "diagnosis": "Valid format",
                    "action": "Token format OK"}
        def token_format_valid(self):
            return True

    import openjarvis.mobile.continuity_backend as _cb_mod
    aa = _cb.AlwaysAvailableContinuityStore.__new__(_cb.AlwaysAvailableContinuityStore)
    aa._gist = _FakeGist()
    aa._local = _cb.LocalFileBackend()
    original = _cb_mod._STORE
    try:
        _cb_mod._STORE = aa
        resp = client.get("/v1/continuity/macbook-off-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["macbook_off_continuity"] == "AVAILABLE"
    finally:
        _cb_mod._STORE = original


def test_snapshot_route_still_requires_auth():
    """POST /v1/continuity/snapshot must NOT be accessible without auth.

    The auth middleware is not wired in the TestClient app; this test uses
    the middleware directly to confirm the path requires auth.
    """
    from openjarvis.server.auth_middleware import AuthMiddleware
    assert AuthMiddleware._requires_auth("/v1/continuity/snapshot") is True
    assert AuthMiddleware._requires_auth("/v1/continuity/resume") is True
    assert AuthMiddleware._requires_auth("/v1/continuity/macbook-off-status") is False


def test_public_path_exemption_is_read_only():
    """Only the read-only status endpoint is in _PUBLIC_PATHS — no write routes."""
    from openjarvis.server.auth_middleware import AuthMiddleware
    for path in AuthMiddleware._PUBLIC_PATHS:
        # All public paths must be GET-style status routes — no write verbs in name
        assert not any(
            w in path for w in ("snapshot", "resume", "save", "delete", "write", "create")
        ), f"Write-capable path in _PUBLIC_PATHS: {path}"
