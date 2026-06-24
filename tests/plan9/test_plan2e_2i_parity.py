"""Plan 2E-2I — Parity foundation smoke tests.

Covers Plans 2E (Life-OS), 2F (Voice), 2G (Approvals), 2H (Long-Running), 2I (Deploy).

Verifies for each:
- Subsection ID correct
- No fake READY for macbook_off (where applicable)
- Public endpoints return sanitized data (no token presence booleans)
- Sprint verdicts reflect correct plan ID
- Blockers are honest
- Parked items stay parked
- Auth middleware public list includes all new endpoints
"""

from __future__ import annotations

import asyncio
import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Plan 2E — Life-OS
# ---------------------------------------------------------------------------

class TestStatus2ELifeOs:
    def test_subsection_id(self):
        from openjarvis.server.plan2_routes import _status_2e_life_os
        assert _status_2e_life_os()["subsection"] == "2E"

    def test_no_fake_ready_macbook_off(self):
        from openjarvis.server.plan2_routes import _status_2e_life_os
        assert _status_2e_life_os()["macbook_off_status"] != "READY"

    def test_public_endpoint_has_verdict(self):
        from openjarvis.server.plan2_routes import get_life_os_parity_status
        r = _run(get_life_os_parity_status())
        assert "PLAN_2E" in r["sprint_verdict"]

    def test_public_endpoint_no_internal_booleans(self):
        from openjarvis.server.plan2_routes import get_life_os_parity_status
        r = _run(get_life_os_parity_status())
        payload = str(r)
        assert "api_key" not in payload.lower() or "AUTH_REQUIRED" in payload
        # No raw credential booleans
        for key in r:
            assert not key.endswith("_present"), f"Key {key!r} looks like a token presence boolean"
            assert not key.endswith("_configured") or key in (
                "cloud_file_index_available",
            ), f"Unexpected configured key: {key!r}"

    def test_blockers_summary_is_list(self):
        from openjarvis.server.plan2_routes import get_life_os_parity_status
        r = _run(get_life_os_parity_status())
        assert isinstance(r["blockers_summary"], list)
        assert len(r["blockers_summary"]) > 0


# ---------------------------------------------------------------------------
# Plan 2F — Voice (tap-to-speak only, Plan 3 parked)
# ---------------------------------------------------------------------------

class TestStatus2FVoice:
    def test_subsection_id(self):
        from openjarvis.server.plan2_routes import _status_2f_voice
        assert _status_2f_voice()["subsection"] == "2F"

    def test_wake_word_tts_parked(self):
        from openjarvis.server.plan2_routes import _status_2f_voice
        s = _status_2f_voice()
        assert s["wake_word_tts_status"] == "PARKED"
        assert "Plan 3" in s["wake_word_tts_plan"]

    def test_no_deepgram_key_value_exposed(self, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg_supersecret123")
        from openjarvis.server.plan2_routes import get_voice_parity_status
        r = _run(get_voice_parity_status())
        assert "dg_supersecret123" not in str(r)

    def test_public_endpoint_has_verdict(self):
        from openjarvis.server.plan2_routes import get_voice_parity_status
        r = _run(get_voice_parity_status())
        assert "PLAN_2F" in r["sprint_verdict"]

    def test_no_deepgram_presence_boolean_in_public(self):
        from openjarvis.server.plan2_routes import get_voice_parity_status
        r = _run(get_voice_parity_status())
        assert "deepgram_key_present" not in r
        assert "stt_provider_configured" not in r
        assert "tts_provider_configured" not in r

    def test_plan3_not_reopened(self):
        from openjarvis.server.plan2_routes import _status_2f_voice
        s = _status_2f_voice()
        for b in s["blockers"]:
            assert "Plan 3" in b or "PARKED" in b or "MediaRecorder" in b or "HTTPS" in b


# ---------------------------------------------------------------------------
# Plan 2G — Approvals/Notifications
# ---------------------------------------------------------------------------

class TestStatus2GApprovals:
    def test_subsection_id(self):
        from openjarvis.server.plan2_routes import _status_2g_approvals
        assert _status_2g_approvals()["subsection"] == "2G"

    def test_blockers_not_empty(self):
        from openjarvis.server.plan2_routes import _status_2g_approvals
        assert len(_status_2g_approvals()["blockers"]) > 0

    def test_public_endpoint_no_telegram_token_boolean(self):
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        assert "telegram_token_present" not in r
        assert "slack_token_present" not in r

    def test_no_telegram_token_value_exposed(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "12345:ABCDEFsecret")
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        assert "12345:ABCDEFsecret" not in str(r)

    def test_public_endpoint_has_verdict(self):
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        assert "PLAN_2G" in r["sprint_verdict"]


# ---------------------------------------------------------------------------
# Plan 2H — Long-Running
# ---------------------------------------------------------------------------

class TestStatus2HLongRunning:
    def test_subsection_id(self):
        from openjarvis.server.plan2_routes import _status_2h_long_running
        assert _status_2h_long_running()["subsection"] == "2H"

    def test_fargate_worker_not_deployed(self):
        from openjarvis.server.plan2_routes import _status_2h_long_running
        assert _status_2h_long_running()["fargate_worker_deployed"] is False

    def test_public_endpoint_no_aws_booleans(self):
        from openjarvis.server.plan2_routes import get_long_running_parity_status
        r = _run(get_long_running_parity_status())
        assert "aws_configured" not in r

    def test_fargate_status_honest_in_public(self):
        from openjarvis.server.plan2_routes import get_long_running_parity_status
        r = _run(get_long_running_parity_status())
        assert r["fargate_worker_deployed"] is False

    def test_public_endpoint_has_verdict(self):
        from openjarvis.server.plan2_routes import get_long_running_parity_status
        r = _run(get_long_running_parity_status())
        assert "PLAN_2H" in r["sprint_verdict"]


# ---------------------------------------------------------------------------
# Plan 2I — Deploy/Signing
# ---------------------------------------------------------------------------

class TestStatus2IDeploy:
    def test_subsection_id(self):
        from openjarvis.server.plan2_routes import _status_2i_deploy
        assert _status_2i_deploy()["subsection"] == "2I"

    def test_tauri_signing_queued_mac_only(self):
        from openjarvis.server.plan2_routes import _status_2i_deploy
        assert "QUEUED_MAC_ONLY" in _status_2i_deploy()["tauri_signing_status"]

    def test_public_endpoint_no_token_booleans(self):
        from openjarvis.server.plan2_routes import get_deploy_parity_status
        r = _run(get_deploy_parity_status())
        assert "github_token_present" not in r
        assert "apple_signing_keys_present" not in r
        assert "aws_configured" not in r

    def test_no_apple_signing_id_exposed(self, monkeypatch):
        monkeypatch.setenv("APPLE_TEAM_ID", "ABC123TEAM")
        from openjarvis.server.plan2_routes import get_deploy_parity_status
        r = _run(get_deploy_parity_status())
        assert "ABC123TEAM" not in str(r)

    def test_public_endpoint_has_verdict(self):
        from openjarvis.server.plan2_routes import get_deploy_parity_status
        r = _run(get_deploy_parity_status())
        assert "PLAN_2I" in r["sprint_verdict"]

    def test_tauri_signing_status_in_public_response(self):
        from openjarvis.server.plan2_routes import get_deploy_parity_status
        r = _run(get_deploy_parity_status())
        assert "QUEUED_MAC_ONLY" in r.get("tauri_signing_status", "")


# ---------------------------------------------------------------------------
# Auth middleware — all new public paths registered
# ---------------------------------------------------------------------------

class TestAuthMiddlewarePublicPaths:
    def test_all_plan2_public_paths_registered(self):
        from openjarvis.server.auth_middleware import AuthMiddleware
        pub = AuthMiddleware._PUBLIC_PATHS
        required = {
            "/v1/continuity/macbook-off-status",
            "/v1/mobile-parity/status",
            "/v1/mobile-parity/connectors",
            "/v1/mobile-parity/files",
            "/v1/mobile-parity/memory",
            "/v1/mobile-parity/life-os",
            "/v1/mobile-parity/voice",
            "/v1/mobile-parity/approvals",
            "/v1/mobile-parity/long-running",
            "/v1/mobile-parity/deploy",
            "/v1/files/cloud-index",
        }
        missing = required - pub
        assert not missing, f"Missing from public paths: {missing}"

    def test_detail_connectors_not_public(self):
        from openjarvis.server.auth_middleware import AuthMiddleware
        # Connectors/detail is auth-gated — must NOT be in public paths
        assert "/v1/mobile-parity/connectors/detail" not in AuthMiddleware._PUBLIC_PATHS

    def test_workspace_status_not_public(self):
        from openjarvis.server.auth_middleware import AuthMiddleware
        # Auth-gated workspace detail must NOT be in public paths
        assert "/v1/files/workspace/status" not in AuthMiddleware._PUBLIC_PATHS
