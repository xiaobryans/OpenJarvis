"""REST endpoints for Jarvis Browser Operator (dry-run / capability-matrix only).

Routes:
  GET  /v1/browser-operator/status             — operator availability and safety flags
  POST /v1/browser-operator/plan               — dry-run action plan (no execution)
  GET  /v1/browser-operator/capability-matrix  — per-category availability matrix

Design rules:
  - No live browser control implemented.
  - No credentials read, no session cookies accessed, no form submissions executed.
  - All plans are dry-run only; execution requires external browser operator integration.
  - Authentication category is permanently blocked.
  - fake_live: False, fake_data: False in all responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for browser operator routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["browser-operator"])

__all__ = ["router"]


class BrowserPlanRequest(BaseModel):
    action: str
    url: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


@router.get("/v1/browser-operator/status")
async def browser_operator_status() -> Dict[str, Any]:
    """Return browser operator availability and safety flags.

    No live browser control is implemented. All values reflect actual
    capability state — no fake_live, no fake_data.
    """
    try:
        return {
            "browser_operator_available": False,
            "dry_run_only": True,
            "supported_actions": [
                {
                    "action_id": "navigate",
                    "name": "Navigate to URL",
                    "dry_run_only": True,
                    "approval_required": True,
                },
                {
                    "action_id": "extract",
                    "name": "Extract page content",
                    "dry_run_only": True,
                    "approval_required": True,
                },
                {
                    "action_id": "form_fill",
                    "name": "Fill form fields",
                    "dry_run_only": True,
                    "approval_required": True,
                },
                {
                    "action_id": "screenshot",
                    "name": "Take screenshot",
                    "dry_run_only": True,
                    "approval_required": True,
                },
            ],
            "external_gates": [
                "Playwright or Puppeteer library not yet integrated",
                "Sandboxed browser execution environment required",
                "Tier 3/4 approval required for all browser actions",
            ],
            "safety": {
                "dry_run_enforced": True,
                "approval_required": True,
                "no_autonomous_browsing": True,
                "no_credential_injection": True,
            },
            "fake_live": False,
            "fake_data": False,
            "note": (
                "Browser operator is dry-run only. No live browser control. "
                "All actions require Tier 3/4 approval."
            ),
        }
    except Exception as exc:
        logger.exception("browser_operator_status failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve browser operator status")


@router.post("/v1/browser-operator/plan")
async def browser_operator_plan(req: BrowserPlanRequest) -> Dict[str, Any]:
    """Return a dry-run action plan for the requested browser action.

    Does NOT execute the action. Validates that action is a non-empty string.
    URL is treated as an opaque string — it is never loaded or accessed.
    """
    try:
        action = (req.action or "").strip()
        if not action:
            raise HTTPException(
                status_code=422,
                detail="'action' must be a non-empty string.",
            )

        url = req.url or ""

        return {
            "dry_run": True,
            "action": action,
            "url": url,
            "plan": [
                {
                    "step": 1,
                    "description": f"Validate URL and permissions for: {action}",
                },
                {
                    "step": 2,
                    "description": "Request Tier 3/4 approval for browser action",
                },
                {
                    "step": 3,
                    "description": (
                        f"Execute: {action} "
                        "(requires browser operator integration — external gate)"
                    ),
                },
            ],
            "executed": False,
            "approval_required": True,
            "browser_live": False,
            "external_gate": "Browser operator integration not yet deployed",
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("browser_operator_plan failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate browser operator plan")


@router.get("/v1/browser-operator/capability-matrix")
async def browser_operator_capability_matrix() -> Dict[str, Any]:
    """Return per-category browser capability matrix.

    The 'authentication' category is permanently blocked — web login and
    session management are not supported for security reasons.
    """
    try:
        return {
            "categories": [
                {
                    "category": "Web Navigation",
                    "available": False,
                    "dry_run_only": True,
                    "approval_tier": "Tier 3",
                    "reason": "Browser library not integrated",
                },
                {
                    "category": "Content Extraction",
                    "available": False,
                    "dry_run_only": True,
                    "approval_tier": "Tier 3",
                    "reason": "Browser library not integrated",
                },
                {
                    "category": "Form Interaction",
                    "available": False,
                    "dry_run_only": True,
                    "approval_tier": "Tier 4",
                    "reason": "Browser library not integrated",
                },
                {
                    "category": "File Download",
                    "available": False,
                    "dry_run_only": True,
                    "approval_tier": "Tier 4",
                    "reason": "External gate: sandboxed environment",
                },
                {
                    "category": "Authentication Flows",
                    "available": False,
                    "dry_run_only": True,
                    "approval_tier": "Tier 4",
                    "reason": "External gate: credential safety review",
                },
            ],
            "live_browser": False,
            "fake_live": False,
            "fake_data": False,
            "note": "Capability matrix only. No live browser execution.",
        }
    except Exception as exc:
        logger.exception("browser_operator_capability_matrix failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve capability matrix")
