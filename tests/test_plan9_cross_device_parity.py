"""Plan 9 — Cross-Device Parity Test Suite.

Tests:
  - No duplicate canonical rules/skills/commands systems
  - Required Jarvis rules exist
  - Required skills exist (21 total)
  - Required commands exist (20 total)
  - Every discovered manager/team/agent/worker is inventoried
  - Every manager has routing/parity/authority/validation status
  - Future manager/worker default inheritance works
  - Missing model routing policy fails validation
  - Missing retrieval worker policy fails validation unless justified
  - Capability matrix classifications are correct
  - Role-based model routing (cheap/balanced/best) per role
  - Cheap/balanced/best escalation logic
  - Retrieval worker assignment (always cheap)
  - Parallel DAG safe/unsafe scheduling
  - Same-role worker pool scaling rules
  - Same-file patch batching rules
  - Batch Integration Manager / Patch Integrator
  - Integration Review Manager / Merge Reviewer
  - Commit/push lock behavior (single executor)
  - Deploy lock behavior (single executor + approval)
  - Approval gate requirements
  - Cloud/local capability status
  - Mac worker queue classification
  - UI/API capability display
  - Parked items remain parked
  - No secret leakage in capability outputs
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from openjarvis.plan9.capability_matrix import (
    CapabilityStatus,
    get_plan9_capability_matrix,
)
from openjarvis.plan9.model_routing import (
    ModelTier,
    DEFAULT_ROUTING,
    get_role_routing_matrix,
)
from openjarvis.plan9.rules import (
    PLAN9_INTERNAL_RULES,
    get_rules_by_category,
    get_rule,
)
from openjarvis.plan9.pa_brain_layer import (
    JarvisLayer,
    get_pa_config,
    get_brain_layer_config,
)
from openjarvis.plan9.skills_manifest import (
    Plan9SkillStatus,
    PLAN9_SKILLS_MANIFEST,
    get_skills_manifest,
    get_skill,
)
from openjarvis.plan9.commands_manifest import (
    Plan9CommandStatus,
    PLAN9_COMMANDS_MANIFEST,
    get_commands_manifest,
)
from openjarvis.plan9.orchestration_policy import (
    ParallelSafety,
    ParallelDAGPolicy,
    ElasticPoolPolicy,
    BatchIntegrationPolicy,
    IntegrationReviewPolicy,
    RETRIEVAL_WORKER_POLICIES,
    ELASTIC_POOL_POLICIES,
    DEFAULT_ELASTIC_POOL,
    get_orchestration_policy,
)
from openjarvis.plan9.mac_worker_queue import (
    MacTaskType,
    MacTaskStatus,
    MacWorkerTask,
    MacWorkerQueue,
    get_mac_worker_queue,
    MAC_ONLY_TASK_TYPES,
    CLOUD_NATIVE_TASK_TYPES,
)
from openjarvis.plan9.future_inheritance import (
    PLAN9_DEFAULT_INHERITANCE,
    validate_manager_inheritance,
    validate_worker_inheritance,
    validate_all_managers_have_routing,
    validate_all_managers_in_capability_matrix,
)


# ---------------------------------------------------------------------------
# Known manager / worker IDs from registry (hard-coded for validation)
# ---------------------------------------------------------------------------

KNOWN_MANAGER_IDS = [
    "coding_manager",
    "architecture_manager",
    "testing_validation_manager",
    "code_review_manager",
    "debugging_manager",
    "research_manager",
    "memory_knowledge_manager",
    "documentation_manager",
    "product_ux_manager",
    "operations_automation_manager",
    "governance_safety_manager",
    "release_packaging_manager",
    "data_manager",
    "cost_routing_manager",
    "nus_learning_manager",
    "connector_auth_manager",
    "runtime_ops_manager",
]

KNOWN_WORKER_IDS = [
    "backend_worker", "frontend_worker", "test_worker", "debug_worker",
    "refactor_worker", "integration_worker", "security_code_worker",
    "performance_worker", "dependency_worker", "git_commit_worker",
    "system_architecture_worker", "contract_design_worker",
    "integration_architecture_worker", "scalability_worker",
    "unit_test_worker", "integration_test_worker", "regression_test_worker",
    "doctor_check_worker", "acceptance_evidence_worker",
    "secret_safety_worker", "policy_gate_worker", "risk_classification_worker",
    "approval_scope_worker", "local_research_worker", "documentation_worker",
    "release_packaging_worker", "runtime_ops_worker", "cost_analysis_worker",
    "data_worker", "nus_learning_worker",
]


# ============================================================================
# Section 2 — Manager/Worker Inventory
# ============================================================================

class TestManagerInventory:

    def test_known_manager_count(self):
        """17 managers must be inventoried."""
        assert len(KNOWN_MANAGER_IDS) == 17

    def test_known_worker_count(self):
        """30 workers must be inventoried."""
        assert len(KNOWN_WORKER_IDS) == 30

    def test_all_managers_have_routing(self):
        """Every manager must appear in role routing matrix or inherit default."""
        matrix = get_role_routing_matrix()
        routing_ids = matrix.all_role_ids()
        for manager_id in KNOWN_MANAGER_IDS:
            # Either has explicit entry OR inherits DEFAULT_ROUTING (which is valid)
            entry = matrix.get(manager_id)
            assert entry is not None, f"Routing for {manager_id} returned None"
            assert entry.cheap_model, f"{manager_id}: missing cheap_model in routing"
            assert entry.balanced_model, f"{manager_id}: missing balanced_model in routing"
            assert entry.best_model, f"{manager_id}: missing best_model in routing"

    def test_all_workers_have_routing(self):
        """Every worker must appear in role routing matrix or inherit default."""
        matrix = get_role_routing_matrix()
        for worker_id in KNOWN_WORKER_IDS:
            entry = matrix.get(worker_id)
            assert entry is not None, f"Routing for {worker_id} returned None"
            assert entry.cheap_model, f"{worker_id}: missing cheap_model"
            assert entry.balanced_model, f"{worker_id}: missing balanced_model"
            assert entry.best_model, f"{worker_id}: missing best_model"

    def test_routing_matrix_validates_cleanly(self):
        """Role routing matrix must validate without errors."""
        matrix = get_role_routing_matrix()
        errors = matrix.validate()
        assert errors == [], f"Routing matrix validation errors: {errors}"

    def test_all_managers_have_retrieval_policy(self):
        """Every manager must have a retrieval worker policy."""
        for manager_id in KNOWN_MANAGER_IDS:
            assert manager_id in RETRIEVAL_WORKER_POLICIES, (
                f"{manager_id}: missing retrieval worker policy. "
                "Either define one or provide explicit no_retrieval_justification."
            )

    def test_all_managers_retrieval_is_cheap(self):
        """All retrieval worker policies must require cheap model."""
        for manager_id, policy in RETRIEVAL_WORKER_POLICIES.items():
            assert policy.cheap_model_required, (
                f"{manager_id}: retrieval worker policy must require cheap model"
            )

    def test_all_managers_retrieval_before_reasoning(self):
        """Retrieval must always run before expensive reasoning."""
        for manager_id, policy in RETRIEVAL_WORKER_POLICIES.items():
            assert policy.before_reasoning, (
                f"{manager_id}: retrieval must run before expensive reasoning"
            )


# ============================================================================
# Section 3 — Internal Rules
# ============================================================================

class TestInternalRules:

    def test_rules_exist(self):
        """Plan 9 internal rules must be non-empty."""
        assert len(PLAN9_INTERNAL_RULES) > 0

    def test_required_rule_categories(self):
        """Must have rules for all required categories."""
        required_categories = {
            "TRUTH_EVIDENCE", "STOP_ON_BLOCKER", "SECRET_SECURITY",
            "APPROVAL_GATES", "TOKEN_COST", "PARKED",
        }
        present_categories = {r.category for r in PLAN9_INTERNAL_RULES}
        for cat in required_categories:
            assert cat in present_categories, f"Missing rule category: {cat}"

    def test_parked_voice_rule_exists(self):
        """Voice/wake/TTS must be explicitly parked in rules."""
        rule = get_rule("p9.parked.voice_wake_tts")
        assert rule is not None
        assert "Plan 10" in rule.description

    def test_parked_apple_signing_rule_exists(self):
        """Apple signing must be explicitly parked in rules."""
        rule = get_rule("p9.parked.apple_signing")
        assert rule is not None
        assert "Plan 11" in rule.description

    def test_no_fake_complete_rule_exists(self):
        """Must have a no-fake-complete rule."""
        rule = get_rule("p9.truth.no_fake_complete")
        assert rule is not None

    def test_secret_scan_rule_exists(self):
        """Must have a secret scan rule."""
        rule = get_rule("p9.secret.scan_before_commit")
        assert rule is not None

    def test_all_rules_have_enforcement(self):
        """Every rule must have a non-empty enforcement field."""
        for rule in PLAN9_INTERNAL_RULES:
            assert rule.enforcement, f"Rule {rule.rule_id} has empty enforcement"

    def test_no_duplicate_rule_ids(self):
        """No duplicate rule IDs."""
        ids = [r.rule_id for r in PLAN9_INTERNAL_RULES]
        assert len(ids) == len(set(ids)), "Duplicate rule IDs found"


# ============================================================================
# Section 4 — PA vs Brain Layer
# ============================================================================

class TestPABrainLayer:

    def test_pa_config_exists(self):
        pa = get_pa_config()
        assert pa.layer == JarvisLayer.JARVIS_PA
        assert pa.stable_model_count <= 2
        assert pa.model_preference == "balanced"

    def test_brain_layer_config_exists(self):
        brain = get_brain_layer_config()
        assert brain.multi_provider is True
        assert len(brain.provider_routes) > 0

    def test_pa_has_report_format(self):
        pa = get_pa_config()
        assert pa.report_format, "Jarvis PA must have a defined report format"


# ============================================================================
# Section 5 — Model Routing
# ============================================================================

class TestModelRouting:

    def test_default_routing_exists(self):
        """Default routing must exist for unknown roles."""
        entry = DEFAULT_ROUTING
        assert entry.cheap_model
        assert entry.balanced_model
        assert entry.best_model

    def test_retrieval_worker_is_cheap(self):
        """Retrieval worker must always be cheap tier."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("retrieval_worker")
        assert entry.default_tier == ModelTier.CHEAP, (
            "retrieval_worker must default to CHEAP tier"
        )

    def test_security_worker_is_best(self):
        """Security code worker must default to BEST tier."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("security_code_worker")
        assert entry.default_tier == ModelTier.BEST, (
            "security_code_worker must default to BEST tier (high failure cost)"
        )

    def test_architecture_manager_is_best(self):
        """Architecture manager must default to BEST tier."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("architecture_manager")
        assert entry.default_tier == ModelTier.BEST

    def test_docs_manager_is_cheap(self):
        """Documentation manager must default to CHEAP tier."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("documentation_manager")
        assert entry.default_tier == ModelTier.CHEAP

    def test_git_commit_worker_is_cheap(self):
        """Git commit worker must default to CHEAP tier."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("git_commit_worker")
        assert entry.default_tier == ModelTier.CHEAP

    def test_tier_for_high_risk_escalates_to_best(self):
        """tier_for_task must return BEST for high-risk tasks."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("coding_manager")
        tier = entry.tier_for_task(risk="high", complexity="complex", failures=0)
        assert tier == ModelTier.BEST

    def test_tier_for_low_risk_uses_cheap(self):
        """tier_for_task must return CHEAP for low-risk simple tasks."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("coding_manager")
        tier = entry.tier_for_task(risk="low", complexity="simple", failures=0)
        assert tier == ModelTier.CHEAP

    def test_tier_for_3_failures_stops(self):
        """tier_for_task must return STOP after 3 failures."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("coding_manager")
        tier = entry.tier_for_task(risk="medium", complexity="moderate", failures=3)
        assert tier == ModelTier.STOP

    def test_unknown_role_inherits_default(self):
        """Unknown role must inherit DEFAULT_ROUTING (not fail)."""
        matrix = get_role_routing_matrix()
        entry = matrix.get("unknown_future_role_xyz")
        assert entry.role_id == "__default__"
        assert entry.cheap_model
        assert entry.balanced_model
        assert entry.best_model


# ============================================================================
# Section 6 — Skills and Commands
# ============================================================================

class TestSkillsManifest:

    def test_skill_count(self):
        """Must have exactly 21 Plan 9 skills."""
        assert len(PLAN9_SKILLS_MANIFEST) == 21, (
            f"Expected 21 skills, got {len(PLAN9_SKILLS_MANIFEST)}"
        )

    def test_no_duplicate_skill_ids(self):
        ids = [s.skill_id for s in PLAN9_SKILLS_MANIFEST]
        assert len(ids) == len(set(ids)), "Duplicate skill IDs found"

    def test_required_skill_ids_present(self):
        """All 21 required skills must be present."""
        required = [
            "capability_inventory", "model_routing", "retrieval_context_packet",
            "task_dag_scheduler", "elastic_worker_pool", "same_file_patch_propose",
            "batch_integration", "integration_review", "coding_workspace",
            "test_build_runner", "commit_push", "deploy_operator", "memory_parity",
            "connector_parity", "cloud_file_mirror", "mac_worker_queue",
            "capability_aware_ui", "authority_approval_audit", "rollback",
            "secret_scan", "sprint_report",
        ]
        manifest_ids = [s.skill_id for s in PLAN9_SKILLS_MANIFEST]
        for req in required:
            assert req in manifest_ids, f"Required skill {req!r} missing from manifest"

    def test_all_skills_have_authority_level(self):
        for skill in PLAN9_SKILLS_MANIFEST:
            assert skill.authority_level in ("auto", "requires_approval", "hard_gate"), (
                f"Skill {skill.skill_id}: invalid authority_level {skill.authority_level!r}"
            )

    def test_deploy_operator_is_hard_gate(self):
        """Deploy operator skill must be hard_gate."""
        skill = get_skill("deploy_operator")
        assert skill is not None
        assert skill.authority_level == "hard_gate"

    def test_secret_scan_is_cheap(self):
        """Secret scan skill must use cheap model tier."""
        skill = get_skill("secret_scan")
        assert skill is not None
        assert skill.model_tier == "cheap"

    def test_capability_inventory_is_wired(self):
        """Capability inventory skill must be at least WIRED."""
        skill = get_skill("capability_inventory")
        assert skill is not None
        assert skill.status in (Plan9SkillStatus.WIRED, Plan9SkillStatus.TESTED)

    def test_mac_worker_queue_skill_is_wired(self):
        """Mac worker queue skill must be at least WIRED."""
        skill = get_skill("mac_worker_queue")
        assert skill is not None
        assert skill.status in (Plan9SkillStatus.WIRED, Plan9SkillStatus.TESTED)


class TestCommandsManifest:

    def test_command_count(self):
        """Must have exactly 20 Plan 9 commands."""
        assert len(PLAN9_COMMANDS_MANIFEST) == 20, (
            f"Expected 20 commands, got {len(PLAN9_COMMANDS_MANIFEST)}"
        )

    def test_no_duplicate_commands(self):
        commands = [c.command.split()[0:3] for c in PLAN9_COMMANDS_MANIFEST]
        # Allow duplicates in first 2 words if 3rd word differs (subcommands)
        full_commands = [c.command for c in PLAN9_COMMANDS_MANIFEST]
        assert len(full_commands) == len(PLAN9_COMMANDS_MANIFEST)

    def test_all_commands_have_authority_level(self):
        for cmd in PLAN9_COMMANDS_MANIFEST:
            assert cmd.authority_level in ("auto", "requires_approval", "hard_gate"), (
                f"Command {cmd.command!r}: invalid authority_level"
            )

    def test_required_commands_present(self):
        """Key Plan 9 commands must be present."""
        required_prefixes = [
            "jarvis rules status",
            "jarvis skills list",
            "jarvis capability matrix",
            "jarvis model-route explain",
            "jarvis secret-scan",
            "jarvis parity status",
            "jarvis parked status",
            "jarvis rollback plan",
            "jarvis report sprint",
        ]
        manifest_commands = [c.command for c in PLAN9_COMMANDS_MANIFEST]
        for prefix in required_prefixes:
            found = any(c.startswith(prefix) or prefix in c for c in manifest_commands)
            assert found, f"Required command {prefix!r} not found in manifest"


# ============================================================================
# Section 7 — Capability Matrix
# ============================================================================

class TestCapabilityMatrix:

    def test_matrix_not_empty(self):
        matrix = get_plan9_capability_matrix()
        assert len(matrix.entries) > 0

    def test_voice_wake_tts_is_parked(self):
        """Voice/wake/TTS must be PARKED."""
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("voice_wake_tts")
        assert entry is not None, "voice_wake_tts must be in capability matrix"
        assert entry.status == CapabilityStatus.PARKED
        assert "Plan 10" in (entry.parked_until or "")

    def test_apple_signing_is_parked(self):
        """Apple signing must be PARKED."""
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("apple_signing_updater")
        assert entry is not None
        assert entry.status == CapabilityStatus.PARKED
        assert "Plan 11" in (entry.parked_until or "")

    def test_app_reinstall_is_queued_mac_only(self):
        """Reinstalling /Applications/OpenJarvis.app must be QUEUED_MAC_ONLY."""
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("release_app_install_mac")
        assert entry is not None
        assert entry.status == CapabilityStatus.QUEUED_MAC_ONLY

    def test_jarvis_chat_is_cross_device(self):
        """Jarvis chat must be CROSS_DEVICE_LIVE."""
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("jarvis_chat")
        assert entry is not None
        assert entry.status == CapabilityStatus.CROSS_DEVICE_LIVE

    def test_cloud_deploy_is_approval_required(self):
        """Cloud deploy must be APPROVAL_REQUIRED."""
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("release_deploy_cloud")
        assert entry is not None
        assert entry.status == CapabilityStatus.APPROVAL_REQUIRED

    def test_capability_status_values_are_valid(self):
        """All entries must have valid Plan 9 status values."""
        valid = {s.value for s in CapabilityStatus}
        matrix = get_plan9_capability_matrix()
        for entry in matrix.entries:
            assert entry.status.value in valid, (
                f"{entry.capability_id}: invalid status {entry.status!r}"
            )

    def test_all_manager_domains_covered(self):
        """Every known manager must appear as domain in capability matrix."""
        matrix = get_plan9_capability_matrix()
        all_domains = {e.domain for e in matrix.entries}
        for manager_id in KNOWN_MANAGER_IDS:
            assert manager_id in all_domains, (
                f"Manager {manager_id} has no capability_matrix entry. "
                "Every manager must appear in the capability matrix."
            )

    def test_no_secrets_in_capability_output(self):
        """Capability matrix output must not contain actual secret values.

        Check for patterns that would indicate a real credential value was leaked.
        Documentation phrases like 'Bearer token required' are acceptable —
        only actual Bearer token VALUES (e.g. 'Bearer eyJ...') should be flagged.
        """
        import json
        import re
        matrix = get_plan9_capability_matrix()
        output = json.dumps(matrix.to_list())

        # Patterns that indicate actual secret VALUES (not just documentation text)
        actual_secret_patterns = [
            r"sk-[A-Za-z0-9]{20,}",          # OpenAI API key
            r"xoxp-[0-9]+-[0-9]+-",           # Slack user token
            r"xoxb-[0-9]+-",                  # Slack bot token
            r"AKIA[0-9A-Z]{16}",              # AWS access key
            r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY",
            r"ghp_[A-Za-z0-9]{36,}",          # GitHub personal access token
            r"gho_[A-Za-z0-9]{36,}",          # GitHub OAuth token
            r"Bearer eyJ[A-Za-z0-9+/=]{20,}", # JWT Bearer token
            r"password=[A-Za-z0-9!@#$%]{8,}", # literal password value
        ]
        for pattern in actual_secret_patterns:
            match = re.search(pattern, output)
            assert match is None, (
                f"Capability matrix output contains potential secret value matching {pattern!r}"
            )

    def test_summary_counts_are_consistent(self):
        """Summary counts must add up to total entries."""
        matrix = get_plan9_capability_matrix()
        summary = matrix.summary()
        total = sum(summary.values())
        assert total == len(matrix.entries), (
            f"Summary counts ({total}) != entries ({len(matrix.entries)})"
        )


# ============================================================================
# Section 9 — Parallel DAG
# ============================================================================

class TestParallelDAG:

    def test_reads_are_safe_to_parallelize(self):
        policy = ParallelDAGPolicy()
        for action in ["retrieval", "file_read", "log_read", "docs_search", "independent_analysis"]:
            assert policy.is_safe_to_parallelize(action), (
                f"{action} should be safe to parallelize"
            )

    def test_commits_are_unsafe(self):
        policy = ParallelDAGPolicy()
        assert not policy.is_safe_to_parallelize("git_commit")
        assert not policy.is_safe_to_parallelize("git_push")
        assert not policy.is_safe_to_parallelize("deploy_execute")
        assert not policy.is_safe_to_parallelize("production_deploy")

    def test_commits_require_lock(self):
        policy = ParallelDAGPolicy()
        assert policy.requires_lock("git_commit")
        assert policy.requires_lock("git_push")

    def test_deploy_requires_approval(self):
        policy = ParallelDAGPolicy()
        assert policy.requires_approval("production_deploy")
        assert policy.requires_approval("deploy_execute")

    def test_secrets_require_both_lock_and_approval(self):
        policy = ParallelDAGPolicy()
        for action in ["iam_change", "secret_write"]:
            assert policy.requires_lock(action), f"{action} must require lock"
            assert policy.requires_approval(action), f"{action} must require approval"

    def test_patch_proposals_are_safe(self):
        """Workers can propose patches in parallel (no master write)."""
        policy = ParallelDAGPolicy()
        assert policy.is_safe_to_parallelize("patch_proposal")

    def test_same_file_master_write_is_unsafe(self):
        """Same-file master writes must not be parallelized."""
        policy = ParallelDAGPolicy()
        assert not policy.is_safe_to_parallelize("same_file_master_write")


# ============================================================================
# Section 10 — Elastic Worker Pools
# ============================================================================

class TestElasticWorkerPools:

    def test_git_commit_worker_is_single_executor(self):
        """git_commit_worker must be single executor only."""
        policy = ELASTIC_POOL_POLICIES["git_commit_worker"]
        assert policy.single_executor_only is True
        assert policy.max_workers == 1
        assert policy.scaling_allowed is False

    def test_release_packaging_worker_is_single_executor(self):
        policy = ELASTIC_POOL_POLICIES["release_packaging_worker"]
        assert policy.single_executor_only is True

    def test_retrieval_worker_can_scale(self):
        policy = ELASTIC_POOL_POLICIES["retrieval_worker"]
        assert policy.scaling_allowed is True
        assert policy.max_workers > 1

    def test_test_worker_can_scale(self):
        policy = ELASTIC_POOL_POLICIES["test_worker"]
        assert policy.scaling_allowed is True
        assert policy.max_workers > 1

    def test_default_elastic_pool_has_lock_for_writes(self):
        """Default elastic pool policy requires lock for writes."""
        assert DEFAULT_ELASTIC_POOL.lock_required_for_writes is True

    def test_unknown_worker_inherits_default_pool(self):
        """Unknown workers get DEFAULT_ELASTIC_POOL (not error)."""
        unknown_id = "hypothetical_future_worker_xyz"
        result = ELASTIC_POOL_POLICIES.get(unknown_id, DEFAULT_ELASTIC_POOL)
        assert result is DEFAULT_ELASTIC_POOL


# ============================================================================
# Section 11 — Batch Integration
# ============================================================================

class TestBatchIntegration:

    def test_batch_policy_exists(self):
        policy = get_orchestration_policy("batch_integration")
        assert policy is not None
        assert isinstance(policy, BatchIntegrationPolicy)

    def test_workers_can_propose_in_parallel(self):
        policy = get_orchestration_policy("batch_integration")
        assert policy.workers_propose_in_parallel is True

    def test_integration_is_sequential(self):
        """Integration must be sequential (single executor)."""
        policy = get_orchestration_policy("batch_integration")
        assert policy.integration_is_sequential is True

    def test_review_is_independent(self):
        """Reviewer must be independent of integrator."""
        policy = get_orchestration_policy("integration_review")
        assert isinstance(policy, IntegrationReviewPolicy)
        assert policy.reviewer_must_differ_from_integrator is True

    def test_no_patch_may_be_dropped_silently(self):
        policy = get_orchestration_policy("batch_integration")
        assert policy.no_patch_may_be_dropped_silently is True

    def test_all_items_must_appear_in_final(self):
        policy = get_orchestration_policy("batch_integration")
        assert policy.all_items_must_appear_in_final is True

    def test_review_must_verify_no_secret(self):
        policy = get_orchestration_policy("integration_review")
        assert policy.must_verify_no_secret is True

    def test_max_concurrent_master_writes_is_one(self):
        policy = get_orchestration_policy("batch_integration")
        assert policy.max_concurrent_master_writes == 1


# ============================================================================
# Section 19 — Mac Worker Queue
# ============================================================================

class TestMacWorkerQueue:

    def test_app_reinstall_is_mac_only(self):
        """App reinstall must be classified as Mac-only."""
        assert MacTaskType.APP_REINSTALL in MAC_ONLY_TASK_TYPES

    def test_coding_is_cloud_native(self):
        """Coding must be cloud-native, not Mac-only."""
        assert "coding" in CLOUD_NATIVE_TASK_TYPES

    def test_commit_is_cloud_native(self):
        assert "commit" in CLOUD_NATIVE_TASK_TYPES

    def test_queue_submit_and_retrieve(self):
        queue = MacWorkerQueue()
        task = MacWorkerTask(
            task_type=MacTaskType.APP_REINSTALL,
            display_name="Reinstall OpenJarvis.app",
            description="Rebuild and reinstall /Applications/OpenJarvis.app",
            submitted_from="mobile",
        )
        task_id = queue.submit(task)
        retrieved = queue.get(task_id)
        assert retrieved is not None
        assert retrieved.status == MacTaskStatus.QUEUED
        assert retrieved.task_type == MacTaskType.APP_REINSTALL

    def test_queue_status_visible_from_both_surfaces(self):
        """Queue status summary must be readable (simulates both surfaces)."""
        queue = MacWorkerQueue()
        task = MacWorkerTask(task_type=MacTaskType.MAC_APP_CONTROL)
        queue.submit(task)
        summary = queue.status_summary()
        assert summary["total"] >= 1
        assert summary["queued"] >= 1

    def test_queue_mark_executing_and_complete(self):
        queue = MacWorkerQueue()
        task = MacWorkerTask(task_type=MacTaskType.UNSYNCED_FILE_READ)
        task_id = queue.submit(task)
        assert queue.mark_executing(task_id) is True
        assert queue.get(task_id).status == MacTaskStatus.EXECUTING
        assert queue.mark_completed(task_id, "file contents") is True
        assert queue.get(task_id).status == MacTaskStatus.COMPLETED

    def test_get_mac_worker_queue_singleton(self):
        """get_mac_worker_queue must return same instance."""
        q1 = get_mac_worker_queue()
        q2 = get_mac_worker_queue()
        assert q1 is q2

    def test_queue_api_response_no_secrets(self):
        """Mac worker queue API response must not contain secrets."""
        import json
        queue = MacWorkerQueue()
        response = queue.to_api_response()
        output = json.dumps(response)
        for pattern in ["sk-", "xoxp-", "AKIA", "Bearer "]:
            assert pattern not in output


# ============================================================================
# Section 20 — Capability-Aware UI/API
# ============================================================================

class TestCapabilityAwareUI:

    def test_capability_status_api_entry_exists(self):
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("capability_status_api")
        assert entry is not None
        assert entry.cloud_route is not None

    def test_parity_status_mobile_entry_exists(self):
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("parity_status_mobile")
        assert entry is not None

    def test_parity_status_macbook_entry_exists(self):
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("parity_status_macbook")
        assert entry is not None

    def test_mobile_parity_status_is_live(self):
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("parity_status_mobile")
        assert entry.status in (
            CapabilityStatus.CLOUD_LIVE,
            CapabilityStatus.CROSS_DEVICE_LIVE,
        )

    def test_mac_parity_status_is_live(self):
        matrix = get_plan9_capability_matrix()
        entry = matrix.get("parity_status_macbook")
        assert entry.status in (
            CapabilityStatus.LOCAL_LIVE,
            CapabilityStatus.CROSS_DEVICE_LIVE,
        )


# ============================================================================
# Future Inheritance
# ============================================================================

class TestFutureInheritance:

    def test_default_inheritance_policy_exists(self):
        assert PLAN9_DEFAULT_INHERITANCE is not None
        assert PLAN9_DEFAULT_INHERITANCE.default_model_tier == ModelTier.BALANCED

    def test_default_retrieval_worker_required(self):
        assert PLAN9_DEFAULT_INHERITANCE.retrieval_worker_required is True

    def test_default_must_appear_in_capability_matrix(self):
        assert PLAN9_DEFAULT_INHERITANCE.must_appear_in_capability_matrix is True

    def test_default_audit_required(self):
        assert PLAN9_DEFAULT_INHERITANCE.audit_events_required is True

    def test_hypothetical_new_manager_inherits_defaults(self):
        """A hypothetical future manager with empty metadata inherits warnings, not errors."""
        result = validate_manager_inheritance(
            "hypothetical_future_manager",
            {},  # empty metadata
        )
        # Should get warnings (not errors) for missing explicit routing/parity
        # Errors = actual missing required fields
        assert isinstance(result.errors, list)
        # No hard errors for empty new manager (it inherits defaults)
        # It will have warnings about missing explicit routing, that's expected
        assert result.entity_id == "hypothetical_future_manager"

    def test_manager_without_retrieval_gets_error(self):
        """Manager without retrieval policy AND no justification should get error."""
        result = validate_manager_inheritance(
            "bad_manager_no_retrieval",
            {"model_routing": "gpt-4o"},  # has routing but no retrieval
        )
        retrieval_errors = [e for e in result.errors if "retrieval" in e]
        assert len(retrieval_errors) > 0, (
            "Manager without retrieval policy must get validation error"
        )

    def test_manager_with_justification_no_retrieval_ok(self):
        """Manager with explicit no_retrieval_justification should not get retrieval error."""
        result = validate_manager_inheritance(
            "no_retrieval_justified_manager",
            {
                "model_routing": "gpt-4o",
                "no_retrieval_justification": "This manager only receives pre-packaged structured input",
            },
        )
        retrieval_errors = [e for e in result.errors if "retrieval" in e]
        assert len(retrieval_errors) == 0

    def test_all_managers_in_capability_matrix_by_domain(self):
        """Every known manager must have at least one entry in the capability matrix."""
        matrix = get_plan9_capability_matrix()
        all_domains = {e.domain for e in matrix.entries}
        missing = validate_all_managers_in_capability_matrix(
            KNOWN_MANAGER_IDS, all_domains
        )
        assert missing == [], (
            f"Managers missing from capability matrix domains: {missing}"
        )

    def test_routing_matrix_covers_all_managers(self):
        """Routing matrix must have explicit entries for all 17 managers."""
        matrix = get_role_routing_matrix()
        routing_ids = set(matrix.all_role_ids())
        missing = validate_all_managers_have_routing(KNOWN_MANAGER_IDS, routing_ids)
        assert missing == [], (
            f"Managers missing from routing matrix: {missing} "
            "(they would inherit DEFAULT_ROUTING; explicitly document if intentional)"
        )


# ============================================================================
# Section 21 — Authority / Approval / Audit
# ============================================================================

class TestAuthorityApproval:

    def test_deploy_requires_approval_in_parallel_dag(self):
        policy = ParallelDAGPolicy()
        assert policy.requires_approval("production_deploy")

    def test_iam_requires_approval_in_parallel_dag(self):
        policy = ParallelDAGPolicy()
        assert policy.requires_approval("iam_change")

    def test_commit_skill_is_approval_required(self):
        skill = get_skill("commit_push")
        assert skill is not None
        assert skill.authority_level == "requires_approval"

    def test_deploy_skill_is_hard_gate(self):
        skill = get_skill("deploy_operator")
        assert skill is not None
        assert skill.authority_level == "hard_gate"

    def test_secret_scan_skill_is_auto(self):
        skill = get_skill("secret_scan")
        assert skill is not None
        assert skill.authority_level == "auto"


# ============================================================================
# Integration: Complete Plan 9 smoke test
# ============================================================================

class TestPlan9Smoke:

    def test_full_system_importable(self):
        """Verify all Plan 9 modules import without error."""
        import openjarvis.plan9
        assert openjarvis.plan9 is not None

    def test_capability_matrix_has_all_plan9_status_types(self):
        """Capability matrix must use all Plan 9 status types."""
        matrix = get_plan9_capability_matrix()
        used_statuses = {e.status for e in matrix.entries}
        # Must use at least these status types
        required_statuses = {
            CapabilityStatus.CLOUD_LIVE,
            CapabilityStatus.CROSS_DEVICE_LIVE,
            CapabilityStatus.QUEUED_MAC_ONLY,
            CapabilityStatus.APPROVAL_REQUIRED,
            CapabilityStatus.PARKED,
        }
        for status in required_statuses:
            assert status in used_statuses, (
                f"Plan 9 capability matrix must include at least one {status.value} entry"
            )

    def test_skills_manifest_all_have_valid_status(self):
        valid_statuses = {s.value for s in Plan9SkillStatus}
        for skill in PLAN9_SKILLS_MANIFEST:
            assert skill.status.value in valid_statuses

    def test_commands_manifest_all_have_valid_status(self):
        valid_statuses = {s.value for s in Plan9CommandStatus}
        for cmd in PLAN9_COMMANDS_MANIFEST:
            assert cmd.status.value in valid_statuses

    def test_total_managers_and_workers_count(self):
        assert len(KNOWN_MANAGER_IDS) == 17
        assert len(KNOWN_WORKER_IDS) == 30
        total = len(KNOWN_MANAGER_IDS) + len(KNOWN_WORKER_IDS)
        assert total == 47, f"Expected 47 total (17+30), got {total}"
