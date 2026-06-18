"""Doctor and readiness REST routes — Ultra Sprint 7.

Routes:
  GET /v1/doctor?project_id=omnix          — run all 12 diagnostic checks
  GET /v1/doctor/project?project_id=omnix  — project-specific checks only
  GET /v1/readiness?project_id=omnix       — readiness gate evaluation
  GET /v1/readiness/report?project_id=omnix — full V1 evidence summary
  GET /v1/version                          — app version, git commit, branch, build date
  GET /v1/limitations                      — structured known limitations list (US12)
  GET /v1/voice/status                     — full voice pipeline readiness (wake-word/STT/TTS/mic/hotkey)

Governance:
  - No secrets in any response
  - No real outbound sends
  - No auto-fix
  - Honest status: no fake green if backend unreachable
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for doctor routes")

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Internal helpers — version / limitations
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _get_git_commit() -> str:
    """Return current HEAD short SHA or 'unknown'."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_REPO_ROOT),
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _get_git_branch() -> str:
    """Return current branch name or 'unknown'."""
    try:
        out = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=str(_REPO_ROOT),
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode().strip() or "unknown"
    except Exception:
        return "unknown"


def _get_app_version() -> str:
    """Return app version from pyproject.toml or tauri.conf.json."""
    try:
        import importlib.metadata
        return importlib.metadata.version("OpenJarvis")
    except Exception:
        pass
    try:
        import json as _json
        tauri_conf = _REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
        if tauri_conf.exists():
            data = _json.loads(tauri_conf.read_text())
            return data.get("version", "unknown")
    except Exception:
        pass
    return "unknown"


_KNOWN_LIMITATIONS: List[Dict[str, str]] = [
    {
        "id": "wake_word",
        "category": "voice",
        "severity": "info",
        "title": "Wake-word requires explicit VoicePipeline.start() to activate",
        "description": (
            "OpenWakeWord is installed in the isolated .wake_worker_venv (Python 3.12). "
            "The wake-word listener is not started automatically. "
            "Input paths available: manual chat (always), push-to-talk hotkey (Cmd+Shift+Space), "
            "and true wake-word (requires VoicePipeline.start() or CLI start)."
        ),
        "workaround": (
            "To activate wake-word: run 'jarvis serve' with --voice flag, or call "
            "VoicePipeline.start() from Python. Push-to-talk hotkey (Cmd+Shift+Space) "
            "works without starting the listener."
        ),
    },
    {
        "id": "packaged_app_signing",
        "category": "distribution",
        "severity": "info",
        "title": "macOS app is ad-hoc signed (public notarization is FUTURE_BACKLOG)",
        "description": (
            "The V1 local/founder build uses ad-hoc signing ('-'). "
            "This is correct for local/founder distribution. Gatekeeper will prompt on first launch. "
            "Public Apple Developer ID notarization (for App Store / public distribution) "
            "is FUTURE_BACKLOG and is not required for V1."
        ),
        "workaround": "Right-click > Open on first launch, or run: xattr -dr com.apple.quarantine /Applications/OpenJarvis.app",
    },
    {
        "id": "connector_slack_live",
        "category": "connectors",
        "severity": "info",
        "title": "Slack live send requires private workspace token",
        "description": (
            "Slack connector status is backend-only. Live sends require a "
            "JARVIS_SLACK_BOT_TOKEN configured in the environment. "
            "No live sends are performed in plan-only or dry-run modes."
        ),
        "workaround": "Set JARVIS_SLACK_BOT_TOKEN and restart the server.",
    },
    {
        "id": "connector_telegram_live",
        "category": "connectors",
        "severity": "info",
        "title": "Telegram live send requires bot token",
        "description": (
            "Telegram connector status is backend-only. Live sends require "
            "JARVIS_TELEGRAM_BOT_TOKEN. No live sends are performed in "
            "plan-only or dry-run modes."
        ),
        "workaround": "Set JARVIS_TELEGRAM_BOT_TOKEN and restart the server.",
    },
    {
        "id": "desktop_permissions_macos",
        "category": "permissions",
        "severity": "info",
        "title": "macOS permissions must be granted manually",
        "description": (
            "Microphone, Accessibility, and Screen Recording permissions "
            "must be granted in System Settings > Privacy & Security. "
            "The app cannot request these on your behalf."
        ),
        "workaround": "Open System Settings > Privacy & Security and grant permissions for OpenJarvis.",
    },
    {
        "id": "us9_us12_backend_only",
        "category": "ui",
        "severity": "info",
        "title": "US9–US12 capabilities are backend-only",
        "description": (
            "Advanced capabilities (budget guard, inject guard, rollback policy, "
            "connector health monitor, alert rate limiter, memory backup, "
            "dogfood loop, trust layer, certification matrix) are fully "
            "implemented in the backend but not yet surfaced in the packaged "
            "app UI. They are accessible via the REST API."
        ),
        "workaround": "Use GET /v1/readiness/report and GET /v1/doctor for full status.",
    },
]


@router.get("/v1/doctor")
async def run_doctor(project_id: str = "omnix") -> Dict[str, Any]:
    """Run all 12 Jarvis diagnostic checks for a project.

    Returns pass/warn/fail/not_configured for each check with evidence.
    Never returns fake green status.
    """
    from openjarvis.doctor.checks import run_all_checks

    results = run_all_checks(project_id=project_id)
    by_status: Dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "project_id": project_id,
        "total_checks": len(results),
        "by_status": by_status,
        "checks": [r.to_dict() for r in results],
    }


@router.get("/v1/doctor/project")
async def run_doctor_project(project_id: str = "omnix") -> Dict[str, Any]:
    """Run project-specific diagnostic checks.

    Checks: project registry, git status, handoff freshness,
    packaged app metadata.
    """
    from openjarvis.doctor.checks import (
        check_git_worktree_status,
        check_handoff_freshness,
        check_packaged_app_build_metadata,
        check_project_registry_health,
    )

    checks = [
        check_project_registry_health(project_id),
        check_git_worktree_status(project_id),
        check_handoff_freshness(project_id),
        check_packaged_app_build_metadata(project_id),
    ]
    by_status: Dict[str, int] = {}
    for r in checks:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "project_id": project_id,
        "total_checks": len(checks),
        "by_status": by_status,
        "checks": [r.to_dict() for r in checks],
    }


@router.get("/v1/readiness")
async def evaluate_readiness(project_id: str = "omnix") -> Dict[str, Any]:
    """Evaluate Jarvis V1 daily-driver readiness gate for a project.

    8 categories, 4 verdicts: ready / warn / hold / unsafe.
    Never self-accepts without evidence.
    UNSAFE if safety/governance check fails.
    HOLD if required evidence is missing.
    """
    from openjarvis.doctor.readiness import evaluate_readiness as _eval

    report = _eval(project_id=project_id)
    return report.to_dict()


@router.get("/v1/readiness/report")
async def readiness_report(project_id: str = "omnix") -> Dict[str, Any]:
    """Generate full V1 readiness evidence summary.

    Includes: tool/skill/watchdog counts, accepted checkpoints,
    unsafe actions blocked, remaining limitations, post-V1 roadmap.
    """
    from openjarvis.doctor.readiness import generate_v1_report

    return generate_v1_report(project_id=project_id)


@router.get("/v1/version")
async def get_version() -> Dict[str, Any]:
    """Return app version, git commit, branch, and query timestamp.

    No secrets in response. Read-only git queries only.
    """
    return {
        "version": _get_app_version(),
        "git_commit": _get_git_commit(),
        "git_branch": _get_git_branch(),
        "queried_at": time.time(),
    }


@router.get("/v1/limitations")
async def get_limitations() -> Dict[str, Any]:
    """Return structured list of known Jarvis limitations.

    Each entry has: id, category, severity (warn/info), title,
    description, and workaround. No secrets in response.
    """
    categories = sorted({lim["category"] for lim in _KNOWN_LIMITATIONS})
    return {
        "total": len(_KNOWN_LIMITATIONS),
        "categories": categories,
        "limitations": _KNOWN_LIMITATIONS,
    }


@router.get("/v1/voice/status")
async def get_voice_status_endpoint() -> Dict[str, Any]:
    """Return full voice pipeline readiness.

    Covers: wake-word engine, STT, TTS, microphone, hotkey,
    manual-chatbox, and voice_readiness (READY/PARTIAL/HOLD).
    No secrets in response. No microphone started.
    """
    try:
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        status = get_voice_status()
        return {
            "voice_readiness": status.get("voice_readiness", "HOLD"),
            "voice_status": status.get("voice_status", "not_configured"),
            "readiness_reason": status.get("readiness_reason", ""),
            "summary": status.get("summary", ""),
            # Input paths
            "manual_chatbox_status": status.get("manual_chatbox_status", "available"),
            "hotkey_status": status.get("hotkey_status", "available"),
            "hotkey_binding": status.get("hotkey_binding", "cmd+shift+space"),
            # Wake-word
            "true_wakeword_status": status.get("true_wakeword_status", "not_configured"),
            "true_wakeword_worker_available": status.get("true_wakeword_worker_available", False),
            # STT / TTS
            "stt_status": status.get("stt_status", "not_configured"),
            "tts_status": status.get("tts_status", "not_configured"),
            # Microphone
            "microphone_status": status.get("microphone_status", "unknown"),
            # Approval pin
            "approval_pin_status": status.get("approval_pin_status", "not_set"),
            "queried_at": time.time(),
        }
    except Exception as exc:
        return {
            "voice_readiness": "HOLD",
            "voice_status": "error",
            "readiness_reason": f"Voice status check failed: {exc}",
            "summary": "Could not retrieve voice pipeline status.",
            "manual_chatbox_status": "available",
            "hotkey_status": "available",
            "hotkey_binding": "cmd+shift+space",
            "true_wakeword_status": "unknown",
            "true_wakeword_worker_available": False,
            "stt_status": "unknown",
            "tts_status": "unknown",
            "microphone_status": "unknown",
            "approval_pin_status": "not_set",
            "queried_at": time.time(),
        }


__all__ = ["router"]
