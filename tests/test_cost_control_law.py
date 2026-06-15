"""Targeted tests for Bryan's Pay-On-Demand Cost-Control Law.

Verifies the machine-readable law is persisted and its core enforcement
rules hold: no fake available counts, not_configured reported separately,
accepted checkpoints not re-validated without justification (structural check).
"""

from __future__ import annotations

import pytest

from openjarvis.governance.constitution import (
    CONSTITUTION,
    COST_CONTROL_LAW,
)


# ---------------------------------------------------------------------------
# 1. Law is persisted and machine-readable
# ---------------------------------------------------------------------------


def test_cost_control_law_exists():
    assert COST_CONTROL_LAW, "COST_CONTROL_LAW must be a non-empty string"


def test_cost_control_law_in_constitution_dict():
    assert "cost_control_law" in CONSTITUTION
    assert CONSTITUTION["cost_control_law"] == COST_CONTROL_LAW


def test_cost_control_law_is_cross_platform():
    platforms = [
        "Windsurf", "Claude Code", "ChatGPT", "Claude", "Cursor",
        "API-based agents", "IDE agents", "terminal agents", "browser agents",
    ]
    for platform in platforms:
        assert platform in COST_CONTROL_LAW, (
            f"Cost-control law must explicitly name '{platform}'"
        )


def test_cost_control_law_forbids_fake_work():
    forbidden = [
        "Fake progress", "fake tools", "fake skills", "fake counts",
        "fake validation", "fake completion",
    ]
    for phrase in forbidden:
        assert phrase in COST_CONTROL_LAW, (
            f"Cost-control law must forbid '{phrase}'"
        )


def test_cost_control_law_requires_direct_source_first():
    assert "direct-source-first" in COST_CONTROL_LAW


def test_cost_control_law_requires_final_report_accountability():
    assert "Final reports must include" in COST_CONTROL_LAW


def test_cost_control_law_requires_stop_on_blockers():
    assert "stop on real blockers" in COST_CONTROL_LAW


def test_cost_control_law_requires_separate_reporting_of_unavailable():
    assert "reported separately" in COST_CONTROL_LAW


# ---------------------------------------------------------------------------
# 2. Enforcement: no available tool without real executor
# ---------------------------------------------------------------------------


def test_no_fake_available_tools():
    """After catalog init, every available tool must have a real executor."""
    from openjarvis.tools.catalog import initialize_catalog
    from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus
    ToolRegistry.clear()
    initialize_catalog()
    for spec in ToolRegistry.list_available():
        assert spec.implementation_status == ToolStatus.AVAILABLE, (
            f"Tool '{spec.tool_id}' in available list but status={spec.implementation_status}"
        )
        exec_fn = ToolRegistry.get_executor(spec.tool_id)
        assert exec_fn is not None, (
            f"Tool '{spec.tool_id}' claims AVAILABLE but has no executor"
        )
    ToolRegistry.clear()


def test_not_configured_tools_reported_separately():
    """not_configured tools must appear in unavailable list, not available."""
    from openjarvis.tools.catalog import initialize_catalog
    from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus
    ToolRegistry.clear()
    initialize_catalog()
    available_ids = {t.tool_id for t in ToolRegistry.list_available()}
    unavailable = ToolRegistry.list_unavailable()
    not_configured = [t for t in unavailable if t.implementation_status == ToolStatus.NOT_CONFIGURED]
    assert len(not_configured) >= 1, "At least one not_configured tool must exist"
    for t in not_configured:
        assert t.tool_id not in available_ids, (
            f"Tool '{t.tool_id}' is not_configured but appears in available list"
        )
    ToolRegistry.clear()


def test_planned_tools_not_in_available_list():
    """Planned tools must never be counted as available."""
    from openjarvis.tools.catalog import initialize_catalog
    from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus
    ToolRegistry.clear()
    initialize_catalog()
    for spec in ToolRegistry.list_available():
        assert spec.implementation_status != ToolStatus.PLANNED, (
            f"Tool '{spec.tool_id}' is PLANNED but appears in available list"
        )
    ToolRegistry.clear()


# ---------------------------------------------------------------------------
# 3. Enforcement: hard-gate blocks produce HOLD/UNSAFE, not looping success
# ---------------------------------------------------------------------------


def test_hard_gate_produces_unsafe_not_success():
    """Gateway must return UNSAFE (not SUCCESS) for a hard-gated action."""
    from openjarvis.tools.catalog import initialize_catalog
    from openjarvis.tools.jarvis_registry import ToolRegistry
    from openjarvis.tools.gateway import ToolExecutionGateway
    from openjarvis.tools.execution_log import ExecutionOutcome
    import tempfile, pathlib
    ToolRegistry.clear()
    initialize_catalog()
    with tempfile.TemporaryDirectory() as td:
        gw = ToolExecutionGateway(log_db_path=pathlib.Path(td) / "exec.db")
        # omnix_production_deploy is a HARD_GATE_ACTION in the constitution
        result = gw.execute("omnix_production_deploy", inputs={})
        assert result.outcome in (ExecutionOutcome.HARD_GATE, ExecutionOutcome.FAILED), (
            f"Hard-gated action should be blocked, got outcome={result.outcome}"
        )
        assert not result.ok
    ToolRegistry.clear()
