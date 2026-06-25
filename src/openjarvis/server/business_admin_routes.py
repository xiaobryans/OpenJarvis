"""Business / Admin Operator routes — B10.

Routes:
  GET /v1/business-admin/dashboard  — full category status with actions
  GET /v1/business-admin/workflows  — flat workflow list with gate metadata
  GET /v1/business-admin/summary    — quick numeric summary

Safety guarantees:
  - No live external calls.
  - No secret access.
  - fake_completion: False, fake_data: False in all responses.
  - Graceful try/except for all handlers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["business-admin"])

# ---------------------------------------------------------------------------
# Static catalog builders
# ---------------------------------------------------------------------------


def _build_categories() -> List[Dict[str, Any]]:
    return [
        {
            "category_id": "finance_tracking",
            "name": "Finance & Budget Tracking",
            "description": (
                "Track personal and business finances. Review budgets, expenses, invoices."
            ),
            "status": "read_only",
            "actions": [
                {
                    "action_id": "log_expense",
                    "name": "Log expense",
                    "approval_required": True,
                    "live": False,
                },
                {
                    "action_id": "view_budget",
                    "name": "View budget",
                    "approval_required": False,
                    "live": False,
                },
            ],
            "external_gate": "Financial accounts not connected. Manual entry only.",
            "fake_completion": False,
        },
        {
            "category_id": "admin_tasks",
            "name": "Admin & Operations",
            "description": (
                "Meeting prep, follow-ups, document drafting, calendar coordination."
            ),
            "status": "available",
            "actions": [
                {
                    "action_id": "draft_agenda",
                    "name": "Draft meeting agenda",
                    "approval_required": False,
                    "live": True,
                },
                {
                    "action_id": "schedule_followup",
                    "name": "Schedule follow-up",
                    "approval_required": True,
                    "live": False,
                },
                {
                    "action_id": "create_checklist",
                    "name": "Create task checklist",
                    "approval_required": False,
                    "live": True,
                },
            ],
            "external_gate": None,
            "fake_completion": False,
        },
        {
            "category_id": "research_analysis",
            "name": "Research & Analysis",
            "description": (
                "Market research, competitive analysis, document summarization, data collection planning."
            ),
            "status": "available",
            "actions": [
                {
                    "action_id": "research_topic",
                    "name": "Research a topic",
                    "approval_required": False,
                    "live": True,
                },
                {
                    "action_id": "summarize_document",
                    "name": "Summarize document",
                    "approval_required": False,
                    "live": True,
                },
                {
                    "action_id": "competitive_scan",
                    "name": "Competitive landscape scan",
                    "approval_required": False,
                    "live": True,
                },
            ],
            "external_gate": None,
            "fake_completion": False,
        },
        {
            "category_id": "company_building",
            "name": "Company Building",
            "description": (
                "Investor updates, hiring checklists, GTM planning, legal/compliance checklist review."
            ),
            "status": "template_only",
            "actions": [
                {
                    "action_id": "investor_update_template",
                    "name": "Investor update template",
                    "approval_required": False,
                    "live": False,
                },
                {
                    "action_id": "hiring_checklist",
                    "name": "Hiring checklist",
                    "approval_required": False,
                    "live": False,
                },
                {
                    "action_id": "gtm_plan_draft",
                    "name": "GTM plan draft",
                    "approval_required": True,
                    "live": False,
                },
            ],
            "external_gate": "Requires live connector or manual input for real execution.",
            "fake_completion": False,
        },
        {
            "category_id": "communications",
            "name": "External Communications",
            "description": (
                "Draft emails, messages, announcements. Send requires connector credentials + approval."
            ),
            "status": "draft_only",
            "actions": [
                {
                    "action_id": "draft_email",
                    "name": "Draft email",
                    "approval_required": False,
                    "live": False,
                },
                {
                    "action_id": "send_email",
                    "name": "Send email",
                    "approval_required": True,
                    "live": False,
                },
                {
                    "action_id": "draft_message",
                    "name": "Draft Slack/Telegram message",
                    "approval_required": False,
                    "live": False,
                },
            ],
            "external_gate": "Send requires Gmail/Slack credentials + Tier 3 approval.",
            "fake_completion": False,
        },
    ]


def _build_workflows() -> List[Dict[str, Any]]:
    return [
        {
            "workflow_id": "daily_standup_prep",
            "name": "Daily standup prep",
            "category": "admin_tasks",
            "source_route": "/v1/life-os/tasks",
            "approval_required": False,
            "available": True,
        },
        {
            "workflow_id": "weekly_review",
            "name": "Weekly review",
            "category": "admin_tasks",
            "source_route": "/v1/life-os/tasks",
            "approval_required": False,
            "available": True,
        },
        {
            "workflow_id": "goal_checkpoint",
            "name": "Goal checkpoint review",
            "category": "admin_tasks",
            "source_route": "/v1/goals",
            "approval_required": False,
            "available": True,
        },
        {
            "workflow_id": "expense_log",
            "name": "Log expense",
            "category": "finance_tracking",
            "source_route": None,
            "approval_required": True,
            "available": False,
            "gate": "No finance connector configured",
        },
        {
            "workflow_id": "investor_update",
            "name": "Investor update draft",
            "category": "company_building",
            "source_route": None,
            "approval_required": True,
            "available": False,
            "gate": "Template only — requires manual completion",
        },
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/business-admin/dashboard")
async def get_business_admin_dashboard() -> Dict[str, Any]:
    """Return the full Business/Admin OS category and action status.

    No live external calls. No secret access.
    fake_completion: False, fake_data: False.
    """
    try:
        categories = _build_categories()
        available_now = sum(1 for c in categories if c["status"] == "available")
        return {
            "categories": categories,
            "total_categories": len(categories),
            "available_now": available_now,
            "approval_gates_active": True,
            "fake_completion": False,
            "fake_data": False,
            "note": (
                "Business/Admin OS. Read-only and draft operations available. "
                "Execution of external actions requires connector credentials and approval gates."
            ),
        }
    except Exception as exc:
        logger.exception("business-admin dashboard error: %s", exc)
        return {
            "categories": [],
            "total_categories": 0,
            "available_now": 0,
            "approval_gates_active": True,
            "fake_completion": False,
            "fake_data": False,
            "error": "dashboard_unavailable",
        }


@router.get("/v1/business-admin/workflows")
async def get_business_admin_workflows() -> Dict[str, Any]:
    """Return available business workflows as a flat list with gate metadata.

    No live external calls. No secret access.
    """
    try:
        workflows = _build_workflows()
        available_count = sum(1 for w in workflows if w["available"])
        return {
            "workflows": workflows,
            "count": len(workflows),
            "available_count": available_count,
            "fake_data": False,
        }
    except Exception as exc:
        logger.exception("business-admin workflows error: %s", exc)
        return {
            "workflows": [],
            "count": 0,
            "available_count": 0,
            "fake_data": False,
            "error": "workflows_unavailable",
        }


@router.get("/v1/business-admin/summary")
async def get_business_admin_summary() -> Dict[str, Any]:
    """Return a quick numeric summary of Business/Admin OS state."""
    try:
        categories = _build_categories()
        workflows = _build_workflows()
        categories_available = sum(1 for c in categories if c["status"] == "available")
        workflows_available = sum(1 for w in workflows if w["available"])
        return {
            "categories_total": len(categories),
            "categories_available": categories_available,
            "workflows_total": len(workflows),
            "workflows_available": workflows_available,
            "approval_gates_active": True,
            "fake_completion": False,
            "fake_data": False,
        }
    except Exception as exc:
        logger.exception("business-admin summary error: %s", exc)
        return {
            "categories_total": 0,
            "categories_available": 0,
            "workflows_total": 0,
            "workflows_available": 0,
            "approval_gates_active": True,
            "fake_completion": False,
            "fake_data": False,
            "error": "summary_unavailable",
        }


__all__ = ["router"]
