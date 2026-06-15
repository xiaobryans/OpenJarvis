"""Jarvis Doctor — diagnostic and readiness layer.

Provides:
  checks   — 12 independent diagnostic checks
  readiness — evidence-backed readiness gate (8 categories, 4 verdicts)
"""

from openjarvis.doctor.checks import (
    CheckResult,
    CheckStatus,
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
    "evaluate_readiness",
    "run_all_checks",
]
