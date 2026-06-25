"""Connector Workflow Expansion routes — B8.

Routes:
  GET  /v1/connector-workflows            — full connector workflow catalog
  GET  /v1/connector-workflows/summary    — quick numeric summary
  POST /v1/connector-workflows/{workflow_id}/dry-run — validate workflow params (no execution)

Safety guarantees:
  - Never reads, prints, or returns actual secret values, tokens, or key contents.
  - Presence-only env checks via os.environ.get().
  - No live external calls.
  - fake_data: False, fake_live: False in all responses.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["connector-workflows"])

# ---------------------------------------------------------------------------
# Presence-only helpers — never expose values
# ---------------------------------------------------------------------------


def _env_any(*names: str) -> bool:
    return any(bool(os.environ.get(n, "").strip()) for n in names)


def _slack_configured() -> bool:
    return _env_any("SLACK_BOT_TOKEN", "SLACK_OAUTH_TOKEN")


def _telegram_configured() -> bool:
    return _env_any("TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN")


def _github_configured() -> bool:
    return _env_any("GITHUB_TOKEN", "GH_TOKEN")


def _notion_configured() -> bool:
    return _env_any("NOTION_API_KEY", "NOTION_TOKEN")


def _google_oauth_present() -> bool:
    return _env_any("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID")


# ---------------------------------------------------------------------------
# Catalog builder
# ---------------------------------------------------------------------------


def _build_catalog() -> List[Dict[str, Any]]:
    slack_ok = _slack_configured()
    telegram_ok = _telegram_configured()
    github_ok = _github_configured()
    notion_ok = _notion_configured()
    google_present = _google_oauth_present()

    connectors: List[Dict[str, Any]] = [
        {
            "connector_id": "gmail",
            "name": "Gmail",
            "status": "partial" if google_present else "not_configured",
            "credential_gate": "GOOGLE_OAUTH_CLIENT_ID env var + OAuth flow",
            "available_workflows": [
                {
                    "workflow_id": "gmail_send",
                    "name": "Send email",
                    "dry_run_only": True,
                    "requires_approval": True,
                },
                {
                    "workflow_id": "gmail_read_recent",
                    "name": "Read recent emails",
                    "dry_run_only": True,
                    "requires_approval": False,
                },
                {
                    "workflow_id": "gmail_label",
                    "name": "Label/archive email",
                    "dry_run_only": True,
                    "requires_approval": True,
                },
            ],
            "live": False,
            "fake_live": False,
        },
        {
            "connector_id": "slack",
            "name": "Slack",
            "status": "configured" if slack_ok else "not_configured",
            "credential_gate": "SLACK_BOT_TOKEN env var",
            "available_workflows": [
                {
                    "workflow_id": "slack_send_message",
                    "name": "Send message",
                    "dry_run_only": not slack_ok,
                    "requires_approval": True,
                },
                {
                    "workflow_id": "slack_read_channel",
                    "name": "Read channel messages",
                    "dry_run_only": not slack_ok,
                    "requires_approval": False,
                },
            ],
            "live": slack_ok,
            "fake_live": False,
        },
        {
            "connector_id": "telegram",
            "name": "Telegram",
            "status": "configured" if telegram_ok else "not_configured",
            "credential_gate": "TELEGRAM_BOT_TOKEN env var",
            "available_workflows": [
                {
                    "workflow_id": "telegram_send",
                    "name": "Send message",
                    "dry_run_only": not telegram_ok,
                    "requires_approval": True,
                },
            ],
            "live": telegram_ok,
            "fake_live": False,
        },
        {
            "connector_id": "github",
            "name": "GitHub",
            "status": "configured" if github_ok else "not_configured",
            "credential_gate": "GITHUB_TOKEN env var",
            "available_workflows": [
                {
                    "workflow_id": "github_create_issue",
                    "name": "Create issue",
                    "dry_run_only": not github_ok,
                    "requires_approval": True,
                },
                {
                    "workflow_id": "github_list_issues",
                    "name": "List issues",
                    "dry_run_only": not github_ok,
                    "requires_approval": False,
                },
                {
                    "workflow_id": "github_create_pr",
                    "name": "Create pull request",
                    "dry_run_only": not github_ok,
                    "requires_approval": True,
                },
            ],
            "live": github_ok,
            "fake_live": False,
        },
        {
            "connector_id": "notion",
            "name": "Notion",
            "status": "configured" if notion_ok else "not_configured",
            "credential_gate": "NOTION_API_KEY env var",
            "available_workflows": [
                {
                    "workflow_id": "notion_create_page",
                    "name": "Create page",
                    "dry_run_only": not notion_ok,
                    "requires_approval": True,
                },
                {
                    "workflow_id": "notion_read_database",
                    "name": "Read database",
                    "dry_run_only": not notion_ok,
                    "requires_approval": False,
                },
            ],
            "live": notion_ok,
            "fake_live": False,
        },
        {
            "connector_id": "google_calendar",
            "name": "Google Calendar",
            "status": "partial" if google_present else "not_configured",
            "credential_gate": "Google OAuth flow + calendar scope",
            "available_workflows": [
                {
                    "workflow_id": "calendar_read_events",
                    "name": "Read events",
                    "dry_run_only": True,
                    "requires_approval": False,
                },
                {
                    "workflow_id": "calendar_create_event",
                    "name": "Create event",
                    "dry_run_only": True,
                    "requires_approval": True,
                },
            ],
            "live": False,
            "fake_live": False,
        },
    ]
    return connectors


def _all_workflow_ids() -> Dict[str, Dict[str, Any]]:
    """Return a flat map of workflow_id -> connector metadata for lookup."""
    catalog = _build_catalog()
    mapping: Dict[str, Dict[str, Any]] = {}
    for connector in catalog:
        for wf in connector["available_workflows"]:
            mapping[wf["workflow_id"]] = {
                "connector_id": connector["connector_id"],
                "connector_status": connector["status"],
                "approval_required": wf["requires_approval"],
                "live": connector["live"],
            }
    return mapping


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class DryRunRequest(BaseModel):
    connector_id: str
    parameters: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/connector-workflows")
async def get_connector_workflows() -> Dict[str, Any]:
    """Return the full connector workflow catalog.

    Presence-only env checks. No secret values. No live external calls.
    dry_run_only=True means credentials are not yet configured for that connector.
    """
    try:
        connectors = _build_catalog()
        live_count = sum(1 for c in connectors if c["live"])
        configured_count = sum(
            1 for c in connectors if c["status"] in ("configured", "partial")
        )
        return {
            "connectors": connectors,
            "live_connector_count": live_count,
            "configured_count": configured_count,
            "total": len(connectors),
            "fake_live": False,
            "fake_data": False,
            "note": (
                "Workflows shown are capability plans. dry_run_only=true means credentials "
                "not yet configured. All live actions require approval gates."
            ),
        }
    except Exception as exc:
        logger.exception("connector-workflows catalog error: %s", exc)
        return {
            "connectors": [],
            "live_connector_count": 0,
            "configured_count": 0,
            "total": 0,
            "fake_live": False,
            "fake_data": False,
            "error": "catalog_unavailable",
        }


@router.get("/v1/connector-workflows/summary")
async def get_connector_workflows_summary() -> Dict[str, Any]:
    """Return a quick numeric summary of connector workflow state."""
    try:
        connectors = _build_catalog()
        live_count = sum(1 for c in connectors if c["live"])
        configured_count = sum(
            1 for c in connectors if c["status"] in ("configured", "partial")
        )
        not_configured_count = sum(
            1 for c in connectors if c["status"] == "not_configured"
        )
        total_workflows = sum(len(c["available_workflows"]) for c in connectors)
        return {
            "live_count": live_count,
            "configured_count": configured_count,
            "not_configured_count": not_configured_count,
            "total_workflows_available": total_workflows,
            "all_dry_run_only": live_count == 0,
            "fake_live": False,
            "fake_data": False,
        }
    except Exception as exc:
        logger.exception("connector-workflows summary error: %s", exc)
        return {
            "live_count": 0,
            "configured_count": 0,
            "not_configured_count": 0,
            "total_workflows_available": 0,
            "all_dry_run_only": True,
            "fake_live": False,
            "fake_data": False,
            "error": "summary_unavailable",
        }


@router.post("/v1/connector-workflows/{workflow_id}/dry-run")
async def dry_run_workflow(
    workflow_id: str,
    body: DryRunRequest,
) -> Dict[str, Any]:
    """Validate workflow parameters without executing anything.

    Returns 404 if workflow_id is not in the known catalog.
    Never executes any external call — dry run only.
    """
    try:
        workflow_map = _all_workflow_ids()
        if workflow_id not in workflow_map:
            raise HTTPException(
                status_code=404,
                detail=f"workflow_id '{workflow_id}' not found in connector workflow catalog",
            )
        meta = workflow_map[workflow_id]
        return {
            "workflow_id": workflow_id,
            "dry_run": True,
            "connector_id": body.connector_id,
            "would_execute": False,
            "connector_status": meta["connector_status"],
            "approval_required": meta["approval_required"],
            "gate": "approval_required_before_live_execution",
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("dry-run error for workflow %s: %s", workflow_id, exc)
        raise HTTPException(status_code=500, detail="dry_run_error")


__all__ = ["router"]
