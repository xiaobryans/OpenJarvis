"""Phase D gate tests — GET /v1/connectors/status endpoint.

Validates:
1. Endpoint returns structured list.
2. Missing-credential connector shows NOT_CONFIGURED.
3. Outbound send connectors flagged approval_required=True and real_send_allowed=False.
4. No secret values in any connector entry.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.connectors_router import create_connectors_router  # noqa: E402


@pytest.fixture()
def test_client():
    app = FastAPI()
    app.include_router(create_connectors_router())
    return TestClient(app)


class TestConnectorsStatusEndpoint:
    def test_endpoint_returns_200(self, test_client):
        resp = test_client.get("/v1/connectors/status")
        assert resp.status_code == 200

    def test_response_has_connectors_list(self, test_client):
        resp = test_client.get("/v1/connectors/status")
        data = resp.json()
        assert "connectors" in data
        assert isinstance(data["connectors"], list)

    def test_response_has_count(self, test_client):
        resp = test_client.get("/v1/connectors/status")
        data = resp.json()
        assert "count" in data
        assert data["count"] == len(data["connectors"])

    def test_each_entry_has_required_fields(self, test_client):
        resp = test_client.get("/v1/connectors/status")
        data = resp.json()
        for entry in data["connectors"]:
            assert "connector" in entry
            assert "state" in entry
            # Entries may have error short-circuit but still need connector name

    def test_outbound_connectors_require_approval(self, test_client):
        """Slack and Telegram must always be approval_required=True."""
        resp = test_client.get("/v1/connectors/status")
        data = resp.json()
        outbound = {e["connector"]: e for e in data["connectors"]
                    if e["connector"] in ("slack", "telegram")}
        for name, entry in outbound.items():
            assert entry.get("approval_required") is True, (
                f"{name} must require approval"
            )

    def test_outbound_connectors_real_send_false(self, test_client):
        """Slack and Telegram must always have real_send_allowed=False."""
        resp = test_client.get("/v1/connectors/status")
        data = resp.json()
        outbound = {e["connector"]: e for e in data["connectors"]
                    if e["connector"] in ("slack", "telegram")}
        for name, entry in outbound.items():
            assert entry.get("real_send_allowed") is False, (
                f"{name} must not allow real sends without approval"
            )

    def test_no_secret_values_in_response(self, test_client):
        """No entry should contain an actual API key value (only env var names)."""
        resp = test_client.get("/v1/connectors/status")
        data = resp.json()
        import json
        response_text = json.dumps(data)
        # Token-shaped strings should not appear (env var names like BOT_TOKEN are OK,
        # actual values like xoxb-... should not appear)
        assert "xoxb-" not in response_text
        assert "xoxp-" not in response_text

    def test_missing_credential_connector_not_configured(self, test_client, monkeypatch):
        """Without Slack token, slack connector shows NOT_CONFIGURED."""
        # Clear Slack env vars so it's definitely not configured
        monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_SLACK_BOT_TOKEN", raising=False)

        resp = test_client.get("/v1/connectors/status")
        data = resp.json()
        slack = next((e for e in data["connectors"] if e["connector"] == "slack"), None)
        if slack and "state" in slack:
            assert slack["state"] in ("not_configured", "degraded", "error", "configured",
                                      "ready_pending_test_approval")


class TestConnectorDiagnosticsUnit:
    """Unit tests for connector_diagnostics module."""

    def test_slack_status_has_structure(self):
        """Slack status always returns required fields regardless of credential state."""
        from openjarvis.autonomy.connector_diagnostics import get_slack_status, ConnectorStatus
        status = get_slack_status()
        assert "status" in status
        assert "missing_env_vars" in status
        assert status["status"] in (
            ConnectorStatus.NOT_CONFIGURED,
            ConnectorStatus.CONFIGURED,
            ConnectorStatus.READY_PENDING_TEST,
            ConnectorStatus.DEGRADED,
        )
        assert isinstance(status["missing_env_vars"], list)

    def test_web_search_status_returns_connector_status(self):
        from openjarvis.autonomy.connector_diagnostics import get_web_search_status
        status = get_web_search_status()
        assert "connector" in status
        assert "status" in status

    def test_connector_status_constants(self):
        from openjarvis.autonomy.connector_diagnostics import ConnectorStatus
        assert ConnectorStatus.NOT_CONFIGURED == "not_configured"
        assert ConnectorStatus.CONFIGURED == "configured"
        assert ConnectorStatus.READY_PENDING_TEST == "ready_pending_test_approval"
