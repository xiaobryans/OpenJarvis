"""Plan 9 — Jarvis Commands Manifest.

Declares all 20 required Plan 9 commands. Maps to existing CLI command modules
in openjarvis.cli where they exist. Marks missing/partial commands honestly.

If existing CLI naming differs from the Plan 9 spec, the mapping is documented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class Plan9CommandStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"    # defined here, not yet in CLI
    WIRED = "WIRED"              # exists in CLI and executes
    TESTED = "TESTED"            # wired and tested
    PARTIAL = "PARTIAL"          # partial implementation in CLI
    MISSING = "MISSING"          # not implemented at all


@dataclass
class Plan9CommandEntry:
    command: str              # canonical Plan 9 command spec
    purpose: str
    arguments: List[str]
    output_shape: str
    authority_level: str      # auto | requires_approval | hard_gate
    manager_scope: str        # which manager(s) own this command
    status: Plan9CommandStatus
    existing_cli_mapping: Optional[str] = None  # existing CLI command if different
    runtime_status_notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "command": self.command,
            "purpose": self.purpose,
            "arguments": self.arguments,
            "output_shape": self.output_shape,
            "authority_level": self.authority_level,
            "manager_scope": self.manager_scope,
            "status": self.status.value,
            "existing_cli_mapping": self.existing_cli_mapping,
            "runtime_status_notes": self.runtime_status_notes,
        }


PLAN9_COMMANDS_MANIFEST: List[Plan9CommandEntry] = [

    Plan9CommandEntry(
        command="jarvis rules status",
        purpose="Show all active Jarvis internal rules with category and enforcement",
        arguments=[],
        output_shape="Table: rule_id | category | description | enforcement",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="PLAN9_INTERNAL_RULES defined in rules.py; CLI command not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis skills list",
        purpose="List all Jarvis skills with current status",
        arguments=["--filter-status (optional)"],
        output_shape="Table: skill_id | display_name | status | model_tier | authority",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.PARTIAL,
        existing_cli_mapping="jarvis skill list (existing in skill_cmd.py)",
        runtime_status_notes="Existing skill_cmd.py covers SkillRegistry; Plan 9 manifest needs wiring",
    ),

    Plan9CommandEntry(
        command="jarvis skills status",
        purpose="Show detailed status of all Plan 9 skills including DOCUMENTED/WIRED/TESTED/PARTIAL/MISSING",
        arguments=["--skill-id (optional)"],
        output_shape="Detailed skill status per skill with runtime_status_notes",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="PLAN9_SKILLS_MANIFEST defined; CLI subcommand not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis commands list",
        purpose="List all Jarvis commands with status (DOCUMENTED/WIRED/TESTED/PARTIAL/MISSING)",
        arguments=["--filter-status (optional)"],
        output_shape="Table: command | status | manager_scope | authority_level",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="PLAN9_COMMANDS_MANIFEST defined; CLI command not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis capability matrix",
        purpose="Show full Plan 9 capability matrix with CLOUD_LIVE/LOCAL_LIVE/CROSS_DEVICE_LIVE/etc status",
        arguments=["--domain (optional)", "--status (optional)"],
        output_shape="Table: capability_id | domain | status | cloud_route | local_route | notes",
        authority_level="auto",
        manager_scope="product_ux_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="Plan9CapabilityMatrix defined; CLI command not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis model-route explain --role <role> --task <task> --risk <risk>",
        purpose="Explain model tier recommendation for a given role, task description, and risk level",
        arguments=["--role", "--task", "--risk", "--complexity (optional)", "--failures (optional)"],
        output_shape="JSON: {tier, model_name, escalation_rule, cost_justification}",
        authority_level="auto",
        manager_scope="cost_routing_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        existing_cli_mapping="model routing exists via LearnedRouter but not this CLI shape",
        runtime_status_notes="model_routing.py provides tier_for_task(); CLI command not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis context-pack prepare --scope <scope>",
        purpose="Prepare compact evidence/context packet for a task scope (cheap retrieval before reasoning)",
        arguments=["--scope", "--max-tokens (optional)"],
        output_shape="CompactContextPacket: {sources, evidence, token_count}",
        authority_level="auto",
        manager_scope="memory_knowledge_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="retrieval_context_packet skill defined; CLI not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis dag plan --task <task>",
        purpose="Generate dependency-aware task DAG with safe parallel groups and sequential constraints",
        arguments=["--task", "--risk (optional)"],
        output_shape="TaskDAG: {nodes, edges, parallel_groups, sequential_constraints}",
        authority_level="auto",
        manager_scope="operations_automation_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="DAG policy defined in orchestration_policy.py; CLI not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis worker-pool plan --role <role> --task <task>",
        purpose="Plan elastic same-role worker pool size for a given role and task",
        arguments=["--role", "--task", "--token-budget (optional)"],
        output_shape="WorkerPoolPlan: {worker_count, shard_plan, conflict_flags}",
        authority_level="auto",
        manager_scope="operations_automation_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="ElasticPoolPolicy defined; CLI not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis patch-propose --file <path> --item <item>",
        purpose="Worker generates structured patch proposal for a single item in a shared file",
        arguments=["--file", "--item", "--ownership (optional)"],
        output_shape="PatchProposal: {target_section, diff_hunk, risk_notes, tests_needed}",
        authority_level="auto",
        manager_scope="coding_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="BatchIntegrationPolicy defined; patch proposal CLI not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis patch-integrate dry-run --file <path>",
        purpose="Batch Integration Manager dry-run: combine all pending patch proposals for file",
        arguments=["--file"],
        output_shape="IntegratedDiff: {diff, dropped_patches, conflict_notes}",
        authority_level="auto",
        manager_scope="coding_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="BatchIntegrationPolicy defined; integration executor not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis merge-review dry-run --file <path>",
        purpose="Integration Review Manager dry-run: independently verify integrated batch patch",
        arguments=["--file"],
        output_shape="ReviewResult: {verdict: PASS|FAIL, dropped_items, conflicts, test_results}",
        authority_level="auto",
        manager_scope="testing_validation_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="IntegrationReviewPolicy defined; reviewer executor not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis validate targeted",
        purpose="Run targeted validation on changed files only (not broad audit)",
        arguments=["--files (optional, defaults to git diff)", "--type (optional: pytest|lint|types)"],
        output_shape="ValidationReport: {passed, failed, errors, duration}",
        authority_level="auto",
        manager_scope="testing_validation_manager",
        status=Plan9CommandStatus.PARTIAL,
        existing_cli_mapping="jarvis doctor (partial), pytest direct (partial)",
        runtime_status_notes="Targeted test runner partially available; unified CLI not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis secret-scan",
        purpose="Scan staged diff and files for secrets before commit/push",
        arguments=["--diff (optional)", "--files (optional)"],
        output_shape="ScanResult: {status: CLEAN|FOUND_SECRETS, locations (no values), abort_required}",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.PARTIAL,
        existing_cli_mapping="jarvis scan (partial in scan_cmd.py)",
        runtime_status_notes="scan_cmd.py exists; Plan 9 pre-commit secret scan integration partial",
    ),

    Plan9CommandEntry(
        command="jarvis approval classify --action <action>",
        purpose="Classify whether an action requires Bryan approval and at what authority level",
        arguments=["--action"],
        output_shape="AuthorityClassification: {action, authority_level, approval_required, hard_gate}",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.PARTIAL,
        existing_cli_mapping="governance gate check exists; approval classify CLI not yet separate command",
        runtime_status_notes="authority.py and policies.py have approval logic; CLI command not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis audit show --limit <n>",
        purpose="Show recent audit events with actor, surface, model, action, timestamp",
        arguments=["--limit (default 20)", "--filter-actor (optional)", "--filter-action (optional)"],
        output_shape="AuditLog: List[{timestamp, actor, surface, model, action, verdict}]",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        existing_cli_mapping="None; audit log route exists in governance routes",
        runtime_status_notes="Audit log exists in governance; CLI command not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis rollback plan",
        purpose="Show rollback plan for last sensitive operation",
        arguments=["--operation (optional)"],
        output_shape="RollbackPlan: {steps, commands, warnings}",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        existing_cli_mapping="ROLLBACK.md exists; programmatic CLI not yet wired",
        runtime_status_notes="ROLLBACK.md has instructions; programmatic rollback plan generator planned",
    ),

    Plan9CommandEntry(
        command="jarvis report sprint",
        purpose="Generate complete Plan 9 sprint report with verdict and all 24 required fields",
        arguments=["--sprint-id (optional)", "--verdict (optional)"],
        output_shape="SprintReport (Section 25 format)",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="sprint_report skill defined; CLI generator not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis parity status",
        purpose="Show cross-device parity status for all capabilities — mobile vs MacBook",
        arguments=["--domain (optional)", "--show-gaps (flag)"],
        output_shape="ParityStatus: {cloud_live, local_live, cross_device_live, queued_mac_only, missing, parked}",
        authority_level="auto",
        manager_scope="product_ux_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="Plan9CapabilityMatrix defined; parity status CLI not yet wired",
    ),

    Plan9CommandEntry(
        command="jarvis parked status",
        purpose="Show all parked capabilities with the plan they're parked to",
        arguments=[],
        output_shape="ParkedList: List[{capability_id, parked_until, notes}]",
        authority_level="auto",
        manager_scope="governance_safety_manager",
        status=Plan9CommandStatus.DOCUMENTED,
        runtime_status_notes="PARKED items in capability_matrix.py; CLI not yet wired",
    ),
]


def get_commands_manifest() -> List[Plan9CommandEntry]:
    return PLAN9_COMMANDS_MANIFEST


def get_command(command_spec: str) -> Optional[Plan9CommandEntry]:
    for c in PLAN9_COMMANDS_MANIFEST:
        if c.command.startswith(command_spec) or command_spec in c.command:
            return c
    return None


def commands_by_status(status: Plan9CommandStatus) -> List[Plan9CommandEntry]:
    return [c for c in PLAN9_COMMANDS_MANIFEST if c.status == status]
