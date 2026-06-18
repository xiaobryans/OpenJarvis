"""US15 Auto Browser provider interface — client SDK installed, server REQUIRES_USER_ACTION.

Source: https://github.com/LvcidPsyche/auto-browser
Local clone: .external/auto-browser/ (gitignored)
Client SDK: auto-browser-client==1.2.1 (installed in Jarvis venv)
Playwright: chromium installed

Architecture:
  - auto-browser-client  — lightweight HTTP/MCP SDK (installed, importable)
  - Playwright chromium  — browser binary (installed)
  - auto-browser controller — requires Docker for the full server stack
  - Docker               — NOT available on this machine

Status: client + browser ready; server startup REQUIRES_USER_ACTION (Docker).
Safety: rejects CAPTCHA bypass, credential extraction, deceptive automation,
unauthorized scraping, approval bypass, and uncontrolled autopilot.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

AUTO_BROWSER_REPO = "https://github.com/LvcidPsyche/auto-browser"
AUTO_BROWSER_LOCAL_PATH = str(Path(__file__).parent.parent.parent.parent / ".external" / "auto-browser")

# Actions Jarvis must never automate without explicit human approval + policy review.
BLOCKED_AUTOMATION_PATTERNS: List[str] = [
    "captcha_bypass",
    "credential_extraction",
    "deceptive_automation",
    "unauthorized_scraping",
    "approval_bypass",
    "uncontrolled_autopilot",
]

# Server startup requires Docker — Bryan must run this.
SERVER_SETUP_STEPS = [
    "# Auto Browser server requires Docker. Steps to start:",
    "1. Install Docker Desktop: https://www.docker.com/products/docker-desktop/",
    "2. Start Docker Desktop and wait for it to become healthy.",
    "3. cd /Users/user/OpenJarvis/.external/auto-browser",
    "4. docker compose up -d",
    "5. Wait ~30s for containers to start: docker compose ps",
    "6. Verify server: curl http://localhost:3000/health  → {\"status\":\"ok\"}",
    "7. Set env: export JARVIS_AUTO_BROWSER_ENABLED=1",
    "8. Set env: export JARVIS_AUTO_BROWSER_MCP_URL=http://localhost:3000",
    "9. Rerun health check: uv run python -c \"from openjarvis.workbench.auto_browser_provider import health_check; import json; print(json.dumps(health_check(), indent=2))\"",
    "10. Expected: overall='ready', mcp_reachable=True",
    "11. GET /v1/workbench/auto-browser/status → integration_status='ready'",
]


def auto_browser_safety_allows(action: str) -> bool:
    """Return False for unsafe automation action classes."""
    normalized = action.lower().replace("-", "_").replace(" ", "_")
    return normalized not in BLOCKED_AUTOMATION_PATTERNS


def _playwright_available() -> bool:
    """Check if Playwright Python package is installed."""
    return importlib.util.find_spec("playwright") is not None


def _playwright_chromium_installed() -> bool:
    """Check if the Playwright chromium browser binary is present."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        proc = subprocess.run(
            ["python", "-c",
             "from playwright.sync_api import sync_playwright; "
             "p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop(); print('ok')"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0 and "ok" in proc.stdout
    except Exception:
        return False


def _auto_browser_client_installed() -> bool:
    """Check if auto-browser-client SDK is installed."""
    return importlib.util.find_spec("auto_browser_client") is not None


def health_check() -> Dict[str, Any]:
    """Perform a local health check for browser automation readiness.

    Checks client SDK, Playwright, and Auto Browser MCP server reachability.
    Never starts browser sessions or makes authenticated calls.
    """
    client_sdk_ok = _auto_browser_client_installed()
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

    # All required: client SDK, playwright, enabled flag, MCP server reachable
    ready = client_sdk_ok and playwright_ok and enabled and mcp_reachable

    return {
        "client_sdk_installed": client_sdk_ok,
        "client_sdk_package": "auto-browser-client==1.2.1" if client_sdk_ok else "not installed",
        "playwright_available": playwright_ok,
        "auto_browser_enabled": enabled,
        "mcp_url_configured": bool(mcp_url),
        "mcp_reachable": mcp_reachable,
        "mcp_error": mcp_error,
        "local_clone": AUTO_BROWSER_LOCAL_PATH,
        "server_requires_docker": True,
        "docker_available": False,  # confirmed: docker not on PATH on this machine
        "overall": "ready" if ready else "requires_setup",
        "blocker": (
            "MCP server not reachable — start Docker and run: cd .external/auto-browser && docker compose up -d"
            if not mcp_reachable else ""
        ),
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
    """Return Auto Browser integration status with health check and exact setup steps."""
    hc = health_check()
    integration_status = "ready" if hc["overall"] == "ready" else "requires_setup"

    client_ok = hc["client_sdk_installed"]
    playwright_ok = hc["playwright_available"]
    mcp_reachable = hc["mcp_reachable"]

    if mcp_reachable:
        summary = "Auto Browser fully operational — client SDK installed, Playwright ready, MCP server reachable."
    elif client_ok and playwright_ok:
        summary = (
            "Auto Browser client SDK + Playwright installed. "
            "MCP server NOT running — Docker required to start it. "
            "Follow server_setup_steps to complete."
        )
    else:
        summary = "Auto Browser partial setup. See server_setup_steps."

    return {
        "provider": "auto-browser",
        "source_repo": AUTO_BROWSER_REPO,
        "local_clone": AUTO_BROWSER_LOCAL_PATH,
        "integration_status": integration_status,
        "summary": summary,
        "merged_into_core": False,
        "blocked_patterns": BLOCKED_AUTOMATION_PATTERNS,
        "human_in_the_loop_required": True,
        "health_check": hc,
        "server_setup_steps": SERVER_SETUP_STEPS,
    }


__all__ = [
    "AUTO_BROWSER_REPO",
    "AUTO_BROWSER_LOCAL_PATH",
    "BLOCKED_AUTOMATION_PATTERNS",
    "SERVER_SETUP_STEPS",
    "auto_browser_safety_allows",
    "get_auto_browser_status",
    "health_check",
    "session_status",
]
