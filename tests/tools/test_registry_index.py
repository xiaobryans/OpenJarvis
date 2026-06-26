"""Tests for the unified tool-registry facade (read-only visibility + drift).

The shared autouse ``_clean_registries`` fixture empties the registries before
each test, so these tests register a probe tool in-test rather than relying on
global registration state.
"""

from openjarvis.core.registry import ToolRegistry as CoreReg
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec
from openjarvis.tools.registry_index import (
    agent_tool_names,
    catalog_tool_ids,
    detect_drift,
    unified_index,
)


def _register_probe(name: str = "__facade_probe__"):
    @CoreReg.register(name)
    class _Probe(BaseTool):
        tool_id = name

        @property
        def spec(self):
            return ToolSpec(
                name=name,
                description="probe",
                parameters={"type": "object", "properties": {}},
                category="test",
            )

        def execute(self, **params):
            return ToolResult(tool_name=name, content="ok", success=True)

    return _Probe


def test_facade_sees_agent_registry():
    _register_probe()
    assert "__facade_probe__" in agent_tool_names()


def test_unified_index_shape():
    _register_probe()
    idx = unified_index()
    assert set(idx) >= {
        "agent_tools",
        "catalog_tools",
        "agent_count",
        "catalog_count",
        "total_unique",
        "collisions",
        "has_drift",
    }
    assert idx["agent_count"] == len(idx["agent_tools"])
    assert idx["catalog_count"] == len(idx["catalog_tools"])
    assert "__facade_probe__" in idx["agent_tools"]
    assert isinstance(idx["collisions"], list)


def test_no_cross_registry_drift():
    # The two registries use disjoint naming conventions on purpose; a name in
    # BOTH layers is a maintenance hazard this test guards against.
    assert detect_drift() == []


def test_catalog_ids_are_strings():
    for tid in catalog_tool_ids():
        assert isinstance(tid, str) and tid
