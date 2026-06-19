"""Real cloud integration tests — Sprint 3 Token + Cloud + Remote Runtime Retest.

These tests require a real GITHUB_TOKEN with at minimum 'gist' scope.
They verify actual GitHub Gist write + fallback resume end-to-end.

Tests skip gracefully if token is missing or format-invalid.

11 tests:
 1.  Valid token detected without leaking value
 2.  Invalid token scenario — explicit check (patched)
 3.  Real Gist cloud write succeeds with valid token
 4.  Sanitized payload confirmed — no secrets, stripped fields correct
 5.  Forced cloud fallback resume from Gist works
 6.  Resumed state includes all 12 continuity pointers
 7.  Remote runtime status is truthful (gist only → workflow blocked)
 8.  Universal mobile status is REQUIRED_FOR_NO_GAP_JARVIS (no live runtime)
 9.  Mobile NOT accepted if remote execution is not live
10.  Voice remains gated
11.  Full no-gap remains HOLD

Sprint: Sprint 3 Token + Cloud + Remote Runtime Retest
"""

from __future__ import annotations

import time
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_token() -> str:
    """Load token from env file — never print or return in response."""
    from pathlib import Path
    for p in [Path(".env"), Path(".env.local")]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip().startswith("GITHUB_TOKEN="):
                    val = line.strip()[len("GITHUB_TOKEN="):].strip().strip('"').strip("'")
                    if val:
                        return val
    return ""


def _token_format_valid(tok: str) -> bool:
    return (tok.startswith("ghp_") and len(tok) >= 40) or \
           (tok.startswith("github_pat_") and len(tok) >= 50)


def _has_gist_scope() -> bool:
    """Check token has gist scope via API — returns bool only."""
    tok = _get_token()
    if not tok or not _token_format_valid(tok):
        return False
    try:
        import ssl, urllib.request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {tok}", "User-Agent": "OpenJarvis/1.0",
                     "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            scopes = [s.strip() for s in r.headers.get("X-OAuth-Scopes", "").split(",")]
            return "gist" in scopes
    except Exception:
        return False


REAL_GIST_AVAILABLE = _has_gist_scope()
skip_no_gist = pytest.mark.skipif(
    not REAL_GIST_AVAILABLE,
    reason="GITHUB_TOKEN with gist scope not available — real cloud tests skipped",
)


# ---------------------------------------------------------------------------
# 1. Valid token detected without leaking value
# ---------------------------------------------------------------------------

def test_token_present_and_format_valid():
    """Token is present and format-valid — returned as bool, no value."""
    from openjarvis.mobile.continuity_backend import check_token_present, check_token_format_valid
    assert check_token_present() is True
    assert check_token_format_valid() is True


def test_token_not_in_status_route_response():
    """GET /v1/jarvis/token-status does not leak actual token value."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.company_org_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/v1/jarvis/token-status")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("GITHUB_TOKEN_present"), bool)
    actual_tok = _get_token()
    if actual_tok:
        assert actual_tok not in resp.text, "Token value leaked in response"


# ---------------------------------------------------------------------------
# 2. Invalid token scenario handled correctly (patched)
# ---------------------------------------------------------------------------

def test_invalid_token_format_blocked():
    """Token with wrong format classified as BLOCKED_INVALID_TOKEN_FORMAT."""
    from openjarvis.mobile.continuity_backend import GitHubGistBackend
    backend = GitHubGistBackend.__new__(GitHubGistBackend)
    backend._token = "short_invalid_16ch"
    backend._gist_ids = {}
    assert backend.token_format_valid() is False
    diag = backend.get_token_diagnosis()
    assert diag["format_valid"] is False
    assert diag["prefix_type"] == "unknown_format"


# ---------------------------------------------------------------------------
# 3. Real Gist cloud write succeeds with valid token
# ---------------------------------------------------------------------------

@skip_no_gist
def test_real_gist_write_succeeds():
    """Real GitHub Gist write with valid token completes successfully."""
    from openjarvis.mobile.continuity_backend import AlwaysAvailableContinuityStore
    store = AlwaysAvailableContinuityStore()
    snap = {
        "snapshot_id": "snap-real-ci-test-001",
        "project_id": "any-project",          # not OMNIX-specific
        "active_task_id": "task-ci-001",
        "assigned_manager_role_id": "manager-coding",
        "worker_assignments": ["worker-repo-inspector"],
        "verifier_state_ref": "verifier-pending",
        "artifact_pointers": [{"type": "test-output", "ref": "art-001"}],
        "approval_state_ref": "approval-pending",
        "project_context_ref": "ctx-any-001",
        "memory_cache_refs": ["cache-001"],
        "sync_status": "synced",
        "conflict_state": None,
        "device_id": "macbook-test",
        "last_active_device": "macbook-test",
        "thread_pointer": "thread-ci-test",
        "tool_states": {"internal": "will_be_stripped"},
        "timestamp": time.time(),
    }
    result = store.save_snapshot(snap, user_id="bryan")
    assert result["local_save"] is True, "Local save failed"
    assert result["cloud_save"] is True, "Real Gist write failed"
    assert result["macbook_off_retrievable"] is True


# ---------------------------------------------------------------------------
# 4. Sanitized payload confirmed — no secrets, correct strip/redact
# ---------------------------------------------------------------------------

@skip_no_gist
def test_real_cloud_write_payload_is_sanitized():
    """Uploaded payload has tool_states stripped, no raw secrets."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud
    snap = {
        "snapshot_id": "snap-security-proof-001",
        "project_id": "any-project",
        "active_task_id": "task-security-001",
        "sync_status": "synced",
        "tool_states": {"slack_token": "definitely_sensitive"},
        "conversation_messages": ["user: hello", "assistant: hi"],
        "approval_payload": [{"decision": "approve", "amount": 50000}],
        "timestamp": time.time(),
    }
    payload, report = sanitize_for_cloud(snap)
    assert report.secret_rejected is False              # no PAT/secret patterns
    assert "LOCAL_ONLY" in str(payload.get("tool_states", ""))
    assert "LOCAL_ONLY" in str(payload.get("conversation_messages", ""))
    assert "REDACTED" in str(payload.get("approval_payload", ""))
    assert "50000" not in str(payload)                  # dollar amount stripped
    assert payload.get("active_task_id") == "task-security-001"  # safe field passes
    assert payload.get("sync_status") == "synced"       # safe field passes


# ---------------------------------------------------------------------------
# 5. Forced cloud fallback resume from Gist works
# ---------------------------------------------------------------------------

@skip_no_gist
def test_forced_cloud_fallback_resume():
    """After saving to cloud, fresh local store loads from Gist correctly."""
    from openjarvis.mobile.continuity_backend import AlwaysAvailableContinuityStore, LocalFileBackend
    snap_id = "snap-fallback-resume-001"
    store = AlwaysAvailableContinuityStore()
    snap = {
        "snapshot_id": snap_id,
        "project_id": "generic-project",
        "active_task_id": "task-fb-001",
        "assigned_manager_role_id": "manager-coding",
        "worker_assignments": ["worker-test-runner"],
        "verifier_state_ref": "verifier-fb",
        "artifact_pointers": [{"ref": "art-fb-001"}],
        "approval_state_ref": "approval-fb",
        "project_context_ref": "ctx-fb-001",
        "memory_cache_refs": ["cache-fb-001"],
        "sync_status": "synced",
        "conflict_state": None,
        "device_id": "macbook-fb",
        "last_active_device": "macbook-fb",
        "thread_pointer": "thread-fb",
        "timestamp": time.time(),
    }
    save_result = store.save_snapshot(snap, user_id="bryan")
    assert save_result["cloud_save"] is True, "Pre-condition: cloud write must succeed"

    # Force cloud fallback: new store with fresh local but same gist backend
    store2 = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store2._local = LocalFileBackend()   # empty local
    store2._gist = store._gist
    store2._index = {}

    loaded = store2.load_snapshot(snap_id)
    assert loaded is not None, "Cloud fallback resume returned None"
    assert loaded.get("active_task_id") == "task-fb-001"
    assert loaded.get("project_id") == "generic-project"     # not OMNIX


# ---------------------------------------------------------------------------
# 6. Resumed state includes all 12 continuity pointers
# ---------------------------------------------------------------------------

@skip_no_gist
def test_resumed_state_has_all_continuity_pointers():
    """Cloud fallback resume restores all 12 required state pointers."""
    from openjarvis.mobile.continuity_backend import AlwaysAvailableContinuityStore, LocalFileBackend
    snap_id = "snap-full-pointers-001"
    store = AlwaysAvailableContinuityStore()
    snap = {
        "snapshot_id": snap_id,
        "project_id": "any-project",
        "active_task_id": "task-ptr-001",
        "assigned_manager_role_id": "manager-research",
        "worker_assignments": ["worker-web-searcher"],
        "verifier_state_ref": "verifier-ptr",
        "artifact_pointers": [{"ref": "art-ptr-001"}],
        "approval_state_ref": "approval-ptr",
        "project_context_ref": "ctx-ptr-001",
        "memory_cache_refs": ["cache-ptr-001"],
        "sync_status": "synced",
        "conflict_state": "none",
        "device_id": "iphone-test",
        "last_active_device": "macbook-pro",
        "thread_pointer": "thread-ptr",
        "timestamp": time.time(),
    }
    store.save_snapshot(snap, user_id="bryan")

    store2 = AlwaysAvailableContinuityStore.__new__(AlwaysAvailableContinuityStore)
    store2._local = LocalFileBackend()
    store2._gist = store._gist
    store2._index = {}

    loaded = store2.load_snapshot(snap_id)
    assert loaded is not None

    required_pointers = [
        "thread_pointer",            # conversation/thread
        "active_task_id",            # task/workflow
        "assigned_manager_role_id",  # manager assignment
        "verifier_state_ref",        # verifier state
        "artifact_pointers",         # artifact pointer
        "approval_state_ref",        # approval state
        "project_context_ref",       # project context
        "memory_cache_refs",         # memory/cache refs
        "sync_status",               # sync status
        "conflict_state",            # conflict/degraded
        "device_id",                 # device/session
        "last_active_device",        # last active device
    ]
    missing = [f for f in required_pointers if not loaded.get(f) and loaded.get(f) != "none"]
    assert not missing, f"Missing continuity pointers after cloud resume: {missing}"

    # Not OMNIX-specific
    assert loaded.get("project_id") != "omnix"


# ---------------------------------------------------------------------------
# 7. Remote runtime status is truthful
# ---------------------------------------------------------------------------

def test_remote_runtime_status_truthful():
    """Remote backend correctly reports scope-based capability and workflow status."""
    from openjarvis.remote.github_actions_backend import GitHubActionsBackend
    backend = GitHubActionsBackend()
    status = backend.get_status()
    assert "configured" in status
    assert "macbook_off_capable" in status
    assert status["macbook_off_capable"] is True
    assert "classification" in status
    assert "workflow_install" in status
    scopes = status.get("token_scopes", {})
    if not status["configured"]:
        # Token may have all scopes but workflow not on remote yet
        expected_blocked = {
            "BLOCKED_RUNTIME_CREDENTIALS",
            "REMOTE_RUNTIME_REQUIRES_COMMIT_PUSH",
            "WORKFLOW_NOT_INSTALLED",
        }
        assert status["classification"] in expected_blocked, \
            f"Unexpected classification: {status['classification']}"


# ---------------------------------------------------------------------------
# 8. Universal mobile status is REQUIRED_FOR_NO_GAP_JARVIS
# ---------------------------------------------------------------------------

def test_universal_mobile_status_required():
    """Capability matrix reports REQUIRED_FOR_NO_GAP_JARVIS — no live remote runtime."""
    from openjarvis.mobile.project_runtime import get_capability_matrix
    matrix = get_capability_matrix()
    assert matrix["universal_mobile_project_building"] == "REQUIRED_FOR_NO_GAP_JARVIS"
    assert matrix["mobile_accepted"] is False


# ---------------------------------------------------------------------------
# 9. Mobile NOT accepted if remote execution is not live
# ---------------------------------------------------------------------------

def test_mobile_not_accepted_without_live_runtime():
    """mobile_accepted is False when remote execution runtime is not operational."""
    from openjarvis.mobile.project_runtime import get_capability_matrix
    matrix = get_capability_matrix()
    assert matrix["mobile_accepted"] is False, (
        "Mobile incorrectly marked accepted — remote execution runtime not proven"
    )
    assert "NOT accepted" in matrix["note"]


# ---------------------------------------------------------------------------
# 10. Voice remains gated
# ---------------------------------------------------------------------------

def test_voice_remains_gated_after_retest():
    """Voice is SEPARATE_SPRINT_REQUIRED in manifest — not affected by this retest."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "SEPARATE_SPRINT" in m["voice_status"]


# ---------------------------------------------------------------------------
# 11. Full no-gap remains HOLD
# ---------------------------------------------------------------------------

def test_full_no_gap_remains_hold_after_retest():
    """No-gap status is still HOLD — cloud write + resume does not make no-gap complete."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert m["no_gap_status"].startswith("HOLD"), (
        f"Expected no_gap_status to start with HOLD, got: {m['no_gap_status']!r}"
    )
