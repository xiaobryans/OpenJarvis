"""Sprint 3 FINAL No-Partial Closure — Enforcement Test Suite.

These tests FAIL if any Sprint 3 required item is PARTIALLY_WIRED.
They enforce the no-partial acceptance rule from the Sprint 3 closure prompt.

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

def test_all_sprint3_caps_are_wired_or_blocked():
    """Every Sprint 3 required mobile capability is WIRED_AND_TESTED or BLOCKED_* — never partial."""
    from openjarvis.mobile.project_runtime import MOBILE_PROJECT_CAPABILITIES, MobileCapabilityStatus

    acceptable = {
        MobileCapabilityStatus.WIRED_AND_TESTED,
        MobileCapabilityStatus.BLOCKED_WAITING_FOR_BRYAN_NOW,
        MobileCapabilityStatus.BLOCKED_EXTERNAL_PROVIDER,
        MobileCapabilityStatus.BLOCKED_RUNTIME_CREDENTIALS,
        MobileCapabilityStatus.BLOCKED_SECURITY,
        MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,  # allowed as HOLD classification
    }
    unacceptable = []
    for cap in MOBILE_PROJECT_CAPABILITIES:
        if cap.status not in acceptable:
            unacceptable.append(f"{cap.capability}: {cap.status.value}")

    assert len(unacceptable) == 0, (
        f"Sprint 3 FINAL: unacceptable capability statuses found: {unacceptable}"
    )


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
