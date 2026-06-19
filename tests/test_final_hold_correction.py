"""Tests — Full No-Gap Jarvis Combined Sprint 3 FINAL HOLD Correction.

20 targeted tests covering:
 1.  MacBook-off continuity classified correctly
 2.  LAN-only continuity cannot be accepted as full no-gap
 3.  Native iOS/Android feasibility classified with cost/practicality
 4.  Native app proceeds only if free/low-cost and practical
 5.  Mobile web/PWA path can retrieve continuity state
 6.  Manual text fallback requirement is present for voice-first UI
 7.  Role-scoped cache exists for Jarvis/COS/GM/managers/workers/verifier
 8.  Cache misses are explicit
 9.  Cache reuse does not skip validation
10.  Worker cannot access unauthorized cache scope
11.  Cost ledger records role/task/cache/retry metadata
12.  Capability manifest reports missing/unverified items
13.  COS routes and escalates blockers
14.  Code Sentinel rejects stale artifact or unsupported claim
15.  Drift guard flags fake readiness/hidden blocker
16.  Company runtime response includes cache/cost/capability/blocker traces
17.  Continuity snapshot includes integrated state references
18.  Mobile UI/PWA gap is classified if not implemented
19.  Voice remains gated
20.  Full no-gap remains HOLD

Sprint: Full No-Gap Jarvis — Combined Sprint 3 FINAL HOLD Correction
"""

from __future__ import annotations

import time
import pytest


# ---------------------------------------------------------------------------
# 1. MacBook-off continuity classified correctly
# ---------------------------------------------------------------------------

def test_macbook_off_continuity_classified():
    """MacBook-off continuity is BLOCKED_WAITING_FOR_BRYAN_NOW when token is absent/invalid."""
    from unittest.mock import patch
    import openjarvis.mobile.continuity_backend as cb
    # Patch _load_token_from_env to return empty — simulates no token scenario
    with patch.object(cb, "_load_token_from_env", return_value=""):
        cb._STORE = None
        store = cb.get_always_available_store()
        status = store.get_macbook_off_status()
        # Without any token, MacBook-off must be BLOCKED
        assert status["macbook_off_continuity"] == "BLOCKED_WAITING_FOR_BRYAN_NOW", (
            f"Expected BLOCKED_WAITING_FOR_BRYAN_NOW, got {status['macbook_off_continuity']}"
        )
        assert status["lan_only_while_macbook_on"] == "WIRED_AND_TESTED"
        assert status["active_macbook_off_backend"] is None
    cb._STORE = None


# ---------------------------------------------------------------------------
# 2. LAN-only continuity cannot be accepted as full no-gap
# ---------------------------------------------------------------------------

def test_lan_only_not_full_no_gap():
    """LAN-only access is explicitly classified as MacBook-on only — not full no-gap."""
    from openjarvis.mobile.continuity_backend import LocalFileBackend
    local = LocalFileBackend()
    status = local.get_status()
    assert status.macbook_off_capable is False
    assert "NOT sufficient for MacBook-off continuity" in status.notes
    assert status.availability.value == "macbook_on_only"


# ---------------------------------------------------------------------------
# 3. Native iOS/Android feasibility classified with cost/practicality
# ---------------------------------------------------------------------------

def test_native_app_feasibility_matrix():
    """Native app feasibility matrix has all required options with cost and classification."""
    from openjarvis.mobile.continuity_backend import NATIVE_APP_FEASIBILITY
    required_keys = {"tauri_2_ios", "tauri_2_android", "pwa_install", "mobile_safari_web"}
    assert required_keys.issubset(set(NATIVE_APP_FEASIBILITY.keys()))
    for key, option in NATIVE_APP_FEASIBILITY.items():
        assert "classification" in option, f"{key} missing classification"
        assert "cost" in option, f"{key} missing cost"
        assert "macbook_off_capable" in option, f"{key} missing macbook_off_capable"
        assert "status_verdict" in option, f"{key} missing status_verdict"


# ---------------------------------------------------------------------------
# 4. Native app proceeds only if free/low-cost and practical
# ---------------------------------------------------------------------------

def test_pwa_classified_free_and_practical():
    """PWA is classified FREE_AND_PRACTICAL_NOW and is recommended."""
    from openjarvis.mobile.continuity_backend import NATIVE_APP_FEASIBILITY
    pwa = NATIVE_APP_FEASIBILITY["pwa_install"]
    assert pwa["classification"] == "FREE_AND_PRACTICAL_NOW"
    assert pwa["recommended"] is True


def test_tauri_ios_not_auto_started():
    """Tauri iOS requires Bryan setup — it is not automatically started."""
    from openjarvis.mobile.continuity_backend import NATIVE_APP_FEASIBILITY
    ios = NATIVE_APP_FEASIBILITY["tauri_2_ios"]
    assert ios["classification"] == "REQUIRES_BRYAN_SETUP"
    assert ios["recommended"] is False
    assert "$99" in ios["cost"]


# ---------------------------------------------------------------------------
# 5. Mobile web/PWA path can retrieve continuity state
# ---------------------------------------------------------------------------

def test_mobile_pwa_route_accessible():
    """FastAPI /mobile route returns HTML with text fallback and continuity API calls."""
    from fastapi.testclient import TestClient
    from openjarvis.server.company_org_routes import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/mobile")
    assert resp.status_code == 200
    html = resp.text
    assert "Jarvis Mobile" in html
    assert "text-input" in html     # text fallback input
    assert "/v1/continuity/macbook-off-status" in html  # continuity state retrieval
    assert "/manifest.webmanifest" in html               # PWA manifest link


def test_pwa_manifest_route():
    """GET /manifest.webmanifest returns valid PWA manifest with required fields."""
    from fastapi.testclient import TestClient
    from openjarvis.server.company_org_routes import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "OpenJarvis"
    assert data["start_url"] == "/mobile"
    assert data["display"] == "standalone"
    assert "icons" in data


# ---------------------------------------------------------------------------
# 6. Manual text fallback requirement is present
# ---------------------------------------------------------------------------

def test_text_fallback_in_mobile_page():
    """Mobile page documents text fallback for mic failure."""
    from fastapi.testclient import TestClient
    from openjarvis.server.company_org_routes import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/mobile")
    html = resp.text
    assert "text" in html.lower()
    assert "fallback" in html.lower() or "text input" in html.lower()
    assert "voice" in html.lower()   # voice acknowledged but gated


def test_mobile_contract_documents_text_fallback():
    """Mobile contract includes text fallback and voice gating."""
    from fastapi.testclient import TestClient
    from openjarvis.server.company_org_routes import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/v1/continuity/mobile-contract")
    assert resp.status_code == 200
    data = resp.json()
    pwa = data.get("pwa_path", {})
    assert "TEXT_FALLBACK_REQUIRED" in pwa.get("text_fallback", "")
    assert "SEPARATE_SPRINT_REQUIRED" in pwa.get("voice", "")


# ---------------------------------------------------------------------------
# 7. Role-scoped cache exists for all hierarchy roles
# ---------------------------------------------------------------------------

def test_role_scoped_cache_all_roles():
    """Cache can store and retrieve entries for all role types."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, SecurityLevel
    cache = RoleScopedCache()
    roles = [
        (CacheLayer.GLOBAL_JARVIS, "jarvis"),
        (CacheLayer.ROLE, "cos"),
        (CacheLayer.ROLE, "gm"),
        (CacheLayer.ROLE, "manager-coding"),
        (CacheLayer.WORKER, "worker-repo-inspector"),
        (CacheLayer.VALIDATION, "verifier"),
        (CacheLayer.CONTINUITY, "mobile-continuity"),
    ]
    for layer, role_id in roles:
        entry = cache.put(layer, role_id, content={"role": role_id}, security_level=SecurityLevel.INTERNAL)
        assert entry.hit_count == 0
        result = cache.get(layer, role_id)
        from openjarvis.jarvis_os.role_cache import CacheEntry
        assert isinstance(result, CacheEntry), f"Expected CacheEntry for {role_id}, got {type(result)}"


# ---------------------------------------------------------------------------
# 8. Cache misses are explicit
# ---------------------------------------------------------------------------

def test_cache_miss_is_explicit():
    """Cache miss returns CacheMiss dataclass, not None or guessed value."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, CacheMiss
    cache = RoleScopedCache()
    result = cache.get(CacheLayer.ROLE, "nonexistent-role")
    assert isinstance(result, CacheMiss)
    assert result.reason == "not_found"
    assert result.scope_key is not None


# ---------------------------------------------------------------------------
# 9. Cache reuse does not skip validation
# ---------------------------------------------------------------------------

def test_cache_reuse_preserves_gates_required():
    """Cached entry retains gates_required even after reuse."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, SecurityLevel
    cache = RoleScopedCache()
    cache.put(
        CacheLayer.ROLE, "manager-coding",
        content={"context": "cached plan"},
        gates_required=["verifier.verify", "tsc"],
        security_level=SecurityLevel.INTERNAL,
    )
    gates = cache.get_gates_required(CacheLayer.ROLE, "manager-coding")
    assert "verifier.verify" in gates
    assert "tsc" in gates


# ---------------------------------------------------------------------------
# 10. Worker cannot access unauthorized cache scope
# ---------------------------------------------------------------------------

def test_worker_cannot_access_private_scope():
    """Worker-level caller cannot access private cache entries of other roles."""
    from openjarvis.jarvis_os.role_cache import RoleScopedCache, CacheLayer, SecurityLevel, CacheMiss
    cache = RoleScopedCache()
    # Store private entry under jarvis
    cache.put(
        CacheLayer.GLOBAL_JARVIS, "jarvis",
        content={"secret_context": "classified"},
        security_level=SecurityLevel.PRIVATE,
    )
    # Worker tries to read it with only INTERNAL security level
    result = cache.get(
        CacheLayer.GLOBAL_JARVIS, "jarvis",
        caller_role_id="worker-repo-inspector",
        caller_security_level=SecurityLevel.INTERNAL,
    )
    assert isinstance(result, CacheMiss)
    assert "security_violation" in result.reason


# ---------------------------------------------------------------------------
# 11. Cost ledger records role/task/cache/retry metadata
# ---------------------------------------------------------------------------

def test_cost_ledger_records_all_metadata():
    """Cost ledger records role, task, cache hit, retry, and model."""
    from openjarvis.jarvis_os.cost_ledger import JarvisCostLedger
    ledger = JarvisCostLedger()
    entry = ledger.record(
        task_id="task-001",
        role_id="manager-coding",
        model="claude-sonnet",
        input_tokens=1000,
        output_tokens=500,
        is_estimate=True,
        cache_hit=True,
        retry_count=2,
        provider="anthropic",
        description="Coding task execution",
    )
    assert entry.role_id == "manager-coding"
    assert entry.task_id == "task-001"
    assert entry.cache_hit is True
    assert entry.retry_count == 2
    assert entry.is_estimate is True
    summary = ledger.get_task_summary("task-001")
    assert summary["total_tokens"] == 1500
    assert summary["cache_hits"] == 1


# ---------------------------------------------------------------------------
# 12. Capability manifest reports missing/unverified items
# ---------------------------------------------------------------------------

def test_capability_manifest_reports_blockers():
    """Capability manifest includes blockers and missing/unverified items."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    manifest = build_capability_manifest()
    assert "blockers" in manifest
    assert "available" in manifest
    assert "missing" in manifest
    assert manifest["no_gap_status"] == "HOLD — see blockers"
    assert manifest["voice_status"] is not None
    # Must have at least the MacBook-off blocker or native app blocker
    blocker_names = [b["name"] for b in manifest["blockers"]]
    assert any("mobile" in n or "voice" in n or "no_gap" in n for n in blocker_names)


# ---------------------------------------------------------------------------
# 13. COS routes and escalates blockers
# ---------------------------------------------------------------------------

def test_cos_routes_task():
    """COS skill routes a task to the correct manager."""
    from openjarvis.agents.cos_skill import COSSkill
    cos = COSSkill()
    decision = cos.route("run tests and fix code", task_count=1)
    assert decision.selected_manager == "manager-coding"
    assert decision.request_id is not None


def test_cos_escalates_blocker():
    """COS escalates blockers to Jarvis level."""
    from openjarvis.agents.cos_skill import COSSkill
    cos = COSSkill()
    esc = cos.escalate_blocker("task-x", "Worker stalled and cannot be reassigned")
    assert esc.escalated_to == "jarvis"
    assert "stalled" in esc.details
    status = cos.status()
    assert status["escalation_count"] == 1
    assert len(status["active_blockers"]) >= 1


def test_cos_enforces_no_hidden_gap():
    """COS detects hidden gaps where completion is claimed but blockers exist."""
    from openjarvis.agents.cos_skill import COSSkill
    cos = COSSkill()
    gaps = cos.enforce_no_hidden_gap(
        claimed_complete=["mobile continuity is complete"],
        actual_blockers=["MacBook-off continuity requires GITHUB_TOKEN"],
    )
    assert len(gaps) >= 1
    assert "HIDDEN_GAP" in gaps[0]


# ---------------------------------------------------------------------------
# 14. Code Sentinel rejects stale artifact or unsupported claim
# ---------------------------------------------------------------------------

def test_sentinel_rejects_stale_artifact():
    """Code Sentinel flags artifact older than TTL as stale."""
    from openjarvis.agents.code_sentinel import CodeSentinel, STALE_ARTIFACT_TTL_SECONDS
    sentinel = CodeSentinel()
    old_time = time.time() - (STALE_ARTIFACT_TTL_SECONDS + 100)
    finding = sentinel.check_stale_artifact("/tmp/old_artifact.json", old_time)
    assert finding is not None
    assert finding.blocks_release is False    # stale alone doesn't block, but flags it


def test_sentinel_rejects_forbidden_claim():
    """Code Sentinel rejects FULL_NO_GAP_JARVIS_COMPLETE in any text."""
    from openjarvis.agents.code_sentinel import CodeSentinel
    sentinel = CodeSentinel()
    findings = sentinel.reject_unsupported_claims("verdict: FULL_NO_GAP_JARVIS_COMPLETE")
    assert len(findings) >= 1
    assert findings[0].blocks_release is True


# ---------------------------------------------------------------------------
# 15. Drift guard flags fake readiness and hidden blockers
# ---------------------------------------------------------------------------

def test_drift_guard_flags_fake_readiness():
    """Drift guard catches 'looks good' and similar fake readiness phrases."""
    from openjarvis.agents.drift_guard import DriftGuard
    guard = DriftGuard()
    findings = guard.check_fake_readiness("Everything looks good, should be fine.")
    assert len(findings) >= 1


def test_drift_guard_flags_forbidden_claim():
    """Drift guard flags FULL_NO_GAP_JARVIS_COMPLETE as over-acceptance."""
    from openjarvis.agents.drift_guard import DriftGuard, DriftType
    guard = DriftGuard()
    findings = guard.check_forbidden_claims("verdict: FULL_NO_GAP_JARVIS_COMPLETE")
    assert any(f.drift_type == DriftType.OVER_ACCEPTANCE for f in findings)
    assert any(f.severity == "CRITICAL" for f in findings)


# ---------------------------------------------------------------------------
# 16. Company runtime response includes all traces
# ---------------------------------------------------------------------------

def test_company_runtime_includes_traces():
    """OrgTaskResult includes cos_routing, cache_trace, cost_trace, capability_status."""
    from openjarvis.agents.company_org_runtime import (
        CompanyOrgRuntime, OrgTaskRequest,
    )
    runtime = CompanyOrgRuntime()
    req = OrgTaskRequest(
        task_id="trace-test-001",
        user_request="inspect the repo",
        intent="coding",
    )
    result = runtime.run(req)
    d = result.to_dict()
    assert d["cos_routing"] is not None, "cos_routing missing from result"
    assert d["cost_trace"] is not None, "cost_trace missing from result"
    assert d["capability_status"] is not None, "capability_status missing from result"
    # cache_trace may be empty list but must be present
    assert "cache_trace" in d


# ---------------------------------------------------------------------------
# 17. Continuity snapshot includes integrated state references
# ---------------------------------------------------------------------------

def test_continuity_snapshot_has_integrated_references():
    """ContinuitySnapshot dataclass includes cache/cost/capability/blocker fields."""
    from openjarvis.mobile.continuity import ContinuitySnapshot, SyncStatus
    snap = ContinuitySnapshot(
        snapshot_id="snap-test-001",
        user_id="bryan",
        source_device_id="macbook-1",
        resume_token="tok-001",
        conversation_id="conv-1",
        conversation_messages=[],
        active_task_id="task-001",
        active_task_description="Build feature X",
        active_task_status="in_progress",
        assigned_manager_role_id="manager-coding",
        assigned_worker_role_ids=["worker-repo-inspector"],
        worker_statuses={"worker-repo-inspector": "completed"},
        pending_approvals=[],
        artifact_pointers=[],
        project_id="openjarvis",
        project_context={},
        memory_refs=[],
        tool_states={},
        sync_status=SyncStatus.SYNCED,
        conflict_state=None,
        verifier_status="ACCEPTED",
        verifier_fix_list=[],
        cache_state_ref="role:manager-coding:task-001",
        cost_task_ref="task-001",
        capability_status_ref="no_gap=HOLD",
        blocker_list=["MacBook-off continuity: GITHUB_TOKEN required"],
    )
    assert snap.cache_state_ref == "role:manager-coding:task-001"
    assert snap.cost_task_ref == "task-001"
    assert snap.capability_status_ref == "no_gap=HOLD"
    assert len(snap.blocker_list) == 1


# ---------------------------------------------------------------------------
# 18. Mobile UI/PWA gap is classified if not fully implemented
# ---------------------------------------------------------------------------

def test_mobile_pwa_gap_classified():
    """Manifest classifies Tauri iOS/Android as REQUIRES_BRYAN_SETUP — not auto-started."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    manifest = build_capability_manifest()
    all_items = {i["name"]: i for i in manifest["all_items"]}
    assert "tauri_mobile_ios" in all_items
    assert all_items["tauri_mobile_ios"]["status"] == "REQUIRES_BRYAN_SETUP"
    assert all_items["tauri_mobile_android"]["status"] == "REQUIRES_BRYAN_SETUP"
    assert all_items["pwa_manifest"]["status"] == "AVAILABLE"


# ---------------------------------------------------------------------------
# 19. Voice remains gated
# ---------------------------------------------------------------------------

def test_voice_remains_gated():
    """Manifest, mobile contract, and policy all gate voice as separate sprint."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    manifest = build_capability_manifest()
    assert "SEPARATE_SPRINT" in manifest["voice_status"]
    all_items = {i["name"]: i for i in manifest["all_items"]}
    assert all_items["voice_daily_driver"]["status"] == "SEPARATE_SPRINT_REQUIRED"

    from openjarvis.agents.drift_guard import JARVIS_POLICY_SPEC
    required_holds = JARVIS_POLICY_SPEC["required_hold_when"]
    assert any("voice" in r for r in required_holds)


# ---------------------------------------------------------------------------
# 20. Full no-gap remains HOLD
# ---------------------------------------------------------------------------

def test_full_no_gap_remains_hold():
    """FULL_NO_GAP_JARVIS_COMPLETE is forbidden and no-gap status is HOLD."""
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    from openjarvis.agents.drift_guard import JARVIS_POLICY_SPEC
    from openjarvis.agents.code_sentinel import CodeSentinel

    manifest = build_capability_manifest()
    assert manifest["no_gap_status"].startswith("HOLD")

    assert "FULL_NO_GAP_JARVIS_COMPLETE" in JARVIS_POLICY_SPEC["forbidden_claims"]

    sentinel = CodeSentinel()
    findings = sentinel.reject_unsupported_claims("FULL_NO_GAP_JARVIS_COMPLETE")
    assert len(findings) >= 1
    assert findings[0].blocks_release is True
