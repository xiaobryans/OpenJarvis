"""US18 Founder Dogfood + Public Readiness Gate tests."""

from __future__ import annotations

import pytest


class TestFounderDogfood:
    def test_evaluate_returns_items(self):
        from openjarvis.workbench.founder_readiness import evaluate_founder_dogfood

        result = evaluate_founder_dogfood()
        assert "items" in result
        assert len(result["items"]) >= 10
        assert "verdict" in result
        assert result["verdict"] in ("ACCEPT", "HOLD", "UNSAFE")

    def test_voice_parked_in_checklist(self):
        from openjarvis.workbench.founder_readiness import evaluate_founder_dogfood

        result = evaluate_founder_dogfood()
        voice = next(i for i in result["items"] if i["item_id"] == "voice_parked")
        assert voice["status"] == "done"

    def test_workbench_usable(self):
        from openjarvis.workbench.founder_readiness import evaluate_founder_dogfood

        result = evaluate_founder_dogfood()
        wb = next(i for i in result["items"] if i["item_id"] == "workbench_usable")
        assert wb["status"] in ("done", "partial")

    def test_us17_in_checklist(self):
        from openjarvis.workbench.founder_readiness import evaluate_founder_dogfood

        result = evaluate_founder_dogfood()
        us17 = next(i for i in result["items"] if i["item_id"] == "us17_adversarial")
        assert us17["status"] in ("done", "partial")


class TestPublicReadinessMatrix:
    def test_matrix_has_honest_claims(self):
        from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix

        m = generate_public_readiness_matrix()
        claims = m["claims"]
        assert claims["hands_free_voice"] is False
        assert claims["uncontrolled_browser_autopilot"] is False
        assert claims["cloud_production_deploy"] is False
        assert claims["all_platform_mobile"] is False

    def test_known_limitations_present(self):
        from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix

        m = generate_public_readiness_matrix()
        assert len(m["known_limitations"]) > 0
        assert any("US13" in lim or "voice" in lim.lower() for lim in m["known_limitations"])

    def test_not_in_scope_includes_waves(self):
        from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix, NOT_IN_SCOPE

        m = generate_public_readiness_matrix()
        assert any("Waves" in x for x in m["not_in_scope"])
        assert "Waves (future)" in NOT_IN_SCOPE

    def test_rollback_instructions_present(self):
        from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix

        m = generate_public_readiness_matrix()
        assert len(m["rollback_instructions"]) >= 2

    def test_founder_retest_steps_present(self):
        from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix

        m = generate_public_readiness_matrix()
        assert any("pytest" in step for step in m["founder_retest_steps"])

    def test_blocked_items_include_voice(self):
        from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix, BLOCKED_ITEMS

        m = generate_public_readiness_matrix()
        assert any("voice" in b.lower() or "US13" in b for b in m["blocked_items"])


class TestReadinessItem:
    def test_item_to_dict(self):
        from openjarvis.workbench.founder_readiness import ReadinessItem

        item = ReadinessItem("test", "Test item", "done", "evidence here")
        d = item.to_dict()
        assert d["item_id"] == "test"
        assert d["status"] == "done"
