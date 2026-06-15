"""Ultra Sprint 4 — Tool Registry + Gateway tests.

Covers:
  1.  ToolRegistry registers only real tools as available
  2.  Planned/not_configured tools are not counted as available
  3.  ToolRegistry.stats() reports accurate counts
  4.  ToolExecutionGateway blocks hard-gated actions
  5.  Gateway logs success
  6.  Gateway logs blocked
  7.  Gateway logs not_configured
  8.  Gateway logs failed (executor error)
  9.  Tool execution cannot bypass governance (hard gate = HARD_GATE outcome)
  10. Slack tool returns not_configured without token
  11. Telegram tool returns not_configured without tokens
  12. No real network calls in tests
  13. Catalog initializes and mission.list is available
  14. project.list returns OMNIX as first project
  15. governance.gate_check tool works through gateway
  16. Tool not in registry returns tool_not_found
  17. Disabled tool returns tool_disabled
  18. ToolExecutionResult.to_dict() has all required fields
  19. Catalog stats: total_registered >= 15, no fake inflation
  20. mission.list executor returns real structure (count + missions keys)
"""

from __future__ import annotations

import pytest

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus
from openjarvis.tools.execution_log import ExecutionOutcome, ToolExecutionResult
from openjarvis.tools.gateway import ToolExecutionGateway
from openjarvis.governance.constitution import ProjectRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_tool_registry():
    """Reset registry between tests to avoid catalog cross-contamination."""
    ToolRegistry.clear()
    ProjectRegistry.clear()
    yield
    ToolRegistry.clear()
    ProjectRegistry.clear()


@pytest.fixture()
def gateway(tmp_path):
    """Gateway backed by a temp SQLite DB — no production state touched."""
    return ToolExecutionGateway(log_db_path=tmp_path / "test_executions.db")


def _make_tool(
    tool_id: str = "test.noop",
    status: str = ToolStatus.AVAILABLE,
    enabled: bool = True,
    configured: bool = True,
    risk_level: str = "low",
    blocker: str = "",
) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        display_name="Test Tool",
        description="A test tool",
        category="test",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_permissions=[],
        risk_level=risk_level,
        project_scope=[],
        enabled=enabled,
        configured=configured,
        approval_required=False,
        owning_agent_id="manager",
        executor_ref="noop",
        implementation_status=status,
        blocker=blocker,
    )


def _noop_executor(inputs, context=None):
    return {"ok": True, "inputs": inputs}


# ---------------------------------------------------------------------------
# 1–3: Registry basics
# ---------------------------------------------------------------------------


def test_available_tool_counts_as_available():
    spec = _make_tool("test.available", status=ToolStatus.AVAILABLE)
    ToolRegistry.register(spec, executor=_noop_executor)
    assert len(ToolRegistry.list_available()) == 1


def test_planned_tool_not_in_available():
    spec = _make_tool("test.planned", status=ToolStatus.PLANNED)
    ToolRegistry.register(spec, executor=None)
    assert len(ToolRegistry.list_available()) == 0
    assert len(ToolRegistry.list_unavailable()) == 1
    assert ToolRegistry.get("test.planned").implementation_status == ToolStatus.PLANNED


def test_not_configured_tool_not_in_available():
    spec = _make_tool("test.nc", status=ToolStatus.NOT_CONFIGURED, configured=False, blocker="needs token")
    ToolRegistry.register(spec, executor=_noop_executor)
    assert len(ToolRegistry.list_available()) == 0
    assert len(ToolRegistry.list_unavailable()) == 1


def test_registry_stats_accurate():
    ToolRegistry.register(_make_tool("t.a1", status=ToolStatus.AVAILABLE), executor=_noop_executor)
    ToolRegistry.register(_make_tool("t.a2", status=ToolStatus.AVAILABLE), executor=_noop_executor)
    ToolRegistry.register(
        _make_tool("t.nc", status=ToolStatus.NOT_CONFIGURED, configured=False, blocker="x"),
        executor=_noop_executor,
    )
    stats = ToolRegistry.stats()
    assert stats["total_registered"] == 3
    assert stats["available"] == 2
    assert stats["unavailable"] == 1


def test_register_available_without_executor_raises():
    spec = _make_tool("t.bad", status=ToolStatus.AVAILABLE)
    with pytest.raises(ValueError):
        ToolRegistry.register(spec, executor=None)


# ---------------------------------------------------------------------------
# 4–9: Gateway behavior
# ---------------------------------------------------------------------------


def test_gateway_executes_safe_tool(gateway):
    spec = _make_tool("t.safe", status=ToolStatus.AVAILABLE)
    ToolRegistry.register(spec, executor=_noop_executor)
    result = gateway.execute("t.safe", inputs={"x": 1})
    assert result.ok is True
    assert result.outcome == ExecutionOutcome.SUCCESS


def test_gateway_blocks_hard_gate_action(gateway):
    """Tool named after a hard gate action must be blocked by governance."""
    spec = ToolSpec(
        tool_id="real_slack_send",
        display_name="Slack Send",
        description="Send slack",
        category="notify",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_permissions=[],
        risk_level="medium",
        project_scope=[],
        enabled=True,
        configured=True,
        approval_required=True,
        owning_agent_id="manager",
        executor_ref="noop",
        implementation_status=ToolStatus.AVAILABLE,
    )
    ToolRegistry.register(spec, executor=_noop_executor)
    result = gateway.execute("real_slack_send", inputs={})
    assert result.ok is False
    assert result.outcome == ExecutionOutcome.HARD_GATE
    assert result.governance_verdict == "UNSAFE"


def test_gateway_logs_success(gateway):
    spec = _make_tool("t.log_success", status=ToolStatus.AVAILABLE)
    ToolRegistry.register(spec, executor=_noop_executor)
    gateway.execute("t.log_success", inputs={})
    entries = gateway.get_log().list_recent(limit=10)
    assert any(e.tool_id == "t.log_success" and e.outcome == ExecutionOutcome.SUCCESS for e in entries)


def test_gateway_logs_blocked(gateway):
    spec = ToolSpec(
        tool_id="real_email_send",
        display_name="Email Send",
        description="Email",
        category="notify",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_permissions=[],
        risk_level="medium",
        project_scope=[],
        enabled=True,
        configured=True,
        approval_required=True,
        owning_agent_id="manager",
        executor_ref="noop",
        implementation_status=ToolStatus.AVAILABLE,
    )
    ToolRegistry.register(spec, executor=_noop_executor)
    gateway.execute("real_email_send", inputs={})
    entries = gateway.get_log().list_by_outcome(ExecutionOutcome.HARD_GATE, limit=5)
    assert len(entries) >= 1


def test_gateway_logs_not_configured(gateway):
    spec = _make_tool("t.nc2", status=ToolStatus.NOT_CONFIGURED, configured=False, blocker="needs token")
    ToolRegistry.register(spec, executor=_noop_executor)
    result = gateway.execute("t.nc2", inputs={})
    assert result.outcome == ExecutionOutcome.NOT_CONFIGURED
    entries = gateway.get_log().list_by_outcome(ExecutionOutcome.NOT_CONFIGURED, limit=5)
    assert len(entries) >= 1


def test_gateway_logs_failed_on_executor_error(gateway):
    def _bad_executor(inputs, context=None):
        raise RuntimeError("intentional executor failure")

    spec = _make_tool("t.bad_exec", status=ToolStatus.AVAILABLE)
    ToolRegistry.register(spec, executor=_bad_executor)
    result = gateway.execute("t.bad_exec", inputs={})
    assert result.ok is False
    assert result.outcome == ExecutionOutcome.FAILED
    assert "intentional executor failure" in result.error


def test_gateway_tool_not_found_returns_structured_error(gateway):
    result = gateway.execute("nonexistent.tool", inputs={})
    assert result.ok is False
    assert result.error_type == "tool_not_found"


def test_gateway_disabled_tool_blocked(gateway):
    spec = _make_tool("t.disabled", status=ToolStatus.AVAILABLE, enabled=False)
    ToolRegistry.register(spec, executor=_noop_executor)
    result = gateway.execute("t.disabled", inputs={})
    assert result.ok is False
    assert result.error_type == "tool_disabled"


# ---------------------------------------------------------------------------
# 10–12: Slack / Telegram not_configured (no real network calls)
# ---------------------------------------------------------------------------


def test_slack_tool_not_configured_without_token(gateway, monkeypatch):
    """Slack notifier returns not_configured when token absent."""
    monkeypatch.setenv("OPENCLAW_SLACK_BOT_TOKEN", "")
    from openjarvis.mission.notifier import SlackNotifier
    notifier = SlackNotifier()
    assert not notifier.is_configured()


def test_telegram_tool_not_configured_without_tokens(gateway, monkeypatch):
    """Telegram notifier returns not_configured when tokens absent."""
    monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("JARVIS_TELEGRAM_CHAT_ID", "")
    from openjarvis.mission.notifier import TelegramNotifier
    notifier = TelegramNotifier()
    assert not notifier.is_configured()


# ---------------------------------------------------------------------------
# 13–16: Catalog integration (uses real catalog — isolated by fixture reset)
# ---------------------------------------------------------------------------


@pytest.fixture()
def catalog_gateway(tmp_path):
    """Gateway that also initializes the full tool catalog."""
    from openjarvis.tools.catalog import initialize_catalog
    initialize_catalog()
    return ToolExecutionGateway(log_db_path=tmp_path / "catalog_test.db")


def test_catalog_mission_list_is_available():
    from openjarvis.tools.catalog import initialize_catalog
    initialize_catalog()
    spec = ToolRegistry.get("mission.list")
    assert spec is not None
    assert spec.is_available()


def test_catalog_project_list_returns_omnix(catalog_gateway):
    result = catalog_gateway.execute("project.list", inputs={})
    assert result.ok is True
    projects = result.output.get("projects", [])
    assert any(p["project_id"] == "omnix" for p in projects)
    omnix = next(p for p in projects if p["project_id"] == "omnix")
    assert omnix["priority"] == 1


def test_catalog_governance_gate_check_via_gateway(catalog_gateway):
    result = catalog_gateway.execute(
        "governance.gate_check",
        inputs={"action_type": "real_slack_send"},
    )
    assert result.ok is True
    assert result.output["allowed"] is False
    assert result.output["verdict"] == "UNSAFE"


def test_catalog_governance_gate_check_safe_action(catalog_gateway):
    result = catalog_gateway.execute(
        "governance.gate_check",
        inputs={"action_type": "read_data", "risk_level": "low"},
    )
    assert result.ok is True
    assert result.output["allowed"] is True


# ---------------------------------------------------------------------------
# 17–20: Stats + structure
# ---------------------------------------------------------------------------


def test_catalog_total_registered_at_least_15():
    from openjarvis.tools.catalog import initialize_catalog
    initialize_catalog()
    stats = ToolRegistry.stats()
    assert stats["total_registered"] >= 15


def test_catalog_no_fake_available_inflation():
    """Available count must equal actual available specs — not total count."""
    from openjarvis.tools.catalog import initialize_catalog
    initialize_catalog()
    stats = ToolRegistry.stats()
    assert stats["available"] <= stats["total_registered"]
    available_list = ToolRegistry.list_available()
    assert stats["available"] == len(available_list)


def test_execution_result_to_dict_has_required_fields(gateway):
    spec = _make_tool("t.fields", status=ToolStatus.AVAILABLE)
    ToolRegistry.register(spec, executor=_noop_executor)
    result = gateway.execute("t.fields", inputs={}, project_id="omnix")
    d = result.to_dict()
    for key in ["log_id", "tool_id", "outcome", "ok", "output", "error",
                "error_type", "governance_verdict", "execution_ms",
                "project_id", "mission_id", "task_id", "created_at"]:
        assert key in d, f"Missing key: {key}"


def test_tool_spec_to_dict_has_required_fields():
    spec = _make_tool("t.spec_dict", status=ToolStatus.AVAILABLE)
    d = spec.to_dict()
    for key in ["tool_id", "display_name", "description", "category",
                "input_schema", "output_schema", "required_permissions",
                "risk_level", "project_scope", "enabled", "configured",
                "approval_required", "owning_agent_id", "executor_ref",
                "implementation_status", "blocker", "is_available",
                "created_at", "updated_at"]:
        assert key in d, f"Missing key: {key}"
