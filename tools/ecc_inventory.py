#!/usr/bin/env python3
"""ECC inventory harness — Python/local-first mechanical inventory of ECC repo.

Fetches ECC from the OFFICIAL GitHub source only:
  https://github.com/affaan-m/ECC

Performs a read-only, mechanical inventory without:
  - Executing any ECC scripts or hooks
  - Running any ECC install procedures
  - Activating any MCP configs
  - Installing any dependencies

Outputs a structured JSON inventory + text summary to stdout and optionally
to files.

Usage:
    python tools/ecc_inventory.py [--output-json FILE] [--output-text FILE]
    python tools/ecc_inventory.py --output-json ecc_inventory.json
    python tools/ecc_inventory.py --summary-only

Requires: Python stdlib only (urllib, json, re, argparse). No pip packages.
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
from typing import Any, Dict, List, Optional

# macOS ships without default cert bundle accessible to Python's urllib.
# Use system certs or certifi if available.
def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # Try system certs (macOS)
    for cert_path in ("/etc/ssl/cert.pem", "/usr/local/etc/openssl/cert.pem"):
        if Path(cert_path).exists():
            ctx.load_verify_locations(cert_path)
            return ctx
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx

_SSL_CTX = _make_ssl_context()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ECC_REPO = "affaan-m/ECC"
ECC_BRANCH = "main"
ECC_API_BASE = "https://api.github.com"
ECC_RAW_BASE = "https://raw.githubusercontent.com"
ECC_LICENSE_SPDX = "MIT"   # confirmed from GitHub API

# Category classifiers: (path_pattern → category)
_CATEGORY_RULES: List[tuple[str, str]] = [
    (r"\.agents/skills/",      "skill"),
    (r"agents/",               "agent"),
    (r"commands/",             "command"),
    (r"hooks/",                "hook"),
    (r"RULES\.md|AGENTS\.md|\.cursorrules", "rule"),
    (r"mcp-configs?/",         "mcp_config"),
    (r"manifests/",            "schema"),
    (r"plugins/",              "plugin"),
    (r"contexts/",             "context"),
    (r"research/|docs/",       "guide_pattern"),
    (r"\.sh$|scripts/.*\.py$", "script"),
]

# Priority heuristics
_LIKELY_ADOPT_PATTERNS = [
    "eval-harness", "contexts/", "checkpoint", "code-reviewer",
    "security-reviewer", "benchmark", "documentation-lookup",
]
_ADAPT_NEEDED_PATTERNS = [
    "hooks/", "mcp-configs/", "plugins/", "manifests/",
    "tdd-guide", "e2e-testing",
]
_UNSAFE_INDICATORS = [
    r"rm\s+-rf\b", r"os\.system\(", r"subprocess\.",
    r"exec\(", r"eval\(", r"socket\.", r"requests\.",
    r"API_KEY", r"PASSWORD", r"SECRET",
]
_IRRELEVANT_PATTERNS = [
    r"docs/es/", r"docs/ja-JP/", r"\.kiro/", r"\.codebuddy/",
    r"\.qwen/", r"\.zed/", r"\.gemini/", r"\.trae/",
]


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def _api_get(path: str, timeout: int = 30) -> Any:
    """Fetch from GitHub REST API. Returns parsed JSON or raises."""
    url = f"{ECC_API_BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-ecc-inventory/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        return json.loads(resp.read())


def _raw_get(path: str, timeout: int = 20) -> str:
    """Fetch raw file content from GitHub. Returns text or empty string."""
    url = f"{ECC_RAW_BASE}/{ECC_REPO}/{ECC_BRANCH}/{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jarvis-ecc-inventory/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def fetch_repo_tree() -> List[Dict[str, Any]]:
    """Fetch full recursive file tree from ECC repo."""
    data = _api_get(f"/repos/{ECC_REPO}/git/trees/{ECC_BRANCH}?recursive=1")
    return data.get("tree", [])


def fetch_repo_info() -> Dict[str, Any]:
    """Fetch basic repo metadata for verification."""
    return _api_get(f"/repos/{ECC_REPO}")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_category(path: str) -> str:
    for pattern, cat in _CATEGORY_RULES:
        if re.search(pattern, path, re.IGNORECASE):
            return cat
    return "other"


def classify_priority(path: str, content_snippet: str = "") -> str:
    combined = (path + " " + content_snippet).lower()

    # Check irrelevant first
    for pat in _IRRELEVANT_PATTERNS:
        if re.search(pat, path, re.IGNORECASE):
            return "irrelevant"

    # Check unsafe
    for pat in _UNSAFE_INDICATORS:
        if re.search(pat, combined):
            return "unsafe"

    # Check adapt_needed (hooks, MCP, plugins — need Jarvis wiring)
    for pat in _ADAPT_NEEDED_PATTERNS:
        if pat in path.lower():
            return "adapt_needed"

    # Check likely_adopt
    for pat in _LIKELY_ADOPT_PATTERNS:
        if pat in path.lower():
            return "likely_adopt"

    return "inspect_later"


def check_safety(content: str) -> List[str]:
    """Return list of safety concerns found in content (text/regex only)."""
    concerns = []
    for pat in _UNSAFE_INDICATORS:
        matches = re.findall(pat, content, re.IGNORECASE)
        if matches:
            concerns.append(f"{pat}: found {matches[:2]}")
    return concerns


# ---------------------------------------------------------------------------
# Inventory core
# ---------------------------------------------------------------------------


def extract_skill_name(path: str) -> Optional[str]:
    """Extract the skill name from a path like .agents/skills/eval-harness/SKILL.md."""
    m = re.search(r"skills?/([^/]+)/", path)
    if m:
        return m.group(1)
    return None


def inventory_item(item: Dict[str, Any], fetch_content: bool = False) -> Dict[str, Any]:
    """Inventory a single tree item, optionally fetching its content for analysis."""
    path = item["path"]
    size = item.get("size", 0)
    category = classify_category(path)

    content_snippet = ""
    safety_concerns: List[str] = []

    if fetch_content and size < 50_000:  # skip large files
        raw = _raw_get(path)
        content_snippet = raw[:500]
        safety_concerns = check_safety(raw)

    priority = classify_priority(path, content_snippet)

    entry = {
        "path": path,
        "category": category,
        "priority": priority,
        "size_bytes": size,
        "skill_name": extract_skill_name(path),
        "safety_concerns": safety_concerns,
        "source": f"https://github.com/{ECC_REPO}/blob/{ECC_BRANCH}/{path}",
    }

    # For skills with SKILL.md, extract description
    if path.endswith("SKILL.md") and fetch_content:
        raw = _raw_get(path) if not content_snippet else (content_snippet + "...")
        desc_m = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
        if desc_m:
            entry["description"] = desc_m.group(1).strip()

    return entry


def run_inventory(
    fetch_content: bool = False,
    max_content_fetches: int = 20,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run full ECC inventory. Returns structured dict."""
    ts_start = time.time()

    if verbose:
        print("Fetching ECC repo info...", file=sys.stderr)

    repo_info = fetch_repo_info()
    assert repo_info.get("full_name") == ECC_REPO, (
        f"Unexpected repo: {repo_info.get('full_name')}. "
        f"Expected: {ECC_REPO}. Aborting to avoid unofficial mirror."
    )

    if verbose:
        print("Fetching repo tree...", file=sys.stderr)

    tree = fetch_repo_tree()
    files = [item for item in tree if item.get("type") == "blob"]

    if verbose:
        print(f"Processing {len(files)} files...", file=sys.stderr)

    # Decide which files to fetch content for
    content_fetch_paths = set()
    if fetch_content:
        # Fetch SKILL.md files + a sample of commands/contexts
        for item in files:
            if len(content_fetch_paths) >= max_content_fetches:
                break
            path = item["path"]
            if (path.endswith("SKILL.md") or
                    path.startswith("contexts/") or
                    "AGENTS.md" == path.split("/")[-1] or
                    "RULES.md" == path.split("/")[-1]):
                content_fetch_paths.add(path)

    items: List[Dict[str, Any]] = []
    for file_item in files:
        do_fetch = file_item["path"] in content_fetch_paths
        entry = inventory_item(file_item, fetch_content=do_fetch)
        items.append(entry)

    # Aggregate counts
    by_category: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    skills_seen: set = set()

    for entry in items:
        cat = entry["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

        pri = entry["priority"]
        by_priority[pri] = by_priority.get(pri, 0) + 1

        if entry.get("skill_name"):
            skills_seen.add(entry["skill_name"])

    # Unique skills
    unique_skills = sorted(skills_seen)

    # License verification
    license_info = {
        "spdx": ECC_LICENSE_SPDX,
        "source": f"https://github.com/{ECC_REPO}",
        "verified": repo_info.get("license", {}).get("spdx_id") == ECC_LICENSE_SPDX,
    }

    # Safety summary
    all_concerns = [entry for entry in items if entry.get("safety_concerns")]

    elapsed = time.time() - ts_start

    return {
        "meta": {
            "source": f"https://github.com/{ECC_REPO}",
            "branch": ECC_BRANCH,
            "official_only": True,
            "no_ecc_code_executed": True,
            "inventory_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_seconds": round(elapsed, 2),
            "python_local_first": True,
        },
        "repo": {
            "full_name": repo_info.get("full_name"),
            "description": repo_info.get("description"),
            "stars": repo_info.get("stargazers_count"),
            "license_spdx": ECC_LICENSE_SPDX,
            "size_kb": repo_info.get("size"),
            "default_branch": repo_info.get("default_branch"),
        },
        "license": license_info,
        "counts": {
            "total_files": len(files),
            "unique_skills": len(unique_skills),
            "by_category": by_category,
            "by_priority": by_priority,
        },
        "unique_skills": unique_skills,
        "safety_flags": len(all_concerns),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Text report formatter
# ---------------------------------------------------------------------------


def format_text_report(inventory: Dict[str, Any]) -> str:
    lines = [
        "=" * 70,
        "ECC INVENTORY REPORT — Jarvis Plan 1 / External Skill Intake",
        "=" * 70,
        f"Source:    {inventory['meta']['source']}  [OFFICIAL ONLY]",
        f"Timestamp: {inventory['meta']['inventory_timestamp']}",
        f"ECC code executed: NO",
        f"Python/local-first: YES",
        "",
        "REPOSITORY",
        "-" * 40,
        f"  Name:        {inventory['repo']['full_name']}",
        f"  Description: {inventory['repo']['description']}",
        f"  Stars:       {inventory['repo']['stars']:,}",
        f"  License:     {inventory['repo']['license_spdx']} "
        f"({'VERIFIED' if inventory['license']['verified'] else 'UNVERIFIED'})",
        f"  Size:        {inventory['repo']['size_kb']} KB",
        "",
        "COUNTS",
        "-" * 40,
        f"  Total files:    {inventory['counts']['total_files']:,}",
        f"  Unique skills:  {inventory['counts']['unique_skills']}",
        "",
        "  By category:",
    ]
    for cat, count in sorted(inventory["counts"]["by_category"].items(), key=lambda x: -x[1]):
        lines.append(f"    {cat:<30} {count:>5}")

    lines += ["", "  By priority:"]
    for pri, count in sorted(inventory["counts"]["by_priority"].items(), key=lambda x: -x[1]):
        lines.append(f"    {pri:<30} {count:>5}")

    lines += [
        "",
        f"  Safety flags: {inventory['safety_flags']}",
        "",
        "UNIQUE SKILLS",
        "-" * 40,
    ]
    for s in inventory["unique_skills"]:
        lines.append(f"  - {s}")

    lines += [
        "",
        "PRIORITY CANDIDATES (likely_adopt)",
        "-" * 40,
    ]
    for item in inventory["items"]:
        if item["priority"] == "likely_adopt":
            lines.append(
                f"  [{item['category']:<15}] {item['path']}"
            )

    lines += [
        "",
        "=" * 70,
        "NOTE: No ECC items are activated or installed by this report.",
        "      All candidates require Jarvis intake review before use.",
        "=" * 70,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ECC inventory harness — read-only mechanical inventory"
    )
    parser.add_argument(
        "--output-json", metavar="FILE",
        help="Write JSON inventory to FILE (default: stdout)"
    )
    parser.add_argument(
        "--output-text", metavar="FILE",
        help="Write text report to FILE (default: stderr)"
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Print only the text summary, no full JSON"
    )
    parser.add_argument(
        "--fetch-content", action="store_true",
        help="Fetch content of key files for deeper analysis (slower)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print progress to stderr"
    )
    args = parser.parse_args()

    try:
        inventory = run_inventory(
            fetch_content=args.fetch_content,
            verbose=args.verbose,
        )
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR fetching ECC inventory: {exc}", file=sys.stderr)
        sys.exit(1)

    text_report = format_text_report(inventory)

    # Write JSON
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(inventory, indent=2))
        print(f"JSON inventory written to: {args.output_json}", file=sys.stderr)
    elif not args.summary_only:
        print(json.dumps(inventory, indent=2))

    # Write text
    if args.output_text:
        Path(args.output_text).write_text(text_report)
        print(f"Text report written to: {args.output_text}", file=sys.stderr)
    else:
        print(text_report, file=sys.stderr)


if __name__ == "__main__":
    main()
