"""Jarvis Connector Diagnostics — status checks for all outbound connectors.

Connectors: Slack, Telegram, Web Search, GitHub, OpenClaw.

Each diagnostic:
  - Checks if required env vars are present (token presence only — NEVER print values)
  - Returns configured/not_configured/degraded/ready_pending_test_approval status
  - Provides exact env var names needed
  - Draft test send capability: always send_status=not_sent
  - No real external sends without explicit approval + Bryan-controlled destination

Hard rules (non-negotiable):
  - NEVER print or log token values
  - No real external sends — draft only
  - GitHub: read-only by default; no merges; no PR without explicit approval
  - OpenClaw: read-only path validation only; no mutations
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.projects.source_links import _load_openjarvis_env as _load_env


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------


class ConnectorStatus:
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    READY_PENDING_TEST = "ready_pending_test_approval"
    DEGRADED = "degraded"


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


def get_slack_status() -> Dict[str, Any]:
    """Check Slack connector readiness. Never prints token values."""
    _load_env()
    bot_token_present = bool(
        os.environ.get("OPENCLAW_SLACK_BOT_TOKEN")
        or os.environ.get("JARVIS_SLACK_BOT_TOKEN")
    )
    bot_token_var = (
        "OPENCLAW_SLACK_BOT_TOKEN"
        if os.environ.get("OPENCLAW_SLACK_BOT_TOKEN")
        else "JARVIS_SLACK_BOT_TOKEN"
    )
    test_channel_present = bool(os.environ.get("JARVIS_SLACK_TEST_CHANNEL_ID"))
    signing_secret_present = bool(os.environ.get("JARVIS_SLACK_SIGNING_SECRET"))

    missing: List[str] = []
    if not bot_token_present:
        missing.append("OPENCLAW_SLACK_BOT_TOKEN or JARVIS_SLACK_BOT_TOKEN")
    if not test_channel_present:
        missing.append("JARVIS_SLACK_TEST_CHANNEL_ID")

    if bot_token_present and test_channel_present:
        status = ConnectorStatus.READY_PENDING_TEST
        summary = (
            "Slack configured. Test send ready — requires approval + "
            "confirmed Bryan-controlled channel."
        )
    elif bot_token_present:
        status = ConnectorStatus.DEGRADED
        summary = "Slack bot token present but JARVIS_SLACK_TEST_CHANNEL_ID not set."
    else:
        status = ConnectorStatus.NOT_CONFIGURED
        summary = "Slack not configured. See missing_env_vars."

    return {
        "connector": "slack",
        "status": status,
        "summary": summary,
        "configured": bot_token_present,
        "bot_token_present": bot_token_present,
        "bot_token_env_var": bot_token_var if bot_token_present else None,
        "test_channel_present": test_channel_present,
        "signing_secret_present": signing_secret_present,
        "missing_env_vars": missing,
        "required_env_vars": [
            "OPENCLAW_SLACK_BOT_TOKEN or JARVIS_SLACK_BOT_TOKEN",
            "JARVIS_SLACK_TEST_CHANNEL_ID",
        ],
        "optional_env_vars": [
            "JARVIS_SLACK_SIGNING_SECRET (only for inbound events/webhooks)"
        ],
        "send_status": (
            "not_configured"
            if not bot_token_present
            else "ready_pending_approval"
        ),
        "real_send_allowed": False,
        "send_requires": (
            "explicit approval + Bryan-controlled channel confirmed + token set"
        ),
    }


def draft_slack_test_send(message: str = "Jarvis test message") -> Dict[str, Any]:
    """Draft a Slack test message. Always send_status=not_sent."""
    status = get_slack_status()
    channel_id = os.environ.get("JARVIS_SLACK_TEST_CHANNEL_ID", "")
    return {
        "draft_text": f"[DRAFT — not sent]\n{message}",
        "channel_id": (
            channel_id if channel_id else "(JARVIS_SLACK_TEST_CHANNEL_ID not set)"
        ),
        "send_status": "not_sent",
        "approval_required": True,
        "connector_status": status["status"],
        "blockers": status["missing_env_vars"],
        "note": (
            "No message sent. "
            "Set JARVIS_SLACK_TEST_CHANNEL_ID and obtain approval to send."
        ),
    }


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def get_telegram_status() -> Dict[str, Any]:
    """Check Telegram connector readiness. Never prints token values."""
    _load_env()
    bot_token_present = bool(os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN"))
    chat_id_present = bool(os.environ.get("JARVIS_TELEGRAM_CHAT_ID"))

    missing: List[str] = []
    if not bot_token_present:
        missing.append("JARVIS_TELEGRAM_BOT_TOKEN")
    if not chat_id_present:
        missing.append("JARVIS_TELEGRAM_CHAT_ID")

    if bot_token_present and chat_id_present:
        status = ConnectorStatus.READY_PENDING_TEST
        summary = (
            "Telegram configured. Test send ready — requires approval + "
            "confirmed Bryan-controlled chat."
        )
    elif bot_token_present:
        status = ConnectorStatus.DEGRADED
        summary = "Telegram bot token present but JARVIS_TELEGRAM_CHAT_ID not set."
    else:
        status = ConnectorStatus.NOT_CONFIGURED
        summary = "Telegram not configured. See missing_env_vars."

    return {
        "connector": "telegram",
        "status": status,
        "summary": summary,
        "configured": bot_token_present and chat_id_present,
        "bot_token_present": bot_token_present,
        "chat_id_present": chat_id_present,
        "missing_env_vars": missing,
        "required_env_vars": [
            "JARVIS_TELEGRAM_BOT_TOKEN",
            "JARVIS_TELEGRAM_CHAT_ID",
        ],
        "send_status": (
            "not_configured"
            if not (bot_token_present and chat_id_present)
            else "ready_pending_approval"
        ),
        "real_send_allowed": False,
        "send_requires": (
            "explicit approval + Bryan-controlled chat confirmed + tokens set"
        ),
    }


def draft_telegram_test_send(message: str = "Jarvis test message") -> Dict[str, Any]:
    """Draft a Telegram test message. Always send_status=not_sent."""
    status = get_telegram_status()
    chat_id = os.environ.get("JARVIS_TELEGRAM_CHAT_ID", "")
    return {
        "draft_text": f"[DRAFT — not sent]\n{message}",
        "chat_id": (
            chat_id if chat_id else "(JARVIS_TELEGRAM_CHAT_ID not set)"
        ),
        "send_status": "not_sent",
        "approval_required": True,
        "connector_status": status["status"],
        "blockers": status["missing_env_vars"],
        "note": (
            "No message sent. "
            "Set JARVIS_TELEGRAM_CHAT_ID and obtain approval to send."
        ),
    }


def get_telegram_command_status(command: str = "/status") -> Dict[str, Any]:
    """Preview what a Telegram command would do. No execution."""
    status = get_telegram_status()
    return {
        "command": command,
        "connector_status": status["status"],
        "would_execute": False,
        "requires": {
            "configured_token": status["bot_token_present"],
            "configured_chat_id": status["chat_id_present"],
            "approval": True,
        },
        "preview_only": True,
    }


def get_telegram_approval_preview(action: str, description: str = "") -> Dict[str, Any]:
    """Preview what a Telegram approval message would look like. No execution."""
    status = get_telegram_status()
    chat_id = os.environ.get("JARVIS_TELEGRAM_CHAT_ID", "")
    draft = (
        f"[JARVIS APPROVAL REQUEST]\n"
        f"Action: {action}\n"
        f"Description: {description or '(none)'}\n"
        f"Reply /approve or /reject"
    )
    return {
        "draft_message": draft,
        "chat_id": chat_id if chat_id else "(not set)",
        "send_status": "not_sent",
        "connector_status": status["status"],
        "approval_required": True,
        "preview_only": True,
    }


# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------


def get_web_search_status() -> Dict[str, Any]:
    """Check web search readiness. No fake available status."""
    _load_env()
    tavily = bool(os.environ.get("TAVILY_API_KEY"))
    serper = bool(os.environ.get("SERPER_API_KEY"))
    brave = bool(os.environ.get("BRAVE_SEARCH_API_KEY"))

    if tavily:
        return {
            "connector": "web_search",
            "status": ConnectorStatus.CONFIGURED,
            "provider": "tavily",
            "env_var": "TAVILY_API_KEY",
            "missing_env_vars": [],
        }
    if serper:
        return {
            "connector": "web_search",
            "status": ConnectorStatus.CONFIGURED,
            "provider": "serper",
            "env_var": "SERPER_API_KEY",
            "missing_env_vars": [],
        }
    if brave:
        return {
            "connector": "web_search",
            "status": ConnectorStatus.CONFIGURED,
            "provider": "brave_search",
            "env_var": "BRAVE_SEARCH_API_KEY",
            "missing_env_vars": [],
        }

    return {
        "connector": "web_search",
        "status": ConnectorStatus.NOT_CONFIGURED,
        "provider": None,
        "missing_env_vars": [
            "TAVILY_API_KEY (preferred — tavily.com)",
            "SERPER_API_KEY (serper.dev)",
            "BRAVE_SEARCH_API_KEY (search.brave.com/api)",
        ],
        "summary": "Web search not configured. No API key found.",
        "setup_options": [
            "Set TAVILY_API_KEY — recommended (tavily.com)",
            "Set SERPER_API_KEY (serper.dev)",
            "Set BRAVE_SEARCH_API_KEY (search.brave.com/api)",
        ],
    }


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


def get_github_status() -> Dict[str, Any]:
    """Check GitHub connector readiness. Read-only by default. No network calls."""
    github_token_present = bool(os.environ.get("GITHUB_TOKEN"))
    git_path = shutil.which("git")

    local_remote: Optional[str] = None
    fork_remote: Optional[str] = None

    if git_path:
        try:
            r = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                local_remote = r.stdout.strip()
        except Exception:
            pass
        try:
            r2 = subprocess.run(
                ["git", "remote", "get-url", "fork"],
                capture_output=True, text=True, timeout=5,
            )
            if r2.returncode == 0:
                fork_remote = r2.stdout.strip()
        except Exception:
            pass

    missing: List[str] = []
    if not github_token_present:
        missing.append(
            "GITHUB_TOKEN (optional — only needed for private repos or GitHub API)"
        )

    return {
        "connector": "github",
        "status": (
            ConnectorStatus.CONFIGURED if git_path
            else ConnectorStatus.NOT_CONFIGURED
        ),
        "git_available": git_path is not None,
        "git_path": git_path,
        "github_token_present": github_token_present,
        "local_remote_origin": local_remote,
        "local_remote_fork": fork_remote,
        "missing_env_vars": missing,
        "optional_env_vars": [
            "GITHUB_TOKEN (for private repos or GitHub API access)"
        ],
        "read_only": True,
        "pr_creation": "draft only, requires explicit approval",
        "merges": "always_blocked",
    }


def get_github_local_remote_info() -> Dict[str, Any]:
    """Get local git remote information (read-only, no network call)."""
    try:
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return {
                "ok": True,
                "remotes": result.stdout.strip(),
                "read_only": True,
            }
        return {"ok": False, "error": result.stderr.strip()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# OpenClaw
# ---------------------------------------------------------------------------


def get_openclaw_status() -> Dict[str, Any]:
    """Check OpenClaw workspace/handoff readiness. Read-only."""
    _load_env()
    workspace_path = os.environ.get("OPENCLAW_WORKSPACE_PATH", "")
    handoff_path = os.environ.get("OPENCLAW_HANDOFF_PATH", "")

    workspace_exists = Path(workspace_path).exists() if workspace_path else False
    handoff_exists = Path(handoff_path).exists() if handoff_path else False

    missing: List[str] = []
    if not workspace_path:
        missing.append("OPENCLAW_WORKSPACE_PATH")
    if not handoff_path:
        missing.append("OPENCLAW_HANDOFF_PATH")

    if workspace_path and handoff_path and workspace_exists and handoff_exists:
        status = ConnectorStatus.CONFIGURED
        summary = "OpenClaw workspace and handoff configured and accessible."
    elif workspace_path or handoff_path:
        status = ConnectorStatus.DEGRADED
        problems = []
        if workspace_path and not workspace_exists:
            problems.append(f"workspace path not found: {workspace_path}")
        if handoff_path and not handoff_exists:
            problems.append(f"handoff path not found: {handoff_path}")
        summary = f"OpenClaw partially configured. Issues: {', '.join(problems)}"
    else:
        status = ConnectorStatus.NOT_CONFIGURED
        summary = "OpenClaw not configured. Set OPENCLAW_WORKSPACE_PATH and OPENCLAW_HANDOFF_PATH."

    return {
        "connector": "openclaw",
        "status": status,
        "summary": summary,
        "workspace_path_set": bool(workspace_path),
        "workspace_exists": workspace_exists,
        "handoff_path_set": bool(handoff_path),
        "handoff_exists": handoff_exists,
        "missing_env_vars": missing,
        "required_env_vars": ["OPENCLAW_WORKSPACE_PATH", "OPENCLAW_HANDOFF_PATH"],
        "read_only": True,
        "mutations_allowed": False,
    }


def read_openclaw_handoff_summary() -> Dict[str, Any]:
    """Read OpenClaw handoff file summary. Read-only."""
    _load_env()
    handoff_path = os.environ.get("OPENCLAW_HANDOFF_PATH", "")
    if not handoff_path:
        return {
            "ok": False,
            "blocker": "OPENCLAW_HANDOFF_PATH not set",
        }
    p = Path(handoff_path)
    if not p.exists():
        return {
            "ok": False,
            "blocker": f"Handoff file not found: {handoff_path}",
        }
    if not p.is_file():
        return {
            "ok": False,
            "blocker": f"Handoff path is not a file: {handoff_path}",
        }
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        return {
            "ok": True,
            "path": handoff_path,
            "line_count": len(lines),
            "first_200_chars": content[:200],
            "size_bytes": p.stat().st_size,
            "read_only": True,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


__all__ = [
    "ConnectorStatus",
    "get_slack_status",
    "draft_slack_test_send",
    "get_telegram_status",
    "draft_telegram_test_send",
    "get_telegram_command_status",
    "get_telegram_approval_preview",
    "get_web_search_status",
    "get_github_status",
    "get_github_local_remote_info",
    "get_openclaw_status",
    "read_openclaw_handoff_summary",
]
