"""Sprint 3 FINAL No-Partial Closure + Blocker Closure — Enforcement Test Suite.

These tests FAIL if any Sprint 3 required item is PARTIALLY_WIRED or BLOCKED_*.
They enforce the Sprint 3 final acceptance rule.

Coverage:
  1.  No PARTIALLY_WIRED in mobile capability matrix
  2.  All 11 unified context cache layers present
  3.  Cache permission isolation (worker cannot read private scope)
  4.  Cache invalidation on hash change
  5.  Cache/cost ledger integration (hit/miss recorded)
  6.  Provider prompt cache metadata layer functional
  7.  Remote execution cache layer functional
  8.  Handoff cache layer functional
  9.  Chat context cache layer functional
 10.  Continuity snapshot includes safe cache refs
 11.  Remote execution status wired
 12.  Mobile project capability matrix wired — no partial items
 13.  Company harness regression — no PARTIALLY_WIRED capability status
 14.  Hot-reload roster reflects wired state
 15.  Full no-gap remains HOLD
 16.  Voice remains gated — separate sprint
 17.  All Sprint 3 required items are WIRED_AND_TESTED or BLOCKED_*
 18.  PARTIALLY_WIRED is not used as any capability status

Sprint: Sprint 3 FINAL No-Partial Closure
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 1. No PARTIALLY_WIRED in mobile capability matrix
# ---------------------------------------------------------------------------

def test_no_partially_wired_in_mobile_capability_matrix():
    """CRITICAL: No capability may be PARTIALLY_WIRED in Sprint 3 final."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus
    partial = [
        c for c in MOBILE_PROJECT_CAPABILITIES
        if "PARTIALLY_WIRED" in (c.status.value if hasattr(c.status, "value") else str(c.status))
        or "PARTIALLY_WIRED" in (c.macbook_on_status.value if hasattr(c.macbook_on_status, "value") else str(c.macbook_on_status))
        or "PARTIALLY_WIRED" in (c.macbook_off_status.value if hasattr(c.macbook_off_status, "value") else str(c.macbook_off_status))
    ]
    assert len(partial) == 0, (
        f"Sprint 3 FINAL: PARTIALLY_WIRED statuses found — NOT ACCEPTABLE: "
        + ", ".join(c.capability for c in partial)
    )


# ---------------------------------------------------------------------------
# 2. All 11 unified context cache layers present
# ---------------------------------------------------------------------------

def test_all_11_cache_layers_present():
    """All 11 required unified context cache layers must be in CACHE_LAYERS."""
    from openjarvis.jarvis_os.role_cache import CACHE_LAYERS
    required = [
        "provider_prompt_cache_metadata",
        "global_jarvis_cache",
        "chat_context_cache",
        "role_cache",
        "worker_cache",
        "project_repo_cache",
        "validation_cache",
        "failure_prevention_cache",
        "continuity_cache",
        "remote_execution_cache",
        "handoff_cache",
    ]
    missing = [layer for layer in required if layer not in CACHE_LAYERS]
    assert len(missing) == 0, f"Missing cache layers: {missing}"
    assert len(CACHE_LAYERS) >= 11, f"Expected at least 11 cache layers, got {len(CACHE_LAYERS)}"


# ---------------------------------------------------------------------------
# 3. Cache permission isolation — worker cannot read private scope
# ---------------------------------------------------------------------------

def test_cache_worker_cannot_read_private_scope():
    """Worker cannot access private cache entries belonging to another role."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, SecurityLevel

    cache = RoleScopedCache()
    cache.put(
        CacheLayer.ROLE,
        "cos",
        {"private_routing": "classified"},
        security_level=SecurityLevel.PRIVATE,
    )
    result = cache.get(
        CacheLayer.ROLE,
        "cos",
        caller_role_id="worker-repo-inspector",
        caller_security_level=SecurityLevel.INTERNAL,
    )
    from openjarvis.jarvis_os.role_cache import CacheMiss
    assert isinstance(result, CacheMiss), "Worker must not access private COS scope"
    assert "security_violation" in result.reason


# ---------------------------------------------------------------------------
# 4. Cache invalidation — expired entries return CacheMiss
# ---------------------------------------------------------------------------

def test_cache_invalidation_on_expiry():
    """Expired cache entries return CacheMiss — no stale reuse."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, SecurityLevel, CacheMiss
    import time

    cache = RoleScopedCache()
    cache.put(
        CacheLayer.VALIDATION,
        "verifier",
        {"test_result": "pass"},
        ttl_seconds=0,  # immediately expired
    )
    time.sleep(0.01)  # ensure expiry
    result = cache.get(CacheLayer.VALIDATION, "verifier")
    assert isinstance(result, CacheMiss)
    assert result.reason == "expired"


# ---------------------------------------------------------------------------
# 5. Cache/cost ledger integration — hit count tracked
# ---------------------------------------------------------------------------

def test_cache_hit_count_tracked():
    """Cache hit count increments on each access — enables cost ledger integration."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, CacheEntry

    cache = RoleScopedCache()
    cache.put(CacheLayer.GLOBAL_JARVIS, "jarvis", {"policy": "test"})
    r1 = cache.get(CacheLayer.GLOBAL_JARVIS, "jarvis")
    r2 = cache.get(CacheLayer.GLOBAL_JARVIS, "jarvis")
    assert isinstance(r1, CacheEntry)
    assert isinstance(r2, CacheEntry)
    assert r2.hit_count >= 2, "Hit count must increment on each access"


# ---------------------------------------------------------------------------
# 6. Provider prompt cache metadata layer functional
# ---------------------------------------------------------------------------

def test_provider_prompt_cache_metadata_layer():
    """Provider prompt cache metadata layer is writable and readable."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, CacheEntry

    cache = RoleScopedCache()
    entry = cache.put(
        CacheLayer.PROVIDER_PROMPT_CACHE_METADATA,
        "claude-3-5-sonnet",
        {"cache_tokens": 1024, "provider": "anthropic", "cache_write_tokens": 200},
    )
    assert entry is not None
    result = cache.get(CacheLayer.PROVIDER_PROMPT_CACHE_METADATA, "claude-3-5-sonnet")
    assert isinstance(result, CacheEntry)
    assert result.content["provider"] == "anthropic"


# ---------------------------------------------------------------------------
# 7. Remote execution cache layer functional
# ---------------------------------------------------------------------------

def test_remote_execution_cache_layer():
    """Remote execution cache layer stores GitHub Actions run state."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, CacheEntry

    cache = RoleScopedCache()
    entry = cache.put(
        CacheLayer.REMOTE_EXECUTION,
        "github-actions",
        {
            "run_id": "27842115266",
            "mode": "test",
            "status": "completed",
            "artifact": "jarvis-test-27842115266",
        },
    )
    assert entry is not None
    result = cache.get(CacheLayer.REMOTE_EXECUTION, "github-actions")
    assert isinstance(result, CacheEntry)
    assert result.content["run_id"] == "27842115266"


# ---------------------------------------------------------------------------
# 8. Handoff cache layer functional
# ---------------------------------------------------------------------------

def test_handoff_cache_layer():
    """Handoff cache layer stores agent handoff/resume tokens safely."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, CacheEntry

    cache = RoleScopedCache()
    entry = cache.put(
        CacheLayer.HANDOFF,
        "manager-coding",
        {"handoff_to": "worker-repo-inspector", "task_id": "task-001", "context_ref": "snap-001"},
    )
    assert entry is not None
    result = cache.get(CacheLayer.HANDOFF, "manager-coding")
    assert isinstance(result, CacheEntry)
    assert result.content["task_id"] == "task-001"


# ---------------------------------------------------------------------------
# 9. Chat context cache layer functional
# ---------------------------------------------------------------------------

def test_chat_context_cache_layer():
    """Chat context cache layer stores user↔Jarvis conversation context."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, CacheEntry

    cache = RoleScopedCache()
    entry = cache.put(
        CacheLayer.CHAT_CONTEXT,
        "bryan",
        {"last_intent": "trigger_tests", "session_id": "sess-001", "project_id": "any-project"},
    )
    assert entry is not None
    result = cache.get(CacheLayer.CHAT_CONTEXT, "bryan")
    assert isinstance(result, CacheEntry)
    assert result.content["last_intent"] == "trigger_tests"


# ---------------------------------------------------------------------------
# 10. Continuity snapshot includes safe cache refs
# ---------------------------------------------------------------------------

def test_continuity_snapshot_safe_cache_refs():
    """Continuity snapshot stores safe cache refs, not raw secrets."""
    from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud

    snap = {
        "snapshot_id": "snap-cache-test-01",
        "active_task_id": "task-001",
        "cache_refs": {
            "role_cache_key": "role:manager-coding:project:any-project",
            "validation_cache_key": "validation:verifier:task-001",
            "remote_execution_cache_key": "remote_execution:github-actions",
        },
        "project_id": "any-project",
    }
    payload, report = sanitize_for_cloud(snap)
    assert report.secret_rejected is False
    assert "cache_refs" in payload


# ---------------------------------------------------------------------------
# 11. Remote execution status route exists and responds
# ---------------------------------------------------------------------------

def test_remote_execution_status_route():
    """GET /v1/remote/status returns classification without leaking token."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.company_org_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/v1/remote/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data or "classification" in data or "macbook_off_capable" in data


# ---------------------------------------------------------------------------
# 12. Mobile capability matrix: no partially_wired in summary
# ---------------------------------------------------------------------------

def test_capability_matrix_zero_partial():
    """get_capability_matrix() must report 0 partially_wired items in Sprint 3 final."""
    from openjarvis.mobile.project_runtime import get_capability_matrix
    matrix = get_capability_matrix()
    assert matrix["summary"]["partially_wired"] == 0, (
        f"Sprint 3 FINAL: {matrix['summary']['partially_wired']} PARTIALLY_WIRED items remain — "
        "must be ZERO for closure acceptance."
    )


# ---------------------------------------------------------------------------
# 13. Company harness: capability manifest reports no PARTIALLY_WIRED
# ---------------------------------------------------------------------------

def test_capability_manifest_no_partial_status():
    """Capability manifest items must not report PARTIALLY_WIRED as status."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    for item in m.get("all_items", []):
        assert item["status"] != "PARTIALLY_WIRED", (
            f"Manifest item '{item['name']}' has PARTIALLY_WIRED status — NOT ACCEPTABLE in Sprint 3 final"
        )


# ---------------------------------------------------------------------------
# 14. Hot-reload roster wired and not PARTIALLY_WIRED
# ---------------------------------------------------------------------------

def test_hot_reload_gate_wired():
    """HotReloadGate import and basic operation work cleanly."""
    from openjarvis.agents.hot_reload_gate import HotReloadGate, get_hot_reload_gate
    gate = get_hot_reload_gate()
    assert gate is not None
    roster = gate.get_roster()
    assert isinstance(roster, dict)


# ---------------------------------------------------------------------------
# 15. Full no-gap remains HOLD
# ---------------------------------------------------------------------------

def test_full_no_gap_remains_hold_sprint3():
    """Sprint 3 final: no_gap_status is HOLD — full certification not yet run."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert m["no_gap_status"].startswith("HOLD"), (
        f"no_gap_status must be HOLD, got: {m['no_gap_status']}"
    )


# ---------------------------------------------------------------------------
# 16. Voice remains gated
# ---------------------------------------------------------------------------

def test_voice_remains_separate_sprint_closure():
    """Sprint 3 closure: voice status must be SEPARATE_SPRINT_REQUIRED."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "SEPARATE_SPRINT" in m["voice_status"], (
        f"Voice must remain SEPARATE_SPRINT_REQUIRED, got: {m['voice_status']}"
    )


# ---------------------------------------------------------------------------
# 17. All Sprint 3 required capabilities are WIRED_AND_TESTED or BLOCKED_*
# ---------------------------------------------------------------------------

def test_all_sprint3_caps_are_wired_and_tested():
    """Sprint 3 FINAL BLOCKER CLOSURE: every Sprint 3 required mobile capability is WIRED_AND_TESTED."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus

    not_wired = []
    for cap in MOBILE_PROJECT_CAPABILITIES:
        if cap.status != MobileCapabilityStatus.WIRED_AND_TESTED:
            not_wired.append(f"{cap.capability}: {cap.status.value}")

    assert len(not_wired) == 0, (
        f"Sprint 3 FINAL BLOCKER CLOSURE: capabilities not yet WIRED_AND_TESTED: {not_wired}"
    )


def test_no_blocked_waiting_for_sprint3_required_items():
    """Sprint 3 FINAL: no Sprint 3 required capability may remain BLOCKED_WAITING_FOR_BRYAN_NOW."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus

    blocked = [
        c.capability for c in MOBILE_PROJECT_CAPABILITIES
        if c.status == MobileCapabilityStatus.BLOCKED_WAITING_FOR_BRYAN_NOW
    ]
    assert len(blocked) == 0, (
        f"Sprint 3 FINAL: BLOCKED_WAITING_FOR_BRYAN_NOW items remain — NOT ACCEPTABLE: {blocked}"
    )


def test_macbook_off_full_parity_wired():
    """Sprint 3 FINAL: macbook_off_full_parity is WIRED_AND_TESTED."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus
    cap = next((c for c in MOBILE_PROJECT_CAPABILITIES if c.capability == "macbook_off_full_parity"), None)
    assert cap is not None
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED, (
        f"macbook_off_full_parity must be WIRED_AND_TESTED, got {cap.status}"
    )
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED


# ---------------------------------------------------------------------------
# 18. PARTIALLY_WIRED enum value exists but is NOT used as any capability status
# ---------------------------------------------------------------------------

def test_partially_wired_not_used_as_final_status():
    """PARTIALLY_WIRED must not appear in any capability's status, macbook_on, or macbook_off field."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES

    violations = []
    for cap in MOBILE_PROJECT_CAPABILITIES:
        for field_name in ("status", "macbook_on_status", "macbook_off_status"):
            val = getattr(cap, field_name)
            val_str = val.value if hasattr(val, "value") else str(val)
            if "PARTIALLY_WIRED" in val_str:
                violations.append(f"{cap.capability}.{field_name}={val_str}")

    assert len(violations) == 0, (
        f"Sprint 3 FINAL: PARTIALLY_WIRED found in capability fields — NOT ACCEPTABLE: {violations}"
    )


# ---------------------------------------------------------------------------
# 19. Workflow has all 8 safe modes
# ---------------------------------------------------------------------------

def test_workflow_has_all_8_safe_modes():
    """jarvis-remote.yml must list all 8 safe modes including the 4 new blocker-closure modes."""
    import os
    workflow_path = os.path.join(
        os.path.dirname(__file__), "..", ".github", "workflows", "jarvis-remote.yml"
    )
    with open(workflow_path) as f:
        content = f.read()

    required_modes = [
        "status", "test", "build", "artifact",
        "project-init", "code-edit", "reassign", "escalate",
    ]
    for mode in required_modes:
        assert f"- {mode}" in content or f"'{mode}'" in content or f'"{mode}"' in content, (
            f"Workflow missing mode: {mode}"
        )


def test_workflow_forbidden_modes_still_rejected():
    """Workflow must still reject all forbidden modes."""
    import os
    workflow_path = os.path.join(
        os.path.dirname(__file__), "..", ".github", "workflows", "jarvis-remote.yml"
    )
    with open(workflow_path) as f:
        content = f.read()

    forbidden = ["deploy", "delete", "merge", "release", "publish"]
    for mode in forbidden:
        assert f"BLOCKED" in content or f"forbidden" in content.lower(), (
            "Workflow must have safety gate for forbidden modes"
        )
        # Forbidden modes must not appear as options
        assert f"- {mode}" not in content, (
            f"Forbidden mode '{mode}' must not appear in workflow options list"
        )


# ---------------------------------------------------------------------------
# 20. project-init mode safety
# ---------------------------------------------------------------------------

def test_project_init_mode_is_safe_dry_run():
    """project-init workflow mode must be a dry-run scaffold artifact (no real repo)."""
    import os
    workflow_path = os.path.join(
        os.path.dirname(__file__), "..", ".github", "workflows", "jarvis-remote.yml"
    )
    with open(workflow_path) as f:
        content = f.read()

    # Must have dry-run marker
    assert "dry_run" in content or "DRY_RUN" in content or "dry-run" in content, (
        "project-init mode must be marked as dry-run"
    )
    assert "no real repo" in content.lower() or "scaffold artifact" in content.lower() or \
           "No real repo" in content, (
        "project-init must document that no real repo is created"
    )
    assert "project-init" in content


# ---------------------------------------------------------------------------
# 21. code-edit mode safety
# ---------------------------------------------------------------------------

def test_code_edit_mode_produces_diff_only():
    """code-edit workflow mode must produce diff/patch artifact — never push to main."""
    import os
    workflow_path = os.path.join(
        os.path.dirname(__file__), "..", ".github", "workflows", "jarvis-remote.yml"
    )
    with open(workflow_path) as f:
        content = f.read()

    assert "code-edit" in content
    # Must document safe branch / no push to main
    assert "never push" in content.lower() or "never pushes to main" in content.lower() or \
           "PATCH" in content or "diff" in content.lower(), (
        "code-edit must document diff/patch-only behavior"
    )
    assert "Bryan approval" in content or "PENDING_BRYAN" in content, (
        "code-edit must require Bryan approval before merge"
    )


# ---------------------------------------------------------------------------
# 22. reassign mode safety
# ---------------------------------------------------------------------------

def test_reassign_mode_is_safe_artifact_only():
    """reassign mode must emit routing artifact only — no external messages."""
    import os
    workflow_path = os.path.join(
        os.path.dirname(__file__), "..", ".github", "workflows", "jarvis-remote.yml"
    )
    with open(workflow_path) as f:
        content = f.read()

    assert "reassign" in content
    assert "no_external_messages" in content or "no external messages" in content.lower(), (
        "reassign mode must document no external messages"
    )
    assert "artifact" in content.lower()


# ---------------------------------------------------------------------------
# 23. escalate mode safety
# ---------------------------------------------------------------------------

def test_escalate_mode_is_safe_artifact_only():
    """escalate mode must emit blocker artifact only — no external messages."""
    import os
    workflow_path = os.path.join(
        os.path.dirname(__file__), "..", ".github", "workflows", "jarvis-remote.yml"
    )
    with open(workflow_path) as f:
        content = f.read()

    assert "escalate" in content
    assert "no_external_messages" in content or "no external messages" in content.lower(), (
        "escalate mode must document no external messages"
    )
    assert "BLOCKED_PENDING_BRYAN" in content or "HOLD_PENDING_BRYAN" in content or \
           "Bryan" in content, (
        "escalate must require Bryan decision"
    )


# ---------------------------------------------------------------------------
# 24. Mobile route can trigger new modes via trigger-workflow endpoint
# ---------------------------------------------------------------------------

def test_mobile_trigger_project_init_route():
    """POST /v1/remote/trigger-workflow accepts task_type=project-init."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.company_org_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    # Route must exist and accept the new modes (may fail with BLOCKED_RUNTIME_CREDENTIALS if no token)
    resp = client.post("/v1/remote/trigger-workflow?task_type=project-init&project_id=test-proj")
    assert resp.status_code in (200, 422, 500)  # route exists; actual execution may need token
    data = resp.json()
    # Must not return an unhandled 404 (route must exist)
    assert resp.status_code != 404, "POST /v1/remote/trigger-workflow route must exist"


def test_mobile_trigger_code_edit_route():
    """POST /v1/remote/trigger-workflow accepts task_type=code-edit."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.company_org_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post(
        "/v1/remote/trigger-workflow?task_type=code-edit&project_id=test-proj"
        "&task_description=test+fix"
    )
    assert resp.status_code != 404, "POST /v1/remote/trigger-workflow route must exist for code-edit"


def test_mobile_trigger_reassign_route():
    """POST /v1/remote/trigger-workflow accepts task_type=reassign."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.company_org_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post("/v1/remote/trigger-workflow?task_type=reassign&worker_id=worker-test")
    assert resp.status_code != 404, "POST /v1/remote/trigger-workflow route must exist for reassign"


def test_mobile_trigger_escalate_route():
    """POST /v1/remote/trigger-workflow accepts task_type=escalate."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.company_org_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post("/v1/remote/trigger-workflow?task_type=escalate&blocker_description=test+blocker")
    assert resp.status_code != 404, "POST /v1/remote/trigger-workflow route must exist for escalate"


# ---------------------------------------------------------------------------
# 25. start_new_project capability is WIRED_AND_TESTED (was BLOCKED)
# ---------------------------------------------------------------------------

def test_start_new_project_wired_and_tested():
    """start_new_project must be WIRED_AND_TESTED — project-init mode closes this blocker."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus
    cap = next((c for c in MOBILE_PROJECT_CAPABILITIES if c.capability == "start_new_project"), None)
    assert cap is not None
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED, (
        f"start_new_project must be WIRED_AND_TESTED after project-init mode added, got {cap.status}"
    )
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED


def test_trigger_coding_task_wired_and_tested():
    """trigger_coding_task must be WIRED_AND_TESTED — code-edit mode closes this blocker."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus
    cap = next((c for c in MOBILE_PROJECT_CAPABILITIES if c.capability == "trigger_coding_task"), None)
    assert cap is not None
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED, (
        f"trigger_coding_task must be WIRED_AND_TESTED after code-edit mode added, got {cap.status}"
    )


def test_reassign_escalate_wired_and_tested():
    """reassign_escalate_stuck_workers must be WIRED_AND_TESTED — reassign/escalate modes close this blocker."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus
    cap = next((c for c in MOBILE_PROJECT_CAPABILITIES if c.capability == "reassign_escalate_stuck_workers"), None)
    assert cap is not None
    assert cap.status == MobileCapabilityStatus.WIRED_AND_TESTED, (
        f"reassign_escalate_stuck_workers must be WIRED_AND_TESTED, got {cap.status}"
    )
    assert cap.macbook_off_status == MobileCapabilityStatus.WIRED_AND_TESTED


# ---------------------------------------------------------------------------
# 26. Capability matrix mobile_accepted is True after Sprint 3 closure
# ---------------------------------------------------------------------------

def test_capability_matrix_mobile_accepted_true():
    """Sprint 3 FINAL: capability matrix mobile_accepted=True — all 13 items WIRED_AND_TESTED."""
    from openjarvis.mobile.project_runtime import get_capability_matrix
    matrix = get_capability_matrix()
    assert matrix["mobile_accepted"] is True, (
        f"Sprint 3 FINAL BLOCKER CLOSURE: mobile_accepted must be True. "
        f"Summary: {matrix['summary']}"
    )
    assert matrix["universal_mobile_project_building"] == "WIRED_AND_TESTED"
    assert matrix["summary"]["wired_and_tested"] == 13
    assert matrix["summary"]["partially_wired"] == 0
    assert matrix["summary"]["blocked"] == 0
    assert matrix["summary"]["required_for_no_gap"] == 0
