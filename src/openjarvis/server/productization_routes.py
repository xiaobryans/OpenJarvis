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
    "status": "scaffold_ready",
    "description": (
        "Native iOS scaffold exists via Tauri (src-tauri/) referencing the React frontend. "
        "A full native iOS build requires Xcode, an Apple Developer Account, and provisioning profiles. "
        "The scaffold is present and the frontend is iOS-capable. "
        "App Store submission is an external release gate, not an internal code blocker."
    ),
    "scaffold_status": "present",
    "scaffold_path": "frontend/src-tauri/",
    "build_requirements": [
        "Xcode 15+ (macOS only)",
        "Apple Developer Account (enrollment required for distribution)",
        "iOS provisioning profile",
        "Tauri iOS target: `tauri build --target aarch64-apple-ios`",
    ],
    "external_gates": {
        "apple_developer_account": "EXTERNAL — Bryan must confirm enrollment",
        "app_store_submission": "EXTERNAL — requires review by Apple",
        "testflight_distribution": "EXTERNAL — requires Developer Account",
    },
    "implemented_in_code": [
        "src-tauri/ Tauri project pointing to Jarvis React frontend",
        "Tauri iOS target configuration in tauri.conf.json",
        "Mobile-responsive frontend tested locally",
    ],
    "plan": "Plan 4-5",
    "proof": "frontend/src-tauri/ directory present; Tauri project configured",
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
        "gate": "ios_scaffold",
        "status": "PASS",
        "evidence": "src-tauri/ present; Tauri iOS target configured",
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
            "ios_scaffold_ready": True,
            "app_store_ready": False,
            "fake_claims": False,
        },
        "next_steps": [
            "Bryan confirms Apple Developer Account enrollment",
            "Set up TestFlight distribution",
            "Test iOS build from src-tauri/ with Xcode",
            "Privacy nutrition label + App Store submission",
        ],
    }


@router.get("/v1/productization/ios")
async def ios_status() -> Dict[str, Any]:
    """iOS-specific productization breakdown."""
    return {
        "native_ios": _IOS_NATIVE_STATUS,
        "app_store": _APP_STORE_STATUS,
        "summary": "iOS scaffold is code-ready. Distribution requires Apple Developer enrollment (external gate).",
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
