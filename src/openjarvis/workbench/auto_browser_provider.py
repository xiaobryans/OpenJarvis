"""US15 Auto Browser provider interface — connector layer only (not merged into core).

Source evaluated: https://github.com/LvcidPsyche/auto-browser
MCP-native browser agent with human-in-the-loop design.

Safety: rejects CAPTCHA bypass, credential extraction, deceptive automation,
unauthorized scraping, approval bypass, and uncontrolled autopilot.

Integration status: REQUIRES_USER_ACTION — see setup_steps in get_auto_browser_status().
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from typing import Any, Dict, List, Optional

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

SETUP_STEPS = [
    "1. Clone auto-browser: git clone https://github.com/LvcidPsyche/auto-browser ~/.openjarvis/auto-browser",
    "2. Install dependencies: cd ~/.openjarvis/auto-browser && pip install -e '.[mcp]'",
    "3. Install Playwright: playwright install chromium --with-deps",
    "4. Set env vars: export JARVIS_AUTO_BROWSER_ENABLED=1",
    "   Set: export JARVIS_AUTO_BROWSER_MCP_URL=http://localhost:8765",
    "5. Start auto-browser server: python -m auto_browser.server --port 8765",
    "6. Verify: curl http://localhost:8765/health → {\"status\": \"ok\"}",
    "7. Rerun: GET /v1/workbench/capabilities to see updated status",
]


def auto_browser_safety_allows(action: str) -> bool:
    """Return False for unsafe automation action classes."""
    normalized = action.lower().replace("-", "_").replace(" ", "_")
    return normalized not in BLOCKED_AUTOMATION_PATTERNS


def _playwright_available() -> bool:
    """Check if Playwright is installed and usable."""
    spec = importlib.util.find_spec("playwright")
    if spec is None:
        return False
    try:
        proc = subprocess.run(
            ["playwright", "install", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception:
        # playwright module exists but binary not on PATH — still usable via Python
        return True


def health_check() -> Dict[str, Any]:
    """Perform a local health check for browser automation readiness.

    Checks Playwright availability and Auto Browser MCP URL reachability (if configured).
    Never starts browser sessions or makes authenticated calls.
    """
    playwright_ok = _playwright_available()
    mcp_url = os.environ.get("JARVIS_AUTO_BROWSER_MCP_URL", "").strip()
    enabled = os.environ.get("JARVIS_AUTO_BROWSER_ENABLED", "").strip().lower() in ("1", "true", "yes")

    mcp_reachable = False
    mcp_error = ""
    if mcp_url:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{mcp_url.rstrip('/')}/health", timeout=3) as resp:
                mcp_reachable = resp.status == 200
        except Exception as exc:
            mcp_error = str(exc)[:120]

    return {
        "playwright_available": playwright_ok,
        "auto_browser_enabled": enabled,
        "mcp_url_configured": bool(mcp_url),
        "mcp_reachable": mcp_reachable,
        "mcp_error": mcp_error,
        "overall": "ready" if (playwright_ok and enabled and mcp_reachable) else "requires_setup",
    }


def session_status() -> Dict[str, Any]:
    """Return current browser session status (no session started by this call)."""
    mcp_url = os.environ.get("JARVIS_AUTO_BROWSER_MCP_URL", "").strip()
    if not mcp_url:
        return {
            "active_sessions": 0,
            "status": "no_mcp_configured",
            "note": "Set JARVIS_AUTO_BROWSER_MCP_URL to enable session tracking",
        }
    try:
        import urllib.request
        with urllib.request.urlopen(f"{mcp_url.rstrip('/')}/sessions", timeout=3) as resp:
            import json
            data = json.loads(resp.read().decode())
            return {"active_sessions": len(data.get("sessions", [])), "status": "ok", "data": data}
    except Exception as exc:
        return {"active_sessions": 0, "status": "unreachable", "error": str(exc)[:120]}


def get_auto_browser_status() -> Dict[str, Any]:
    """Return Auto Browser integration status with health check and setup steps."""
    enabled = os.environ.get("JARVIS_AUTO_BROWSER_ENABLED", "").strip().lower() in (
        "1", "true", "yes",
    )
    mcp_configured = bool(os.environ.get("JARVIS_AUTO_BROWSER_MCP_URL", "").strip())
    playwright_ok = _playwright_available()

    if enabled and mcp_configured:
        hc = health_check()
        integration_status = "ready" if hc["overall"] == "ready" else "requires_setup"
        return {
            "provider": "auto-browser",
            "source_repo": AUTO_BROWSER_REPO,
            "integration_status": integration_status,
            "summary": (
                "Auto Browser configured. MCP connector "
                + ("reachable — ready for approval-gated sessions." if hc["mcp_reachable"]
                   else "NOT reachable — start auto-browser server.")
            ),
            "merged_into_core": False,
            "blocked_patterns": BLOCKED_AUTOMATION_PATTERNS,
            "human_in_the_loop_required": True,
            "health_check": hc,
            "setup_steps": SETUP_STEPS if not hc["mcp_reachable"] else [],
        }

    hc = {
        "playwright_available": playwright_ok,
        "auto_browser_enabled": enabled,
        "mcp_url_configured": mcp_configured,
        "mcp_reachable": False,
        "overall": "requires_setup",
    }

    return {
        "provider": "auto-browser",
        "source_repo": AUTO_BROWSER_REPO,
        "integration_status": "requires_setup",
        "summary": (
            "Auto Browser not configured. "
            + ("Playwright installed — ready once MCP server configured. "
               if playwright_ok else "Playwright not installed — see setup steps. ")
            + "Follow setup_steps to complete integration."
        ),
        "merged_into_core": False,
        "evaluation": "metadata_only — full integration requires security review + MCP server setup",
        "blocked_patterns": BLOCKED_AUTOMATION_PATTERNS,
        "human_in_the_loop_required": True,
        "health_check": hc,
        "setup_steps": SETUP_STEPS,
    }


__all__ = [
    "AUTO_BROWSER_REPO",
    "BLOCKED_AUTOMATION_PATTERNS",
    "SETUP_STEPS",
    "auto_browser_safety_allows",
    "get_auto_browser_status",
    "health_check",
    "session_status",
]
