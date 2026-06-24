"""Plan 2 reviewer-correction sprint tests.

Verifies:
1. Overall Plan 2 status endpoint returns HOLD verdict (no fake PATCHED_PENDING_REVIEW)
2. Sprint field updated from Plan 2A to Plan 2A-2I
3. Public files endpoint (/v1/mobile-parity/files) does not expose env var names in blockers
4. Public memory endpoint (/v1/mobile-parity/memory) does not expose env var names in blockers
5. B3 fix: _telegram_present() detects both TELEGRAM_BOT_TOKEN and JARVIS_TELEGRAM_BOT_TOKEN
6. No macbook_off_ready count in summary claims READY when Fargate not deployed
7. Life-OS macbook_off_status is not READY (SQLite local-only)
8. Long-running fargate_worker_deployed is False in public response
9. Auth-gated workspace/status is NOT in public paths
10. Approvals endpoint does not expose token env var names
"""

from __future__ import annotations

import asyncio
import pytest


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Plan 2 overall status: HOLD verdict
# ---------------------------------------------------------------------------

class TestPlan2OverallStatusHold:
    def test_sprint_verdict_is_hold(self):
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        assert r["sprint_verdict"] == "PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_HOLD", (
            f"Expected HOLD verdict, got: {r['sprint_verdict']!r}"
        )

    def test_sprint_field_covers_all_subsections(self):
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        sprint = r["sprint"]
        assert "2A" in sprint and "2I" in sprint, (
            f"Sprint field {sprint!r} should reference 2A through 2I"
        )

    def test_no_macbook_off_ready_subsections(self):
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        summary = r["summary"]
        assert summary["macbook_off_ready"] == 0, (
            f"No subsections should be macbook_off_ready while Fargate not deployed; "
            f"got: {summary['macbook_off_ready']}"
        )

    def test_global_blocker_present(self):
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        assert "global" in r
        assert "macbook_off_global_blocker" in r["global"]
        assert len(r["global"]["macbook_off_global_blocker"]) > 20


# ---------------------------------------------------------------------------
# Public files endpoint: no env var names in blockers
# ---------------------------------------------------------------------------

class TestPublicFilesNoEnvVarNames:
    _ENV_VAR_NAMES = [
        "OMNIX_WORKBENCH_ARTIFACT_BUCKET",
        "OMNIX_WORKBENCH_MEMORY_BUCKET",
        "OMNIX_WORKBENCH_STATE_TABLE",
        "OMNIX_WORKBENCH_AWS_REGION",
        "OMNIX_WORKBENCH_STORAGE_PROVIDER",
        "OMNIX_WORKBENCH_AWS_PROFILE",
        "OPENJARVIS_API_KEY",
        "GITHUB_TOKEN",
    ]

    def test_no_env_var_names_in_blockers(self):
        from openjarvis.server.plan2_routes import get_file_parity_status
        r = _run(get_file_parity_status())
        blockers_str = str(r.get("blockers", []))
        for name in self._ENV_VAR_NAMES:
            assert name not in blockers_str, (
                f"Env var name {name!r} must not appear in public files endpoint blockers"
            )

    def test_no_env_var_names_in_notes(self):
        from openjarvis.server.plan2_routes import get_file_parity_status
        r = _run(get_file_parity_status())
        notes_str = str(r.get("notes", []))
        for name in self._ENV_VAR_NAMES:
            assert name not in notes_str, (
                f"Env var name {name!r} must not appear in public files endpoint notes"
            )

    def test_blockers_still_present_and_honest(self):
        from openjarvis.server.plan2_routes import get_file_parity_status
        r = _run(get_file_parity_status())
        assert isinstance(r["blockers"], list)
        assert len(r["blockers"]) > 0, "Blockers must be non-empty (full workspace sync not complete)"

    def test_s3_status_is_valid_enum(self):
        from openjarvis.server.plan2_routes import get_file_parity_status
        r = _run(get_file_parity_status())
        assert r["s3_artifact_store_status"] in ("READY", "PARTIAL", "BLOCKED", "NOT_CONFIGURED")

    def test_no_env_var_values_exposed(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_ARTIFACT_BUCKET", "my-top-secret-bucket")
        from openjarvis.server.plan2_routes import get_file_parity_status
        r = _run(get_file_parity_status())
        payload = str(r)
        assert "my-top-secret-bucket" not in payload


# ---------------------------------------------------------------------------
# Public memory endpoint: no env var names in blockers
# ---------------------------------------------------------------------------

class TestPublicMemoryNoEnvVarNames:
    _ENV_VAR_NAMES = [
        "OMNIX_WORKBENCH_MEMORY_BUCKET",
        "OMNIX_WORKBENCH_AWS_REGION",
        "OMNIX_WORKBENCH_AWS_PROFILE",
        "PINECONE_API_KEY",
        "OPENJARVIS_API_KEY",
    ]

    def test_no_env_var_names_in_blockers(self):
        from openjarvis.server.plan2_routes import get_memory_parity_status
        r = _run(get_memory_parity_status())
        blockers_str = str(r.get("blockers", []))
        for name in self._ENV_VAR_NAMES:
            assert name not in blockers_str, (
                f"Env var name {name!r} must not appear in public memory endpoint blockers"
            )

    def test_blockers_still_honest_and_non_empty(self):
        from openjarvis.server.plan2_routes import get_memory_parity_status
        r = _run(get_memory_parity_status())
        assert isinstance(r["blockers"], list)
        assert len(r["blockers"]) > 0, "Memory blockers must be non-empty (Fargate sync not complete)"

    def test_no_bucket_values_exposed(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "classified-memory-bucket")
        from openjarvis.server.plan2_routes import get_memory_parity_status
        r = _run(get_memory_parity_status())
        payload = str(r)
        assert "classified-memory-bucket" not in payload


# ---------------------------------------------------------------------------
# B3 fix: Telegram dual-env detection
# ---------------------------------------------------------------------------

class TestTelegramDualEnv:
    def test_detects_primary_env_var(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-primary-token")
        monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
        from openjarvis.server.plan2_routes import _telegram_present
        assert _telegram_present() is True

    def test_detects_canonical_env_var(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "test-canonical-token")
        from openjarvis.server.plan2_routes import _telegram_present
        assert _telegram_present() is True

    def test_false_when_neither_present(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
        from openjarvis.server.plan2_routes import _telegram_present
        assert _telegram_present() is False

    def test_token_value_never_returned(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "12345:SuperSecretBotToken")
        monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "67890:AnotherSecretBotToken")
        from openjarvis.server.plan2_routes import _telegram_present
        result = _telegram_present()
        assert isinstance(result, bool), "Must return bool, not the token value"
        assert result is not "12345:SuperSecretBotToken"  # noqa: F632

    def test_connector_registry_also_checks_both(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "canonical-token")
        from openjarvis.server.plan2_routes import _CONNECTOR_REGISTRY, _connector_token_present
        telegram_rec = next(r for r in _CONNECTOR_REGISTRY if r["connector_id"] == "telegram")
        assert _connector_token_present(telegram_rec) is True


# ---------------------------------------------------------------------------
# Fargate / MacBook-off honesty
# ---------------------------------------------------------------------------

class TestFargateMacbookOffHonesty:
    def test_fargate_worker_not_deployed_in_long_running(self):
        from openjarvis.server.plan2_routes import get_long_running_parity_status
        r = _run(get_long_running_parity_status())
        assert r["fargate_worker_deployed"] is False

    def test_life_os_macbook_off_not_ready(self):
        from openjarvis.server.plan2_routes import _status_2e_life_os
        s = _status_2e_life_os()
        assert s["macbook_off_status"] != "READY", (
            "Life-OS macbook_off cannot be READY while SQLite is local-only"
        )

    def test_approvals_macbook_off_not_ready(self):
        from openjarvis.server.plan2_routes import _status_2g_approvals
        s = _status_2g_approvals()
        assert s["macbook_off_status"] != "READY", (
            "Approvals macbook_off cannot be READY while approval store is local SQLite"
        )

    def test_memory_macbook_off_not_ready(self):
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        assert s["macbook_off_status"] != "READY", (
            "Memory macbook_off cannot be READY while SQLite is local-only"
        )


# ---------------------------------------------------------------------------
# Auth-gated endpoints remain gated
# ---------------------------------------------------------------------------

class TestAuthGating:
    def test_workspace_status_not_in_public_paths(self):
        from openjarvis.server.auth_middleware import AuthMiddleware
        assert "/v1/files/workspace/status" not in AuthMiddleware._PUBLIC_PATHS

    def test_connectors_detail_not_in_public_paths(self):
        from openjarvis.server.auth_middleware import AuthMiddleware
        assert "/v1/mobile-parity/connectors/detail" not in AuthMiddleware._PUBLIC_PATHS

    def test_approvals_endpoint_no_token_env_var_names(self):
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        payload = str(r)
        assert "TELEGRAM_BOT_TOKEN" not in payload
        assert "JARVIS_TELEGRAM_BOT_TOKEN" not in payload
        assert "SLACK_BOT_TOKEN" not in payload
        assert "OPENCLAW_SLACK_BOT_TOKEN" not in payload

    def test_approvals_endpoint_no_token_values(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "supersecret:TelegramToken")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-supersecretslack")
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        payload = str(r)
        assert "supersecret:TelegramToken" not in payload
        assert "xoxb-supersecretslack" not in payload
