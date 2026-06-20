"""Jarvis Company Org Runtime — callable task pipeline.

Implements the real callable path:
  Jarvis → COS → GM → Manager → Workers → Verifier

This is NOT dry-run. It executes the actual local pipeline with:
  - Real company org spec lookup
  - Real worker pool creation and execution
  - Real verifier gate call
  - Real artifact pointers (file paths or dicts)
  - Real stall simulation/detection
  - Real skill/tool coverage enforcement

Blocked actions (permanent):
  - No external sends without approval
  - No production deploy
  - No auto-push/merge
  - No secret access

Sprint: Full No-Gap Jarvis — Combined Sprint 3 HOLD Correction
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from openjarvis.company_org import (
    build_company_org_spec,
    get_company_org_spec,
    CapabilityStatus,
    RoleTier,
    RoleCapabilitySpec,
)
from openjarvis.agents.worker_pool import (
    WorkerPool,
    WorkerTask,
    WorkerTaskStatus,
    StallReport,
    create_worker_pool,
    create_worker_task,
)
from openjarvis.agents.verifier import (
    VerifierGate,
    EvidenceItem,
    VerificationOutcome,
    VerificationReport,
    get_default_verifier_gate,
)
from openjarvis.agents.self_improvement import (
    get_self_improvement_registry,
    FlawSeverity,
)
from openjarvis.agents.cos_skill import get_cos_skill
from openjarvis.agents.code_sentinel import get_code_sentinel
from openjarvis.agents.drift_guard import get_drift_guard
from openjarvis.jarvis_os.role_cache import get_role_cache, CacheLayer, SecurityLevel
from openjarvis.jarvis_os.cost_ledger import get_cost_ledger
from openjarvis.jarvis_os.manifest import build_capability_manifest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task routing request / response
# ---------------------------------------------------------------------------

@dataclass
class OrgTaskRequest:
    """A task routed through the company org pipeline."""

    task_id: str
    user_request: str
    intent: str                          # "coding" | "research" | "memory" | "ops" | "general"
    required_skills: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    simulate_stall: bool = False         # test: simulate a worker stall
    stall_worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerResult:
    """Result from a single worker execution."""

    worker_role_id: str
    status: str
    artifact_pointer: Optional[str]     # file path or structured pointer
    output: Dict[str, Any]
    stall_report: Optional[Dict[str, Any]] = None


@dataclass
class OrgTaskResult:
    """Full result from the company org task pipeline."""

    task_id: str
    pipeline_status: str                # "completed" | "hold" | "blocked" | "stalled"
    routing_trace: List[str]            # ordered: Jarvis → COS → GM → Manager → Workers
    assigned_manager_role_id: Optional[str]
    assigned_workers: List[str]
    worker_results: List[WorkerResult]
    verifier_outcome: Optional[str]
    verifier_fix_list: List[str]
    verifier_acceptance_trace: Optional[str]
    blockers: List[str]
    stall_reports: List[Dict[str, Any]]
    skill_tool_gaps: List[Dict[str, Any]]
    elapsed_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Extra fields for one-system integration
    cos_routing: Optional[Dict[str, Any]] = None
    cache_trace: Optional[List[Dict[str, Any]]] = None
    cost_trace: Optional[Dict[str, Any]] = None
    capability_status: Optional[Dict[str, Any]] = None
    sentinel_findings: Optional[List[Dict[str, Any]]] = None
    drift_findings: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "pipeline_status": self.pipeline_status,
            "routing_trace": self.routing_trace,
            "assigned_manager_role_id": self.assigned_manager_role_id,
            "assigned_workers": self.assigned_workers,
            "worker_results": [
                {
                    "worker_role_id": r.worker_role_id,
                    "status": r.status,
                    "artifact_pointer": r.artifact_pointer,
                    "output": r.output,
                    "stall_report": r.stall_report,
                }
                for r in self.worker_results
            ],
            "verifier_outcome": self.verifier_outcome,
            "verifier_fix_list": self.verifier_fix_list,
            "verifier_acceptance_trace": self.verifier_acceptance_trace,
            "blockers": self.blockers,
            "stall_reports": self.stall_reports,
            "skill_tool_gaps": self.skill_tool_gaps,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "metadata": self.metadata,
            "cos_routing": self.cos_routing,
            "cache_trace": self.cache_trace,
            "cost_trace": self.cost_trace,
            "capability_status": self.capability_status,
            "sentinel_findings": self.sentinel_findings,
            "drift_findings": self.drift_findings,
        }


# ---------------------------------------------------------------------------
# Skill/tool coverage enforcement
# ---------------------------------------------------------------------------

def _check_skill_tool_coverage(role: RoleCapabilitySpec) -> List[Dict[str, Any]]:
    """Return gaps if role has REQUIRED_AND_MISSING tools or skills."""
    gaps = []
    if role.tool_coverage_status == CapabilityStatus.REQUIRED_AND_MISSING:
        gaps.append({
            "role_id": role.role_id,
            "gap_type": "tools",
            "missing": role.missing_tools,
            "action": "Cannot assign — required tools missing",
        })
    if role.skill_coverage_status == CapabilityStatus.REQUIRED_AND_MISSING:
        gaps.append({
            "role_id": role.role_id,
            "gap_type": "skills",
            "missing": role.missing_skills,
            "action": "Cannot assign — required skills missing",
        })
    return gaps


# ---------------------------------------------------------------------------
# Intent → manager mapping
# ---------------------------------------------------------------------------

_INTENT_TO_MANAGER = {
    "coding": "manager-coding",
    "research": "manager-research",
    "memory": "manager-memory",
    "ops": "manager-ops-safety",
    "connector": "manager-connector",
    "general": "manager-coding",   # default to coding for general tasks
}

_MANAGER_TO_DEFAULT_WORKERS = {
    "manager-coding": ["worker-repo-inspector", "worker-test-runner"],
    "manager-research": [],        # dynamic — no pre-assigned workers
    "manager-memory": ["worker-memory-sync", "worker-obsidian-exporter"],
    "manager-ops-safety": [],
    "manager-connector": [],
}


# ---------------------------------------------------------------------------
# Company Org Runtime
# ---------------------------------------------------------------------------

class CompanyOrgRuntime:
    """Executes tasks through the Jarvis company org pipeline.

    Pipeline:
      1. Jarvis receives request
      2. COS routes to appropriate manager
      3. GM coordinates parallel/sequenced worker execution
      4. Workers execute and produce artifacts
      5. Verifier validates artifacts
      6. Blockers and stalls are surfaced

    All actions are local — no external sends, no production deploy.
    """

    def __init__(
        self,
        verifier_gate: Optional[VerifierGate] = None,
        stale_threshold_seconds: int = 86400,
    ) -> None:
        self._spec = get_company_org_spec()
        self._verifier = verifier_gate or VerifierGate(
            verifier_id="verifier",
            stale_threshold_seconds=stale_threshold_seconds,
        )
        self._si_registry = get_self_improvement_registry()

    def run(
        self,
        request: OrgTaskRequest,
        worker_executor: Optional[Callable[[WorkerTask], Dict[str, Any]]] = None,
    ) -> OrgTaskResult:
        """Execute a task through the full company org pipeline."""
        t0 = time.time()
        trace: List[str] = []
        blockers: List[str] = []
        stall_reports: List[Dict[str, Any]] = []
        skill_tool_gaps: List[Dict[str, Any]] = []

        # One-system integration: get singletons
        cos = get_cos_skill()
        cache = get_role_cache()
        ledger = get_cost_ledger()
        sentinel = get_code_sentinel()
        drift_guard = get_drift_guard()

        # 1. Jarvis receives request
        trace.append(f"jarvis: received task '{request.task_id}' intent={request.intent}")

        # 2. COS routes (real COS skill call)
        cos_decision = cos.route(
            task_description=request.user_request,
            task_count=1,
            has_dependencies=False,
        )
        manager_role_id = _INTENT_TO_MANAGER.get(request.intent, cos_decision.selected_manager)
        trace.append(
            f"cos: routing to {manager_role_id} "
            f"(priority={cos_decision.priority.value}, mode={cos_decision.execution_mode.value})"
        )

        # Record COS cost
        ledger.record(request.task_id, "cos", model="local", description="COS routing")

        # 3. Check skill/tool coverage for manager
        manager_role = self._spec.get_role(manager_role_id)
        if manager_role is None:
            blockers.append(f"Manager role '{manager_role_id}' not found in org spec")
            return self._make_result(
                request, "blocked", trace, None, [], [], None, [], None,
                blockers, stall_reports, skill_tool_gaps, t0
            )

        gaps = _check_skill_tool_coverage(manager_role)
        if gaps:
            skill_tool_gaps.extend(gaps)
            blockers.append(f"Manager '{manager_role_id}' has REQUIRED_AND_MISSING tools/skills")
            trace.append(f"gm: BLOCKED — manager '{manager_role_id}' has missing capabilities")
            return self._make_result(
                request, "blocked", trace, manager_role_id, [], [], None, [],
                None, blockers, stall_reports, skill_tool_gaps, t0
            )

        # 4. GM activates workers
        trace.append(f"gm: activating workers under {manager_role_id}")
        worker_ids = _MANAGER_TO_DEFAULT_WORKERS.get(manager_role_id, [])

        # Check required_skills/required_tools from request against what's available
        if request.required_tools:
            available = set(manager_role.required_tools)
            missing = [t for t in request.required_tools if t not in available]
            if missing:
                skill_tool_gaps.append({
                    "role_id": manager_role_id,
                    "gap_type": "requested_tools",
                    "missing": missing,
                    "action": "Requested tools not in manager's required_tools list",
                })
                blockers.append(f"Missing tools for manager: {missing}")

        # Check worker coverage
        valid_workers = []
        for wid in worker_ids:
            wrole = self._spec.get_role(wid)
            if wrole is None:
                continue
            wgaps = _check_skill_tool_coverage(wrole)
            if wgaps:
                skill_tool_gaps.extend(wgaps)
                trace.append(f"gm: worker '{wid}' has missing capabilities — skipping")
            else:
                valid_workers.append(wid)

        trace.append(f"manager: assigned workers: {valid_workers}")

        # 5. Execute workers via pool
        pool = create_worker_pool(manager_role_id)
        task_map: Dict[str, WorkerTask] = {}

        # Build tasks — first worker has no deps; subsequent depend on first
        for i, wid in enumerate(valid_workers):
            deps = [task_map[valid_workers[i - 1]].task_id] if i > 0 else []
            wt = create_worker_task(
                worker_role_id=wid,
                description=f"Execute {wid} for task {request.task_id}",
                input_data={"user_request": request.user_request},
                stall_timeout_seconds=300,
                dependencies=deps,
                parallelizable=(i == 0),   # first can parallelize; rest depend on it
            )
            # Simulate stall: pre-mark as RUNNING with old timestamp so
            # pool.execute() skips execution and check_stalls() detects it.
            if request.simulate_stall and wid == request.stall_worker_id:
                wt.status = WorkerTaskStatus.RUNNING
                wt.started_at = time.time() - 400   # 400s in the past → stall
                wt.stall_timeout_seconds = 1         # timeout exceeded

            task_map[wid] = wt
            pool.add_task(wt)

        # Use provided executor or default safe local executor
        if worker_executor is None:
            worker_executor = _default_local_executor

        pool_result = pool.execute(worker_executor)

        # Also run check_stalls with reassignment target for any pre-marked stalls
        pool.check_stalls(reassign_to=manager_role_id)

        # Collect stall reports
        for sr in pool.get_all_stall_reports():
            stall_reports.append(sr.to_dict())
            trace.append(
                f"gm: STALL detected — worker '{sr.worker_role_id}' "
                f"after {sr.stall_duration_seconds:.0f}s"
            )
            if sr.reassignable:
                trace.append(f"gm: reassigning stalled worker '{sr.worker_role_id}' to manager")

        # Record stall as caught flaw in self-improvement
        if stall_reports:
            self._si_registry.record_flaw(
                description=f"Worker stall detected in task {request.task_id}",
                severity=FlawSeverity.MEDIUM,
                caught_by="gm",
                affected_task=request.task_id,
                root_cause="Worker exceeded stall timeout",
                fix_applied="Stall detected and reported; reassignment triggered",
                prevention_type="validation_gate",
                prevention_action="Add stall monitoring to all worker pools",
            )

        # Build worker results
        worker_results: List[WorkerResult] = []
        for wid, wt in task_map.items():
            stall_rep = next(
                (sr.to_dict() for sr in pool.get_all_stall_reports() if sr.task_id == wt.task_id),
                None,
            )
            artifact = pool.get_artifacts().get(wt.task_id)
            worker_results.append(WorkerResult(
                worker_role_id=wid,
                status=wt.status.value,
                artifact_pointer=artifact,
                output=wt.result or {},
                stall_report=stall_rep,
            ))
            trace.append(
                f"worker/{wid}: status={wt.status.value} artifact={artifact}"
            )

        # 6. Verifier validates
        trace.append("verifier: validating worker artifacts")
        evidence_items = []
        for wr in worker_results:
            evidence_items.append(EvidenceItem(
                claim_id=f"worker-{wr.worker_role_id}",
                claim_text=f"Worker '{wr.worker_role_id}' produced artifact",
                source_type="worker_output",
                source_ref=wr.artifact_pointer or "",
                last_updated_at=time.time(),
                is_supported=(wr.status == WorkerTaskStatus.COMPLETED.value),
            ))

        verifier_report: Optional[VerificationReport] = None
        if evidence_items:
            verifier_report = self._verifier.verify(
                team_id=manager_role_id,
                evidence_items=evidence_items,
            )
            trace.append(
                f"verifier: outcome={verifier_report.outcome.value} "
                f"accepted={len(verifier_report.accepted_claims)} "
                f"rejected={len(verifier_report.rejected_claims)}"
            )

        # Record worker costs
        for wr in worker_results:
            ledger.record(
                request.task_id, wr.worker_role_id,
                model="local",
                description=f"Worker {wr.worker_role_id} execution",
                cache_hit=False,
            )

        # Record verifier cost
        if verifier_report:
            ledger.record(request.task_id, "verifier", model="local", description="Verifier gate")

        # Sentinel: check changed files (task artifacts) and claims
        sentinel_result = sentinel.run_gate(
            changed_files=[wr.artifact_pointer for wr in worker_results if wr.artifact_pointer],
            claims=[request.user_request],
            validation_commands=["pool.execute", "verifier.verify"],
        )

        # Drift guard: check for fake readiness in pipeline
        drift_result = drift_guard.run_full_guard(
            text=request.user_request + " " + " ".join(trace),
        )

        # Cache: store manager result for role reuse
        cache.put(
            CacheLayer.ROLE,
            manager_role_id,
            content={"task_id": request.task_id, "pipeline_status": "pending"},
            qualifier=request.task_id,
            security_level=SecurityLevel.INTERNAL,
            gates_required=["verifier.verify"],
        )

        # Determine pipeline status
        if blockers:
            pipeline_status = "blocked"
        elif stall_reports and not valid_workers:
            pipeline_status = "stalled"
        elif verifier_report and verifier_report.outcome == VerificationOutcome.REJECTED:
            pipeline_status = "hold"
        else:
            pipeline_status = "completed"

        trace.append(f"cos: pipeline_status={pipeline_status}")

        # COS handoff
        handoff = cos.create_handoff(
            from_role="gm",
            to_role="verifier",
            task_id=request.task_id,
            task_description=request.user_request,
            context_summary=f"Pipeline {pipeline_status} — {len(worker_results)} workers",
            blockers=blockers,
        )
        trace.append(f"cos: handoff created handoff_id={handoff.handoff_id}")

        return self._make_result(
            request,
            pipeline_status,
            trace,
            manager_role_id,
            valid_workers,
            worker_results,
            verifier_report,
            blockers,
            None,
            blockers,
            stall_reports,
            skill_tool_gaps,
            t0,
            cos_routing=cos_decision.to_dict(),
            cache_trace=cache.get_trace(),
            cost_trace=ledger.get_task_summary(request.task_id),
            capability_status={
                "no_gap_status": "HOLD",
                "voice_status": "SEPARATE_SPRINT_REQUIRED",
                "mobile_continuity": "WIRED_AND_TESTED (LAN); MacBook-off requires GITHUB_TOKEN",
            },
            sentinel_findings=sentinel_result.get("findings", []),
            drift_findings=drift_result.get("findings", []),
        )

    def _make_result(
        self,
        request: OrgTaskRequest,
        pipeline_status: str,
        trace: List[str],
        manager_role_id: Optional[str],
        assigned_workers: List[str],
        worker_results: List[WorkerResult],
        verifier_report: Optional[VerificationReport],
        blockers: List[str],
        _unused: Any,
        all_blockers: List[str],
        stall_reports: List[Dict[str, Any]],
        skill_tool_gaps: List[Dict[str, Any]],
        t0: float,
        cos_routing: Optional[Dict[str, Any]] = None,
        cache_trace: Optional[List[Dict[str, Any]]] = None,
        cost_trace: Optional[Dict[str, Any]] = None,
        capability_status: Optional[Dict[str, Any]] = None,
        sentinel_findings: Optional[List[Dict[str, Any]]] = None,
        drift_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> OrgTaskResult:
        return OrgTaskResult(
            task_id=request.task_id,
            pipeline_status=pipeline_status,
            routing_trace=trace,
            assigned_manager_role_id=manager_role_id,
            assigned_workers=assigned_workers,
            worker_results=worker_results,
            verifier_outcome=verifier_report.outcome.value if verifier_report else None,
            verifier_fix_list=verifier_report.fix_list if verifier_report else [],
            verifier_acceptance_trace=verifier_report.acceptance_trace if verifier_report else None,
            blockers=all_blockers,
            stall_reports=stall_reports,
            skill_tool_gaps=skill_tool_gaps,
            elapsed_seconds=time.time() - t0,
            cos_routing=cos_routing,
            cache_trace=cache_trace,
            cost_trace=cost_trace,
            capability_status=capability_status,
            sentinel_findings=sentinel_findings,
            drift_findings=drift_findings,
        )


# ---------------------------------------------------------------------------
# Default safe local executor (gated, real tool dispatch)
# ---------------------------------------------------------------------------

# Allowlist of tool IDs that the default local executor may dispatch.
# Only read-only / non-destructive tools are permitted. Every dispatch goes
# through ToolExecutionGateway which enforces governance gates.
_LOCAL_EXECUTOR_TOOL_ALLOWLIST: frozenset = frozenset(
    [
        "mission.list",
        "mission.get",
        "task.get",
        "event.list_recent",
        "project.list",
        "project.get",
        "agent.list",
        "governance.gate_check",
        "notify.status",
        "memory.search",
    ]
)

# Tool IDs that are NEVER permitted in the local executor (hard gates).
_LOCAL_EXECUTOR_BLOCKED_TOOLS: frozenset = frozenset(
    [
        "shell_exec",
        "fs_write",
        "git_push",
        "deploy",
        "slack.send",
        "telegram.send",
        "email.send",
    ]
)


def _default_local_executor(task: WorkerTask) -> Dict[str, Any]:
    """Gated local tool executor for CompanyOrgRuntime worker tasks.

    Replaces the former scaffold that returned a static fake artifact path.
    This executor:
      - Dispatches only tools in _LOCAL_EXECUTOR_TOOL_ALLOWLIST.
      - All dispatch goes through ToolExecutionGateway (governance gates, audit log).
      - Returns an honest status when no tool matches the task or the tool is
        blocked — never returns a fake success.
      - No destructive actions by default.
      - dry_run support: when task.input_data.get("dry_run") is True, records
        intent but does not call gateway.execute().
      - Audit log path: ~/.jarvis/tool_executions.db (ToolExecutionGateway default).
    """
    from openjarvis.tools.gateway import ToolExecutionGateway
    from openjarvis.tools.jarvis_registry import ToolRegistry

    dry_run = bool(task.input_data.get("dry_run", False))
    task_tool_hint = task.input_data.get("tool_id", "")

    # Determine which tool to dispatch, if any.
    candidate_tool: str = ""
    if task_tool_hint and task_tool_hint in _LOCAL_EXECUTOR_TOOL_ALLOWLIST:
        candidate_tool = task_tool_hint
    else:
        # Hard-blocked tool requested: refuse immediately.
        if task_tool_hint in _LOCAL_EXECUTOR_BLOCKED_TOOLS:
            return {
                "worker_role_id": task.worker_role_id,
                "description": task.description,
                "executed_at": time.time(),
                "status": "blocked",
                "tool_id": task_tool_hint,
                "reason": (
                    f"Tool '{task_tool_hint}' is hard-gated — "
                    "Bryan authorization required per governance constitution."
                ),
                "artifact": None,
            }
        # No matching allowed tool — report unavailable rather than fake success.
        return {
            "worker_role_id": task.worker_role_id,
            "description": task.description,
            "executed_at": time.time(),
            "status": "unavailable",
            "tool_id": task_tool_hint or None,
            "reason": (
                f"No allowed local tool for task '{task.description[:80]}'. "
                "Allowed tools: "
                + ", ".join(sorted(_LOCAL_EXECUTOR_TOOL_ALLOWLIST))
            ),
            "artifact": None,
        }

    if dry_run:
        return {
            "worker_role_id": task.worker_role_id,
            "description": task.description,
            "executed_at": time.time(),
            "status": "dry_run",
            "tool_id": candidate_tool,
            "inputs": {k: v for k, v in task.input_data.items() if k != "dry_run"},
            "artifact": None,
        }

    # Real dispatch through the gateway (governance gates + audit log).
    gateway = ToolExecutionGateway()
    tool_inputs = {k: v for k, v in task.input_data.items()
                   if k not in ("tool_id", "dry_run")}
    result = gateway.execute(
        candidate_tool,
        inputs=tool_inputs,
        project_id=task.input_data.get("project_id", ""),
        task_id=task.task_id,
        agent_id=task.worker_role_id,
    )

    return {
        "worker_role_id": task.worker_role_id,
        "description": task.description,
        "executed_at": time.time(),
        "status": result.outcome,
        "tool_id": candidate_tool,
        "output": result.output,
        "error": result.error,
        "artifact": None,
    }


# ---------------------------------------------------------------------------
# Module-level runtime singleton
# ---------------------------------------------------------------------------

_RUNTIME: Optional[CompanyOrgRuntime] = None


def get_company_org_runtime() -> CompanyOrgRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = CompanyOrgRuntime()
    return _RUNTIME


__all__ = [
    "OrgTaskRequest",
    "WorkerResult",
    "OrgTaskResult",
    "CompanyOrgRuntime",
    "get_company_org_runtime",
]
