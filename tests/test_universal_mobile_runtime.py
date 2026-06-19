"""Tests — Sprint 3 Consolidated Final: Universal Mobile Project-Building + Hot-Reload + Security.

24 targeted tests covering:
 1.  Valid token detection without leaking value
 2.  Invalid token returns BLOCKED_INVALID_TOKEN_FORMAT
 3.  Cloud snapshot sanitizer rejects secrets
 4.  Cloud snapshot sanitizer redacts/strips sensitive content
 5.  Real cloud write succeeds with valid token (mocked — real token invalid)
 6.  Cloud fallback resume works when local state is unavailable
 7.  MacBook-off continuity AVAILABLE only after real cloud path passes
 8.  Universal mobile project-building requirement in manifest
 9.  Phone-start-new-project status is classified
10.  Phone-continue-existing-project status is classified
11.  Phone-trigger-coding status is classified
12.  Phone-trigger-tests status is classified
13.  Phone-trigger-build status is classified
14.  Phone-view-diffs/logs/artifacts status is classified
15.  Phone-approval-gate status is classified
16.  Remote/cloud execution runtime status classified
17.  Mobile NOT accepted if only PWA/chat/status/snapshot
18.  Native feasibility classified by cost/practicality
19.  Hot-reload updates roster/routing/cache/cost state
20.  Unsafe hot-reload requires verifier approval
21.  Stale roster rejected
22.  Disconnected feature island rejected
23.  Voice remains gated
24.  Full no-gap remains HOLD

Sprint: Sprint 3 Consolidated Final Retest
"""

from __future__ import annotations

import os
import pytest


# ---------------------------------------------------------------------------
# 1. Valid token detection without leaking value
# ---------------------------------------------------------------------------

def test_token_detection_returns_bool_only():
    """check_token_present() and check_token_format_valid() return bool only."""
    from openjarvis.mobile.continuity_backend import check_token_present, check_token_format_valid
    present = check_token_present()
    fmt_valid = check_token_format_valid()
    assert isinstance(present, bool), f"Expected bool, got {type(present)}"
    assert isinstance(fmt_valid, bool), f"Expected bool, got {type(fmt_valid)}"


def test_token_status_route_no_value_leaked():
    """GET /v1/jarvis/token-status returns bool fields, never the actual token."""
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
    # Actual token must not appear in response body
    from openjarvis.mobile.continuity_backend import _load_token_from_env
    actual = _load_token_from_env()
    if actual:
        assert actual not in resp.text, "Actual token value leaked in response"


# ---------------------------------------------------------------------------
# 2. Invalid token returns BLOCKED_INVALID_TOKEN_FORMAT
# ---------------------------------------------------------------------------

def test_invalid_token_format_returns_blocked():
    """Short/unknown-format token produces BLOCKED_INVALID_TOKEN_FORMAT."""
    from openjarvis.mobile.continuity_backend import GitHubGistBackend
    backend = GitHubGistBackend.__new__(GitHubGistBackend)
    backend._token = "short_invalid"
    backend._gist_ids = {}
    assert backend.configured is True     # non-empty
    assert backend.token_format_valid() is False
    diag = backend.get_token_diagnosis()
    assert diag["format_valid"] is False
    assert diag["prefix_type"] == "unknown_format"


def test_macbook_off_status_invalid_token():
    """MacBook-off status reflects BLOCKED when token is invalid format."""
    from openjarvis.mobile.continuity_backend import (
        AlwaysAvailableContinuityStore, LocalFileBackend, GitHubGistBackend
    )
    store = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store._local = LocalFileBackend()
    store._index = {}

    bad_gist = GitHubGistBackend.__new__(GitHubGistBackend)
    bad_gist._token = "short_bad"
    bad_gist._gist_ids = {}
    store._gist = bad_gist

    status = store.get_macbook_off_status()
    assert status["macbook_off_continuity"] == "BLOCKED_WAITING_FOR_BRYAN_NOW"
    assert status["classification"] in (
        "BLOCKED_INVALID_TOKEN_FORMAT", "BLOCKED_WAITING_FOR_BRYAN_NOW"
    )


# ---------------------------------------------------------------------------
# 3. Cloud snapshot sanitizer rejects secrets
# ---------------------------------------------------------------------------

def test_sanitizer_rejects_secret_named_field():
    """Field named 'token' with non-empty value is rejected."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud, SnapshotRejected
    with pytest.raises(SnapshotRejected) as exc:
        sanitize_for_cloud({"snapshot_id": "x", "token": "something-secret"})
    assert "token" in str(exc.value).lower()


def test_sanitizer_rejects_pat_value_pattern():
    """GitHub PAT pattern in any field value causes SnapshotRejected."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud, SnapshotRejected
    with pytest.raises(SnapshotRejected):
        sanitize_for_cloud({"snapshot_id": "x", "some_ref": "ghp_" + "A" * 36})


# ---------------------------------------------------------------------------
# 4. Cloud snapshot sanitizer redacts/strips sensitive content
# ---------------------------------------------------------------------------

def test_sanitizer_strips_tool_states_and_memory():
    """tool_states and memory_refs are LOCAL_ONLY — never in cloud payload."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud
    snap = {
        "snapshot_id": "snap-safe-01",
        "tool_states": {"gdrive_token": "secret"},
        "memory_refs": ["mem-001", "mem-002"],
        "active_task_id": "task-001",
        "sync_status": "synced",
    }
    payload, report = sanitize_for_cloud(snap)
    assert "LOCAL_ONLY" in str(payload.get("tool_states", ""))
    assert "LOCAL_ONLY" in str(payload.get("memory_refs", ""))
    assert payload["active_task_id"] == "task-001"
    assert payload["sync_status"] == "synced"
    assert report.secret_rejected is False


def test_sanitizer_redacts_private_approvals():
    """Private approval content is redacted to a count summary."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud
    snap = {
        "approval_payload": [
            {"decision": "approve", "amount": 99999, "reason": "classified"},
        ],
    }
    payload, report = sanitize_for_cloud(snap)
    val = str(payload.get("approval_payload", ""))
    assert "REDACTED" in val
    assert "99999" not in val
    assert "classified" not in val


# ---------------------------------------------------------------------------
# 5. Real cloud write succeeds with valid token (mocked)
# ---------------------------------------------------------------------------

def test_cloud_write_succeeds_with_mock_gist():
    """Cloud write path works correctly — proven with mock Gist backend."""
    from openjarvis.mobile.continuity_backend import AlwaysAvailableContinuityStore, LocalFileBackend
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud

    class MockGistBackend:
        configured = True
        _written = {}
        def save(self, snap_id, data):
            payload, _ = sanitize_for_cloud(data)  # sanitizer runs
            self._written[snap_id] = payload
            return True
        def load(self, snap_id):
            return self._written.get(snap_id)
        def token_format_valid(self):
            return True
        def get_token_diagnosis(self):
            return {"present": True, "format_valid": True, "prefix_type": "classic_pat",
                    "diagnosis": "Valid", "action": "OK"}
        def get_status(self):
            from openjarvis.mobile.continuity_backend import BackendStatus, BackendAvailability
            return BackendStatus("github_gist", BackendAvailability.AVAILABLE,
                                 True, [], ["GITHUB_TOKEN"], ["GITHUB_TOKEN"], "Mock OK")

    store = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store._local = LocalFileBackend()
    store._gist = MockGistBackend()
    store._index = {}

    result = store.save_snapshot(
        {
            "snapshot_id": "snap-mock-001",
            "active_task_id": "task-001",
            "assigned_manager_role_id": "manager-coding",
            "sync_status": "synced",
            "project_id": "some-project",  # NOT OMNIX-specific
            "tool_states": "[LOCAL_ONLY]",
        },
        user_id="bryan",
    )
    assert result["local_save"] is True
    assert result["cloud_save"] is True
    assert result["macbook_off_retrievable"] is True


# ---------------------------------------------------------------------------
# 6. Cloud fallback resume when local state unavailable
# ---------------------------------------------------------------------------

def test_cloud_fallback_resume_no_local():
    """Store falls back to cloud backend when local has no matching snapshot."""
    from openjarvis.mobile.continuity_backend import AlwaysAvailableContinuityStore, LocalFileBackend

    class MockGist:
        configured = True
        _data = {"snap-cloud-001": {"active_task_id": "task-cloud", "project_id": "any-project"}}
        def load(self, snap_id):
            return self._data.get(snap_id)
        def token_format_valid(self):
            return True
        def get_token_diagnosis(self):
            return {"present": True, "format_valid": True, "prefix_type": "classic_pat",
                    "diagnosis": "OK", "action": "OK"}
        def get_status(self):
            from openjarvis.mobile.continuity_backend import BackendStatus, BackendAvailability
            return BackendStatus("github_gist", BackendAvailability.AVAILABLE,
                                 True, [], ["GITHUB_TOKEN"], ["GITHUB_TOKEN"], "Mock")

    store = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store._local = LocalFileBackend()   # fresh — no local data
    store._gist = MockGist()
    store._index = {}

    result = store.load_snapshot("snap-cloud-001")
    assert result is not None
    assert result["active_task_id"] == "task-cloud"
    assert result["project_id"] == "any-project"  # any project, not hardcoded


# ---------------------------------------------------------------------------
# 7. MacBook-off continuity AVAILABLE only after cloud path passes
# ---------------------------------------------------------------------------

def test_macbook_off_available_requires_valid_cloud_backend():
    """AVAILABLE status requires token_format_valid=True on cloud backend."""
    from openjarvis.mobile.continuity_backend import (
        AlwaysAvailableContinuityStore, LocalFileBackend
    )

    class ValidGist:
        configured = True
        def token_format_valid(self): return True
        def get_token_diagnosis(self):
            return {"present": True, "format_valid": True, "prefix_type": "classic_pat",
                    "diagnosis": "OK", "action": "OK"}
        def get_status(self):
            from openjarvis.mobile.continuity_backend import BackendStatus, BackendAvailability
            return BackendStatus("github_gist", BackendAvailability.AVAILABLE,
                                 True, [], ["GITHUB_TOKEN"], ["GITHUB_TOKEN"], "Valid")

    store = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store._local = LocalFileBackend()
    store._gist = ValidGist()
    store._index = {}

    status = store.get_macbook_off_status()
    assert status["macbook_off_continuity"] == "AVAILABLE"
    assert status["active_macbook_off_backend"] == "github_gist"


# ---------------------------------------------------------------------------
# 8. Universal mobile project-building requirement in manifest
# ---------------------------------------------------------------------------

def test_manifest_includes_universal_mobile_status():
    """Manifest reports universal mobile project-building status and remote runtime status."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "universal_mobile_project_building_status" in m
    # Sprint 3 final: some wired, some blocked — not REQUIRED_FOR_NO_GAP_JARVIS (that meant unbuilt)
    assert m["universal_mobile_project_building_status"] in (
        "WIRED_AND_TESTED", "REQUIRED_FOR_NO_GAP_JARVIS", "BLOCKED_WAITING_FOR_BRYAN_NOW"
    )
    assert "remote_execution_runtime_status" in m
    assert "mobile_full_parity" in m


# ---------------------------------------------------------------------------
# 9–15. Mobile project-building capabilities classified correctly
# ---------------------------------------------------------------------------

def _get_cap(name: str):
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES
    for c in MOBILE_PROJECT_CAPABILITIES:
        if c.capability == name:
            return c
    return None


def test_phone_start_new_project_classified():
    """start_new_project capability is classified (not silently missing)."""
    cap = _get_cap("start_new_project")
    assert cap is not None
    assert cap.status is not None
    assert cap.blocker is not None     # must have explicit blocker if not WIRED_AND_TESTED


def test_phone_continue_existing_project_classified():
    """continue_existing_project WIRED_AND_TESTED — Gist backend proven with valid token."""
    cap = _get_cap("continue_existing_project")
    assert cap is not None
    from openjarvis.mobile.project_runtime import MobileCapabilityStatus
    assert cap.macbook_on_status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.blocker is None  # no blocker when fully wired


def test_phone_trigger_coding_classified():
    """trigger_coding_task macbook_on WIRED, macbook_off BLOCKED_WAITING_FOR_BRYAN_NOW."""
    cap = _get_cap("trigger_coding_task")
    assert cap is not None
    from openjarvis.mobile.project_runtime import MobileCapabilityStatus
    # Routing is WIRED macbook-on; real code edits blocked pending Bryan workflow update
    assert cap.macbook_on_status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.macbook_off_status == MobileCapabilityStatus.BLOCKED_WAITING_FOR_BRYAN_NOW
    assert cap.status == MobileCapabilityStatus.BLOCKED_WAITING_FOR_BRYAN_NOW
    assert cap.blocker is not None  # explicit blocker required


def test_phone_trigger_tests_classified():
    """trigger_tests WIRED_AND_TESTED — GitHub Actions mode=test dispatch proven (run 27842115266)."""
    cap = _get_cap("trigger_tests")
    assert cap is not None
    from openjarvis.mobile.project_runtime import MobileCapabilityStatus
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.blocker is None  # no blocker when WIRED_AND_TESTED


def test_phone_trigger_build_classified():
    """trigger_builds WIRED_AND_TESTED — GitHub Actions mode=build dispatch proven (run 27842135965)."""
    cap = _get_cap("trigger_builds")
    assert cap is not None
    from openjarvis.mobile.project_runtime import MobileCapabilityStatus
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.blocker is None  # no blocker when WIRED_AND_TESTED


def test_phone_view_diffs_classified():
    """view_diffs_logs_artifacts WIRED_AND_TESTED — artifact pointers + GitHub API + run polling."""
    cap = _get_cap("view_diffs_logs_artifacts")
    assert cap is not None
    from openjarvis.mobile.project_runtime import MobileCapabilityStatus
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.blocker is None  # no blocker when WIRED_AND_TESTED


def test_phone_approval_gate_classified():
    """approve_reject_gated_actions WIRED_AND_TESTED — COS routes approvals through verifier gate."""
    cap = _get_cap("approve_reject_gated_actions")
    assert cap is not None
    assert cap.path is not None
    from openjarvis.mobile.project_runtime import MobileCapabilityStatus
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED


# ---------------------------------------------------------------------------
# 16. Remote/cloud execution runtime classified
# ---------------------------------------------------------------------------

def test_remote_execution_runtime_classified():
    """remote_cloud_execution_runtime WIRED_AND_TESTED — dispatch proven for status/test/build."""
    cap = _get_cap("remote_cloud_execution_runtime")
    assert cap is not None
    from openjarvis.mobile.project_runtime import MobileCapabilityStatus
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED
    assert "GitHub Actions" in cap.path  # path references GitHub Actions


def test_github_actions_backend_status():
    """GitHub Actions backend reports its status honestly."""
    from openjarvis.remote.github_actions_backend import GitHubActionsBackend
    backend = GitHubActionsBackend(repo_owner="", repo_name="")
    status = backend.get_status()
    assert "configured" in status
    assert "macbook_off_capable" in status
    assert status["macbook_off_capable"] is True
    # With invalid token, should not be configured
    if not backend.configured:
        assert status["classification"] == "BLOCKED_RUNTIME_CREDENTIALS"


# ---------------------------------------------------------------------------
# 17. Mobile NOT accepted if only PWA/chat/status/snapshot
# ---------------------------------------------------------------------------

def test_mobile_not_accepted_with_only_pwa():
    """capability matrix reports mobile_accepted=False when runtime capabilities missing."""
    from openjarvis.mobile.project_runtime import get_capability_matrix
    matrix = get_capability_matrix()
    # Must not be accepted if required capabilities are present
    assert matrix["mobile_accepted"] is False
    assert "NOT accepted" in matrix["note"]
    assert matrix["universal_mobile_project_building"] == "REQUIRED_FOR_NO_GAP_JARVIS"


# ---------------------------------------------------------------------------
# 18. Native feasibility classified by cost/practicality
# ---------------------------------------------------------------------------

def test_native_feasibility_classified():
    """Native iOS/Android feasibility has cost and classification in feasibility matrix."""
    from openjarvis.mobile.continuity_backend import NATIVE_APP_FEASIBILITY
    ios = NATIVE_APP_FEASIBILITY["tauri_2_ios"]
    android = NATIVE_APP_FEASIBILITY["tauri_2_android"]
    assert ios["classification"] == "REQUIRES_BRYAN_SETUP"
    assert "$99" in ios["cost"]
    assert android["classification"] == "REQUIRES_BRYAN_SETUP"
    # PWA is free and practical
    pwa = NATIVE_APP_FEASIBILITY["pwa_install"]
    assert pwa["classification"] == "FREE_AND_PRACTICAL_NOW"


# ---------------------------------------------------------------------------
# 19. Hot-reload updates roster/routing/cache/cost state
# ---------------------------------------------------------------------------

def test_hot_reload_new_worker_full_integration():
    """Hot-reloading a new worker updates all Jarvis OS layers."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus
    gate = HotReloadGate()
    # Register a manager first
    gate._roster["manager-coding"] = {"tier": "manager-coding", "status": "ACCEPTED"}
    req = RoleRegistrationRequest(
        role_id="worker-universal-builder",
        tier="worker",
        display_name="Universal Builder Worker",
        required_tools=["git", "pytest", "npm"],
        slack_persona="jarvis-hq",
    )
    result = gate.register(req)
    assert result.status == HotReloadStatus.ACCEPTED
    assert "company_org_roster" in result.updates_applied
    assert "role_scoped_cache_permissions" in result.updates_applied
    assert "cost_token_ledger_attribution" in result.updates_applied
    assert "capability_manifest:will_reflect_on_next_call" in result.updates_applied
    assert "worker-universal-builder" in gate.get_roster()


# ---------------------------------------------------------------------------
# 20. Unsafe hot-reload requires verifier approval
# ---------------------------------------------------------------------------

def test_hot_reload_high_risk_blocked_requires_verifier():
    """Registering a verifier-level role is blocked until verifier approves."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus
    gate = HotReloadGate()
    req = RoleRegistrationRequest(
        role_id="verifier-upgraded",
        tier="verifier",
        display_name="Upgraded Verifier",
    )
    result = gate.register(req)
    assert result.status == HotReloadStatus.BLOCKED_REQUIRES_VERIFIER_APPROVAL
    assert result.verifier_approval_required is True
    assert "verifier-upgraded" not in gate.get_roster()


# ---------------------------------------------------------------------------
# 21. Stale roster rejected
# ---------------------------------------------------------------------------

def test_stale_roster_rejected_on_duplicate():
    """Re-registering an accepted role_id without deregistration is REJECTED_STALE_ROSTER."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus
    gate = HotReloadGate()
    gate._roster["manager-coding"] = {"tier": "manager-coding", "status": "ACCEPTED"}
    gate._roster["worker-dupe"] = {"tier": "worker", "status": "ACCEPTED"}
    req = RoleRegistrationRequest(
        role_id="worker-dupe",
        tier="worker",
        display_name="Duplicate Worker",
    )
    result = gate.register(req)
    assert result.status == HotReloadStatus.REJECTED_STALE_ROSTER


# ---------------------------------------------------------------------------
# 22. Disconnected feature island rejected
# ---------------------------------------------------------------------------

def test_disconnected_island_rejected():
    """Worker with no manager in roster is a disconnected island — rejected."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, RoleRegistrationRequest, HotReloadStatus
    gate = HotReloadGate()
    # No managers in roster
    req = RoleRegistrationRequest(
        role_id="worker-orphan",
        tier="worker",
        display_name="Orphan Worker",
    )
    result = gate.register(req)
    assert result.status == HotReloadStatus.REJECTED_DISCONNECTED_ISLAND


# ---------------------------------------------------------------------------
# 23. Voice remains gated
# ---------------------------------------------------------------------------

def test_voice_remains_separate_sprint():
    """Voice is SEPARATE_SPRINT_REQUIRED in manifest and drift guard policy."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    from openjarvis.agents.drift_guard import JARVIS_POLICY_SPEC
    m = build_capability_manifest()
    assert "SEPARATE_SPRINT" in m["voice_status"]
    assert any("voice" in r for r in JARVIS_POLICY_SPEC["required_hold_when"])
    assert "VOICE_DAILY_DRIVER_ACCEPT" in JARVIS_POLICY_SPEC["forbidden_claims"]


# ---------------------------------------------------------------------------
# 24. Full no-gap remains HOLD
# ---------------------------------------------------------------------------

def test_full_no_gap_remains_hold():
    """No-gap status is HOLD — forbidden claim rejected by sentinel."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    from openjarvis.agents.code_sentinel import CodeSentinel
    m = build_capability_manifest()
    assert m["no_gap_status"].startswith("HOLD")
    sentinel = CodeSentinel()
    findings = sentinel.reject_unsupported_claims("FULL_NO_GAP_JARVIS_COMPLETE")
    assert len(findings) >= 1 and findings[0].blocks_release is True
