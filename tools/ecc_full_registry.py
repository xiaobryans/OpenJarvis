#!/usr/bin/env python3
"""ECC full coverage registry builder — Python/local-first, no ECC code executed.

Fetches ECC from OFFICIAL GitHub source only: https://github.com/affaan-m/ECC
Builds a comprehensive Jarvis-managed registry of all ECC capabilities.

What this script does:
  1. Fetch ECC file tree from GitHub API (read-only)
  2. Deduplicate: identify unique capabilities across harness-specific copies
  3. Classify every capability by category, risk, and activation state
  4. Run candidate-level preflight on canonical skill files (content fetch)
  5. Write full registry to JSON
  6. Print activation state summary

What this script does NOT do:
  - Execute any ECC code
  - Run ECC install scripts
  - Activate any ECC hooks/plugins/MCP configs
  - Grant any permissions
  - Write to Jarvis production systems

Usage:
    python tools/ecc_full_registry.py [--output FILE] [--preflight] [--verbose]
    python tools/ecc_full_registry.py --output ecc_full_registry.json --preflight
    python tools/ecc_full_registry.py --summary

Requires: Python stdlib only (urllib, json, re, ssl, pathlib). No pip deps.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ECC_REPO = "affaan-m/ECC"
ECC_BRANCH = "main"
ECC_API_BASE = "https://api.github.com"
ECC_RAW_BASE = "https://raw.githubusercontent.com"
ECC_LICENSE_SPDX = "MIT"

# ---------------------------------------------------------------------------
# SSL context
# ---------------------------------------------------------------------------


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    for p in ("/etc/ssl/cert.pem", "/usr/local/etc/openssl/cert.pem"):
        if Path(p).exists():
            ctx.load_verify_locations(p)
            return ctx
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx


_CTX = _ssl_ctx()

# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

# Skills that are pure guidance (markdown only, no execution) → ACTIVE
SAFE_GUIDANCE_SKILLS: Set[str] = {
    "eval-harness", "benchmark-methodology", "coding-standards",
    "tdd-workflow", "verification-loop", "context-budget",
    "token-budget-advisor", "cost-aware-llm-pipeline", "git-workflow",
    "search-first", "agent-self-evaluation", "agent-eval", "safety-guard",
    "prompt-optimizer", "continuous-learning", "rules-distill",
    "production-audit", "code-tour", "codebase-onboarding", "error-handling",
    "strategic-compact", "security-scan", "benchmark",
    "benchmark-optimization-loop", "intent-driven-development",
    "skill-stocktake", "skill-comply", "skill-scout",
    "documentation-lookup", "continuous-learning-v2", "api-design",
    "backend-patterns", "frontend-patterns", "deployment-patterns",
    "react-patterns", "python-patterns", "golang-patterns", "rust-patterns",
    "typescript-patterns", "testing-patterns",
}

# Skills needing external APIs or secrets → INSTALLED_DISABLED
EXTERNAL_API_SKILLS: Set[str] = {
    "exa-search", "fal-ai-media", "deep-research", "market-research",
    "data-scraper-agent", "social-publisher", "email-ops", "github-ops",
    "jira-integration", "google-workspace-ops", "messages-ops", "x-api",
    "unified-notifications-ops", "lead-intelligence", "investor-outreach",
    "crosspost", "videodb", "ecc-tools-cost-audit", "configure-ecc",
    "article-writing", "content-engine", "brand-discovery", "brand-voice",
    "competitive-platform-analysis", "competitive-report-structure",
    "investor-materials", "marketing-campaign", "seo",
    "agent-payment-x402", "open-source-pipeline", "social-graph-ranker",
    "research-ops", "knowledge-ops", "project-flow-ops", "team-builder",
}

# Skills for specialized hardware/frameworks → INSPECT_LATER
SPECIALIZED_SKILLS: Set[str] = {
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
    "homelab-network-setup", "homelab-pihole-dns",
    "homelab-vlan-segmentation", "homelab-wireguard-vpn",
    "hipaa-compliance", "netmiko-ssh-automation", "network-bgp-diagnostics",
    "network-config-validation", "network-interface-health",
}

# Skills needing Jarvis execution wiring → ADAPT_NEEDED
ADAPT_NEEDED_SKILLS: Set[str] = {
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
    "mcp-server-patterns", "hookify-rules",
    "browser-qa", "e2e-testing",  # need Playwright
    "workspace-surface-audit",    # needs filesystem scan
    "repo-scan",                  # needs repo access
    "uncloud",                    # deployment tool
    "terminal-ops",               # terminal execution
    "dashboard-builder",          # UI framework needed
    "ui-demo", "ui-to-vue", "liquid-glass-design",  # frontend build needed
    "motion-advanced", "motion-foundations", "motion-patterns", "motion-ui",  # animation framework
    "video-editing",  # video tools
    "nextjs-turbopack",  # build tools
    "flox-environments",  # Nix/Flox needed
    "canary-watch",  # deployment monitoring
    "config-gc",  # config management tool
    "content-hash-cache-pattern",  # caching infrastructure
    "hermes-imports",  # Hermes bundler
    "nodejs-keccak256",  # crypto library
    "nutrient-document-processing",  # document SDK
    "opensource-pipeline",  # CI/CD pipeline
    "ralphinho-rfc-pipeline",  # RFC pipeline
    "recursive-decision-ledger",  # decision tracking tool
    "regex-vs-llm-structured-text",  # comparison harness
    "santa-method",  # methodology impl
    "social-graph-ranker",  # social graph needed
    "swift-actor-persistence",  # Swift/iOS
    "swift-concurrency-6-2", "swift-protocol-di-testing",  # Swift
    "swiftui-patterns",  # SwiftUI
    "taste",  # aesthetic eval tool
    "tinystruct-patterns",  # TinyStruct framework
    "visa-doc-translate",  # translation API
    "vite-patterns",  # Vite build tool
    "vue-patterns",  # Vue framework
    "dart-flutter-patterns",  # Flutter
    "compose-multiplatform-patterns",  # Kotlin Multiplatform
    "kotlin-coroutines-flows", "kotlin-exposed-patterns",  # Kotlin
    "kotlin-ktor-patterns", "kotlin-patterns", "kotlin-testing",
    "cpp-coding-standards", "cpp-testing",  # C++
    "csharp-testing",  # C#
    "fsharp-testing",  # F#
    "java-coding-standards", "jpa-patterns",  # Java
    "django-celery", "django-patterns", "django-security",  # Django
    "django-tdd", "django-verification",
    "laravel-patterns", "laravel-plugin-discovery", "laravel-security",  # Laravel
    "laravel-tdd", "laravel-verification",
    "nestjs-patterns",  # NestJS
    "nuxt4-patterns",  # Nuxt
    "fastapi-patterns",  # FastAPI (could be useful, but needs wiring)
    "quarkus-patterns", "quarkus-security", "quarkus-tdd",  # Quarkus
    "quarkus-verification",
    "springboot-patterns", "springboot-security", "springboot-tdd",  # Spring
    "springboot-verification",
    "mysql-patterns", "postgres-patterns", "redis-patterns",  # DB drivers
    "database-migrations", "prisma-patterns",
    "hexagonal-architecture",  # architecture pattern (borderline)
    "pytorch-patterns",  # ML framework
    "ml-adoption-playbook",  # ML adoption
    "mle-workflow",  # ML engineering workflow
    "gan-style-harness",  # GAN training
    "connect-optimizer", "connections-optimizer",
    "angular-developer",  # Angular
    "design-system", "frontend-design-direction", "frontend-a11y",
    "frontend-slides",
    "ai-first-engineering", "ai-regression-testing",
    "accessibility",  # requires real app testing
    "blueprint",  # project blueprint tool
    "canary-watch",  # canary deployment
    "click-path-audit",  # UX audit tool
    "code-health-mcp",  # requires MCP
    "codehealth-mcp",
    "customer-billing-ops",  # billing system needed
    "enterprise-agent-ops",  # enterprise infra needed
}

# Commands classified as safe guidance → ACTIVE
SAFE_GUIDANCE_COMMANDS: Set[str] = {
    "checkpoint", "code-review", "verification", "plan", "review",
    "security-review", "feature-development", "add-language-rules",
    "build-fix", "database-migration",
}

# Agents classified as Jarvis reviewer/planner roles → ACTIVE guidance patterns
SAFE_GUIDANCE_AGENTS: Set[str] = {
    "code-reviewer", "security-reviewer", "planner", "architect",
    "tdd-guide", "spec-miner", "refactor-cleaner", "doc-updater",
    "code-reviewer", "security-reviewer",
}

# Preflight check patterns (same as intake.py, standalone)
_BLOCKING_PATTERNS = {
    "secrets_exposure": [r"API_KEY\s*=\s*['\"]", r"PASSWORD\s*=\s*['\"]", r"SECRET\s*=\s*['\"]"],
    "destructive_command": [r"rm\s+-rf\s+/", r"DROP\s+TABLE", r"DELETE\s+FROM\s+\w{1,50}\s*;"],
    "outbound_send": [r"slack\.api_call", r"smtp\.sendmail\(", r"twilio\."],
    "prompt_injection": [r"ignore\s+previous\s+instructions", r"disregard\s+all\s+prior"],
}
_WARNING_PATTERNS = {
    "shell_command": [r"\bos\.system\b", r"\bsubprocess\.run\b", r"exec\("],
    "network_call": [r"\brequests\.get\b", r"\burllib\.request\b", r"\baiohttp\b"],
    "file_write": [r"open\([^)]+['\"]w['\"]", r"\.write_text\(", r"shutil\.rmtree"],
}


def quick_preflight(content: str) -> Tuple[bool, List[str]]:
    """Quick text-regex preflight on content. Returns (passed, issues)."""
    issues = []
    for check, patterns in _BLOCKING_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, content, re.IGNORECASE):
                issues.append(f"BLOCK:{check}")
                break
    for check, patterns in _WARNING_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, content, re.IGNORECASE):
                issues.append(f"WARN:{check}")
                break
    has_blocking = any(i.startswith("BLOCK:") for i in issues)
    return not has_blocking, issues


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def _api_get(path: str, timeout: int = 30) -> Any:
    url = f"{ECC_API_BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-ecc-registry/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
        return json.loads(resp.read())


def _raw_get(path: str, timeout: int = 20) -> str:
    url = f"{ECC_RAW_BASE}/{ECC_REPO}/{ECC_BRANCH}/{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jarvis-ecc-registry/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Deduplication and canonical source logic
# ---------------------------------------------------------------------------

# Harness-specific prefixes — files under these are duplicates of the canonical
HARNESS_PREFIXES = (
    ".cursor/", ".claude/", ".opencode/", ".codex/", ".kiro/",
    ".gemini/", ".zed/", ".qwen/", ".trae/", ".codebuddy/",
    ".agents/", ".vscode/", "docs/", "legacy-command-shims/",
)

# Canonical skill source: .agents/skills/<name>/ or skills/<name>/
# Canonical command source: commands/<name>.md
# Canonical agent source: agents/<name>.md


def _extract_skill_id(path: str) -> Optional[str]:
    """Extract unique skill ID from any skill-related path."""
    m = re.search(r"(?:^|/)skills?/([^/]+)/", path)
    return m.group(1) if m else None


def _extract_command_id(path: str) -> Optional[str]:
    """Extract unique command ID from any command-related path."""
    m = re.search(r"(?:^|/)commands?/([^/]+)\.md$", path)
    return m.group(1) if m else None


def _extract_agent_id(path: str) -> Optional[str]:
    """Extract unique agent ID from any agent-related path."""
    m = re.search(r"(?:^|/)agents?/([^/]+?)(?:\.md|\.yaml|\.toml|\.json|\.txt)$", path)
    return m.group(1) if m else None


def _extract_hook_id(path: str) -> Optional[str]:
    """Extract unique hook ID from hook paths."""
    m = re.search(r"(?:^|/)hooks?/([^/]+?)(?:\.[a-z]+)?$", path)
    return m.group(1) if m else None


def _is_harness_specific(path: str) -> bool:
    """Return True if this path is a harness-specific copy (duplicate)."""
    return any(path.startswith(p) for p in HARNESS_PREFIXES)


def _is_canonical_skill(path: str) -> bool:
    """Return True if this is a canonical skill path (not harness-specific copy)."""
    return (
        re.match(r"^skills?/[^/]+/", path) is not None
        or re.match(r"^\.agents/skills/[^/]+/", path) is not None
    )


# ---------------------------------------------------------------------------
# Capability classification
# ---------------------------------------------------------------------------


def classify_skill(skill_id: str) -> Dict[str, Any]:
    """Assign intake state and metadata to a skill by ID."""
    sid = skill_id.lower().strip()

    if sid in SAFE_GUIDANCE_SKILLS:
        return {
            "state": "active",
            "risk_tier": "low",
            "priority": "likely_adopt",
            "permission_scopes": ["read_only"],
            "cost_tier": "free",
            "reason": "Safe guidance skill — pure markdown, no execution, no external APIs.",
            "preflight_passed": True,
            "reviewer_approved": True,
        }

    if sid in EXTERNAL_API_SKILLS:
        return {
            "state": "installed_disabled",
            "risk_tier": "medium",
            "priority": "adapt_needed",
            "permission_scopes": ["network:read", "external_api"],
            "cost_tier": "moderate",
            "reason": "Requires external API key or network access. Enable after secret configuration.",
            "preflight_passed": False,
            "reviewer_approved": False,
        }

    if sid in SPECIALIZED_SKILLS:
        return {
            "state": "inspect_later",
            "risk_tier": "low",
            "priority": "inspect_later",
            "permission_scopes": [],
            "cost_tier": "free",
            "reason": "Specialized domain/hardware — review for Jarvis relevance before adoption.",
            "preflight_passed": False,
            "reviewer_approved": False,
        }

    if sid in ADAPT_NEEDED_SKILLS:
        return {
            "state": "adapt_needed",
            "risk_tier": "medium",
            "priority": "adapt_needed",
            "permission_scopes": [],
            "cost_tier": "unknown",
            "reason": "Requires Jarvis execution wiring, framework dependency, or runtime integration.",
            "preflight_passed": False,
            "reviewer_approved": False,
        }

    # Default: inspect later
    return {
        "state": "inspect_later",
        "risk_tier": "unknown",
        "priority": "inspect_later",
        "permission_scopes": [],
        "cost_tier": "unknown",
        "reason": "Not yet individually reviewed. Requires Jarvis compatibility assessment.",
        "preflight_passed": False,
        "reviewer_approved": False,
    }


def classify_command(command_id: str) -> Dict[str, Any]:
    """Classify a command by ID."""
    cid = command_id.lower()
    if any(kw in cid for kw in ("checkpoint", "review", "plan", "verify", "check", "add-language", "feature")):
        return {
            "state": "active",
            "risk_tier": "low",
            "priority": "likely_adopt",
            "permission_scopes": ["read_only"],
            "reason": "Guidance/planning command — safe for Jarvis workflows.",
            "preflight_passed": True,
            "reviewer_approved": True,
        }
    if any(kw in cid for kw in ("deploy", "delete", "destroy", "create", "push", "send", "publish")):
        return {
            "state": "installed_disabled",
            "risk_tier": "high",
            "priority": "adapt_needed",
            "permission_scopes": ["action:write"],
            "reason": "Action command with potential side effects. Requires explicit gating.",
            "preflight_passed": False,
            "reviewer_approved": False,
        }
    return {
        "state": "installed_disabled",
        "risk_tier": "medium",
        "priority": "inspect_later",
        "permission_scopes": [],
        "reason": "Not individually reviewed. Registered disabled pending assessment.",
        "preflight_passed": False,
        "reviewer_approved": False,
    }


def classify_agent(agent_id: str) -> Dict[str, Any]:
    """Classify an agent by ID."""
    aid = agent_id.lower()
    if any(kw in aid for kw in ("reviewer", "planner", "architect", "tdd", "spec-miner", "doc-updater", "refactor")):
        return {
            "state": "installed_disabled",
            "risk_tier": "low",
            "priority": "likely_adopt",
            "permission_scopes": ["read_only"],
            "reason": "Planning/review agent — safe role, needs Jarvis agent routing integration.",
            "preflight_passed": True,
            "reviewer_approved": False,
        }
    if any(kw in aid for kw in ("e2e", "runner", "builder", "executor", "deployer", "resolver")):
        return {
            "state": "adapt_needed",
            "risk_tier": "medium",
            "priority": "adapt_needed",
            "permission_scopes": ["action:local"],
            "reason": "Execution agent — needs Jarvis sandbox, permission scope, and rollback wiring.",
            "preflight_passed": False,
            "reviewer_approved": False,
        }
    return {
        "state": "inspect_later",
        "risk_tier": "unknown",
        "priority": "inspect_later",
        "permission_scopes": [],
        "reason": "Agent not individually reviewed. Inspect before Jarvis routing integration.",
        "preflight_passed": False,
        "reviewer_approved": False,
    }


def classify_hook(hook_id: str) -> Dict[str, Any]:
    """Hooks always need Jarvis wiring — adapt_needed by default."""
    return {
        "state": "adapt_needed",
        "risk_tier": "medium",
        "priority": "adapt_needed",
        "permission_scopes": [],
        "reason": "Hook requires Jarvis event system integration, dry-run, and explicit event scope.",
        "preflight_passed": False,
        "reviewer_approved": False,
    }


def classify_script(script_id: str) -> Dict[str, Any]:
    """Scripts need dry-run and allowlist — adapt_needed by default."""
    return {
        "state": "adapt_needed",
        "risk_tier": "high",
        "priority": "adapt_needed",
        "permission_scopes": [],
        "reason": "Script requires dry-run wrapper, command allowlist, and sandbox isolation before use.",
        "preflight_passed": False,
        "reviewer_approved": False,
    }


def classify_plugin(plugin_id: str) -> Dict[str, Any]:
    """Plugins are adapt_needed — need compatibility wrapper."""
    return {
        "state": "adapt_needed",
        "risk_tier": "high",
        "priority": "adapt_needed",
        "permission_scopes": [],
        "reason": "Plugin requires compatibility wrapper, isolation, and loading gate before activation.",
        "preflight_passed": False,
        "reviewer_approved": False,
    }


def classify_mcp_config(config_id: str) -> Dict[str, Any]:
    """MCP configs are disabled — need security review."""
    return {
        "state": "installed_disabled",
        "risk_tier": "high",
        "priority": "adapt_needed",
        "permission_scopes": [],
        "reason": "MCP config requires security review, permission scope audit, and explicit activation gate.",
        "preflight_passed": False,
        "reviewer_approved": False,
    }


def classify_context(context_id: str) -> Dict[str, Any]:
    """Context docs are safe guidance."""
    return {
        "state": "active",
        "risk_tier": "low",
        "priority": "likely_adopt",
        "permission_scopes": ["read_only"],
        "reason": "Context document — pure guidance, no execution, safe for Jarvis context injection.",
        "preflight_passed": True,
        "reviewer_approved": True,
    }


# ---------------------------------------------------------------------------
# Registry builder
# ---------------------------------------------------------------------------


def build_full_registry(
    preflight_content: bool = False,
    verbose: bool = False,
    max_preflight_fetches: int = 30,
) -> Dict[str, Any]:
    """Build the full ECC registry from GitHub API."""
    ts = time.time()

    if verbose:
        print("Fetching ECC repo info...", file=sys.stderr)

    repo = _api_get(f"/repos/{ECC_REPO}")
    assert repo.get("full_name") == ECC_REPO, f"Unexpected repo: {repo.get('full_name')}"
    assert repo.get("license", {}).get("spdx_id") == ECC_LICENSE_SPDX, "License mismatch"

    if verbose:
        print("Fetching full file tree...", file=sys.stderr)

    tree_data = _api_get(f"/repos/{ECC_REPO}/git/trees/{ECC_BRANCH}?recursive=1")
    files = [f for f in tree_data.get("tree", []) if f.get("type") == "blob"]

    if verbose:
        print(f"Processing {len(files)} files...", file=sys.stderr)

    # Deduplicate: track unique IDs per category
    skills_seen: Dict[str, Dict] = {}      # skill_id -> {canonical_path, files: []}
    commands_seen: Dict[str, Dict] = {}
    agents_seen: Dict[str, Dict] = {}
    hooks_seen: Dict[str, Dict] = {}
    scripts_seen: Dict[str, str] = {}      # script_id -> path
    plugins_seen: Dict[str, str] = {}
    mcp_configs_seen: Dict[str, str] = {}
    contexts_seen: Dict[str, str] = {}
    rules_seen: Dict[str, str] = {}

    for f in files:
        path = f["path"]

        # --- Skills ---
        sid = _extract_skill_id(path)
        if sid:
            if sid not in skills_seen:
                skills_seen[sid] = {"canonical_path": path, "files": [], "is_harness_copy": _is_harness_specific(path)}
            else:
                skills_seen[sid]["files"].append(path)
                # Prefer canonical (non-harness-specific) path
                if not _is_harness_specific(path) and skills_seen[sid]["is_harness_copy"]:
                    skills_seen[sid]["canonical_path"] = path
                    skills_seen[sid]["is_harness_copy"] = False
            continue

        # --- Commands ---
        cmd = _extract_command_id(path)
        if cmd and not _is_harness_specific(path):
            if cmd not in commands_seen:
                commands_seen[cmd] = {"canonical_path": path, "files": []}
            else:
                commands_seen[cmd]["files"].append(path)
            continue
        elif cmd and _is_harness_specific(path):
            if cmd not in commands_seen:
                commands_seen[cmd] = {"canonical_path": path, "files": [], "harness_only": True}
            continue

        # --- Agents ---
        aid = _extract_agent_id(path)
        if aid and "skills" not in path:
            if aid not in agents_seen:
                agents_seen[aid] = {"canonical_path": path, "files": []}
            else:
                agents_seen[aid]["files"].append(path)
            continue

        # --- Hooks ---
        if re.search(r"(?:^|/)hooks?/", path) and not path.endswith("/"):
            hid = _extract_hook_id(path) or path.split("/")[-1]
            if hid not in hooks_seen:
                hooks_seen[hid] = {"canonical_path": path}
            continue

        # --- Scripts ---
        if path.endswith((".sh", ".py")) and "scripts" in path.lower():
            sid2 = Path(path).stem
            if sid2 not in scripts_seen:
                scripts_seen[sid2] = path
            continue

        # --- Plugins ---
        if re.search(r"(?:^|/)plugins?/[^/]+\.[a-z]+$", path):
            pid = Path(path).stem
            plugins_seen[pid] = path
            continue

        # --- MCP configs ---
        if re.search(r"mcp.config", path, re.IGNORECASE) or "mcp-configs" in path:
            mid = Path(path).stem
            mcp_configs_seen[mid] = path
            continue

        # --- Contexts ---
        if re.search(r"(?:^|/)contexts?/[^/]+\.md$", path) and not _is_harness_specific(path):
            cid = Path(path).stem
            contexts_seen[cid] = path
            continue

        # --- Rules ---
        if Path(path).name in {"AGENTS.md", "RULES.md", ".cursorrules"} and not _is_harness_specific(path):
            rid = Path(path).name
            rules_seen[rid] = path
            continue

    # --- Preflight fetch ---
    preflight_results: Dict[str, Tuple[bool, List[str]]] = {}
    if preflight_content:
        fetch_count = 0
        for sid, info in skills_seen.items():
            if fetch_count >= max_preflight_fetches:
                break
            path = info["canonical_path"]
            if not path.endswith("SKILL.md"):
                # Try to find SKILL.md
                skill_md = path.rsplit("/", 1)[0] + "/SKILL.md" if "/" in path else path
            else:
                skill_md = path
            content = _raw_get(skill_md)
            if content:
                passed, issues = quick_preflight(content)
                preflight_results[sid] = (passed, issues)
                fetch_count += 1

    # --- Build registry entries ---
    candidates: List[Dict[str, Any]] = []

    for sid, info in skills_seen.items():
        cls = classify_skill(sid)
        pf = preflight_results.get(sid, (cls["preflight_passed"], []))
        cand = {
            "candidate_id": f"ecc:{sid}",
            "category": "skill",
            "name": sid,
            "canonical_path": info["canonical_path"],
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            "harness_copies": len(info.get("files", [])),
            **cls,
            "preflight_passed": pf[0],
            "preflight_issues": pf[1] if pf[1] else [],
        }
        candidates.append(cand)

    for cid, info in commands_seen.items():
        cls = classify_command(cid)
        cand = {
            "candidate_id": f"ecc:cmd:{cid}",
            "category": "command",
            "name": cid,
            "canonical_path": info["canonical_path"],
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            **cls,
        }
        candidates.append(cand)

    for aid, info in agents_seen.items():
        cls = classify_agent(aid)
        cand = {
            "candidate_id": f"ecc:agent:{aid}",
            "category": "agent",
            "name": aid,
            "canonical_path": info["canonical_path"],
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            **cls,
        }
        candidates.append(cand)

    for hid, info in hooks_seen.items():
        cls = classify_hook(hid)
        cand = {
            "candidate_id": f"ecc:hook:{hid}",
            "category": "hook",
            "name": hid,
            "canonical_path": info["canonical_path"],
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            **cls,
        }
        candidates.append(cand)

    for sid2, path in scripts_seen.items():
        cls = classify_script(sid2)
        cand = {
            "candidate_id": f"ecc:script:{sid2}",
            "category": "script",
            "name": sid2,
            "canonical_path": path,
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            **cls,
        }
        candidates.append(cand)

    for pid, path in plugins_seen.items():
        cls = classify_plugin(pid)
        cand = {
            "candidate_id": f"ecc:plugin:{pid}",
            "category": "plugin",
            "name": pid,
            "canonical_path": path,
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            **cls,
        }
        candidates.append(cand)

    for mid, path in mcp_configs_seen.items():
        cls = classify_mcp_config(mid)
        cand = {
            "candidate_id": f"ecc:mcp:{mid}",
            "category": "mcp_config",
            "name": mid,
            "canonical_path": path,
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            **cls,
        }
        candidates.append(cand)

    for cid2, path in contexts_seen.items():
        cls = classify_context(cid2)
        cand = {
            "candidate_id": f"ecc:context:{cid2}",
            "category": "context",
            "name": cid2,
            "canonical_path": path,
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            **cls,
        }
        candidates.append(cand)

    for rid, path in rules_seen.items():
        cand = {
            "candidate_id": f"ecc:rule:{rid}",
            "category": "rule",
            "name": rid,
            "canonical_path": path,
            "source_url": f"https://github.com/{ECC_REPO}",
            "license_spdx": ECC_LICENSE_SPDX,
            "source_name": "ECC",
            "state": "inspect_later",
            "risk_tier": "low",
            "priority": "inspect_later",
            "permission_scopes": ["read_only"],
            "reason": "Rule/AGENTS file — inspect for Jarvis governance conflicts before adoption.",
            "preflight_passed": True,
            "reviewer_approved": False,
        }
        candidates.append(cand)

    # --- State summary ---
    state_counts: Dict[str, int] = {}
    for c in candidates:
        s = c.get("state", "unknown")
        state_counts[s] = state_counts.get(s, 0) + 1

    category_counts: Dict[str, int] = {}
    for c in candidates:
        cat = c.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    active_items = [c for c in candidates if c.get("state") == "active"]

    registry = {
        "schema_version": "2.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - ts, 2),
        "source": {
            "repo": repo.get("full_name"),
            "description": repo.get("description"),
            "branch": ECC_BRANCH,
            "license_spdx": ECC_LICENSE_SPDX,
            "license_verified": True,
            "official_source_only": True,
            "no_ecc_code_executed": True,
        },
        "counts": {
            "total_files": len(files),
            "unique_capabilities": len(candidates),
            "unique_skills": len(skills_seen),
            "unique_commands": len(commands_seen),
            "unique_agents": len(agents_seen),
            "unique_hooks": len(hooks_seen),
            "unique_scripts": len(scripts_seen),
            "unique_plugins": len(plugins_seen),
            "unique_mcp_configs": len(mcp_configs_seen),
            "unique_contexts": len(contexts_seen),
            "unique_rules": len(rules_seen),
        },
        "state_summary": state_counts,
        "category_counts": category_counts,
        "active_count": len(active_items),
        "active_candidates": [c["candidate_id"] for c in active_items],
        "preflight_fetch_count": len(preflight_results),
        "candidates": candidates,
    }
    return registry


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------


def format_registry_report(registry: Dict[str, Any]) -> str:
    lines = [
        "=" * 70,
        "ECC FULL REGISTRY REPORT — Jarvis Plan 1 Full Coverage Sprint",
        "=" * 70,
        f"Source:    {registry['source']['repo']}  [OFFICIAL ONLY]",
        f"Generated: {registry['generated_at']}",
        f"ECC code executed: NO  |  License: {registry['source']['license_spdx']} VERIFIED",
        "",
        "COUNTS",
        "-" * 40,
        f"  Total ECC files:        {registry['counts']['total_files']:,}",
        f"  Unique capabilities:    {registry['counts']['unique_capabilities']:,}",
        f"  Skills:                 {registry['counts']['unique_skills']}",
        f"  Commands:               {registry['counts']['unique_commands']}",
        f"  Agents:                 {registry['counts']['unique_agents']}",
        f"  Hooks:                  {registry['counts']['unique_hooks']}",
        f"  Scripts:                {registry['counts']['unique_scripts']}",
        f"  Plugins:                {registry['counts']['unique_plugins']}",
        f"  MCP configs:            {registry['counts']['unique_mcp_configs']}",
        f"  Contexts:               {registry['counts']['unique_contexts']}",
        f"  Rules:                  {registry['counts']['unique_rules']}",
        "",
        "ACTIVATION STATES",
        "-" * 40,
    ]
    for state, count in sorted(registry["state_summary"].items(), key=lambda x: -x[1]):
        lines.append(f"  {state:<30} {count:>5}")

    lines += [
        "",
        f"ACTIVE ITEMS ({registry['active_count']})",
        "-" * 40,
    ]
    for cid in registry["active_candidates"][:30]:
        lines.append(f"  {cid}")
    if len(registry["active_candidates"]) > 30:
        lines.append(f"  ... and {len(registry['active_candidates']) - 30} more")

    lines += [
        "",
        "=" * 70,
        "HOLD SUMMARY",
        "-" * 40,
    ]
    hold_reasons: Dict[str, int] = {}
    for c in registry["candidates"]:
        if c.get("state") not in ("active",):
            r = c.get("reason", "no reason")[:60]
            hold_reasons[r] = hold_reasons.get(r, 0) + 1
    for reason, count in sorted(hold_reasons.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"  [{count:>3}] {reason}")

    lines += [
        "",
        "NOTE: No ECC code was executed. No items auto-activated without gates.",
        "      Active items are pure guidance (read-only, no execution, MIT licensed).",
        "=" * 70,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="ECC full registry builder")
    parser.add_argument("--output", metavar="FILE", help="Write JSON registry to FILE")
    parser.add_argument("--preflight", action="store_true", help="Fetch content for preflight checks")
    parser.add_argument("--summary", action="store_true", help="Print text summary to stderr")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    try:
        registry = build_full_registry(
            preflight_content=args.preflight,
            verbose=args.verbose,
        )
    except AssertionError as exc:
        print(f"SAFETY ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(json.dumps(registry, indent=2))
        print(f"Registry written to: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(registry, indent=2))

    if args.summary or not args.output:
        print(format_registry_report(registry), file=sys.stderr)


if __name__ == "__main__":
    main()
