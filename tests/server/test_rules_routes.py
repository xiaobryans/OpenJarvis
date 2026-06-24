"""Tests for the Rules Engine REST API routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from openjarvis.rules.registry import RuleRegistry


@pytest.fixture(autouse=True)
def reset_registry(tmp_path, monkeypatch):
    """Each test gets a fresh registry backed by tmp_path."""
    RuleRegistry.reset_instance()
    reg = RuleRegistry(store_dir=tmp_path / "rules")
    RuleRegistry._instance = reg
    yield
    RuleRegistry.reset_instance()


@pytest.fixture()
def client():
    from openjarvis.server.rules_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _create_rule(client, **kwargs):
    payload = {
        "name": kwargs.get("name", "test rule"),
        "description": kwargs.get("description", ""),
        "rule_type": kwargs.get("rule_type", "behavioral"),
        "scope": kwargs.get("scope", "global"),
        "priority": kwargs.get("priority", 50),
        "condition": kwargs.get("condition", {}),
        "action": kwargs.get("action", {"effect": "allow", "target": "responses"}),
        "safety_level": kwargs.get("safety_level", "low"),
        "tags": kwargs.get("tags", []),
    }
    return client.post("/v1/rules", json=payload)


class TestListRules:
    def test_empty_list(self, client):
        r = client.get("/v1/rules")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["rules"] == []

    def test_list_after_create(self, client):
        _create_rule(client)
        r = client.get("/v1/rules")
        assert r.json()["count"] == 1

    def test_filter_by_scope(self, client):
        _create_rule(client, scope="global")
        _create_rule(client, scope="project")
        r = client.get("/v1/rules?scope=global")
        data = r.json()
        assert data["count"] == 1
        assert data["rules"][0]["scope"] == "global"

    def test_filter_by_status(self, client):
        _create_rule(client, safety_level="low")   # active
        _create_rule(client, safety_level="high")  # draft
        r = client.get("/v1/rules?status=active")
        data = r.json()
        assert data["count"] == 1


class TestGetRule:
    def test_get_existing(self, client):
        resp = _create_rule(client, name="my rule")
        rule_id = resp.json()["rule"]["rule_id"]
        r = client.get(f"/v1/rules/{rule_id}")
        assert r.status_code == 200
        assert r.json()["rule"]["name"] == "my rule"

    def test_get_missing_404(self, client):
        r = client.get("/v1/rules/nonexistent_rule_id")
        assert r.status_code == 404


class TestCreateRule:
    def test_create_ok(self, client):
        r = _create_rule(client, name="hello rule")
        assert r.status_code == 200
        data = r.json()
        assert data["rule"]["name"] == "hello rule"
        assert data["rule"]["rule_id"].startswith("rule_")

    def test_high_safety_starts_as_draft(self, client):
        r = _create_rule(client, safety_level="high")
        assert r.json()["rule"]["status"] == "draft"

    def test_low_safety_starts_as_active(self, client):
        r = _create_rule(client, safety_level="low")
        assert r.json()["rule"]["status"] == "active"

    def test_conflict_detected_on_create(self, client):
        _create_rule(client, action={"effect": "block", "target": "emails"}, rule_type="filter")
        r = _create_rule(client, action={"effect": "allow", "target": "emails"}, rule_type="filter")
        data = r.json()
        assert len(data["conflicts"]) > 0
        assert data["rule"]["status"] == "conflicted"


class TestActivateDeactivate:
    def test_deactivate_active_rule(self, client):
        resp = _create_rule(client)
        rule_id = resp.json()["rule"]["rule_id"]
        r = client.post(f"/v1/rules/{rule_id}/deactivate")
        assert r.status_code == 200
        assert r.json()["status"] == "deactivated"

    def test_activate_inactive_rule(self, client):
        resp = _create_rule(client)
        rule_id = resp.json()["rule"]["rule_id"]
        client.post(f"/v1/rules/{rule_id}/deactivate")
        r = client.post(f"/v1/rules/{rule_id}/activate")
        assert r.status_code == 200
        assert r.json()["status"] == "activated"

    def test_activate_high_safety_blocked(self, client):
        resp = _create_rule(client, safety_level="high")
        rule_id = resp.json()["rule"]["rule_id"]
        r = client.post(f"/v1/rules/{rule_id}/activate")
        assert r.status_code == 403

    def test_deactivate_system_safety_blocked(self, client):
        from openjarvis.rules.types import Rule, RuleStatus, RuleType, make_rule_id
        import time
        reg = RuleRegistry.get_instance()
        rule = Rule(
            rule_id=make_rule_id(),
            name="system safety rule",
            description="",
            rule_type=RuleType.SAFETY,
            scope="global",
            status=RuleStatus.ACTIVE,
            priority=100,
            condition={},
            action={},
            source="system",
            safety_level="high",
            created_at=time.time(),
            updated_at=time.time(),
        )
        reg.create(rule)
        r = client.post(f"/v1/rules/{rule.rule_id}/deactivate")
        assert r.status_code == 403


class TestUpdateRule:
    def test_update_name(self, client):
        resp = _create_rule(client, name="original")
        rule_id = resp.json()["rule"]["rule_id"]
        r = client.patch(f"/v1/rules/{rule_id}", json={"name": "updated"})
        assert r.status_code == 200
        assert r.json()["rule"]["name"] == "updated"

    def test_update_empty_body_400(self, client):
        resp = _create_rule(client)
        rule_id = resp.json()["rule"]["rule_id"]
        r = client.patch(f"/v1/rules/{rule_id}", json={})
        assert r.status_code == 400


class TestDeleteRule:
    def test_delete_ok(self, client):
        resp = _create_rule(client)
        rule_id = resp.json()["rule"]["rule_id"]
        r = client.delete(f"/v1/rules/{rule_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    def test_delete_missing_404(self, client):
        r = client.delete("/v1/rules/nonexistent")
        assert r.status_code == 404

    def test_delete_system_safety_blocked(self, client):
        from openjarvis.rules.types import Rule, RuleStatus, RuleType, make_rule_id
        import time
        reg = RuleRegistry.get_instance()
        rule = Rule(
            rule_id=make_rule_id(),
            name="sys safety",
            description="",
            rule_type=RuleType.SAFETY,
            scope="global",
            status=RuleStatus.ACTIVE,
            priority=100,
            condition={},
            action={},
            source="system",
            safety_level="high",
            created_at=time.time(),
            updated_at=time.time(),
        )
        reg.create(rule)
        r = client.delete(f"/v1/rules/{rule.rule_id}")
        assert r.status_code == 403


class TestEvaluateRules:
    def test_evaluate_empty(self, client):
        r = client.post("/v1/rules/evaluate", json={"action_type": "chat"})
        assert r.status_code == 200
        data = r.json()
        assert "evaluation" in data
        assert data["evaluation"]["matched_count"] == 0

    def test_evaluate_with_matching_rule(self, client):
        _create_rule(client, scope="global")
        r = client.post("/v1/rules/evaluate", json={"action_type": "chat"})
        data = r.json()
        assert data["evaluation"]["matched_count"] == 1
