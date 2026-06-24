"""Mobile / iOS / Productization Status Routes.

Routes:
  GET /v1/productization/status     — unified mobile/iOS/PWA/App Store status
  GET /v1/productization/ios        — iOS-specific breakdown
  GET /v1/productization/mobile     — mobile web/PWA readiness

Design rules:
  - Honest reporting only. No fake App Store readiness.
  - Apple Developer Account is an EXTERNAL release gate, not a fake code blocker.
  - Native iOS scaffold status is reported separately from PWA status.
  - All status fields reflect actual implementation state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi required for productization routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["productization"])


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

_MOBILE_WEB_STATUS: Dict[str, Any] = {
    "type": "mobile_web_pwa",
    "status": "implemented",
    "description": "PWA shell with offline support, install prompt, and mobile-first responsive layout.",
    "features": [
        "PWA manifest (name, short_name, display=standalone, icons)",
        "Service worker with Workbox offline caching",
        "Apple touch icon (180x180)",
        "192x192 and 512x512 PWA icons",
        "Mobile-first responsive layout (Tailwind)",
        "Mobile page /mobile with cloud API connectivity",
        "Plan 2 mobile/MacBook-off parity endpoints (/v1/mobile-parity/*)",
    ],
    "plan": "Plan 2 (accepted)",
    "proof": "manifest.webmanifest present; pwa-192x192.png, pwa-512x512.png, sw.js present",
}

_IOS_NATIVE_STATUS: Dict[str, Any] = {
    "type": "native_ios",
    "status": "not_scaffolded",
    "description": (
        "A Tauri desktop scaffold exists at frontend/src-tauri/ for macOS/Windows/Linux only. "
        "The iOS target has NOT been initialized — no ios/ directory, no iOS Xcode project, "
        "no iOS bundle section in tauri.conf.json (identifier: com.openjarvis.desktop), "
        "and no iOS-specific Rust dependencies. "
        "To scaffold iOS support: run 'tauri ios init', then enroll an Apple Developer Account. "
        "App Store distribution is an external release gate, not an internal code blocker."
    ),
    "scaffold_status": "not_scaffolded",
    "desktop_scaffold_status": "present",
    "desktop_scaffold_path": "frontend/src-tauri/",
    "build_requirements": [
        "Run 'tauri ios init' to configure the iOS target (not yet done)",
        "Xcode 15+ (macOS only)",
        "Apple Developer Account (enrollment required for distribution)",
        "iOS provisioning profile",
    ],
    "external_gates": {
        "apple_developer_account": "EXTERNAL — Bryan must confirm enrollment",
        "tauri_ios_init": "PENDING — iOS target not yet initialized",
        "app_store_submission": "EXTERNAL — requires review by Apple",
        "testflight_distribution": "EXTERNAL — requires Developer Account",
    },
    "implemented_in_code": [
        "frontend/src-tauri/ Tauri desktop project (macOS/Windows/Linux only)",
        "Mobile-responsive frontend tested locally",
        "PWA manifest for installable web app (Plan 2)",
    ],
    "plan": "Plan 4-5",
    "proof": "frontend/src-tauri/ is a desktop-only Tauri project (com.openjarvis.desktop); no iOS bundle or target configured",
}

_APP_STORE_STATUS: Dict[str, Any] = {
    "type": "app_store",
    "status": "not_submitted",
    "description": "App Store submission has not been attempted. Requires: enrolled Apple Developer Account, app review, privacy nutrition label.",
    "external_gates": {
        "apple_developer_account": "EXTERNAL",
        "app_review": "EXTERNAL",
        "privacy_nutrition_label": "pending",
        "testflight": "not_set_up",
    },
    "fake_claim": False,
    "note": "Do not claim App Store ready until TestFlight distribution is proven.",
}

_PRODUCTIZATION_GATES: List[Dict[str, Any]] = [
    {
        "gate": "pwa_installable",
        "status": "PASS",
        "evidence": "manifest.webmanifest, service worker, icons present",
    },
    {
        "gate": "mobile_responsive_ui",
        "status": "PASS",
        "evidence": "Tailwind mobile-first layout; MobilePage component",
    },
    {
        "gate": "mobile_api_parity",
        "status": "PASS",
        "evidence": "Plan 2 /v1/mobile-parity/* endpoints accepted",
    },
    {
        "gate": "desktop_scaffold",
        "status": "PASS",
        "evidence": "frontend/src-tauri/ present; Tauri desktop project configured for macOS/Windows/Linux",
    },
    {
        "gate": "ios_scaffold",
        "status": "NOT_STARTED",
        "evidence": "iOS target not initialized; 'tauri ios init' has not been run; no ios/ directory present",
    },
    {
        "gate": "apple_developer_account",
        "status": "EXTERNAL_GATE",
        "evidence": "Bryan must confirm enrollment — not a code blocker",
    },
    {
        "gate": "app_store_submission",
        "status": "NOT_STARTED",
        "evidence": "External gate: Apple Developer Account required first",
    },
    {
        "gate": "testflight_distribution",
        "status": "NOT_STARTED",
        "evidence": "External gate: Apple Developer Account required first",
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/productization/status")
async def productization_status() -> Dict[str, Any]:
    """Unified mobile/iOS/PWA/App Store productization status.

    Reports what is actually implemented vs what is externally blocked.
    Never claims App Store readiness unless proven.
    """
    pass_count = sum(1 for g in _PRODUCTIZATION_GATES if g["status"] == "PASS")
    external_count = sum(1 for g in _PRODUCTIZATION_GATES if g["status"] == "EXTERNAL_GATE")
    not_started_count = sum(1 for g in _PRODUCTIZATION_GATES if g["status"] == "NOT_STARTED")
    return {
        "mobile_web_pwa": _MOBILE_WEB_STATUS,
        "native_ios": _IOS_NATIVE_STATUS,
        "app_store": _APP_STORE_STATUS,
        "gates": _PRODUCTIZATION_GATES,
        "summary": {
            "gates_total": len(_PRODUCTIZATION_GATES),
            "gates_pass": pass_count,
            "gates_external": external_count,
            "gates_not_started": not_started_count,
            "pwa_ready": True,
            "desktop_scaffold_ready": True,
            "ios_scaffold_ready": False,
            "app_store_ready": False,
            "fake_claims": False,
        },
        "next_steps": [
            "Run 'tauri ios init' to configure the iOS target in frontend/src-tauri/",
            "Bryan confirms Apple Developer Account enrollment",
            "Set up TestFlight distribution",
            "Privacy nutrition label + App Store submission",
        ],
    }


@router.get("/v1/productization/ios")
async def ios_status() -> Dict[str, Any]:
    """iOS-specific productization breakdown."""
    return {
        "native_ios": _IOS_NATIVE_STATUS,
        "app_store": _APP_STORE_STATUS,
        "summary": "Tauri desktop scaffold present (macOS/Windows/Linux). iOS target not yet initialized — run 'tauri ios init' to begin. Distribution requires Apple Developer enrollment (external gate).",
    }


@router.get("/v1/productization/mobile")
async def mobile_status() -> Dict[str, Any]:
    """Mobile web / PWA readiness status."""
    return {
        "mobile_web_pwa": _MOBILE_WEB_STATUS,
        "responsive_ui": True,
        "api_parity": True,
        "installable": True,
        "summary": "Mobile web/PWA is fully implemented and accepted (Plan 2).",
    }


__all__ = ["router"]
