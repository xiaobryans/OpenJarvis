"""Domain managers for the lean hierarchy.

A fresh, universal manager set (Approach A) replacing the legacy 17 dev-centric
managers in ``orchestrator/manager_registry.py`` (which stay parked, not
deleted). Each manager owns a life/work domain and a small set of **workers** —
real registered tools it may dispatch. Prefer many small-scope workers.

Legacy-manager audit (superseded by this set; none deleted — parked stack):
  coding/architecture/debugging/code_review/testing_validation -> code_build +
    quality;  research -> research;  memory_knowledge -> learning + data;
    documentation -> code_build;  product_ux -> planning;
    operations_automation/runtime_ops/release_packaging -> automation;
    governance_safety -> security;  data -> data;  cost_routing -> (engine
    routing, not a domain manager);  nus_learning -> learning;
    connector_auth -> integration.
New universal domains added that the old set lacked: communications, finance,
personal_life.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class ManagerSpec:
    """A domain manager: its identity and the workers (tools) it can dispatch."""

    manager_id: str
    name: str
    domain: str  # one-line description used in planning prompts
    workers: List[str] = field(default_factory=list)  # registered tool names


# The 12 required managers + their real worker tools. Workers reference tools
# that exist in the registry today; domains whose tools aren't built yet carry
# an empty worker list and are skipped gracefully at execution time.
MANAGERS: Dict[str, ManagerSpec] = {
    m.manager_id: m
    for m in [
        ManagerSpec(
            "research", "Research Manager",
            "Web/knowledge research, finding and reading information.",
            ["web_search", "http_request", "notion_search", "notion_read"],
        ),
        ManagerSpec(
            "code_build", "Code/Build Manager",
            "Read/write files, run code/commands, git — engineering tasks.",
            ["file_read", "file_search", "file_write", "shell_exec",
             "git_status", "git_diff"],
        ),
        ManagerSpec(
            "communications", "Communications Manager",
            "Email and Slack — read, summarize, AND send/reply.",
            ["gmail_important", "slack_recent", "gmail_send", "slack_send"],
        ),
        ManagerSpec(
            "finance", "Finance Manager",
            "Revenue, transactions, budgets, spend (Stripe pending credentials).",
            [],  # stripe connector not yet configured
        ),
        ManagerSpec(
            "personal_life", "Personal/Life Manager",
            "Calendar (read + create/delete events), weather, time, reminders.",
            ["calendar_today", "current_weather", "current_time",
             "morning_briefing", "calendar_create", "calendar_delete"],
        ),
        ManagerSpec(
            "security", "Security Manager",
            "Account/system security checks and safety review.",
            [],  # security worker tools to be added
        ),
        ManagerSpec(
            "data", "Data Manager",
            "Querying structured data, knowledge bases and calculations.",
            ["db_query", "knowledge_search", "calculator"],
        ),
        ManagerSpec(
            "integration", "Integration Manager",
            "Connecting to external APIs/services and Notion workspaces.",
            ["http_request", "notion_search"],
        ),
        ManagerSpec(
            "planning", "Planning Manager",
            "Breaking down goals, scheduling, and structuring work.",
            ["think", "current_time", "calendar_today"],
        ),
        ManagerSpec(
            "quality", "Quality Manager",
            "Reviews/verifies worker output before it returns (tester layer).",
            [],  # tester role wired in Stage 5
        ),
        ManagerSpec(
            "learning", "Learning Manager",
            "Memory, recall and personal knowledge about Bryan.",
            ["memory_manage", "user_profile_manage", "knowledge_search"],
        ),
        ManagerSpec(
            "automation", "Automation Manager",
            "Scheduled tasks, briefings, monitoring and recurring ops.",
            ["morning_briefing"],
        ),
    ]
}


def get_manager(manager_id: str) -> ManagerSpec | None:
    return MANAGERS.get(manager_id)


def managers_catalog() -> str:
    """Render the manager+worker catalog for a planning prompt."""
    lines = []
    for m in MANAGERS.values():
        workers = ", ".join(m.workers) if m.workers else "(no workers yet)"
        lines.append(f"- {m.manager_id}: {m.domain} | workers: {workers}")
    return "\n".join(lines)


__all__ = ["ManagerSpec", "MANAGERS", "get_manager", "managers_catalog"]
