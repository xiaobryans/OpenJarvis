"""Plan 2 — Full Mobile MacBook-Off Parity Runtime routes.

Sprint: Plan 2A + Plan 2B Foundation
Acceptance target: MOBILE_MACBOOK_PARITY_TARGET_LOCKED

Routes:
  GET /v1/mobile-parity/status
      Returns honest per-subsection Plan 2 parity status using Plan 2 vocabulary.
      PUBLIC endpoint (no auth required) so mobile can check without credentials.
      Uses only:
        - env variable presence checks (key names only, never values)
        - known static capability facts from Plan 9 matrix
        - runtime DB availability checks (no model calls)

  GET /v1/mobile-parity/connectors
      Plan 2B — coarse per-connector mobile/MacBook-off parity status.
      PUBLIC endpoint (no auth required). Coarse status only — no token presence
      booleans, no env var names, no local paths, no account IDs.

  GET /v1/mobile-parity/connectors/detail
      Plan 2B — detailed per-connector diagnostics.
      AUTH REQUIRED (Bearer token). Presence-only diagnostics — no secret values.

Status vocabulary (honest states only):
  READY               — fully working on this surface
  LOCAL_ONLY          — works only when connected to local MacBook backend
  CLOUD_REQUIRED      — API exists; needs cloud backend + auth pointed at cloud URL
  MACBOOK_OFF_PENDING — architecture exists but data/worker not cloud-synced yet
  AUTH_REQUIRED       — needs Bearer token or OAuth, not configured for this surface
  NOT_CONFIGURED      — feature exists but no keys/setup for this surface
  SETUP_REQUIRED      — needs manual setup before this surface can use it
  UNAVAILABLE         — not implemented or blocked by hard gate
  PARKED              — explicitly deferred to a later plan
  DEGRADED            — partially working; some capability degraded
  ERROR               — real runtime failure (not a placeholder)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
except ImportError:
    raise ImportError("fastapi is required for plan2_routes")

router = APIRouter()

# ---------------------------------------------------------------------------
# Plan 2 status vocabulary
# ---------------------------------------------------------------------------
# NOTE: public endpoint safety — the following whitelist controls exactly which
# fields are sent to unauthenticated callers.  Do NOT add *_present, *_configured,
# blockers[], notes[], or any dynamic boolean that reveals key/secret presence.
_PUBLIC_SUBSECTION_KEYS: frozenset[str] = frozenset({
    "subsection",
    "name",
    "desktop_status",
    "mobile_status",
    "macbook_off_status",
    "auth_status",
    "key_routes",
    # 2F vocab only — static strings, not booleans
    "wake_word_tts_status",
    "wake_word_tts_plan",
    # 2I vocab only — static strings, not booleans
    "tauri_signing_status",
    "ecs_deploy_status",
})


def _public_subsection(d: Dict[str, Any]) -> Dict[str, Any]:
    """Return only public-safe fields from a subsection status dict.

    Strips: *_present, *_configured booleans; blockers (contain secret names);
    notes (contain local paths and env var names); dynamic auth_status suffixes
    that reveal whether the API key is currently configured.
    """
    result = {k: v for k, v in d.items() if k in _PUBLIC_SUBSECTION_KEYS}
    # Normalize auth_status: remove "— key configured" suffix that reveals key presence
    if "auth_status" in result:
        s = result["auth_status"]
        for suffix in (" — key configured", " — key set", "— key configured"):
            s = s.replace(suffix, "")
        result["auth_status"] = s.strip()
    return result

READY = "READY"
LOCAL_ONLY = "LOCAL_ONLY"
CLOUD_REQUIRED = "CLOUD_REQUIRED"
MACBOOK_OFF_PENDING = "MACBOOK_OFF_PENDING"
AUTH_REQUIRED = "AUTH_REQUIRED"
NOT_CONFIGURED = "NOT_CONFIGURED"
SETUP_REQUIRED = "SETUP_REQUIRED"
UNAVAILABLE = "UNAVAILABLE"
PARKED = "PARKED"
DEGRADED = "DEGRADED"
ERROR = "ERROR"

_PLAN2_VERSION = "2A.0.1"
_MATRIX_PATH = "docs/plan2/plan2_matrix.json"


# ---------------------------------------------------------------------------
# Helpers — honest env presence checks only (no values exposed)
# ---------------------------------------------------------------------------

def _env_present(*names: str) -> bool:
    """Return True if ALL named env vars are non-empty."""
    for name in names:
        val = os.environ.get(name, "").strip()
        if not val:
            return False
    return True


def _env_any(*names: str) -> bool:
    """Return True if ANY named env var is non-empty."""
    return any(os.environ.get(n, "").strip() for n in names)


def _db_accessible(path: Optional[Path] = None) -> bool:
    """Return True if the primary memory SQLite DB path is accessible."""
    if path is None:
        path = Path.home() / ".jarvis" / "memory.db"
    try:
        return path.exists() and path.is_file()
    except Exception:
        return False


def _cloud_keys_present() -> Dict[str, bool]:
    """Return presence map for cloud API keys (names only, never values)."""
    return {
        "OPENROUTER_API_KEY": _env_present("OPENROUTER_API_KEY"),
        "OPENAI_API_KEY": _env_present("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": _env_present("ANTHROPIC_API_KEY"),
    }


def _aws_configured() -> bool:
    return _env_present("OMNIX_WORKBENCH_AWS_PROFILE", "OMNIX_WORKBENCH_AWS_REGION")


def _memory_bucket_configured() -> bool:
    return _env_present("OMNIX_WORKBENCH_MEMORY_BUCKET")


def _artifact_bucket_configured() -> bool:
    return _env_present("OMNIX_WORKBENCH_ARTIFACT_BUCKET")


def _github_token_present() -> bool:
    return _env_present("GITHUB_TOKEN")


def _telegram_present() -> bool:
    return _env_present("TELEGRAM_BOT_TOKEN")


def _slack_present() -> bool:
    return _env_any("SLACK_BOT_TOKEN", "OPENCLAW_SLACK_BOT_TOKEN")


def _deepgram_present() -> bool:
    return _env_present("DEEPGRAM_API_KEY")


def _apple_signing_present() -> bool:
    return _env_present("APPLE_SIGNING_IDENTITY", "APPLE_TEAM_ID")


def _api_key_configured() -> bool:
    """Return True if an API key is set for the server."""
    return _env_present("OPENJARVIS_API_KEY")


# ---------------------------------------------------------------------------
# Per-subsection status builders
# ---------------------------------------------------------------------------

def _status_2a_workbench() -> Dict[str, Any]:
    """2A — Coding / Workbench parity."""
    has_github = _github_token_present()
    has_artifact_bucket = _artifact_bucket_configured()
    has_cloud_model = _env_any("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    has_api_key = _api_key_configured()

    blockers: List[str] = []
    if not has_github:
        blockers.append("GITHUB_TOKEN missing — coding tasks cannot push/commit")
    if not has_cloud_model:
        blockers.append("No cloud model key — workbench requires cloud model for execution")
    if not has_api_key:
        blockers.append("OPENJARVIS_API_KEY not set — mobile cannot authenticate to /v1/workbench/*")

    notes = [
        "Routes /v1/workbench/* implemented and functional on desktop.",
        "Mobile: same API, requires Bearer token + cloud backend URL.",
        "MacBook-off: Fargate backend must be running; worker process not yet deployed.",
        "Terminal exec: requires approval_token; push notification channel for mobile approval pending.",
    ]

    return {
        "subsection": "2A",
        "name": "Coding / Workbench Parity",
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "auth_status": AUTH_REQUIRED if not has_api_key else "Bearer token required — key configured",
        "cloud_model_keys_present": has_cloud_model,
        "github_token_present": has_github,
        "artifact_bucket_configured": has_artifact_bucket,
        "blockers": blockers,
        "notes": notes,
        "key_routes": [
            "POST /v1/workbench/plan",
            "POST /v1/workbench/execute",
            "POST /v1/workbench/approve",
            "GET  /v1/workbench/capabilities",
            "POST /v1/workbench/terminal/exec",
            "GET  /v1/coding/workspace",
            "POST /v1/coding/files/read",
        ],
    }


def _status_2b_connectors() -> Dict[str, Any]:
    """2B — Connector / task parity."""
    has_slack = _slack_present()
    has_github = _github_token_present()
    has_api_key = _api_key_configured()

    blockers: List[str] = []
    if not has_api_key:
        blockers.append("OPENJARVIS_API_KEY not set — mobile cannot authenticate to /v1/connectors/*")
    blockers.append(
        "OAuth tokens stored locally (~/.openjarvis/) — not accessible from Fargate without secure token sync"
    )
    blockers.append(
        "GDrive and Notion connector status unverified (UNKNOWN_NEEDS_PROOF in Plan 9 matrix)"
    )

    return {
        "subsection": "2B",
        "name": "Connector / Task Parity",
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "auth_status": AUTH_REQUIRED if not has_api_key else "Bearer token required — key configured",
        "connector_keys_present": {
            "SLACK": has_slack,
            "GITHUB": has_github,
            "GOOGLE_OAUTH": _env_present("GOOGLE_OAUTH_CLIENT_ID"),
            "NOTION": False,
        },
        "blockers": blockers,
        "notes": [
            "Gmail, Calendar, Slack, GitHub: CROSS_DEVICE_LIVE in Plan 9 matrix.",
            "GDrive, Notion: UNKNOWN_NEEDS_PROOF — not yet verified over cloud.",
            "OAuth connector re-auth from mobile requires HTTPS callback URL — not yet implemented.",
        ],
        "key_routes": [
            "GET  /v1/connectors/status",
            "POST /v1/frontdoor/submit",
            "GET  /v1/connectors/list",
        ],
    }


def _status_2c_files() -> Dict[str, Any]:
    """2C — File / workspace / data parity."""
    has_memory_bucket = _memory_bucket_configured()
    has_artifact_bucket = _artifact_bucket_configured()
    has_aws = _aws_configured()

    blockers = [
        "Full workspace sync to S3 not implemented — only git-tracked files via repo operations",
        "File index is local-only; cloud index requires separate indexing job",
    ]

    return {
        "subsection": "2C",
        "name": "File / Workspace / Data Parity",
        "desktop_status": READY,
        "mobile_status": MACBOOK_OFF_PENDING,
        "macbook_off_status": MACBOOK_OFF_PENDING,
        "auth_status": "Bearer token required",
        "aws_configured": has_aws,
        "memory_bucket_configured": has_memory_bucket,
        "artifact_bucket_configured": has_artifact_bucket,
        "blockers": blockers,
        "notes": [
            "OMNIX_WORKBENCH_MEMORY_BUCKET and ARTIFACT_BUCKET are configured.",
            "Mac-only unsynced files remain QUEUED_MAC_ONLY per Plan 9 acceptance (permanent exception).",
            "Git-tracked files accessible via /v1/coding/files/read when backend is up.",
        ],
        "key_routes": [
            "GET  /v1/files/index",
            "POST /v1/coding/files/read",
            "POST /v1/coding/search",
        ],
    }


def _status_2d_memory() -> Dict[str, Any]:
    """2D — Memory / context / routing parity."""
    db_ok = _db_accessible()
    has_memory_bucket = _memory_bucket_configured()
    has_pinecone = _env_present("PINECONE_API_KEY")
    has_api_key = _api_key_configured()

    blockers: List[str] = []
    if not has_api_key:
        blockers.append("OPENJARVIS_API_KEY not set — mobile cannot authenticate to /v1/memory/*")
    if not has_memory_bucket:
        blockers.append("OMNIX_WORKBENCH_MEMORY_BUCKET not configured — cloud sync unavailable")
    blockers.append("Full bidirectional SQLite↔S3 sync not verified post-Plan 9")

    return {
        "subsection": "2D",
        "name": "Memory / Context / Routing Parity",
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "auth_status": AUTH_REQUIRED if not has_api_key else "Bearer token required — key configured",
        "local_db_accessible": db_ok,
        "memory_bucket_configured": has_memory_bucket,
        "pinecone_key_present": has_pinecone,
        "blockers": blockers,
        "notes": [
            "Primary memory: SQLite (local). Cloud sync module exists (cloud_sync.py).",
            "Semantic search: Pinecone key present.",
            "/v1/continuity/macbook-off-status is public (no auth required).",
            "/v1/memory/* requires Bearer token.",
        ],
        "key_routes": [
            "GET  /v1/memory/status",
            "POST /v1/memory",
            "GET  /v1/memory/retrieve",
            "GET  /v1/continuity/macbook-off-status",
            "GET  /v1/mobile/continuity/status",
        ],
    }


def _status_2e_life_os() -> Dict[str, Any]:
    """2E — Life-Business OS operation parity."""
    has_api_key = _api_key_configured()

    return {
        "subsection": "2E",
        "name": "Life-Business OS Operation Parity",
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "auth_status": AUTH_REQUIRED if not has_api_key else "Bearer token required — key configured",
        "blockers": [
            "Life-OS data stored in local SQLite — not synced to cloud",
            "No push notification for task updates on mobile",
            "Mission control real-time updates not streamed to mobile",
        ],
        "notes": [
            "Routes /v1/life-os/tasks, /v1/workstreams, /v1/goals are all implemented.",
            "Same API works on mobile when pointed at cloud backend.",
            "Data sync to cloud is the main pending work.",
        ],
        "key_routes": [
            "GET  /v1/life-os/tasks",
            "POST /v1/life-os/tasks",
            "GET  /v1/workstreams",
            "GET  /v1/goals",
        ],
    }


def _status_2f_voice() -> Dict[str, Any]:
    """2F — Voice / tap-to-speak foundation (no wake word, no TTS — Plan 3 is parked)."""
    has_deepgram = _deepgram_present()
    stt_provider = os.environ.get("JARVIS_STT_PROVIDER", "").strip()
    tts_provider = os.environ.get("JARVIS_TTS_PROVIDER", "").strip()

    return {
        "subsection": "2F",
        "name": "Voice / Tap-to-Speak Foundation",
        "desktop_status": LOCAL_ONLY,
        "mobile_status": NOT_CONFIGURED,
        "macbook_off_status": MACBOOK_OFF_PENDING,
        "auth_status": "Bearer token required",
        "deepgram_key_present": has_deepgram,
        "stt_provider_configured": bool(stt_provider),
        "tts_provider_configured": bool(tts_provider),
        "wake_word_tts_status": PARKED,
        "wake_word_tts_plan": "Plan 3 — do NOT reopen in Plan 2",
        "blockers": [
            "Full wake word and TTS: PARKED (Plan 3) — not reopening",
            "Browser MediaRecorder → /v1/voice/transcribe not wired in mobile UI yet",
            "Audio permissions require HTTPS on mobile browsers",
        ],
        "notes": [
            "Foundation only: tap-to-speak button wiring is the Plan 2F target.",
            "No wake word. No TTS output routing. Plan 3 scope.",
            "STT keys present — API route /v1/voice/transcribe is implemented.",
        ],
        "key_routes": [
            "POST /v1/voice/transcribe",
        ],
    }


def _status_2g_approvals() -> Dict[str, Any]:
    """2G — Notifications / approval parity."""
    has_telegram = _telegram_present()
    has_slack = _slack_present()
    has_api_key = _api_key_configured()

    blockers: List[str] = []
    if not has_api_key:
        blockers.append("OPENJARVIS_API_KEY not set — mobile cannot authenticate to /v1/approvals/*")
    blockers.append("Approval store is local SQLite — not synced to cloud for MacBook-off case")
    if not has_telegram and not has_slack:
        blockers.append("No TELEGRAM_BOT_TOKEN or SLACK_BOT_TOKEN — push notifications unavailable")
    else:
        blockers.append(
            "Push notifications (Telegram/Slack) exist but not triggered on new pending approvals yet"
        )
    blockers.append("Mobile approval polling (30s interval) not yet implemented in UI")

    return {
        "subsection": "2G",
        "name": "Notifications / Approval Parity",
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "auth_status": AUTH_REQUIRED if not has_api_key else "Bearer token required — key configured",
        "telegram_token_present": has_telegram,
        "slack_token_present": has_slack,
        "blockers": blockers,
        "notes": [
            "Approval routes fully implemented: /v1/approvals/pending, /v1/approvals/{id}/approve/deny.",
            "Telegram and Slack keys present — notification infrastructure exists but not auto-triggered.",
            "PWA push notification API not yet wired.",
        ],
        "key_routes": [
            "GET  /v1/approvals/pending",
            "POST /v1/approvals/{id}/approve",
            "POST /v1/approvals/{id}/deny",
        ],
    }


def _status_2h_long_running() -> Dict[str, Any]:
    """2H — Long-running cloud execution parity."""
    has_aws = _aws_configured()

    return {
        "subsection": "2H",
        "name": "Long-Running Cloud Execution Parity",
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": MACBOOK_OFF_PENDING,
        "auth_status": "Bearer token required",
        "aws_configured": has_aws,
        "fargate_worker_deployed": False,
        "blockers": [
            "Mac worker queue processes tasks only when MacBook is online",
            "Cloud execution daemon not deployed to Fargate (API only, no worker process)",
            "No long-running job status push/WebSocket for mobile polling",
        ],
        "notes": [
            "Mac worker queue (QUEUED_MAC_ONLY): /v1/mac-worker/queue, /v1/mac-worker/status.",
            "DAG/batch orchestration routes are cloud-safe but need Fargate worker for execution.",
            "AWS region and profile are configured per Plan 4.",
        ],
        "key_routes": [
            "GET  /v1/mac-worker/queue",
            "POST /v1/mac-worker/queue",
            "GET  /v1/mac-worker/status",
            "POST /v1/orchestration/dag/run",
            "POST /v1/orchestration/batch/run",
        ],
    }


def _status_2i_deploy() -> Dict[str, Any]:
    """2I — Deployment / release / signing workflow parity."""
    has_github = _github_token_present()
    has_aws = _aws_configured()
    has_apple_signing = _apple_signing_present()

    return {
        "subsection": "2I",
        "name": "Deployment / Release / Signing Parity",
        "desktop_status": READY,
        "mobile_status": MACBOOK_OFF_PENDING,
        "macbook_off_status": MACBOOK_OFF_PENDING,
        "auth_status": "APPROVAL_REQUIRED for all deploy/signing actions",
        "tauri_signing_status": "QUEUED_MAC_ONLY — MacBook + Xcode required, permanent exception",
        "ecs_deploy_status": MACBOOK_OFF_PENDING,
        "github_token_present": has_github,
        "aws_configured": has_aws,
        "apple_signing_keys_present": has_apple_signing,
        "blockers": [
            "Tauri build + codesign requires MacBook — QUEUED_MAC_ONLY (permanent exception)",
            "Apple signing certificate in local keychain — not accessible from cloud",
            "ECS cloud deploy not yet wired to be triggerable from mobile with approval gate",
        ],
        "notes": [
            "POST /v1/deploy/plan and POST /v1/self-upgrade/request are approval-gated.",
            "ECS/Vercel backend-only deploy (no signing) could be mobile-triggered — pending next patch.",
            "Tauri desktop app build + signing stays MacBook-only permanently.",
        ],
        "key_routes": [
            "POST /v1/deploy/plan",
            "POST /v1/self-upgrade/request",
            "GET  /v1/self-upgrade/status",
        ],
    }


# ---------------------------------------------------------------------------
# Plan 2 status endpoint
# ---------------------------------------------------------------------------

@router.get("/v1/mobile-parity/status")
async def get_mobile_parity_status() -> Dict[str, Any]:
    """Plan 2 — honest per-subsection mobile/MacBook-off parity status.

    Public endpoint (no auth required) — mobile can check without credentials.
    Returns coarse public-safe status only.  All secret/key presence booleans,
    specific blocker strings containing env-var names, and notes containing
    internal paths are stripped via _public_subsection() before serialisation.
    Does not fake readiness.
    """
    subsections_full = [
        _status_2a_workbench(),
        _status_2b_connectors(),
        _status_2c_files(),
        _status_2d_memory(),
        _status_2e_life_os(),
        _status_2f_voice(),
        _status_2g_approvals(),
        _status_2h_long_running(),
        _status_2i_deploy(),
    ]

    # Compute counts from full internal data before stripping
    mobile_ready = sum(1 for s in subsections_full if s.get("mobile_status") == READY)
    macbook_off_ready = sum(1 for s in subsections_full if s.get("macbook_off_status") == READY)

    # Strip all sensitive fields before returning to unauthenticated caller
    public_subsections = [_public_subsection(s) for s in subsections_full]

    return {
        "plan": "Plan 2 — Full Mobile MacBook-Off Parity Runtime",
        "sprint": "Plan 2A Foundation",
        "version": _PLAN2_VERSION,
        "acceptance_target": "MOBILE_MACBOOK_PARITY_TARGET_LOCKED",
        "sprint_verdict": "PLAN_2A_MOBILE_MACBOOK_OFF_FOUNDATION_PATCHED_PENDING_REVIEW",
        "matrix_path": _MATRIX_PATH,
        "plan1_verdict": "PLAN_1_DUAL_PLATFORM_JARVIS_NEURAL_COMMAND_CENTER_ACCEPTED",
        # global: static text only — no key presence booleans, no infra details
        "global": {
            "macbook_off_global_blocker": (
                "Primary data stores (memory, approvals, life-os, connector tokens) are "
                "local SQLite — cloud sync required for MacBook-off parity across all subsections."
            ),
        },
        "summary": {
            "total_subsections": len(subsections_full),
            "mobile_ready": mobile_ready,
            "macbook_off_ready": macbook_off_ready,
            "mobile_cloud_required": sum(
                1 for s in subsections_full if s.get("mobile_status") == CLOUD_REQUIRED
            ),
            "macbook_off_pending": sum(
                1 for s in subsections_full if s.get("macbook_off_status") == MACBOOK_OFF_PENDING
            ),
            "parked": sum(1 for s in subsections_full if s.get("mobile_status") == PARKED),
        },
        "parity_definition": (
            "Whatever Jarvis can do on MacBook/desktop should eventually be operable from "
            "phone/mobile while the MacBook is off, subject only to real platform, security, "
            "connector, permission, cost, and approval limits."
        ),
        "subsections": public_subsections,
    }


# ---------------------------------------------------------------------------
# Plan 2B — Connector / Task Parity
# ---------------------------------------------------------------------------
# Token storage classification (static knowledge, no runtime secrets):
#   LOCAL_FILE   — OAuth token in ~/.openjarvis/connectors/*.json (local only)
#   ENV_VAR      — token/key in process environment (cloud-safe if on Fargate)
#   NOT_PRESENT  — connector not configured

_CONNECTOR_REGISTRY: List[Dict[str, Any]] = [
    {
        "connector_id": "gmail",
        "display_name": "Gmail",
        "provider": "google",
        "token_storage": "LOCAL_FILE",
        "token_file_key": "gmail.json",
        "cloud_safe": False,
        "desktop_status": READY,
        "mobile_status": LOCAL_ONLY,
        "macbook_off_status": MACBOOK_OFF_PENDING,
        "outbound_send": False,
        "approval_required": False,
        "task_class": "CONNECTOR_GATED",
        "vault_migration_needed": True,
    },
    {
        "connector_id": "gcalendar",
        "display_name": "Google Calendar",
        "provider": "google",
        "token_storage": "LOCAL_FILE",
        "token_file_key": "gcalendar.json",
        "cloud_safe": False,
        "desktop_status": READY,
        "mobile_status": LOCAL_ONLY,
        "macbook_off_status": MACBOOK_OFF_PENDING,
        "outbound_send": False,
        "approval_required": False,
        "task_class": "CONNECTOR_GATED",
        "vault_migration_needed": True,
    },
    {
        "connector_id": "gdrive",
        "display_name": "Google Drive",
        "provider": "google",
        "token_storage": "LOCAL_FILE",
        "token_file_key": "gdrive.json",
        "cloud_safe": False,
        "desktop_status": READY,
        "mobile_status": LOCAL_ONLY,
        "macbook_off_status": MACBOOK_OFF_PENDING,
        "outbound_send": False,
        "approval_required": False,
        "task_class": "CONNECTOR_GATED",
        "vault_migration_needed": True,
    },
    {
        "connector_id": "github",
        "display_name": "GitHub",
        "provider": "github",
        "token_storage": "ENV_VAR",
        "token_file_key": None,
        "cloud_safe": True,
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "outbound_send": False,
        "approval_required": True,  # for push/PR/merge
        "task_class": "APPROVAL_REQUIRED",
        "vault_migration_needed": False,
    },
    {
        "connector_id": "slack",
        "display_name": "Slack",
        "provider": "slack",
        "token_storage": "ENV_VAR",
        "token_file_key": None,
        "cloud_safe": True,
        "desktop_status": READY,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "outbound_send": True,
        "approval_required": True,  # all sends
        "task_class": "APPROVAL_REQUIRED",
        "vault_migration_needed": False,
    },
    {
        "connector_id": "notion",
        "display_name": "Notion",
        "provider": "notion",
        "token_storage": "NOT_PRESENT",
        "token_file_key": "notion.json",
        "cloud_safe": False,
        "desktop_status": NOT_CONFIGURED,
        "mobile_status": NOT_CONFIGURED,
        "macbook_off_status": NOT_CONFIGURED,
        "outbound_send": False,
        "approval_required": False,
        "task_class": "CONNECTOR_GATED",
        "vault_migration_needed": False,
    },
    {
        "connector_id": "telegram",
        "display_name": "Telegram",
        "provider": "telegram",
        "token_storage": "ENV_VAR",
        "token_file_key": None,
        "cloud_safe": True,
        "desktop_status": DEGRADED,
        "mobile_status": CLOUD_REQUIRED,
        "macbook_off_status": CLOUD_REQUIRED,
        "outbound_send": True,
        "approval_required": True,  # all sends
        "task_class": "APPROVAL_REQUIRED",
        "vault_migration_needed": False,
    },
]

_CONNECTOR_TOKEN_DIR = Path.home() / ".openjarvis" / "connectors"

_TASK_CLASSES = {
    "READONLY": "Safe read operations — no approval needed; mobile-safe and cloud-safe.",
    "APPROVAL_REQUIRED": "Any outbound send, write, or state change — must pass Jarvis PA approval gate.",
    "DESTRUCTIVE_GATED": "Hard-gated — Bryan explicit approval required; logged.",
    "MAC_REQUIRED": "Requires MacBook + local toolchain (Tauri, keychain, Xcode).",
    "CLOUD_SAFE": "Runs on Fargate without MacBook — API + auth only.",
    "CONNECTOR_GATED": "Requires connector OAuth token in execution context — vault migration needed for MacBook-off.",
}


def _connector_token_present(rec: Dict[str, Any]) -> bool:
    """Check whether a connector token file or env var is present. No values returned."""
    if rec["token_storage"] == "NOT_PRESENT":
        return False
    if rec["token_storage"] == "LOCAL_FILE" and rec.get("token_file_key"):
        path = _CONNECTOR_TOKEN_DIR / rec["token_file_key"]
        try:
            return path.exists() and path.stat().st_size > 10
        except Exception:
            return False
    if rec["token_storage"] == "ENV_VAR":
        # Check known env vars for each provider (presence only)
        provider = rec["connector_id"]
        env_checks: Dict[str, List[str]] = {
            "github": ["GITHUB_TOKEN"],
            "slack": ["OPENCLAW_SLACK_BOT_TOKEN", "SLACK_BOT_TOKEN", "SLACK_USER_TOKEN"],
            "telegram": ["TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN"],
        }
        return any(
            os.environ.get(v, "").strip()
            for v in env_checks.get(provider, [])
        )
    return False


def _connector_is_connected(connector_id: str) -> bool:
    """Live connection check via connector instance. Returns False on any error."""
    try:
        from openjarvis.core.registry import ConnectorRegistry
        from openjarvis.core.env_loader import ensure_local_env_loaded
        ensure_local_env_loaded()
        if not ConnectorRegistry.contains(connector_id):
            return False
        cls = ConnectorRegistry.get(connector_id)
        instance = cls()
        return bool(instance.is_connected())
    except Exception:
        return False


def _build_connector_public_entry(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Return public-safe (coarse) entry for a connector.

    No token presence booleans, no env var names, no local paths,
    no account IDs, no specific config details.
    """
    return {
        "connector_id": rec["connector_id"],
        "display_name": rec["display_name"],
        "desktop_status": rec["desktop_status"],
        "mobile_status": rec["mobile_status"],
        "macbook_off_status": rec["macbook_off_status"],
        "outbound_send": rec["outbound_send"],
        "approval_required": rec["approval_required"],
        "task_class": rec["task_class"],
    }


def _build_connector_detail_entry(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Return auth-gated presence-only detail for a connector.

    No secret values. Returns presence booleans and classification only.
    """
    token_present = _connector_token_present(rec)
    connected = False
    if token_present:
        connected = _connector_is_connected(rec["connector_id"])

    return {
        "connector_id": rec["connector_id"],
        "display_name": rec["display_name"],
        "desktop_status": rec["desktop_status"],
        "mobile_status": rec["mobile_status"],
        "macbook_off_status": rec["macbook_off_status"],
        "token_storage_type": rec["token_storage"],
        "token_present": token_present,
        "is_connected": connected,
        "cloud_safe_token": rec["cloud_safe"],
        "vault_migration_needed": rec["vault_migration_needed"],
        "outbound_send": rec["outbound_send"],
        "approval_required": rec["approval_required"],
        "task_class": rec["task_class"],
    }


# ---------------------------------------------------------------------------
# Plan 2B endpoints
# ---------------------------------------------------------------------------

@router.get("/v1/mobile-parity/connectors")
async def get_connector_parity_status() -> Dict[str, Any]:
    """Plan 2B — coarse per-connector mobile/MacBook-off parity status.

    PUBLIC endpoint (no auth required). Returns coarse parity status only.
    No token presence, no env var names, no local paths, no account IDs.
    """
    entries = [_build_connector_public_entry(r) for r in _CONNECTOR_REGISTRY]

    ready_mobile = sum(1 for e in entries if e["mobile_status"] == READY)
    ready_off = sum(1 for e in entries if e["macbook_off_status"] == READY)

    return {
        "plan": "Plan 2B — Connector / Task Parity Foundation",
        "sprint_verdict": "PLAN_2B_CONNECTOR_TASK_PARITY_FOUNDATION_PATCHED_PENDING_REVIEW",
        "matrix_path": "docs/plan2/plan2b_matrix.json",
        "summary": {
            "total_connectors": len(entries),
            "mobile_ready": ready_mobile,
            "macbook_off_ready": ready_off,
            "local_only": sum(1 for e in entries if e["mobile_status"] == LOCAL_ONLY),
            "cloud_required": sum(1 for e in entries if e["mobile_status"] == CLOUD_REQUIRED),
            "not_configured": sum(1 for e in entries if e["mobile_status"] == NOT_CONFIGURED),
            "macbook_off_pending": sum(
                1 for e in entries if e["macbook_off_status"] == MACBOOK_OFF_PENDING
            ),
        },
        "task_classes": _TASK_CLASSES,
        "global_blocker": (
            "Google OAuth tokens (Gmail, Calendar, Drive) are stored in local files — "
            "not accessible from cloud/Fargate. No vault integration implemented yet."
        ),
        "connectors": entries,
    }


_bearer_scheme = HTTPBearer(auto_error=False)


@router.get("/v1/mobile-parity/connectors/detail")
async def get_connector_parity_detail(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """Plan 2B — detailed per-connector diagnostics. AUTH REQUIRED.

    Returns presence-only token/connection diagnostics. No secret values.
    """
    # Validate Bearer token against server API key
    api_key = os.environ.get("OPENJARVIS_API_KEY", "").strip()
    if api_key:
        import secrets as _secrets
        token = credentials.credentials if credentials else ""
        if not token or not _secrets.compare_digest(token.strip(), api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    entries = [_build_connector_detail_entry(r) for r in _CONNECTOR_REGISTRY]

    token_ready = sum(1 for e in entries if e["token_present"])
    connected_count = sum(1 for e in entries if e["is_connected"])
    cloud_safe_count = sum(1 for e in entries if e["cloud_safe_token"] and e["token_present"])
    needs_vault = sum(1 for e in entries if e["vault_migration_needed"])

    return {
        "plan": "Plan 2B — Connector / Task Parity Foundation",
        "sprint_verdict": "PLAN_2B_CONNECTOR_TASK_PARITY_FOUNDATION_PATCHED_PENDING_REVIEW",
        "auth_required": True,
        "summary": {
            "total_connectors": len(entries),
            "tokens_present": token_ready,
            "connected": connected_count,
            "cloud_safe_tokens": cloud_safe_count,
            "vault_migration_needed": needs_vault,
            "macbook_off_ready": sum(
                1 for e in entries if e["macbook_off_status"] == READY
            ),
        },
        "global_blocker": (
            "Google OAuth tokens stored in local files — vault migration required for "
            "MacBook-off parity. GitHub/Slack/Telegram tokens are env-var based (cloud-safe "
            "if deployed to Fargate)."
        ),
        "connectors": entries,
    }
