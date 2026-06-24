"""Plan 2G — Approval notification queue closure tests (B5A / B5B / B5C).

Verifies:
1.  B5A: Approval gate still requires approval for tier 2+ actions (no bypass).
2.  B5A: Tier 0/1 actions are AUTO_ALLOW — no internal notification event created.
3.  B5B: PENDING approval creation enqueues an internal notification event.
4.  B5B: Notification event contains only safe metadata (no secrets).
5.  B5B: Notification event fields are correct type and non-empty.
6.  B5B: Multiple approvals produce distinct events.
7.  B5B: NotificationQueue list_pending() returns queued events.
8.  B5B: mark_delivery_status() updates event status correctly.
9.  B5C: External delivery is NOT attempted by the notification queue module.
10. Public /v1/mobile-parity/approvals returns three-layer B5 status.
11. Public endpoint does not leak env var names.
12. Public endpoint does not leak token names.
13. Public endpoint does not leak private paths.
14. Public endpoint does not leak provider account identifiers.
15. Public endpoint distinguishes internal queue readiness from external delivery blocked.
16. /v1/approvals/pending is auth-gated (not in public path list).
17. /v1/approvals/{id}/approve is auth-gated.
18. /v1/approvals/{id}/deny is auth-gated.
19. Overall Plan 2 verdict remains HOLD while B1/B2/B4/B6/B7/B8 remain open.
20. Approval grant does NOT create a notification event (only PENDING creation does).
21. NotificationQueue is import-safe (no external dependencies required).
22. enqueue_approval_notification() never raises even if queue fails.
23. is_queue_ready() returns a boolean (no exception).
24. Notification event status vocabulary is correct (STATUS_QUEUED is default).
25. NotificationQueue count_queued() reflects enqueued events.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# B5A — Approval gate correctness
# ---------------------------------------------------------------------------


class TestB5AApprovalGate:
    def test_tier2_action_creates_pending_not_granted(self):
        """Tier 2 action must create PENDING approval, not GRANTED."""
        from openjarvis.authority.approval_engine import ApprovalEngine, ApprovalStatus
        with tempfile.TemporaryDirectory() as td:
            engine = ApprovalEngine(db_path=Path(td) / "approvals.db")
            record = engine.request_approval(
                action_type="terminal_exec",
                requester="test_agent",
                tier=2,
                risk_level="medium",
            )
            assert record.status == ApprovalStatus.PENDING, (
                f"Tier 2 approval should be PENDING, got {record.status}"
            )
            engine.close()

    def test_tier0_action_is_auto_granted(self):
        """Tier 0 action should be AUTO_ALLOW and GRANTED immediately."""
        from openjarvis.authority.approval_engine import ApprovalEngine, ApprovalStatus
        with tempfile.TemporaryDirectory() as td:
            engine = ApprovalEngine(db_path=Path(td) / "approvals.db")
            record = engine.request_approval(
                action_type="read_file",
                requester="test_agent",
                tier=0,
                risk_level="low",
            )
            assert record.status == ApprovalStatus.GRANTED, (
                f"Tier 0 approval should be GRANTED, got {record.status}"
            )
            engine.close()

    def test_tier1_action_is_auto_granted(self):
        """Tier 1 action should be AUTO_ALLOW and GRANTED immediately."""
        from openjarvis.authority.approval_engine import ApprovalEngine, ApprovalStatus
        with tempfile.TemporaryDirectory() as td:
            engine = ApprovalEngine(db_path=Path(td) / "approvals.db")
            record = engine.request_approval(
                action_type="list_files",
                requester="test_agent",
                tier=1,
                risk_level="low",
            )
            assert record.status == ApprovalStatus.GRANTED
            engine.close()

    def test_pending_approval_not_active(self):
        """A PENDING approval must not be considered active (is_active() = False)."""
        from openjarvis.authority.approval_engine import ApprovalEngine
        with tempfile.TemporaryDirectory() as td:
            engine = ApprovalEngine(db_path=Path(td) / "approvals.db")
            record = engine.request_approval(
                action_type="deploy",
                requester="test_agent",
                tier=3,
                risk_level="high",
            )
            assert not record.is_active(), "PENDING approval must not be active"
            engine.close()

    def test_deny_blocks_action(self):
        """Denying an approval must set status to DENIED."""
        from openjarvis.authority.approval_engine import ApprovalEngine, ApprovalStatus
        with tempfile.TemporaryDirectory() as td:
            engine = ApprovalEngine(db_path=Path(td) / "approvals.db")
            record = engine.request_approval(
                action_type="send_slack",
                requester="test_agent",
                tier=2,
                risk_level="medium",
            )
            result = engine.deny(record.approval_id, reason="not authorized")
            assert result is True
            updated = engine.get(record.approval_id)
            assert updated.status == ApprovalStatus.DENIED
            engine.close()

    def test_pending_list_returns_pending_only(self):
        """list_pending() must only return PENDING records."""
        from openjarvis.authority.approval_engine import ApprovalEngine, ApprovalStatus
        with tempfile.TemporaryDirectory() as td:
            engine = ApprovalEngine(db_path=Path(td) / "approvals.db")
            # create tier 2 (PENDING)
            engine.request_approval("act_pending", "agent", tier=2, risk_level="medium")
            # create tier 0 (GRANTED)
            engine.request_approval("act_granted", "agent", tier=0, risk_level="low")
            pending = engine.list_pending()
            assert all(r.status == ApprovalStatus.PENDING for r in pending)
            engine.close()


# ---------------------------------------------------------------------------
# B5B — Internal notification enqueue
# ---------------------------------------------------------------------------


class TestB5BInternalNotificationQueue:
    def test_notification_queue_importable(self):
        """NotificationQueue must be importable without external dependencies."""
        from openjarvis.authority.notification_queue import NotificationQueue
        assert NotificationQueue is not None

    def test_is_queue_ready_returns_bool(self):
        """is_queue_ready() must return a boolean and not raise."""
        from openjarvis.authority.notification_queue import is_queue_ready
        result = is_queue_ready()
        assert isinstance(result, bool)

    def test_enqueue_returns_event(self):
        """enqueue() must return a NotificationEvent with safe metadata."""
        from openjarvis.authority.notification_queue import NotificationQueue, STATUS_QUEUED
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            event = q.enqueue(
                approval_id="abc123",
                action_type="terminal_exec",
                risk_level="medium",
            )
            assert event.event_id
            assert event.approval_id == "abc123"
            assert event.action_type == "terminal_exec"
            assert event.risk_level == "medium"
            assert event.status == STATUS_QUEUED
            assert event.created_at  # non-empty ISO8601 string
            q.close()

    def test_notification_event_has_no_secrets(self):
        """Notification event fields must not contain secret values or env var names."""
        from openjarvis.authority.notification_queue import NotificationQueue
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            event = q.enqueue(
                approval_id="test_id",
                action_type="send_slack",
                risk_level="high",
            )
            d = event.to_dict()
            payload_str = str(d).lower()
            # Must not contain secret-like substrings
            for forbidden in ("token", "secret", "password", "api_key", "xoxb", "oauth", "private_key"):
                assert forbidden not in payload_str, (
                    f"Notification event contains forbidden keyword: {forbidden!r}"
                )
            q.close()

    def test_notification_event_no_private_paths(self):
        """Notification event must not contain private local paths."""
        from openjarvis.authority.notification_queue import NotificationQueue
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            event = q.enqueue(
                approval_id="path_test",
                action_type="file_delete",
                risk_level="high",
            )
            d = event.to_dict()
            payload_str = str(d)
            assert "~/.openjarvis" not in payload_str
            assert "/home/" not in payload_str
            assert ".env" not in payload_str
            q.close()

    def test_pending_approval_creates_notification_event(self):
        """Creating a tier 2+ PENDING approval must enqueue an internal notification event."""
        from openjarvis.authority.approval_engine import ApprovalEngine
        from openjarvis.authority.notification_queue import NotificationQueue
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "approvals.db"
            nq_path = Path(td) / "nq.db"
            # Pre-initialize the queue in the same path so ApprovalEngine uses it
            import openjarvis.authority.notification_queue as nqmod
            original = nqmod._queue_instance
            nqmod._queue_instance = NotificationQueue(db_path=nq_path)
            try:
                engine = ApprovalEngine(db_path=db_path)
                record = engine.request_approval(
                    action_type="terminal_exec",
                    requester="test_agent",
                    tier=2,
                    risk_level="medium",
                )
                # Should have enqueued a notification event
                events = nqmod._queue_instance.list_all()
                matching = [e for e in events if e.approval_id == record.approval_id]
                assert len(matching) >= 1, (
                    "PENDING approval creation should enqueue at least one notification event"
                )
                engine.close()
            finally:
                nqmod._queue_instance = original

    def test_auto_allow_does_not_create_notification_event(self):
        """Tier 0/1 AUTO_ALLOW approvals must NOT create notification events."""
        from openjarvis.authority.approval_engine import ApprovalEngine
        from openjarvis.authority.notification_queue import NotificationQueue
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "approvals.db"
            nq_path = Path(td) / "nq.db"
            import openjarvis.authority.notification_queue as nqmod
            original = nqmod._queue_instance
            nqmod._queue_instance = NotificationQueue(db_path=nq_path)
            try:
                engine = ApprovalEngine(db_path=db_path)
                initial_count = nqmod._queue_instance.count_queued()
                record = engine.request_approval(
                    action_type="read_file",
                    requester="test_agent",
                    tier=0,
                    risk_level="low",
                )
                after_count = nqmod._queue_instance.count_queued()
                assert after_count == initial_count, (
                    "Tier 0 AUTO_ALLOW should NOT add a notification event"
                )
                engine.close()
            finally:
                nqmod._queue_instance = original

    def test_multiple_pending_approvals_create_distinct_events(self):
        """Multiple PENDING approvals must create distinct notification events."""
        from openjarvis.authority.notification_queue import NotificationQueue
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            e1 = q.enqueue("approval_1", "act_a", "medium")
            e2 = q.enqueue("approval_2", "act_b", "high")
            assert e1.event_id != e2.event_id
            assert e1.approval_id != e2.approval_id
            q.close()

    def test_list_pending_returns_queued_events(self):
        """list_pending() must return events with queued or delivery_blocked status."""
        from openjarvis.authority.notification_queue import NotificationQueue, STATUS_QUEUED, STATUS_SENT
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            q.enqueue("ap1", "act_1", "medium")
            q.enqueue("ap2", "act_2", "high")
            pending = q.list_pending()
            assert len(pending) == 2
            assert all(e.status in (STATUS_QUEUED,) for e in pending)
            q.close()

    def test_mark_delivery_status_updates_event(self):
        """mark_delivery_status() must update a notification event's status."""
        from openjarvis.authority.notification_queue import NotificationQueue, STATUS_SENT
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            event = q.enqueue("ap1", "act_x", "low")
            result = q.mark_delivery_status(event.event_id, STATUS_SENT)
            assert result is True
            updated = [e for e in q.list_all() if e.event_id == event.event_id]
            assert updated[0].status == STATUS_SENT
            q.close()

    def test_count_queued_reflects_enqueued(self):
        """count_queued() must reflect the number of pending events."""
        from openjarvis.authority.notification_queue import NotificationQueue
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            assert q.count_queued() == 0
            q.enqueue("ap1", "act_1", "medium")
            assert q.count_queued() == 1
            q.enqueue("ap2", "act_2", "high")
            assert q.count_queued() == 2
            q.close()

    def test_enqueue_approval_notification_never_raises(self):
        """enqueue_approval_notification() must never raise, even on bad input."""
        from openjarvis.authority.notification_queue import enqueue_approval_notification
        # Should not raise regardless of input
        result = enqueue_approval_notification("", "", "")
        # Returns NotificationEvent or None — not an exception

    def test_notification_event_to_dict_safe_keys(self):
        """to_dict() must only return safe, documented keys."""
        from openjarvis.authority.notification_queue import NotificationQueue
        with tempfile.TemporaryDirectory() as td:
            q = NotificationQueue(db_path=Path(td) / "nq.db")
            event = q.enqueue("ap_test", "action_type_x", "medium")
            d = event.to_dict()
            expected_keys = {
                "event_id", "approval_id", "action_type", "action_category",
                "risk_level", "created_at", "channel_target_class", "status",
            }
            assert set(d.keys()) == expected_keys, (
                f"Unexpected keys in event dict: {set(d.keys()) - expected_keys}"
            )
            q.close()


# ---------------------------------------------------------------------------
# B5C — External delivery NOT attempted
# ---------------------------------------------------------------------------


class TestB5CExternalDeliveryBlocked:
    def test_notification_queue_does_not_send_slack(self):
        """NotificationQueue enqueue must NOT call Slack send."""
        import unittest.mock as mock
        with mock.patch("openjarvis.mission.notifier.SlackNotifier.send") as slack_mock:
            from openjarvis.authority.notification_queue import NotificationQueue
            with tempfile.TemporaryDirectory() as td:
                q = NotificationQueue(db_path=Path(td) / "nq.db")
                q.enqueue("ap1", "send_slack", "high")
                q.close()
            slack_mock.assert_not_called()

    def test_notification_queue_does_not_send_telegram(self):
        """NotificationQueue enqueue must NOT call Telegram send."""
        import unittest.mock as mock
        with mock.patch("openjarvis.mission.notifier.TelegramNotifier.send") as tg_mock:
            from openjarvis.authority.notification_queue import NotificationQueue
            with tempfile.TemporaryDirectory() as td:
                q = NotificationQueue(db_path=Path(td) / "nq.db")
                q.enqueue("ap1", "send_telegram", "high")
                q.close()
            tg_mock.assert_not_called()

    def test_external_delivery_status_is_not_ready(self):
        """External delivery status must not be READY while no Fargate deployment exists."""
        from openjarvis.server.plan2_routes import _notification_queue_probe
        probe = _notification_queue_probe()
        # Must NOT be READY — Fargate is not deployed
        assert probe["external_notification_delivery_status"] != "READY", (
            "External delivery must not claim READY without live Fargate deployment"
        )


# ---------------------------------------------------------------------------
# Public endpoint safety
# ---------------------------------------------------------------------------


class TestPublicApprovalEndpointSafety:
    def test_public_endpoint_returns_three_layer_status(self):
        """Public /v1/mobile-parity/approvals must include B5A/B5B/B5C layer fields."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        assert "approval_gate_status" in r, "Missing approval_gate_status (B5A)"
        assert "internal_notification_queue_status" in r, "Missing internal_notification_queue_status (B5B)"
        assert "external_notification_delivery_status" in r, "Missing external_notification_delivery_status (B5C)"

    def test_public_endpoint_no_env_var_names(self):
        """Public endpoint must not expose env var names."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        payload = str(r)
        forbidden_env_vars = [
            "TELEGRAM_BOT_TOKEN",
            "JARVIS_TELEGRAM_BOT_TOKEN",
            "SLACK_BOT_TOKEN",
            "OPENCLAW_SLACK_BOT_TOKEN",
            "OPENJARVIS_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
        ]
        for env_var in forbidden_env_vars:
            assert env_var not in payload, (
                f"Public endpoint leaks env var name: {env_var!r}"
            )

    def test_public_endpoint_no_token_values(self):
        """Public endpoint must not expose token presence booleans as keys."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        for key in r:
            assert not key.endswith("_present"), (
                f"Public endpoint has token presence boolean key: {key!r}"
            )

    def test_public_endpoint_no_private_paths(self):
        """Public endpoint must not expose private local paths."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        payload = str(r)
        for path_fragment in ("~/.openjarvis", "/home/", ".env", "oauth_tokens"):
            assert path_fragment not in payload, (
                f"Public endpoint leaks private path: {path_fragment!r}"
            )

    def test_public_endpoint_no_provider_account_ids(self):
        """Public endpoint must not expose provider account identifiers."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        payload = str(r)
        # These are example account ID patterns — must never appear
        for forbidden in ("xoxb-", "C0BAF", "Bearer ", "sk-"):
            assert forbidden not in payload, (
                f"Public endpoint may expose provider account ID: {forbidden!r}"
            )

    def test_public_endpoint_b5b_ready_b5c_not_ready(self):
        """B5B should be READY; B5C must NOT be READY in public endpoint."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        # B5B (internal queue) should now be READY
        assert r.get("internal_notification_queue_status") == "READY", (
            f"B5B should be READY after this sprint, got: {r.get('internal_notification_queue_status')!r}"
        )
        # B5C (external delivery) must NOT be READY
        assert r.get("external_notification_delivery_status") != "READY", (
            "B5C external delivery must not claim READY without live Fargate deployment"
        )

    def test_public_endpoint_mobile_action_requires_auth(self):
        """mobile_approval_action_status must indicate AUTH_REQUIRED."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        assert r.get("mobile_approval_action_status") == "AUTH_REQUIRED", (
            "Mobile approval actions must require authentication"
        )

    def test_public_endpoint_has_plan2g_verdict(self):
        """Public endpoint must include sprint_verdict for plan 2G."""
        from openjarvis.server.plan2_routes import get_approvals_parity_status
        r = _run(get_approvals_parity_status())
        assert "PLAN_2G" in r.get("sprint_verdict", ""), (
            "Public endpoint missing PLAN_2G sprint_verdict"
        )


# ---------------------------------------------------------------------------
# Auth-gated approval routes
# ---------------------------------------------------------------------------


class TestApprovalRoutesAuthGated:
    def test_approvals_pending_not_in_public_paths(self):
        """/v1/approvals/pending must NOT be in the public path whitelist."""
        from openjarvis.server.auth_middleware import AuthMiddleware
        public_paths = AuthMiddleware._PUBLIC_PATHS  # type: ignore[attr-defined]
        assert "/v1/approvals/pending" not in public_paths, (
            "/v1/approvals/pending must not be in public paths — it requires auth"
        )

    def test_approvals_approve_not_in_public_paths(self):
        """/v1/approvals/ prefix routes must be auth-gated."""
        from openjarvis.server.auth_middleware import AuthMiddleware
        public_paths = AuthMiddleware._PUBLIC_PATHS  # type: ignore[attr-defined]
        for path in public_paths:
            assert not path.startswith("/v1/approvals/"), (
                f"Approval action route {path!r} must not be in public paths"
            )

    def test_mobile_parity_approvals_is_public(self):
        """/v1/mobile-parity/approvals must be in the public path list (status only)."""
        from openjarvis.server.auth_middleware import AuthMiddleware
        assert "/v1/mobile-parity/approvals" in AuthMiddleware._PUBLIC_PATHS


# ---------------------------------------------------------------------------
# Overall Plan 2 verdict remains HOLD
# ---------------------------------------------------------------------------


class TestOverallPlan2VerdictHold:
    def test_plan2_overall_verdict_is_hold(self):
        """Overall Plan 2 verdict must remain HOLD while external blockers remain."""
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        verdict = r.get("sprint_verdict", "")
        assert "HOLD" in verdict, (
            f"Overall Plan 2 verdict must be HOLD, got: {verdict!r}"
        )

    def test_plan2_macbook_off_not_ready(self):
        """Plan 2 must not claim macbook_off READY while Fargate/vault blockers remain."""
        from openjarvis.server.plan2_routes import get_mobile_parity_status
        r = _run(get_mobile_parity_status())
        # Check that at least some subsections report non-READY macbook_off status
        subsections = r.get("subsections", [])
        non_ready = [s for s in subsections if s.get("macbook_off_status") != "READY"]
        assert len(non_ready) > 0, (
            "At least some subsections must report macbook_off status as non-READY"
        )
