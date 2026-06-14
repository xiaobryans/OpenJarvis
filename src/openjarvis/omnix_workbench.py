#!/usr/bin/env python3
"""
Jarvis OMNIX Workbench v1 — All-in-one local front door for OMNIX upgrade work.

This workbench provides Jarvis-led coordination for OMNIX upgrade planning,
coding prompts, review, QA, and release gates.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Add OpenJarvis source directory to Python path
_script_dir = Path(__file__).parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))


# Expected schema
_EXPECTED_SCHEMA = "omnix.jarvis.status_bundle.v1"

# Default dashboard URL
_DEFAULT_URL = "http://127.0.0.1:3091/api/jarvis/status-bundle"

# Allowed hosts
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def validate_url(url: str) -> str:
    """Validate URL is localhost only."""
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("Invalid URL: no hostname")

    if hostname not in _ALLOWED_HOSTS:
        raise ValueError(f"URL must use localhost only. Got: {hostname}")

    if parsed.scheme != "http":
        raise ValueError("Only http scheme is supported for localhost")

    return url


def fetch_status_bundle(url: str, timeout: int = 10) -> dict[str, Any]:
    """Fetch the status bundle from localhost."""
    try:
        request = urllib.request.Request(url)
        request.add_header("User-Agent", "OMNIX-Workbench/1.0")
        
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            raise RuntimeError(f"Request timed out after {timeout}s")
        raise RuntimeError(f"Request error: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {e}")


def validate_schema(bundle: dict[str, Any]) -> None:
    """Validate the status bundle schema."""
    schema = bundle.get("schema")
    if schema != _EXPECTED_SCHEMA:
        raise ValueError(
            f"Unexpected schema: {schema}. Expected: {_EXPECTED_SCHEMA}"
        )


def call_jarvis_agent(agent: str, prompt: str) -> tuple[str, bool]:
    """Call Jarvis agent with compact prompt."""
    import subprocess

    try:
        # Use jarvis ask with --agent flag for agent routing
        result = subprocess.run(
            ["jarvis", "ask", "--no-stream", "--agent", agent, prompt],
            capture_output=True,
            text=True,
            timeout=180,
        )
        
        if result.returncode == 0:
            # Extract actual response from jarvis ask output
            lines = result.stdout.strip().split('\n')
            response_lines = []
            in_response = False
            for line in lines:
                if in_response or (line and not line.startswith(' ') and not line.startswith('_') and not line.startswith('J') and not line.startswith('P')):
                    in_response = True
                    if line.strip():
                        response_lines.append(line)
            
            if response_lines:
                return '\n'.join(response_lines), True
            return result.stdout.strip(), True
        else:
            return f"jarvis ask failed: {result.stderr}", False
            
    except subprocess.TimeoutExpired:
        return "jarvis ask timed out after 180 seconds", False
    except (FileNotFoundError, Exception) as e:
        return f"jarvis ask exception: {e}", False


def mode_status(url: str) -> str:
    """Status mode: fetch and summarize status bundle."""
    try:
        validate_url(url)
        bundle = fetch_status_bundle(url)
        validate_schema(bundle)
        
        runtime = bundle.get("runtime", {})
        slack = bundle.get("slack", {})
        health = bundle.get("health", {})
        safety = bundle.get("safety", {})
        
        summary = f"""OMNIX Status Summary
==================
Schema: {bundle.get('schema')}
Safety: readOnly={safety.get('readOnly')}, noWrites={safety.get('noWrites')}, noSecrets={safety.get('noSecrets')}
Runtime: {len(runtime.get('missions', []))} missions, {runtime.get('health', {}).get('missions', 0)} active
Pending: {len(runtime.get('pendingApprovals', []))} approvals
Slack: installed={slack.get('installed')}, configured={slack.get('configured')}, running={slack.get('continuousOpsRunning')}
Health: dashboard={health.get('commandCenter', {}).get('ok')}, gateway={health.get('localGateway', {}).get('ok')}
"""
        return summary
    except Exception as e:
        return f"Status error: {e}"


def mode_plan(url: str, objective: str) -> str:
    """Plan mode: produce Jarvis-led OMNIX upgrade plan."""
    try:
        validate_url(url)
        bundle = fetch_status_bundle(url)
        validate_schema(bundle)
        
        # Extract ultra-compact context
        runtime = bundle.get("runtime", {})
        slack = bundle.get("slack", {})
        pending_count = len(runtime.get("pendingApprovals", []))
        mission_count = len(runtime.get("missions", []))
        schema_ok = bundle.get("schema") == _EXPECTED_SCHEMA
        slack_configured = slack.get("configured", False)
        slack_running = slack.get("continuousOpsRunning", False)
        
        # Ultra-compact prompt with exact required fields
        prompt = f"""Plan: {objective}
Schema: {schema_ok}
Runtime: {mission_count} missions
Pending: {pending_count} approvals
Slack: configured={slack_configured}, running={slack_running} (risk only)
Output: JARVIS OMNIX PLAN ACCEPT or HOLD + 3-5 step plan"""
        
        response, success = call_jarvis_agent("simple", prompt)
        source = "[JARVIS LLM]" if success else "[FALLBACK - LLM unavailable]"
        return f"{source}\n{response}"
    except Exception as e:
        return f"Plan error: {e}"


def mode_prompt(url: str, objective: str) -> str:
    """Prompt mode: generate branch-only coding-agent prompt."""
    try:
        validate_url(url)
        bundle = fetch_status_bundle(url)
        validate_schema(bundle)
        
        # Ultra-compact prompt with required fields
        prompt = f"""Coding prompt: {objective}
Branch-only: yes
Repo sync gate: required
Scope: local changes only
Safety: no production, no secrets, no writes
Validation: local tests pass
Output: JARVIS OMNIX CODING PROMPT ACCEPT or HOLD + branch-only coding prompt"""
        
        response, success = call_jarvis_agent("simple", prompt)
        source = "[JARVIS LLM]" if success else "[FALLBACK - LLM unavailable]"
        return f"{source}\n{response}"
    except Exception as e:
        return f"Prompt error: {e}"


def mode_review(content: str) -> str:
    """Review mode: review coding-agent report and return ACCEPT/HOLD."""
    prompt = f"""Review this report for ACCEPT/HOLD.

Report: {content[:1000]}

Criteria: correctness, completeness, safety, test coverage.
Output: ACCEPT or HOLD with specific reasoning."""
    
    response, success = call_jarvis_agent("simple", prompt)
    source = "[JARVIS LLM]" if success else "[FALLBACK]"
    return f"{source}\n{response}"


def mode_qa(content: str) -> str:
    """QA mode: list necessary validation gaps."""
    prompt = f"""List validation gaps from this evidence.

Evidence: {content[:1000]}

Focus: Missing tests, edge cases, integration points.
Output: Bullet list of necessary validation steps only."""
    
    response, success = call_jarvis_agent("simple", prompt)
    source = "[JARVIS LLM]" if success else "[FALLBACK]"
    return f"{source}\n{response}"


def mode_gate(content: str) -> str:
    """Gate mode: release-gatekeeper ACCEPT/HOLD decision."""
    prompt = f"""Release gate decision for this report.

Report: {content[:1000]}

Criteria: All tests pass, no blockers, documentation complete.
Output: ACCEPT or HOLD with gate-specific reasoning.
Note: Do not mark production-ready unless explicitly stated."""
    
    response, success = call_jarvis_agent("simple", prompt)
    source = "[JARVIS LLM]" if success else "[FALLBACK]"
    return f"{source}\n{response}"


def mode_memory(query: str) -> str:
    """Memory mode: placeholder for future memory/continuity features."""
    return """[PLACEHOLDER - NOT IMPLEMENTED] Memory Mode

This mode is a placeholder for future memory/continuity features.
Not yet implemented: no persistence, no knowledge graph, no search.
Current status: Placeholder only - no functionality."""


def mode_artifact(context: str) -> str:
    """Artifact mode: placeholder for future document/artifact context features."""
    return f"""[PLACEHOLDER - NOT IMPLEMENTED] Artifact Mode

This mode is a placeholder for future document/artifact context features.
Not yet implemented: no indexing, no retrieval, no relationship tracking.
Current status: Placeholder only - no functionality."""


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Jarvis OMNIX Workbench v1 — All-in-one OMNIX upgrade coordination"
    )
    parser.add_argument(
        "--url",
        default=_DEFAULT_URL,
        help=f"Status bundle URL (default: {_DEFAULT_URL})",
    )
    
    subparsers = parser.add_subparsers(dest="mode", help="Workbench mode")
    
    # Status mode
    subparsers.add_parser("status", help="Fetch and summarize status bundle")
    
    # Plan mode
    plan_parser = subparsers.add_parser("plan", help="Produce OMNIX upgrade plan")
    plan_parser.add_argument("objective", help="Upgrade objective")
    
    # Prompt mode
    prompt_parser = subparsers.add_parser("prompt", help="Generate coding-agent prompt")
    prompt_parser.add_argument("objective", help="Coding objective")
    
    # Review mode
    review_parser = subparsers.add_parser("review", help="Review coding-agent report")
    review_parser.add_argument("content", help="Report content to review")
    
    # QA mode
    qa_parser = subparsers.add_parser("qa", help="List validation gaps")
    qa_parser.add_argument("content", help="Validation evidence")
    
    # Gate mode
    gate_parser = subparsers.add_parser("gate", help="Release gatekeeper decision")
    gate_parser.add_argument("content", help="Report for gate review")
    
    # Memory mode
    memory_parser = subparsers.add_parser("memory", help="Memory/continuity placeholder")
    memory_parser.add_argument("query", nargs="?", default="", help="Memory query")
    
    # Artifact mode
    artifact_parser = subparsers.add_parser("artifact", help="Artifact/document context placeholder")
    artifact_parser.add_argument("context", nargs="?", default="", help="Document context")
    
    args = parser.parse_args()
    
    if not args.mode:
        parser.print_help()
        return 1
    
    try:
        if args.mode == "status":
            result = mode_status(args.url)
        elif args.mode == "plan":
            result = mode_plan(args.url, args.objective)
        elif args.mode == "prompt":
            result = mode_prompt(args.url, args.objective)
        elif args.mode == "review":
            result = mode_review(args.content)
        elif args.mode == "qa":
            result = mode_qa(args.content)
        elif args.mode == "gate":
            result = mode_gate(args.content)
        elif args.mode == "memory":
            result = mode_memory(args.query)
        elif args.mode == "artifact":
            result = mode_artifact(args.context)
        else:
            parser.print_help()
            return 1
        
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
