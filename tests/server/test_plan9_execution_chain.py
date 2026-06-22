"""Plan 9 execution chain — approval, commit, push, workflow tests."""

from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.authority.approval_engine import ApprovalEngine
from openjarvis.authority.audit_store import AuditStore
from openjarvis.server.authority_routes import router as authority_router
from openjarvis.server.plan9_routes import router as plan9_router
import openjarvis.server.authority_routes as ar
import openjarvis.plan9.execution_chain as ec
import openjarvis.plan9.mac_worker_queue as mwq


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(plan9_router)
    app.include_router(authority_router)
    return app


@pytest.fixture()
def authority_client(monkeypatch, tmp_path):
    """TestClient with isolated Plan 8 DBs for approval + audit."""
    approval_db = tmp_path / "approvals.db"
    audit_db = tmp_path / "audit.db"
    monkeypatch.setattr(mwq, "_MAC_QUEUE", None)
    monkeypatch.setattr(ar, "_approval_engine", ApprovalEngine(approval_db))
    monkeypatch.setattr(ar, "_audit_store", AuditStore(audit_db))
    monkeypatch.setattr(ec, "get_approval_engine", lambda: ApprovalEngine(approval_db))
    monkeypatch.setattr(ec, "get_audit_store", lambda: AuditStore(audit_db))
    app = _make_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestAuthorityApprovalFlow:
    def test_git_commit_request_is_pending_until_grant(self, authority_client):
        r = authority_client.post("/v1/authority/approvals/request", json={
            "action_type": "git_commit",
            "requester": "jarvis",
            "action_preview": "plan9 test commit",
            "affected_files": ["tests/fixtures/plan9_workflow_status.txt"],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending"
        approval_id = data["approval_id"]

        pending = authority_client.get("/v1/authority/approvals/pending").json()
        assert pending["count"] >= 1
        assert any(a["approval_id"] == approval_id for a in pending["approvals"])

        grant = authority_client.post(
            f"/v1/authority/approvals/{approval_id}/grant",
            json={"expires_in_seconds": 3600},
        )
        assert grant.status_code == 200
        assert grant.json()["status"] == "granted"

        audit = authority_client.get("/v1/authority/audit?limit=20").json()
        actions = [e["action_type"] for e in audit["entries"]]
        assert "approval_requested" in actions
        assert "approval_granted" in actions

    def test_deny_and_bad_id(self, authority_client):
        r = authority_client.post("/v1/authority/approvals/request", json={
            "action_type": "git_push",
            "requester": "jarvis",
            "action_preview": "plan9 test push",
        })
        approval_id = r.json()["approval_id"]

        deny = authority_client.post(
            f"/v1/authority/approvals/{approval_id}/deny",
            json={"reason": "test deny"},
        )
        assert deny.status_code == 200

        bad = authority_client.post("/v1/authority/approvals/doesnotexist/grant", json={})
        assert bad.status_code == 404


class TestGitCommitExecution:
    def test_commit_requires_valid_approval(self, authority_client, monkeypatch):
        import subprocess

        def fake_run(cmd, **kwargs):
            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            if cmd[:3] == ["git", "diff"]:
                R.stdout = "+status=probe\n"
            if cmd[:2] == ["git", "rev-parse"] and "HEAD" in cmd:
                R.stdout = "abc123def456\n"
            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)

        r = authority_client.post("/v1/git/commit", json={
            "commit_message": "plan9: execution chain test",
            "files": ["tests/fixtures/plan9_workflow_status.txt"],
            "dry_run": False,
            "approval_token": "invalid-token",
        })
        assert r.status_code == 403

    def test_dry_run_still_works(self, authority_client):
        r = authority_client.post("/v1/git/commit", json={
            "commit_message": "plan9: dry run only",
        })
        assert r.status_code == 200
        assert r.json()["mode"] == "DRY_RUN"
        assert r.json()["committed"] is False


class TestCodingWorkflow:
    def test_workflow_dry_run_edits_and_tests(self, authority_client, monkeypatch, tmp_path):
        import subprocess

        target = Path("tests/fixtures/plan9_workflow_status.txt")
        original = target.read_text(encoding="utf-8") if target.exists() else ""

        def fake_run(cmd, **kwargs):
            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            if cmd[0:2] == ["git", "diff"]:
                R.stdout = "+# loop test\n"
            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)

        try:
            r = authority_client.post("/v1/coding/workflow/run", json={
                "task": "Append harmless workflow probe line",
                "edit_line": "# plan9-test-probe",
                "workflow_id": "test-dry-run",
                "commit_message": "plan9: workflow dry run",
                "dry_run": True,
            })
            assert r.status_code == 200
            data = r.json()
            assert data["tests_passed"] is True
            assert "diff" in data
            assert data["status"] in ("DRY_RUN_COMPLETE", "READY_FOR_APPROVAL")

            status = authority_client.get("/v1/coding/workflow/status").json()
            assert status["last_workflow"] is not None
        finally:
            if target.exists():
                target.write_text(original, encoding="utf-8")

    def test_workflow_blocks_non_allowlisted_file(self, authority_client):
        r = authority_client.post("/v1/coding/workflow/run", json={
            "task": "Try blocked file",
            "target_file": "JARVIS_OMNIX_HANDOFF.md",
            "edit_line": "# bad",
            "commit_message": "plan9: should fail",
        })
        assert r.status_code == 400
