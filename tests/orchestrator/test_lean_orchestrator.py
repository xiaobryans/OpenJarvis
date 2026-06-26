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


def test_run_complex_parallel(monkeypatch):
    _ensure_current_time_registered()
    orch = LeanOrchestrator(model="mock")

    def fake_llm(system, user, **kw):
        if "COS/GM" in system:
            return (
                '{"estimate_seconds": 30, "rationale": "parallel test", "steps": ['
                '{"manager":"personal_life","tool":"current_time","args":{}},'
                '{"manager":"personal_life","tool":"current_time","args":{"timezone":"UTC"}}]}'
            )
        return "Compiled answer from parallel workers."

    monkeypatch.setattr(orch, "_llm", fake_llm)
    statuses = []
    orch._status = statuses.append

    res = orch.run_complex("do two things at once")
    assert res.error == ""
    assert res.tier == "complex"
    assert len(res.workers) == 2 and all(w.success for w in res.workers)
    assert any("parallel" in s.lower() for s in statuses)
    assert any("estimated" in s.lower() or "about 30s" in s.lower() for s in statuses)


def test_recovery_planning_failure_escalates(monkeypatch):
    orch = LeanOrchestrator(model="mock")
    monkeypatch.setattr(orch, "plan",
                        lambda r: (_ for _ in ()).throw(RuntimeError("planner down")))
    monkeypatch.setattr(orch, "_llm", lambda s, u, **k: "Direct answer, boss.")
    orch._status = lambda *_: None
    res = orch.run_standard("do something")
    assert res.escalated is True and res.answer.strip()  # never empty


def test_recovery_no_steps_direct_answer(monkeypatch):
    orch = LeanOrchestrator(model="mock")
    monkeypatch.setattr(orch, "_llm",
                        lambda s, u, **k: '{"steps":[]}' if "COS/GM" in s
                        else "Direct answer.")
    orch._status = lambda *_: None
    res = orch.run_standard("something with no tools")
    assert res.escalated is True and res.answer.strip()


def test_recovery_all_workers_rejected_escalates(monkeypatch):
    _ensure_current_time_registered()
    orch = LeanOrchestrator(model="mock")
    monkeypatch.setattr(
        orch, "_llm",
        lambda s, u, **k: (
            '{"steps":[{"manager":"personal_life","tool":"current_time","args":{}}]}'
            if "COS/GM" in s else "Explanation answer, boss."
        ),
    )
    monkeypatch.setattr(orch, "_run_tool",
                        staticmethod(lambda tool, args: (False, "boom")))
    orch._status = lambda *_: None
    res = orch.run_standard("x")
    assert res.escalated is True and res.answer.strip()
    assert res.workers and not any(w.approved for w in res.workers)


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


def test_quality_gate_review_logic():
    r = LeanOrchestrator._review
    assert r(True, "real useful content")[0] is True
    assert r(False, "boom")[0] is False
    assert r(True, "")[0] is False
    assert r(True, "(worker 'x' not available)")[0] is False
    assert r(True, "Notion is not configured. Add NOTION_API_KEY")[0] is False


def test_rejected_worker_retried_and_not_approved(monkeypatch):
    _ensure_current_time_registered()
    orch = LeanOrchestrator(model="mock")
    monkeypatch.setattr(
        orch, "_llm",
        lambda s, u, **k: (
            '{"steps":[{"manager":"personal_life","tool":"current_time","args":{}}]}'
            if "COS/GM" in s else "answer"
        ),
    )
    # Force the worker to always fail -> gate rejects -> retried once.
    monkeypatch.setattr(orch, "_run_tool",
                        staticmethod(lambda tool, args: (False, "boom")))
    orch._status = lambda *_: None
    res = orch.run_standard("x")
    w = res.workers[0]
    assert w.approved is False and w.retried is True
