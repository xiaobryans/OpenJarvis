"""US15 Auto Browser provider interface — connector layer only (not merged into core).

Source evaluated: https://github.com/LvcidPsyche/auto-browser
MCP-native browser agent with human-in-the-loop design.

Safety: rejects CAPTCHA bypass, credential extraction, deceptive automation,
unauthorized scraping, approval bypass, and uncontrolled autopilot.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

AUTO_BROWSER_REPO = "https://github.com/LvcidPsyche/auto-browser"

# Actions Jarvis must never automate without explicit human approval + policy review.
BLOCKED_AUTOMATION_PATTERNS: List[str] = [
    "captcha_bypass",
    "credential_extraction",
    "deceptive_automation",
    "unauthorized_scraping",
    "approval_bypass",
    "uncontrolled_autopilot",
]


def auto_browser_safety_allows(action: str) -> bool:
    """Return False for unsafe automation action classes."""
    normalized = action.lower().replace("-", "_").replace(" ", "_")
    return normalized not in BLOCKED_AUTOMATION_PATTERNS


def get_auto_browser_status() -> Dict[str, Any]:
    """Return Auto Browser integration status without fetching external code."""
    enabled = os.environ.get("JARVIS_AUTO_BROWSER_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    mcp_configured = bool(os.environ.get("JARVIS_AUTO_BROWSER_MCP_URL", "").strip())

    if enabled and mcp_configured:
        return {
            "provider": "auto-browser",
            "source_repo": AUTO_BROWSER_REPO,
            "integration_status": "requires_setup",
            "summary": (
                "Auto Browser env flags set but connector not live-proven in Jarvis. "
                "Use Playwright tools or complete MCP connector setup."
            ),
            "merged_into_core": False,
            "blocked_patterns": BLOCKED_AUTOMATION_PATTERNS,
            "human_in_the_loop_required": True,
        }

    return {
        "provider": "auto-browser",
        "source_repo": AUTO_BROWSER_REPO,
        "integration_status": "blocked",
        "summary": (
            "Auto Browser not integrated — provider interface only. "
            "Set JARVIS_AUTO_BROWSER_ENABLED=1 and JARVIS_AUTO_BROWSER_MCP_URL after review. "
            "Existing Playwright browser tools remain the supported path."
        ),
        "merged_into_core": False,
        "evaluation": "metadata_only — not merged without security review",
        "blocked_patterns": BLOCKED_AUTOMATION_PATTERNS,
        "human_in_the_loop_required": True,
    }


__all__ = [
    "AUTO_BROWSER_REPO",
    "BLOCKED_AUTOMATION_PATTERNS",
    "auto_browser_safety_allows",
    "get_auto_browser_status",
]
