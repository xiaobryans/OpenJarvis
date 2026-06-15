"""Jarvis Doctor — diagnostic and readiness layer.

Provides:
  checks   — 13 independent diagnostic checks (incl. project_linkage_status)
  readiness — evidence-backed readiness gate (9 categories, 4 verdicts)
"""

from openjarvis.doctor.checks import (
    CheckResult,
    CheckStatus,
    check_project_linkage_status,
    run_all_checks,
)
from openjarvis.doctor.readiness import (
    ReadinessCategory,
    ReadinessVerdict,
    evaluate_readiness,
)

__all__ = [
    "CheckResult",
    "CheckStatus",
    "ReadinessCategory",
    "ReadinessVerdict",
    "check_project_linkage_status",
    "evaluate_readiness",
    "run_all_checks",
]
