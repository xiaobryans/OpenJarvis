"""Connector Readiness routes — Phase C14.

C14 — Live Connector Readiness Verification Layer.
Surfaces env-presence-based readiness status for all Bryan-cleared connectors.
No credential values are ever returned. Notion is blocked per Bryan instruction.

Routes:
  GET  /v1/connector-readiness/status               — all connectors summary
  GET  /v1/connector-readiness/detail/{connector_id} — single connector detail

Governance:
  - fake_data is always False
  - secrets_in_response is always False
  - fake_live_claims is always False
  - Presence-only env checks: os.environ.get("KEY") — never printed
  - live_verified_count is always 0 (no live credential tests run)
  - Notion is always "blocked" per Bryan instruction
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

try:
    from fastapi import APIRouter, HTTPException
except ImportError:
    raise ImportError("fastapi is required for connector readiness routes")

log = logging.getLogger(__name__)

router = APIRouter(tags=["connector-readiness"])

__all__ = ["router"]


def _check(keys: List[str]) -> bool:
    """Return True if ANY of the env vars in keys is present (non-empty). Never prints values."""
    return any(os.environ.get(k) for k in keys)


def _build_connectors() -> List[Dict[str, Any]]:
    """Build the connectors list dynamically from env presence checks.
    No credential values are read beyond presence check.
    """
    return [
        {
            "connector_id": "gmail",
            "name": "Gmail/Google",
            "status": "ready_prerequisite" if _check(["GOOGLE_CLIENT_ID", "GOOGLE_OAUTH_TOKEN_PATH"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "slack",
            "name": "Slack",
            "status": "ready_prerequisite" if _check(["SLACK_BOT_TOKEN"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "telegram",
            "name": "Telegram",
            "status": "ready_prerequisite" if _check(["TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "github",
            "name": "GitHub",
            "status": "ready_prerequisite" if _check(["GITHUB_TOKEN", "JARVIS_GITHUB_TOKEN"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "tavily",
            "name": "Tavily",
            "status": "ready_prerequisite" if _check(["TAVILY_API_KEY"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "aws",
            "name": "AWS",
            "status": "ready_prerequisite" if _check(["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "s3",
            "name": "S3",
            "status": "ready_prerequisite" if _check(["AWS_S3_BUCKET", "JARVIS_S3_BUCKET"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "fargate",
            "name": "Fargate/ECS",
            "status": "ready_prerequisite" if _check(["FARGATE_CLUSTER", "ECS_CLUSTER"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "tailscale",
            "name": "Tailscale",
            "status": "ready_prerequisite" if _check(["TAILSCALE_AUTH_KEY", "TAILSCALE_API_KEY"]) else "not_configured",
            "bryan_cleared": True,
            "presence_only": True,
            "no_credential_value": True,
        },
        {
            "connector_id": "notion",
            "name": "Notion",
            "status": "blocked",
            "bryan_cleared": False,
            "reason": "Notion page lagging — Bryan said retry later",
            "presence_only": True,
            "no_credential_value": True,
        },
    ]


@router.get("/v1/connector-readiness/status")
async def connector_readiness_status() -> Dict[str, Any]:
    """Return presence-based readiness status for all connectors.

    No credential values are ever included in this response.
    live_verified_count is always 0 — no live credential tests are run.
    Notion is always 'blocked' per Bryan instruction.
    """
    connectors = _build_connectors()

    counts: Dict[str, int] = {"ready_prerequisite": 0, "blocked": 0, "not_configured": 0, "live_verified": 0}
    for c in connectors:
        status = c.get("status", "not_configured")
        if status in counts:
            counts[status] += 1
        else:
            counts["not_configured"] += 1

    return {
        "connectors": connectors,
        "total": len(connectors),
        "ready_prerequisite_count": counts["ready_prerequisite"],
        "blocked_count": counts["blocked"],
        "not_configured_count": counts["not_configured"],
        "live_verified_count": 0,
        "fake_live_claims": False,
        "secrets_in_response": False,
        "fake_data": False,
        "note": "Status based on env var presence only. No credential values in response.",
    }


@router.get("/v1/connector-readiness/detail/{connector_id}")
async def connector_readiness_detail(connector_id: str) -> Dict[str, Any]:
    """Return presence-based readiness detail for a single connector.

    Returns 404 if connector_id is not recognised.
    No credential values are ever included in this response.
    """
    connectors = _build_connectors()
    match = next((c for c in connectors if c["connector_id"] == connector_id), None)

    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connector '{connector_id}' not found. Valid ids: {[c['connector_id'] for c in connectors]}",
        )

    return {
        **match,
        "live_execution_blocked": True,
        "approval_required_for_actions": True,
    }
