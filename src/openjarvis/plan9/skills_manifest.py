"""Plan 9 — Jarvis Skills Manifest.

Declares all 21 required Plan 9 skills. Extends the existing SkillSpec/SkillRegistry
system in openjarvis.skills — does not duplicate it.

Skills marked DOCUMENTED are defined here but not yet wired to real tools.
Skills marked WIRED have real tool backing in the skills catalog or executor.
Skills marked TESTED have passing tests.
Skills marked PARTIAL have partial coverage only.
Skills marked MISSING have not been implemented at all.

Runtime status is honest — no inflation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class Plan9SkillStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"    # defined here, not wired
    WIRED = "WIRED"              # wired to real tools/executor
    TESTED = "TESTED"            # wired and has passing tests
    PARTIAL = "PARTIAL"          # some components wired, not all
    MISSING = "MISSING"          # not yet implemented at all


@dataclass
class Plan9SkillEntry:
    skill_id: str
    display_name: str
    purpose: str
    inputs: List[str]
    outputs: List[str]
    authority_level: str   # auto | requires_approval | hard_gate
    model_tier: str        # cheap | balanced | best
    validation_requirements: str
    applicable_managers: List[str]   # manager_ids this skill applies to
    default_inheritance: bool        # True = future managers inherit by default
    status: Plan9SkillStatus
    runtime_status_notes: str = ""   # honest notes about current implementation

    def to_dict(self) -> Dict:
        return {
            "skill_id": self.skill_id,
            "display_name": self.display_name,
            "purpose": self.purpose,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "authority_level": self.authority_level,
            "model_tier": self.model_tier,
            "validation_requirements": self.validation_requirements,
            "applicable_managers": self.applicable_managers,
            "default_inheritance": self.default_inheritance,
            "status": self.status.value,
            "runtime_status_notes": self.runtime_status_notes,
        }


_ALL_MANAGERS = [
    "coding_manager", "architecture_manager", "testing_validation_manager",
    "code_review_manager", "debugging_manager", "research_manager",
    "memory_knowledge_manager", "documentation_manager", "product_ux_manager",
    "operations_automation_manager", "governance_safety_manager",
    "release_packaging_manager", "data_manager", "cost_routing_manager",
    "nus_learning_manager", "connector_auth_manager", "runtime_ops_manager",
]


PLAN9_SKILLS_MANIFEST: List[Plan9SkillEntry] = [

    Plan9SkillEntry(
        skill_id="capability_inventory",
        display_name="Capability Inventory Skill",
        purpose="Build and query full capability inventory across all managers, workers, domains",
        inputs=["scope: str (optional)", "filter_status: CapabilityStatus (optional)"],
        outputs=["Plan9CapabilityMatrix", "capability summary by status"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="All 17 managers must appear in matrix output",
        applicable_managers=_ALL_MANAGERS,
        default_inheritance=True,
        status=Plan9SkillStatus.WIRED,
        runtime_status_notes="Implemented in capability_matrix.py; get_plan9_capability_matrix() returns full matrix",
    ),

    Plan9SkillEntry(
        skill_id="model_routing",
        display_name="Model Routing Skill",
        purpose="Determine correct model tier for role + task + risk context",
        inputs=["role_id: str", "task_description: str", "risk_level: str", "complexity: str", "failures: int"],
        outputs=["ModelTier recommendation", "model name suggestion", "escalation justification"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Routing decision must include tier + justification",
        applicable_managers=_ALL_MANAGERS,
        default_inheritance=True,
        status=Plan9SkillStatus.WIRED,
        runtime_status_notes="Implemented in model_routing.py; get_role_routing_matrix() + tier_for_task()",
    ),

    Plan9SkillEntry(
        skill_id="retrieval_context_packet",
        display_name="Retrieval / Context Packet Skill",
        purpose="Gather compact evidence packet before expensive reasoning; cheap deterministic retrieval",
        inputs=["scope: str", "query: str", "max_tokens: int"],
        outputs=["compact evidence packet", "sources list", "dedup status"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Evidence packet must be compact (not raw dump); sources cited",
        applicable_managers=_ALL_MANAGERS,
        default_inheritance=True,
        status=Plan9SkillStatus.PARTIAL,
        runtime_status_notes="retrieval_worker policy defined; connector/context retrieval partially wired",
    ),

    Plan9SkillEntry(
        skill_id="task_dag_scheduler",
        display_name="Task DAG / Scheduler Skill",
        purpose="Build dependency graph for multi-step tasks; schedule safe parallel execution",
        inputs=["task_list: List[Task]", "dependency_map: Dict"],
        outputs=["TaskDAG", "safe parallel groups", "sequential constraints"],
        authority_level="auto",
        model_tier="balanced",
        validation_requirements="No risky actions in parallel group; dependency ordering correct",
        applicable_managers=_ALL_MANAGERS,
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Policy defined in orchestration_policy.py; executor not yet wired",
    ),

    Plan9SkillEntry(
        skill_id="elastic_worker_pool",
        display_name="Elastic Worker Pool Skill",
        purpose="Scale same-role workers dynamically based on task independence, risk, token budget",
        inputs=["role_id: str", "task_count: int", "risk: str", "token_budget: int"],
        outputs=["worker_count recommendation", "shard plan", "conflict risk flags"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Single-executor for commits/deploys/destructive ops enforced",
        applicable_managers=_ALL_MANAGERS,
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Policy defined in orchestration_policy.py; dynamic scaling not yet wired",
    ),

    Plan9SkillEntry(
        skill_id="same_file_patch_propose",
        display_name="Same-File Patch Proposal Skill",
        purpose="Worker generates structured patch proposal for a single item in a shared file",
        inputs=["file_path: str", "item_id: str", "diff_hunk: str", "ownership_claim: str"],
        outputs=["PatchProposal with target section, risk notes, tests needed"],
        authority_level="auto",
        model_tier="balanced",
        validation_requirements="Patch proposal must include ownership claim and non-overlapping assertion",
        applicable_managers=["coding_manager", "documentation_manager", "architecture_manager"],
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Protocol defined in orchestration_policy.py; patch integrator not yet wired",
    ),

    Plan9SkillEntry(
        skill_id="batch_integration",
        display_name="Batch Integration Skill",
        purpose="Batch Integration Manager collects all worker patches, combines into one coherent diff",
        inputs=["patch_proposals: List[PatchProposal]", "master_file_path: str"],
        outputs=["integrated_diff: str", "dropped_patches: List", "conflict_resolution_notes: str"],
        authority_level="auto",
        model_tier="balanced",
        validation_requirements="No patch dropped; overlaps resolved; all acceptance items present",
        applicable_managers=["coding_manager", "documentation_manager"],
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Protocol defined in orchestration_policy.py BatchIntegrationPolicy",
    ),

    Plan9SkillEntry(
        skill_id="integration_review",
        display_name="Integration Review Skill",
        purpose="Integration Review Manager independently verifies final integrated batch patch",
        inputs=["integrated_diff: str", "original_patch_proposals: List[PatchProposal]"],
        outputs=["review_result: PASS/FAIL", "dropped_item_list", "conflict_issues", "test_results"],
        authority_level="auto",
        model_tier="balanced",
        validation_requirements="All assigned items present; no dropped patches; tests pass",
        applicable_managers=["coding_manager", "testing_validation_manager"],
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Protocol defined in orchestration_policy.py IntegrationReviewPolicy",
    ),

    Plan9SkillEntry(
        skill_id="coding_workspace",
        display_name="Coding Workspace Skill",
        purpose="Cloud-native coding: inspect/search/read/edit repo files, stage diffs, create branches",
        inputs=["repo_path: str", "operation: str (read|edit|search|diff|branch)", "params: Dict"],
        outputs=["file content | diff | search results | branch status"],
        authority_level="requires_approval",
        model_tier="balanced",
        validation_requirements="Diffs staged and reviewed before any commit; no secrets in files",
        applicable_managers=["coding_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Route /v1/coding/workspace planned; not yet implemented in server",
    ),

    Plan9SkillEntry(
        skill_id="test_build_runner",
        display_name="Test / Build Runner Skill",
        purpose="Run targeted tests, lint, type checks on cloud; capture logs; route failures",
        inputs=["test_paths: List[str]", "test_type: str (pytest|lint|type)", "capture_artifacts: bool"],
        outputs=["test_results: TestReport", "failure_summary", "artifact_paths"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Full test output captured; failures routed to correct manager",
        applicable_managers=["testing_validation_manager", "coding_manager"],
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Route /v1/testing/run planned; local pytest available; cloud runner not yet wired",
    ),

    Plan9SkillEntry(
        skill_id="commit_push",
        display_name="Commit / Push Skill",
        purpose="Mobile/cloud diff review → commit message → branch status → push to remote → PR",
        inputs=["diff: str", "commit_message: str", "branch: str", "push_remote: bool"],
        outputs=["commit_sha", "push_status", "pr_url (if configured)"],
        authority_level="requires_approval",
        model_tier="cheap",
        validation_requirements="Secret scan passing; single active executor lock; Bryan approval where required",
        applicable_managers=["coding_manager", "release_packaging_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Route /v1/git/commit planned; single-executor lock required",
    ),

    Plan9SkillEntry(
        skill_id="deploy_operator",
        display_name="Deploy Operator Skill",
        purpose="Prepare cloud deploy plan, pre-deploy validation, health checks, rollback plan",
        inputs=["deploy_target: str", "image_tag: str", "approval_evidence: str"],
        outputs=["deploy_plan: DeployPlan", "health_check_results", "rollback_steps"],
        authority_level="hard_gate",
        model_tier="best",
        validation_requirements="Bryan approval required; health check passing; rollback plan documented",
        applicable_managers=["release_packaging_manager", "runtime_ops_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Route /v1/deploy/plan planned; execution blocked on Bryan approval hard gate",
    ),

    Plan9SkillEntry(
        skill_id="memory_parity",
        display_name="Memory Parity Skill",
        purpose="Verify cloud/mobile and MacBook/local see consistent memory state; no stale local claims",
        inputs=["namespace: str", "surface: str (cloud|local|both)"],
        outputs=["memory_parity_report", "sync_status", "stale_items"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Cloud and local memory match; stale items flagged",
        applicable_managers=["memory_knowledge_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.PARTIAL,
        runtime_status_notes="cloud_memory.py and cloud_sync.py exist; parity check partially implemented",
    ),

    Plan9SkillEntry(
        skill_id="connector_parity",
        display_name="Connector Parity Skill",
        purpose="Verify connector availability on cloud without MacBook; classify local-only connectors",
        inputs=["connector_id: str (optional)", "check_cloud: bool"],
        outputs=["ConnectorParityReport per connector", "cloud-safe status", "closure items"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Each connector classified; local-only ones have closure items",
        applicable_managers=["connector_auth_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.PARTIAL,
        runtime_status_notes="Connector status route exists; cloud-parity classification not yet complete",
    ),

    Plan9SkillEntry(
        skill_id="cloud_file_mirror",
        display_name="Cloud-Safe File Mirror / Index Skill",
        purpose="Index/mirror allowlisted safe files for cloud/mobile access; no blind Mac exposure",
        inputs=["allowlist: List[str]", "sync_mode: str (read-only|staged)"],
        outputs=["indexed_files: List", "mirror_status", "local_only_files: List"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Only allowlisted files indexed; no secrets in mirror",
        applicable_managers=["coding_manager", "memory_knowledge_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Route /v1/files/index planned; implementation not yet wired",
    ),

    Plan9SkillEntry(
        skill_id="mac_worker_queue",
        display_name="Mac Worker Queue Skill",
        purpose="Queue Mac-only tasks when MacBook offline; execute when online; visible on both surfaces",
        inputs=["task: MacWorkerTask", "surface: str (mobile|mac)"],
        outputs=["task_id", "queue_status", "execution_result (when executed)"],
        authority_level="requires_approval",
        model_tier="cheap",
        validation_requirements="Task queued when Mac offline; executed when online; both surfaces see status",
        applicable_managers=["runtime_ops_manager", "release_packaging_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.WIRED,
        runtime_status_notes="mac_worker_queue.py implemented; integration with server routes needed",
    ),

    Plan9SkillEntry(
        skill_id="capability_aware_ui",
        display_name="Capability-Aware UI/API Skill",
        purpose="Surface Plan 9 capability status (CLOUD_LIVE, LOCAL_LIVE, etc.) in mobile and MacBook UI",
        inputs=["surface: str (mobile|mac|both)", "filter_status: str (optional)"],
        outputs=["capabilities by status", "parity gaps", "parked items"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="All Plan 9 status types surfaced correctly; PARKED items shown as parked",
        applicable_managers=["product_ux_manager"],
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Route /v1/capabilities/status planned; frontend integration not yet wired",
    ),

    Plan9SkillEntry(
        skill_id="authority_approval_audit",
        display_name="Authority / Approval / Audit Skill",
        purpose="Classify action authority, check approval requirements, emit audit events, note rollback",
        inputs=["action: str", "actor: str", "surface: str", "model_used: str"],
        outputs=["AuthorityClassification", "approval_required: bool", "audit_event_id"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="All sensitive actions have audit event; approval gate checked",
        applicable_managers=["governance_safety_manager"],
        default_inheritance=True,
        status=Plan9SkillStatus.PARTIAL,
        runtime_status_notes="Governance gate check exists; Plan 9 audit trail partially implemented",
    ),

    Plan9SkillEntry(
        skill_id="rollback",
        display_name="Rollback Skill",
        purpose="Prepare rollback plan for any sensitive operation; document steps before execution",
        inputs=["operation: str", "state_before: Dict"],
        outputs=["rollback_steps: List[str]", "rollback_commands: List[str]"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Rollback plan documented before any deploy/destructive action",
        applicable_managers=_ALL_MANAGERS,
        default_inheritance=True,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="ROLLBACK.md exists; programmatic rollback plan generation not yet wired",
    ),

    Plan9SkillEntry(
        skill_id="secret_scan",
        display_name="Secret Scan Skill",
        purpose="Scan staged diffs and files for secrets before any commit/push/report",
        inputs=["diff: str (optional)", "file_paths: List[str] (optional)"],
        outputs=["scan_result: CLEAN | FOUND_SECRETS", "secret_locations (without values)", "abort_flag"],
        authority_level="auto",
        model_tier="cheap",
        validation_requirements="Run before every commit/push; ABORT if secrets found; no secret values in output",
        applicable_managers=_ALL_MANAGERS,
        default_inheritance=True,
        status=Plan9SkillStatus.PARTIAL,
        runtime_status_notes="secret_safety_worker exists; git-secrets/detect-secrets scan partially configured",
    ),

    Plan9SkillEntry(
        skill_id="sprint_report",
        display_name="Sprint Report Skill",
        purpose="Generate complete Plan 9 sprint report with verdict, files, tests, blockers, rollback",
        inputs=["sprint_id: str", "verdict: str", "changed_files: List", "test_results: Dict",
                "blockers: List", "secret_scan_result: str"],
        outputs=["SprintReport with all 24 required fields from Section 25"],
        authority_level="auto",
        model_tier="balanced",
        validation_requirements="All 24 final report fields populated; verdict is one of Plan 9 verdicts",
        applicable_managers=["governance_safety_manager"],
        default_inheritance=False,
        status=Plan9SkillStatus.DOCUMENTED,
        runtime_status_notes="Report format defined in pa_brain_layer.py; generator not yet wired",
    ),
]


def get_skills_manifest() -> List[Plan9SkillEntry]:
    return PLAN9_SKILLS_MANIFEST


def get_skill(skill_id: str) -> Optional[Plan9SkillEntry]:
    for s in PLAN9_SKILLS_MANIFEST:
        if s.skill_id == skill_id:
            return s
    return None


def skills_by_status(status: Plan9SkillStatus) -> List[Plan9SkillEntry]:
    return [s for s in PLAN9_SKILLS_MANIFEST if s.status == status]
