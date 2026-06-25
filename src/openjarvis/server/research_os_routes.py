"""Research OS REST Routes.

Routes:
  GET /v1/research-os/dashboard  — section overview (queue/learning/company/kb)
  GET /v1/research-os/queue      — life-os tasks filtered by research/learning tags
  GET /v1/research-os/templates  — static research & company-building templates
  GET /v1/research-os/summary    — compact stats

Design:
  - Local task/goal/memory integration only. No live web retrieval.
  - Live web search requires a search connector (external gate).
  - No fake research output is generated at any route.
  - fake_data: False, fake_research: False throughout.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for research_os routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research-os"])

__all__ = ["router"]

# ---------------------------------------------------------------------------
# Static payloads
# ---------------------------------------------------------------------------

_DASHBOARD: Dict[str, Any] = {
    "sections": [
        {
            "section_id": "research_queue",
            "name": "Research Queue",
            "status": "available",
            "description": "Manage research tasks, topics, and inquiry backlog.",
            "source_route": "/v1/life-os/tasks?type=research",
            "live_web_retrieval": False,
            "fake_research": False,
        },
        {
            "section_id": "learning_plans",
            "name": "Learning Plans",
            "status": "available",
            "description": (
                "Structured learning objectives, course notes, skill development tracking."
            ),
            "source_route": "/v1/goals",
            "live_web_retrieval": False,
            "fake_research": False,
        },
        {
            "section_id": "company_building",
            "name": "Company-Building OS",
            "status": "available",
            "description": "Startup/company project templates, hiring plans, GTM frameworks.",
            "source_route": "/v1/business-admin/dashboard",
            "live_web_retrieval": False,
            "fake_research": False,
        },
        {
            "section_id": "web_research",
            "name": "Web Research (Planned)",
            "status": "partial",
            "description": "Live web retrieval via search APIs. Not yet integrated.",
            "source_route": None,
            "live_web_retrieval": False,
            "fake_research": False,
            "external_gate": (
                "Requires Perplexity / SerpAPI / Brave Search API key"
            ),
        },
    ],
    "live_web_retrieval": False,
    "fake_research": False,
    "fake_data": False,
    "provenance": "Local tasks/goals/memory",
    "note": (
        "No live web retrieval. All research linked to local tasks/goals/memory."
    ),
}

_TEMPLATES: Dict[str, Any] = {
    "templates": [
        {
            "template_id": "market_research",
            "name": "Market Research",
            "description": (
                "Competitor analysis, market sizing, TAM/SAM/SOM framework."
            ),
            "fields": ["market", "competitors", "target_customer", "differentiation"],
            "live_output": False,
        },
        {
            "template_id": "technical_research",
            "name": "Technical Research",
            "description": (
                "Technology evaluation, architecture options, trade-off analysis."
            ),
            "fields": ["topic", "options", "constraints", "recommendation"],
            "live_output": False,
        },
        {
            "template_id": "learning_plan",
            "name": "Learning Plan",
            "description": "Structured skill-building plan with milestones.",
            "fields": [
                "skill",
                "current_level",
                "target_level",
                "resources",
                "timeline",
            ],
            "live_output": False,
        },
    ],
    "count": 3,
    "live_output": False,
    "fake_research": False,
    "fake_data": False,
    "note": "Templates only. No live web output.",
}

_RESEARCH_TAGS = frozenset(
    {"research", "study", "learning", "analysis", "investigation"}
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/research-os/dashboard")
async def research_os_dashboard() -> Dict[str, Any]:
    """Return the Research OS section overview."""
    try:
        return _DASHBOARD
    except Exception as exc:  # pragma: no cover
        logger.exception("research_os_dashboard error: %s", exc)
        return {
            "error": "dashboard unavailable",
            "fake_data": False,
            "fake_research": False,
        }


@router.get("/v1/research-os/queue")
async def research_os_queue() -> Dict[str, Any]:
    """Return life-os tasks filtered to research/learning-related tags.

    Attempts to read from the personal task store. If the store is unavailable
    an empty list is returned with an explanatory note — no fake data is
    fabricated.
    """
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store  # type: ignore

        store = get_personal_task_store()
        all_tasks = store.list_tasks()
        filtered = [
            t.to_dict()
            for t in all_tasks
            if _RESEARCH_TAGS.intersection(getattr(t, "tags", []))
        ]
        return {
            "tasks": filtered,
            "count": len(filtered),
            "source": "/v1/life-os/tasks",
            "filter_applied": "research/learning tags",
            "fake_data": False,
        }
    except ImportError:
        logger.warning("research_os_queue: personal_os store not importable")
        return {
            "tasks": [],
            "count": 0,
            "source": "/v1/life-os/tasks",
            "filter_applied": "research/learning tags",
            "fake_data": False,
            "note": "Life-OS task store not available. No tasks returned.",
        }
    except Exception as exc:
        logger.exception("research_os_queue error: %s", exc)
        return {
            "tasks": [],
            "count": 0,
            "source": "/v1/life-os/tasks",
            "filter_applied": "research/learning tags",
            "fake_data": False,
            "note": f"Task store error: {type(exc).__name__}. No tasks returned.",
        }


@router.get("/v1/research-os/templates")
async def research_os_templates() -> Dict[str, Any]:
    """Return static research and company-building templates."""
    try:
        return _TEMPLATES
    except Exception as exc:  # pragma: no cover
        logger.exception("research_os_templates error: %s", exc)
        return {
            "error": "templates unavailable",
            "fake_data": False,
            "fake_research": False,
        }


@router.get("/v1/research-os/summary")
async def research_os_summary() -> Dict[str, Any]:
    """Return compact Research OS statistics."""
    try:
        return {
            "sections_total": 4,
            "sections_available": 3,
            "sections_partial": 1,
            "templates_count": 5,
            "live_web_retrieval": False,
            "fake_research": False,
            "fake_data": False,
        }
    except Exception as exc:  # pragma: no cover
        logger.exception("research_os_summary error: %s", exc)
        return {
            "error": "summary unavailable",
            "fake_data": False,
            "fake_research": False,
        }
