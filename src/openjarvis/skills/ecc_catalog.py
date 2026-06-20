"""ECC Catalog — Jarvis-native registry of all ECC capabilities.

This module provides the authoritative static catalog of all ECC
(https://github.com/affaan-m/ECC, MIT) capabilities inventoried for Jarvis.
Every ECC capability is represented here with its intake state.

The catalog is STATIC (no network calls at import time) and operates in
two modes:
  1. Static mode (default): Uses hardcoded classification from inventory analysis.
  2. Dynamic mode: Loads a generated registry JSON if available.

Key invariants:
  - ACTIVE items are pure guidance (read-only, no execution, no external APIs).
  - No ECC code is executed by this module.
  - ACTIVE items require reviewer_approved=True in their ExternalCandidate record.
  - All other states require explicit reviewer transitions to reach ACTIVE.

Usage:
    from openjarvis.skills.ecc_catalog import ECCCatalog

    catalog = ECCCatalog()
    active = catalog.list_active()
    summary = catalog.get_status_summary()
    skill = catalog.get("ecc:eval-harness")

Machine-readable: openjarvis.skills.ecc_catalog
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Catalog constants
# ---------------------------------------------------------------------------

ECC_SOURCE = "https://github.com/affaan-m/ECC"
ECC_LICENSE_SPDX = "MIT"
ECC_LICENSE_VERIFIED = True

# ---------------------------------------------------------------------------
# Static catalog — all unique ECC capabilities with Jarvis intake state
# Format: candidate_id → {state, category, risk_tier, priority, reason, ...}
# ---------------------------------------------------------------------------

# ---- ACTIVE skills (pure guidance, read-only, MIT, no external APIs) ----
_ACTIVE_SKILLS: List[Dict[str, Any]] = [
    # Phase 1E pilot — activated separately, listed here for catalog completeness
    {
        "candidate_id": "ecc:eval-harness",
        "category": "skill", "name": "eval-harness",
        "state": "installed_disabled",  # activated separately via EvalContextSkill
        "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "First pilot — use EvalContextSkill in sources/ecc/eval_context_skill.py.",
        "jarvis_skill_id": "ecc_eval_context",
        "preflight_passed": True, "reviewer_approved": False,
        "ui_route": "skill:ecc_eval_context:invoke",
    },
    {
        "candidate_id": "ecc:benchmark-methodology",
        "category": "skill", "name": "benchmark-methodology",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — evaluation and benchmarking methodology checklist.",
        "jarvis_skill_id": "ecc_benchmark_methodology",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_benchmark_methodology:invoke",
    },
    {
        "candidate_id": "ecc:coding-standards",
        "category": "skill", "name": "coding-standards",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — code quality standards and review checklist.",
        "jarvis_skill_id": "ecc_coding_standards",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_coding_standards:invoke",
    },
    {
        "candidate_id": "ecc:tdd-workflow",
        "category": "skill", "name": "tdd-workflow",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — test-driven development workflow patterns.",
        "jarvis_skill_id": "ecc_tdd_workflow",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_tdd_workflow:invoke",
    },
    {
        "candidate_id": "ecc:verification-loop",
        "category": "skill", "name": "verification-loop",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — verification loop patterns for AI agent tasks.",
        "jarvis_skill_id": "ecc_verification_loop",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_verification_loop:invoke",
    },
    {
        "candidate_id": "ecc:context-budget",
        "category": "skill", "name": "context-budget",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — context window budget management for AI agents.",
        "jarvis_skill_id": "ecc_context_budget",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_context_budget:invoke",
    },
    {
        "candidate_id": "ecc:token-budget-advisor",
        "category": "skill", "name": "token-budget-advisor",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — token/cost budget advisory for model selection.",
        "jarvis_skill_id": "ecc_token_budget_advisor",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_token_budget_advisor:invoke",
    },
    {
        "candidate_id": "ecc:cost-aware-llm-pipeline",
        "category": "skill", "name": "cost-aware-llm-pipeline",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — cost-aware AI pipeline design patterns.",
        "jarvis_skill_id": "ecc_cost_aware_pipeline",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_cost_aware_pipeline:invoke",
    },
    {
        "candidate_id": "ecc:git-workflow",
        "category": "skill", "name": "git-workflow",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — git workflow best practices and commit standards.",
        "jarvis_skill_id": "ecc_git_workflow",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_git_workflow:invoke",
    },
    {
        "candidate_id": "ecc:search-first",
        "category": "skill", "name": "search-first",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — search-first development pattern (grep before read).",
        "jarvis_skill_id": "ecc_search_first",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_search_first:invoke",
    },
    {
        "candidate_id": "ecc:agent-self-evaluation",
        "category": "skill", "name": "agent-self-evaluation",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — agent self-evaluation and quality assessment patterns.",
        "jarvis_skill_id": "ecc_agent_self_eval",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_agent_self_eval:invoke",
    },
    {
        "candidate_id": "ecc:agent-eval",
        "category": "skill", "name": "agent-eval",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — agent evaluation framework and scoring methodology.",
        "jarvis_skill_id": "ecc_agent_eval",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_agent_eval:invoke",
    },
    {
        "candidate_id": "ecc:safety-guard",
        "category": "skill", "name": "safety-guard",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — safety guardrail patterns for AI agents.",
        "jarvis_skill_id": "ecc_safety_guard",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_safety_guard:invoke",
    },
    {
        "candidate_id": "ecc:prompt-optimizer",
        "category": "skill", "name": "prompt-optimizer",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — prompt engineering and optimization techniques.",
        "jarvis_skill_id": "ecc_prompt_optimizer",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_prompt_optimizer:invoke",
    },
    {
        "candidate_id": "ecc:continuous-learning",
        "category": "skill", "name": "continuous-learning",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — continuous learning patterns for AI agent improvement.",
        "jarvis_skill_id": "ecc_continuous_learning",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_continuous_learning:invoke",
    },
    {
        "candidate_id": "ecc:rules-distill",
        "category": "skill", "name": "rules-distill",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — rules extraction and distillation methodology.",
        "jarvis_skill_id": "ecc_rules_distill",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_rules_distill:invoke",
    },
    {
        "candidate_id": "ecc:production-audit",
        "category": "skill", "name": "production-audit",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — production system audit checklist.",
        "jarvis_skill_id": "ecc_production_audit",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_production_audit:invoke",
    },
    {
        "candidate_id": "ecc:code-tour",
        "category": "skill", "name": "code-tour",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — codebase navigation and code tour patterns.",
        "jarvis_skill_id": "ecc_code_tour",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_code_tour:invoke",
    },
    {
        "candidate_id": "ecc:codebase-onboarding",
        "category": "skill", "name": "codebase-onboarding",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — codebase onboarding process and patterns.",
        "jarvis_skill_id": "ecc_codebase_onboarding",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_codebase_onboarding:invoke",
    },
    {
        "candidate_id": "ecc:error-handling",
        "category": "skill", "name": "error-handling",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — error handling patterns and recovery strategies.",
        "jarvis_skill_id": "ecc_error_handling",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_error_handling:invoke",
    },
    {
        "candidate_id": "ecc:strategic-compact",
        "category": "skill", "name": "strategic-compact",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — strategic planning and compact decision frameworks.",
        "jarvis_skill_id": "ecc_strategic_compact",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_strategic_compact:invoke",
    },
    {
        "candidate_id": "ecc:security-scan",
        "category": "skill", "name": "security-scan",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — security scanning checklist and vulnerability patterns.",
        "jarvis_skill_id": "ecc_security_scan",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_security_scan:invoke",
    },
    {
        "candidate_id": "ecc:documentation-lookup",
        "category": "skill", "name": "documentation-lookup",
        "state": "active", "risk_tier": "low", "priority": "likely_adopt",
        "permission_scopes": ["read_only"], "cost_tier": "free",
        "reason": "Safe guidance — documentation lookup and reference patterns.",
        "jarvis_skill_id": "ecc_documentation_lookup",
        "preflight_passed": True, "reviewer_approved": True,
        "ui_route": "skill:ecc_documentation_lookup:invoke",
    },
]

# ---- INSTALLED_DISABLED skills (need API keys/external services) ----
_DISABLED_SKILL_IDS = [
    "exa-search", "fal-ai-media", "deep-research", "market-research",
    "data-scraper-agent", "social-publisher", "email-ops", "github-ops",
    "jira-integration", "google-workspace-ops", "messages-ops", "x-api",
    "unified-notifications-ops", "lead-intelligence", "investor-outreach",
    "crosspost", "videodb", "ecc-tools-cost-audit", "configure-ecc",
    "article-writing", "content-engine", "brand-discovery", "brand-voice",
    "competitive-platform-analysis", "competitive-report-structure",
    "investor-materials", "marketing-campaign", "seo", "agent-payment-x402",
    "social-graph-ranker", "research-ops", "knowledge-ops",
    "project-flow-ops", "team-builder",
]

# ---- ADAPT_NEEDED skills (need Jarvis execution wiring) ----
_ADAPT_NEEDED_SKILL_IDS = [
    "dmux-workflows", "nanoclaw-repl", "ecc-guide",
    "team-agent-orchestration", "autonomous-loops",
    "parallel-execution-optimizer", "claude-devfleet",
    "orch-add-feature", "orch-build-mvp", "orch-change-feature",
    "orch-fix-defect", "orch-pipeline", "orch-refine-code",
    "council", "dynamic-workflow-mode", "plan-orchestrate",
    "agent-introspection-debugging", "agent-sort", "agent-architecture-audit",
    "agent-harness-construction", "agentic-os", "agentic-engineering",
    "autonomous-agent-harness", "recsys-pipeline-architect",
    "data-throughput-accelerator", "latency-critical-systems",
    "mcp-server-patterns", "hookify-rules", "browser-qa", "e2e-testing",
    "workspace-surface-audit", "repo-scan", "uncloud", "terminal-ops",
    "dashboard-builder", "ui-demo", "ui-to-vue", "liquid-glass-design",
    "motion-advanced", "motion-foundations", "motion-patterns", "motion-ui",
    "video-editing", "nextjs-turbopack", "flox-environments", "canary-watch",
    "config-gc", "content-hash-cache-pattern", "hermes-imports",
    "nodejs-keccak256", "nutrient-document-processing", "opensource-pipeline",
    "recursive-decision-ledger", "santa-method", "taste", "tinystruct-patterns",
    "visa-doc-translate", "vite-patterns", "vue-patterns", "angular-developer",
    "design-system", "frontend-design-direction", "frontend-a11y",
    "frontend-slides", "ai-first-engineering", "ai-regression-testing",
    "accessibility", "blueprint", "click-path-audit",
    "codehealth-mcp", "enterprise-agent-ops",
    "react-patterns", "python-patterns", "golang-patterns", "rust-patterns",
    "backend-patterns", "frontend-patterns", "deployment-patterns",
    "api-design", "intent-driven-development",
    "skill-stocktake", "skill-comply", "skill-scout",
    "continuous-learning-v2", "benchmark", "benchmark-optimization-loop",
]

# ---- INSPECT_LATER skills (specialized domains) ----
_INSPECT_LATER_SKILL_IDS = [
    "android-clean-architecture", "ios-icon-gen", "blender-motion-state-inspection",
    "clickhouse-io", "defi-amm-security", "evm-token-decimals",
    "llm-trading-agent-security", "prediction-market-oracle-research",
    "prediction-market-risk-review", "ito-basket-compare",
    "ito-data-atlas-agent", "ito-market-intelligence", "ito-trade-planner",
    "carrier-relationship-management", "customs-trade-compliance",
    "healthcare-cdss-patterns", "healthcare-emr-patterns",
    "healthcare-eval-harness", "healthcare-phi-compliance",
    "cisco-ios-patterns", "windows-desktop-e2e", "manim-video",
    "remotion-video-creation", "foundation-models-on-device",
    "energy-procurement", "finance-billing-ops", "customer-billing-ops",
    "quality-nonconformance", "inventory-demand-planning",
    "returns-reverse-logistics", "production-scheduling",
    "scientific-db-pubmed-database", "scientific-db-uspto-database",
    "scientific-pkg-gget", "scientific-thinking-literature-review",
    "scientific-thinking-scholar-evaluation", "homelab-network-readiness",
    "homelab-network-setup", "homelab-pihole-dns", "homelab-vlan-segmentation",
    "homelab-wireguard-vpn", "hipaa-compliance", "netmiko-ssh-automation",
    "network-bgp-diagnostics", "network-config-validation",
    "network-interface-health",
    "dart-flutter-patterns", "compose-multiplatform-patterns",
    "kotlin-coroutines-flows", "kotlin-exposed-patterns",
    "kotlin-ktor-patterns", "kotlin-patterns", "kotlin-testing",
    "cpp-coding-standards", "cpp-testing", "csharp-testing", "fsharp-testing",
    "java-coding-standards", "jpa-patterns",
    "django-celery", "django-patterns", "django-security",
    "django-tdd", "django-verification",
    "laravel-patterns", "laravel-plugin-discovery", "laravel-security",
    "laravel-tdd", "laravel-verification", "nestjs-patterns", "nuxt4-patterns",
    "fastapi-patterns", "quarkus-patterns", "quarkus-security", "quarkus-tdd",
    "quarkus-verification", "springboot-patterns", "springboot-security",
    "springboot-tdd", "springboot-verification",
    "mysql-patterns", "postgres-patterns", "redis-patterns",
    "database-migrations", "prisma-patterns", "hexagonal-architecture",
    "pytorch-patterns", "ml-adoption-playbook", "mle-workflow",
    "gan-style-harness", "swift-actor-persistence",
    "swift-concurrency-6-2", "swift-protocol-di-testing", "swiftui-patterns",
    "ralphinho-rfc-pipeline", "regex-vs-llm-structured-text",
    "connections-optimizer", "parallel-execution-optimizer",
]

# ---- ACTIVE contexts ----
_ACTIVE_CONTEXTS = ["dev", "research", "review"]

# ---- Agents: planning/review roles → INSTALLED_DISABLED (need routing wiring) ----
_REVIEW_AGENT_IDS = [
    "code-reviewer", "security-reviewer", "planner", "architect",
    "tdd-guide", "spec-miner", "refactor-cleaner", "doc-updater",
    "build-error-resolver", "reviewer", "explorer",
]

# ---- Agent-only ECC agents → ADAPT_NEEDED ----
_ADAPT_AGENT_IDS = [
    "e2e-runner", "docs-researcher", "explorer", "reviewer",
]

# ---- Safe guidance commands → ACTIVE ----
_ACTIVE_COMMAND_IDS = ["checkpoint", "feature-development", "add-language-rules"]

# ---- Hook/script/plugin/MCP → ADAPT_NEEDED by default ----


# ---------------------------------------------------------------------------
# Catalog entry builder helpers
# ---------------------------------------------------------------------------

def _skill_entry(
    skill_id: str,
    state: str,
    risk_tier: str = "low",
    priority: str = "inspect_later",
    reason: str = "",
    jarvis_skill_id: Optional[str] = None,
    preflight_passed: bool = False,
    reviewer_approved: bool = False,
) -> Dict[str, Any]:
    return {
        "candidate_id": f"ecc:{skill_id}",
        "category": "skill",
        "name": skill_id,
        "state": state,
        "risk_tier": risk_tier,
        "priority": priority,
        "permission_scopes": ["read_only"] if state == "active" else [],
        "cost_tier": "free" if state in ("active", "installed_disabled") else "unknown",
        "license_spdx": ECC_LICENSE_SPDX,
        "source_url": ECC_SOURCE,
        "source_name": "ECC",
        "reason": reason,
        "jarvis_skill_id": jarvis_skill_id,
        "preflight_passed": preflight_passed,
        "reviewer_approved": reviewer_approved,
        "rollback_available": True,
        "ui_route": f"skill:{jarvis_skill_id}:invoke" if jarvis_skill_id else None,
    }


def _build_static_catalog() -> Dict[str, Dict[str, Any]]:
    """Build the full static catalog dict: candidate_id → entry."""
    catalog: Dict[str, Dict[str, Any]] = {}

    # Active skills (already have full entries — ensure source_url/license_spdx present)
    for entry in _ACTIVE_SKILLS:
        if "source_url" not in entry:
            entry["source_url"] = ECC_SOURCE
        if "license_spdx" not in entry:
            entry["license_spdx"] = ECC_LICENSE_SPDX
        if "rollback_available" not in entry:
            entry["rollback_available"] = True
        catalog[entry["candidate_id"]] = entry

    # Disabled skills
    for sid in _DISABLED_SKILL_IDS:
        cid = f"ecc:{sid}"
        if cid not in catalog:
            catalog[cid] = _skill_entry(
                sid, "installed_disabled",
                risk_tier="medium", priority="adapt_needed",
                reason="Requires external API key, network access, or secret configuration.",
            )

    # Adapt-needed skills
    for sid in _ADAPT_NEEDED_SKILL_IDS:
        cid = f"ecc:{sid}"
        if cid not in catalog:
            catalog[cid] = _skill_entry(
                sid, "adapt_needed",
                risk_tier="medium", priority="adapt_needed",
                reason="Requires Jarvis execution wiring, framework dependency, or runtime integration.",
            )

    # Inspect-later skills
    for sid in _INSPECT_LATER_SKILL_IDS:
        cid = f"ecc:{sid}"
        if cid not in catalog:
            catalog[cid] = _skill_entry(
                sid, "inspect_later",
                risk_tier="low", priority="inspect_later",
                reason="Specialized domain or framework — review for Jarvis relevance before adoption.",
            )

    # Contexts
    for ctx in _ACTIVE_CONTEXTS:
        catalog[f"ecc:context:{ctx}"] = {
            "candidate_id": f"ecc:context:{ctx}",
            "category": "context",
            "name": ctx,
            "state": "active",
            "risk_tier": "low",
            "priority": "likely_adopt",
            "permission_scopes": ["read_only"],
            "cost_tier": "free",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_url": ECC_SOURCE,
            "source_name": "ECC",
            "reason": "Context document — pure guidance, safe for Jarvis context injection.",
            "preflight_passed": True,
            "reviewer_approved": True,
            "rollback_available": True,
            "ui_route": f"context:ecc_{ctx}:inject",
        }

    # Agents — planning/review roles
    for aid in _REVIEW_AGENT_IDS:
        catalog[f"ecc:agent:{aid}"] = {
            "candidate_id": f"ecc:agent:{aid}",
            "category": "agent",
            "name": aid,
            "state": "installed_disabled",
            "risk_tier": "low",
            "priority": "likely_adopt",
            "permission_scopes": ["read_only"],
            "cost_tier": "free",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_url": ECC_SOURCE,
            "source_name": "ECC",
            "reason": "Planning/review agent — safe role, needs Jarvis agent routing integration before activation.",
            "preflight_passed": True,
            "reviewer_approved": False,
            "rollback_available": True,
            "ui_route": None,
        }

    # Agents — adapt needed
    for aid in _ADAPT_AGENT_IDS:
        cid = f"ecc:agent:{aid}"
        if cid not in catalog:
            catalog[cid] = {
                "candidate_id": cid,
                "category": "agent",
                "name": aid,
                "state": "adapt_needed",
                "risk_tier": "medium",
                "priority": "adapt_needed",
                "permission_scopes": [],
                "cost_tier": "unknown",
                "license_spdx": ECC_LICENSE_SPDX,
                "source_url": ECC_SOURCE,
                "source_name": "ECC",
                "reason": "Execution agent — needs sandbox, permission scope, and rollback wiring.",
                "preflight_passed": False,
                "reviewer_approved": False,
                "rollback_available": True,
                "ui_route": None,
            }

    # Commands
    for cmd in _ACTIVE_COMMAND_IDS:
        catalog[f"ecc:cmd:{cmd}"] = {
            "candidate_id": f"ecc:cmd:{cmd}",
            "category": "command",
            "name": cmd,
            "state": "active",
            "risk_tier": "low",
            "priority": "likely_adopt",
            "permission_scopes": ["read_only"],
            "cost_tier": "free",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_url": ECC_SOURCE,
            "source_name": "ECC",
            "reason": "Guidance/planning command — safe for Jarvis workflows.",
            "preflight_passed": True,
            "reviewer_approved": True,
            "rollback_available": True,
            "ui_route": f"command:ecc_{cmd}:run",
        }

    # Known command IDs from ECC inventory (INSTALLED_DISABLED by default)
    known_commands = [
        "database-migration", "build-fix", "security-review",
        "code-review", "review", "plan",
    ]
    for cmd in known_commands:
        cid = f"ecc:cmd:{cmd}"
        if cid not in catalog:
            catalog[cid] = {
                "candidate_id": cid,
                "category": "command",
                "name": cmd,
                "state": "installed_disabled",
                "risk_tier": "medium",
                "priority": "inspect_later",
                "permission_scopes": [],
                "cost_tier": "unknown",
                "license_spdx": ECC_LICENSE_SPDX,
                "source_url": ECC_SOURCE,
                "source_name": "ECC",
                "reason": "Command not individually reviewed — registered disabled pending assessment.",
                "preflight_passed": False,
                "reviewer_approved": False,
                "rollback_available": True,
                "ui_route": None,
            }

    # Hooks (from ECC inventory — adapt_needed by default)
    known_hooks = [
        "adapter", "after-file-edit", "after-mcp-execution",
        "after-shell-execution", "after-tab-file-edit",
        "before-tool-call", "notification", "on-error",
        "pre-commit", "post-task",
    ]
    for hid in known_hooks:
        catalog[f"ecc:hook:{hid}"] = {
            "candidate_id": f"ecc:hook:{hid}",
            "category": "hook",
            "name": hid,
            "state": "adapt_needed",
            "risk_tier": "medium",
            "priority": "adapt_needed",
            "permission_scopes": [],
            "cost_tier": "unknown",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_url": ECC_SOURCE,
            "source_name": "ECC",
            "reason": "Hook requires Jarvis event system, dry-run support, and explicit event scope before activation.",
            "preflight_passed": False,
            "reviewer_approved": False,
            "rollback_available": True,
            "ui_route": None,
        }

    # Plugins (adapt_needed)
    known_plugins = [
        "marketplace", "ecc-hooks", "index",
        "changed-files-store", "lib",
    ]
    for pid in known_plugins:
        catalog[f"ecc:plugin:{pid}"] = {
            "candidate_id": f"ecc:plugin:{pid}",
            "category": "plugin",
            "name": pid,
            "state": "adapt_needed",
            "risk_tier": "high",
            "priority": "adapt_needed",
            "permission_scopes": [],
            "cost_tier": "unknown",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_url": ECC_SOURCE,
            "source_name": "ECC",
            "reason": "Plugin requires compatibility wrapper, isolation testing, and loading gate.",
            "preflight_passed": False,
            "reviewer_approved": False,
            "rollback_available": True,
            "ui_route": None,
        }

    # MCP configs (installed_disabled — need security review)
    known_mcp = ["mcp-servers"]
    for mid in known_mcp:
        catalog[f"ecc:mcp:{mid}"] = {
            "candidate_id": f"ecc:mcp:{mid}",
            "category": "mcp_config",
            "name": mid,
            "state": "installed_disabled",
            "risk_tier": "high",
            "priority": "adapt_needed",
            "permission_scopes": [],
            "cost_tier": "unknown",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_url": ECC_SOURCE,
            "source_name": "ECC",
            "reason": "MCP config requires security review, permission scope audit, and explicit activation gate.",
            "preflight_passed": False,
            "reviewer_approved": False,
            "rollback_available": True,
            "ui_route": None,
        }

    return catalog


# Module-level catalog (built at import time — no network calls)
_STATIC_CATALOG: Dict[str, Dict[str, Any]] = _build_static_catalog()


# ---------------------------------------------------------------------------
# ECCCatalog — query interface
# ---------------------------------------------------------------------------


class ECCCatalog:
    """Jarvis-visible query interface for the ECC candidate catalog.

    Operates in static mode (default) or dynamic mode (loads from JSON if available).

    Usage:
        catalog = ECCCatalog()
        active = catalog.list_active()
        summary = catalog.get_status_summary()
        skill = catalog.get("ecc:benchmark-methodology")
    """

    def __init__(self, registry_json_path: Optional[Path] = None) -> None:
        """Initialize catalog.

        Args:
            registry_json_path: Optional path to generated registry JSON.
                                If provided and exists, loads dynamic registry.
                                Otherwise uses static catalog.
        """
        self._static = _STATIC_CATALOG
        self._dynamic: Optional[Dict[str, Dict]] = None

        if registry_json_path and Path(registry_json_path).exists():
            try:
                data = json.loads(Path(registry_json_path).read_text())
                self._dynamic = {c["candidate_id"]: c for c in data.get("candidates", [])}
            except Exception:
                self._dynamic = None

    def _entries(self) -> Dict[str, Dict]:
        if self._dynamic is not None:
            return {**self._static, **self._dynamic}
        return self._static

    def get(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Return catalog entry for a candidate_id, or None if not found."""
        return self._entries().get(candidate_id)

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all catalog entries."""
        return list(self._entries().values())

    def list_by_state(self, state: str) -> List[Dict[str, Any]]:
        """Return all entries in a given state."""
        return [e for e in self._entries().values() if e.get("state") == state]

    def list_active(self) -> List[Dict[str, Any]]:
        """Return all ACTIVE entries (usable, reviewer-approved, read-only)."""
        return self.list_by_state("active")

    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Return all entries of a given category."""
        return [e for e in self._entries().values() if e.get("category") == category]

    def get_status_summary(self) -> Dict[str, Any]:
        """Return a structured status summary for API/CLI reporting."""
        entries = self._entries()
        state_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}
        active_items: List[str] = []

        for entry in entries.values():
            state = entry.get("state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1

            cat = entry.get("category", "other")
            category_counts[cat] = category_counts.get(cat, 0) + 1

            if state == "active":
                active_items.append(entry.get("candidate_id", ""))

        # HOLD breakdown
        hold_by_category: Dict[str, int] = {}
        for entry in entries.values():
            if entry.get("state") != "active":
                cat = entry.get("category", "other")
                hold_by_category[cat] = hold_by_category.get(cat, 0) + 1

        return {
            "source": ECC_SOURCE,
            "license": ECC_LICENSE_SPDX,
            "license_verified": ECC_LICENSE_VERIFIED,
            "total_registered": len(entries),
            "state_counts": state_counts,
            "category_counts": category_counts,
            "active_count": state_counts.get("active", 0),
            "active_items": sorted(active_items),
            "hold_by_category": hold_by_category,
            "activation_policy": {
                "active": "Safe read-only/guidance items, MIT licensed, no external dependencies",
                "installed_disabled": "Safe but needs API key, secrets, or explicit activation",
                "adapt_needed": "Needs Jarvis execution wiring, framework dependency, or sandbox",
                "inspect_later": "Specialized domain — review for Jarvis relevance",
                "quarantined": "Blocked — safety concern or gate failure",
                "rejected": "Not applicable to Jarvis",
                "duplicate": "Same capability exists elsewhere in Jarvis",
            },
            "no_ecc_code_executed": True,
            "python_local_first": True,
        }

    def find_by_jarvis_skill_id(self, jarvis_skill_id: str) -> Optional[Dict[str, Any]]:
        """Find a catalog entry by its Jarvis skill ID."""
        for entry in self._entries().values():
            if entry.get("jarvis_skill_id") == jarvis_skill_id:
                return entry
        return None

    def list_hold_blockers(self) -> List[Dict[str, str]]:
        """Return a list of items not in ACTIVE state with their blocker reasons."""
        return [
            {
                "candidate_id": e["candidate_id"],
                "category": e.get("category", "?"),
                "state": e.get("state", "?"),
                "reason": e.get("reason", "no reason recorded"),
            }
            for e in self._entries().values()
            if e.get("state") != "active"
        ]

    def format_cli_report(self) -> str:
        """Return a text summary suitable for CLI/API output."""
        summary = self.get_status_summary()
        lines = [
            "=" * 70,
            "JARVIS ECC CATALOG — Intake Status Report",
            "=" * 70,
            f"Source:    {summary['source']}",
            f"License:   {summary['license']} (verified: {summary['license_verified']})",
            f"Total:     {summary['total_registered']} unique capabilities registered",
            f"Active:    {summary['active_count']} items immediately usable",
            "",
            "STATE COUNTS",
            "-" * 40,
        ]
        for state, count in sorted(summary["state_counts"].items(), key=lambda x: -x[1]):
            lines.append(f"  {state:<30} {count:>4}")

        lines += ["", "CATEGORY COUNTS", "-" * 40]
        for cat, count in sorted(summary["category_counts"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat:<30} {count:>4}")

        lines += ["", f"ACTIVE ITEMS ({summary['active_count']})", "-" * 40]
        for item in summary["active_items"]:
            lines.append(f"  {item}")

        lines += [
            "",
            "HOLD SUMMARY BY CATEGORY",
            "-" * 40,
        ]
        for cat, count in sorted(summary["hold_by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat:<30} {count:>4} items on HOLD")

        lines += [
            "",
            "NOTE: No ECC code executed. Active items are read-only guidance (MIT).",
            "=" * 70,
        ]
        return "\n".join(lines)


# Module-level singleton
_DEFAULT_CATALOG: Optional[ECCCatalog] = None


def get_catalog(registry_json_path: Optional[Path] = None) -> ECCCatalog:
    """Return the default ECCCatalog instance (singleton unless path given)."""
    global _DEFAULT_CATALOG
    if registry_json_path is not None:
        return ECCCatalog(registry_json_path=registry_json_path)
    if _DEFAULT_CATALOG is None:
        _DEFAULT_CATALOG = ECCCatalog()
    return _DEFAULT_CATALOG


__all__ = [
    "ECCCatalog",
    "get_catalog",
    "ECC_SOURCE",
    "ECC_LICENSE_SPDX",
    "ECC_LICENSE_VERIFIED",
]
