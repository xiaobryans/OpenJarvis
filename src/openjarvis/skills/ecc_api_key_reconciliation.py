"""ECC API-key delta reconciliation — 53 → 35 → 37.

Documents the authoritative source-of-truth and explains all count changes.

Summary:
  - The "53" figure was NOT from the authoritative catalog source.
    It was approximated from conversation-summary context (pre-sprint baseline),
    which conflated "installed_disabled" items (including guidance skills that
    appeared as disabled but were actually guidance-only) with API-key skills.

  - The authoritative source is ecc_catalog.py (ECCCatalog).

  - After Plan 1 full completion sprint (d26df349):
    35 skills had state READY_BUT_WAITING_FOR_API_KEY.

  - After Plan 1 correction sprint (this run):
    37 skills have state READY_BUT_WAITING_FOR_API_KEY.
    The 2 additional: nutrient-document-processing, continuous-learning-v2
    (previously ADAPT_NEEDED — wrappers now built, state updated).

Machine-readable: openjarvis.skills.ecc_api_key_reconciliation
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Reconciliation table: prior state → current state
# ---------------------------------------------------------------------------

# Source-of-truth statement
SOURCE_OF_TRUTH = (
    "The authoritative source for all ECC item states is "
    "src/openjarvis/skills/ecc_catalog.py (ECCCatalog.list_all()). "
    "The '53 installed_disabled/API-key skills' figure in prior conversation summaries "
    "was not derived from this source — it was an approximation from the intake checkpoint "
    "text, which combined installed_disabled items (including guidance skills that were "
    "subsequently activated) with API-key-needing skills. "
    "The 53 figure should be treated as a pre-sprint approximation, not an authoritative count."
)

# Changes from previous sprint (35) to correction sprint (37)
CORRECTION_SPRINT_ADDITIONS: List[Dict[str, Any]] = [
    {
        "skill_id": "ecc:nutrient-document-processing",
        "prior_state": "ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK",
        "new_state": "READY_BUT_WAITING_FOR_API_KEY",
        "reason_changed": "Wrapper built (NutrientDocWrapper). Only remaining blocker is NUTRIENT_API_KEY.",
        "still_needs_key": True,
        "required_key": "NUTRIENT_API_KEY",
        "became_active": False,
        "became_duplicate_rejected": False,
        "evidence_file": "src/openjarvis/skills/sources/ecc/wrappers/execution_wrappers.py",
    },
    {
        "skill_id": "ecc:continuous-learning-v2",
        "prior_state": "ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK",
        "new_state": "READY_BUT_WAITING_FOR_API_KEY",
        "reason_changed": (
            "Wrapper built (ContinuousLearningV2Wrapper). "
            "Consolidates to AIMLAPI_API_KEY (primary) or OPENROUTER_API_KEY (fallback). "
            "No native Anthropic/OpenAI key required."
        ),
        "still_needs_key": True,
        "required_key": "AIMLAPI_API_KEY (or OPENROUTER_API_KEY)",
        "became_active": False,
        "became_duplicate_rejected": False,
        "evidence_file": "src/openjarvis/skills/sources/ecc/wrappers/execution_wrappers.py",
    },
]

# Explanation of 53 → 35 delta (from pre-sprint baseline to completion sprint)
DELTA_53_TO_35_EXPLANATION: List[Dict[str, Any]] = [
    {
        "category": "Guidance skills incorrectly counted as API-key skills",
        "approximate_count": 14,
        "explanation": (
            "~14 skills in the pre-sprint '53' were guidance/documentation skills "
            "that appeared as 'installed_disabled' in the intake text. "
            "After review, they were pure guidance (no API key, no execution) "
            "and were activated as ACTIVE in the Plan 1 full completion sprint."
        ),
        "new_state": "ACTIVE",
    },
    {
        "category": "Skills requiring execution wrappers (not just API keys)",
        "approximate_count": 4,
        "explanation": (
            "~4 skills needed engineering work (wrappers) beyond just providing a key. "
            "They were moved to ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK in the completion sprint, "
            "and to READY_BUT_WAITING_FOR_API_KEY/APPROVAL in the correction sprint "
            "after wrappers were built."
        ),
        "new_state": "READY_BUT_WAITING_FOR_API_KEY or READY_BUT_WAITING_FOR_APPROVAL",
    },
    {
        "category": "True API-key skills remaining",
        "approximate_count": 35,
        "explanation": (
            "35 skills genuinely require external service API keys. "
            "These are the authoritative READY_BUT_WAITING_FOR_API_KEY items "
            "from the Plan 1 completion sprint (d26df349)."
        ),
        "new_state": "READY_BUT_WAITING_FOR_API_KEY",
    },
]

# Final authoritative counts
AUTHORITATIVE_COUNTS = {
    "pre_sprint_approximation": {
        "label": "Pre-sprint '53' (approximation, not authoritative)",
        "source": "Conversation summary / intake checkpoint text",
        "count": 53,
        "is_authoritative": False,
        "note": "Included guidance skills + skills needing engineering work",
    },
    "completion_sprint": {
        "label": "After Plan 1 full completion sprint (d26df349)",
        "source": "ECCCatalog.list_all() — authoritative",
        "count": 35,
        "is_authoritative": True,
        "breakdown": "35 genuine API-key skills, properly classified",
    },
    "correction_sprint": {
        "label": "After Plan 1 correction sprint (this run)",
        "source": "ECCCatalog.list_all() — authoritative",
        "count": 37,
        "is_authoritative": True,
        "breakdown": (
            "35 existing + 2 new additions from ADAPT_NEEDED "
            "(nutrient-document-processing, continuous-learning-v2) "
            "after wrappers built"
        ),
    },
}


def get_reconciliation_report() -> Dict[str, Any]:
    """Return full reconciliation report as a dict."""
    return {
        "source_of_truth": SOURCE_OF_TRUTH,
        "authoritative_counts": AUTHORITATIVE_COUNTS,
        "delta_53_to_35_explanation": DELTA_53_TO_35_EXPLANATION,
        "correction_sprint_additions": CORRECTION_SPRINT_ADDITIONS,
        "summary": (
            "53 (approximated, not authoritative) → "
            "35 (authoritative, completion sprint) → "
            "37 (authoritative, correction sprint). "
            "The 53 was not from the catalog source-of-truth. "
            "All 37 current API-key skills have exact key requirements documented in "
            "docs/certification/plan1_ecc_minimal_provider_keys.json."
        ),
    }


__all__ = [
    "SOURCE_OF_TRUTH",
    "CORRECTION_SPRINT_ADDITIONS",
    "DELTA_53_TO_35_EXPLANATION",
    "AUTHORITATIVE_COUNTS",
    "get_reconciliation_report",
]
