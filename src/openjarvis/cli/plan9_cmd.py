"""``jarvis plan9`` — Plan 9 cross-device parity CLI commands.

Commands:
  jarvis plan9 capability-matrix   Show full Plan 9 capability matrix
  jarvis plan9 parity-status       Show cloud/mobile vs MacBook/local parity
  jarvis plan9 model-routing       Show role-based model routing matrix
  jarvis plan9 model-route-explain Explain model tier for role/task/risk
  jarvis plan9 worker-pool         Show elastic worker pool policy
  jarvis plan9 mac-queue           Show Mac worker queue status
  jarvis plan9 mac-queue-submit    Submit a Mac-only task to the queue
  jarvis plan9 secret-scan         Scan files/diff for secrets
  jarvis plan9 validate            Run targeted Plan 9 tests
  jarvis plan9 rules               Show Plan 9 internal rules
  jarvis plan9 skills              Show Plan 9 skills manifest
  jarvis plan9 commands            Show Plan 9 commands manifest
  jarvis plan9 parked              Show parked capabilities

All dangerous commands (commit, deploy) are approval-gated or dry-run only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click


@click.group("plan9")
def plan9() -> None:
    """Plan 9 cross-device parity commands."""


# ---------------------------------------------------------------------------
# capability-matrix
# ---------------------------------------------------------------------------

@plan9.command("capability-matrix")
@click.option("--domain", default=None, help="Filter by manager/domain ID")
@click.option("--status", default=None, help="Filter by status (CLOUD_LIVE, PARKED, etc.)")
@click.option("--json-out", is_flag=True, default=False, help="Output as JSON")
def capability_matrix(domain: Optional[str], status: Optional[str], json_out: bool) -> None:
    """Show full Plan 9 capability matrix."""
    from openjarvis.plan9.capability_matrix import get_plan9_capability_matrix, CapabilityStatus

    matrix = get_plan9_capability_matrix()
    entries = matrix.entries

    if domain:
        entries = [e for e in entries if e.domain == domain]
    if status:
        try:
            st = CapabilityStatus(status.upper())
            entries = [e for e in entries if e.status == st]
        except ValueError:
            valid = [s.value for s in CapabilityStatus]
            click.echo(f"Invalid status {status!r}. Valid: {valid}", err=True)
            sys.exit(1)

    if json_out:
        click.echo(json.dumps([e.to_dict() for e in entries], indent=2))
        return

    # Pretty table
    click.echo(f"\n{'Capability ID':<35} {'Domain':<30} {'Status':<22} {'Route'}")
    click.echo("-" * 110)
    for e in sorted(entries, key=lambda x: (x.domain, x.capability_id)):
        route = e.cloud_route or e.local_route or "(none)"
        click.echo(f"{e.capability_id:<35} {e.domain:<30} {e.status.value:<22} {route}")

    click.echo(f"\nTotal: {len(entries)} entries")
    if not domain and not status:
        summary = matrix.summary()
        for k, v in sorted(summary.items()):
            click.echo(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# parity-status
# ---------------------------------------------------------------------------

@plan9.command("parity-status")
@click.option("--show-gaps", is_flag=True, default=False, help="Show MISSING/UNKNOWN items")
@click.option("--json-out", is_flag=True, default=False, help="Output as JSON")
def parity_status(show_gaps: bool, json_out: bool) -> None:
    """Show cross-device parity status: cloud/mobile vs MacBook/local."""
    from openjarvis.plan9.capability_matrix import get_plan9_capability_matrix, CapabilityStatus

    matrix = get_plan9_capability_matrix()
    summary = matrix.summary()

    data = {
        "summary": summary,
        "total": len(matrix.entries),
        "parked": [e.to_dict() for e in matrix.parked()],
    }
    if show_gaps:
        data["gaps"] = [e.to_dict() for e in matrix.gaps()]

    if json_out:
        click.echo(json.dumps(data, indent=2))
        return

    click.echo("\n=== Plan 9 Cross-Device Parity Status ===\n")
    click.echo(f"Total capabilities tracked: {len(matrix.entries)}")
    click.echo()
    for status_val, count in sorted(summary.items()):
        icon = {
            "CROSS_DEVICE_LIVE": "✓",
            "CLOUD_LIVE": "☁",
            "LOCAL_LIVE": "⌂",
            "QUEUED_MAC_ONLY": "⧗",
            "APPROVAL_REQUIRED": "⚠",
            "PARKED": "…",
            "MISSING": "✗",
            "UNSAFE": "✕",
            "UNKNOWN_NEEDS_PROOF": "?",
        }.get(status_val, " ")
        click.echo(f"  {icon} {status_val}: {count}")

    click.echo()
    click.echo("Parked items:")
    for e in matrix.parked():
        click.echo(f"  - {e.capability_id} → {e.parked_until}")

    if show_gaps:
        click.echo("\nGaps (need proof or implementation):")
        for e in matrix.gaps():
            click.echo(f"  - {e.capability_id} [{e.status.value}] {e.notes or ''}")


# ---------------------------------------------------------------------------
# model-routing
# ---------------------------------------------------------------------------

@plan9.command("model-routing")
@click.option("--role", default=None, help="Filter to a specific role")
@click.option("--json-out", is_flag=True, default=False, help="Output as JSON")
def model_routing(role: Optional[str], json_out: bool) -> None:
    """Show role-based model routing matrix."""
    from openjarvis.plan9.model_routing import get_role_routing_matrix, DEFAULT_ROUTING

    matrix = get_role_routing_matrix()
    entries = matrix.entries

    if role:
        entries = [e for e in entries if e.role_id == role]
        if not entries:
            click.echo(f"Role {role!r} not found. Showing DEFAULT_ROUTING.")
            entries = [matrix.get(role)]  # Returns DEFAULT_ROUTING

    if json_out:
        click.echo(json.dumps([e.to_dict() for e in entries], indent=2))
        return

    click.echo(f"\n{'Role ID':<35} {'Type':<10} {'Default Tier':<14} {'Cheap':<18} {'Balanced':<18} {'Best'}")
    click.echo("-" * 120)
    for e in sorted(entries, key=lambda x: (x.role_type, x.role_id)):
        click.echo(
            f"{e.role_id:<35} {e.role_type:<10} {e.default_tier.value:<14} "
            f"{e.cheap_model:<18} {e.balanced_model:<18} {e.best_model}"
        )
    click.echo(f"\nTotal roles: {len(entries)}")
    errors = matrix.validate()
    if errors:
        click.echo(f"\nValidation errors: {errors}", err=True)
    else:
        click.echo("Routing matrix validation: OK")


# ---------------------------------------------------------------------------
# model-route-explain
# ---------------------------------------------------------------------------

@plan9.command("model-route-explain")
@click.option("--role", required=True, help="Role ID")
@click.option("--task", default="", help="Task description")
@click.option("--risk", default="medium", type=click.Choice(["low", "medium", "high", "critical"]))
@click.option("--complexity", default="moderate", type=click.Choice(["simple", "moderate", "complex"]))
@click.option("--failures", default=0, type=int, help="Prior failure count")
def model_route_explain(role: str, task: str, risk: str, complexity: str, failures: int) -> None:
    """Explain model tier recommendation for a role/task/risk context."""
    from openjarvis.plan9.model_routing import get_role_routing_matrix, ModelTier

    matrix = get_role_routing_matrix()
    entry = matrix.get(role)
    tier = entry.tier_for_task(risk=risk, complexity=complexity, failures=failures)

    model_map = {
        ModelTier.CHEAP: entry.cheap_model,
        ModelTier.BALANCED: entry.balanced_model,
        ModelTier.BEST: entry.best_model,
        ModelTier.STOP: "STOP — break approach",
    }

    click.echo(f"\nRole:              {role}")
    click.echo(f"Task:              {task or '(not specified)'}")
    click.echo(f"Risk:              {risk}")
    click.echo(f"Complexity:        {complexity}")
    click.echo(f"Failures:          {failures}")
    click.echo(f"Inherited default: {entry.role_id == '__default__'}")
    click.echo(f"\nRecommended tier:  {tier.value}")
    click.echo(f"Recommended model: {model_map.get(tier, 'unknown')}")
    click.echo(f"\nEscalation rule:   {entry.escalation_rule}")
    click.echo(f"Fallback rule:     {entry.fallback_rule}")
    click.echo(f"Justification:     {entry.cost_justification}")


# ---------------------------------------------------------------------------
# worker-pool
# ---------------------------------------------------------------------------

@plan9.command("worker-pool")
@click.option("--role", default=None, help="Filter to specific role")
@click.option("--json-out", is_flag=True, default=False, help="Output as JSON")
def worker_pool(role: Optional[str], json_out: bool) -> None:
    """Show elastic same-role worker pool policies."""
    from openjarvis.plan9.orchestration_policy import ELASTIC_POOL_POLICIES, DEFAULT_ELASTIC_POOL

    policies = ELASTIC_POOL_POLICIES
    if role:
        if role in policies:
            policies = {role: policies[role]}
        else:
            click.echo(f"Role {role!r} not in explicit pool policy. Showing DEFAULT.")
            policies = {"__default__": DEFAULT_ELASTIC_POOL}

    if json_out:
        click.echo(json.dumps({k: {
            "scaling_allowed": v.scaling_allowed,
            "max_workers": v.max_workers,
            "single_executor_only": v.single_executor_only,
            "lock_required_for_writes": v.lock_required_for_writes,
            "notes": v.notes,
        } for k, v in policies.items()}, indent=2))
        return

    click.echo(f"\n{'Role ID':<35} {'Scale?':<8} {'Max':<5} {'Single-Exec?':<14} {'Lock?':<7} Notes")
    click.echo("-" * 100)
    for role_id, p in sorted(policies.items()):
        click.echo(
            f"{role_id:<35} {'Yes' if p.scaling_allowed else 'No':<8} "
            f"{p.max_workers:<5} {'YES' if p.single_executor_only else 'no':<14} "
            f"{'Yes' if p.lock_required_for_writes else 'no':<7} {p.notes[:50]}"
        )


# ---------------------------------------------------------------------------
# mac-queue
# ---------------------------------------------------------------------------

@plan9.command("mac-queue")
@click.option("--json-out", is_flag=True, default=False, help="Output as JSON")
def mac_queue(json_out: bool) -> None:
    """Show Mac worker queue status."""
    from openjarvis.plan9.mac_worker_queue import get_mac_worker_queue, MAC_ONLY_TASK_TYPES

    q = get_mac_worker_queue()
    data = q.to_api_response()

    if json_out:
        click.echo(json.dumps(data, indent=2))
        return

    summary = data["queue_status"]
    click.echo("\n=== Mac Worker Queue ===\n")
    click.echo(f"Total tasks: {summary['total']}")
    click.echo(f"  Queued:    {summary['queued']}")
    click.echo(f"  Executing: {summary['executing']}")
    click.echo(f"  Completed: {summary['completed']}")
    click.echo(f"  Failed:    {summary['failed']}")
    click.echo(f"\nMac-only task types: {[t.value for t in MAC_ONLY_TASK_TYPES]}")

    if data["tasks"]:
        click.echo("\nTasks:")
        for t in data["tasks"]:
            click.echo(f"  [{t['status']}] {t['task_id'][:8]}… {t['display_name']} ({t['task_type']})")


# ---------------------------------------------------------------------------
# mac-queue-submit
# ---------------------------------------------------------------------------

@plan9.command("mac-queue-submit")
@click.option("--type", "task_type", required=True,
              type=click.Choice(["app_reinstall", "mac_app_control", "unsynced_file_read",
                                 "keychain_credential", "mac_hardware"]),
              help="Mac task type")
@click.option("--name", required=True, help="Task display name")
@click.option("--description", default="", help="Task description")
@click.option("--from-surface", default="cli", help="Surface submitting the task")
def mac_queue_submit(task_type: str, name: str, description: str, from_surface: str) -> None:
    """Submit a Mac-only task to the queue."""
    from openjarvis.plan9.mac_worker_queue import MacWorkerTask, MacTaskType, get_mac_worker_queue

    task = MacWorkerTask(
        task_type=MacTaskType(task_type),
        display_name=name,
        description=description,
        submitted_from=from_surface,
    )
    q = get_mac_worker_queue()
    task_id = q.submit(task)
    click.echo(f"Task queued: {task_id}")
    click.echo(f"Type: {task_type} | Name: {name}")
    click.echo("Run 'jarvis plan9 mac-queue' to check status.")


# ---------------------------------------------------------------------------
# secret-scan
# ---------------------------------------------------------------------------

@plan9.command("secret-scan")
@click.argument("paths", nargs=-1, type=click.Path())
@click.option("--diff", is_flag=True, default=False, help="Scan staged git diff instead of files")
def secret_scan(paths: tuple, diff: bool) -> None:
    """Scan files or staged diff for secrets. CLEAN or FOUND_SECRETS."""
    import re

    secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"xoxp-[0-9]+-[0-9]+-"),
        re.compile(r"xoxb-[0-9]+-"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY"),
        re.compile(r"ghp_[A-Za-z0-9]{36,}"),
        re.compile(r"gho_[A-Za-z0-9]{36,}"),
        re.compile(r"Bearer eyJ[A-Za-z0-9+/=]{20,}"),
    ]

    texts = []
    labels = []

    if diff:
        try:
            r = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True, timeout=10)
            texts.append(r.stdout)
            labels.append("staged diff")
        except Exception as e:
            click.echo(f"Could not get diff: {e}", err=True)

    for path_str in paths:
        p = Path(path_str)
        if p.is_file():
            try:
                texts.append(p.read_text(encoding="utf-8", errors="replace"))
                labels.append(str(path_str))
            except Exception as e:
                click.echo(f"Could not read {path_str}: {e}", err=True)

    if not texts:
        click.echo("Nothing to scan. Provide file paths or --diff flag.")
        return

    total_found = 0
    for label, text in zip(labels, texts):
        found = []
        for pattern in secret_patterns:
            for m in pattern.finditer(text):
                found.append(f"  pattern={pattern.pattern!r} at offset {m.start()}")
        if found:
            total_found += len(found)
            click.echo(f"\n[FOUND_SECRETS] {label}:")
            for loc in found:
                click.echo(loc)
        else:
            click.echo(f"[CLEAN] {label}")

    if total_found > 0:
        click.echo(f"\nScan result: FOUND_SECRETS ({total_found} matches) — ABORT COMMIT", err=True)
        sys.exit(1)
    else:
        click.echo("\nScan result: CLEAN")


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@plan9.command("validate")
@click.option("--full", is_flag=True, default=False, help="Run full test suite (default: Plan 9 targeted only)")
def validate(full: bool) -> None:
    """Run targeted Plan 9 validation tests."""
    test_paths = ["tests/test_plan9_cross_device_parity.py"]
    if full:
        test_paths.extend(["tests/server/test_plan9_routes.py", "tests/cli/test_plan9_cmd.py"])

    click.echo(f"Running: pytest {' '.join(test_paths)}")
    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + test_paths + ["-v", "--tb=short"],
        capture_output=False,
    )
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------

@plan9.command("rules")
@click.option("--category", default=None, help="Filter by category")
def rules_cmd(category: Optional[str]) -> None:
    """Show Plan 9 internal operating rules."""
    from openjarvis.plan9.rules import PLAN9_INTERNAL_RULES

    rules = PLAN9_INTERNAL_RULES
    if category:
        rules = [r for r in rules if r.category == category.upper()]

    categories = sorted({r.category for r in PLAN9_INTERNAL_RULES})
    click.echo(f"\nPlan 9 Rules — {len(rules)} shown (categories: {', '.join(categories)})\n")
    for r in rules:
        click.echo(f"[{r.category}] {r.rule_id}")
        click.echo(f"  {r.description[:120]}")
        click.echo()


# ---------------------------------------------------------------------------
# skills
# ---------------------------------------------------------------------------

@plan9.command("skills")
@click.option("--status", default=None, help="Filter by status (WIRED, DOCUMENTED, etc.)")
def skills_cmd(status: Optional[str]) -> None:
    """Show Plan 9 skills manifest."""
    from openjarvis.plan9.skills_manifest import PLAN9_SKILLS_MANIFEST, Plan9SkillStatus

    skills = PLAN9_SKILLS_MANIFEST
    if status:
        try:
            st = Plan9SkillStatus(status.upper())
            skills = [s for s in skills if s.status == st]
        except ValueError:
            valid = [s.value for s in Plan9SkillStatus]
            click.echo(f"Invalid status {status!r}. Valid: {valid}", err=True)
            sys.exit(1)

    click.echo(f"\n{'Skill ID':<35} {'Status':<14} {'Authority':<20} {'Model Tier'}")
    click.echo("-" * 90)
    for s in skills:
        click.echo(f"{s.skill_id:<35} {s.status.value:<14} {s.authority_level:<20} {s.model_tier}")
    click.echo(f"\nTotal: {len(skills)}")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

@plan9.command("commands")
@click.option("--status", default=None, help="Filter by status")
def commands_cmd(status: Optional[str]) -> None:
    """Show Plan 9 commands manifest."""
    from openjarvis.plan9.commands_manifest import PLAN9_COMMANDS_MANIFEST, Plan9CommandStatus

    commands = PLAN9_COMMANDS_MANIFEST
    if status:
        try:
            st = Plan9CommandStatus(status.upper())
            commands = [c for c in commands if c.status == st]
        except ValueError:
            valid = [s.value for s in Plan9CommandStatus]
            click.echo(f"Invalid status {status!r}. Valid: {valid}", err=True)
            sys.exit(1)

    click.echo(f"\n{'Command':<55} {'Status':<14} {'Authority'}")
    click.echo("-" * 90)
    for c in commands:
        cmd_short = c.command[:54]
        click.echo(f"{cmd_short:<55} {c.status.value:<14} {c.authority_level}")
    click.echo(f"\nTotal: {len(commands)}")


# ---------------------------------------------------------------------------
# parked
# ---------------------------------------------------------------------------

@plan9.command("parked")
def parked_cmd() -> None:
    """Show all parked capabilities with the plan they're parked to."""
    from openjarvis.plan9.capability_matrix import get_plan9_capability_matrix

    matrix = get_plan9_capability_matrix()
    parked = matrix.parked()
    click.echo(f"\nParked capabilities ({len(parked)} total):\n")
    for e in parked:
        click.echo(f"  {e.capability_id}")
        click.echo(f"    Status:   {e.status.value}")
        click.echo(f"    Until:    {e.parked_until or 'unspecified'}")
        click.echo(f"    Notes:    {e.notes}")
        click.echo()
    click.echo("Permanent exception (QUEUED_MAC_ONLY, not parked):")
    from openjarvis.plan9.capability_matrix import CapabilityStatus
    mac_only = [e for e in matrix.entries if e.status == CapabilityStatus.QUEUED_MAC_ONLY]
    for e in mac_only:
        click.echo(f"  {e.capability_id}: {e.notes}")


# ---------------------------------------------------------------------------
# proof-checklist
# ---------------------------------------------------------------------------

@plan9.command("proof-checklist")
@click.option("--category", default=None,
              type=click.Choice(["mobile_api", "memory_parity", "connector_parity", "mac_worker_parity"]),
              help="Filter checklist to one category")
@click.option("--json-out", is_flag=True, default=False, help="Output as JSON")
def proof_checklist(category: "Optional[str]", json_out: bool) -> None:
    """Show Bryan's iPhone/mobile runtime proof checklist.

    Lists exactly what to verify from iPhone to complete Plan 9.
    No secrets required.
    """
    items = [
        {"id": "cap_status_mobile", "category": "mobile_api",
         "description": "GET /v1/capabilities/status from iPhone",
         "how": "Open https://<jarvis-api>/v1/capabilities/status in Safari on iPhone.",
         "expected": "HTTP 200, JSON with 'capabilities' list, total > 0"},
        {"id": "parity_status_mobile", "category": "mobile_api",
         "description": "GET /v1/parity/status from iPhone",
         "how": "Open https://<jarvis-api>/v1/parity/status in Safari on iPhone.",
         "expected": "HTTP 200, JSON with parity_definition, summary, parked list"},
        {"id": "coding_search_mobile", "category": "mobile_api",
         "description": "POST /v1/coding/search from iPhone",
         "how": (
             "curl -X POST https://<jarvis-api>/v1/coding/search "
             "-H 'Content-Type: application/json' "
             "-d '{\"query\": \"Plan9CapabilityEntry\", \"paths\": [\"src/\"]}'"
         ),
         "expected": "HTTP 200, results > 0, secret_scan.status == CLEAN"},
        {"id": "cloud_memory_read", "category": "memory_parity",
         "description": "Cloud memory read parity",
         "how": "Create memory on MacBook; verify via GET /v1/memory/list from iPhone.",
         "expected": "Memory created on MacBook appears in iPhone response"},
        {"id": "cloud_memory_write", "category": "memory_parity",
         "description": "Cloud memory write parity",
         "how": "POST /v1/memory/add from iPhone; verify memory appears on MacBook.",
         "expected": "Memory created from iPhone is visible on MacBook"},
        {"id": "gdrive_connector", "category": "connector_parity",
         "description": "GDrive connector parity (skip if not configured)",
         "how": "GET /v1/connectors/gdrive/list from iPhone.",
         "expected": "File list or not_configured status — no 500 error"},
        {"id": "notion_connector", "category": "connector_parity",
         "description": "Notion connector parity (skip if not configured)",
         "how": "GET /v1/connectors/notion/list from iPhone.",
         "expected": "Page list or not_configured status — no 500 error"},
        {"id": "mac_worker_queue_mobile", "category": "mac_worker_parity",
         "description": "Submit Mac-only task from iPhone, verify on MacBook",
         "how": (
             "On iPhone: POST /v1/mac-worker/queue with task_type=app_reinstall. "
             "On MacBook: GET /v1/mac-worker/queue to verify task_id appears."
         ),
         "expected": "Task queued successfully; visible on both surfaces"},
    ]

    if category:
        items = [i for i in items if i["category"] == category]

    if json_out:
        import json
        click.echo(json.dumps(items, indent=2))
        return

    click.echo("\n=== Plan 9 iPhone / Mobile Runtime Proof Checklist ===\n")
    click.echo("Complete all items below from iPhone to reach PLAN_9_ACCEPT_PENDING_REVIEW.\n")
    click.echo("No secrets required. Open URLs in Safari or paste curl commands into Shortcuts.\n")

    current_cat = None
    for i, item in enumerate(items, 1):
        if item["category"] != current_cat:
            current_cat = item["category"]
            click.echo(f"\n[{current_cat.upper()}]")
        click.echo(f"  {i}. {item['description']}")
        click.echo(f"     How:      {item['how'][:100]}")
        click.echo(f"     Expected: {item['expected']}")

    click.echo(f"\n--- Total items: {len(items)} | Verified: 0 (manual) ---")
    click.echo("voice_wake_tts and apple_signing_updater are PARKED (Plan 10/11) — not in this list.")
