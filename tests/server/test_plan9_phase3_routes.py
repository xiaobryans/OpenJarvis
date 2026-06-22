"""Plan 9 Phase 3 — Server Route Tests.

Tests for newly wired routes:
  - POST /v1/coding/search
  - POST /v1/coding/create-branch
  - POST /v1/coding/diff/stage  (upgraded: real git apply --cached + approval-gated)
  - POST /v1/git/push
  - GET  /v1/files/index
  - GET  /v1/plan9/runtime-proof-checklist

Key assertions:
  - search: allowlisted paths only, secret-safe output, injection-blocked
  - create-branch: dry-run default, approval-gated, protected branch blocked, bad name rejected
  - diff/stage: write without approval rejected, secret in diff aborted, dry-run never mutates git state
  - push: dry-run default no actual push, force push to main/master blocked, secret in diff aborts
  - files/index: metadata only (no content), allowlisted paths, traversal blocked
  - runtime-proof-checklist: all 8 items, categories present, no secrets
"""

from __future__ import annotations

import re

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.plan9_routes import router
import openjarvis.plan9.mac_worker_queue as mwq


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(mwq, "_MAC_QUEUE", None)
    app = _make_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer eyJ[A-Za-z0-9+/=]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY"),
]


def _assert_no_secrets(text: str) -> None:
    for p in _SECRET_PATTERNS:
        assert not p.search(text), f"Secret pattern {p.pattern!r} in response"


# ============================================================================
# /v1/coding/search
# ============================================================================

class TestCodingSearch:

    def test_basic_search_returns_200(self, client):
        r = client.post("/v1/coding/search", json={"query": "Plan9CapabilityEntry"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "OK"

    def test_finds_known_symbol(self, client):
        r = client.post("/v1/coding/search", json={
            "query": "Plan9CapabilityEntry",
            "paths": ["src/openjarvis/plan9/"],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0
        assert any("plan9" in result["file"] for result in data["results"])

    def test_default_paths_are_allowlisted(self, client):
        r = client.post("/v1/coding/search", json={"query": "import"})
        assert r.status_code == 200
        data = r.json()
        for result in data["results"]:
            assert any(result["file"].startswith(p) for p in ("src/", "tests/", "docs/"))

    def test_non_allowlisted_path_blocked(self, client):
        r = client.post("/v1/coding/search", json={
            "query": "secret",
            "paths": [".git/"],
        })
        assert r.status_code == 403

    def test_path_traversal_blocked(self, client):
        r = client.post("/v1/coding/search", json={
            "query": "secret",
            "paths": ["../../../etc/"],
        })
        assert r.status_code == 400

    def test_max_results_respected(self, client):
        r = client.post("/v1/coding/search", json={
            "query": "def ",
            "max_results": 5,
        })
        assert r.status_code == 200
        assert r.json()["count"] <= 5

    def test_secret_in_results_suppressed(self, client, tmp_path, monkeypatch):
        """If search results contain a secret pattern, they must be suppressed."""
        import subprocess
        # Build a fake rg output that contains a secret-looking value
        fake_key = "sk-" + "z" * 21
        fake_rg_output = (
            '{"type":"match","data":{"path":{"text":"src/test.py"},'
            '"line_number":1,"lines":{"text":"key = \'' + fake_key + '\'\\n"}}}\n'
        )
        original_run = subprocess.run

        def mock_rg(cmd, **kwargs):
            import types
            if isinstance(cmd, list) and cmd and cmd[0] == "rg":
                r = types.SimpleNamespace()
                r.stdout = fake_rg_output
                r.returncode = 0
                r.stderr = ""
                return r
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_rg)
        r = client.post("/v1/coding/search", json={"query": "key"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "SECRET_DETECTED"
        assert data["count"] == 0
        assert data["results"] == []

    def test_short_query_rejected(self, client):
        r = client.post("/v1/coding/search", json={"query": "x"})
        assert r.status_code == 422

    def test_regex_search(self, client):
        r = client.post("/v1/coding/search", json={
            "query": r"class Plan9\w+",
            "regex": True,
            "paths": ["src/openjarvis/plan9/"],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "OK"

    def test_no_secrets_in_response(self, client):
        r = client.post("/v1/coding/search", json={"query": "CapabilityStatus"})
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/coding/create-branch
# ============================================================================

class TestCreateBranch:

    def test_dry_run_default_no_create(self, client):
        r = client.post("/v1/coding/create-branch", json={
            "branch_name": "plan9/test-branch",
            "base_branch": "main",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "DRY_RUN"
        assert data["approval_required_for_create"] is True

    def test_dry_run_shows_command_preview(self, client):
        r = client.post("/v1/coding/create-branch", json={
            "branch_name": "feature/test-123",
        })
        data = r.json()
        assert "git checkout -b" in data["command_preview"]
        assert "feature/test-123" in data["command_preview"]

    def test_no_approval_write_rejected(self, client):
        r = client.post("/v1/coding/create-branch", json={
            "branch_name": "feature/no-token",
            "dry_run": False,
        })
        assert r.status_code == 403

    def test_protected_branch_name_blocked(self, client):
        for name in ("main", "master", "production", "prod"):
            r = client.post("/v1/coding/create-branch", json={
                "branch_name": name,
            })
            assert r.status_code == 403, f"Protected branch {name!r} should be rejected"

    def test_unsafe_branch_name_rejected(self, client):
        for bad in ("../bad", "bad branch", "bad;cmd", "a" * 101):
            r = client.post("/v1/coding/create-branch", json={
                "branch_name": bad,
            })
            assert r.status_code in (400, 422), f"Bad branch name {bad!r} should be rejected"

    def test_safe_branch_names_accepted(self, client):
        safe_names = [
            "plan9/feature-x", "fix/issue-42", "feature_new", "v1.2.3-rc1",
        ]
        for name in safe_names:
            r = client.post("/v1/coding/create-branch", json={"branch_name": name})
            assert r.status_code == 200, f"Safe branch name {name!r} was rejected"
            assert r.json()["mode"] == "DRY_RUN"

    def test_no_secrets_in_response(self, client):
        r = client.post("/v1/coding/create-branch", json={"branch_name": "plan9/test"})
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/coding/diff/stage  (upgraded)
# ============================================================================

class TestDiffStageUpgraded:

    VALID_DIFF = (
        "--- a/src/openjarvis/plan9/__init__.py\n"
        "+++ b/src/openjarvis/plan9/__init__.py\n"
        "@@ -1,1 +1,2 @@\n"
        " # Plan 9\n"
        "+# Phase 3\n"
    )

    def test_dry_run_default_does_not_mutate_git(self, client, monkeypatch):
        """dry_run=True must never call git apply."""
        called = []
        import subprocess
        original = subprocess.run

        def spy_run(cmd, **kwargs):
            if isinstance(cmd, list) and "apply" in cmd:
                called.append(cmd)
            return original(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", spy_run)
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/test.py",
            "diff_hunk": self.VALID_DIFF,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "DRY_RUN"
        assert not any("apply" in " ".join(c) for c in called), (
            "git apply was called during dry_run=True — git state was mutated"
        )

    def test_write_without_approval_rejected(self, client):
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/test.py",
            "diff_hunk": self.VALID_DIFF,
            "dry_run": False,
        })
        assert r.status_code == 403

    def test_secret_in_diff_aborts(self, client):
        fake_key = "sk-" + "a" * 21
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/test.py",
            "diff_hunk": f"+api_key = '{fake_key}'",
        })
        assert r.status_code == 400

    def test_dry_run_returns_diff_line_count(self, client):
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/test.py",
            "diff_hunk": self.VALID_DIFF,
        })
        data = r.json()
        assert "diff_lines" in data
        assert data["diff_lines"] > 0

    def test_dry_run_secret_scan_clean(self, client):
        r = client.post("/v1/coding/diff/stage", json={
            "file_path": "src/test.py",
            "diff_hunk": self.VALID_DIFF,
        })
        data = r.json()
        assert data["secret_scan"] == "CLEAN"


# ============================================================================
# /v1/git/push
# ============================================================================

class TestGitPush:

    def test_dry_run_default_no_push(self, client):
        r = client.post("/v1/git/push", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "DRY_RUN"
        assert data["pushed"] is False
        assert data["approval_required"] is True

    def test_no_approval_stays_dry_run(self, client):
        r = client.post("/v1/git/push", json={"dry_run": False})
        assert r.status_code == 200
        data = r.json()
        assert data["pushed"] is False

    def test_force_to_main_blocked(self, client):
        r = client.post("/v1/git/push", json={
            "branch": "main",
            "force": True,
            "confirm_force": True,
        })
        assert r.status_code == 403

    def test_force_to_master_blocked(self, client):
        r = client.post("/v1/git/push", json={
            "branch": "master",
            "force": True,
            "confirm_force": True,
        })
        assert r.status_code == 403

    def test_force_requires_confirm_force(self, client):
        r = client.post("/v1/git/push", json={
            "branch": "feature/x",
            "force": True,
            "confirm_force": False,
        })
        assert r.status_code == 400

    def test_dry_run_returns_commits_to_push(self, client):
        r = client.post("/v1/git/push", json={})
        data = r.json()
        assert "commits_to_push" in data
        assert "branch" in data

    def test_secret_in_diff_aborts_push(self, client, monkeypatch):
        import subprocess
        fake_key = "sk-" + "b" * 21
        original = subprocess.run

        def mock_run(cmd, **kwargs):
            import types
            if isinstance(cmd, list) and "git" in cmd and "diff" in cmd:
                r = types.SimpleNamespace()
                r.stdout = f"+key = '{fake_key}'"
                r.returncode = 0
                return r
            return original(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)
        r = client.post("/v1/git/push", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ABORTED"
        assert data["pushed"] is False

    def test_no_secrets_in_response(self, client):
        r = client.post("/v1/git/push", json={})
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/files/index
# ============================================================================

class TestFilesIndex:

    def test_returns_200(self, client):
        r = client.get("/v1/files/index")
        assert r.status_code == 200

    def test_returns_files_list(self, client):
        r = client.get("/v1/files/index")
        data = r.json()
        assert "files" in data
        assert data["total"] > 0

    def test_files_have_metadata_not_content(self, client):
        r = client.get("/v1/files/index")
        data = r.json()
        for f in data["files"][:5]:
            assert "path" in f
            assert "size_bytes" in f
            assert "modified_ts" in f
            assert "content" not in f  # content must never appear

    def test_paths_are_allowlisted(self, client):
        r = client.get("/v1/files/index")
        data = r.json()
        for f in data["files"]:
            assert any(
                f["path"].startswith(p) for p in ("src/", "tests/", "docs/", "configs/")
            ), f"File {f['path']!r} not in allowlist"

    def test_path_prefix_filter(self, client):
        r = client.get("/v1/files/index?path_prefix=src/openjarvis/plan9/")
        assert r.status_code == 200
        data = r.json()
        for f in data["files"]:
            assert f["path"].startswith("src/openjarvis/plan9/")

    def test_traversal_blocked(self, client):
        r = client.get("/v1/files/index?path_prefix=../../etc/")
        assert r.status_code == 400

    def test_non_allowlisted_prefix_blocked(self, client):
        r = client.get("/v1/files/index?path_prefix=.git/")
        assert r.status_code == 403

    def test_max_files_respected(self, client):
        r = client.get("/v1/files/index?max_files=10")
        data = r.json()
        assert data["total"] <= 10

    def test_with_git_status(self, client):
        r = client.get("/v1/files/index?include_git_status=true&path_prefix=src/openjarvis/plan9/&max_files=5")
        assert r.status_code == 200
        data = r.json()
        for f in data["files"]:
            assert "git_status" in f

    def test_no_secrets_in_response(self, client):
        r = client.get("/v1/files/index?path_prefix=src/openjarvis/plan9/&max_files=20")
        _assert_no_secrets(r.text)


# ============================================================================
# /v1/plan9/runtime-proof-checklist
# ============================================================================

class TestRuntimeProofChecklist:

    def test_returns_200(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist")
        assert r.status_code == 200

    def test_has_8_items(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist")
        data = r.json()
        assert data["total_items"] == 8

    def test_all_categories_present(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist")
        data = r.json()
        cats = set(data["categories"])
        assert "mobile_api" in cats
        assert "memory_parity" in cats
        assert "connector_parity" in cats
        assert "mac_worker_parity" in cats

    def test_filter_by_category(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist?category=mobile_api")
        data = r.json()
        for item in data["items"]:
            assert item["category"] == "mobile_api"

    def test_mobile_api_items_have_how(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist?category=mobile_api")
        data = r.json()
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert "how" in item
            assert item["how"]

    def test_verdict_field_present(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist")
        data = r.json()
        assert "verdict_when_all_verified" in data
        assert data["verdict_when_all_verified"] == "PLAN_9_ACCEPT_PENDING_REVIEW"

    def test_voice_and_signing_not_in_checklist(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist")
        data = r.json()
        ids = [item["id"] for item in data["items"]]
        assert "voice_wake_tts" not in ids
        assert "apple_signing_updater" not in ids

    def test_no_secrets_in_checklist(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist")
        _assert_no_secrets(r.text)

    def test_items_have_no_actual_token_values(self, client):
        r = client.get("/v1/plan9/runtime-proof-checklist")
        text = r.text
        assert "Bearer eyJ" not in text
        assert "ghp_" not in text


# ============================================================================
# /v1/coding/workspace (verify updated operations list)
# ============================================================================

class TestCodingWorkspaceUpdated:

    def test_search_now_wired(self, client):
        r = client.get("/v1/coding/workspace")
        data = r.json()
        ops = {o["op"]: o for o in data["operations"]}
        assert ops["search_code"]["status"] == "WIRED"

    def test_create_branch_now_wired(self, client):
        r = client.get("/v1/coding/workspace")
        data = r.json()
        ops = {o["op"]: o for o in data["operations"]}
        assert ops["create_branch"]["status"] == "WIRED"

    def test_push_now_wired(self, client):
        r = client.get("/v1/coding/workspace")
        data = r.json()
        ops = {o["op"]: o for o in data["operations"]}
        assert ops["push"]["status"] == "WIRED"

    def test_file_index_now_wired(self, client):
        r = client.get("/v1/coding/workspace")
        data = r.json()
        ops = {o["op"]: o for o in data["operations"]}
        assert ops["file_index"]["status"] == "WIRED"


# ============================================================================
# Cross-cutting: no secrets in any new Phase 3 route response
# ============================================================================

class TestPhase3NoSecrets:

    def test_all_new_routes_no_secrets(self, client):
        responses = [
            client.post("/v1/coding/search", json={"query": "CapabilityStatus"}),
            client.post("/v1/coding/create-branch", json={"branch_name": "plan9/check"}),
            client.post("/v1/git/push", json={}),
            client.get("/v1/files/index?path_prefix=src/openjarvis/plan9/&max_files=10"),
            client.get("/v1/plan9/runtime-proof-checklist"),
        ]
        for r in responses:
            _assert_no_secrets(r.text)
