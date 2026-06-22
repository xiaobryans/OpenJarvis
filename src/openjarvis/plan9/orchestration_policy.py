"""Plan 9 — Orchestration Policies.

Covers Sections 8-11:
  8.  Retrieval / Reader Worker Policy per Team
  9.  Safe Parallel Execution / DAG Policy
  10. Elastic Same-Role Worker Pools Policy
  11. Same-File Batch Integration Protocol

These are machine-readable policy definitions. Executors are wired separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


# ============================================================================
# Section 8 — Retrieval / Reader Worker Policy
# ============================================================================

@dataclass(frozen=True)
class RetrievalWorkerPolicy:
    """Per-team retrieval/reader/context worker policy.

    Every team must have or inherit a retrieval worker policy.
    If a team explicitly does not need one, it must document why.
    Missing retrieval policy is a validation failure.
    """
    team_id: str
    retrieval_needed: bool
    retrieval_worker_id: str   # "retrieval_worker" for inherited; custom for override
    responsibilities: tuple    # what this team's retrieval worker does
    cheap_model_required: bool = True
    before_reasoning: bool = True  # retrieval runs before expensive reasoning
    explicit_justification_if_not_needed: str = ""


# Default retrieval responsibilities (inherited by all teams)
_DEFAULT_RETRIEVAL_RESPONSIBILITIES = (
    "repo/file search",
    "log reads",
    "docs lookup",
    "connector status reads",
    "memory/context retrieval",
    "test output summarization",
    "evidence extraction",
    "source packet preparation",
    "deduplication",
    "'what changed?' summaries",
)


def _make_retrieval_policy(team_id: str, extra: tuple = ()) -> RetrievalWorkerPolicy:
    return RetrievalWorkerPolicy(
        team_id=team_id,
        retrieval_needed=True,
        retrieval_worker_id="retrieval_worker",
        responsibilities=_DEFAULT_RETRIEVAL_RESPONSIBILITIES + extra,
        cheap_model_required=True,
        before_reasoning=True,
    )


RETRIEVAL_WORKER_POLICIES: Dict[str, RetrievalWorkerPolicy] = {
    "coding_manager": _make_retrieval_policy("coding_manager", ("code search", "file read", "test discovery")),
    "architecture_manager": _make_retrieval_policy("architecture_manager", ("design doc lookup", "ADR search")),
    "testing_validation_manager": _make_retrieval_policy("testing_validation_manager", ("test discovery", "failure log reads")),
    "code_review_manager": _make_retrieval_policy("code_review_manager", ("diff reads", "PR context")),
    "debugging_manager": _make_retrieval_policy("debugging_manager", ("stack trace reads", "log reads")),
    "research_manager": _make_retrieval_policy("research_manager", ("knowledge base lookup", "prior research reads")),
    "memory_knowledge_manager": _make_retrieval_policy("memory_knowledge_manager", ("memory namespace reads", "context retrieval")),
    "documentation_manager": _make_retrieval_policy("documentation_manager", ("doc lookup", "existing doc reads")),
    "product_ux_manager": _make_retrieval_policy("product_ux_manager", ("capability status reads", "UI state reads")),
    "operations_automation_manager": _make_retrieval_policy("operations_automation_manager", ("scheduler state reads", "automation log reads")),
    "governance_safety_manager": _make_retrieval_policy("governance_safety_manager", ("policy reads", "audit log reads")),
    "release_packaging_manager": _make_retrieval_policy("release_packaging_manager", ("version reads", "changelog reads", "build log reads")),
    "data_manager": _make_retrieval_policy("data_manager", ("data source reads", "schema reads")),
    "cost_routing_manager": _make_retrieval_policy("cost_routing_manager", ("cost ledger reads", "model pricing reads")),
    "nus_learning_manager": _make_retrieval_policy("nus_learning_manager", ("scorecard reads", "failure pattern reads")),
    "connector_auth_manager": _make_retrieval_policy("connector_auth_manager", ("connector status reads", "OAuth state reads")),
    "runtime_ops_manager": _make_retrieval_policy("runtime_ops_manager", ("health endpoint reads", "runtime log reads")),
}


# ============================================================================
# Section 9 — Safe Parallel Execution / DAG Policy
# ============================================================================

class ParallelSafety(str, Enum):
    SAFE = "SAFE"                  # independent; safe to parallelize
    UNSAFE_STATE = "UNSAFE_STATE"  # shared mutable state
    UNSAFE_COMMIT = "UNSAFE_COMMIT"  # commit/push — single executor
    UNSAFE_DEPLOY = "UNSAFE_DEPLOY"   # deploy — single executor
    UNSAFE_DESTRUCTIVE = "UNSAFE_DESTRUCTIVE"  # destructive — single executor + approval
    UNSAFE_EXTERNAL = "UNSAFE_EXTERNAL"  # external sends — approval gated
    UNSAFE_SECRETS = "UNSAFE_SECRETS"    # secrets/IAM — hard gate
    SEQUENTIAL_DEPENDENCY = "SEQUENTIAL_DEPENDENCY"  # depends on prior output


@dataclass(frozen=True)
class TaskSafetyRule:
    action_type: str
    safety: ParallelSafety
    reason: str
    lock_required: bool = False
    approval_required: bool = False


PARALLEL_SAFETY_RULES: List[TaskSafetyRule] = [
    # Safe to parallelize
    TaskSafetyRule("retrieval", ParallelSafety.SAFE, "Reads only; independent"),
    TaskSafetyRule("file_read", ParallelSafety.SAFE, "Reads only; independent"),
    TaskSafetyRule("log_read", ParallelSafety.SAFE, "Reads only; independent"),
    TaskSafetyRule("docs_search", ParallelSafety.SAFE, "Reads only; independent"),
    TaskSafetyRule("independent_analysis", ParallelSafety.SAFE, "No shared state; independent"),
    TaskSafetyRule("test_discovery", ParallelSafety.SAFE, "Read-only; independent"),
    TaskSafetyRule("validation_planning", ParallelSafety.SAFE, "No writes; independent"),
    TaskSafetyRule("independent_review", ParallelSafety.SAFE, "No writes; independent"),
    TaskSafetyRule("patch_proposal", ParallelSafety.SAFE, "Worker produces proposal; no master write"),
    TaskSafetyRule("web_research", ParallelSafety.SAFE, "Independent external reads"),

    # Unsafe / single executor
    TaskSafetyRule("same_file_master_write", ParallelSafety.UNSAFE_STATE,
                   "Single master file; only batch integrator writes", lock_required=True),
    TaskSafetyRule("git_commit", ParallelSafety.UNSAFE_COMMIT,
                   "Single active commit executor", lock_required=True),
    TaskSafetyRule("git_push", ParallelSafety.UNSAFE_COMMIT,
                   "Single active push executor; secret scan required", lock_required=True),
    TaskSafetyRule("deploy_execute", ParallelSafety.UNSAFE_DEPLOY,
                   "Single deploy executor; Bryan approval required",
                   lock_required=True, approval_required=True),
    TaskSafetyRule("iam_change", ParallelSafety.UNSAFE_SECRETS,
                   "Hard gate; Bryan approval required", lock_required=True, approval_required=True),
    TaskSafetyRule("secret_write", ParallelSafety.UNSAFE_SECRETS,
                   "Hard gate; Bryan approval required", lock_required=True, approval_required=True),
    TaskSafetyRule("external_send", ParallelSafety.UNSAFE_EXTERNAL,
                   "Approval gated; Bryan must approve", approval_required=True),
    TaskSafetyRule("destructive_data_op", ParallelSafety.UNSAFE_DESTRUCTIVE,
                   "Hard gate; Bryan approval required", lock_required=True, approval_required=True),
    TaskSafetyRule("production_deploy", ParallelSafety.UNSAFE_DEPLOY,
                   "Hard gate; Bryan approval required", lock_required=True, approval_required=True),
    TaskSafetyRule("shared_config_write", ParallelSafety.UNSAFE_STATE,
                   "Shared config; serialize writes", lock_required=True),
]


@dataclass
class ParallelDAGPolicy:
    """Policy for dependency-aware parallel orchestration."""
    policy_id: str = "plan9_parallel_dag"
    description: str = "Plan 9 safe parallel execution policy"
    safety_rules: List[TaskSafetyRule] = field(default_factory=lambda: PARALLEL_SAFETY_RULES)

    def get_safety(self, action_type: str) -> ParallelSafety:
        for rule in self.safety_rules:
            if rule.action_type == action_type:
                return rule.safety
        return ParallelSafety.SEQUENTIAL_DEPENDENCY  # unknown = assume sequential

    def is_safe_to_parallelize(self, action_type: str) -> bool:
        return self.get_safety(action_type) == ParallelSafety.SAFE

    def requires_lock(self, action_type: str) -> bool:
        for rule in self.safety_rules:
            if rule.action_type == action_type:
                return rule.lock_required
        return False

    def requires_approval(self, action_type: str) -> bool:
        for rule in self.safety_rules:
            if rule.action_type == action_type:
                return rule.approval_required
        return False


# ============================================================================
# Section 10 — Elastic Same-Role Worker Pools
# ============================================================================

@dataclass(frozen=True)
class ElasticPoolPolicy:
    """Policy for elastic same-role worker pool scaling."""
    role_id: str
    scaling_allowed: bool
    max_workers: int
    single_executor_only: bool          # True for commits/deploys
    shard_dimensions: tuple              # how to shard work
    scale_factors: tuple                 # what influences scale decision
    lock_required_for_writes: bool
    notes: str = ""


ELASTIC_POOL_POLICIES: Dict[str, ElasticPoolPolicy] = {
    # Scale allowed
    "retrieval_worker": ElasticPoolPolicy(
        role_id="retrieval_worker",
        scaling_allowed=True,
        max_workers=10,
        single_executor_only=False,
        shard_dimensions=("file", "domain", "evidence_source"),
        scale_factors=("task_count", "token_budget", "time_urgency"),
        lock_required_for_writes=False,
        notes="Retrieval workers are fully independent; scale freely",
    ),
    "backend_worker": ElasticPoolPolicy(
        role_id="backend_worker",
        scaling_allowed=True,
        max_workers=5,
        single_executor_only=False,
        shard_dimensions=("file", "module", "function", "feature"),
        scale_factors=("task_independence", "same_file_conflict_risk"),
        lock_required_for_writes=True,
        notes="Scale by module/file; same-file writes go through batch integrator",
    ),
    "frontend_worker": ElasticPoolPolicy(
        role_id="frontend_worker",
        scaling_allowed=True,
        max_workers=5,
        single_executor_only=False,
        shard_dimensions=("component", "page", "feature"),
        scale_factors=("task_independence", "same_file_conflict_risk"),
        lock_required_for_writes=True,
        notes="Scale by component; same-file writes go through batch integrator",
    ),
    "test_worker": ElasticPoolPolicy(
        role_id="test_worker",
        scaling_allowed=True,
        max_workers=8,
        single_executor_only=False,
        shard_dimensions=("test_group", "module", "domain"),
        scale_factors=("test_count", "independence"),
        lock_required_for_writes=False,
        notes="Test workers are independent; scale freely by test group",
    ),
    "debug_worker": ElasticPoolPolicy(
        role_id="debug_worker",
        scaling_allowed=True,
        max_workers=3,
        single_executor_only=False,
        shard_dimensions=("error_category", "module", "risk_area"),
        scale_factors=("error_count",),
        lock_required_for_writes=False,
        notes="Debug workers analyze independently; moderate scale",
    ),
    "unit_test_worker": ElasticPoolPolicy(
        role_id="unit_test_worker",
        scaling_allowed=True,
        max_workers=8,
        single_executor_only=False,
        shard_dimensions=("module", "test_file"),
        scale_factors=("test_count",),
        lock_required_for_writes=False,
    ),
    "integration_test_worker": ElasticPoolPolicy(
        role_id="integration_test_worker",
        scaling_allowed=True,
        max_workers=4,
        single_executor_only=False,
        shard_dimensions=("integration_domain",),
        scale_factors=("integration_count", "dependency_graph"),
        lock_required_for_writes=False,
    ),
    "local_research_worker": ElasticPoolPolicy(
        role_id="local_research_worker",
        scaling_allowed=True,
        max_workers=6,
        single_executor_only=False,
        shard_dimensions=("research_domain", "evidence_source"),
        scale_factors=("query_count",),
        lock_required_for_writes=False,
    ),
    "documentation_worker": ElasticPoolPolicy(
        role_id="documentation_worker",
        scaling_allowed=True,
        max_workers=5,
        single_executor_only=False,
        shard_dimensions=("doc_section", "file"),
        scale_factors=("doc_count", "same_file_conflict_risk"),
        lock_required_for_writes=True,
        notes="Doc writes go through batch integrator for same-file items",
    ),
    # Single executor only
    "git_commit_worker": ElasticPoolPolicy(
        role_id="git_commit_worker",
        scaling_allowed=False,
        max_workers=1,
        single_executor_only=True,
        shard_dimensions=(),
        scale_factors=(),
        lock_required_for_writes=True,
        notes="SINGLE EXECUTOR ONLY. No parallel commits. Lock required.",
    ),
    "release_packaging_worker": ElasticPoolPolicy(
        role_id="release_packaging_worker",
        scaling_allowed=False,
        max_workers=1,
        single_executor_only=True,
        shard_dimensions=(),
        scale_factors=(),
        lock_required_for_writes=True,
        notes="SINGLE EXECUTOR ONLY. Deploy/release is sequential with Bryan approval.",
    ),
    "secret_safety_worker": ElasticPoolPolicy(
        role_id="secret_safety_worker",
        scaling_allowed=False,
        max_workers=1,
        single_executor_only=True,
        shard_dimensions=(),
        scale_factors=(),
        lock_required_for_writes=True,
        notes="SINGLE EXECUTOR ONLY. Secret scan must be atomic.",
    ),
    "runtime_ops_worker": ElasticPoolPolicy(
        role_id="runtime_ops_worker",
        scaling_allowed=False,
        max_workers=1,
        single_executor_only=True,
        shard_dimensions=(),
        scale_factors=(),
        lock_required_for_writes=True,
        notes="SINGLE EXECUTOR ONLY for destructive ops. Reads can scale.",
    ),
}

# Default elastic pool policy for roles not explicitly listed
DEFAULT_ELASTIC_POOL = ElasticPoolPolicy(
    role_id="__default__",
    scaling_allowed=True,
    max_workers=3,
    single_executor_only=False,
    shard_dimensions=("domain", "task"),
    scale_factors=("task_independence", "risk", "token_budget"),
    lock_required_for_writes=True,
    notes="Default: scale up to 3 workers; lock writes; shard by domain",
)


# ============================================================================
# Section 11 — Same-File Batch Integration Protocol
# ============================================================================

@dataclass
class PatchProposal:
    """Structured patch proposal from a single worker for a single item."""
    worker_id: str
    item_id: str                  # which acceptance item this patch covers
    target_file: str
    target_section: str           # function/class/section ownership
    diff_hunk: str                # the actual change
    risk_notes: str
    tests_needed: List[str]
    non_overlapping_assertion: str  # worker's claim that this hunk doesn't overlap others
    metadata: Dict = field(default_factory=dict)


@dataclass
class IntegratedPatch:
    """Result of Batch Integration Manager combining all worker patches."""
    target_file: str
    integrated_diff: str
    included_items: List[str]    # item_ids included
    dropped_patches: List[str]   # any dropped with reason
    conflict_resolution_notes: str
    style_normalized: bool
    imports_normalized: bool


@dataclass
class IntegrationReviewResult:
    """Result of Integration Review Manager independently verifying the batch."""
    verdict: str                  # PASS | FAIL
    all_items_present: bool
    dropped_items: List[str]
    conflicts_resolved: bool
    conflicts_unresolved: List[str]
    tests_passing: bool
    formatting_ok: bool
    no_regression: bool
    no_security_issue: bool
    no_secret: bool
    notes: str = ""


@dataclass(frozen=True)
class BatchIntegrationPolicy:
    """Policy for same-file batch integration (Batch Integration Manager role)."""
    policy_id: str = "plan9_batch_integration"

    # Roles
    integrator_role: str = "batch_integration_manager"
    reviewer_role: str = "integration_review_manager"

    # Rules
    max_concurrent_master_writes: int = 1
    workers_propose_in_parallel: bool = True   # workers can draft in parallel
    integration_is_sequential: bool = True     # integration is single-executor
    review_is_independent: bool = True         # reviewer != integrator

    # Conflict handling
    compatible_hunks_batch: bool = True        # non-overlapping → batch merge
    overlapping_hunks_sequential: bool = True  # overlapping → sequential

    # Validation
    all_items_must_appear_in_final: bool = True
    no_patch_may_be_dropped_silently: bool = True
    style_normalization_required: bool = True
    tests_required_after_integration: bool = True


@dataclass
class IntegrationReviewPolicy:
    """Policy for integration review (Integration Review Manager role)."""
    policy_id: str = "plan9_integration_review"
    reviewer_must_differ_from_integrator: bool = True
    must_verify_all_items: bool = True
    must_verify_no_dropped_patches: bool = True
    must_verify_overlap_resolution: bool = True
    must_verify_tests_pass: bool = True
    must_verify_no_regression: bool = True
    must_verify_no_secret: bool = True
    verdict_options: tuple = ("PASS", "FAIL")


# ============================================================================
# Combined orchestration policy registry
# ============================================================================

PLAN9_ORCHESTRATION_POLICIES = {
    "retrieval": {pid: p for pid, p in RETRIEVAL_WORKER_POLICIES.items()},
    "parallel_dag": ParallelDAGPolicy(),
    "elastic_pools": ELASTIC_POOL_POLICIES,
    "batch_integration": BatchIntegrationPolicy(),
    "integration_review": IntegrationReviewPolicy(),
}


def get_orchestration_policy(policy_type: str):
    return PLAN9_ORCHESTRATION_POLICIES.get(policy_type)
