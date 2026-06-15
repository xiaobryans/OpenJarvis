"""Targeted tests for the Mega Sprint 1 Mission Control foundation.

Covers:
  1. Mission / Task model creation and serialisation
  2. SpecialistRegistry integrity (all 12 agents, correct fields)
  3. SpecialistRegistry capability lookup
  4. MissionStore persist + retrieve (missions, tasks, events)
  5. MissionRouter: mission creation, task decomposition, agent assignment
  6. MissionRouter: events emitted and queryable
  7. MissionRouter: high-risk / privileged tasks marked awaiting_approval
  8. MissionRouter: no task is falsely completed
  9. EventBus: mission event types published
 10. Functional demo: full objective → mission → tasks → events
"""

from __future__ import annotations

import pytest

from openjarvis.core.events import EventType, get_event_bus, reset_event_bus
from openjarvis.mission.agent_registry import (
    SpecialistRegistry,
    _EXPECTED_AGENT_IDS,
)
from openjarvis.mission.models import (
    AgentStatus,
    Mission,
    MissionEvent,
    MissionStatus,
    RiskLevel,
    SpecialistAgentSpec,
    Task,
    TaskStatus,
)
from openjarvis.mission.router import MissionRouter, PLANNING_METHOD
from openjarvis.mission.store import MissionStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_specialist_registry() -> None:
    """Reset SpecialistRegistry between tests."""
    SpecialistRegistry.clear()
    reset_event_bus()


@pytest.fixture
def tmp_store(tmp_path):
    """In-memory (tmp_path) MissionStore isolated per test."""
    db = str(tmp_path / "test_missions.db")
    store = MissionStore(db_path=db)
    yield store
    store.close()


@pytest.fixture
def router(tmp_store):
    """MissionRouter backed by an isolated tmp store."""
    return MissionRouter(store=tmp_store, emit_to_bus=True)


# ---------------------------------------------------------------------------
# 1. Model creation
# ---------------------------------------------------------------------------


def test_mission_defaults():
    m = Mission(title="Test", objective="Do something")
    assert m.id
    assert len(m.id) == 16
    assert m.status == MissionStatus.QUEUED
    assert m.risk_level == RiskLevel.LOW
    assert m.owner == "Bryan"
    assert m.linked_task_ids == []
    assert m.linked_event_ids == []


def test_mission_to_dict():
    m = Mission(title="T", objective="O", owner="CLI")
    d = m.to_dict()
    assert d["title"] == "T"
    assert d["objective"] == "O"
    assert d["owner"] == "CLI"
    assert d["status"] == "queued"
    assert d["risk_level"] == "low"
    assert isinstance(d["linked_task_ids"], list)


def test_task_defaults():
    t = Task(mission_id="abc", title="Do it", assigned_agent_id="coding")
    assert t.id
    assert t.status == TaskStatus.PENDING
    assert t.risk_level == RiskLevel.LOW
    assert t.dependencies == []
    assert t.result == ""


def test_task_to_dict():
    t = Task(mission_id="m1", title="Build X", assigned_agent_id="coding")
    d = t.to_dict()
    assert d["mission_id"] == "m1"
    assert d["assigned_agent_id"] == "coding"
    assert d["status"] == "pending"


def test_mission_event_to_dict():
    e = MissionEvent(
        mission_id="m1",
        task_id="t1",
        agent_id="research",
        event_type="task_created",
        severity="info",
        message="Task created",
        payload={"key": "val"},
    )
    d = e.to_dict()
    assert d["event_type"] == "task_created"
    assert d["agent_id"] == "research"
    assert d["payload"]["key"] == "val"


# ---------------------------------------------------------------------------
# 2. SpecialistRegistry integrity
# ---------------------------------------------------------------------------


def test_specialist_registry_has_all_12_agents():
    agents = SpecialistRegistry.all()
    registered_ids = {a.agent_id for a in agents}
    assert registered_ids == _EXPECTED_AGENT_IDS, (
        f"Missing: {_EXPECTED_AGENT_IDS - registered_ids}, "
        f"Extra: {registered_ids - _EXPECTED_AGENT_IDS}"
    )


def test_specialist_registry_fields():
    for spec in SpecialistRegistry.all():
        assert spec.agent_id, f"agent_id empty for {spec}"
        assert spec.display_name, f"display_name empty for {spec.agent_id}"
        assert spec.role, f"role empty for {spec.agent_id}"
        assert isinstance(spec.capabilities, list), f"capabilities not list for {spec.agent_id}"
        assert len(spec.capabilities) >= 1, f"no capabilities for {spec.agent_id}"
        assert spec.permission_level in (
            "minimal", "standard", "elevated", "privileged"
        ), f"invalid permission_level for {spec.agent_id}: {spec.permission_level}"
        assert isinstance(spec.can_auto_execute_low_risk, bool)
        assert spec.status == AgentStatus.IDLE


def test_deployment_agent_always_requires_approval():
    spec = SpecialistRegistry.get("deployment")
    assert spec is not None
    assert spec.permission_level == "privileged"
    assert spec.can_auto_execute_low_risk is False
    assert spec.escalation_rules.get("always_require_approval") is True


def test_email_agent_always_requires_approval():
    spec = SpecialistRegistry.get("email")
    assert spec is not None
    assert spec.can_auto_execute_low_risk is False
    assert spec.escalation_rules.get("always_require_approval") is True


def test_security_risk_agent_no_auto_execute():
    spec = SpecialistRegistry.get("security_risk")
    assert spec is not None
    assert spec.can_auto_execute_low_risk is False


# ---------------------------------------------------------------------------
# 3. Capability lookup
# ---------------------------------------------------------------------------


def test_find_by_capability_research():
    agents = SpecialistRegistry.find_by_capability("research")
    ids = {a.agent_id for a in agents}
    assert "research" in ids


def test_find_by_capability_deploy():
    agents = SpecialistRegistry.find_by_capability("deploy")
    ids = {a.agent_id for a in agents}
    assert "deployment" in ids


def test_find_by_capability_nonexistent():
    agents = SpecialistRegistry.find_by_capability("xyzzy_nonexistent")
    assert agents == []


def test_specialist_to_dict():
    spec = SpecialistRegistry.get("coding")
    assert spec is not None
    d = spec.to_dict()
    assert d["agent_id"] == "coding"
    assert "code" in d["capabilities"]
    assert isinstance(d["allowed_tools"], list)


# ---------------------------------------------------------------------------
# 4. MissionStore persistence
# ---------------------------------------------------------------------------


def test_store_save_and_get_mission(tmp_store):
    m = Mission(title="Persist test", objective="Test persistence")
    tmp_store.save_mission(m)
    got = tmp_store.get_mission(m.id)
    assert got is not None
    assert got.id == m.id
    assert got.title == "Persist test"
    assert got.status == MissionStatus.QUEUED


def test_store_list_missions(tmp_store):
    m1 = Mission(title="M1", objective="Obj1")
    m2 = Mission(title="M2", objective="Obj2")
    tmp_store.save_mission(m1)
    tmp_store.save_mission(m2)
    missions = tmp_store.list_missions()
    ids = {m.id for m in missions}
    assert m1.id in ids
    assert m2.id in ids


def test_store_update_mission_status(tmp_store):
    m = Mission(title="T", objective="O")
    tmp_store.save_mission(m)
    tmp_store.update_mission_status(m.id, MissionStatus.RUNNING)
    got = tmp_store.get_mission(m.id)
    assert got.status == MissionStatus.RUNNING


def test_store_save_and_get_task(tmp_store):
    m = Mission(title="M", objective="O")
    tmp_store.save_mission(m)
    t = Task(
        mission_id=m.id,
        title="Task 1",
        description="Do something",
        assigned_agent_id="research",
        risk_level=RiskLevel.LOW,
    )
    tmp_store.save_task(t)
    got = tmp_store.get_task(t.id)
    assert got is not None
    assert got.mission_id == m.id
    assert got.assigned_agent_id == "research"
    assert got.risk_level == RiskLevel.LOW


def test_store_list_tasks(tmp_store):
    m = Mission(title="M", objective="O")
    tmp_store.save_mission(m)
    for i in range(3):
        t = Task(mission_id=m.id, title=f"Task {i}", priority=i + 1)
        tmp_store.save_task(t)
    tasks = tmp_store.list_tasks(m.id)
    assert len(tasks) == 3


def test_store_save_and_list_events(tmp_store):
    m = Mission(title="M", objective="O")
    tmp_store.save_mission(m)
    for et in ["mission_created", "task_created", "task_assigned"]:
        e = MissionEvent(
            mission_id=m.id,
            event_type=et,
            message=f"Test event: {et}",
        )
        tmp_store.save_event(e)
    events = tmp_store.list_events(m.id)
    assert len(events) == 3
    types = {e.event_type for e in events}
    assert "mission_created" in types
    assert "task_created" in types


def test_store_events_query_by_mission_id(tmp_store):
    m1 = Mission(title="M1", objective="O1")
    m2 = Mission(title="M2", objective="O2")
    tmp_store.save_mission(m1)
    tmp_store.save_mission(m2)
    e1 = MissionEvent(mission_id=m1.id, event_type="mission_created", message="m1")
    e2 = MissionEvent(mission_id=m2.id, event_type="mission_created", message="m2")
    tmp_store.save_event(e1)
    tmp_store.save_event(e2)
    events_m1 = tmp_store.list_events(m1.id)
    events_m2 = tmp_store.list_events(m2.id)
    assert len(events_m1) == 1
    assert events_m1[0].message == "m1"
    assert len(events_m2) == 1
    assert events_m2[0].message == "m2"


# ---------------------------------------------------------------------------
# 5. MissionRouter: mission creation + task decomposition
# ---------------------------------------------------------------------------


def test_router_creates_mission(router, tmp_store):
    plan = router.create_mission("Research the current app state")
    assert plan.mission.id
    assert plan.mission.status in (MissionStatus.RUNNING, MissionStatus.AWAITING_APPROVAL)
    assert len(plan.tasks) >= 1
    # Mission must be persisted
    stored = tmp_store.get_mission(plan.mission.id)
    assert stored is not None
    assert stored.id == plan.mission.id


def test_router_planning_method_tagged(router):
    plan = router.create_mission("Analyze the codebase")
    assert plan.planning_method == PLANNING_METHOD


def test_router_assigns_tasks_to_agents(router):
    plan = router.create_mission("Research the current app state and prepare a safe coding plan")
    agent_ids = {t.assigned_agent_id for t in plan.tasks}
    # Both research and coding keywords present → research + coding agents expected
    assert "research" in agent_ids
    assert "coding" in agent_ids


def test_router_research_keyword_assigns_research_agent(router):
    plan = router.create_mission("Research AI frameworks")
    agent_ids = {t.assigned_agent_id for t in plan.tasks}
    assert "research" in agent_ids


def test_router_coding_keyword_gets_architect_and_qa(router):
    plan = router.create_mission("Implement a new feature")
    agent_ids = {t.assigned_agent_id for t in plan.tasks}
    # coding → architect auto-prepended, qa auto-appended
    assert "coding" in agent_ids
    assert "architect" in agent_ids
    assert "qa" in agent_ids or "testing_bug" in agent_ids


def test_router_always_appends_docs_report(router):
    plan = router.create_mission("Research something simple")
    agent_ids = {t.assigned_agent_id for t in plan.tasks}
    assert "docs_report" in agent_ids


def test_router_fallback_to_research_on_no_keywords(router):
    plan = router.create_mission("xyzzy gobbledegook with no recognizable intent")
    agent_ids = {t.assigned_agent_id for t in plan.tasks}
    assert "research" in agent_ids


def test_router_tasks_persisted(router, tmp_store):
    plan = router.create_mission("Build a new API endpoint")
    stored_tasks = tmp_store.list_tasks(plan.mission.id)
    assert len(stored_tasks) == len(plan.tasks)
    stored_ids = {t.id for t in stored_tasks}
    plan_ids = {t.id for t in plan.tasks}
    assert stored_ids == plan_ids


def test_router_mission_linked_task_ids(router):
    plan = router.create_mission("Analyze and implement feature")
    task_ids_in_mission = set(plan.mission.linked_task_ids)
    task_ids_from_tasks = {t.id for t in plan.tasks}
    assert task_ids_in_mission == task_ids_from_tasks


# ---------------------------------------------------------------------------
# 6. Events emitted and queryable
# ---------------------------------------------------------------------------


def test_router_emits_mission_created_event(router):
    plan = router.create_mission("Research the current app state")
    types = {e.event_type for e in plan.events}
    assert "mission_created" in types


def test_router_emits_task_created_events(router):
    plan = router.create_mission("Research the current app state")
    types = [e.event_type for e in plan.events]
    assert types.count("task_created") >= 1


def test_router_emits_mission_status_changed_event(router):
    plan = router.create_mission("Research the current app state")
    types = {e.event_type for e in plan.events}
    assert "mission_status_changed" in types


def test_router_events_persisted_and_queryable(router, tmp_store):
    plan = router.create_mission("Research the current app state")
    stored_events = tmp_store.list_events(plan.mission.id)
    assert len(stored_events) >= 3  # at minimum: mission_created, task_created, mission_status_changed
    stored_types = {e.event_type for e in stored_events}
    assert "mission_created" in stored_types
    assert "mission_status_changed" in stored_types


def test_router_events_linked_to_mission(router):
    plan = router.create_mission("Build something")
    event_ids_in_mission = set(plan.mission.linked_event_ids)
    event_ids_from_events = {e.event_id for e in plan.events}
    assert event_ids_in_mission == event_ids_from_events


def test_router_task_events_have_task_id(router):
    plan = router.create_mission("Implement a feature")
    task_events = [
        e for e in plan.events if e.event_type in ("task_created", "task_assigned", "task_awaiting_approval")
    ]
    assert len(task_events) >= 1
    for e in task_events:
        assert e.task_id is not None, f"task_id missing on event {e.event_type}"


# ---------------------------------------------------------------------------
# 7. Approval / risk gates
# ---------------------------------------------------------------------------


def test_router_deploy_task_requires_approval(router):
    plan = router.create_mission("Deploy the application to production")
    deploy_tasks = [t for t in plan.tasks if t.assigned_agent_id == "deployment"]
    assert len(deploy_tasks) >= 1, "Expected at least one deployment task"
    for t in deploy_tasks:
        assert t.status == TaskStatus.AWAITING_APPROVAL, (
            f"Deployment task {t.id} should be awaiting_approval, got {t.status}"
        )
        assert t.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_router_email_task_requires_approval(router):
    plan = router.create_mission("Send email notification to the team")
    email_tasks = [t for t in plan.tasks if t.assigned_agent_id == "email"]
    assert len(email_tasks) >= 1
    for t in email_tasks:
        assert t.status == TaskStatus.AWAITING_APPROVAL


def test_router_security_task_requires_approval(router):
    plan = router.create_mission("Run a security audit of the system")
    security_tasks = [t for t in plan.tasks if t.assigned_agent_id == "security_risk"]
    assert len(security_tasks) >= 1
    for t in security_tasks:
        assert t.status == TaskStatus.AWAITING_APPROVAL


def test_router_critical_risk_tasks_require_approval(router):
    plan = router.create_mission("Release the new version")
    critical_tasks = [t for t in plan.tasks if t.risk_level == RiskLevel.CRITICAL]
    for t in critical_tasks:
        assert t.status == TaskStatus.AWAITING_APPROVAL, (
            f"CRITICAL task {t.id} must be awaiting_approval"
        )


def test_router_low_risk_research_not_blocked(router):
    plan = router.create_mission("Research the current app state")
    research_tasks = [t for t in plan.tasks if t.assigned_agent_id == "research"]
    assert len(research_tasks) >= 1
    for t in research_tasks:
        assert t.status == TaskStatus.ASSIGNED, (
            f"Research task {t.id} should be ASSIGNED, not {t.status}"
        )


def test_router_mission_awaiting_approval_when_risky_tasks_present(router):
    plan = router.create_mission("Deploy the system")
    assert plan.mission.status == MissionStatus.AWAITING_APPROVAL


def test_router_approval_events_emitted_for_risky_tasks(router):
    plan = router.create_mission("Deploy the application")
    approval_events = [e for e in plan.events if e.event_type == "task_awaiting_approval"]
    assert len(approval_events) >= 1
    for e in approval_events:
        assert e.severity == "warning"


# ---------------------------------------------------------------------------
# 8. No fake completion
# ---------------------------------------------------------------------------


def test_router_no_task_falsely_completed(router):
    """No task should ever be marked completed by the router."""
    objectives = [
        "Research the current app state and prepare a safe coding plan",
        "Deploy the application to production",
        "Build a new feature",
        "Send email to the team",
        "Analyze security vulnerabilities",
    ]
    for obj in objectives:
        plan = router.create_mission(obj)
        for t in plan.tasks:
            assert t.status != TaskStatus.COMPLETED, (
                f"Task '{t.title}' (agent={t.assigned_agent_id}) "
                f"was falsely marked COMPLETED by the router"
            )


def test_router_mission_never_marked_completed_on_creation(router):
    plan = router.create_mission("Research and implement everything")
    assert plan.mission.status != MissionStatus.COMPLETED


# ---------------------------------------------------------------------------
# 9. EventBus integration
# ---------------------------------------------------------------------------


def test_event_bus_receives_mission_events(router):
    bus = get_event_bus(record_history=True)
    router._emit_to_bus = True
    plan = router.create_mission("Research the current app state")
    history = bus.history
    event_types_on_bus = {e.event_type for e in history}
    assert EventType.MISSION_CREATED in event_types_on_bus
    assert EventType.TASK_CREATED in event_types_on_bus
    assert EventType.MISSION_STATUS_CHANGED in event_types_on_bus


def test_new_event_type_values_exist():
    assert EventType.MISSION_CREATED == "mission_created"
    assert EventType.MISSION_STATUS_CHANGED == "mission_status_changed"
    assert EventType.TASK_CREATED == "task_created"
    assert EventType.TASK_ASSIGNED == "task_assigned"
    assert EventType.TASK_AWAITING_APPROVAL == "task_awaiting_approval"
    assert EventType.TASK_STATUS_CHANGED == "task_status_changed"


# ---------------------------------------------------------------------------
# 10. Full functional demo
# ---------------------------------------------------------------------------


def test_functional_demo_full_objective(router, tmp_store, capsys):
    """Functional validation: Research app state + prepare coding plan.

    Mirrors the ACCEPT criteria from the sprint spec.
    """
    objective = "Research the current app state and prepare a safe coding plan."

    plan = router.create_mission(objective, owner="Bryan", title="Sprint 1 Foundation Demo")

    mission = plan.mission
    tasks = plan.tasks
    events = plan.events

    # Mission created
    assert mission.id
    assert mission.owner == "Bryan"
    assert mission.status in (MissionStatus.RUNNING, MissionStatus.AWAITING_APPROVAL)

    # Tasks created and assigned
    assert len(tasks) >= 2
    agent_ids = {t.assigned_agent_id for t in tasks}
    assert "research" in agent_ids
    assert "coding" in agent_ids

    # Events emitted
    event_types = {e.event_type for e in events}
    assert "mission_created" in event_types
    assert "task_created" in event_types
    assert "mission_status_changed" in event_types

    # Events queryable from store
    stored_events = tmp_store.list_events(mission.id)
    assert len(stored_events) == len(events)

    # No task is falsely completed
    for t in tasks:
        assert t.status != TaskStatus.COMPLETED

    # Mission status correct
    assert mission.status != MissionStatus.COMPLETED
    assert mission.status != MissionStatus.FAILED

    # High-risk tasks not auto-executed
    for t in tasks:
        if t.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            assert t.status == TaskStatus.AWAITING_APPROVAL

    # Print demo output for validation report
    print(f"\n=== FUNCTIONAL DEMO OUTPUT ===")
    print(f"Mission ID    : {mission.id}")
    print(f"Title         : {mission.title}")
    print(f"Owner         : {mission.owner}")
    print(f"Status        : {mission.status.value}")
    print(f"Risk Level    : {mission.risk_level.value}")
    print(f"Planning      : {plan.planning_method}")
    print(f"Tasks ({len(tasks)}):")
    for t in tasks:
        print(f"  [{t.status.value:20s}] {t.assigned_agent_id:15s} | {t.title}")
    print(f"Events ({len(events)}):")
    for e in events:
        print(f"  [{e.severity:7s}] {e.event_type:30s} | {e.message[:60]}")
    print(f"==============================")

    captured = capsys.readouterr()
    assert "Mission ID" in captured.out
    assert mission.id in captured.out
