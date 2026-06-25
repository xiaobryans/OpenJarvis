"""
Tests for FINAL_PHASE_A_NEURAL_COMMAND_CENTER_TAXONOMY_ROUTINES_AND_VISUAL_LANGUAGE_CORRECTIVE sprint.

Verifies:
- Status taxonomy is correct (no stale Plan 9 / Plan 2 pending labels)
- Panel coverage includes Routines / Cadence
- Backend routes return correct acceptance states
- Frontend source has no forbidden stale taxonomy strings
"""
from __future__ import annotations

import pathlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).parent.parent.parent  # OpenJarvis root

COCKPIT_PAGE = ROOT / "frontend" / "src" / "pages" / "JarvisCockpitPage.tsx"
NEURAL_CMD = ROOT / "frontend" / "src" / "pages" / "NeuralCommandCenter.tsx"
LIVING_ORB = ROOT / "frontend" / "src" / "components" / "Jarvis" / "LivingOrb.tsx"


@pytest.fixture(scope="module")
def tower_client():
    from openjarvis.server.control_tower_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def sk_client():
    from openjarvis.server.self_knowledge_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Backend taxonomy correctness
# ---------------------------------------------------------------------------

class TestBackendTaxonomy:
    def test_active_sprint_is_corrective(self, tower_client):
        """GET /v1/control-tower/status active_sprint must be a valid Final Phase A or Phase D sprint."""
        data = tower_client.get("/v1/control-tower/status").json()
        sprint = data.get("active_sprint", "")
        assert (
            "CORRECTIVE" in sprint or "TAXONOMY_ROUTINES" in sprint
            or "PHASE_D" in sprint or "ONE_MEGA_SPRINT" in sprint
        ), f"Expected Final Phase A or Phase D sprint name, got: {sprint!r}"

    def test_plan2_accepted_in_phases(self, tower_client):
        """GET /v1/control-tower/status phases must have an entry where plan/phase is 'Plan 2' and status is 'ACCEPTED'."""
        data = tower_client.get("/v1/control-tower/status").json()
        phases = data.get("phases", [])
        plan2_entry = next(
            (p for p in phases if "Plan 2" in p.get("phase", "") and p.get("status") == "ACCEPTED"),
            None,
        )
        assert plan2_entry is not None, (
            f"Expected a phases entry with 'Plan 2' and status 'ACCEPTED'. Got phases: {phases}"
        )

    def test_plan4_6_accepted_in_phases(self, tower_client):
        """GET /v1/control-tower/status phases must have 'Plan 4-6' with status 'ACCEPTED'."""
        data = tower_client.get("/v1/control-tower/status").json()
        phases = data.get("phases", [])
        p46_entry = next(
            (p for p in phases if "Plan 4-6" in p.get("phase", "") and p.get("status") == "ACCEPTED"),
            None,
        )
        assert p46_entry is not None, (
            f"Expected phases entry with 'Plan 4-6' and status 'ACCEPTED'. Got phases: {phases}"
        )

    def test_phase_b_accepted_on_hold(self, sk_client):
        """GET /v1/jarvis/roadmap roadmap list must have an entry with 'B' in plan and status 'ACCEPTED_ON_HOLD'."""
        data = sk_client.get("/v1/jarvis/roadmap").json()
        roadmap = data.get("roadmap", [])
        phase_b_entry = next(
            (p for p in roadmap if "B" in p.get("plan", "") and p.get("status") == "ACCEPTED_ON_HOLD"),
            None,
        )
        assert phase_b_entry is not None, (
            f"Expected roadmap entry with 'B' in plan and status 'ACCEPTED_ON_HOLD'. "
            f"Got entries: {[p.get('plan') for p in roadmap]}"
        )

    def test_phase_c_accepted(self, sk_client):
        """GET /v1/jarvis/roadmap roadmap list must have an entry with 'C1' in plan and status 'ACCEPTED'."""
        data = sk_client.get("/v1/jarvis/roadmap").json()
        roadmap = data.get("roadmap", [])
        phase_c1_entry = next(
            (p for p in roadmap if "C1" in p.get("plan", "") and p.get("status") == "ACCEPTED"),
            None,
        )
        assert phase_c1_entry is not None, (
            f"Expected roadmap entry with 'C1' in plan and status 'ACCEPTED'. "
            f"Got entries: {[(p.get('plan'), p.get('status')) for p in roadmap if 'C' in p.get('plan','')]}"
        )

    def test_fargate_gate_has_phase_d_note(self, tower_client):
        """GET /v1/control-tower/gate-registry fargate_deployment gate must have 'phase' field containing 'Phase D' or 'not started'."""
        data = tower_client.get("/v1/control-tower/gate-registry").json()
        open_gates = data.get("open_gates", [])
        fargate_gate = next(
            (g for g in open_gates if g.get("gate_id") == "fargate_deployment"),
            None,
        )
        assert fargate_gate is not None, "Expected fargate_deployment gate in open_gates"
        phase_field = fargate_gate.get("phase", "")
        assert "Phase D" in phase_field or "not started" in phase_field, (
            f"Expected fargate_deployment gate 'phase' to contain 'Phase D' or 'not started', got: {phase_field!r}"
        )

    def test_fargate_not_plan2_pending(self, tower_client):
        """fargate_deployment gate must NOT contain 'PENDING PLAN 2' anywhere in its fields."""
        data = tower_client.get("/v1/control-tower/gate-registry").json()
        open_gates = data.get("open_gates", [])
        fargate_gate = next(
            (g for g in open_gates if g.get("gate_id") == "fargate_deployment"),
            None,
        )
        assert fargate_gate is not None, "Expected fargate_deployment gate in open_gates"
        # Serialize the entire gate entry and scan for forbidden string
        gate_text = str(fargate_gate)
        assert "PENDING PLAN 2" not in gate_text, (
            f"fargate_deployment gate must NOT contain 'PENDING PLAN 2'. Gate: {gate_text}"
        )

    def test_plan3_voice_parked(self, tower_client):
        """Gate or phase with 'plan3_voice' or 'Voice' must have status 'parked'."""
        data = tower_client.get("/v1/control-tower/gate-registry").json()
        open_gates = data.get("open_gates", [])
        voice_gate = next(
            (g for g in open_gates if "plan3_voice" in g.get("gate_id", "") or "Voice" in g.get("name", "")),
            None,
        )
        assert voice_gate is not None, (
            f"Expected a gate with 'plan3_voice' gate_id or 'Voice' in name. Gates: {[g.get('gate_id') for g in open_gates]}"
        )
        assert voice_gate.get("status") == "parked", (
            f"Voice gate status must be 'parked', got: {voice_gate.get('status')!r}"
        )

    def test_ios_init_completed(self, tower_client):
        """GET /v1/control-tower/completion-score capability_coverage.ios_init_completed must be True."""
        data = tower_client.get("/v1/control-tower/completion-score").json()
        cap = data.get("capability_coverage", {})
        assert cap.get("ios_init_completed") is True, (
            f"Expected ios_init_completed=True, got: {cap.get('ios_init_completed')!r}"
        )

    def test_native_ios_distribution_not_proven(self, tower_client):
        """capability_coverage.native_ios_distributed must be False (not yet proven)."""
        data = tower_client.get("/v1/control-tower/completion-score").json()
        cap = data.get("capability_coverage", {})
        assert cap.get("native_ios_distributed") is False, (
            f"Expected native_ios_distributed=False, got: {cap.get('native_ios_distributed')!r}"
        )

    def test_installed_app_smoke_needs_proof(self, tower_client):
        """capability_coverage.installed_app_smoke_visual must be False (Bryan proof needed)."""
        data = tower_client.get("/v1/control-tower/completion-score").json()
        cap = data.get("capability_coverage", {})
        assert cap.get("installed_app_smoke_visual") is False, (
            f"Expected installed_app_smoke_visual=False, got: {cap.get('installed_app_smoke_visual')!r}"
        )

    def test_daily_driver_needs_proof(self, tower_client):
        """capability_coverage.daily_driver_certified must be False (Bryan usage sessions needed)."""
        data = tower_client.get("/v1/control-tower/completion-score").json()
        cap = data.get("capability_coverage", {})
        assert cap.get("daily_driver_certified") is False, (
            f"Expected daily_driver_certified=False, got: {cap.get('daily_driver_certified')!r}"
        )

    def test_no_plan9_foundation_taxonomy_in_active_sprint(self, tower_client):
        """active_sprint must NOT contain 'PLAN_9' or 'Plan 9'."""
        data = tower_client.get("/v1/control-tower/status").json()
        sprint = data.get("active_sprint", "")
        assert "PLAN_9" not in sprint and "Plan 9" not in sprint, (
            f"active_sprint must not contain stale Plan 9 taxonomy. Got: {sprint!r}"
        )

    def test_no_fake_acceptance(self, tower_client):
        """fake_acceptance must be False in control-tower status."""
        data = tower_client.get("/v1/control-tower/status").json()
        assert data.get("fake_acceptance") is False, (
            f"fake_acceptance must be False, got: {data.get('fake_acceptance')!r}"
        )


# ---------------------------------------------------------------------------
# Frontend source taxonomy checks (static analysis)
# ---------------------------------------------------------------------------

class TestFrontendSourceTaxonomy:
    def test_frontend_no_plan9_foundation_heading(self):
        """JarvisCockpitPage.tsx must NOT contain 'Plan 9 Foundation (Accepted)'."""
        text = COCKPIT_PAGE.read_text(encoding="utf-8")
        assert "Plan 9 Foundation (Accepted)" not in text, (
            "Stale 'Plan 9 Foundation (Accepted)' heading found in JarvisCockpitPage.tsx — must be removed"
        )

    def test_frontend_no_pending_plan2_text(self):
        """JarvisCockpitPage.tsx must NOT contain 'PENDING PLAN 2'."""
        text = COCKPIT_PAGE.read_text(encoding="utf-8")
        assert "PENDING PLAN 2" not in text, (
            "Stale 'PENDING PLAN 2' text found in JarvisCockpitPage.tsx — must be removed"
        )

    def test_frontend_no_cloud_off_pending_plan2(self):
        """JarvisCockpitPage.tsx must NOT have 'Cloud-off runtime' combined with 'PENDING PLAN 2'."""
        text = COCKPIT_PAGE.read_text(encoding="utf-8")
        # Both strings must not co-exist in the file
        assert not ("Cloud-off runtime" in text and "PENDING PLAN 2" in text), (
            "Stale combination of 'Cloud-off runtime' and 'PENDING PLAN 2' found in JarvisCockpitPage.tsx"
        )

    def test_frontend_plan9_overlay_fixed(self):
        """JarvisCockpitPage.tsx MUST contain 'Plan 2 Runtime — ACCEPTED'."""
        text = COCKPIT_PAGE.read_text(encoding="utf-8")
        assert "Plan 2 Runtime — ACCEPTED" in text, (
            "Expected 'Plan 2 Runtime — ACCEPTED' in JarvisCockpitPage.tsx — corrective sprint must add it"
        )

    def test_frontend_fargate_phase_d(self):
        """JarvisCockpitPage.tsx MUST contain 'PHASE_D_NOT_STARTED'."""
        text = COCKPIT_PAGE.read_text(encoding="utf-8")
        assert "PHASE_D_NOT_STARTED" in text, (
            "Expected 'PHASE_D_NOT_STARTED' in JarvisCockpitPage.tsx to show Fargate is Phase D, not stale Plan 2 pending"
        )

    def test_frontend_no_verified_plan9_label(self):
        """JarvisCockpitPage.tsx must NOT contain 'Verified (Plan 9)'."""
        text = COCKPIT_PAGE.read_text(encoding="utf-8")
        assert "Verified (Plan 9)" not in text, (
            "Stale 'Verified (Plan 9)' label found in JarvisCockpitPage.tsx — must be removed"
        )

    def test_frontend_no_pending_plan2_row_label(self):
        """JarvisCockpitPage.tsx must NOT contain 'Pending (Plan 2)'."""
        text = COCKPIT_PAGE.read_text(encoding="utf-8")
        assert "Pending (Plan 2)" not in text, (
            "Stale 'Pending (Plan 2)' row label found in JarvisCockpitPage.tsx — must be removed"
        )


# ---------------------------------------------------------------------------
# Frontend panel coverage checks
# ---------------------------------------------------------------------------

class TestFrontendPanelCoverage:
    def test_frontend_routines_panel_desktop(self):
        """NeuralCommandCenter.tsx must contain 'Routines / Cadence' (desktop panel)."""
        text = NEURAL_CMD.read_text(encoding="utf-8")
        assert "Routines / Cadence" in text, (
            "Expected 'Routines / Cadence' panel label in NeuralCommandCenter.tsx"
        )

    def test_frontend_routines_panel_mobile(self):
        """NeuralCommandCenter.tsx must contain 'Routines / Cadence' at least twice (desktop + mobile)."""
        text = NEURAL_CMD.read_text(encoding="utf-8")
        count = text.count("Routines / Cadence")
        assert count >= 2, (
            f"Expected 'Routines / Cadence' to appear at least twice (desktop + mobile), found {count} occurrence(s)"
        )

    def test_frontend_phase_b_accepted_on_hold_badge(self):
        """NeuralCommandCenter.tsx must contain 'ACCEPTED_ON_HOLD' for Phase B badge."""
        text = NEURAL_CMD.read_text(encoding="utf-8")
        assert "ACCEPTED_ON_HOLD" in text, (
            "Expected 'ACCEPTED_ON_HOLD' badge text in NeuralCommandCenter.tsx for Phase B status"
        )

    def test_frontend_plan2_accepted_badge(self):
        """NeuralCommandCenter.tsx must contain both 'Plan 2' and 'ACCEPTED'."""
        text = NEURAL_CMD.read_text(encoding="utf-8")
        assert "Plan 2" in text, "Expected 'Plan 2' in NeuralCommandCenter.tsx"
        assert "ACCEPTED" in text, "Expected 'ACCEPTED' in NeuralCommandCenter.tsx"


# ---------------------------------------------------------------------------
# Frontend visual language checks
# ---------------------------------------------------------------------------

class TestFrontendVisualLanguage:
    def test_frontend_hud_background(self):
        """NeuralCommandCenter.tsx must contain the perspective grid background string."""
        text = NEURAL_CMD.read_text(encoding="utf-8")
        # The HUD perspective grid uses repeating-linear-gradient — check a distinctive part
        assert "repeating-linear-gradient" in text, (
            "Expected 'repeating-linear-gradient' (HUD grid background) in NeuralCommandCenter.tsx"
        )

    def test_frontend_monospace_typography(self):
        """NeuralCommandCenter.tsx must contain 'JetBrains Mono' or \"'Consolas', monospace\"."""
        text = NEURAL_CMD.read_text(encoding="utf-8")
        assert "JetBrains Mono" in text or "'Consolas', monospace" in text, (
            "Expected 'JetBrains Mono' or \"'Consolas', monospace\" in NeuralCommandCenter.tsx for HUD typography"
        )

    def test_frontend_orb_orbital_arc(self):
        """LivingOrb.tsx must contain 'orb-orbital-rotate'."""
        text = LIVING_ORB.read_text(encoding="utf-8")
        assert "orb-orbital-rotate" in text, (
            "Expected 'orb-orbital-rotate' animation in LivingOrb.tsx for orbital arc visual"
        )
