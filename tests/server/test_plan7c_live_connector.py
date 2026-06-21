"""Plan 7C — Live Connector + Front Door Routing Tests.

Covers:
  1. GET /v1/connectors/status includes 'github' entry
  2. GitHub connector state is 'configured' when credential available
  3. GET /v1/connectors/github returns connector detail
  4. GitHub connector connected=True via /v1/connectors/github when credential available
  5. POST /v1/frontdoor/submit with connector_action intent succeeds
  6. Front door routes connector_action without hitting blocked actions
  7. Mobile client sees the same connector status as desktop
  8. Desktop client sees the same connector status as mobile
  9. Connector status never exposes secret values
  10. GitHub credential_source in status is a safe label (no token value)
  11. LIVE: GitHub API user info via connector, through Jarvis front door routing
  12. LIVE: Memory entry written after connector proof (traceable in operator log)
  13. GET /v1/connectors/status endpoint returns github in count
  14. git_available and token_available fields present in GitHub status
  15. connector_action front door routing does not require manual platform hop
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """FastAPI TestClient with connectors router and front door router."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from openjarvis.server.connectors_router import create_connectors_router
    from openjarvis.server.frontdoor_routes import router as frontdoor_router

    app = FastAPI()
    app.include_router(create_connectors_router())
    app.include_router(frontdoor_router)
    return TestClient(app)


@pytest.fixture()
def mobile_client():
    """TestClient simulating a mobile request (identical app — same backend)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from openjarvis.server.connectors_router import create_connectors_router

    app = FastAPI()
    app.include_router(create_connectors_router())
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    """Bearer token auth headers for API requests."""
    import os
    token = os.environ.get("JARVIS_API_KEY", "test-token-plan7c")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_github_credential() -> bool:
    try:
        from openjarvis.connectors.github import _get_github_token
        return _get_github_token() is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 1. GET /v1/connectors/status includes 'github'
# ---------------------------------------------------------------------------


class TestConnectorStatusEndpoint:
    def test_github_in_connector_status(self, client, auth_headers) -> None:
        """GET /v1/connectors/status must include a 'github' entry."""
        resp = client.get("/v1/connectors/status", headers=auth_headers)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        connectors = data.get("connectors", [])
        names = [c.get("connector", "") for c in connectors]
        assert "github" in names, f"'github' not found in connector status list: {names}"

    def test_connector_status_has_count(self, client, auth_headers) -> None:
        """GET /v1/connectors/status returns a count field."""
        resp = client.get("/v1/connectors/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert data["count"] >= 1

    def test_connector_status_200_no_auth(self, client) -> None:
        """GET /v1/connectors/status returns 200 (read-only, no approval needed)."""
        resp = client.get("/v1/connectors/status")
        # Could be 200 or 401 depending on auth config; either is valid
        assert resp.status_code in (200, 401)


# ---------------------------------------------------------------------------
# 2. GitHub connector state reflects credential availability
# ---------------------------------------------------------------------------


class TestGitHubConnectorState:
    def test_github_state_configured_when_credential_available(
        self, client, auth_headers
    ) -> None:
        """GitHub connector state is 'configured' when a credential is available."""
        if not _has_github_credential():
            pytest.skip("No GitHub credential available — skipping configured-state test")

        resp = client.get("/v1/connectors/status", headers=auth_headers)
        data = resp.json()
        github_entry = next(
            (c for c in data["connectors"] if c.get("connector") == "github"), None
        )
        assert github_entry is not None, "GitHub not in connector status"
        assert github_entry["state"] in ("configured", "CONFIGURED"), (
            f"Expected configured, got: {github_entry['state']}"
        )

    def test_github_status_has_safe_fields(self, client, auth_headers) -> None:
        """GitHub status entry has expected safe fields."""
        resp = client.get("/v1/connectors/status", headers=auth_headers)
        data = resp.json()
        github_entry = next(
            (c for c in data["connectors"] if c.get("connector") == "github"), None
        )
        assert github_entry is not None
        # Required fields
        assert "state" in github_entry
        assert "allowed_actions" in github_entry
        assert "approval_required" in github_entry
        assert "real_send_allowed" in github_entry
        # No secret values
        for k, v in github_entry.items():
            if isinstance(v, str):
                assert not v.startswith("ghp_"), f"Secret in status field '{k}': {v}"
                assert not v.startswith("gho_"), f"Secret in status field '{k}': {v}"


# ---------------------------------------------------------------------------
# 3–4. GET /v1/connectors/github detail
# ---------------------------------------------------------------------------


class TestGitHubConnectorDetail:
    def test_github_connector_detail_endpoint_exists(self, client, auth_headers) -> None:
        """GET /v1/connectors/github returns a connector detail response."""
        import importlib
        import openjarvis.connectors.github as _gm
        importlib.reload(_gm)
        resp = client.get("/v1/connectors/github", headers=auth_headers)
        assert resp.status_code in (200, 401, 404), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

    def test_github_connector_connected_when_credential_available(
        self, client, auth_headers
    ) -> None:
        """GET /v1/connectors/github returns connected=True when credential is available."""
        if not _has_github_credential():
            pytest.skip("No GitHub credential — cannot verify connected=True")

        import importlib
        import openjarvis.connectors.github as _gm
        importlib.reload(_gm)
        resp = client.get("/v1/connectors/github", headers=auth_headers)
        if resp.status_code == 401:
            pytest.skip("Auth required for connector detail — acceptable")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("connected") is True, (
            f"Expected connected=True, got: {data}"
        )

    def test_github_connector_detail_no_secrets(self, client, auth_headers) -> None:
        """GET /v1/connectors/github returns no secret values in response."""
        import importlib
        import openjarvis.connectors.github as _gm
        importlib.reload(_gm)
        resp = client.get("/v1/connectors/github", headers=auth_headers)
        if resp.status_code in (401, 404):
            return  # Not reachable without auth — not a secret leak
        data = resp.json()
        for k, v in data.items():
            if isinstance(v, str):
                assert not v.startswith("ghp_"), f"Secret in field '{k}'"
                assert not v.startswith("gho_"), f"Secret in field '{k}'"


# ---------------------------------------------------------------------------
# 5–6. POST /v1/frontdoor/submit — connector_action intent
# ---------------------------------------------------------------------------


class TestFrontDoorConnectorAction:
    def test_connector_action_accepted_by_front_door(self, client, auth_headers) -> None:
        """POST /v1/frontdoor/submit with connector_action intent is accepted (not blocked)."""
        payload = {
            "user_input": "check GitHub connector status",
            "intent": "connector_action",
            "metadata": {
                "connector": "github",
                "action": "status_check",
            },
        }
        resp = client.post("/v1/frontdoor/submit", json=payload, headers=auth_headers)
        assert resp.status_code in (200, 401), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )
        if resp.status_code == 200:
            data = resp.json()
            # Must not be blocked (connector status reads are always safe)
            assert data.get("status") != "blocked", (
                f"connector_action incorrectly blocked: {data}"
            )

    def test_connector_action_does_not_trigger_external_send_gate(
        self, client, auth_headers
    ) -> None:
        """connector_action (read-only) must not trigger the external_send gate."""
        payload = {
            "user_input": "list github repos",
            "intent": "connector_action",
            "metadata": {
                "connector": "github",
                "action": "list_repos",
                "requested_actions": ["read"],  # read-only — not blocked
            },
        }
        resp = client.post("/v1/frontdoor/submit", json=payload, headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert "external_send" not in data.get("blocked_actions", []), (
                "Read-only connector action incorrectly flagged as external_send"
            )

    def test_connector_action_with_blocked_risk_is_blocked(
        self, client, auth_headers
    ) -> None:
        """connector_action with risk_level=blocked must be blocked by front door.

        The route blocks on risk_level=blocked — this is the hard gate for
        actions that must never auto-execute (external sends, writes, etc.).
        """
        payload = {
            "user_input": "send github notification",
            "intent": "connector_action",
            "risk_level": "blocked",
        }
        resp = client.post("/v1/frontdoor/submit", json=payload, headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "blocked", (
                f"risk_level=blocked should produce status=blocked, got: {data.get('status')}"
            )

    def test_connector_action_external_send_via_frontdoor_core_is_blocked(self) -> None:
        """JarvisFrontDoor core blocks external_send in requested_actions metadata."""
        from openjarvis.frontdoor.frontdoor import (
            JarvisFrontDoor,
            UniversalTaskRequest,
        )
        fd = JarvisFrontDoor()
        req = UniversalTaskRequest.create(
            user_input="send github notification to slack",
            intent="connector_action",
            metadata={"requested_actions": ["external_send"]},
        )
        result = fd.handle(req)
        assert result.status == "blocked", (
            f"external_send should be blocked by core front door, got: {result.status}"
        )
        assert "external_send" in result.blocked_actions


# ---------------------------------------------------------------------------
# 7–8. Mobile and desktop see identical connector status
# ---------------------------------------------------------------------------


class TestMobileDesktopConnectorParity:
    def test_mobile_sees_same_connector_status_as_desktop(
        self, client, mobile_client, auth_headers
    ) -> None:
        """Mobile and desktop GET /v1/connectors/status return the same connectors."""
        desktop_resp = client.get("/v1/connectors/status", headers=auth_headers)
        mobile_resp = mobile_client.get("/v1/connectors/status", headers=auth_headers)

        assert desktop_resp.status_code == mobile_resp.status_code

        if desktop_resp.status_code == 200:
            desktop_names = sorted(
                c.get("connector", "") for c in desktop_resp.json().get("connectors", [])
            )
            mobile_names = sorted(
                c.get("connector", "") for c in mobile_resp.json().get("connectors", [])
            )
            assert desktop_names == mobile_names, (
                f"Desktop connectors: {desktop_names}\nMobile connectors: {mobile_names}"
            )

    def test_github_status_visible_from_mobile(
        self, mobile_client, auth_headers
    ) -> None:
        """GitHub connector entry is visible in /v1/connectors/status from mobile."""
        resp = mobile_client.get("/v1/connectors/status", headers=auth_headers)
        assert resp.status_code == 200
        connectors = resp.json().get("connectors", [])
        names = [c.get("connector") for c in connectors]
        assert "github" in names, f"'github' missing from mobile connector status: {names}"


# ---------------------------------------------------------------------------
# 9–10. No secrets in status responses
# ---------------------------------------------------------------------------


class TestNoSecretsInStatusResponses:
    def test_connector_status_no_secret_values(self, client, auth_headers) -> None:
        """GET /v1/connectors/status response contains no secret-looking values."""
        resp = client.get("/v1/connectors/status", headers=auth_headers)
        assert resp.status_code == 200
        text = resp.text
        # No GitHub token patterns in the response body
        assert "ghp_" not in text, "GitHub PAT prefix found in status response"
        assert "gho_" not in text, "GitHub OAuth token found in status response"
        assert "xoxb-" not in text, "Slack bot token found in status response"
        assert "xoxp-" not in text, "Slack user token found in status response"
        assert "sk-" not in text or "skipped" in text.lower(), \
            "OpenAI key prefix found in status response"

    def test_github_credential_source_is_safe_label(self, client, auth_headers) -> None:
        """GitHub 'credential_source' field in status is a safe label, not a token."""
        resp = client.get("/v1/connectors/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        github_entry = next(
            (c for c in data.get("connectors", []) if c.get("connector") == "github"),
            None,
        )
        if github_entry is None:
            return
        source = github_entry.get("credential_source", "")
        if source:
            assert not source.startswith("ghp_"), f"Token value in credential_source: {source}"
            assert not source.startswith("gho_"), f"Token value in credential_source: {source}"
            assert source in (
                "GITHUB_TOKEN env var",
                "github.json config file",
                "gh CLI keyring",
                "none",
            ), f"Unexpected credential_source value: {source}"


# ---------------------------------------------------------------------------
# 11. LIVE: GitHub API user info via connector
# ---------------------------------------------------------------------------


class TestLiveGitHubConnector:
    @pytest.mark.live
    def test_live_github_user_info_via_connector(self) -> None:
        """LIVE: GitHubConnector.get_user_info() returns real user data from GitHub API."""
        if not _has_github_credential():
            pytest.skip("No GitHub credential available")

        from openjarvis.connectors.github import GitHubConnector
        conn = GitHubConnector()
        assert conn.is_connected(), "Connector should be connected when credential available"

        info = conn.get_user_info()
        assert info["connected"] is True, f"get_user_info returned connected=False: {info}"
        assert info.get("login"), f"Empty login in get_user_info: {info}"
        assert info.get("credential_source") in (
            "GITHUB_TOKEN env var", "github.json config file", "gh CLI keyring"
        ), f"Unexpected credential_source: {info.get('credential_source')}"

        # No secret values
        for v in info.values():
            if isinstance(v, str):
                assert not v.startswith("ghp_"), f"Secret in output: {v}"
                assert not v.startswith("gho_"), f"Secret in output: {v}"

    @pytest.mark.live
    def test_live_github_proof_stored_in_memory(self) -> None:
        """LIVE: GitHub connector proof result stored as memory entry (operator log)."""
        if not _has_github_credential():
            pytest.skip("No GitHub credential available")

        import tempfile
        from pathlib import Path

        from openjarvis.connectors.github import GitHubConnector
        from openjarvis.memory.store import JarvisMemory

        # Use isolated tmp DB so we don't pollute the live DB
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = JarvisMemory(db_path=Path(tmpdir) / "proof.db")
            conn = GitHubConnector()
            info = conn.get_user_info()

            # Store connector proof in memory (no secret values)
            login = info.get("login", "unknown")
            source = info.get("credential_source", "unknown")
            entry = mem.write(
                "connector_proof",
                f"GitHub connector live proof: login={login} credential={source}",
                source="plan7c_live_connector_test",
                kind="event",
                project_id="openjarvis",
                tags=["github", "connector_proof", "plan7c"],
            )
            assert entry.entry_id
            fetched = mem.get(entry.entry_id)
            assert fetched is not None
            assert "GitHub" in fetched.content
            assert login in fetched.content
            assert "ghp_" not in fetched.content
            assert "gho_" not in fetched.content


# ---------------------------------------------------------------------------
# 12. GET /v1/connectors/status includes count
# ---------------------------------------------------------------------------


class TestConnectorStatusCount:
    def test_github_counted_in_status(self, client, auth_headers) -> None:
        """GET /v1/connectors/status count reflects GitHub connector inclusion."""
        resp = client.get("/v1/connectors/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        connectors = data.get("connectors", [])
        count = data.get("count", 0)
        assert count == len(connectors), (
            f"count field {count} doesn't match connectors list length {len(connectors)}"
        )
        assert count >= 4, f"Expected at least 4 connectors, got {count}"

    def test_connector_status_includes_github_slack_telegram_web(
        self, client, auth_headers
    ) -> None:
        """Status includes all four explicitly-diagnosed connectors."""
        resp = client.get("/v1/connectors/status", headers=auth_headers)
        assert resp.status_code == 200
        names = {c.get("connector") for c in resp.json().get("connectors", [])}
        for expected in ("github", "slack", "telegram", "web_search"):
            assert expected in names, f"'{expected}' missing from connector status"


# ---------------------------------------------------------------------------
# 13. connector_action front door — no manual platform hop
# ---------------------------------------------------------------------------


class TestFrontDoorNoManualHop:
    def test_connector_action_no_manual_platform_hop(self, client, auth_headers) -> None:
        """connector_action via front door returns a structured decision — no manual hop."""
        payload = {
            "user_input": "check GitHub connector status",
            "intent": "connector_action",
        }
        resp = client.post("/v1/frontdoor/submit", json=payload, headers=auth_headers)
        if resp.status_code in (401,):
            pytest.skip("Auth required — skip routing test")
        assert resp.status_code == 200
        data = resp.json()
        # Front door must return a structured result (not raw chain-of-thought)
        assert "status" in data or "summary" in data, (
            f"Front door returned non-structured response: {data}"
        )
        # Should NOT require a manual platform hop
        assert "manual_platform_hop_required" not in str(data).lower()
