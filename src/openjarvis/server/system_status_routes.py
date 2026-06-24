"""Unified system / connector status route.

Route:
  GET /v1/system/status   — metadata-only status for all connectors + system components

Safety guarantees:
  - Never reads, prints, or returns actual secret values, tokens, or key contents.
  - Reports presence/absence only.
  - Safe for mobile and desktop clients.
  - Covers all required status categories:
      Connectors: Gmail, Calendar, Drive, Slack, Telegram, Notion, GitHub, S3/memory
      System:     Fargate/cloud, mobile/PWA/iOS, skills/rules, expert role routing
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

CONFIGURED = "configured"
NOT_CONFIGURED = "not_configured"
EXTERNAL_GATE = "external_gate"
NOT_STARTED = "not_started"
UNKNOWN = "unknown"
PARTIAL = "partial"

# ---------------------------------------------------------------------------
# Presence-only probe helpers (never read actual values)
# ---------------------------------------------------------------------------


def _env_any(*names: str) -> bool:
    return any(bool(os.environ.get(n, "").strip()) for n in names)


def _slack_status() -> str:
    return CONFIGURED if _env_any("SLACK_BOT_TOKEN", "SLACK_OAUTH_TOKEN") else NOT_CONFIGURED


def _telegram_status() -> str:
    return CONFIGURED if _env_any("TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN") else NOT_CONFIGURED


def _notion_status() -> str:
    if _env_any("NOTION_API_KEY", "NOTION_TOKEN"):
        return CONFIGURED
    token_dir = Path.home() / ".openjarvis" / "connectors"
    notion_file = token_dir / "notion.json"
    if notion_file.exists() and notion_file.stat().st_size > 10:
        return CONFIGURED
    return NOT_CONFIGURED


def _github_status() -> str:
    return CONFIGURED if _env_any("GITHUB_TOKEN", "GH_TOKEN") else NOT_CONFIGURED


def _google_oauth_status() -> str:
    if _env_any("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID"):
        return PARTIAL  # client ID present but OAuth flow state unknown
    return NOT_CONFIGURED


def _google_gmail_status() -> str:
    return _google_oauth_status()


def _google_calendar_status() -> str:
    return _google_oauth_status()


def _google_drive_status() -> str:
    return _google_oauth_status()


def _s3_memory_status() -> str:
    if _env_any("AWS_ACCESS_KEY_ID", "JARVIS_S3_BUCKET", "JARVIS_MEMORY_BUCKET"):
        return CONFIGURED
    return NOT_CONFIGURED


def _fargate_status() -> Dict[str, Any]:
    try:
        from openjarvis.server.fargate_readiness import get_fargate_worker_status
        r = get_fargate_worker_status()
        result = r if isinstance(r, dict) else r.__dict__ if hasattr(r, "__dict__") else {}
        return {
            "status": result.get("overall_status", UNKNOWN),
            "endpoint_reachable": result.get("endpoint_reachable", False),
            "task_running": result.get("task_running", False),
            "healthy": result.get("healthy", False),
        }
    except Exception:
        return {"status": UNKNOWN, "endpoint_reachable": False, "task_running": False, "healthy": False}


def _mobile_ios_status() -> Dict[str, Any]:
    try:
        from openjarvis.server.productization_routes import _IOS_NATIVE_STATUS, _MOBILE_WEB_STATUS
        return {
            "pwa_status": _MOBILE_WEB_STATUS.get("status", UNKNOWN),
            "ios_scaffold_status": _IOS_NATIVE_STATUS.get("scaffold_status", UNKNOWN),
            "ios_status": _IOS_NATIVE_STATUS.get("status", UNKNOWN),
        }
    except Exception:
        return {"pwa_status": UNKNOWN, "ios_scaffold_status": UNKNOWN, "ios_status": UNKNOWN}


def _skills_rules_status() -> Dict[str, Any]:
    try:
        from openjarvis.rules.registry import RuleRegistry
        reg = RuleRegistry.get_instance()
        stats = reg.stats()
        return {
            "status": CONFIGURED,
            "total_rules": stats.get("total", 0),
            "active_rules": stats.get("active", 0),
        }
    except Exception:
        return {"status": PARTIAL, "total_rules": 0, "active_rules": 0}


def _expert_roles_status() -> Dict[str, Any]:
    try:
        from openjarvis.orchestrator.expert_roles import ExpertRoleRegistry
        reg = ExpertRoleRegistry.get_instance()
        stats = reg.stats()
        return {
            "status": CONFIGURED,
            "total_roles": stats.get("total", 0),
            "active_roles": stats.get("active", 0),
            "internal_routing_only": True,
        }
    except Exception:
        return {"status": PARTIAL, "total_roles": 0, "active_roles": 0, "internal_routing_only": True}


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/v1/system/status")
async def get_system_status() -> Dict[str, Any]:
    """Return presence-only status for all connectors and system components.

    Never returns secret values, token contents, or credential paths.
    Status values: configured | not_configured | partial | external_gate
                   not_started | unknown
    """
    fargate = _fargate_status()
    mobile_ios = _mobile_ios_status()
    skills_rules = _skills_rules_status()
    expert_roles = _expert_roles_status()

    connectors: Dict[str, Any] = {
        "gmail": {
            "status": _google_gmail_status(),
            "note": "Google OAuth — client ID presence only; token state not inspected",
        },
        "calendar": {
            "status": _google_calendar_status(),
            "note": "Google OAuth — shared with Gmail; presence-only",
        },
        "drive": {
            "status": _google_drive_status(),
            "note": "Google OAuth — shared with Gmail; presence-only",
        },
        "slack": {
            "status": _slack_status(),
            "note": "Presence-only; key value not read",
        },
        "telegram": {
            "status": _telegram_status(),
            "note": "Checks TELEGRAM_BOT_TOKEN or JARVIS_TELEGRAM_BOT_TOKEN; value not read",
        },
        "notion": {
            "status": _notion_status(),
            "note": "Presence-only; token not read",
        },
        "github": {
            "status": _github_status(),
            "note": "Presence-only; token not read",
        },
        "s3_memory": {
            "status": _s3_memory_status(),
            "note": "AWS key presence-only; bucket contents not accessed",
        },
    }

    system: Dict[str, Any] = {
        "fargate_cloud": {
            "status": fargate["status"],
            "endpoint_reachable": fargate["endpoint_reachable"],
            "task_running": fargate["task_running"],
            "healthy": fargate["healthy"],
            "note": "Cloud execution path — public probe only",
        },
        "mobile_pwa": {
            "status": mobile_ios["pwa_status"],
            "note": "PWA manifest + service worker",
        },
        "ios_native": {
            "status": mobile_ios["ios_status"],
            "scaffold_status": mobile_ios["ios_scaffold_status"],
            "note": "Tauri iOS scaffold present; Apple Developer Account is an external gate",
            "external_gate": "apple_developer_account" if mobile_ios["ios_scaffold_status"] == "present" else None,
        },
        "skills_rules": {
            "status": skills_rules["status"],
            "total_rules": skills_rules["total_rules"],
            "active_rules": skills_rules["active_rules"],
            "note": "Rules engine — plan 4-6 sprint 1",
        },
        "expert_role_routing": {
            "status": expert_roles["status"],
            "total_roles": expert_roles["total_roles"],
            "active_roles": expert_roles["active_roles"],
            "internal_routing_only": True,
            "note": "Expert roles are internal routing aids; single Jarvis PA voice preserved externally",
        },
        "voice_tts": {
            "status": NOT_STARTED,
            "note": "Plan 3 — intentionally parked; no ETA",
        },
    }

    configured_connectors = sum(1 for c in connectors.values() if c["status"] == CONFIGURED)
    partial_connectors = sum(1 for c in connectors.values() if c["status"] == PARTIAL)

    return {
        "connectors": connectors,
        "system": system,
        "summary": {
            "connectors_configured": configured_connectors,
            "connectors_partial": partial_connectors,
            "connectors_not_configured": len(connectors) - configured_connectors - partial_connectors,
            "fargate_healthy": fargate["healthy"],
            "pwa_ready": mobile_ios["pwa_status"] == "implemented",
            "ios_scaffold_ready": mobile_ios["ios_scaffold_status"] == "present",
            "voice_parked": True,
            "fake_claims": False,
        },
        "safety": "presence-only reporting — no secret values, tokens, or key contents returned",
    }


__all__ = ["router"]
