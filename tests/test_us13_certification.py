"""US13 V1 Daily-Driver Certification — scoped tests.

Covers all US13 scope items:
  1. Certification matrix structure         — CertificationMatrix, CertificationItem, FailureModeItem
  2. Runtime truthfulness gate              — no item claims certified without evidence
  3. CertificationStatus / Visibility       — constants, values
  4. build_certification_matrix()           — builds 12 items, 8 failure modes
  5. Failure-mode coverage                  — all 8 required failure modes documented
  6. Backend-only vs UI-visible             — items correctly classified
  7. Hold-blocker detection                 — get_hold_blockers() returns items with hold/insufficient_data
  8. Verdict logic                          — hold when any item is hold/insufficient_data
  9. INSUFFICIENT_DATA_MSG                  — used for missing evidence, not inferred readiness
  10. check_certification_matrix()          — check #33 registered and functional
  11. Readiness integration                 — CERTIFICATION category (28th) in _CATEGORY_CHECKS

Performance note:
  run_all_checks() takes ~54 s.  All tests that need a live matrix or check
  result share a single module-scoped pre-run via the `shared_checks` and
  `shared_matrix` fixtures so the suite only pays that cost once.

Rules:
  - No real subprocesses started beyond git rev-parse (read-only)
  - No secrets used
  - No real external sends
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Module-scoped shared fixtures — run checks/matrix ONCE for the whole module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def shared_checks():
    """Run all 33 checks once; reused by every test that needs live results."""
    from openjarvis.doctor.checks import run_all_checks
    return run_all_checks(project_id="omnix")


@pytest.fixture(scope="module")
def shared_matrix(shared_checks):
    """Build the certification matrix once from pre-run checks."""
    from openjarvis.doctor.certification import build_certification_matrix
    return build_certification_matrix(project_id="omnix", check_results=shared_checks)


@pytest.fixture(scope="module")
def shared_check_result(shared_checks):
    """Single check_certification_matrix result from pre-run checks."""
    check_map = {r.check_id: r for r in shared_checks}
    # certification_matrix is check #33; it will be in shared_checks
    return check_map.get("certification_matrix")


# ---------------------------------------------------------------------------
# 1. CertificationStatus constants  (pure — no runtime needed)
# ---------------------------------------------------------------------------


class TestCertificationStatus:
    def test_certified_constant(self):
        from openjarvis.doctor.certification import CertificationStatus
        assert CertificationStatus.CERTIFIED == "certified"

    def test_backend_only_constant(self):
        from openjarvis.doctor.certification import CertificationStatus
        assert CertificationStatus.BACKEND_ONLY == "backend_only"

    def test_hold_constant(self):
        from openjarvis.doctor.certification import CertificationStatus
        assert CertificationStatus.HOLD == "hold"

    def test_insufficient_data_constant(self):
        from openjarvis.doctor.certification import CertificationStatus
        assert CertificationStatus.INSUFFICIENT_DATA == "insufficient_data_to_verify"

    def test_four_distinct_values(self):
        from openjarvis.doctor.certification import CertificationStatus
        vals = {
            CertificationStatus.CERTIFIED,
            CertificationStatus.BACKEND_ONLY,
            CertificationStatus.HOLD,
            CertificationStatus.INSUFFICIENT_DATA,
        }
        assert len(vals) == 4


# ---------------------------------------------------------------------------
# 2. CertificationVisibility constants  (pure)
# ---------------------------------------------------------------------------


class TestCertificationVisibility:
    def test_ui_visible_constant(self):
        from openjarvis.doctor.certification import CertificationVisibility
        assert CertificationVisibility.UI_VISIBLE == "ui_visible"

    def test_backend_only_constant(self):
        from openjarvis.doctor.certification import CertificationVisibility
        assert CertificationVisibility.BACKEND_ONLY == "backend_only"

    def test_unavailable_constant(self):
        from openjarvis.doctor.certification import CertificationVisibility
        assert CertificationVisibility.UNAVAILABLE == "unavailable"


# ---------------------------------------------------------------------------
# 3. INSUFFICIENT_DATA_MSG  (pure)
# ---------------------------------------------------------------------------


class TestInsufficientDataMsg:
    def test_msg_value(self):
        from openjarvis.doctor.certification import INSUFFICIENT_DATA_MSG
        assert INSUFFICIENT_DATA_MSG == "Insufficient data to verify."

    def test_helper_no_reason(self):
        from openjarvis.doctor.certification import insufficient_data, INSUFFICIENT_DATA_MSG
        assert insufficient_data() == INSUFFICIENT_DATA_MSG

    def test_helper_with_reason(self):
        from openjarvis.doctor.certification import insufficient_data, INSUFFICIENT_DATA_MSG
        result = insufficient_data("check_id missing")
        assert result.startswith(INSUFFICIENT_DATA_MSG)
        assert "check_id missing" in result

    def test_msg_does_not_claim_readiness(self):
        from openjarvis.doctor.certification import INSUFFICIENT_DATA_MSG
        low = INSUFFICIENT_DATA_MSG.lower()
        assert "ready" not in low
        assert "pass" not in low
        assert "certified" not in low


# ---------------------------------------------------------------------------
# 4. CertificationItem  (pure)
# ---------------------------------------------------------------------------


class TestCertificationItem:
    def test_to_dict_has_required_fields(self):
        from openjarvis.doctor.certification import (
            CertificationItem, CertificationStatus, CertificationVisibility,
        )
        item = CertificationItem(
            name="test item", area="test_area",
            status=CertificationStatus.BACKEND_ONLY,
            visibility=CertificationVisibility.BACKEND_ONLY,
            evidence="backend_health=pass",
        )
        d = item.to_dict()
        assert d["name"] == "test item"
        assert d["status"] == CertificationStatus.BACKEND_ONLY
        assert d["visibility"] == CertificationVisibility.BACKEND_ONLY
        assert d["evidence"] == "backend_health=pass"
        assert "hold_reason" in d

    def test_hold_reason_defaults_none(self):
        from openjarvis.doctor.certification import (
            CertificationItem, CertificationStatus, CertificationVisibility,
        )
        item = CertificationItem(
            name="x", area="y",
            status=CertificationStatus.CERTIFIED,
            visibility=CertificationVisibility.UI_VISIBLE,
            evidence="ok",
        )
        assert item.hold_reason is None


# ---------------------------------------------------------------------------
# 5. FailureModeItem  (pure)
# ---------------------------------------------------------------------------


class TestFailureModeItem:
    def test_to_dict_has_required_fields(self):
        from openjarvis.doctor.certification import FailureModeItem
        fm = FailureModeItem(
            failure_mode="missing_microphone_permission",
            behavior="voice_pipeline returns not_configured",
            evidence="voice_pipeline=not_configured",
        )
        d = fm.to_dict()
        assert d["failure_mode"] == "missing_microphone_permission"
        assert d["behavior"]
        assert d["evidence"]


# ---------------------------------------------------------------------------
# 6. CertificationMatrix.verdict()  (pure — no runtime)
# ---------------------------------------------------------------------------


class TestCertificationMatrixVerdict:
    def test_hold_when_ui_visible_item_is_hold(self):
        from openjarvis.doctor.certification import (
            CertificationItem, CertificationMatrix,
            CertificationStatus, CertificationVisibility,
        )
        items = [
            CertificationItem(
                name="ok", area="ok_area",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence="ok",
            ),
            CertificationItem(
                name="blocked", area="blocked_area",
                status=CertificationStatus.HOLD,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence="check failed",
                hold_reason="some failure",
            ),
        ]
        matrix = CertificationMatrix(head="abc123", project_id="omnix", items=items, failure_modes=[])
        assert matrix.verdict() == "hold"

    def test_backend_only_hold_does_not_block_daily_driver_verdict(self):
        from openjarvis.doctor.certification import (
            CertificationItem, CertificationMatrix,
            CertificationStatus, CertificationVisibility,
        )
        items = [
            CertificationItem(
                name="ok", area="ok_area",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence="ok",
            ),
            CertificationItem(
                name="backend_hold", area="backend_area",
                status=CertificationStatus.HOLD,
                visibility=CertificationVisibility.BACKEND_ONLY,
                evidence="check failed",
                hold_reason="backend only failure",
            ),
        ]
        matrix = CertificationMatrix(head="abc123", project_id="omnix", items=items, failure_modes=[])
        assert matrix.verdict() == "certified"

    def test_hold_when_ui_visible_item_insufficient_data(self):
        from openjarvis.doctor.certification import (
            CertificationItem, CertificationMatrix,
            CertificationStatus, CertificationVisibility,
        )
        items = [
            CertificationItem(
                name="missing", area="missing_area",
                status=CertificationStatus.INSUFFICIENT_DATA,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence="Insufficient data to verify.",
            ),
        ]
        matrix = CertificationMatrix(head="abc123", project_id="omnix", items=items, failure_modes=[])
        assert matrix.verdict() == "hold"

    def test_certified_when_all_items_pass(self):
        from openjarvis.doctor.certification import (
            CertificationItem, CertificationMatrix,
            CertificationStatus, CertificationVisibility,
        )
        items = [
            CertificationItem(
                name="ok1", area="area1",
                status=CertificationStatus.CERTIFIED,
                visibility=CertificationVisibility.UI_VISIBLE,
                evidence="evidence1",
            ),
            CertificationItem(
                name="ok2", area="area2",
                status=CertificationStatus.BACKEND_ONLY,
                visibility=CertificationVisibility.BACKEND_ONLY,
                evidence="evidence2",
            ),
        ]
        matrix = CertificationMatrix(head="abc123", project_id="omnix", items=items, failure_modes=[])
        assert matrix.verdict() == "certified"


# ---------------------------------------------------------------------------
# 7. build_certification_matrix — structure  (uses shared_matrix)
# ---------------------------------------------------------------------------


class TestBuildCertificationMatrix:
    def test_returns_certification_matrix(self, shared_matrix):
        from openjarvis.doctor.certification import CertificationMatrix
        assert isinstance(shared_matrix, CertificationMatrix)

    def test_has_12_items(self, shared_matrix):
        assert len(shared_matrix.items) == 12

    def test_has_8_failure_modes(self, shared_matrix):
        assert len(shared_matrix.failure_modes) == 8

    def test_head_is_set(self, shared_matrix):
        assert shared_matrix.head
        assert isinstance(shared_matrix.head, str)

    def test_project_id_propagated(self, shared_matrix):
        assert shared_matrix.project_id == "omnix"

    def test_evaluated_at_is_recent(self, shared_matrix):
        import time
        assert time.time() - shared_matrix.evaluated_at < 300

    def test_all_items_have_nonempty_names(self, shared_matrix):
        for item in shared_matrix.items:
            assert item.name, f"Item with area={item.area} has empty name"

    def test_all_items_have_nonempty_areas(self, shared_matrix):
        for item in shared_matrix.items:
            assert item.area, f"Item {item.name} has empty area"

    def test_all_items_have_nonempty_evidence(self, shared_matrix):
        for item in shared_matrix.items:
            assert item.evidence, f"Item {item.name} has empty evidence"

    def test_all_areas_unique(self, shared_matrix):
        areas = [i.area for i in shared_matrix.items]
        assert len(areas) == len(set(areas)), f"Duplicate areas: {areas}"

    def test_all_failure_modes_have_evidence(self, shared_matrix):
        for fm in shared_matrix.failure_modes:
            assert fm.evidence, f"Failure mode {fm.failure_mode} has empty evidence"

    def test_all_failure_modes_have_behavior(self, shared_matrix):
        for fm in shared_matrix.failure_modes:
            assert fm.behavior, f"Failure mode {fm.failure_mode} has empty behavior"

    def test_verdict_is_valid(self, shared_matrix):
        assert shared_matrix.verdict() in ("certified", "hold")

    def test_to_dict_is_json_serializable(self, shared_matrix):
        import json
        d = shared_matrix.to_dict()
        json_str = json.dumps(d)
        assert len(json_str) > 200

    def test_to_dict_has_required_keys(self, shared_matrix):
        d = shared_matrix.to_dict()
        for key in ["head", "project_id", "verdict", "evaluated_at",
                    "items", "failure_modes", "hold_blockers",
                    "backend_only", "ui_visible"]:
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# 8. Runtime truthfulness gate  (uses shared_matrix)
# ---------------------------------------------------------------------------


class TestRuntimeTruthfulnessGate:
    def test_no_item_has_empty_evidence(self, shared_matrix):
        empty = [i.name for i in shared_matrix.items if not i.evidence]
        assert not empty, f"Items with empty evidence: {empty}"

    def test_no_failure_mode_has_empty_evidence(self, shared_matrix):
        empty = [f.failure_mode for f in shared_matrix.failure_modes if not f.evidence]
        assert not empty, f"Failure modes with empty evidence: {empty}"

    def test_insufficient_data_not_claimed_as_ready(self, shared_matrix):
        from openjarvis.doctor.certification import INSUFFICIENT_DATA_MSG, CertificationStatus
        for item in shared_matrix.items:
            if item.evidence == INSUFFICIENT_DATA_MSG:
                assert item.status in (
                    CertificationStatus.HOLD,
                    CertificationStatus.INSUFFICIENT_DATA,
                ), (
                    f"Item {item.name} has INSUFFICIENT_DATA_MSG evidence "
                    f"but status={item.status}"
                )

    def test_certified_items_have_real_evidence(self, shared_matrix):
        from openjarvis.doctor.certification import INSUFFICIENT_DATA_MSG, CertificationStatus
        for item in shared_matrix.items:
            if item.status == CertificationStatus.CERTIFIED:
                assert item.evidence != INSUFFICIENT_DATA_MSG, (
                    f"Item {item.name} claims CERTIFIED but evidence is INSUFFICIENT_DATA_MSG"
                )
                assert item.evidence

    def test_hold_items_have_evidence(self, shared_matrix):
        from openjarvis.doctor.certification import CertificationStatus
        for item in shared_matrix.items:
            if item.status == CertificationStatus.HOLD:
                assert item.evidence, f"Hold item {item.name} has empty evidence"


# ---------------------------------------------------------------------------
# 9. Failure-mode coverage  (uses shared_matrix)
# ---------------------------------------------------------------------------


_REQUIRED_FAILURE_MODES = [
    "missing_microphone_permission",
    "voice_worker_unavailable",
    "connector_unconfigured_degraded_blocked",
    "local_dependency_missing",
    "queue_stalled_or_empty",
    "missing_memory_context_evidence",
    "external_action_requiring_approval",
    "backend_only_feature_not_visible_in_ui",
]


class TestFailureModeCoverage:
    def test_all_required_failure_modes_present(self, shared_matrix):
        documented = {fm.failure_mode for fm in shared_matrix.failure_modes}
        for mode in _REQUIRED_FAILURE_MODES:
            assert mode in documented, f"Required failure mode not documented: {mode}"

    def test_all_failure_modes_have_nonempty_behavior(self, shared_matrix):
        for fm in shared_matrix.failure_modes:
            assert fm.behavior, f"Failure mode {fm.failure_mode} has empty behavior"


# ---------------------------------------------------------------------------
# 10. Backend-only vs UI-visible classification  (uses shared_matrix)
# ---------------------------------------------------------------------------


class TestBackendOnlyVsUIVisible:
    def test_app_launch_area_is_ui_visible(self, shared_matrix):
        from openjarvis.doctor.certification import CertificationVisibility
        items = {i.area: i for i in shared_matrix.items}
        assert items["app_launch_runtime_connection"].visibility == CertificationVisibility.UI_VISIBLE

    def test_mission_control_area_is_ui_visible(self, shared_matrix):
        from openjarvis.doctor.certification import CertificationVisibility
        items = {i.area: i for i in shared_matrix.items}
        assert items["mission_control_status_readiness"].visibility == CertificationVisibility.UI_VISIBLE

    def test_voice_path_is_ui_visible(self, shared_matrix):
        from openjarvis.doctor.certification import CertificationVisibility
        items = {i.area: i for i in shared_matrix.items}
        assert items["voice_path"].visibility == CertificationVisibility.UI_VISIBLE

    def test_connector_health_is_ui_visible(self, shared_matrix):
        from openjarvis.doctor.certification import CertificationVisibility
        items = {i.area: i for i in shared_matrix.items}
        assert items["connector_health"].visibility == CertificationVisibility.UI_VISIBLE

    def test_trust_layer_is_backend_only(self, shared_matrix):
        from openjarvis.doctor.certification import CertificationVisibility
        items = {i.area: i for i in shared_matrix.items}
        assert items["trust_evidence_layer"].visibility == CertificationVisibility.BACKEND_ONLY

    def test_get_backend_only_nonempty(self, shared_matrix):
        assert len(shared_matrix.get_backend_only()) > 0

    def test_get_hold_blockers_returns_list(self, shared_matrix):
        blockers = shared_matrix.get_hold_blockers()
        assert isinstance(blockers, list)

    def test_hold_blockers_all_have_evidence(self, shared_matrix):
        for item in shared_matrix.get_hold_blockers():
            assert item.evidence, f"Hold blocker {item.area} has empty evidence"


# ---------------------------------------------------------------------------
# 11. check_certification_matrix (check #33)  (uses shared_check_result)
# ---------------------------------------------------------------------------


class TestCheckCertificationMatrix:
    def test_check_is_importable(self):
        from openjarvis.doctor.checks import check_certification_matrix
        assert check_certification_matrix is not None

    def test_check_in_all_check_fns(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS, check_certification_matrix
        assert check_certification_matrix in _ALL_CHECK_FNS

    def test_check_is_last(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS, check_certification_matrix
        assert _ALL_CHECK_FNS[-1] is check_certification_matrix

    def test_check_id_is_certification_matrix(self, shared_check_result):
        assert shared_check_result is not None, "certification_matrix check not found in shared_checks"
        assert shared_check_result.check_id == "certification_matrix"

    def test_category_is_certification(self, shared_check_result):
        assert shared_check_result.category == "certification"

    def test_status_is_valid(self, shared_check_result):
        from openjarvis.doctor.checks import CheckStatus
        valid = {CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.NOT_CONFIGURED}
        assert shared_check_result.status in valid

    def test_evidence_has_total_items(self, shared_check_result):
        assert "total_items" in shared_check_result.evidence
        assert shared_check_result.evidence["total_items"] == 12

    def test_evidence_has_failure_modes_documented(self, shared_check_result):
        assert "failure_modes_documented" in shared_check_result.evidence
        assert shared_check_result.evidence["failure_modes_documented"] == 8

    def test_no_empty_evidence_items(self, shared_check_result):
        assert shared_check_result.evidence.get("empty_evidence_items") == []


# ---------------------------------------------------------------------------
# 12. Readiness integration — CERTIFICATION category (28th)  (pure + 1 live call)
# ---------------------------------------------------------------------------


class TestReadinessCertificationCategory:
    def test_certification_constant_exists(self):
        from openjarvis.doctor.readiness import ReadinessCategory
        assert ReadinessCategory.CERTIFICATION == "certification"

    def test_certification_in_category_checks(self):
        from openjarvis.doctor.readiness import _CATEGORY_CHECKS, ReadinessCategory
        assert ReadinessCategory.CERTIFICATION in _CATEGORY_CHECKS

    def test_certification_maps_to_certification_matrix_check(self):
        from openjarvis.doctor.readiness import _CATEGORY_CHECKS, ReadinessCategory
        check_ids = _CATEGORY_CHECKS[ReadinessCategory.CERTIFICATION]
        assert "certification_matrix" in check_ids

    def test_certification_not_required(self):
        from openjarvis.doctor.readiness import _REQUIRED_CATEGORIES, ReadinessCategory
        assert ReadinessCategory.CERTIFICATION not in _REQUIRED_CATEGORIES

    def test_total_categories_is_28(self):
        from openjarvis.doctor.readiness import _CATEGORY_CHECKS
        assert len(_CATEGORY_CHECKS) == 28

    def test_evaluate_readiness_has_28_categories(self, shared_checks):
        from openjarvis.doctor.readiness import evaluate_readiness
        report = evaluate_readiness(project_id="omnix", check_results=shared_checks)
        assert len(report.categories) == 28

    def test_certification_category_in_report(self, shared_checks):
        from openjarvis.doctor.readiness import evaluate_readiness, ReadinessCategory
        report = evaluate_readiness(project_id="omnix", check_results=shared_checks)
        cat_names = {c.category for c in report.categories}
        assert ReadinessCategory.CERTIFICATION in cat_names

    def test_us13_checkpoint_in_accepted_checkpoints(self):
        from openjarvis.doctor.readiness import _ACCEPTED_CHECKPOINTS
        combined = "\n".join(_ACCEPTED_CHECKPOINTS)
        assert "Ultra Sprint 13" in combined

    def test_accepted_checkpoints_count(self):
        from openjarvis.doctor.readiness import _ACCEPTED_CHECKPOINTS
        assert len(_ACCEPTED_CHECKPOINTS) >= 14
