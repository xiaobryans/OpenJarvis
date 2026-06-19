"""Slack Workspace Identity and Jarvis HQ Migration Model.

Tracks the migration from OMNIX HQ (legacy) to Jarvis HQ (target).

Design rules:
  - Never prints or returns token values.
  - auth.test is the only live Slack call made here; it reads workspace identity only.
  - No channel creation, deletion, rename, or message sending.
  - Migration actions that require Bryan authorization are classified
    BLOCKED_USER_AUTHORIZATION — not auto-executed.
  - All live-send actions are permanently BLOCKED_SAFETY until per-action auth.

Migration modes:
  REUSE_EXISTING_WORKSPACE   — keep OMNIX HQ workspace; rename app/bot only
  RENAME_EXISTING_WORKSPACE  — rename workspace (requires Bryan + Slack admin)
  CREATE_NEW_WORKSPACE_MANUAL_FALLBACK — manual new workspace if rename impossible

Migration status values:
  OMNIX_HQ_CURRENT                — token verified as OMNIX HQ workspace
  JARVIS_HQ_TARGET_READY          — workspace renamed/confirmed as Jarvis HQ
  JARVIS_HQ_RENAME_REQUIRED       — rename needed; not yet done
  JARVIS_HQ_TOKEN_VERIFIED        — token valid and points to Jarvis HQ
  TOKEN_WORKSPACE_IDENTITY_UNKNOWN — token valid but workspace name unresolved
  MIGRATION_BLOCKED_USER_ACTION   — migration requires explicit Bryan action
  TOKEN_NOT_PRESENT               — SLACK_BOT_TOKEN not configured
  TOKEN_INVALID                   — auth.test returned not-ok
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Target identity
JARVIS_HQ_TARGET_NAME = "Jarvis HQ"
LEGACY_WORKSPACE_NAME = "OMNIX HQ"

_CLOUD_KEYS_PATH = Path.home() / ".jarvis" / "cloud-keys.env"


def _load_slack_token() -> Optional[str]:
    """Load SLACK_BOT_TOKEN from env or ~/.jarvis/cloud-keys.env. Never returns value in logs."""
    for key in ["SLACK_BOT_TOKEN", "OPENCLAW_SLACK_BOT_TOKEN", "JARVIS_SLACK_BOT_TOKEN"]:
        v = os.environ.get(key)
        if v:
            return v
    if _CLOUD_KEYS_PATH.exists():
        try:
            for line in _CLOUD_KEYS_PATH.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                k, _, v = line.partition("=")
                if k.strip() in ("SLACK_BOT_TOKEN", "OPENCLAW_SLACK_BOT_TOKEN", "JARVIS_SLACK_BOT_TOKEN"):
                    return v.strip()
        except Exception:
            pass
    return None


def _safe_auth_test(token: str) -> Dict[str, Any]:
    """Call Slack auth.test to get workspace identity. Never logs token."""
    try:
        import urllib.request
        import json
        req = urllib.request.Request(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        return data
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@dataclass
class SlackWorkspaceIdentity:
    """Result of workspace identity verification via auth.test."""
    token_present: bool
    token_valid: bool
    workspace_name: Optional[str]
    workspace_team_id: Optional[str]
    bot_user: Optional[str]
    bot_id: Optional[str]
    is_legacy_omnix_hq: bool
    is_jarvis_hq: bool
    migration_status: str
    migration_mode: str
    migration_notes: List[str]
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_present": self.token_present,
            "token_valid": self.token_valid,
            "workspace_name": self.workspace_name,
            "workspace_team_id": self.workspace_team_id,
            "bot_user": self.bot_user,
            "bot_id": self.bot_id,
            "is_legacy_omnix_hq": self.is_legacy_omnix_hq,
            "is_jarvis_hq": self.is_jarvis_hq,
            "migration_status": self.migration_status,
            "migration_mode": self.migration_mode,
            "migration_notes": self.migration_notes,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


def verify_workspace_identity() -> SlackWorkspaceIdentity:
    """Check Slack token and determine workspace identity/migration status.

    Makes one safe auth.test call. Never prints or returns token value.
    """
    token = _load_slack_token()
    if not token:
        return SlackWorkspaceIdentity(
            token_present=False,
            token_valid=False,
            workspace_name=None,
            workspace_team_id=None,
            bot_user=None,
            bot_id=None,
            is_legacy_omnix_hq=False,
            is_jarvis_hq=False,
            migration_status="TOKEN_NOT_PRESENT",
            migration_mode="CREATE_NEW_WORKSPACE_MANUAL_FALLBACK",
            migration_notes=[
                "SLACK_BOT_TOKEN not configured.",
                "Bryan action: set SLACK_BOT_TOKEN in ~/.jarvis/cloud-keys.env",
            ],
        )

    data = _safe_auth_test(token)
    if not data.get("ok"):
        return SlackWorkspaceIdentity(
            token_present=True,
            token_valid=False,
            workspace_name=None,
            workspace_team_id=None,
            bot_user=None,
            bot_id=None,
            is_legacy_omnix_hq=False,
            is_jarvis_hq=False,
            migration_status="TOKEN_INVALID",
            migration_mode="REUSE_EXISTING_WORKSPACE",
            migration_notes=[
                f"auth.test returned error: {data.get('error', 'unknown')}",
                "Bryan action: verify SLACK_BOT_TOKEN is valid and not revoked.",
            ],
        )

    ws_name = data.get("team", "") or ""
    team_id = data.get("team_id", "") or ""
    bot_user = data.get("user", "") or ""
    bot_id = data.get("bot_id", "") or ""

    is_legacy = ws_name == LEGACY_WORKSPACE_NAME or "omnix" in ws_name.lower()
    is_jarvis_hq = ws_name == JARVIS_HQ_TARGET_NAME or "jarvis" in ws_name.lower()

    if is_jarvis_hq:
        status = "JARVIS_HQ_TOKEN_VERIFIED"
        mode = "REUSE_EXISTING_WORKSPACE"
        notes = ["Token is verified against Jarvis HQ workspace. Migration complete."]
    elif is_legacy:
        status = "OMNIX_HQ_CURRENT"
        mode = "REUSE_EXISTING_WORKSPACE"
        notes = [
            f"Token is verified against legacy workspace '{ws_name}'.",
            "Preferred migration path: REUSE_EXISTING_WORKSPACE.",
            "Bryan can rename the Slack workspace from Slack admin settings: "
            f"Settings → Workspace Settings → Name → change from '{ws_name}' to 'Jarvis HQ'.",
            "Workspace rename requires Slack admin permission and is a Bryan manual action.",
            "Bot user 'openjarvis' is already Jarvis-named — app identity is ready.",
            "Migration status: JARVIS_HQ_RENAME_REQUIRED — workspace name only.",
        ]
        status = "JARVIS_HQ_RENAME_REQUIRED"
    else:
        status = "TOKEN_WORKSPACE_IDENTITY_UNKNOWN"
        mode = "REUSE_EXISTING_WORKSPACE"
        notes = [
            f"Token workspace: '{ws_name}'. Neither OMNIX HQ nor Jarvis HQ by name.",
            "Treat as reusable workspace. Confirm workspace intent with Bryan.",
        ]

    return SlackWorkspaceIdentity(
        token_present=True,
        token_valid=True,
        workspace_name=ws_name,
        workspace_team_id=team_id,
        bot_user=bot_user,
        bot_id=bot_id,
        is_legacy_omnix_hq=is_legacy,
        is_jarvis_hq=is_jarvis_hq,
        migration_status=status,
        migration_mode=mode,
        migration_notes=notes,
    )


# ---------------------------------------------------------------------------
# Jarvis HQ Channel/App/Agent Manifest
# ---------------------------------------------------------------------------

JARVIS_HQ_MANIFEST: Dict[str, Any] = {
    "workspace_target": "Jarvis HQ",
    "migration_mode": "REUSE_EXISTING_WORKSPACE",
    "required_channels": [
        {"name": "#jarvis-ops", "purpose": "Jarvis runtime ops, alerts, health checks"},
        {"name": "#jarvis-tasks", "purpose": "Task dispatch, status, completion notifications"},
        {"name": "#jarvis-debug", "purpose": "Trace replay, error logs, doctor output"},
        {"name": "#jarvis-approvals", "purpose": "Hard-gate approval requests"},
        {"name": "#omnix-project", "purpose": "OMNIX project-specific updates (OMNIX as one project)"},
    ],
    "optional_channels": [
        {"name": "#jarvis-coding", "purpose": "Coding agent activity, patch proposals, test results"},
        {"name": "#jarvis-memory", "purpose": "Memory quality alerts, stale conflict flags"},
        {"name": "#jarvis-connectors", "purpose": "Connector auth status, dry-run plans"},
        {"name": "#jarvis-voice", "purpose": "Voice pipeline status — reserved for Voice sprint"},
    ],
    "bot_roles": [
        {"role": "Jarvis Runtime Bot", "token_var": "SLACK_BOT_TOKEN",
         "scopes": ["channels:read", "channels:history", "chat:write", "files:write"],
         "current_bot_user": "openjarvis",
         "status": "BLOCKED_CREDENTIALS",
         "note": "SLACK_BOT_TOKEN present; write scopes may need re-authorization for new channels"},
    ],
    "agent_channel_mapping": {
        "cos_gm_orchestrator": "#jarvis-ops",
        "doctor_worker": "#jarvis-debug",
        "approval_worker": "#jarvis-approvals",
        "coding_worker": "#jarvis-coding",
        "omnix_adapter": "#omnix-project",
    },
    "live_send_policy": "BLOCKED_SAFETY — all live sends require per-action Bryan authorization",
    "dry_run_policy": "All connector actions produce structured dry-run plans; no live sends",
    "approval_gates": [
        "Real message sends require explicit Bryan approval per send",
        "Channel creation requires Bryan authorization",
        "App installation requires Bryan authorization",
    ],
    "migration_checklist": [
        {"step": "Verify token linked to correct workspace", "status": "DONE — verified via auth.test"},
        {"step": "Rename workspace to 'Jarvis HQ'", "status": "REQUIRED — Bryan manual action in Slack admin"},
        {"step": "Update bot display name to 'Jarvis'", "status": "REQUIRED — Bryan action in Slack app settings"},
        {"step": "Create required channels", "status": "BLOCKED_USER_AUTHORIZATION — Bryan must authorize channel creation"},
        {"step": "Configure channel IDs in cloud-keys.env", "status": "BLOCKED_USER_AUTHORIZATION — after channel creation"},
        {"step": "Remove OMNIX HQ identity references in code", "status": "IN_PROGRESS — omnix_slack.py refactored"},
    ],
    "rollback_plan": (
        "If Jarvis HQ migration fails: OMNIX HQ workspace remains fully functional. "
        "Token is unchanged. No channels or apps deleted. "
        "Revert: clear JARVIS_WORKSPACE_NAME env var; existing OMNIX HQ setup resumes."
    ),
    "omnix_hq_deletion": "OPTIONAL_BACKLOG — not required; OMNIX remains as legacy project/adapter",
}


def get_jarvis_hq_manifest() -> Dict[str, Any]:
    """Return the Jarvis HQ Slack workspace manifest."""
    return JARVIS_HQ_MANIFEST


__all__ = [
    "SlackWorkspaceIdentity",
    "verify_workspace_identity",
    "get_jarvis_hq_manifest",
    "JARVIS_HQ_MANIFEST",
    "JARVIS_HQ_TARGET_NAME",
    "LEGACY_WORKSPACE_NAME",
]
