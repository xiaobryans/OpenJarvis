"""Sprint 4 proactive-intelligence endpoints (read-only; no secrets).

  GET /v1/email/triage          — URGENT/IMPORTANT emails (noise filtered) (4A)
  GET /v1/anomalies/recent      — recent anomalies (4B)
  GET /v1/research/overnight     — overnight research findings (4C)
  GET /v1/research/queue         — pending research queue (4G)
  GET /v1/summaries/weekly       — latest weekly summary (4D)
  GET /v1/relationships/checkups — people overdue for a check-in (4E)
  GET /v1/tasks/pending          — pending + overdue captured tasks (4F)
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/v1/email/triage")
async def email_triage() -> dict:
    from openjarvis.proactive.stores import EmailTriageStore
    rows = EmailTriageStore().actionable()
    return {"actionable": rows, "count": len(rows)}


@router.get("/v1/anomalies/recent")
async def anomalies_recent(limit: int = 20) -> dict:
    from openjarvis.proactive.stores import AnomalyStore
    rows = AnomalyStore().recent(limit)
    return {"anomalies": rows, "count": len(rows)}


@router.get("/v1/research/overnight")
async def research_overnight(limit: int = 10) -> dict:
    from openjarvis.proactive.stores import ResearchStore
    rows = ResearchStore().overnight(limit)
    return {"findings": rows, "count": len(rows)}


@router.get("/v1/research/queue")
async def research_queue() -> dict:
    from openjarvis.proactive.stores import ResearchStore
    rows = ResearchStore().queue()
    return {"queue": rows, "count": len(rows)}


@router.get("/v1/summaries/weekly")
async def summaries_weekly() -> dict:
    from openjarvis.proactive.stores import WeeklySummaryStore
    return {"summary": WeeklySummaryStore().latest()}


@router.get("/v1/relationships/checkups")
async def relationship_checkups() -> dict:
    from openjarvis.proactive.stores import RelationshipStore
    rows = RelationshipStore().checkups()
    return {"checkups": rows, "count": len(rows)}


@router.get("/v1/tasks/pending")
async def tasks_pending() -> dict:
    from openjarvis.proactive.stores import TaskStore
    store = TaskStore()
    pending = store.pending()
    return {"pending": pending, "overdue": store.overdue(), "count": len(pending)}
