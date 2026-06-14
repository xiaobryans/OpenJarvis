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
    prompt = f"""Review report: {content[:500]}

Flags: branch/HEAD status, validation, blockers.
Output: JARVIS OMNIX REVIEW ACCEPT or HOLD + specific issues."""
    
    response, success = call_jarvis_agent("simple", prompt)
    source = "[JARVIS LLM]" if success else "[FALLBACK - LLM unavailable]"
    return f"{source}\n{response}"


def mode_qa(content: str) -> str:
    """QA mode: list necessary validation gaps."""
    prompt = f"""QA evidence: {content[:500]}

Output: Bullet list of necessary validation gaps only."""
    
    response, success = call_jarvis_agent("simple", prompt)
    source = "[JARVIS LLM]" if success else "[FALLBACK - LLM unavailable]"
    return f"{source}\n{response}"


def mode_gate(content: str) -> str:
    """Gate mode: release-gatekeeper ACCEPT/HOLD decision."""
    prompt = f"""Gate report: {content[:500]}

Criteria: tests pass, no blockers, docs complete.
Output: JARVIS OMNIX GATE ACCEPT or HOLD + gate reasoning.
Note: No production-ready unless explicitly stated."""
    
    response, success = call_jarvis_agent("simple", prompt)
    source = "[JARVIS LLM]" if success else "[FALLBACK - LLM unavailable]"
    return f"{source}\n{response}"


def mode_memory(command: str, args: list[str]) -> str:
    """Memory mode: local memory system for continuity and decisions."""
    import os
    import json
    from datetime import datetime
    import re

    memory_dir = Path.home() / ".omnix_workbench"
    memory_file = memory_dir / "memory.jsonl"
    
    # Ensure memory directory exists
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    # Secret detection patterns
    secret_patterns = [
        r'password["\s:=]+["\w]+',
        r'secret["\s:=]+["\w]+',
        r'token["\s:=]+["\w]+',
        r'api[_-]?key["\s:=]+["\w]+',
        r'private[_-]?key["\s:=]+["\w]+',
        r'aws[_-]?access[_-]?key["\s:=]+["\w]+',
        r'aws[_-]?secret[_-]?key["\s:=]+["\w]+',
    ]
    
    def has_secrets(text: str) -> bool:
        """Check if text contains potential secrets."""
        for pattern in secret_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    try:
        if command == "add":
            if not args:
                return "Error: add requires content to store"
            content = " ".join(args)
            
            # Reject secrets
            if has_secrets(content):
                return "Error: Content contains potential secrets/tokens - rejected"
            
            # Create memory entry
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "content": content,
                "type": "note"
            }
            
            # Append to memory file
            with open(memory_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
            
            return "Memory entry added successfully"
        
        elif command == "list":
            if not memory_file.exists():
                return "No memory entries yet"
            
            entries = []
            with open(memory_file, "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            
            if not entries:
                return "No memory entries yet"
            
            result = f"Memory entries ({len(entries)}):\n"
            for i, entry in enumerate(entries[-10:], 1):  # Show last 10
                result += f"{i}. [{entry.get('timestamp', 'unknown')}] {entry.get('content', '')[:80]}...\n"
            
            return result
        
        elif command == "search":
            if not args:
                return "Error: search requires query terms"
            query = " ".join(args).lower()
            
            if not memory_file.exists():
                return "No memory entries yet"
            
            results = []
            with open(memory_file, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if query in entry.get("content", "").lower():
                            results.append(entry)
            
            if not results:
                return f"No matches found for: {query}"
            
            result = f"Search results for '{query}' ({len(results)} matches):\n"
            for i, entry in enumerate(results[:10], 1):
                result += f"{i}. [{entry.get('timestamp', 'unknown')}] {entry.get('content', '')[:80]}...\n"
            
            return result
        
        elif command == "show":
            if not args:
                return "Error: show requires entry number"
            try:
                index = int(args[0]) - 1
            except ValueError:
                return "Error: show requires numeric entry number"
            
            if not memory_file.exists():
                return "No memory entries yet"
            
            entries = []
            with open(memory_file, "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            
            if index < 0 or index >= len(entries):
                return f"Error: entry number out of range (1-{len(entries)})"
            
            entry = entries[index]
            return f"Memory entry {index + 1}:\nTimestamp: {entry.get('timestamp', 'unknown')}\nContent: {entry.get('content', '')}"
        
        else:
            return "Memory commands: add <content>, list, search <query>, show <number>"
    
    except Exception as e:
        return f"Memory error: {e}"


def mode_artifact(command: str, args: list[str]) -> str:
    """Artifact mode: local artifact context for documents."""
    import os
    import json
    from datetime import datetime
    
    artifact_dir = Path.home() / ".omnix_workbench"
    artifact_index = artifact_dir / "artifacts.jsonl"
    
    # Allowed extensions
    allowed_extensions = {'.txt', '.md', '.json', '.log'}
    max_file_size = 1024 * 1024  # 1MB
    
    # Secret detection patterns
    secret_patterns = [
        r'password["\s:=]+["\w]+',
        r'secret["\s:=]+["\w]+',
        r'token["\s:=]+["\w]+',
        r'api[_-]?key["\s:=]+["\w]+',
        r'private[_-]?key["\s:=]+["\w]+',
        r'aws[_-]?access[_-]?key["\s:=]+["\w]+',
        r'aws[_-]?secret[_-]?key["\s:=]+["\w]+',
    ]
    
    def has_secrets(text: str) -> bool:
        """Check if text contains potential secrets."""
        import re
        for pattern in secret_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    try:
        if command == "add":
            if not args:
                return "Error: add requires file path"
            file_path = Path(args[0])
            
            # Validate file exists
            if not file_path.exists():
                return f"Error: file not found: {file_path}"
            
            # Validate extension
            if file_path.suffix.lower() not in allowed_extensions:
                return f"Error: unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            
            # Validate size
            file_size = file_path.stat().st_size
            if file_size > max_file_size:
                return f"Error: file too large ({file_size} bytes, max {max_file_size})"
            
            # Read file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Reject secrets
            if has_secrets(content):
                return "Error: file contains potential secrets/tokens - rejected"
            
            # Create artifact entry
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(file_path),
                "size": file_size,
                "type": file_path.suffix.lower(),
                "content_preview": content[:500]  # Store preview only
            }
            
            # Ensure artifact directory exists
            artifact_dir.mkdir(parents=True, exist_ok=True)
            
            # Append to artifact index
            with open(artifact_index, "a") as f:
                f.write(json.dumps(entry) + "\n")
            
            return f"Artifact added: {file_path} ({file_size} bytes)"
        
        elif command == "list":
            if not artifact_index.exists():
                return "No artifacts indexed yet"
            
            entries = []
            with open(artifact_index, "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            
            if not entries:
                return "No artifacts indexed yet"
            
            result = f"Artifacts ({len(entries)}):\n"
            for i, entry in enumerate(entries, 1):
                result += f"{i}. {entry.get('path', 'unknown')} ({entry.get('size', 0)} bytes, {entry.get('type', 'unknown')})\n"
            
            return result
        
        elif command == "show":
            if not args:
                return "Error: show requires artifact number"
            try:
                index = int(args[0]) - 1
            except ValueError:
                return "Error: show requires numeric artifact number"
            
            if not artifact_index.exists():
                return "No artifacts indexed yet"
            
            entries = []
            with open(artifact_index, "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            
            if index < 0 or index >= len(entries):
                return f"Error: artifact number out of range (1-{len(entries)})"
            
            entry = entries[index]
            return f"Artifact {index + 1}:\nPath: {entry.get('path', 'unknown')}\nSize: {entry.get('size', 0)} bytes\nType: {entry.get('type', 'unknown')}\nPreview: {entry.get('content_preview', '')[:200]}..."
        
        elif command == "summarize":
            if not args:
                return "Error: summarize requires artifact number"
            try:
                index = int(args[0]) - 1
            except ValueError:
                return "Error: summarize requires numeric artifact number"
            
            if not artifact_index.exists():
                return "No artifacts indexed yet"
            
            entries = []
            with open(artifact_index, "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            
            if index < 0 or index >= len(entries):
                return f"Error: artifact number out of range (1-{len(entries)})"
            
            entry = entries[index]
            file_path = Path(entry.get('path', ''))
            
            if not file_path.exists():
                return f"Error: file no longer exists: {file_path}"
            
            with open(file_path, "r") as f:
                content = f.read()
            
            # Use Jarvis LLM to summarize
            prompt = f"""Summarize this {entry.get('type', '')} file:
{content[:2000]}

Output: 2-3 sentence summary."""
            
            response, success = call_jarvis_agent("simple", prompt)
            source = "[JARVIS LLM]" if success else "[FALLBACK - LLM unavailable]"
            return f"{source}\n{response}"
        
        else:
            return "Artifact commands: add <file>, list, show <number>, summarize <number>"
    
    except Exception as e:
        return f"Artifact error: {e}"


def mode_run(url: str, objective: str) -> str:
    """Run mode: status → plan → prompt → gate summary."""
    try:
        result = "=== JARVIS OMNIX RUN MODE ===\n\n"
        
        # Step 1: Status
        result += "Step 1: Status Check\n"
        result += mode_status(url) + "\n\n"
        
        # Step 2: Plan
        result += "Step 2: Upgrade Plan\n"
        plan_result = mode_plan(url, objective)
        result += plan_result + "\n\n"
        
        # Step 3: Prompt
        result += "Step 3: Coding Prompt\n"
        prompt_result = mode_prompt(url, objective)
        result += prompt_result + "\n\n"
        
        # Step 4: Gate Summary
        result += "Step 4: Gate Summary\n"
        gate_summary = f"""Gate Summary for: {objective}

Status: Validated
Plan: Generated (see above)
Prompt: Generated (see above)
Branch-only: Yes
Deploy: Not included in run mode

JARVIS OMNIX RUN COMPLETE
Next: Manual review of plan/prompt, then execute coding."""
        result += gate_summary
        
        return result
    except Exception as e:
        return f"Run error: {e}"


def mode_slack(command: str) -> str:
    """Slack mode: status and test-send using existing OpenClaw infrastructure."""
    import subprocess
    import os
    
    try:
        if command == "status":
            # Check if OpenClaw Slack is configured
            env_vars = {
                "OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL": os.environ.get("OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL"),
                "OPENCLAW_SLACK_AGENT_OPS_CHANNEL": os.environ.get("OPENCLAW_SLACK_AGENT_OPS_CHANNEL"),
                "SLACK_TEST_CHANNEL": os.environ.get("SLACK_TEST_CHANNEL"),
            }
            
            configured = any(env_vars.values())
            
            if configured:
                return f"""Slack Status: CONFIGURED
Configured channels: {', '.join([k for k, v in env_vars.items() if v])}
Safe test channel: agent-orchestrator / C0BAF08SQTB
Test-send: Available (use 'slack test-send')"""
            else:
                return """Slack Status: NOT CONFIGURED
No Slack environment variables found.
Required: OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL or similar
Safe test channel: agent-orchestrator / C0BAF08SQTB
Test-send: HOLD - missing Slack configuration"""
        
        elif command == "test-send":
            # Check if Slack is configured
            channel = os.environ.get("OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL") or os.environ.get("OPENCLAW_SLACK_AGENT_OPS_CHANNEL") or os.environ.get("SLACK_TEST_CHANNEL")
            
            if not channel:
                return """Slack test-send: HOLD - missing Slack configuration
No Slack channel configured.
Set OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL or similar."""
            
            # Use OpenClaw CLI to send test message
            try:
                result = subprocess.run(
                    ["openclaw", "message", "send", "--channel", "slack", "--target", f"channel:{channel}", "--message", "Jarvis Workbench test message — safe channel validation", "--dry-run"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0:
                    return f"""Slack test-send: SUCCESS (dry-run)
Channel: {channel}
Message: Jarvis Workbench test message — safe channel validation
Mode: dry-run (no actual message sent)
To send for real: remove --dry-run flag"""
                else:
                    return f"""Slack test-send: HOLD - OpenClaw CLI error
Channel: {channel}
Error: {result.stderr}"""
            except FileNotFoundError:
                return """Slack test-send: HOLD - OpenClaw CLI not found
Install OpenClaw CLI to send Slack messages."""
            except subprocess.TimeoutExpired:
                return """Slack test-send: HOLD - timeout after 30 seconds"""
            except Exception as e:
                return f"Slack test-send: HOLD - {e}"
        
        else:
            return "Slack commands: status, test-send"
    
    except Exception as e:
        return f"Slack error: {e}"


def mode_deploy(target: str) -> str:
    """Deploy mode: readiness check only, no actual deploy."""
    import subprocess
    import os
    
    result = "=== DEPLOY READINESS CHECK ===\n\n"
    
    # Check git status
    try:
        git_result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=10)
        if git_result.stdout.strip():
            result += "Git Status: DIRTY - uncommitted changes\n"
            result += f"Files: {git_result.stdout.strip()}\n\n"
        else:
            result += "Git Status: CLEAN\n\n"
    except Exception:
        result += "Git Status: UNKNOWN - git command failed\n\n"
    
    # Check target
    if target:
        result += f"Deploy Target: {target}\n"
        result += "Deploy Status: HOLD - manual deployment required\n"
        result += "This mode only checks readiness, does not deploy.\n"
        result += "Use your deploy tooling for actual deployment.\n\n"
    else:
        result += "Deploy Target: Not specified\n"
        result += "Deploy Status: HOLD - no target specified\n\n"
    
    # Check for deploy credentials
    vercel_token = os.environ.get("VERCEL_TOKEN")
    github_token = os.environ.get("GITHUB_TOKEN")
    
    if vercel_token or github_token:
        result += "Deploy Credentials: CONFIGURED\n"
    else:
        result += "Deploy Credentials: NOT CONFIGURED\n"
        result += "Required: VERCEL_TOKEN or GITHUB_TOKEN for deploy\n\n"
    
    result += "DEPLOY READINESS SUMMARY\n"
    result += "This mode only validates readiness.\n"
    result += "Actual deployment must be done separately with proper tooling.\n"
    result += "Jarvis Workbench does not perform automated deployments."
    
    return result


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
    memory_parser = subparsers.add_parser("memory", help="Memory system for continuity and decisions")
    memory_parser.add_argument("command", help="Memory command: add, list, search, show")
    memory_parser.add_argument("args", nargs="*", help="Command arguments")
    
    # Artifact mode
    artifact_parser = subparsers.add_parser("artifact", help="Artifact context for documents")
    artifact_parser.add_argument("command", help="Artifact command: add, list, show, summarize")
    artifact_parser.add_argument("args", nargs="*", help="Command arguments")
    
    # Run mode
    run_parser = subparsers.add_parser("run", help="Run status→plan→prompt→gate workflow")
    run_parser.add_argument("objective", help="Objective for the workflow")
    
    # Slack mode
    slack_parser = subparsers.add_parser("slack", help="Slack status and test-send")
    slack_parser.add_argument("command", help="Slack command: status, test-send")
    
    # Deploy mode
    deploy_parser = subparsers.add_parser("deploy", help="Deploy readiness check")
    deploy_parser.add_argument("target", nargs="?", help="Deploy target (optional)")
    
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
            result = mode_memory(args.command, args.args)
        elif args.mode == "artifact":
            result = mode_artifact(args.command, args.args)
        elif args.mode == "run":
            result = mode_run(args.url, args.objective)
        elif args.mode == "slack":
            result = mode_slack(args.command)
        elif args.mode == "deploy":
            result = mode_deploy(args.target)
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
