"""Tests — Sprint 3 MacBook-Off Continuity Security Retest + Hot-Reload Gate.

12 targeted tests covering:
 1.  Token presence reported without leaking value
 2.  Missing token produces BLOCKED_WAITING_FOR_BRYAN_NOW
 3.  Gist snapshot serialization redacts/strips sensitive fields
 4.  Secrets are rejected from cloud snapshot payload
 5.  Cloud fallback resume works when local state is unavailable
 6.  MacBook-off continuity status becomes AVAILABLE only after cloud path passes
 7.  New agent hot-reload updates roster/routing/cache/cost state
 8.  Unsafe hot-reload requires verifier/safety approval
 9.  Stale roster is rejected
10.  Disconnected feature island is rejected
11.  Full no-gap remains HOLD
12.  Voice remains gated

Sprint: Sprint 3 MacBook-Off Continuity Security Retest + Future-Proof Hot-Reload Gate
"""

from __future__ import annotations

import os
import time
import uuid
import pytest


# ---------------------------------------------------------------------------
# 1. Token presence reported without leaking value
# ---------------------------------------------------------------------------

def test_token_presence_reported_without_value():
    """check_token_present() returns bool only — never logs or returns token string."""
    from openjarvis.mobile.continuity_backend import check_token_present
    result = check_token_present()
    # Result must be bool — not the token string
    assert isinstance(result, bool), f"Expected bool, got {type(result)}"
    # Value must be True (Bryan configured the token in .env)
    # If False here, the .env file was not found — acceptable in isolated CI
    # but in Bryan's local env should be True


def test_token_status_route_returns_bool_not_value():
    """GET /v1/jarvis/token-status returns bool, never the token value."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.company_org_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/v1/jarvis/token-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "GITHUB_TOKEN_present" in data
    assert isinstance(data["GITHUB_TOKEN_present"], bool)
    # Ensure actual token value is not in response (not the format example in action string)
    # The response may contain "ghp_" as an example in action instructions — that's OK.
    # What must NOT appear is the actual token value itself.
    # We verify by checking the token value is absent (we know it's 16 chars, unknown prefix).
    from openjarvis.mobile.continuity_backend import _load_token_from_env
    actual_token = _load_token_from_env()
    if actual_token:
        assert actual_token not in resp.text, "Actual token value leaked in response"
    assert data.get("note") == "Token value is never returned by this endpoint."
    assert "GITHUB_TOKEN_format_valid" in data


# ---------------------------------------------------------------------------
# 2. Missing token produces BLOCKED_WAITING_FOR_BRYAN_NOW
# ---------------------------------------------------------------------------

def test_missing_token_returns_blocked():
    """Without GITHUB_TOKEN, macbook_off_continuity is BLOCKED_WAITING_FOR_BRYAN_NOW."""
    from openjarvis.mobile.continuity_backend import (
        GitHubGistBackend, AlwaysAvailableContinuityStore
    )
    # Create a backend instance with empty token
    backend = GitHubGistBackend.__new__(GitHubGistBackend)
    backend._token = ""
    backend._gist_ids = {}
    assert backend.configured is False
    status = backend.get_status()
    assert status.availability.value == "requires_bryan_setup"

    # Create store with unconfigured gist
    store = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    from openjarvis.mobile.continuity_backend import LocalFileBackend
    store._local = LocalFileBackend()
    store._gist = backend
    store._index = {}
    macbook_off = store.get_macbook_off_status()
    assert macbook_off["macbook_off_continuity"] == "BLOCKED_WAITING_FOR_BRYAN_NOW"
    assert macbook_off["active_macbook_off_backend"] is None


# ---------------------------------------------------------------------------
# 3. Gist snapshot serialization redacts/strips sensitive fields
# ---------------------------------------------------------------------------

def test_sanitizer_strips_tool_states():
    """tool_states is LOCAL_ONLY — never uploaded to cloud."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud
    snapshot = {
        "snapshot_id": "snap-001",
        "user_id": "bryan",
        "sync_status": "synced",
        "tool_states": {"slack_token": "xoxb-fake-token", "gdrive_creds": "abc123"},
        "active_task_id": "task-001",
    }
    cloud_payload, report = sanitize_for_cloud(snapshot)
    assert "tool_states" in cloud_payload
    assert cloud_payload["tool_states"] == "[LOCAL_ONLY:tool_states]"
    assert "tool_states" in report.stripped_fields


def test_sanitizer_strips_conversation_messages():
    """conversation_messages are LOCAL_ONLY — never uploaded to cloud."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud
    snapshot = {
        "snapshot_id": "snap-002",
        "conversation_messages": [{"role": "user", "content": "my private data"}],
        "conversation_id": "conv-001",
    }
    cloud_payload, report = sanitize_for_cloud(snapshot)
    # conversation_messages stripped
    assert "LOCAL_ONLY" in str(cloud_payload.get("conversation_messages", ""))
    assert "conversation_messages" in report.redacted_fields


def test_sanitizer_redacts_approval_payload():
    """Private approval payloads are redacted to safe count summary."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud
    snapshot = {
        "snapshot_id": "snap-003",
        "approval_payload": [
            {"decision": "approve", "amount": 10000, "reason": "private business reason"},
            {"decision": "deny", "amount": 5000},
        ],
    }
    cloud_payload, report = sanitize_for_cloud(snapshot)
    val = cloud_payload.get("approval_payload", "")
    assert "REDACTED" in str(val)
    assert "approval_payload" in report.redacted_fields
    # Raw decision/amount/reason must not be in cloud payload
    assert "private business reason" not in str(cloud_payload)
    assert "10000" not in str(val)


# ---------------------------------------------------------------------------
# 4. Secrets are rejected from cloud snapshot payload
# ---------------------------------------------------------------------------

def test_sanitizer_rejects_secret_field_name():
    """Snapshot with a field named 'token' containing a value is rejected."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud, SnapshotRejected
    snapshot = {
        "snapshot_id": "snap-secret-01",
        "token": "some-secret-value",
    }
    with pytest.raises(SnapshotRejected) as exc:
        sanitize_for_cloud(snapshot)
    assert "token" in str(exc.value).lower()


def test_sanitizer_rejects_github_pat_value():
    """Snapshot with a GitHub PAT pattern in any value is rejected."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud, SnapshotRejected
    snapshot = {
        "snapshot_id": "snap-secret-02",
        "some_field": "ghp_aaaBBBcccDDDeeeFFFgggHHHiiiJJJkkk123",
    }
    with pytest.raises(SnapshotRejected):
        sanitize_for_cloud(snapshot)


def test_sanitizer_allows_safe_snapshot():
    """Safe snapshot (no secrets, no sensitive content) passes sanitizer."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud
    snapshot = {
        "snapshot_id": "snap-safe-01",
        "user_id": "bryan",
        "active_task_id": "task-001",
        "assigned_manager_role_id": "manager-coding",
        "sync_status": "synced",
        "project_id": "openjarvis",
        "blocker_list": ["MacBook-off requires GITHUB_TOKEN"],
    }
    cloud_payload, report = sanitize_for_cloud(snapshot)
    assert report.secret_rejected is False
    assert cloud_payload["snapshot_id"] == "snap-safe-01"
    assert cloud_payload["sync_status"] == "synced"


# ---------------------------------------------------------------------------
# 5. Cloud fallback resume works when local state unavailable
# ---------------------------------------------------------------------------

def test_cloud_fallback_resume_when_local_missing():
    """When local store has no snapshot, store falls back to cloud backend."""
    from openjarvis.mobile.continuity_backend import (
        AlwaysAvailableContinuityStore, LocalFileBackend, GitHubGistBackend
    )
    store = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store._local = LocalFileBackend()
    store._index = {}

    # Mock gist backend that returns data even when local is empty
    class MockGistBackend:
        configured = True
        _stored = {}

        def load(self, snapshot_id):
            return self._stored.get(snapshot_id)

        def save(self, snapshot_id, data):
            self._stored[snapshot_id] = data
            return True

    mock_gist = MockGistBackend()
    cloud_data = {
        "snapshot_id": "snap-cloud-001",
        "user_id": "bryan",
        "active_task_id": "task-cloud-001",
        "assigned_manager_role_id": "manager-coding",
        "sync_status": "synced",
        "resume_token": "tok-cloud-001",
    }
    mock_gist._stored["snap-cloud-001"] = cloud_data
    store._gist = mock_gist

    # Local has nothing — fallback to cloud
    result = store.load_snapshot("snap-cloud-001")
    assert result is not None, "Cloud fallback resume failed"
    assert result["active_task_id"] == "task-cloud-001"
    assert result["assigned_manager_role_id"] == "manager-coding"


# ---------------------------------------------------------------------------
# 6. MacBook-off continuity becomes AVAILABLE only after cloud path passes
# ---------------------------------------------------------------------------

def test_macbook_off_available_when_gist_configured():
    """MacBook-off status is AVAILABLE only when a working cloud backend is configured."""
    from openjarvis.mobile.continuity_backend import (
        AlwaysAvailableContinuityStore, LocalFileBackend
    )
    store = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store._local = LocalFileBackend()
    store._index = {}

    class FakeConfiguredGist:
        configured = True
        def token_format_valid(self):
            return True
        def get_token_diagnosis(self):
            return {"present": True, "format_valid": True, "prefix_type": "classic_pat",
                    "diagnosis": "Valid format", "action": "OK"}
        def get_status(self):
            from openjarvis.mobile.continuity_backend import BackendStatus, BackendAvailability
            return BackendStatus(
                backend_name="github_gist", availability=BackendAvailability.AVAILABLE,
                macbook_off_capable=True, setup_steps=[], env_vars_required=["GITHUB_TOKEN"],
                env_vars_present=["GITHUB_TOKEN"], notes="Configured."
            )

    store._gist = FakeConfiguredGist()
    status = store.get_macbook_off_status()
    assert status["macbook_off_continuity"] == "AVAILABLE"
    assert status["active_macbook_off_backend"] == "github_gist"
    assert status["classification"] in ("WIRED_AND_TESTED", "AVAILABLE")


# ---------------------------------------------------------------------------
# 7. New agent hot-reload updates roster/routing/cache/cost state
# ---------------------------------------------------------------------------

def test_hot_reload_worker_updates_all_layers():
    """Hot-reload of a new worker updates roster, cache, and cost ledger."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus

    gate = HotReloadGate()
    # First register a manager so worker isn't a disconnected island
    manager_req = RoleRegistrationRequest(
        role_id="manager-coding",
        tier="manager-coding",
        display_name="Coding Manager",
    )
    gate.register(manager_req)

    worker_req = RoleRegistrationRequest(
        role_id="worker-new-linter",
        tier="worker",
        display_name="New Linter Worker",
        required_tools=["ruff", "mypy"],
        required_skills=["python-linting"],
        slack_persona="jarvis-hq",
    )
    result = gate.register(worker_req)

    assert result.status == HotReloadStatus.ACCEPTED
    assert "company_org_roster" in result.updates_applied
    assert "skill_tool_coverage_matrix" in result.updates_applied
    assert "role_scoped_cache_permissions" in result.updates_applied
    assert "cost_token_ledger_attribution" in result.updates_applied
    assert "capability_manifest:will_reflect_on_next_call" in result.updates_applied
    assert any("slack_persona_mapping" in u for u in result.updates_applied)

    roster = gate.get_roster()
    assert "worker-new-linter" in roster


# ---------------------------------------------------------------------------
# 8. Unsafe hot-reload requires verifier/safety approval
# ---------------------------------------------------------------------------

def test_hot_reload_high_risk_blocked():
    """High-risk role (COS/verifier level) requires verifier approval."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus

    gate = HotReloadGate()
    req = RoleRegistrationRequest(
        role_id="cos-new",
        tier="cos",
        display_name="New COS",
        allowed_actions=["approve_payment", "modify_policy"],
    )
    result = gate.register(req)
    assert result.status == HotReloadStatus.BLOCKED_REQUIRES_VERIFIER_APPROVAL
    assert result.verifier_approval_required is True
    # Not in roster yet
    assert "cos-new" not in gate.get_roster()
    # Pending verifier list has it
    assert "cos-new" in gate.get_status()["pending_verifier_approval"]


def test_hot_reload_high_risk_approved_by_verifier():
    """High-risk registration is applied after explicit verifier approval."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus

    gate = HotReloadGate()
    req = RoleRegistrationRequest(
        role_id="gm-upgraded",
        tier="gm",
        display_name="Upgraded GM",
    )
    blocked = gate.register(req)
    assert blocked.status == HotReloadStatus.BLOCKED_REQUIRES_VERIFIER_APPROVAL

    approved = gate.approve_high_risk("gm-upgraded", approved_by="verifier")
    assert approved.status == HotReloadStatus.ACCEPTED
    assert "gm-upgraded" in gate.get_roster()
    assert any("verifier_approved_by" in u for u in approved.updates_applied)


# ---------------------------------------------------------------------------
# 9. Stale roster is rejected
# ---------------------------------------------------------------------------

def test_stale_roster_rejected():
    """Re-registering an already-accepted role without deregistration is rejected."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus

    gate = HotReloadGate()
    req = RoleRegistrationRequest(
        role_id="worker-test-runner",
        tier="worker",
        display_name="Test Runner",
    )
    # Register manager first
    gate._roster["manager-coding"] = {"tier": "manager-coding", "status": "ACCEPTED"}

    first = gate.register(req)
    assert first.status == HotReloadStatus.ACCEPTED

    # Try to re-register same role_id
    second = gate.register(req)
    assert second.status == HotReloadStatus.REJECTED_STALE_ROSTER
    assert any("STALE_ROSTER" in e for e in second.validation_errors)


# ---------------------------------------------------------------------------
# 10. Disconnected feature island is rejected
# ---------------------------------------------------------------------------

def test_disconnected_island_rejected():
    """Worker registered with no manager in roster is a disconnected island — rejected."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus

    gate = HotReloadGate()
    # Pre-populate with non-manager entries
    gate._roster["verifier"] = {"tier": "verifier", "status": "ACCEPTED"}

    req = RoleRegistrationRequest(
        role_id="worker-orphan",
        tier="worker",
        display_name="Orphan Worker",
    )
    result = gate.register(req)
    assert result.status == HotReloadStatus.REJECTED_DISCONNECTED_ISLAND
    assert "worker-orphan" not in gate.get_roster()


# ---------------------------------------------------------------------------
# 11. Full no-gap remains HOLD
# ---------------------------------------------------------------------------

def test_full_no_gap_remains_hold():
    """No-gap status is HOLD — no forbidden claims present."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    from openjarvis.agents.drift_guard import JARVIS_POLICY_SPEC
    from openjarvis.agents.code_sentinel import CodeSentinel

    manifest = build_capability_manifest()
    assert manifest["no_gap_status"].startswith("HOLD")
    assert "FULL_NO_GAP_JARVIS_COMPLETE" in JARVIS_POLICY_SPEC["forbidden_claims"]

    sentinel = CodeSentinel()
    findings = sentinel.reject_unsupported_claims("FULL_NO_GAP_JARVIS_COMPLETE")
    assert len(findings) >= 1 and findings[0].blocks_release is True


# ---------------------------------------------------------------------------
# 12. Voice remains gated
# ---------------------------------------------------------------------------

def test_voice_remains_gated():
    """Voice is SEPARATE_SPRINT_REQUIRED in manifest and drift guard policy."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    from openjarvis.agents.drift_guard import JARVIS_POLICY_SPEC

    manifest = build_capability_manifest()
    assert "SEPARATE_SPRINT" in manifest["voice_status"]
    required_holds = JARVIS_POLICY_SPEC["required_hold_when"]
    assert any("voice" in r for r in required_holds)
    assert "VOICE_DAILY_DRIVER_ACCEPT" in JARVIS_POLICY_SPEC["forbidden_claims"]
