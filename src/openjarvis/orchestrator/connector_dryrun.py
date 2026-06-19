"""Connector Dry-Run Framework and Auth Manager Classification.

Provides per-connector capability records and dry-run action planning
for Gmail, Calendar, Slack, Telegram, GitHub, and Drive.

Design rules (non-negotiable):
  - No live connector execution in this module.
  - No real OAuth token reads, writes, or refreshes.
  - No external HTTP calls.
  - No secret values in any record or output.
  - Live execution remains BLOCKED unless Bryan explicitly authorizes.
  - Dry-run produces a structured action plan with required scopes/credentials.
  - Auth manager is classified into four distinct categories — not combined.

Connector auth manager blocker categories (separate, not combined):
  1. BLOCKED_IMPLEMENTATION — workers not yet written
  2. BLOCKED_CREDENTIALS — OAuth tokens / API keys not configured
  3. BLOCKED_SAFETY — live secret access permanently blocked
  4. BLOCKED_USER_AUTHORIZATION — requires explicit Bryan authorization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# ConnectorRecord — per-connector capability record
# ---------------------------------------------------------------------------

@dataclass
class ConnectorRecord:
    """Capability record for a single connector."""
    connector_id: str
    display_name: str
    credential_env_vars: List[str]           # env vars needed (never shown as values)
    required_oauth_scopes: List[str]         # OAuth scopes needed (if applicable)
    dry_run_actions: List[str]               # safe planning-only actions available now
    live_actions_blocked_until: str          # what must happen before live exec allowed
    implementation_status: str              # "available" | "BLOCKED_IMPLEMENTATION" | "partial"
    credentials_status: str                 # "configured" | "BLOCKED_CREDENTIALS"
    authorization_status: str               # "authorized" | "BLOCKED_USER_AUTHORIZATION"
    safety_status: str                      # "safe" | "BLOCKED_SAFETY"
    bryan_action: str
    fallback_behavior: str

    def overall_status(self) -> str:
        """Return the most restrictive status."""
        if self.safety_status == "BLOCKED_SAFETY":
            return "BLOCKED_SAFETY"
        if self.implementation_status == "BLOCKED_IMPLEMENTATION":
            return "BLOCKED_IMPLEMENTATION"
        if self.credentials_status == "BLOCKED_CREDENTIALS":
            return "BLOCKED_CREDENTIALS"
        if self.authorization_status == "BLOCKED_USER_AUTHORIZATION":
            return "BLOCKED_USER_AUTHORIZATION"
        return "dry_run_available"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "display_name": self.display_name,
            "credential_env_vars": self.credential_env_vars,
            "required_oauth_scopes": self.required_oauth_scopes,
            "dry_run_actions": self.dry_run_actions,
            "live_actions_blocked_until": self.live_actions_blocked_until,
            "implementation_status": self.implementation_status,
            "credentials_status": self.credentials_status,
            "authorization_status": self.authorization_status,
            "safety_status": self.safety_status,
            "overall_status": self.overall_status(),
            "bryan_action": self.bryan_action,
            "fallback_behavior": self.fallback_behavior,
        }


# ---------------------------------------------------------------------------
# ConnectorDryRunPlan — structured action plan without live execution
# ---------------------------------------------------------------------------

@dataclass
class ConnectorDryRunPlan:
    """Structured dry-run action plan for a connector action.

    This is a planning-only output — no live execution performed.
    All values are descriptions/plans, never real credentials or data.
    """
    connector_id: str
    action: str
    status: str          # "dry_run_plan" | "blocked"
    blocked_reason: Optional[str]
    plan_steps: List[str]
    required_credentials: List[str]   # env var names only, no values
    required_scopes: List[str]
    estimated_safety: str             # "safe" | "requires_approval"
    approval_required: bool
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "action": self.action,
            "status": self.status,
            "blocked_reason": self.blocked_reason,
            "plan_steps": self.plan_steps,
            "required_credentials": self.required_credentials,
            "required_scopes": self.required_scopes,
            "estimated_safety": self.estimated_safety,
            "approval_required": self.approval_required,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


# ---------------------------------------------------------------------------
# ConnectorRegistry — all known connectors
# ---------------------------------------------------------------------------

_CONNECTOR_REGISTRY: Dict[str, ConnectorRecord] = {}


def _build_registry() -> None:
    records = [
        ConnectorRecord(
            connector_id="gmail",
            display_name="Gmail",
            credential_env_vars=["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"],
            required_oauth_scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
            ],
            dry_run_actions=[
                "list_labels_plan",
                "search_emails_plan",
                "draft_email_plan",
            ],
            live_actions_blocked_until=(
                "GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET configured "
                "AND Bryan explicitly authorizes Gmail connector activation."
            ),
            implementation_status="available",
            credentials_status="BLOCKED_CREDENTIALS",
            authorization_status="BLOCKED_USER_AUTHORIZATION",
            safety_status="safe",
            bryan_action=(
                "1. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET "
                "in ~/.jarvis/cloud-keys.env. "
                "2. Authorize Gmail connector: jarvis connect gmail"
            ),
            fallback_behavior="Dry-run email action plans only. No real sends.",
        ),
        ConnectorRecord(
            connector_id="gcalendar",
            display_name="Google Calendar",
            credential_env_vars=["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"],
            required_oauth_scopes=[
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/calendar.events",
            ],
            dry_run_actions=[
                "list_events_plan",
                "create_event_plan",
                "check_availability_plan",
            ],
            live_actions_blocked_until=(
                "GOOGLE_OAUTH_CLIENT_ID configured AND Bryan authorizes Calendar connector."
            ),
            implementation_status="available",
            credentials_status="BLOCKED_CREDENTIALS",
            authorization_status="BLOCKED_USER_AUTHORIZATION",
            safety_status="safe",
            bryan_action=(
                "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET "
                "in ~/.jarvis/cloud-keys.env, then authorize: jarvis connect gcalendar"
            ),
            fallback_behavior="Dry-run calendar action plans only. No real event creation.",
        ),
        ConnectorRecord(
            connector_id="slack",
            display_name="Slack",
            credential_env_vars=["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"],
            required_oauth_scopes=[
                "channels:read",
                "chat:write",
                "files:write",
            ],
            dry_run_actions=[
                "list_channels_plan",
                "draft_message_plan",
            ],
            live_actions_blocked_until=(
                "SLACK_BOT_TOKEN configured AND Bryan authorizes Slack sends. "
                "Real sends are a hard-gated external_send action."
            ),
            implementation_status="available",
            credentials_status="BLOCKED_CREDENTIALS",
            authorization_status="BLOCKED_USER_AUTHORIZATION",
            safety_status="BLOCKED_SAFETY",
            bryan_action=(
                "Set SLACK_BOT_TOKEN in ~/.jarvis/cloud-keys.env. "
                "Real sends require explicit authorization per message. "
                "external_send is permanently blocked without per-request approval."
            ),
            fallback_behavior="Dry-run message plans only. No real sends.",
        ),
        ConnectorRecord(
            connector_id="telegram",
            display_name="Telegram",
            credential_env_vars=["TELEGRAM_BOT_TOKEN"],
            required_oauth_scopes=[],
            dry_run_actions=[
                "draft_message_plan",
                "list_chats_plan",
            ],
            live_actions_blocked_until=(
                "TELEGRAM_BOT_TOKEN configured AND Bryan authorizes per-message sends. "
                "Real sends are a hard-gated external_send action."
            ),
            implementation_status="available",
            credentials_status="BLOCKED_CREDENTIALS",
            authorization_status="BLOCKED_USER_AUTHORIZATION",
            safety_status="BLOCKED_SAFETY",
            bryan_action=(
                "Set TELEGRAM_BOT_TOKEN in ~/.jarvis/cloud-keys.env. "
                "Authorize per-message sends explicitly."
            ),
            fallback_behavior="Dry-run message plans only.",
        ),
        ConnectorRecord(
            connector_id="github",
            display_name="GitHub",
            credential_env_vars=["GITHUB_TOKEN"],
            required_oauth_scopes=[
                "repo:read",
                "issues:write",
                "pull_requests:write",
            ],
            dry_run_actions=[
                "list_repos_plan",
                "search_issues_plan",
                "draft_pr_plan",
                "list_notifications_plan",
            ],
            live_actions_blocked_until=(
                "GITHUB_TOKEN configured AND Bryan authorizes GitHub write operations."
            ),
            implementation_status="available",
            credentials_status="BLOCKED_CREDENTIALS",
            authorization_status="BLOCKED_USER_AUTHORIZATION",
            safety_status="safe",
            bryan_action=(
                "Set GITHUB_TOKEN in ~/.jarvis/cloud-keys.env. "
                "Read-only actions available after token configured. "
                "Write actions require per-operation authorization."
            ),
            fallback_behavior="Dry-run PR/issue plans only. No real writes.",
        ),
        ConnectorRecord(
            connector_id="gdrive",
            display_name="Google Drive",
            credential_env_vars=["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"],
            required_oauth_scopes=[
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/drive.file",
            ],
            dry_run_actions=[
                "list_files_plan",
                "search_files_plan",
                "download_file_plan",
            ],
            live_actions_blocked_until=(
                "GOOGLE_OAUTH_CLIENT_ID configured AND Bryan authorizes Drive connector."
            ),
            implementation_status="available",
            credentials_status="BLOCKED_CREDENTIALS",
            authorization_status="BLOCKED_USER_AUTHORIZATION",
            safety_status="safe",
            bryan_action=(
                "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET "
                "in ~/.jarvis/cloud-keys.env, then authorize: jarvis connect gdrive"
            ),
            fallback_behavior="Dry-run file listing plans only.",
        ),
    ]
    for rec in records:
        _CONNECTOR_REGISTRY[rec.connector_id] = rec


_build_registry()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_connector_record(connector_id: str) -> Optional[ConnectorRecord]:
    """Return the ConnectorRecord for a given connector, or None."""
    return _CONNECTOR_REGISTRY.get(connector_id)


def all_connector_records() -> List[ConnectorRecord]:
    """Return all registered connector records."""
    return list(_CONNECTOR_REGISTRY.values())


def get_connector_status_summary() -> Dict[str, Any]:
    """Return a structured summary of all connectors for doctor/status surfaces."""
    records = all_connector_records()
    by_status: Dict[str, List[str]] = {}
    for rec in records:
        s = rec.overall_status()
        by_status.setdefault(s, []).append(rec.connector_id)
    return {
        "total_connectors": len(records),
        "by_status": by_status,
        "connectors": [rec.to_dict() for rec in records],
    }


def plan_connector_action(
    connector_id: str,
    action: str,
) -> ConnectorDryRunPlan:
    """Produce a dry-run action plan for a connector action.

    Never executes live. Returns a structured plan with required
    credentials, scopes, and steps.
    """
    rec = _CONNECTOR_REGISTRY.get(connector_id)
    if rec is None:
        return ConnectorDryRunPlan(
            connector_id=connector_id,
            action=action,
            status="blocked",
            blocked_reason=f"Connector '{connector_id}' not registered.",
            plan_steps=[],
            required_credentials=[],
            required_scopes=[],
            estimated_safety="unknown",
            approval_required=True,
        )

    overall = rec.overall_status()
    if overall in ("BLOCKED_SAFETY", "BLOCKED_IMPLEMENTATION"):
        return ConnectorDryRunPlan(
            connector_id=connector_id,
            action=action,
            status="blocked",
            blocked_reason=f"{overall}: {rec.live_actions_blocked_until}",
            plan_steps=[],
            required_credentials=rec.credential_env_vars,
            required_scopes=rec.required_oauth_scopes,
            estimated_safety="blocked",
            approval_required=True,
        )

    # Produce a dry-run plan even if credentials/authorization missing
    plan_steps = [
        f"[DRY-RUN] Check {action} is in connector's allowed_actions",
        f"[DRY-RUN] Verify credentials: {', '.join(rec.credential_env_vars) or 'none required'}",
        f"[DRY-RUN] Request scopes: {', '.join(rec.required_oauth_scopes) or 'none required'}",
        f"[DRY-RUN] Execute {action} on {rec.display_name} (live execution blocked until authorized)",
        f"[DRY-RUN] Report result; no real data modified",
    ]

    return ConnectorDryRunPlan(
        connector_id=connector_id,
        action=action,
        status="dry_run_plan",
        blocked_reason=(
            f"Live execution blocked: {rec.live_actions_blocked_until}"
            if overall != "dry_run_available" else None
        ),
        plan_steps=plan_steps,
        required_credentials=rec.credential_env_vars,
        required_scopes=rec.required_oauth_scopes,
        estimated_safety="requires_approval" if rec.safety_status == "BLOCKED_SAFETY" else "safe",
        approval_required=(rec.safety_status == "BLOCKED_SAFETY" or
                           rec.authorization_status == "BLOCKED_USER_AUTHORIZATION"),
    )


# ---------------------------------------------------------------------------
# Connector auth manager classification (explicit, not combined)
# ---------------------------------------------------------------------------

def get_connector_auth_manager_classification() -> Dict[str, Any]:
    """Return the exact four-way blocker classification for connector_auth_manager.

    Follows sprint rule: split clearly into implementation/credentials/
    authorization/safety — do not combine into vague language.
    """
    return {
        "manager_id": "connector_auth_manager",
        "overall_status": "STATUS_INACTIVE",
        "blockers": {
            "BLOCKED_IMPLEMENTATION": {
                "present": True,
                "detail": "No connector_auth_worker implementations registered and active.",
                "bryan_action": "No Bryan action can unblock this alone — code change required.",
                "resolved_when": "At least one connector_auth_worker registered with STATUS_ACTIVE.",
            },
            "BLOCKED_CREDENTIALS": {
                "present": True,
                "detail": (
                    "OAuth tokens and connector API keys not configured. "
                    "Missing: GOOGLE_OAUTH_CLIENT_ID, SLACK_BOT_TOKEN, TELEGRAM_BOT_TOKEN, "
                    "GITHUB_TOKEN."
                ),
                "bryan_action": (
                    "Configure connector credentials in ~/.jarvis/cloud-keys.env: "
                    "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, SLACK_BOT_TOKEN, "
                    "TELEGRAM_BOT_TOKEN, GITHUB_TOKEN."
                ),
                "resolved_when": "Credentials present for at least one connector.",
            },
            "BLOCKED_SAFETY": {
                "present": True,
                "detail": (
                    "access_live_secrets and rotate_credentials are permanently blocked "
                    "in blocked_action_types. This is intentional — live secret access "
                    "via connector_auth_manager is a hard-gated action."
                ),
                "bryan_action": "None — intentional permanent block.",
                "resolved_when": "Never — intentional safety policy.",
            },
            "BLOCKED_USER_AUTHORIZATION": {
                "present": False,
                "detail": (
                    "Authorization not yet relevant because BLOCKED_IMPLEMENTATION "
                    "and BLOCKED_CREDENTIALS are unresolved first."
                ),
                "bryan_action": (
                    "After BLOCKED_IMPLEMENTATION and BLOCKED_CREDENTIALS resolved: "
                    "explicitly authorize connector activation via jarvis connect <connector>."
                ),
                "resolved_when": (
                    "BLOCKED_IMPLEMENTATION and BLOCKED_CREDENTIALS resolved, "
                    "then Bryan explicitly authorizes each connector."
                ),
            },
        },
        "does_not_block_core_runtime": True,
        "dry_run_available": True,
        "note": (
            "connector_auth_manager STATUS_INACTIVE for two primary reasons: "
            "(1) no workers assigned (BLOCKED_IMPLEMENTATION), "
            "(2) live secret access permanently blocked (BLOCKED_SAFETY). "
            "Credentials are also missing (BLOCKED_CREDENTIALS). "
            "Dry-run connector planning is available via plan_connector_action()."
        ),
    }


__all__ = [
    "ConnectorRecord",
    "ConnectorDryRunPlan",
    "get_connector_record",
    "all_connector_records",
    "get_connector_status_summary",
    "plan_connector_action",
    "get_connector_auth_manager_classification",
]
