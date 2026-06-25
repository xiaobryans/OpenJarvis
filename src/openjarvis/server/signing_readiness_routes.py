"""Signing Readiness routes — Phase C16.

C16 — macOS Signing / Notarization Readiness Gate.
Surfaces toolchain and env-presence-based readiness for macOS code signing
and notarization. No signing or notarization is ever performed here.

Routes:
  GET  /v1/signing-readiness/status                   — overall signing readiness
  GET  /v1/signing-readiness/prerequisites             — individual prerequisite checks
  GET  /v1/signing-readiness/notarization-assessment  — notarization deferral state

Governance:
  - fake_data is always False
  - fake_notarization is always False
  - actual_signing_run is always False
  - actual_notarization_run is always False
  - no_secret_values_in_response is always True
  - All env checks are presence-only: os.environ.get("KEY") — never printed
  - Developer ID cert presence confirmed by Bryan; not read programmatically
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for signing readiness routes")

log = logging.getLogger(__name__)

router = APIRouter(tags=["signing-readiness"])

__all__ = ["router"]


def _tool(cmd: str) -> bool:
    """Return True if command is available on PATH. No output produced."""
    return shutil.which(cmd) is not None


def _env_present(key: str) -> bool:
    """Return True if the env var is set and non-empty. Never prints the value."""
    return bool(os.environ.get(key))


@router.get("/v1/signing-readiness/status")
async def signing_readiness_status() -> Dict[str, Any]:
    """Return overall macOS signing and notarization readiness state.

    No signing or notarization is performed. All credential checks are
    presence-only — no values are read or returned in the response.
    Developer ID cert presence confirmed by Bryan; not read programmatically.
    """
    return {
        "notarytool_present": _tool("notarytool") or _tool("xcrun"),
        "stapler_present": _tool("stapler") or _tool("xcrun"),
        "apple_api_issuer_present": _env_present("APPLE_API_ISSUER"),
        "apple_api_key_present": _env_present("APPLE_API_KEY"),
        "apple_api_key_path_present": _env_present("APPLE_API_KEY_PATH"),
        "apple_team_id_present": _env_present("APPLE_TEAM_ID"),
        "apple_signing_identity_present": _env_present("APPLE_SIGNING_IDENTITY"),
        "prerequisites_bryan_cleared": True,
        "actual_signing_run": False,
        "actual_notarization_run": False,
        "signing_deferred": True,
        "signing_deferred_reason": (
            "No stable build artifact in current sprint scope. "
            "Actual sign/notarize requires completed DMG build."
        ),
        "notarization_claimed": False,
        "public_release_ready": False,
        "fake_notarization": False,
        "fake_data": False,
        "no_secret_values_in_response": True,
        "note": "All credential checks are presence-only. No values read or printed.",
    }


@router.get("/v1/signing-readiness/prerequisites")
async def signing_readiness_prerequisites() -> Dict[str, Any]:
    """Return individual prerequisite checks for macOS signing.

    Developer ID cert presence confirmed by Bryan — not read programmatically.
    All env checks are presence-only.
    """
    prerequisites: List[Dict[str, Any]] = [
        {
            "id": "notarytool",
            "name": "notarytool available",
            "present": _tool("notarytool") or _tool("xcrun"),
            "bryan_cleared": True,
        },
        {
            "id": "stapler",
            "name": "stapler available",
            "present": _tool("stapler") or _tool("xcrun"),
            "bryan_cleared": True,
        },
        {
            "id": "apple_api_issuer",
            "name": "APPLE_API_ISSUER",
            "present": _env_present("APPLE_API_ISSUER"),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "apple_api_key",
            "name": "APPLE_API_KEY",
            "present": _env_present("APPLE_API_KEY"),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "apple_api_key_path",
            "name": "APPLE_API_KEY_PATH",
            "present": _env_present("APPLE_API_KEY_PATH"),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "apple_team_id",
            "name": "APPLE_TEAM_ID",
            "present": _env_present("APPLE_TEAM_ID"),
            "bryan_cleared": True,
            "presence_only": True,
        },
        {
            "id": "developer_id_cert",
            "name": "Developer ID Application certificate",
            "present": True,
            "bryan_cleared": True,
            "note": "Presence confirmed by Bryan; not read programmatically",
        },
    ]

    blocking = [p for p in prerequisites if not p["present"]]

    return {
        "prerequisites": prerequisites,
        "all_bryan_cleared": True,
        "blocking_count": len(blocking),
        "fake_data": False,
    }


@router.get("/v1/signing-readiness/notarization-assessment")
async def signing_readiness_notarization_assessment() -> Dict[str, Any]:
    """Return notarization readiness assessment.

    Notarization is NOT run here. A completed macOS DMG/app bundle build
    artifact is required before notarization can proceed.
    """
    apple_creds_all_present = all([
        _env_present("APPLE_API_ISSUER"),
        _env_present("APPLE_API_KEY"),
        _env_present("APPLE_API_KEY_PATH"),
        _env_present("APPLE_TEAM_ID"),
    ])

    return {
        "assessment": "ready_when_build_available",
        "all_credentials_present": apple_creds_all_present,
        "toolchain_present": _tool("notarytool") or _tool("xcrun"),
        "build_artifact_available": False,
        "deferred_reason": (
            "No completed macOS DMG build in current sprint. "
            "Notarization requires a signed .app bundle."
        ),
        "notarization_run_this_sprint": False,
        "fake_notarized": False,
        "fake_data": False,
    }
