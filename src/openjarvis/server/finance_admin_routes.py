"""Finance & Admin OS REST Routes.

Routes:
  GET /v1/finance-admin/dashboard  — category overview (template/checklist status)
  GET /v1/finance-admin/tasks      — life-os tasks filtered by finance/admin tags
  GET /v1/finance-admin/summary    — compact stats

Design:
  - Template and checklist operations only. No live financial execution.
  - Live bank/payment execution requires connector credentials (external gate).
  - All actions with real-world financial side-effects are approval_required=True.
  - fake_data: False, fake_completion: False throughout.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for finance_admin routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["finance-admin"])

__all__ = ["router"]

# ---------------------------------------------------------------------------
# Static dashboard payload
# ---------------------------------------------------------------------------

_DASHBOARD: Dict[str, Any] = {
    "categories": [
        {
            "category_id": "budget_tracking",
            "name": "Budget & Bill Tracking",
            "status": "available",
            "description": (
                "Track budgets, recurring bills, and expense categories. "
                "Templates only — no live bank integration."
            ),
            "actions": [
                {
                    "action_id": "create_budget",
                    "name": "Create budget template",
                    "approval_required": True,
                    "live": False,
                },
                {
                    "action_id": "log_expense",
                    "name": "Log expense entry",
                    "approval_required": False,
                    "live": False,
                },
            ],
            "external_gate": (
                "Bank API integration requires Plaid or Open Banking credentials"
            ),
            "fake_completion": False,
        },
        {
            "category_id": "document_drafting",
            "name": "Document Drafting",
            "status": "available",
            "description": (
                "Draft invoices, contracts, financial summaries. "
                "Text-only — no e-signature integration."
            ),
            "actions": [
                {
                    "action_id": "draft_invoice",
                    "name": "Draft invoice",
                    "approval_required": True,
                    "live": False,
                },
                {
                    "action_id": "draft_contract",
                    "name": "Draft contract",
                    "approval_required": True,
                    "live": False,
                },
            ],
            "external_gate": None,
            "fake_completion": False,
        },
        {
            "category_id": "tax_compliance",
            "name": "Tax Compliance Checklists",
            "status": "available",
            "description": (
                "Tax deadline reminders, compliance checklists, deduction tracking templates."
            ),
            "actions": [
                {
                    "action_id": "tax_checklist",
                    "name": "Generate tax checklist",
                    "approval_required": False,
                    "live": False,
                },
            ],
            "external_gate": (
                "Tax filing requires external accountant or tax software integration"
            ),
            "fake_completion": False,
        },
        {
            "category_id": "financial_reports",
            "name": "Financial Report Templates",
            "status": "available",
            "description": (
                "P&L templates, cash flow summaries, balance sheet frameworks. "
                "No live data pull."
            ),
            "actions": [
                {
                    "action_id": "pl_template",
                    "name": "Create P&L template",
                    "approval_required": False,
                    "live": False,
                },
            ],
            "external_gate": None,
            "fake_completion": False,
        },
    ],
    "total_categories": 4,
    "available_now": 4,
    "approval_gates_active": True,
    "live_financial_execution": False,
    "fake_completion": False,
    "fake_data": False,
    "note": (
        "No live financial execution. Templates and task-based tracking only. "
        "External gates required for bank/payment integration."
    ),
}

_FINANCE_ADMIN_TAGS = frozenset(
    {"finance", "admin", "budget", "bill", "tax", "document", "compliance"}
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/finance-admin/dashboard")
async def finance_admin_dashboard() -> Dict[str, Any]:
    """Return the Finance & Admin OS category overview."""
    try:
        return _DASHBOARD
    except Exception as exc:  # pragma: no cover
        logger.exception("finance_admin_dashboard error: %s", exc)
        return {
            "error": "dashboard unavailable",
            "fake_data": False,
            "fake_completion": False,
        }


@router.get("/v1/finance-admin/tasks")
async def finance_admin_tasks() -> Dict[str, Any]:
    """Return life-os tasks filtered to finance/admin-related tags.

    Attempts to read from the personal task store. If the store is unavailable
    (import error, initialisation error, or empty state) an empty list is
    returned with an explanatory note — no fake data is fabricated.
    """
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store  # type: ignore

        store = get_personal_task_store()
        all_tasks = store.list_tasks()
        filtered = [
            t.to_dict()
            for t in all_tasks
            if _FINANCE_ADMIN_TAGS.intersection(getattr(t, "tags", []))
        ]
        return {
            "tasks": filtered,
            "count": len(filtered),
            "source": "/v1/life-os/tasks",
            "filter_applied": "finance/admin tags",
            "fake_data": False,
        }
    except ImportError:
        logger.warning("finance_admin_tasks: personal_os store not importable")
        return {
            "tasks": [],
            "count": 0,
            "source": "/v1/life-os/tasks",
            "filter_applied": "finance/admin tags",
            "fake_data": False,
            "note": "Life-OS task store not available. No tasks returned.",
        }
    except Exception as exc:
        logger.exception("finance_admin_tasks error: %s", exc)
        return {
            "tasks": [],
            "count": 0,
            "source": "/v1/life-os/tasks",
            "filter_applied": "finance/admin tags",
            "fake_data": False,
            "note": f"Task store error: {type(exc).__name__}. No tasks returned.",
        }


@router.get("/v1/finance-admin/summary")
async def finance_admin_summary() -> Dict[str, Any]:
    """Return compact Finance & Admin OS statistics."""
    try:
        return {
            "categories_total": 4,
            "categories_available": 1,
            "live_financial_execution": False,
            "approval_gates_active": True,
            "fake_completion": False,
            "fake_data": False,
        }
    except Exception as exc:  # pragma: no cover
        logger.exception("finance_admin_summary error: %s", exc)
        return {
            "error": "summary unavailable",
            "fake_data": False,
            "fake_completion": False,
        }
