#!/usr/bin/env python3
"""Plan 9 mobile/iPhone cloud path proof via Playwright mobile viewport + cloud API.

Note: This proves mobile-accessible cloud API/UI path from mobile viewport emulation.
Physical iPhone proof requires Bryan manual screenshot unless BrowserStack/device farm is configured.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FRONTEND = REPO / "frontend"
EVIDENCE = REPO / "evidence" / "plan9-mobile-proof"
CLOUD = "https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com"
PREVIEW_PORT = 5174


def _cloud_key() -> str:
    import boto3

    sm = boto3.Session(profile_name="openclaw-admin").client(
        "secretsmanager", region_name="ap-southeast-1"
    )
    raw = sm.get_secret_value(SecretId="omnix-workbench-071179620006-ap-southeast-1-secrets")
    return json.loads(raw["SecretString"]).get("OPENJARVIS_API_KEY", "")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL: playwright not installed")
        return 2

    key = _cloud_key()
    if not key:
        print("FAIL: cloud API key missing")
        return 1

    EVIDENCE.mkdir(parents=True, exist_ok=True)

    # Direct cloud API metadata proof (mobile-accessible)
    api_paths = [
        "/health",
        "/v1/plan9/registry",
        "/v1/authority/approvals/pending",
        "/v1/authority/audit",
        "/v1/coding/workflow/status",
        "/v1/model-routing/status",
        "/v1/memory/rust-status",
    ]
    api_report = {}
    for path in api_paths:
        req = urllib.request.Request(
            f"{CLOUD}{path}",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                api_report[path] = {"http": r.status, "reachable": True}
        except Exception as e:
            api_report[path] = {"http": getattr(e, "code", None), "reachable": False}
    (EVIDENCE / "mobile_api_report.json").write_text(json.dumps(api_report, indent=2))

    dist = FRONTEND / "dist" / "index.html"
    if not dist.is_file():
        subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND), check=True)

    preview = subprocess.Popen(
        ["npm", "run", "preview", "--", "--host", "127.0.0.1", "--port", str(PREVIEW_PORT)],
        cwd=str(FRONTEND),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PREVIEW_PORT}/mobile", timeout=2)
                break
            except Exception:
                time.sleep(0.5)

        mobile_settings = json.dumps({"apiUrl": CLOUD, "apiKey": key})
        with sync_playwright() as p:
            iphone = p.devices["iPhone 13"]
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**iphone)
            context.add_init_script(
                f"localStorage.setItem('jarvis_mobile_backend_url', {json.dumps(CLOUD)});"
                f"localStorage.setItem('jarvis_mobile_api_key', {json.dumps(key)});"
                f"localStorage.setItem('openjarvis-settings', {json.dumps(mobile_settings)});"
            )
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{PREVIEW_PORT}/mobile", wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(4000)
            text = page.inner_text("body")
            shot = EVIDENCE / "mobile-iphone-viewport.png"
            page.screenshot(path=str(shot), full_page=True)
            browser.close()

        ui_ok = "cloud" in text.lower() or "remote" in text.lower() or "health" in text.lower()
        api_ok = all(v.get("http") == 200 for v in api_report.values() if "/health" not in v or True)
        api_ok = api_report.get("/health", {}).get("http") == 200 and all(
            v.get("http") == 200 for k, v in api_report.items() if k != "/health"
        )
        report = {
            "api_ok": api_ok,
            "ui_ok": ui_ok,
            "screenshot": str(shot.relative_to(REPO)),
            "physical_iphone_proven": False,
            "note": "Mobile viewport emulation + public cloud URL; physical iPhone not in CI",
        }
        (EVIDENCE / "mobile_report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        print(f"OVERALL: {'PASS_EMULATED' if api_ok and ui_ok else 'HOLD'}")
        return 0 if api_ok and ui_ok else 1
    finally:
        preview.terminate()
        preview.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
