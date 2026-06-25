"""iOS Readiness routes — Phase C15.

C15 — Native iOS / Mobile App Readiness Gate.
Surfaces presence-based prerequisite checks for iOS build toolchain.
tauri ios init is explicitly deferred pending Bryan authorization per CLAUDE.md
rebuild constraint.

Routes:
  GET  /v1/ios-readiness/status               — overall iOS readiness state
  GET  /v1/ios-readiness/prerequisites        — individual prerequisite checks
  GET  /v1/ios-readiness/tauri-init-assessment — tauri ios init deferral status

Governance:
  - fake_data is always False
  - fake_ios_readiness is always False
  - native_ios_app_ready is False until tauri ios init is run
  - tauri_ios_init_run is always False until Bryan explicitly authorizes
  - All subprocess calls are read-only tool detection (shutil.which / version check)
  - No secret values are ever returned
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for ios readiness routes")

log = logging.getLogger(__name__)

router = APIRouter(tags=["ios-readiness"])

__all__ = ["router"]


def _cmd_present(cmd: str) -> bool:
    """Return True if the command is available on PATH. No output produced."""
    return shutil.which(cmd) is not None


def _xcode_version() -> str:
    """Return the first line of xcodebuild -version output, or 'unknown' on any error.
    Read-only detection only — no build or install actions.
    """
    try:
        result = subprocess.run(
            ["xcodebuild", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = result.stdout.strip().split("\n")[0] if result.stdout else ""
        return first_line  # e.g. "Xcode 16.4"
    except Exception:
        return "unknown"


def _rust_ios_targets() -> List[str]:
    """Return installed rustup targets that include 'ios' or 'aarch64-apple'.
    Read-only detection only — no installs.
    """
    try:
        result = subprocess.run(
            ["rustup", "target", "list", "--installed"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        return [line for line in lines if "ios" in line.lower() or "aarch64-apple" in line.lower()]
    except Exception:
        return []


@router.get("/v1/ios-readiness/status")
async def ios_readiness_status() -> Dict[str, Any]:
    """Return overall iOS build readiness state.

    tauri ios init is explicitly deferred — it is NOT run here.
    native_ios_app_ready is False until tauri ios init is run with Bryan's authorization.
    All tool checks are read-only (shutil.which / subprocess version query).
    """
    ios_targets = _rust_ios_targets()

    return {
        "xcode_present": _cmd_present("xcodebuild"),
        "xcode_version": _xcode_version(),
        "cocoapods_present": _cmd_present("pod"),
        "rust_present": _cmd_present("rustup") or _cmd_present("cargo"),
        "ios_rust_targets": ios_targets,
        "ios_rust_targets_count": len(ios_targets),
        "prerequisites_bryan_cleared": True,
        "tauri_ios_init_run": False,
        "tauri_ios_init_deferred": True,
        "tauri_ios_init_deferred_reason": (
            "Unrelated dirty files in repo + CLAUDE.md rebuild constraint "
            "requires explicit Bryan authorization"
        ),
        "native_ios_app_ready": False,
        "testflight_ready": False,
        "app_store_ready": False,
        "fake_ios_readiness": False,
        "fake_data": False,
        "note": (
            "Prerequisites cleared by Bryan. tauri ios init deferred "
            "pending explicit authorization."
        ),
    }


@router.get("/v1/ios-readiness/prerequisites")
async def ios_readiness_prerequisites() -> Dict[str, Any]:
    """Return individual prerequisite checks for iOS build readiness.

    Apple certificates presence confirmed by Bryan — not read programmatically.
    All tool checks are read-only (shutil.which / rustup target list).
    """
    ios_targets = _rust_ios_targets()

    prerequisites: List[Dict[str, Any]] = [
        {
            "id": "xcode",
            "name": "Xcode 16.4",
            "present": _cmd_present("xcodebuild"),
            "bryan_cleared": True,
        },
        {
            "id": "xcode_license",
            "name": "Xcode license",
            "present": True,
            "bryan_cleared": True,
        },
        {
            "id": "ios_rust_targets",
            "name": "iOS Rust targets",
            "present": len(ios_targets) > 0,
            "bryan_cleared": True,
        },
        {
            "id": "cocoapods",
            "name": "CocoaPods",
            "present": _cmd_present("pod"),
            "bryan_cleared": True,
        },
        {
            "id": "apple_certs",
            "name": "Apple certificates",
            "present": True,
            "bryan_cleared": True,
            "note": "Presence confirmed by Bryan; values not read",
        },
    ]

    blocking = [p for p in prerequisites if not p["present"]]

    return {
        "prerequisites": prerequisites,
        "bryan_cleared_all": True,
        "blocking_prerequisites": len(blocking),
        "fake_data": False,
    }


@router.get("/v1/ios-readiness/tauri-init-assessment")
async def ios_readiness_tauri_init_assessment() -> Dict[str, Any]:
    """Return the deferral assessment for tauri ios init.

    tauri ios init is NOT run here. Explicit Bryan authorization is required
    per CLAUDE.md rebuild constraint before this command may be executed.
    """
    return {
        "assessment": "deferred",
        "reason": (
            "Explicit Bryan authorization required per CLAUDE.md rebuild constraint"
        ),
        "would_create_files_in": [
            "src-tauri/gen/apple/",
            "src-tauri/Cargo.toml changes",
        ],
        "safe_to_run_when": (
            "All unrelated dirty files resolved AND Bryan explicitly authorizes tauri ios init"
        ),
        "ran_in_this_sprint": False,
        "fake_data": False,
    }
