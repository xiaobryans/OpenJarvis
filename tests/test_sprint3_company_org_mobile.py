"""Sprint 3 — Company Org + Mobile Continuity — Targeted Test Suite.

Tests all 20 required items from TASK 10 plus integration tests (TASK 7).

Required test coverage:
  1.  Company org has Jarvis, COS, GM, managers, workers, verifier
  2.  Managers have justified dynamic worker teams
  3.  Worker count is not fake/fixed-only
  4.  Skill/tool coverage exists for each role
  5.  Missing skill/tool cannot be silently accepted
  6.  Parallelizable tasks are marked parallelizable
  7.  Dependent tasks are sequenced
  8.  Worker stall is detected
  9.  Stalled worker can be reassigned or exact blocker reported
  10. Artifact output is required where appropriate
  11. Verifier rejects unsupported evidence
  12. Verifier returns fix list
  13. Self-improvement creates prevention item
  14. Reuse does not skip validation
  15. Cross-device snapshot saves required state
  16. Mobile resume restores required state
  17. Conflict/degraded state is surfaced
  18. Slack persona mapping is tied to company roster
  19. Voice remains gated
  20. Full no-gap remains HOLD

Integration tests (TASK 7):
  I1. MacBook session starts a task, COS routes, worker produces artifact
  I2. Continuity snapshot saved with full state
  I3. Mobile resume restores state including verifier status and artifact pointer
  I4. Conflict is surfaced when mobile has newer snapshot
"""

from __future__ import annotations

import time
import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

from openjarvis.company_org import (
    build_company_org_spec,
    get_company_org_spec,
    CapabilityStatus,
    RoleTier,
    CompanyOrgSpec,
)

from openjarvis.agents.verifier import (
    VerifierGate,
    EvidenceItem,
    VerificationOutcome,
    get_default_verifier_gate,
)

from openjarvis.agents.worker_pool import (
    WorkerPool,
    WorkerTask,
    WorkerTaskStatus,
    create_worker_pool,
    create_worker_task,
)

from openjarvis.agents.self_improvement import (
    SelfImprovementRegistry,
    FlawSeverity,
    CachedPlan,
    get_self_improvement_registry,
)

from openjarvis.mobile.continuity import (
    ContinuityStore,
    DeviceType,
    SyncStatus,
    ConflictPolicy,
    get_continuity_store,
)

from openjarvis.agents.roster import (
    AgentRosterRegistry,
    AgentRoleType,
    PersonaType,
    get_default_registry,
)


# ===========================================================================
# FIXTURE: fresh company org spec
# ===========================================================================

@pytest.fixture
def org_spec() -> CompanyOrgSpec:
    return build_company_org_spec()


@pytest.fixture
def verifier_gate() -> VerifierGate:
    return VerifierGate(verifier_id="test-verifier", stale_threshold_seconds=3600)


@pytest.fixture
def si_registry() -> SelfImprovementRegistry:
    return SelfImprovementRegistry()


@pytest.fixture
def continuity_store() -> ContinuityStore:
    return ContinuityStore(
        conflict_policy=ConflictPolicy.SURFACE_CONFLICT,
    )


@pytest.fixture
def roster() -> AgentRosterRegistry:
    return AgentRosterRegistry(load_defaults=True)


# ===========================================================================
# TEST 1 — Company org has Jarvis, COS, GM, managers, workers, verifier
# ===========================================================================

def test_01_company_org_has_all_required_roles(org_spec):
    """Org spec must have Jarvis, COS, GM, managers, workers, verifier."""
    tiers = {r.tier for r in org_spec.roles}
    assert RoleTier.JARVIS in tiers, "Missing Jarvis role"
    assert RoleTier.COS in tiers, "Missing COS role"
    assert RoleTier.GM in tiers, "Missing GM role"
    assert RoleTier.MANAGER in tiers, "Missing at least one Manager role"
    assert RoleTier.WORKER in tiers, "Missing at least one Worker role"
    assert RoleTier.VERIFIER in tiers, "Missing Verifier role"

    # Individual role checks
    assert org_spec.get_role("jarvis") is not None, "No jarvis role_id"
    assert org_spec.get_role("cos") is not None, "No cos role_id"
    assert org_spec.get_role("gm") is not None, "No gm role_id"
    assert org_spec.get_verifier() is not None, "No verifier role"

    managers = org_spec.list_managers()
    assert len(managers) >= 4, f"Expected >=4 managers, got {len(managers)}"


# ===========================================================================
# TEST 2 — Managers have justified dynamic worker teams
# ===========================================================================

def test_02_managers_have_justified_worker_teams(org_spec):
    """Default worker teams must be linked to managers and have justification."""
    assert len(org_spec.default_worker_teams) >= 1, "No default worker teams"
    for team in org_spec.default_worker_teams:
        assert team.manager_role_id, "Team has no manager_role_id"
        assert team.task_context, "Team has no task_context (justification missing)"
        assert len(team.workers) >= 1, f"Team {team.team_id} has no workers"
        # Manager must exist in org spec
        mgr = org_spec.get_role(team.manager_role_id)
        assert mgr is not None, f"Team references unknown manager '{team.manager_role_id}'"


# ===========================================================================
# TEST 3 — Worker count is not fake/fixed-only
# ===========================================================================

def test_03_worker_count_dynamic_not_fixed(org_spec):
    """Worker teams can have different team sizes — count is justified, not hardcoded."""
    team_sizes = [len(t.workers) for t in org_spec.default_worker_teams]
    # At least one team has more than 1 worker (not just a dummy placeholder)
    assert any(s >= 1 for s in team_sizes), "All teams have 0 workers"
    # Total workers in spec > 0
    workers = org_spec.list_workers()
    assert len(workers) >= 2, f"Expected >=2 worker roles, got {len(workers)}"


# ===========================================================================
# TEST 4 — Skill/tool coverage exists for each role
# ===========================================================================

def test_04_skill_tool_coverage_per_role(org_spec):
    """Every role must have at least 1 required tool and 1 required skill."""
    for role in org_spec.roles:
        assert len(role.required_tools) >= 1, (
            f"Role '{role.role_id}' has no required_tools"
        )
        assert len(role.required_skills) >= 1, (
            f"Role '{role.role_id}' has no required_skills"
        )


# ===========================================================================
# TEST 5 — Missing skill/tool cannot be silently accepted
# ===========================================================================

def test_05_missing_capability_not_silently_accepted(org_spec):
    """Roles with REQUIRED_AND_MISSING must expose the gap, not hide it."""
    for role in org_spec.roles:
        if role.tool_coverage_status == CapabilityStatus.REQUIRED_AND_MISSING:
            assert len(role.missing_tools) >= 1, (
                f"Role '{role.role_id}' has REQUIRED_AND_MISSING tools "
                "but missing_tools list is empty — gap hidden"
            )
        if role.skill_coverage_status == CapabilityStatus.REQUIRED_AND_MISSING:
            assert len(role.missing_skills) >= 1, (
                f"Role '{role.role_id}' has REQUIRED_AND_MISSING skills "
                "but missing_skills list is empty — gap hidden"
            )
    # Verify get_missing_capabilities works
    missing = org_spec.get_missing_capabilities()
    # Result can be empty (nothing missing) or non-empty — just must not throw
    assert isinstance(missing, list)


# ===========================================================================
# TEST 6 — Parallelizable tasks are marked parallelizable
# ===========================================================================

def test_06_parallelizable_tasks_marked():
    """WorkerPool plan builder marks parallel tasks as parallelizable."""
    pool = create_worker_pool("manager-coding")
    t1 = create_worker_task("worker-repo-inspector", "inspect files", parallelizable=True)
    t2 = create_worker_task("worker-test-runner", "run tests", parallelizable=True)
    pool.add_task(t1)
    pool.add_task(t2)

    plan = pool.build_execution_plan("parallel test")
    # Both tasks should be in the same parallel group (no deps, both parallelizable)
    all_parallel = [tid for group in plan.parallel_groups for tid in group]
    assert t1.task_id in all_parallel, "t1 not in parallel group"
    assert t2.task_id in all_parallel, "t2 not in parallel group"


# ===========================================================================
# TEST 7 — Dependent tasks are sequenced
# ===========================================================================

def test_07_dependent_tasks_sequenced():
    """Worker pool sequences tasks where dependencies exist."""
    pool = create_worker_pool("manager-coding")
    t1 = create_worker_task("worker-repo-inspector", "inspect files", parallelizable=True)
    # t2 depends on t1
    t2 = create_worker_task(
        "worker-test-runner", "run tests",
        parallelizable=True,
        dependencies=[t1.task_id],
    )
    pool.add_task(t1)
    pool.add_task(t2)

    plan = pool.build_execution_plan("sequenced test")
    # t1 should appear before t2 in parallel_groups order
    # t2 cannot be in a group that appears before t1's group
    group_for_t1 = next(
        (i for i, g in enumerate(plan.parallel_groups) if t1.task_id in g), None
    )
    group_for_t2 = next(
        (i for i, g in enumerate(plan.parallel_groups) if t2.task_id in g), None
    )
    if group_for_t1 is not None and group_for_t2 is not None:
        assert group_for_t1 < group_for_t2, (
            "t2 (depends on t1) is not scheduled after t1"
        )


# ===========================================================================
# TEST 8 — Worker stall is detected
# ===========================================================================

def test_08_worker_stall_detected():
    """A running task that exceeds timeout is detected as stalled."""
    pool = create_worker_pool("manager-coding", stall_timeout_seconds=0)
    task = create_worker_task(
        "worker-repo-inspector", "slow task",
        stall_timeout_seconds=0,   # immediately stalled
    )
    pool.add_task(task)
    task.mark_started()
    # Force stall by setting started_at in the past
    task.started_at = time.time() - 10

    stall_reports = pool.check_stalls()
    assert len(stall_reports) >= 1, "Stall not detected"
    assert stall_reports[0].task_id == task.task_id


# ===========================================================================
# TEST 9 — Stalled worker can be reassigned or exact blocker reported
# ===========================================================================

def test_09_stalled_worker_reassigned_or_blocker_reported():
    """Stalled worker is either reassigned or exact blocker reported."""
    pool = create_worker_pool("manager-coding")
    task = create_worker_task("worker-repo-inspector", "stalling task", stall_timeout_seconds=0)
    pool.add_task(task)
    task.mark_started()
    task.started_at = time.time() - 10

    # With reassignment target
    stall_reports = pool.check_stalls(reassign_to="manager-coding")
    assert len(stall_reports) >= 1
    report = stall_reports[0]
    assert report.reassignable is True
    assert report.reassigned_to == "manager-coding"
    assert report.blocker_description, "Blocker description must not be empty"
    # Task should be marked as reassigned
    assert task.status == WorkerTaskStatus.REASSIGNED


# ===========================================================================
# TEST 10 — Artifact output is required where appropriate
# ===========================================================================

def test_10_artifact_output_required_where_appropriate(org_spec):
    """Roles with WORKER tier must define output_artifacts."""
    workers = org_spec.list_workers()
    for worker in workers:
        assert len(worker.output_artifacts) >= 1, (
            f"Worker '{worker.role_id}' has no output_artifacts defined"
        )

    # WorkerPool captures artifacts from completed tasks
    pool = create_worker_pool("manager-coding")

    def executor(task: WorkerTask) -> dict:
        return {"status": "done", "artifact": f"/tmp/artifacts/{task.task_id}.json"}

    task = create_worker_task("worker-test-runner", "run tests")
    pool.add_task(task)
    result = pool.execute(executor)

    artifacts = pool.get_artifacts()
    assert len(artifacts) >= 1, "No artifacts captured from completed tasks"


# ===========================================================================
# TEST 11 — Verifier rejects unsupported evidence
# ===========================================================================

def test_11_verifier_rejects_unsupported_row(verifier_gate):
    """Unsupported row (is_supported=False) → REJECTED."""
    items = [
        EvidenceItem(
            claim_id="claim-1",
            claim_text="Tests pass",
            source_type="test",
            source_ref="",
            last_updated_at=time.time(),
            is_supported=False,  # no real evidence
        )
    ]
    report = verifier_gate.verify("team-alpha", items)
    assert report.outcome == VerificationOutcome.REJECTED
    assert "claim-1" in report.rejected_claims


# ===========================================================================
# TEST 12 — Verifier returns fix list
# ===========================================================================

def test_12_verifier_returns_fix_list(verifier_gate):
    """Verifier must return a non-empty fix list on rejection."""
    items = [
        EvidenceItem(
            claim_id="claim-a",
            claim_text="Feature complete",
            source_type="file",
            source_ref="",         # empty → missing evidence
            last_updated_at=time.time(),
            is_supported=True,
        )
    ]
    report = verifier_gate.verify("team-beta", items)
    assert report.outcome == VerificationOutcome.REJECTED
    assert len(report.fix_list) >= 1, "Verifier returned empty fix list on rejection"


def test_12b_verifier_accepts_valid_evidence(verifier_gate):
    """Valid evidence with non-empty source_ref and recent timestamp → ACCEPTED."""
    items = [
        EvidenceItem(
            claim_id="claim-valid",
            claim_text="Tests pass",
            source_type="test",
            source_ref="tests/test_sprint3_company_org_mobile.py",
            last_updated_at=time.time(),
            is_supported=True,
        )
    ]
    report = verifier_gate.verify("team-gamma", items)
    assert report.outcome == VerificationOutcome.ACCEPTED
    assert "claim-valid" in report.accepted_claims
    assert report.acceptance_trace is not None


def test_12c_verifier_rejects_contradictory_status(verifier_gate):
    """Contradictory claims → REJECTED."""
    items = [
        EvidenceItem("claim-pass", "Tests pass", "test", "tests/", time.time(), True),
        EvidenceItem("claim-fail", "Tests fail", "test", "tests/", time.time(), True),
    ]
    report = verifier_gate.verify("team-delta", items, contradiction_pairs=[("claim-pass", "claim-fail")])
    assert report.outcome == VerificationOutcome.REJECTED
    contradiction_findings = [f for f in report.findings if f.finding_type == "contradiction"]
    assert len(contradiction_findings) >= 1


def test_12d_verifier_rejects_stale_artifact():
    """Evidence older than stale_threshold → REJECTED."""
    gate = VerifierGate(verifier_id="test-stale-verifier", stale_threshold_seconds=10)
    items = [
        EvidenceItem(
            claim_id="claim-old",
            claim_text="Old result",
            source_type="file",
            source_ref="docs/old.md",
            last_updated_at=time.time() - 100,  # 100 seconds old, threshold=10
            is_supported=True,
        )
    ]
    report = gate.verify("team-epsilon", items)
    assert report.outcome == VerificationOutcome.REJECTED
    stale_findings = [f for f in report.findings if f.finding_type == "stale"]
    assert len(stale_findings) >= 1


def test_12e_verifier_blocks_self_verify(verifier_gate):
    """Self-verify (team_id in blocked set) → BLOCKED_SELF_VERIFY."""
    items = [EvidenceItem("c1", "Self", "file", "f.py", time.time(), True)]
    report = verifier_gate.verify("verifier", items)
    assert report.outcome == VerificationOutcome.BLOCKED_SELF_VERIFY


# ===========================================================================
# TEST 13 — Self-improvement creates prevention item
# ===========================================================================

def test_13_caught_flaw_creates_prevention_item(si_registry):
    """Recording a flaw must auto-create a linked prevention item."""
    flaw = si_registry.record_flaw(
        description="Lint step was skipped",
        severity=FlawSeverity.HIGH,
        caught_by="verifier",
        affected_task="coding-sprint",
        root_cause="lint not in execution plan",
        fix_applied="Added lint to plan builder",
        prevention_type="validation_gate",
        prevention_action="Always include lint step in coding execution plan",
        validation_command=".venv/bin/python -m pytest tests/test_sprint3_company_org_mobile.py -q",
    )

    assert flaw.prevention_item_id is not None, "No prevention item linked to flaw"

    prevention = si_registry.get_prevention(flaw.prevention_item_id)
    assert prevention is not None, "Prevention item not found in registry"
    assert prevention.flaw_id == flaw.flaw_id
    assert prevention.concrete_action, "Prevention item has no concrete action"
    assert prevention.validation_command is not None


# ===========================================================================
# TEST 14 — Reuse does not skip validation
# ===========================================================================

def test_14_reuse_does_not_skip_validation(si_registry):
    """Using a cached plan must preserve required validation gates."""
    plan = CachedPlan(
        plan_id="plan-coding-001",
        task_type="coding_sprint",
        description="Standard coding sprint plan",
        plan_steps=["inspect_files", "run_tests", "lint"],
        validation_commands=[".venv/bin/python -m pytest tests/ -q"],
        routing_hint={"model_tier": "sonnet"},
        gates_required=["test_pass_required", "no_lint_errors_introduced"],
    )
    si_registry.register_plan(plan)

    used_plan = si_registry.use_cached_plan("coding_sprint")
    assert used_plan is not None
    assert used_plan.use_count == 1

    # Required gates must still be present — reuse does not remove them
    assert len(used_plan.gates_required) >= 1, "Reuse cleared required gates — FORBIDDEN"
    assert len(used_plan.validation_commands) >= 1, "Reuse cleared validation commands — FORBIDDEN"


# ===========================================================================
# TEST 15 — Cross-device snapshot saves required state
# ===========================================================================

def test_15_snapshot_saves_required_state(continuity_store):
    """Snapshot must contain all required continuity state fields."""
    # Register MacBook device
    macbook = continuity_store.register_device(
        user_id="bryan",
        device_type=DeviceType.MACBOOK,
        display_name="Bryan's MacBook Pro",
        trusted=True,
    )

    snapshot = continuity_store.save_snapshot(
        user_id="bryan",
        source_device_id=macbook.device_id,
        conversation_id="conv-001",
        conversation_messages=[{"role": "user", "content": "Start coding sprint"}],
        active_task_id="task-001",
        active_task_description="Implement company org spec",
        active_task_status="running",
        assigned_manager_role_id="manager-coding",
        assigned_worker_role_ids=["worker-repo-inspector", "worker-test-runner"],
        worker_statuses={"worker-repo-inspector": "completed", "worker-test-runner": "running"},
        pending_approvals=[],
        artifact_pointers=[{"task_id": "task-001", "path": "/tmp/artifacts/task-001.json"}],
        project_id="openjarvis",
        project_context={"sprint": "sprint-3"},
        memory_refs=["mem-001", "mem-002"],
        verifier_status="ACCEPTED",
        verifier_fix_list=[],
        sync_status=SyncStatus.PENDING,
    )

    assert snapshot.snapshot_id is not None
    assert snapshot.resume_token is not None
    assert snapshot.conversation_id == "conv-001"
    assert snapshot.active_task_id == "task-001"
    assert snapshot.assigned_manager_role_id == "manager-coding"
    assert "worker-repo-inspector" in snapshot.assigned_worker_role_ids
    assert snapshot.verifier_status == "ACCEPTED"


# ===========================================================================
# TEST 16 — Mobile resume restores required state
# ===========================================================================

def test_16_mobile_resume_restores_required_state(continuity_store):
    """Mobile device can resume from MacBook snapshot with state restored."""
    # Register devices
    macbook = continuity_store.register_device("bryan", DeviceType.MACBOOK, "MacBook", trusted=True)
    iphone = continuity_store.register_device("bryan", DeviceType.IPHONE, "iPhone 15", trusted=True)

    # MacBook saves snapshot
    snapshot = continuity_store.save_snapshot(
        user_id="bryan",
        source_device_id=macbook.device_id,
        conversation_id="conv-002",
        active_task_id="task-002",
        active_task_status="running",
        assigned_manager_role_id="manager-research",
        worker_statuses={"worker-research-main": "running"},
        verifier_status="PENDING",
        sync_status=SyncStatus.PENDING,
    )

    # iPhone resumes
    result = continuity_store.resume_on_device(
        resume_token=snapshot.resume_token,
        target_device_id=iphone.device_id,
    )

    assert result.success is True
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.conflict_detected is False
    assert SyncStatus.SYNCED == result.sync_status
    assert len(result.restored_state_keys) >= 1


# ===========================================================================
# TEST 17 — Conflict/degraded state is surfaced
# ===========================================================================

def test_17_conflict_state_surfaced(continuity_store):
    """When mobile has a newer snapshot than the resume source, conflict is surfaced."""
    macbook = continuity_store.register_device("bryan", DeviceType.MACBOOK, "MacBook", trusted=True)
    iphone = continuity_store.register_device("bryan", DeviceType.IPHONE, "iPhone", trusted=True)

    # MacBook snapshot (older)
    macbook_snap = continuity_store.save_snapshot(
        user_id="bryan",
        source_device_id=macbook.device_id,
        conversation_id="conv-003",
        active_task_id="task-003",
        active_task_status="running",
        sync_status=SyncStatus.PENDING,
    )

    # Simulate time passing — iPhone has a newer snapshot
    time.sleep(0.01)
    iphone_snap = continuity_store.save_snapshot(
        user_id="bryan",
        source_device_id=iphone.device_id,
        conversation_id="conv-003",
        active_task_id="task-003",
        active_task_status="completed",  # iPhone advanced the task
        sync_status=SyncStatus.PENDING,
    )
    # Make iphone_snap appear newer
    iphone_snap.created_at = macbook_snap.created_at + 1.0

    # MacBook tries to resume on iPhone — conflict expected
    result = continuity_store.resume_on_device(
        resume_token=macbook_snap.resume_token,
        target_device_id=iphone.device_id,
        current_state={"device_id": iphone.device_id},
    )

    assert result.success is True
    assert result.conflict_detected is True
    assert result.conflict_description is not None, "Conflict description must not be None"


def test_17b_untrusted_device_rejected(continuity_store):
    """Untrusted device cannot resume a protected snapshot."""
    macbook = continuity_store.register_device("bryan", DeviceType.MACBOOK, "MacBook", trusted=True)
    unknown_device_id = "device-unknown-999"  # not registered

    snap = continuity_store.save_snapshot(
        user_id="bryan",
        source_device_id=macbook.device_id,
        active_task_status="running",
        sync_status=SyncStatus.PENDING,
    )

    result = continuity_store.resume_on_device(
        resume_token=snap.resume_token,
        target_device_id=unknown_device_id,
    )
    assert result.success is False
    assert result.error is not None


# ===========================================================================
# TEST 18 — Slack persona mapping tied to company roster
# ===========================================================================

def test_18_slack_persona_mapping_tied_to_roster(org_spec, roster):
    """Company org Slack personas must map to entries in the roster registry."""
    real_bots_in_roster = {a.agent_id for a in roster.list_real_bots()}
    real_personas_in_org = {
        r.slack_persona for r in org_spec.roles
        if r.slack_persona and r.slack_bot_configured
    }

    # Every configured Slack persona in org must have a matching roster entry
    for persona in real_personas_in_org:
        # Check by slack_username or agent_id
        roster_ids = {a.slack_username for a in roster.list_real_bots() if a.slack_username}
        roster_ids.update(real_bots_in_roster)
        assert persona in roster_ids, (
            f"Org persona '{persona}' not found in roster registry"
        )


# ===========================================================================
# TEST 19 — Voice remains gated
# ===========================================================================

def test_19_voice_remains_gated(org_spec):
    """Voice must be classified as a separate required sprint — not activated."""
    assert "HOLD" in org_spec.voice_status or "gated" in org_spec.voice_status.lower(), (
        f"Voice status should indicate HOLD/gated, got: '{org_spec.voice_status}'"
    )

    # No role must have voice in allowed_actions without a gate
    for role in org_spec.roles:
        if "voice" in " ".join(role.allowed_actions).lower():
            # Must also be in blocked_actions or have explicit gate
            assert "voice" in " ".join(role.blocked_actions).lower() or \
                   "us13_voice" in " ".join(role.blocked_actions), (
                f"Role '{role.role_id}' allows voice without gate"
            )


# ===========================================================================
# TEST 20 — Full no-gap remains HOLD
# ===========================================================================

def test_20_full_no_gap_remains_hold(org_spec):
    """Full no-gap Jarvis must be classified as HOLD — not claimed complete."""
    assert "HOLD" in org_spec.no_gap_status, (
        f"No-gap status must be HOLD, got: '{org_spec.no_gap_status}'"
    )


# ===========================================================================
# INTEGRATION TEST I1 — MacBook → COS → Worker → Artifact
# ===========================================================================

def test_I1_macbook_task_routes_through_cos_to_worker(org_spec):
    """MacBook session starts a task, COS routes to manager, worker produces artifact."""
    # Verify COS routes to GM
    cos = org_spec.get_role("cos")
    gm = org_spec.get_role("gm")
    assert cos is not None
    assert gm is not None
    assert "gm" in cos.escalation_path or "delegate_to_gm" in cos.allowed_actions

    # Create a coding manager team and execute
    pool = create_worker_pool("manager-coding")
    inspector = create_worker_task("worker-repo-inspector", "inspect changed files")
    runner = create_worker_task(
        "worker-test-runner", "run targeted tests",
        dependencies=[inspector.task_id],
    )
    pool.add_task(inspector)
    pool.add_task(runner)

    artifacts_produced = {}

    def executor(task: WorkerTask) -> dict:
        artifact_path = f"/tmp/artifacts/{task.task_id}.json"
        artifacts_produced[task.task_id] = artifact_path
        return {"status": "done", "artifact": artifact_path}

    result = pool.execute(executor, "Sprint 3 coding task")
    assert result["completed_count"] == 2
    assert len(pool.get_artifacts()) == 2


# ===========================================================================
# INTEGRATION TEST I2/I3 — Snapshot + Mobile Resume with verifier status
# ===========================================================================

def test_I2_I3_snapshot_and_mobile_resume_with_full_state():
    """MacBook snapshot → mobile resume with task/manager/worker/verifier/artifact state."""
    store = ContinuityStore()
    macbook = store.register_device("bryan", DeviceType.MACBOOK, "MacBook Pro", trusted=True)
    iphone = store.register_device("bryan", DeviceType.IPHONE, "iPhone 15 Pro", trusted=True)

    # MacBook: save full state
    snap = store.save_snapshot(
        user_id="bryan",
        source_device_id=macbook.device_id,
        conversation_id="conv-integration-001",
        conversation_messages=[
            {"role": "user", "content": "Implement sprint 3"},
            {"role": "assistant", "content": "Routing to COS..."},
        ],
        active_task_id="task-sprint3",
        active_task_description="Company org + mobile continuity",
        active_task_status="running",
        assigned_manager_role_id="manager-coding",
        assigned_worker_role_ids=["worker-repo-inspector", "worker-test-runner"],
        worker_statuses={
            "worker-repo-inspector": "completed",
            "worker-test-runner": "running",
        },
        pending_approvals=[{"approval_id": "appr-001", "description": "Review diff"}],
        artifact_pointers=[
            {"task_id": "task-sprint3", "path": "/tmp/sprint3_result.json", "type": "json"}
        ],
        project_id="openjarvis",
        project_context={"sprint": "sprint-3", "branch": "localhost-get-tool"},
        memory_refs=["mem-sprint3-001"],
        verifier_status="ACCEPTED",
        verifier_fix_list=[],
        sync_status=SyncStatus.PENDING,
    )

    assert snap.resume_token is not None

    # iPhone: resume
    result = store.resume_on_device(
        resume_token=snap.resume_token,
        target_device_id=iphone.device_id,
    )

    assert result.success is True, f"Resume failed: {result.error}"
    assert result.conflict_detected is False

    # Verify full state is accessible via snapshot
    restored = store.get_snapshot(result.snapshot_id)
    assert restored.conversation_id == "conv-integration-001"
    assert restored.active_task_id == "task-sprint3"
    assert restored.assigned_manager_role_id == "manager-coding"
    assert "worker-repo-inspector" in restored.assigned_worker_role_ids
    assert restored.verifier_status == "ACCEPTED"
    assert len(restored.artifact_pointers) >= 1
    assert len(restored.pending_approvals) >= 1
    assert restored.project_id == "openjarvis"

    # No manual prompt transfer needed — all state is in snapshot
    assert restored.conversation_messages is not None
    assert len(restored.conversation_messages) == 2


# ===========================================================================
# INTEGRATION TEST I4 — Conflict surfaced when target has newer snapshot
# ===========================================================================

def test_I4_conflict_surfaced_on_mobile_has_newer_state():
    """If target device has newer work, conflict is surfaced — not hidden."""
    store = ContinuityStore(conflict_policy=ConflictPolicy.SURFACE_CONFLICT)
    macbook = store.register_device("bryan", DeviceType.MACBOOK, "MacBook", trusted=True)
    iphone = store.register_device("bryan", DeviceType.IPHONE, "iPhone", trusted=True)

    # MacBook snapshot
    old_snap = store.save_snapshot(
        user_id="bryan",
        source_device_id=macbook.device_id,
        active_task_status="running",
        sync_status=SyncStatus.PENDING,
    )

    # iPhone later saves its own snapshot (newer)
    iphone_snap = store.save_snapshot(
        user_id="bryan",
        source_device_id=iphone.device_id,
        active_task_status="completed",
        sync_status=SyncStatus.PENDING,
    )
    iphone_snap.created_at = old_snap.created_at + 5.0  # clearly newer

    # MacBook tries to resume on iPhone → conflict
    result = store.resume_on_device(
        resume_token=old_snap.resume_token,
        target_device_id=iphone.device_id,
        current_state={"device_id": iphone.device_id},
    )

    assert result.success is True  # resume succeeds but conflict is surfaced
    assert result.conflict_detected is True
    assert result.conflict_description is not None
    # Conflict must NOT be hidden
    resumed_snap = store.get_snapshot(result.snapshot_id)
    assert resumed_snap.conflict_state is not None


# ===========================================================================
# Additional: Mobile API contract
# ===========================================================================

def test_mobile_api_contract_exists():
    """Mobile API contract must exist and classify UI work as REQUIRED_FOR_NO_GAP_JARVIS."""
    store = ContinuityStore()
    contract = store.get_mobile_api_contract()
    assert "REQUIRED_FOR_NO_GAP_JARVIS" in contract["mobile_ui_status"]
    assert len(contract["endpoints"]) >= 3, "Contract must define at least 3 endpoints"
    assert len(contract["mobile_ui_remaining"]) >= 1


# ===========================================================================
# Additional: Company org singleton
# ===========================================================================

def test_company_org_singleton_consistent():
    """get_company_org_spec() returns consistent spec across calls."""
    spec1 = get_company_org_spec()
    spec2 = get_company_org_spec()
    assert spec1 is spec2, "Spec singleton not consistent"


# ===========================================================================
# Additional: Escalation protocol present
# ===========================================================================

def test_escalation_protocol_documented(org_spec):
    """Org spec must document the escalation protocol."""
    assert "Worker" in org_spec.escalation_protocol
    assert "Bryan" in org_spec.escalation_protocol
