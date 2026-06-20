"""Plan 3 test fixture — safe, controlled file for real worker inspection.

This file is intentionally simple with a deliberate None-check bug so the
Plan 3 real worker can read it, produce a diff suggestion, and the reviewer
can verify the evidence.

DO NOT modify this file without updating tests/workbench/test_plan3_real_worker.py.
"""

from __future__ import annotations

from typing import Optional


# FIXTURE_VERSION is checked by the real-worker test to confirm the file was read.
FIXTURE_VERSION = "plan3-fixture-v1"

# Bug: missing None check — real worker should identify this
def get_display_name(user: Optional[dict]) -> str:
    """Return the display name of a user dict.

    Known bug: crashes with AttributeError if user is None.
    The real worker should read this file and identify the issue.
    """
    return user["name"]  # BUG: no None check


def get_display_name_fixed(user: Optional[dict]) -> str:
    """Corrected version — safe None check."""
    if user is None:
        return "Anonymous"
    return user.get("name", "Anonymous")
