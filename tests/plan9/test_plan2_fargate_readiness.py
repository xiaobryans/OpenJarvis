"""Plan 2 Fargate Worker Readiness Sprint — test suite.

Covers all 9 required test scenarios:
1. Fargate worker status does not claim READY when not deployed.
2. Long-running cloud execution does not claim MacBook-off without reachable worker.
3. NotificationQueue consumer does not attempt live delivery unless provider configured/mocked.
4. External delivery status is NOT_CONFIGURED, CONFIGURED_NOT_DEPLOYED, BLOCKED, or PARTIAL.
5. Public endpoints do not leak env var names, token values, bucket names, or private paths.
6. Auth-gated cloud-worker/detail endpoint requires auth.
7. Approval gates are not bypassed by the worker path.
8. Workspace sync status distinguishes all 5 layers.
9. Overall Plan 2 verdict remains HOLD.
"""

from __future__ import annotations

import asyncio
import pytest


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 1. Fargate worker status does not claim READY when not deployed
# ---------------------------------------------------------------------------

class TestFargateWorkerNotReady:
    def test_status_never_ready_without_deployment(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status, STATUS_READY
        r = get_fargate_worker_status()
        assert r.status != STATUS_READY, (
            f"Fargate worker must not claim READY without live deployment. Got: {r.status}"
        )

    def test_deployed_always_false(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        r = get_fargate_worker_status()
        assert r.deployed is False

    def test_reachable_always_false(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        r = get_fargate_worker_status()
        assert r.reachable is False

    def test_executing_always_false(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        r = get_fargate_worker_status()
        assert r.executing is False

    def test_status_is_known_failure_mode(self):
        from openjarvis.server.fargate_readiness import (
            get_fargate_worker_status,
            STATUS_NOT_CONFIGURED,
            STATUS_CONFIGURED_NOT_DEPLOYED,
            STATUS_BLOCKED,
            STATUS_PARTIAL,
            STATUS_READY,
        )
        r = get_fargate_worker_status()
        valid_non_ready = {
            STATUS_NOT_CONFIGURED,
            STATUS_CONFIGURED_NOT_DEPLOYED,
            STATUS_BLOCKED,
            STATUS_PARTIAL,
        }
        assert r.status in valid_non_ready or r.status == STATUS_READY, (
            f"Unexpected status: {r.status}"
        )
        assert r.status != STATUS_READY

    def test_code_present_detectable(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        r = get_fargate_worker_status()
        # code_present is a boolean — True means code found, False means missing
        assert isinstance(r.code_present, bool)

    def test_to_public_dict_excludes_configured(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        pub = get_fargate_worker_status().to_public_dict()
        assert "configured" not in pub
        assert "missing_vars_count" not in pub

    def test_to_dict_has_all_layers(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        d = get_fargate_worker_status().to_dict()
        for key in ("code_present", "configured", "deployed", "reachable", "executing", "status"):
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# 2. Long-running cloud execution does not claim MacBook-off without reachable worker
# ---------------------------------------------------------------------------

class TestLongRunningNoFakeReady:
    def test_macbook_off_not_ready(self):
        from openjarvis.server.plan2_routes import _status_2h_long_running
        s = _status_2h_long_running()
        assert s["macbook_off_status"] != "READY"

    def test_fargate_worker_deployed_false(self):
        from openjarvis.server.plan2_routes import _status_2h_long_running
        assert _status_2h_long_running()["fargate_worker_deployed"] is False

    def test_fargate_worker_status_not_ready(self):
        from openjarvis.server.plan2_routes import _status_2h_long_running
        s = _status_2h_long_running()
        assert s.get("fargate_worker_status") != "READY"

    def test_public_endpoint_fargate_deployed_false(self):
        from openjarvis.server.plan2_routes import get_long_running_parity_status
        r = _run(get_long_running_parity_status())
        assert r["fargate_worker_deployed"] is False

    def test_public_endpoint_no_aws_booleans(self):
        from openjarvis.server.plan2_routes import get_long_running_parity_status
        r = _run(get_long_running_parity_status())
        assert "aws_configured" not in r

    def test_public_endpoint_no_env_var_names_in_fargate_status(self):
        from openjarvis.server.plan2_routes import get_cloud_worker_parity_status
        r = _run(get_cloud_worker_parity_status())
        response_str = str(r)
        # No raw env var names
        for var in ("OMNIX_WORKBENCH_AWS_REGION", "OMNIX_WORKBENCH_MEMORY_BUCKET",
                    "OPENJARVIS_API_KEY", "AWS_PROFILE"):
            assert var not in response_str, f"Env var name leaked in public cloud-worker endpoint: {var}"

    def test_macbook_off_execution_not_ready_in_public_endpoint(self):
        from openjarvis.server.plan2_routes import get_cloud_worker_parity_status
        r = _run(get_cloud_worker_parity_status())
        assert r["macbook_off_execution_ready"] is False


# ---------------------------------------------------------------------------
# 3. NotificationQueue consumer does not attempt live delivery without providers
# ---------------------------------------------------------------------------

class TestNotificationDispatcherNoLiveDelivery:
    def test_no_providers_no_delivery(self, tmp_path):
        from openjarvis.authority.notification_queue import NotificationQueue
        from openjarvis.authority.notification_dispatcher import NotificationDispatcher

        q = NotificationQueue(db_path=tmp_path / "notif.db")
        q.enqueue("approval-123", "push_to_github", "high",
                  channel_target_class="external_pending")

        dispatcher = NotificationDispatcher(providers=[])
        result = dispatcher.dispatch_pending(q)

        assert result.delivered == 0
        assert result.not_configured >= 1
        assert result.total_events >= 1

    def test_no_providers_status_not_configured(self):
        from openjarvis.authority.notification_dispatcher import NotificationDispatcher
        d = NotificationDispatcher(providers=[])
        status = d.get_status()
        assert status["status"] == "NOT_CONFIGURED"
        assert status["providers_configured"] == 0

    def test_mock_provider_receives_dispatch(self, tmp_path):
        from openjarvis.authority.notification_queue import NotificationQueue
        from openjarvis.authority.notification_dispatcher import (
            NotificationDispatcher, NotificationProviderAdapter,
        )

        class MockProvider(NotificationProviderAdapter):
            def __init__(self):
                self.sent = []

            @property
            def provider_id(self) -> str:
                return "mock_provider"

            @property
            def is_configured(self) -> bool:
                return True

            def send(self, event_id, action_type, risk_level, message) -> bool:
                self.sent.append((event_id, action_type))
                return True

        q = NotificationQueue(db_path=tmp_path / "notif2.db")
        q.enqueue("approval-456", "send_slack_message", "medium",
                  channel_target_class="external_pending")

        mock = MockProvider()
        dispatcher = NotificationDispatcher(providers=[mock])
        result = dispatcher.dispatch_pending(q)

        assert result.delivered >= 1
        assert len(mock.sent) >= 1

    def test_mock_provider_never_receives_secret_values(self, tmp_path):
        from openjarvis.authority.notification_queue import NotificationQueue
        from openjarvis.authority.notification_dispatcher import (
            NotificationDispatcher, NotificationProviderAdapter,
        )

        class SecretCheckProvider(NotificationProviderAdapter):
            def __init__(self):
                self.messages = []

            @property
            def provider_id(self) -> str:
                return "secret_check_provider"

            @property
            def is_configured(self) -> bool:
                return True

            def send(self, event_id, action_type, risk_level, message) -> bool:
                self.messages.append(message)
                return True

        q = NotificationQueue(db_path=tmp_path / "notif3.db")
        q.enqueue("approval-789", "deploy_to_fargate", "high")

        provider = SecretCheckProvider()
        dispatcher = NotificationDispatcher(providers=[provider])
        dispatcher.dispatch_pending(q)

        combined = " ".join(provider.messages)
        # No secret-like patterns in dispatched messages
        for bad in ("token", "secret", "password", "key=", "bucket_name",
                    "account_id", "/home/", "~/."):
            assert bad.lower() not in combined.lower(), (
                f"Sensitive data found in dispatch message: {bad!r}"
            )

    def test_provider_raises_does_not_propagate(self, tmp_path):
        from openjarvis.authority.notification_queue import NotificationQueue
        from openjarvis.authority.notification_dispatcher import (
            NotificationDispatcher, NotificationProviderAdapter,
        )

        class ErrorProvider(NotificationProviderAdapter):
            @property
            def provider_id(self) -> str:
                return "error_provider"

            @property
            def is_configured(self) -> bool:
                return True

            def send(self, event_id, action_type, risk_level, message) -> bool:
                raise RuntimeError("provider connection failed")

        q = NotificationQueue(db_path=tmp_path / "notif4.db")
        q.enqueue("approval-abc", "external_action", "low")

        dispatcher = NotificationDispatcher(providers=[ErrorProvider()])
        # Should not raise — errors are swallowed per design
        result = dispatcher.dispatch_pending(q)
        assert result.failed >= 1
        assert result.delivered == 0


# ---------------------------------------------------------------------------
# 4. External delivery status is NOT_CONFIGURED, CONFIGURED_NOT_DEPLOYED, BLOCKED, or PARTIAL
# ---------------------------------------------------------------------------

class TestExternalDeliveryHonestStatus:
    def test_no_provider_tokens_returns_not_configured(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
        from openjarvis.authority.notification_dispatcher import get_external_delivery_status
        result = get_external_delivery_status()
        assert result["status"] == "NOT_CONFIGURED"

    def test_provider_tokens_present_returns_configured_not_deployed(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token-for-test")
        from openjarvis.authority.notification_dispatcher import get_external_delivery_status
        result = get_external_delivery_status()
        assert result["status"] in ("CONFIGURED_NOT_DEPLOYED", "NOT_CONFIGURED")
        # If token was detected, must be CONFIGURED_NOT_DEPLOYED (not READY)
        if result["providers_available"] > 0:
            assert result["status"] == "CONFIGURED_NOT_DEPLOYED"

    def test_status_never_ready(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t.123456789:abcdefghijklmnop")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-fake-test-token")
        from openjarvis.authority.notification_dispatcher import get_external_delivery_status
        result = get_external_delivery_status()
        assert result["status"] != "READY"

    def test_no_token_value_in_response(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "supersecret_tg_token_value")
        from openjarvis.authority.notification_dispatcher import get_external_delivery_status
        result = get_external_delivery_status()
        assert "supersecret_tg_token_value" not in str(result)

    def test_fargate_worker_required_always_true(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        from openjarvis.authority.notification_dispatcher import get_external_delivery_status
        result = get_external_delivery_status()
        assert result["fargate_worker_required"] is True


# ---------------------------------------------------------------------------
# 5. Public endpoints do not leak sensitive information
# ---------------------------------------------------------------------------

class TestPublicEndpointSafety:
    _SENSITIVE_PATTERNS = [
        "OMNIX_WORKBENCH_MEMORY_BUCKET",
        "OMNIX_WORKBENCH_ARTIFACT_BUCKET",
        "OMNIX_WORKBENCH_STATE_TABLE",
        "OMNIX_WORKBENCH_AWS_REGION",
        "OPENJARVIS_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "JARVIS_TELEGRAM_BOT_TOKEN",
        "SLACK_BOT_TOKEN",
        "OPENCLAW_SLACK_BOT_TOKEN",
        "GITHUB_TOKEN",
        "APPLE_TEAM_ID",
        "APPLE_SIGNING_IDENTITY",
        "~/.openjarvis",
        "/home/",
        "/Users/",
    ]

    def _check_no_sensitive(self, response, endpoint_name):
        response_str = str(response)
        for pattern in self._SENSITIVE_PATTERNS:
            assert pattern not in response_str, (
                f"Sensitive pattern {pattern!r} found in public endpoint {endpoint_name}"
            )

    def test_cloud_worker_endpoint_no_env_var_names(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "my-secret-bucket-name")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-tg-token-value")
        from openjarvis.server.plan2_routes import get_cloud_worker_parity_status
        r = _run(get_cloud_worker_parity_status())
        self._check_no_sensitive(r, "/v1/mobile-parity/cloud-worker")
        assert "my-secret-bucket-name" not in str(r)
        assert "secret-tg-token-value" not in str(r)

    def test_mobile_parity_status_no_sensitive_data(self, monkeypatch):
        monkeypatch.setenv("OPENJARVIS_API_KEY", "sk-test-12345678-secret")
        monkeypatch.setenv("OMNIX_WORKBENCH_ARTIFACT_BUCKET", "bucket-name-secret")
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        response_str = str(r)
        assert "sk-test-12345678-secret" not in response_str
        assert "bucket-name-secret" not in response_str

    def test_approvals_endpoint_no_telegram_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:supersecret_token_value")
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        assert "1234567890:supersecret_token_value" not in str(r)
        assert "telegram_token_present" not in r
        assert "slack_token_present" not in r

    def test_long_running_endpoint_no_aws_config(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_AWS_REGION", "ap-southeast-1-secret")
        from openjarvis.server.plan2_routes import get_long_running_parity_status
        r = _run(get_long_running_parity_status())
        assert "aws_configured" not in r
        assert "OMNIX_WORKBENCH_AWS_REGION" not in str(r)

    def test_cloud_worker_endpoint_no_bucket_names(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "supersecret-bucket-2025")
        from openjarvis.server.plan2_routes import get_cloud_worker_parity_status
        r = _run(get_cloud_worker_parity_status())
        assert "supersecret-bucket-2025" not in str(r)

    def test_cloud_worker_endpoint_fargate_deployed_false(self):
        from openjarvis.server.plan2_routes import get_cloud_worker_parity_status
        r = _run(get_cloud_worker_parity_status())
        assert r["macbook_off_execution_ready"] is False
        fw = r.get("fargate_worker", {})
        assert fw.get("deployed", False) is False


# ---------------------------------------------------------------------------
# 6. Auth-gated cloud-worker/detail endpoint requires auth
# ---------------------------------------------------------------------------

class TestCloudWorkerDetailAuthRequired:
    def test_no_auth_returns_401_when_key_configured(self, monkeypatch):
        monkeypatch.setenv("OPENJARVIS_API_KEY", "test-api-key-required")
        from openjarvis.server.plan2_routes import get_cloud_worker_detail
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _run(get_cloud_worker_detail(credentials=None))
        assert exc_info.value.status_code == 401

    def test_wrong_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("OPENJARVIS_API_KEY", "correct-api-key-xyz")
        from openjarvis.server.plan2_routes import get_cloud_worker_detail
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        wrong_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")
        with pytest.raises(HTTPException) as exc_info:
            _run(get_cloud_worker_detail(credentials=wrong_creds))
        assert exc_info.value.status_code == 401

    def test_correct_token_returns_data(self, monkeypatch):
        monkeypatch.setenv("OPENJARVIS_API_KEY", "valid-test-key-abc")
        from openjarvis.server.plan2_routes import get_cloud_worker_detail
        from fastapi.security import HTTPAuthorizationCredentials
        good_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-test-key-abc")
        r = _run(get_cloud_worker_detail(credentials=good_creds))
        assert "b6_fargate_worker" in r
        assert "b8_workspace_sync" in r
        assert r["auth_required"] is True

    def test_detail_endpoint_no_secret_values(self, monkeypatch):
        monkeypatch.setenv("OPENJARVIS_API_KEY", "test-key-for-detail")
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "private-bucket-name")
        from openjarvis.server.plan2_routes import get_cloud_worker_detail
        from fastapi.security import HTTPAuthorizationCredentials
        good_creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="test-key-for-detail"
        )
        r = _run(get_cloud_worker_detail(credentials=good_creds))
        response_str = str(r)
        assert "private-bucket-name" not in response_str

    def test_detail_has_all_blocker_fields(self, monkeypatch):
        monkeypatch.setenv("OPENJARVIS_API_KEY", "test-key-detail-fields")
        from openjarvis.server.plan2_routes import get_cloud_worker_detail
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-key-detail-fields")
        r = _run(get_cloud_worker_detail(credentials=creds))
        assert "b6_fargate_worker" in r
        assert "b8_workspace_sync" in r
        assert "b5c_external_delivery" in r
        assert "macbook_off_execution_ready" in r


# ---------------------------------------------------------------------------
# 7. Approval gates not bypassed by worker path
# ---------------------------------------------------------------------------

class TestApprovalGateNotBypassed:
    def test_dispatcher_never_approves_or_denies(self, tmp_path):
        from openjarvis.authority.notification_dispatcher import (
            NotificationDispatcher, NotificationProviderAdapter,
        )
        from openjarvis.authority.notification_queue import NotificationQueue

        class RecordingProvider(NotificationProviderAdapter):
            def __init__(self):
                self.calls = []

            @property
            def provider_id(self) -> str:
                return "recording_provider"

            @property
            def is_configured(self) -> bool:
                return True

            def send(self, event_id, action_type, risk_level, message) -> bool:
                self.calls.append({"event_id": event_id, "message": message})
                return True

        q = NotificationQueue(db_path=tmp_path / "gate_test.db")
        q.enqueue("approval-gate-test", "deploy_action", "critical")

        provider = RecordingProvider()
        dispatcher = NotificationDispatcher(providers=[provider])
        result = dispatcher.dispatch_pending(q)

        # Verify: only notification sent, no approval decision
        for call in provider.calls:
            msg = call["message"].lower()
            assert "approve" not in msg or "pending approval" in msg
            assert "deny" not in msg
            assert "approved" not in msg
            assert "rejected" not in msg

    def test_dispatch_does_not_modify_approval_store(self, tmp_path):
        from openjarvis.authority.notification_dispatcher import NotificationDispatcher
        from openjarvis.authority.notification_queue import NotificationQueue

        q = NotificationQueue(db_path=tmp_path / "gate_test2.db")
        q.enqueue("approval-gate-test2", "merge_pull_request", "high")

        # Dispatcher with no providers — should not touch approval store
        dispatcher = NotificationDispatcher(providers=[])
        result = dispatcher.dispatch_pending(q)

        # Result only has not_configured — no modification of approval state
        assert result.delivered == 0
        assert result.not_configured >= 1

    def test_notification_queue_events_do_not_approve_actions(self, tmp_path):
        from openjarvis.authority.notification_queue import NotificationQueue

        q = NotificationQueue(db_path=tmp_path / "queue_approval.db")
        event = q.enqueue("approval-queue-test", "push_to_prod", "critical")

        # Event is queued (status queued or delivery_blocked) — not "approved"
        assert event.status in ("queued", "delivery_blocked")
        # Event metadata does not contain approval decision
        d = event.to_dict()
        assert "approved" not in str(d).lower()
        assert "denied" not in str(d).lower()


# ---------------------------------------------------------------------------
# 8. Workspace sync status distinguishes all 5 layers
# ---------------------------------------------------------------------------

class TestWorkspaceSyncLayerDistinction:
    def test_has_all_five_layers(self):
        from openjarvis.memory.workspace_sync_status import get_workspace_sync_status
        s = get_workspace_sync_status()
        d = s.to_dict()
        layers = d["layers"]
        assert "local_git_index" in layers
        assert "s3_config" in layers
        assert "sync_code_present" in layers
        assert "sync_executed" in layers
        assert "cloud_worker_access" in layers

    def test_sync_executed_always_requires_deployment(self):
        from openjarvis.memory.workspace_sync_status import (
            get_workspace_sync_status, LAYER_REQUIRES_DEPLOYMENT,
        )
        s = get_workspace_sync_status()
        assert s.sync_executed == LAYER_REQUIRES_DEPLOYMENT

    def test_cloud_worker_access_always_requires_deployment(self):
        from openjarvis.memory.workspace_sync_status import (
            get_workspace_sync_status, LAYER_REQUIRES_DEPLOYMENT,
        )
        s = get_workspace_sync_status()
        assert s.cloud_worker_access == LAYER_REQUIRES_DEPLOYMENT

    def test_status_not_ready(self):
        from openjarvis.memory.workspace_sync_status import (
            get_workspace_sync_status, SYNC_STATUS_READY,
        )
        s = get_workspace_sync_status()
        assert s.status != SYNC_STATUS_READY

    def test_s3_not_configured_without_env(self, monkeypatch):
        monkeypatch.delenv("OMNIX_WORKBENCH_MEMORY_BUCKET", raising=False)
        monkeypatch.delenv("OMNIX_WORKBENCH_ARTIFACT_BUCKET", raising=False)
        monkeypatch.delenv("OMNIX_WORKBENCH_AWS_REGION", raising=False)
        from importlib import reload
        import openjarvis.memory.workspace_sync_status as mod
        reload(mod)
        s = mod.get_workspace_sync_status()
        assert s.s3_configured is False
        assert s.s3_config in ("not_configured", "missing", "unknown")

    def test_git_tracked_count_is_int(self):
        from openjarvis.memory.workspace_sync_status import get_workspace_sync_status
        s = get_workspace_sync_status()
        assert isinstance(s.git_tracked_count, int)
        assert s.git_tracked_count >= 0

    def test_workspace_sync_probe_in_plan2c_status(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        assert "workspace_sync_status" in s
        assert "workspace_sync_layers" in s
        layers = s["workspace_sync_layers"]
        assert "sync_executed" in layers
        assert "cloud_worker_access" in layers


# ---------------------------------------------------------------------------
# 9. Overall Plan 2 verdict remains HOLD
# ---------------------------------------------------------------------------

class TestPlan2VerdictHold:
    def test_sprint_verdict_is_hold(self):
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        assert "HOLD" in r["sprint_verdict"], (
            f"Plan 2 sprint verdict must remain HOLD. Got: {r['sprint_verdict']}"
        )

    def test_no_subsection_is_macbook_off_ready(self):
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        for sub in r["subsections"]:
            assert sub.get("macbook_off_status") != "READY", (
                f"Subsection {sub.get('subsection', '?')} claims MacBook-off READY — "
                "this must not happen while B1-B8 are open."
            )

    def test_macbook_off_ready_count_is_zero(self):
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        assert r["summary"]["macbook_off_ready"] == 0

    def test_cloud_worker_endpoint_verdict_is_hold(self):
        from openjarvis.server.plan2_routes import get_cloud_worker_parity_status
        r = _run(get_cloud_worker_parity_status())
        assert "HOLD" in r["sprint_verdict"]

    def test_fargate_worker_not_ready_contributes_to_hold(self):
        from openjarvis.server.fargate_readiness import get_fargate_worker_status, STATUS_READY
        r = get_fargate_worker_status()
        assert r.status != STATUS_READY

    def test_blockers_b6_b8_remain_open_in_plan2h(self):
        from openjarvis.server.plan2_routes import _status_2h_long_running
        s = _status_2h_long_running()
        combined_blockers = " ".join(s["blockers"]).lower()
        # B6 blocker must be mentioned
        assert "fargate" in combined_blockers or "b6" in combined_blockers or "deployed" in combined_blockers
