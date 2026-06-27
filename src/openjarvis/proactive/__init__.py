"""Sprint 4 — Stage 4 proactive intelligence for VANTA.

SQLite-backed stores + pure classification/extraction logic for the proactive
features: email triage (4A), anomaly detection (4B), overnight research
(4C/4G), weekly summaries (4D), relationship check-ins (4E), proactive task
capture (4F), and behaviour pattern learning (4H).

All stores accept an explicit db path so the whole module is unit-testable
headlessly. Live data (real Gmail scans, the 2am scheduler, etc.) is wired on
top by the scheduler + connectors.
"""

from openjarvis.proactive.stores import (
    AnomalyStore,
    EmailTriageStore,
    PatternStore,
    RelationshipStore,
    ResearchStore,
    TaskStore,
    WeeklySummaryStore,
    classify_email,
    extract_tasks,
)

__all__ = [
    "TaskStore", "ResearchStore", "AnomalyStore", "RelationshipStore",
    "EmailTriageStore", "WeeklySummaryStore", "PatternStore",
    "classify_email", "extract_tasks",
]
