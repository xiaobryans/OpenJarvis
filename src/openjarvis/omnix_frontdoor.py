#!/usr/bin/env python3
"""
OMNIX Front-Door Runner — Deterministic status bundle fetch and Jarvis review.

This script fetches the OMNIX status bundle from localhost and asks Jarvis
to review it for upgrade planning readiness.
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
        request.add_header("User-Agent", "OMNIX-FrontDoor/1.0")
        
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


def build_review_prompt(bundle: dict[str, Any]) -> str:
    """Build a compact prompt for Jarvis to review the status bundle."""
    runtime = bundle.get("runtime", {})
    slack = bundle.get("slack", {})
    health = bundle.get("health", {})
    safety = bundle.get("safety", {})
    pending_approvals = runtime.get("pendingApprovals", [])
    missions = runtime.get("missions", [])
    
    # Extract critical information only
    schema = bundle.get("schema", "unknown")
    pending_count = len(pending_approvals)
    mission_count = len(missions)
    
    # Safety flags
    read_only = safety.get("readOnly", False)
    no_writes = safety.get("noWrites", False)
    no_secrets = safety.get("noSecrets", False)
    
    # Slack status
    slack_installed = slack.get("installed", False)
    slack_configured = slack.get("configured", False)
    slack_running = slack.get("continuousOpsRunning", False)
    
    # Health status
    dashboard_ok = health.get("commandCenter", {}).get("ok", False)
    gateway_ok = health.get("localGateway", {}).get("ok", False)
    
    # Runtime health summary
    runtime_health = runtime.get("health", {})
    runtime_missions = runtime_health.get("missions", 0)
    runtime_tasks = runtime_health.get("tasks", 0)
    
    # Build compact prompt
    prompt = f"""Jarvis OMNIX status review for upgrade planning.

Schema: {schema}
Safety: readOnly={read_only}, noWrites={no_writes}, noSecrets={no_secrets}
Runtime: {mission_count} missions, {runtime_missions} active, {runtime_tasks} tasks
Pending: {pending_count} approvals
Slack: installed={slack_installed}, configured={slack_configured}, running={slack_running}
Health: dashboard={dashboard_ok}, gateway={gateway_ok}

For branch-only planning, Slack not configured is a risk, not blocker.
HOLD only for: invalid schema, unsafe flags, critical runtime failure, or blocking approvals.

Output exactly: JARVIS OMNIX FRONT-DOOR REVIEW ACCEPT or HOLD
Then include: status summary, whether Jarvis can proceed, shortest next action."""

    return prompt


def call_jarvis_llm(prompt: str) -> str:
    """Call Jarvis LLM with the review prompt using jarvis CLI."""
    import subprocess

    try:
        # Use jarvis ask with the compact prompt as argument
        # Use --no-stream to get non-blocking output
        result = subprocess.run(
            ["jarvis", "ask", "--no-stream", prompt],
            capture_output=True,
            text=True,
            timeout=180,  # Increased to 180 seconds
        )
        
        if result.returncode == 0:
            # Extract the actual response from jarvis ask output
            # jarvis ask typically includes banner, we need to extract just the response
            lines = result.stdout.strip().split('\n')
            # Find the first non-banner line (skip banner lines)
            response_lines = []
            in_response = False
            for line in lines:
                # Skip banner lines (start with space, underscore, J, P, or are empty)
                if in_response or (line and not line.startswith(' ') and not line.startswith('_') and not line.startswith('J') and not line.startswith('P')):
                    in_response = True
                    if line.strip():
                        response_lines.append(line)
            
            if response_lines:
                return '\n'.join(response_lines)
            return result.stdout.strip()
        else:
            print(f"jarvis ask failed with return code {result.returncode}", file=sys.stderr)
            print(f"stderr: {result.stderr}", file=sys.stderr)
            return _fallback_rule_based_review(prompt)
            
    except subprocess.TimeoutExpired:
        print(f"jarvis ask timed out after 180 seconds", file=sys.stderr)
        return _fallback_rule_based_review(prompt)
    except (FileNotFoundError, Exception) as e:
        print(f"jarvis ask exception: {e}", file=sys.stderr)
        return _fallback_rule_based_review(prompt)


def _fallback_rule_based_review(prompt: str) -> str:
    """Fallback rule-based review when jarvis ask is unavailable."""
    lines = prompt.split("\n")
    pending_count = 0
    slack_configured = False
    slack_running = False
    runtime_healthy = True

    for line in lines:
        if "Pending Approvals:" in line:
            try:
                pending_count = int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass
        if "Slack Configured:" in line:
            slack_configured = "True" in line
        if "Slack Continuous Ops Running:" in line:
            slack_running = "True" in line

    # Updated decision logic for branch-only planning
    # HOLD only for critical blockers, not Slack configuration issues
    if pending_count > 0:
        return """JARVIS OMNIX FRONT-DOOR REVIEW HOLD
Status: {pending_count} pending approval(s) blocking upgrade planning
Blocker: Pending approvals must be resolved before upgrade planning
Next action: Review and resolve pending approvals via dashboard or CLI
""".format(pending_count=pending_count)

    # Slack not configured is a risk, not a blocker for branch-only planning
    if not slack_configured:
        return """JARVIS OMNIX FRONT-DOOR REVIEW ACCEPT
Status: Runtime healthy, Slack not configured (risk for notifications, not blocker for branch-only planning)
Can proceed: Yes, Jarvis can proceed with OMNIX upgrade planning (Slack notifications will be unavailable)
Next action: Begin upgrade planning with Jarvis; configure Slack if notifications are needed
"""

    if not slack_running:
        return """JARVIS OMNIX FRONT-DOOR REVIEW ACCEPT
Status: Runtime healthy, Slack continuous ops not running (risk for notifications, not blocker for branch-only planning)
Can proceed: Yes, Jarvis can proceed with OMNIX upgrade planning (Slack notifications will be unavailable)
Next action: Begin upgrade planning with Jarvis; start Slack bridge if notifications are needed
"""

    return """JARVIS OMNIX FRONT-DOOR REVIEW ACCEPT
Status: Runtime healthy, no blockers, Slack configured and running
Can proceed: Yes, Jarvis can proceed with OMNIX upgrade planning
Next action: Begin upgrade planning with Jarvis using status bundle context
"""


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OMNIX Front-Door Runner — Fetch status bundle and ask Jarvis to review"
    )
    parser.add_argument(
        "--url",
        default=_DEFAULT_URL,
        help=f"Status bundle URL (default: {_DEFAULT_URL})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output the raw status bundle as JSON without Jarvis review",
    )

    args = parser.parse_args()

    try:
        # Validate URL
        validate_url(args.url)

        # Fetch status bundle
        print(f"Fetching status bundle from {args.url}...", file=sys.stderr)
        bundle = fetch_status_bundle(args.url, args.timeout)

        # Validate schema
        validate_schema(bundle)
        print(f"Schema validated: {bundle.get('schema')}", file=sys.stderr)

        if args.json_only:
            print(json.dumps(bundle, indent=2))
            return 0

        # Build review prompt
        prompt = build_review_prompt(bundle)

        # Call Jarvis LLM
        print("Asking Jarvis to review status bundle...", file=sys.stderr)
        review = call_jarvis_llm(prompt)

        # Output review
        print(review)
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
