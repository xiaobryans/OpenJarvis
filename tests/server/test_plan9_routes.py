"""Plan 9 — Server Route Tests.

Tests every route wired in plan9_routes.py:
  - GET  /v1/capabilities/status
  - GET  /v1/capabilities/matrix-summary
  - GET  /v1/parity/status
  - GET  /v1/model-routing/matrix
  - POST /v1/model-routing/explain
  - GET  /v1/orchestration/policy
  - GET  /v1/coding/workspace
  - POST /v1/coding/files/read
  - POST /v1/coding/diff/stage
  - POST /v1/testing/run
  - POST /v1/testing/lint
  - POST /v1/git/commit
  - POST /v1/deploy/plan
  - GET  /v1/mac-worker/queue
  - POST /v1/mac-worker/queue
  - GET  /v1/mac-worker/status
  - GET  /v1/plan9/rules
  - GET  /v1/plan9/skills
  - GET  /v1/plan9/commands
  - GET  /v1/plan9/inheritance

Key assertions:
  - /v1/capabilities/status contains every discovered manager
  - /v1/capabilities/status enriches with routing + retrieval policy
  - /v1/parity/status includes PA and brain layer summaries
  - /v1/model-routing/matrix covers all 52 roles
  - /v1/model-routing/explain returns correct tier for risk/complexity
  - /v1/orchestration/policy exposes batch integration + integration review roles
  - /v1/git/commit dry_run=True never commits + secret scan passes
  - /v1/git/commit without approval_token returns plan only
  - /v1/deploy/plan always returns approval_required=True
  - /v1/mac-worker/queue submit + retrieve works
  - No secrets in any route response
  - Future inheritance visible via /v1/plan9/inheritance
"""

from __future__ import annotations

import json
import re

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.plan9_routes import router
import openjarvis.server.plan9_routes as _routes_module


# ---------------------------------------------------------------------------
# Test app factory — isolated mac worker queue per test
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture()
def client(monkeypatch):
    """Fresh TestClient with isolated mac worker queue per test."""
    _routes_module._routes_module = None  # no state on module level
    # Reset mac worker queue singleton for isolation
    import openjarvis.plan9.mac_worker_queue as mwq
    monkeypatch.setattr(mwq, "_MAC_QUEUE", None)
    app = _make_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# Known manager IDs from plan9 architecture
KNOWN_MANAGER_IDS = [
    "coding_manager", "architecture_manager", "testing_validation_manager",
    "code_review_manager", "debugging_manager", "research_manager",
    "memory_knowledge_manager", "documentation_manager", "product_ux_manager",
    "operations_automation_manager", "governance_safety_manager",
    "release_packaging_manager", "data_manager", "cost_routing_manager",
    "nus_learning_manager", "connector_auth_manager", "runtime_ops_manager",
]

_SECRET_ACTUAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xoxp-[0-9]+-[0-9]+-"),
    re.compile(r"xoxb-[0-9]+-"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"gho_[A-Za-z0-9]{36,}"),
    re.compile(r"Bearer eyJ[A-Za-z0-9+/=]{20,}"),
]


def _assert_no_secrets(response_text: str) -> None:
    for pattern in _SECRET_ACTUAL_PATTERNS:
        assert not pattern.search(response_text), (
            f"Secret pattern {pattern.pattern!r} found in response"
        )


# ============================================================================
# /v1/capabilities/status
# ============================================================================

class TestCapabilitiesStatus:

    def test_returns_200(self, client):
        r = client.get("/v1/capabilities/status")
        assert r.status_code == 200

    def test_has_capabilities_list(self, client):
        r = client.get("/v1/capabilities/status")
        data = r.json()
        assert "capabilities" in data
        assert "total" in data
        assert data["total"] > 0

    def test_contains_all_manager_domains(self, client):
        r = client.get("/v1/capabilities/status")
        data = r.json()
        present_domains = {c["domain"] for c in data["capabilities"]}
        for manager_id in KNOWN_MANAGER_IDS:
            assert manager_id in present_domains, (
                f"Manager {manager_id!r} not found in /v1/capabilities/status domains"
            )

    def test_entries_enriched_with_routing(self, client):
        r = client.get("/v1/capabilities/status")
        data = r.json()
        # Find a manager-domain entry
        coding = [c for c in data["capabilities"] if c["domain"] == "coding_manager"]
        assert len(coding) > 0
        for c in coding:
            assert "routing" in c, "Capability entry missing routing enrichment"
            assert "retrieval_policy" in c, "Capability entry missing retrieval_policy enrichment"
            assert "audit_required" in c

    def test_filter_by_domain(self, client):
        r = client.get("/v1/capabilities/status?domain=mac_worker")
        assert r.status_code == 200
        data = r.json()
        for c in data["capabilities"]:
            assert c["domain"] == "mac_worker"

    def test_filter_by_status(self, client):
        r = client.get("/v1/capabilities/status?status=PARKED")
        assert r.status_code == 200
        data = r.json()
        for c in data["capabilities"]:
            assert c["status"] == "PARKED"

    def test_parked_items_include_voice(self, client):
        r = client.get("/v1/capabilities/status?status=PARKED")
        data = r.json()
        ids = [c["capability_id"] for c in data["capabilities"]]
        assert "voice_wake_tts" in ids, "voice_wake_tts must be in PARKED capabilities"

    def test_no_secrets_in_response(self, client):
        r = client.get("/v1/capabilities/status")
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/capabilities/matrix-summary
# ============================================================================

class TestCapabilitiesMatrixSummary:

    def test_returns_200(self, client):
        r = client.get("/v1/capabilities/matrix-summary")
        assert r.status_code == 200

    def test_has_summary_and_counts(self, client):
        r = client.get("/v1/capabilities/matrix-summary")
        data = r.json()
        assert "summary" in data
        assert "total" in data
        assert data["total"] > 0
        assert "parked" in data
        assert "gaps" in data

    def test_summary_counts_add_up(self, client):
        r = client.get("/v1/capabilities/matrix-summary")
        data = r.json()
        assert sum(data["summary"].values()) == data["total"]

    def test_voice_in_parked(self, client):
        r = client.get("/v1/capabilities/matrix-summary")
        data = r.json()
        parked_ids = [p["capability_id"] for p in data["parked"]]
        assert "voice_wake_tts" in parked_ids


# ============================================================================
# /v1/parity/status
# ============================================================================

class TestParityStatus:

    def test_returns_200(self, client):
        r = client.get("/v1/parity/status")
        assert r.status_code == 200

    def test_has_parity_definition(self, client):
        r = client.get("/v1/parity/status")
        data = r.json()
        assert "parity_definition" in data
        assert "MacBook" in data["parity_definition"]
        assert "mobile" in data["parity_definition"].lower() or "cloud" in data["parity_definition"].lower()

    def test_has_pa_layer(self, client):
        r = client.get("/v1/parity/status")
        data = r.json()
        assert "pa_layer" in data
        assert data["pa_layer"]["layer"] == "jarvis_pa"

    def test_has_brain_layer(self, client):
        r = client.get("/v1/parity/status")
        data = r.json()
        assert "brain_layer" in data
        assert data["brain_layer"]["multi_provider"] is True

    def test_has_accepted_exception(self, client):
        r = client.get("/v1/parity/status")
        data = r.json()
        assert "accepted_exception" in data
        assert "/Applications/OpenJarvis.app" in data["accepted_exception"]

    def test_mobile_cloud_live_count_positive(self, client):
        r = client.get("/v1/parity/status")
        data = r.json()
        assert data["mobile_cloud_live"] > 0

    def test_parked_appears_in_parity(self, client):
        r = client.get("/v1/parity/status")
        data = r.json()
        parked_ids = [p["capability_id"] for p in data["parked"]]
        assert "voice_wake_tts" in parked_ids


# ============================================================================
# /v1/model-routing/matrix
# ============================================================================

class TestModelRoutingMatrix:

    def test_returns_200(self, client):
        r = client.get("/v1/model-routing/matrix")
        assert r.status_code == 200

    def test_has_52_plus_roles(self, client):
        r = client.get("/v1/model-routing/matrix")
        data = r.json()
        assert data["role_count"] >= 52

    def test_no_validation_errors(self, client):
        r = client.get("/v1/model-routing/matrix")
        data = r.json()
        assert data["validation_errors"] == [], (
            f"Model routing matrix has validation errors: {data['validation_errors']}"
        )

    def test_all_managers_in_matrix(self, client):
        r = client.get("/v1/model-routing/matrix")
        data = r.json()
        role_ids = {e["role_id"] for e in data["roles"]}
        for manager_id in KNOWN_MANAGER_IDS:
            assert manager_id in role_ids, (
                f"Manager {manager_id!r} missing from model routing matrix"
            )

    def test_has_default_routing(self, client):
        r = client.get("/v1/model-routing/matrix")
        data = r.json()
        assert "default_routing" in data
        assert data["default_routing"]["role_id"] == "__default__"

    def test_cheap_balanced_best_all_present(self, client):
        r = client.get("/v1/model-routing/matrix")
        data = r.json()
        for entry in data["roles"]:
            assert entry["cheap_model"], f"{entry['role_id']}: missing cheap_model"
            assert entry["balanced_model"], f"{entry['role_id']}: missing balanced_model"
            assert entry["best_model"], f"{entry['role_id']}: missing best_model"


# ============================================================================
# /v1/model-routing/explain
# ============================================================================

class TestModelRoutingExplain:

    def test_returns_200(self, client):
        r = client.post("/v1/model-routing/explain", json={
            "role": "coding_manager", "risk": "medium", "complexity": "moderate"
        })
        assert r.status_code == 200

    def test_high_risk_returns_best(self, client):
        r = client.post("/v1/model-routing/explain", json={
            "role": "coding_manager", "risk": "high", "complexity": "complex"
        })
        data = r.json()
        assert data["recommended_tier"] == "best"

    def test_low_risk_returns_cheap(self, client):
        r = client.post("/v1/model-routing/explain", json={
            "role": "coding_manager", "risk": "low", "complexity": "simple"
        })
        data = r.json()
        assert data["recommended_tier"] == "cheap"

    def test_3_failures_returns_stop(self, client):
        r = client.post("/v1/model-routing/explain", json={
            "role": "coding_manager", "risk": "medium", "complexity": "moderate", "failures": 3
        })
        data = r.json()
        assert data["recommended_tier"] == "stop"

    def test_unknown_role_inherits_default(self, client):
        r = client.post("/v1/model-routing/explain", json={
            "role": "nonexistent_future_role_xyz", "risk": "medium"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_default_inherited"] is True

    def test_response_has_all_required_fields(self, client):
        r = client.post("/v1/model-routing/explain", json={"role": "architecture_manager"})
        data = r.json()
        for field in ["recommended_tier", "recommended_model", "escalation_rule",
                      "cost_justification", "fallback_rule"]:
            assert field in data, f"Missing field {field!r} in model-routing/explain"


# ============================================================================
# /v1/orchestration/policy
# ============================================================================

class TestOrchestrationPolicy:

    def test_returns_200(self, client):
        r = client.get("/v1/orchestration/policy")
        assert r.status_code == 200

    def test_has_batch_integration(self, client):
        r = client.get("/v1/orchestration/policy")
        data = r.json()
        bi = data["batch_integration"]
        assert bi["workers_propose_in_parallel"] is True
        assert bi["integration_is_sequential"] is True
        assert bi["max_concurrent_master_writes"] == 1
        assert bi["no_patch_may_be_dropped_silently"] is True

    def test_has_integration_review(self, client):
        r = client.get("/v1/orchestration/policy")
        data = r.json()
        ir = data["integration_review"]
        assert ir["reviewer_must_differ_from_integrator"] is True
        assert ir["must_verify_all_items"] is True
        assert ir["must_verify_no_secret"] is True

    def test_batch_integration_manager_role(self, client):
        r = client.get("/v1/orchestration/policy")
        data = r.json()
        assert data["batch_integration"]["integrator_role"] == "batch_integration_manager"
        assert data["batch_integration"]["reviewer_role"] == "integration_review_manager"

    def test_parallel_dag_has_safety_rules(self, client):
        r = client.get("/v1/orchestration/policy")
        data = r.json()
        rules = data["parallel_dag"]["safety_rules"]
        assert len(rules) > 0
        safe_actions = [r["action_type"] for r in rules if r["safety"] == "SAFE"]
        assert "retrieval" in safe_actions
        assert "file_read" in safe_actions

    def test_commit_is_unsafe_in_dag(self, client):
        r = client.get("/v1/orchestration/policy")
        data = r.json()
        rules = {r["action_type"]: r for r in data["parallel_dag"]["safety_rules"]}
        assert "git_commit" in rules
        assert rules["git_commit"]["safety"] != "SAFE"
        assert rules["git_commit"]["lock_required"] is True

    def test_all_17_managers_have_retrieval_policy(self, client):
        r = client.get("/v1/orchestration/policy")
        data = r.json()
        retrieval = data["retrieval_worker_policies"]
        for manager_id in KNOWN_MANAGER_IDS:
            assert manager_id in retrieval, (
                f"Manager {manager_id!r} missing from retrieval worker policies"
            )

    def test_elastic_pool_git_commit_is_single_executor(self, client):
        r = client.get("/v1/orchestration/policy")
        data = r.json()
        pools = {p["role_id"]: p for p in data["elastic_pools"]["roles"]}
        assert "git_commit_worker" in pools
        assert pools["git_commit_worker"]["single_executor_only"] is True
        assert pools["git_commit_worker"]["max_workers"] == 1


# ============================================================================
# /v1/coding/workspace
# ============================================================================

class TestCodingWorkspace:

    def test_returns_200(self, client):
        r = client.get("/v1/coding/workspace")
        assert r.status_code == 200

    def test_has_operations(self, client):
        r = client.get("/v1/coding/workspace")
        data = r.json()
        assert "operations" in data
        assert len(data["operations"]) > 0

    def test_cloud_safe_flag(self, client):
        r = client.get("/v1/coding/workspace")
        data = r.json()
        assert data["cloud_safe"] is True
        assert data["mac_required"] is False


# ============================================================================
# /v1/coding/files/read
# ============================================================================

class TestCodingFilesRead:

    def test_read_allowed_file(self, client):
        r = client.post("/v1/coding/files/read", json={"file_path": "pyproject.toml"})
        assert r.status_code == 200
        data = r.json()
        assert "content" in data
        assert len(data["content"]) > 0

    def test_read_src_file(self, client):
        r = client.post("/v1/coding/files/read", json={
            "file_path": "src/openjarvis/plan9/__init__.py",
            "start_line": 1, "end_line": 5
        })
        assert r.status_code == 200
        data = r.json()
        assert data["secret_scan"]["status"] == "CLEAN"

    def test_path_traversal_blocked(self, client):
        r = client.post("/v1/coding/files/read", json={"file_path": "../../etc/passwd"})
        assert r.status_code == 400

    def test_env_file_blocked(self, client):
        r = client.post("/v1/coding/files/read", json={"file_path": ".env"})
        assert r.status_code == 403

    def test_absolute_path_blocked(self, client):
        r = client.post("/v1/coding/files/read", json={"file_path": "/etc/hosts"})
        assert r.status_code == 400

    def test_non_allowlisted_path_blocked(self, client):
        r = client.post("/v1/coding/files/read", json={"file_path": "Makefile"})
        assert r.status_code == 403

    def test_response_no_secrets(self, client):
        r = client.post("/v1/coding/files/read", json={"file_path": "pyproject.toml"})
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/coding/diff/stage
# ============================================================================

class TestCodingDiffStage:

    def test_dry_run_default(self, client):
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/openjarvis/plan9/__init__.py",
            "diff_hunk": "--- a/foo.py\n+++ b/foo.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "DRY_RUN"
        assert data["secret_scan"] == "CLEAN"
        assert data["approval_required_for_write"] is True

    def test_no_approval_for_write_rejected(self, client):
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/foo.py",
            "diff_hunk": "+new line",
            "dry_run": False,
        })
        assert r.status_code == 403

    def test_secret_in_diff_aborted(self, client):
        # Fake key assembled at runtime so it doesn't match scanner outside the test context
        fake = "sk-" + "a" * 21  # clearly-fake pattern used only to exercise scanning
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/foo.py",
            "diff_hunk": f"+api_key = '{fake}'",
        })
        assert r.status_code == 400


# ============================================================================
# /v1/testing/run
# ============================================================================

class TestTestingRun:

    def test_no_paths_returns_skipped(self, client):
        r = client.post("/v1/testing/run", json={"test_paths": []})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "SKIPPED"

    def test_plan9_tests_pass(self, client):
        r = client.post("/v1/testing/run", json={
            "test_paths": ["tests/test_plan9_cross_device_parity.py"],
            "timeout_seconds": 60,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "PASSED", (
            f"Plan 9 tests failed via API. stdout: {data.get('stdout', '')[:500]}"
        )

    def test_injection_blocked(self, client):
        r = client.post("/v1/testing/run", json={"test_paths": ["tests/; rm -rf /"]})
        assert r.status_code == 400

    def test_response_has_return_code(self, client):
        r = client.post("/v1/testing/run", json={
            "test_paths": ["tests/test_plan9_cross_device_parity.py"],
            "timeout_seconds": 60,
        })
        data = r.json()
        assert "return_code" in data
        assert "stdout" in data


# ============================================================================
# /v1/testing/lint
# ============================================================================

class TestTestingLint:

    def test_lint_plan9_module(self, client):
        r = client.post("/v1/testing/lint", json={
            "file_paths": ["src/openjarvis/plan9/"],
            "linter": "ruff",
        })
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "results" in data

    def test_lint_server_routes_file(self, client):
        r = client.post("/v1/testing/lint", json={
            "file_paths": ["src/openjarvis/server/plan9_routes.py"],
            "linter": "ruff",
        })
        assert r.status_code == 200


# ============================================================================
# /v1/git/commit
# ============================================================================

class TestGitCommit:

    def test_dry_run_default_no_commit(self, client):
        """dry_run=True (default) must NEVER commit."""
        r = client.post("/v1/git/commit", json={
            "commit_message": "plan9: dry run validation test",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["committed"] is False
        assert data["mode"] == "DRY_RUN"
        assert data["approval_required"] is True

    def test_no_approval_token_no_commit(self, client):
        """Without approval_token, must remain dry-run."""
        r = client.post("/v1/git/commit", json={
            "commit_message": "plan9: no token test",
            "dry_run": False,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["committed"] is False
        assert "approval_required" in data

    def test_secret_in_diff_aborts(self, client, monkeypatch):
        """If diff contains a secret pattern, abort immediately."""
        import subprocess

        fake_diff = "+api_key = '" + "sk-" + "a" * 21 + "'"  # clearly-fake test key
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            import types
            if isinstance(cmd, list) and "git" in cmd and "diff" in cmd:
                r = types.SimpleNamespace()
                r.stdout = fake_diff
                r.returncode = 0
                return r
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)
        r = client.post("/v1/git/commit", json={"commit_message": "test: scan"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ABORTED"
        assert data["committed"] is False

    def test_dry_run_includes_secret_scan(self, client):
        r = client.post("/v1/git/commit", json={"commit_message": "test: dry run check"})
        data = r.json()
        assert "secret_scan" in data
        assert data["secret_scan"]["abort_required"] is False

    def test_no_secrets_in_response(self, client):
        r = client.post("/v1/git/commit", json={"commit_message": "test: secret check"})
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/deploy/plan
# ============================================================================

class TestDeployPlan:

    def test_always_returns_approval_required(self, client):
        r = client.post("/v1/deploy/plan", json={
            "deploy_target": "ecs-fargate",
            "image_tag": "v1.2.3",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["approval_required"] is True
        assert data["executed"] is False

    def test_mode_is_dry_run_plan_only(self, client):
        r = client.post("/v1/deploy/plan", json={"deploy_target": "ecs-fargate"})
        data = r.json()
        assert "DRY_RUN" in data["mode"]

    def test_has_rollback_plan(self, client):
        r = client.post("/v1/deploy/plan", json={"deploy_target": "ecs-fargate"})
        data = r.json()
        assert "rollback_plan" in data
        assert len(data["rollback_plan"]) > 0

    def test_has_deploy_steps(self, client):
        r = client.post("/v1/deploy/plan", json={"deploy_target": "vercel"})
        data = r.json()
        assert "plan" in data
        assert len(data["plan"]) > 0

    def test_no_secrets_in_deploy_response(self, client):
        r = client.post("/v1/deploy/plan", json={"deploy_target": "ecs-fargate"})
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/mac-worker/queue + /v1/mac-worker/status
# ============================================================================

class TestMacWorkerRoutes:

    def test_get_queue_empty(self, client):
        r = client.get("/v1/mac-worker/queue")
        assert r.status_code == 200
        data = r.json()
        assert "queue_status" in data
        assert data["queue_status"]["total"] == 0

    def test_submit_mac_task(self, client):
        r = client.post("/v1/mac-worker/queue", json={
            "task_type": "app_reinstall",
            "display_name": "Reinstall OpenJarvis.app",
            "submitted_from": "mobile",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "QUEUED"
        assert "task_id" in data

    def test_task_appears_in_queue(self, client):
        # Submit
        r1 = client.post("/v1/mac-worker/queue", json={
            "task_type": "app_reinstall",
            "display_name": "Test Task",
            "submitted_from": "mobile",
        })
        task_id = r1.json()["task_id"]

        # Retrieve
        r2 = client.get("/v1/mac-worker/queue")
        data = r2.json()
        task_ids = [t["task_id"] for t in data["tasks"]]
        assert task_id in task_ids

    def test_status_shows_summary(self, client):
        r = client.get("/v1/mac-worker/status")
        assert r.status_code == 200
        data = r.json()
        assert "queue_status" in data
        assert "mac_only_task_types" in data
        assert "cloud_native_task_types" in data
        assert "app_reinstall" in data["mac_only_task_types"]

    def test_invalid_task_type_rejected(self, client):
        r = client.post("/v1/mac-worker/queue", json={
            "task_type": "not_a_real_type",
            "display_name": "Bad task",
        })
        assert r.status_code == 400

    def test_mac_queue_visible_from_both_surfaces(self, client):
        """Queue status is same regardless of how you fetch it (both surfaces share queue)."""
        client.post("/v1/mac-worker/queue", json={
            "task_type": "mac_app_control",
            "display_name": "Control Finder",
        })
        # "MacBook" surface read
        mac_r = client.get("/v1/mac-worker/queue")
        # "Mobile" surface read (same endpoint)
        mobile_r = client.get("/v1/mac-worker/status")
        mac_count = mac_r.json()["queue_status"]["total"]
        mobile_summary = mobile_r.json()["queue_status"]["total"]
        assert mac_count == mobile_summary

    def test_no_secrets_in_mac_queue(self, client):
        r = client.get("/v1/mac-worker/queue")
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/plan9/rules, /v1/plan9/skills, /v1/plan9/commands, /v1/plan9/inheritance
# ============================================================================

class TestPlan9Introspection:

    def test_rules_returns_200(self, client):
        r = client.get("/v1/plan9/rules")
        assert r.status_code == 200

    def test_rules_has_21_entries(self, client):
        r = client.get("/v1/plan9/rules")
        data = r.json()
        assert data["total"] == 21

    def test_rules_filter_by_category(self, client):
        r = client.get("/v1/plan9/rules?category=PARKED")
        data = r.json()
        for rule in data["rules"]:
            assert rule["category"] == "PARKED"

    def test_skills_returns_21(self, client):
        r = client.get("/v1/plan9/skills")
        data = r.json()
        assert data["total"] == 21

    def test_skills_filter_by_status(self, client):
        r = client.get("/v1/plan9/skills?status=WIRED")
        data = r.json()
        for skill in data["skills"]:
            assert skill["status"] == "WIRED"

    def test_commands_returns_20(self, client):
        r = client.get("/v1/plan9/commands")
        data = r.json()
        assert data["total"] == 20

    def test_registry_returns_live_roles(self, client):
        r = client.get("/v1/plan9/registry")
        assert r.status_code == 200
        data = r.json()
        assert data["total_roles"] > 0
        assert data["total_managers"] > 0
        assert data["total_workers"] > 0
        assert len(data["roles"]) == data["total_roles"]
        assert "routed_model" in data["roles"][0]

    def test_inheritance_has_key_fields(self, client):
        r = client.get("/v1/plan9/inheritance")
        assert r.status_code == 200
        data = r.json()
        assert data["retrieval_worker_required"] is True
        assert data["must_appear_in_capability_matrix"] is True
        assert data["audit_events_required"] is True
        assert data["bryan_approval_required_for_sensitive"] is True
        assert data["mobile_parity_required"] is True
        assert data["mac_parity_required"] is True

    def test_no_secrets_in_introspection(self, client):
        for path in ["/v1/plan9/rules", "/v1/plan9/skills", "/v1/plan9/commands", "/v1/plan9/inheritance", "/v1/plan9/registry"]:
            r = client.get(path)
            _assert_no_secrets(r.text)


# ============================================================================
# Cross-cutting: no secrets in any Plan 9 route response
# ============================================================================

class TestNoSecretsInAnyRoute:

    def test_all_get_routes_no_secrets(self, client):
        get_routes = [
            "/v1/capabilities/status",
            "/v1/capabilities/matrix-summary",
            "/v1/parity/status",
            "/v1/model-routing/matrix",
            "/v1/orchestration/policy",
            "/v1/coding/workspace",
            "/v1/mac-worker/queue",
            "/v1/mac-worker/status",
            "/v1/plan9/rules",
            "/v1/plan9/skills",
            "/v1/plan9/commands",
            "/v1/plan9/inheritance",
            "/v1/plan9/registry",
        ]
        for route in get_routes:
            r = client.get(route)
            _assert_no_secrets(r.text)
