"""Tests for the lean hierarchy (Stage 3). CI-safe: the cloud LLM is mocked;
worker execution uses a real registered tool (current_time)."""

from openjarvis.orchestrator.lean import LeanOrchestrator, MANAGERS


REQUIRED = {
    "research", "code_build", "communications", "finance", "personal_life",
    "security", "data", "integration", "planning", "quality", "learning",
    "automation",
}


def test_twelve_required_managers_present():
    assert REQUIRED.issubset(set(MANAGERS)), MANAGERS.keys()


def _ensure_current_time_registered():
    # The shared autouse _clean_registries fixture empties ToolRegistry; re-add
    # the real current_time tool so the worker executes for real in-test.
    from openjarvis.core.registry import ToolRegistry
    from openjarvis.tools.datetime_tool import CurrentDateTimeTool

    if "current_time" not in ToolRegistry.keys():
        ToolRegistry.register("current_time")(CurrentDateTimeTool)


def test_run_standard_offline_flow(monkeypatch):
    _ensure_current_time_registered()
    orch = LeanOrchestrator(model="mock")

    def fake_llm(system, user, **kw):
        if "COS/GM" in system:  # planning call
            return (
                '{"estimate_seconds": 5, "rationale": "test plan", '
                '"steps": [{"manager": "personal_life", "tool": "current_time", "args": {}}]}'
            )
        return "It is currently the time reported by the worker."

    monkeypatch.setattr(orch, "_llm", fake_llm)
    statuses = []
    orch._status = statuses.append

    res = orch.run_standard("what time is it")
    assert res.error == ""
    assert res.workers and res.workers[0].tool == "current_time"
    assert res.workers[0].success  # real tool executed
    assert res.answer
    assert res.managers_used == ["personal_life"]
    # live status: immediate ack + completion
    assert any("On it" in s for s in statuses)
    assert any("Done" in s for s in statuses)


def test_plan_rejects_invalid_steps(monkeypatch):
    orch = LeanOrchestrator(model="mock")
    monkeypatch.setattr(
        orch, "_llm",
        lambda s, u, **k: '{"steps":[{"manager":"nope","tool":"bad"},'
                          '{"manager":"research","tool":"not_a_tool"}]}',
    )
    plan = orch.plan("x")
    assert plan["steps"] == []  # both invalid steps dropped


def test_run_tool_unknown_is_graceful():
    ok, content = LeanOrchestrator._run_tool("does_not_exist", {})
    assert ok is False and "not available" in content
