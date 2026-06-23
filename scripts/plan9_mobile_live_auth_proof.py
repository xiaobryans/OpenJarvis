#!/usr/bin/env python3
"""Live AWS mobile auth proof — Playwright WebKit against public cloud /mobile URL.

Uses Secrets Manager key in browser localStorage only (never printed).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "evidence" / "plan9-mobile-proof"
CLOUD = "https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com"


def _cloud_key() -> str:
    raw = subprocess.check_output(
        [
            "aws", "secretsmanager", "get-secret-value",
            "--secret-id", "omnix-workbench-071179620006-ap-southeast-1-secrets",
            "--region", "ap-southeast-1",
            "--profile", "openclaw-admin",
            "--query", "SecretString", "--output", "text",
        ],
        text=True,
    )
    return json.loads(raw).get("OPENJARVIS_API_KEY", "")


def _run_case(page, label: str, stored: str) -> dict:
    page.evaluate("localStorage.clear()")
    page.evaluate("(k) => localStorage.setItem('jarvis_mobile_api_key', k)", stored)
    page.click('button.secondary[onclick="testApiKey()"]')
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    verdict_ok = "AUTHENTICATED" in text and "HTTP 200" in text
    return {
        "case": label,
        "verdict_ok": verdict_ok,
        "has_token_mismatch": "token_mismatch" in text,
        "has_header_mode": "Authorization: Bearer" in text,
    }


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL: playwright not installed")
        return 2

    key = _cloud_key()
    if not key:
        print("FAIL: cloud API key missing in Secrets Manager")
        return 1

    build = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], text=True, cwd=str(REPO)
    ).strip()

    EVIDENCE.mkdir(parents=True, exist_ok=True)

    url = f"{CLOUD}/health/mobile-proof?v={build}"
    report: dict = {"url": url, "build": build, "cases": []}

    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        report["build_marker_visible"] = build in body or "Mobile build" in body
        report["not_react_page"] = "AWS Always-On" not in body.split("SW-safe URL")[0]
        report["header_mode_visible"] = "Header mode" in body

        report["cases"].append(_run_case(page, "raw_key", key))
        report["cases"].append(_run_case(page, "bearer_prefixed", f"Bearer {key}"))
        report["cases"].append(_run_case(page, "whitespace_padded", f"  {key}  "))

        shot = EVIDENCE / "mobile-live-webkit-auth.png"
        page.screenshot(path=str(shot), full_page=True)
        report["screenshot"] = str(shot.relative_to(REPO))
        browser.close()

    raw_ok = report["cases"][0]["verdict_ok"]
    bearer_ok = report["cases"][1]["verdict_ok"]
    report["overall"] = (
        "PASS" if raw_ok and bearer_ok and report["build_marker_visible"] else "HOLD"
    )
    out = EVIDENCE / "mobile_live_auth_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"OVERALL: {report['overall']}")
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
