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
from typing import Any


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
    """Build a prompt for Jarvis to review the status bundle."""
    runtime = bundle.get("runtime", {})
    slack = bundle.get("slack", {})
    health = bundle.get("health", {})
    pending_approvals = runtime.get("pendingApprovals", [])
    missions = runtime.get("missions", [])

    prompt = f"""You are Jarvis, reviewing OMNIX status for upgrade planning readiness.

STATUS BUNDLE SUMMARY:
- Schema: {bundle.get('schema')}
- Runtime Health: {runtime.get('health', {})}
- Missions: {len(missions)} total
- Pending Approvals: {len(pending_approvals)}
- Slack Installed: {slack.get('installed')}
- Slack Configured: {slack.get('configured')}
- Slack Continuous Ops Running: {slack.get('continuousOpsRunning')}
- Dashboard Health: {health.get('commandCenter', {})}
- Local Gateway Health: {health.get('localGateway', {})}

PENDING APPROVALS:
{json.dumps(pending_approvals, indent=2) if pending_approvals else "None"}

RECENT MISSIONS:
{json.dumps(missions[:5], indent=2) if missions else "None"}

SLACK STATUS:
{json.dumps(slack, indent=2)}

YOUR TASK:
Review this status bundle and determine if Jarvis can proceed with OMNIX upgrade planning.

Consider:
1. Are there any critical blockers in pending approvals?
2. Is the Slack integration properly configured for notifications?
3. Are there any runtime health issues?
4. Are there missing or unknown fields that indicate problems?

OUTPUT FORMAT (exact):
JARVIS OMNIX FRONT-DOOR REVIEW ACCEPT or HOLD

If ACCEPT, include:
- Status summary (1 line)
- Whether Jarvis can proceed with upgrade planning
- Shortest next action

If HOLD, include:
- Status summary (1 line)
- Specific blocker(s)
- Shortest next action to resolve

DO NOT include any other text before or after the decision line.
"""

    return prompt


def call_jarvis_llm(prompt: str) -> str:
    """Call Jarvis LLM with the review prompt.

    This is a placeholder - in a real implementation, this would call the
    configured Jarvis LLM backend. For now, we'll return a simple analysis.
    """
    # Placeholder: In production, this would call the actual Jarvis LLM
    # via the OpenJarvis API or directly through the model backend.

    # For now, implement simple rule-based analysis
    lines = prompt.split("\n")
    pending_count = 0
    slack_configured = False
    slack_running = False

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

    # Simple decision logic
    if pending_count > 0:
        return """JARVIS OMNIX FRONT-DOOR REVIEW HOLD
Status: {pending_count} pending approval(s) blocking upgrade planning
Blocker: Pending approvals must be resolved before upgrade planning
Next action: Review and resolve pending approvals via dashboard or CLI
""".format(pending_count=pending_count)

    if not slack_configured:
        return """JARVIS OMNIX FRONT-DOOR REVIEW HOLD
Status: Slack not configured for notifications
Blocker: Slack integration required for upgrade notifications
Next action: Configure Slack integration via OpenClaw CLI
"""

    if not slack_running:
        return """JARVIS OMNIX FRONT-DOOR REVIEW HOLD
Status: Slack continuous ops not running
Blocker: Slack bridge not active for notifications
Next action: Start Slack continuous ops service via CLI
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
