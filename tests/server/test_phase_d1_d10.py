"""Tests for ONE_MEGA_SPRINT_PHASE_D1_D10_AND_FINAL_RELEASE_CUTOVER.

Verifies Phase D1-D10 status is honest:
- No fake deployment
- No fake TestFlight/App Store completion
- No fake daily-driver certification
- No fake mobile URL
- Fargate not marked deployed unless truly deployed
- iOS not marked distributed unless actually distributed
- Plan 3 voice remains parked
- Chat path preservation intact
- Daily-driver cert not claimed without proof
- Mobile proof separate until Bryan confirms
"""
from __future__ import annotations

import pathlib
import pytest

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

ROOT = pathlib.Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def phase_d_client():
    if not HAS_FASTAPI:
        pytest.skip("fastapi not available")
    try:
        from openjarvis.server.phase_d_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)
    except ImportError as exc:
        pytest.skip(f"phase_d_routes not importable: {exc}")

@pytest.fixture(scope="module")
def tower_client():
    if not HAS_FASTAPI:
        pytest.skip("fastapi not available")
    from openjarvis.server.control_tower_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

@pytest.fixture(scope="module")
def sk_client():
    if not HAS_FASTAPI:
        pytest.skip("fastapi not available")
    from openjarvis.server.self_knowledge_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

@pytest.fixture(scope="module")
def core_client():
    if not HAS_FASTAPI:
        pytest.skip("fastapi not available")
    from openjarvis.server.core_completion_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

@pytest.fixture(scope="module")
def ios_client():
    if not HAS_FASTAPI:
        pytest.skip("fastapi not available")
    from openjarvis.server.ios_readiness_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

@pytest.fixture(scope="module")
def daily_driver_client():
    if not HAS_FASTAPI:
        pytest.skip("fastapi not available")
    try:
        from openjarvis.server.daily_driver_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)
    except ImportError as exc:
        pytest.skip(f"daily_driver_routes not importable: {exc}")


# ---------------------------------------------------------------------------
# Phase D status endpoint tests
# ---------------------------------------------------------------------------

class TestPhaseDStatus:
    def test_phase_d_status_returns_200(self, phase_d_client):
        r = phase_d_client.get("/v1/phase-d/status")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"

    def test_phase_d_no_fake_data(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        assert data.get("fake_data") is False
        assert data.get("fake_acceptance") is False

    def test_phase_d_has_ten_phases(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        phases = data.get("phases", [])
        assert len(phases) == 10, f"Expected 10 Phase D items, got {len(phases)}"

    def test_phase_d1_cloud_not_deployed(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        d1 = next((p for p in data["phases"] if p["id"] == "D1"), None)
        assert d1 is not None, "D1 not found"
        assert "DEFERRED" in d1["status"] or "NOT_STARTED" in d1["status"], (
            f"D1 must not claim deployment: status={d1['status']}"
        )

    def test_phase_d2_ios_not_distributed(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        d2 = next((p for p in data["phases"] if p["id"] == "D2"), None)
        assert d2 is not None, "D2 not found"
        # Must not claim TestFlight or App Store complete
        d2_str = str(d2).lower()
        assert "testflight_complete" not in d2_str, "D2 must not claim TestFlight complete"
        assert "app_store_ready: true" not in d2_str, "D2 must not claim App Store ready"

    def test_phase_d10_daily_driver_not_certified(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        d10 = next((p for p in data["phases"] if p["id"] == "D10"), None)
        assert d10 is not None, "D10 not found"
        d10_str = str(d10)
        assert "CERTIFIED" not in d10_str or "NEEDS" in d10_str, (
            "D10 must not claim daily-driver certified without proof"
        )

    def test_phase_d_summary_counts_present(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        summary = data.get("summary", {})
        assert summary.get("total") == 10

    def test_phase_d_all_decisions_require_bryan(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        assert data.get("all_decisions_require_bryan") is True


# ---------------------------------------------------------------------------
# Fargate / Cloud honesty
# ---------------------------------------------------------------------------

class TestFargateHonesty:
    def test_fargate_not_deployed_without_endpoint(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        import os
        # Save and clear JARVIS_CLOUD_ENDPOINT to simulate local state
        saved = os.environ.pop("JARVIS_CLOUD_ENDPOINT", None)
        try:
            status = get_fargate_worker_status()
            assert status.deployed is False, "Fargate must not claim deployed without JARVIS_CLOUD_ENDPOINT"
            assert status.executing is False, "Fargate must not claim executing without live proof"
        finally:
            if saved:
                os.environ["JARVIS_CLOUD_ENDPOINT"] = saved

    def test_fargate_status_not_ready_without_deployment(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status, STATUS_READY
        import os
        saved = os.environ.pop("JARVIS_CLOUD_ENDPOINT", None)
        try:
            status = get_fargate_worker_status()
            assert status.status != STATUS_READY, "Fargate must not claim READY without live deployment"
        finally:
            if saved:
                os.environ["JARVIS_CLOUD_ENDPOINT"] = saved


# ---------------------------------------------------------------------------
# iOS honesty
# ---------------------------------------------------------------------------

class TestIOSHonesty:
    def test_ios_native_app_not_ready(self, ios_client):
        data = ios_client.get("/v1/ios-readiness/status").json()
        assert data.get("native_ios_app_ready") is False, "native_ios_app_ready must be False"

    def test_testflight_not_ready(self, ios_client):
        data = ios_client.get("/v1/ios-readiness/status").json()
        assert data.get("testflight_ready") is False, "testflight_ready must be False"

    def test_app_store_not_ready(self, ios_client):
        data = ios_client.get("/v1/ios-readiness/status").json()
        assert data.get("app_store_ready") is False, "app_store_ready must be False"

    def test_ios_init_completed(self, ios_client):
        data = ios_client.get("/v1/ios-readiness/status").json()
        assert data.get("tauri_ios_init_run") is True, "tauri ios init must be marked complete"

    def test_no_fake_ios(self, ios_client):
        data = ios_client.get("/v1/ios-readiness/status").json()
        assert data.get("fake_ios_readiness") is False


# ---------------------------------------------------------------------------
# Daily-driver honesty
# ---------------------------------------------------------------------------

class TestDailyDriverHonesty:
    def test_daily_driver_not_certified(self, daily_driver_client):
        r = daily_driver_client.get("/v1/daily-driver/status")
        if r.status_code == 404:
            pytest.skip("daily-driver status route not implemented")
        data = r.json()
        certified = data.get("certified") or data.get("daily_driver_certified") or data.get("certification_complete")
        assert not certified, f"Daily-driver must not claim certified without proof: {data}"

    def test_daily_driver_no_fake_data(self, daily_driver_client):
        r = daily_driver_client.get("/v1/daily-driver/status")
        if r.status_code == 404:
            pytest.skip("daily-driver status route not implemented")
        data = r.json()
        assert data.get("fake_data") is False


# ---------------------------------------------------------------------------
# Core completion honesty
# ---------------------------------------------------------------------------

class TestCoreCompletionHonesty:
    def test_core_completion_no_fake_score(self, core_client):
        data = core_client.get("/v1/core-completion/status").json()
        assert data.get("fake_completion") is False
        assert data.get("fake_score") is False

    def test_core_completion_score_realistic(self, core_client):
        data = core_client.get("/v1/core-completion/status").json()
        score = data.get("completion_score_pct", 0)
        assert score < 100, "Completion score must not claim 100% with deferred gates"
        assert score >= 80, f"Score should reflect strong progress: {score}%"

    def test_phase_d_present_in_phases(self, core_client):
        data = core_client.get("/v1/core-completion/status").json()
        phases = data.get("phases", [])
        phase_names = [p.get("phase", "") for p in phases]
        # Should have some phase D reference or Plan D
        has_d = any("D" in name or "Phase D" in name for name in phase_names)
        assert has_d, f"Phase D should appear in phases list: {phase_names}"


# ---------------------------------------------------------------------------
# Active sprint
# ---------------------------------------------------------------------------

class TestActiveSprintPhaseD:
    def test_tower_active_sprint_is_phase_d(self, tower_client):
        data = tower_client.get("/v1/control-tower/status").json()
        sprint = data.get("active_sprint", "")
        assert "PHASE_D" in sprint or "D1_D10" in sprint, (
            f"Active sprint should be Phase D sprint, got: {sprint}"
        )

    def test_sk_active_sprint_is_phase_d(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        sprint = data.get("active_sprint", "")
        assert "PHASE_D" in sprint or "D1_D10" in sprint, (
            f"SK active sprint should be Phase D sprint, got: {sprint}"
        )


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

class TestSecurityPostCorrective:
    def test_capabilities_no_hardcoded_team_id(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        # Presence-only check: Team ID TQL4A44WDJ must not appear in any capability description
        all_text = str(data)
        assert "TQL4A44WDJ" not in all_text, (
            "Apple Team ID must not appear in /v1/jarvis/capabilities response"
        )

    def test_plan3_voice_still_parked(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        # The roadmap endpoint returns key "roadmap", fallback to "phases" for forward compat
        phases = data.get("phases", data.get("roadmap", []))
        # Only match exact Plan 3 entries (not Phase B3, C3, B13, C13, etc.)
        plan3_entries = [
            p for p in phases
            if p.get("plan") == "Plan 3" or p.get("name") == "Voice / Wake / TTS"
        ]
        assert len(plan3_entries) > 0, "Plan 3 voice entry must appear in roadmap"
        for entry in plan3_entries:
            status = entry.get("status", "")
            assert "PARKED" in status or "parked" in status.lower(), (
                f"Plan 3 voice must remain parked: {entry}"
            )

    def test_mobile_proof_separate(self, phase_d_client):
        data = phase_d_client.get("/v1/phase-d/status").json()
        d10 = next((p for p in data["phases"] if p["id"] == "D10"), None)
        if d10:
            mobile_str = str(d10.get("sub_items", {}).get("mobile_narrow_layout", ""))
            assert "UNVERIFIED" in mobile_str or "NEEDS" in mobile_str or "PROOF" in mobile_str, (
                "Mobile proof must remain separate until Bryan confirms"
            )


# ---------------------------------------------------------------------------
# Mobile serve script
# ---------------------------------------------------------------------------

class TestMobileServeScript:
    def test_mobile_serve_script_exists(self):
        script = ROOT / "scripts" / "mobile-serve.sh"
        assert script.exists(), "scripts/mobile-serve.sh must exist"

    def test_mobile_serve_script_no_secrets(self):
        script = ROOT / "scripts" / "mobile-serve.sh"
        if not script.exists():
            pytest.skip("script not created yet")
        content = script.read_text()
        assert "TQL4A44WDJ" not in content, "Team ID must not appear in mobile-serve.sh"
        assert "AKIA" not in content, "AWS key prefix must not appear in mobile-serve.sh"
        assert "xoxb-" not in content, "Slack token must not appear in mobile-serve.sh"

    def test_mobile_serve_script_documents_lan_access(self):
        script = ROOT / "scripts" / "mobile-serve.sh"
        if not script.exists():
            pytest.skip("script not created yet")
        content = script.read_text()
        assert "LAN" in content or "lan" in content or "5173" in content, (
            "mobile-serve.sh must document LAN access"
        )

    def test_gitignore_covers_sensitive_scripts(self):
        gitignore = ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore must exist"
        content = gitignore.read_text()
        assert "plan9_copy_cloud_api_key.sh" in content, (
            ".gitignore must cover plan9_copy_cloud_api_key.sh"
        )
