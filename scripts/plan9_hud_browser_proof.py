#!/usr/bin/env python3
"""Plan 9 HUD browser visual + DOM/API parity proof.

Uses Playwright against vite preview with live local backend on :8000.
Writes screenshots and a JSON report to evidence/plan9-hud-proof/.
Never prints secret values.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent
FRONTEND = REPO / "frontend"
EVIDENCE = REPO / "evidence" / "plan9-hud-proof"
API_BASE = "http://127.0.0.1:8000"
PREVIEW_PORT = 5173
PREVIEW_URL = f"http://127.0.0.1:{PREVIEW_PORT}"

HUD_ROUTES: List[Tuple[str, str, str]] = [
    ("cockpit", "/", "Jarvis Cockpit HUD"),
    ("mission-control", "/mission-control", "Mission Control"),
    ("authority", "/authority", "Authority"),
    ("workbench", "/workbench", "Workbench"),
    ("connectors", "/data-sources", "Connectors"),
    ("agents", "/agents", "Agents"),
    ("logs", "/logs", "Logs/Audit"),
    ("settings", "/settings", "Settings/API target"),
    ("mobile", "/mobile", "Mobile cloud path"),
]


def _load_api_key() -> str:
    cfg = Path.home() / ".openjarvis" / "config.toml"
    with cfg.open("rb") as f:
        raw = tomllib.load(f)
    return raw.get("server", {}).get("auth", {}).get("api_key") or raw.get("api_key", "")


def _api_get(path: str, key: str) -> Tuple[int, Any]:
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read()[:200].decode("utf-8", "replace")}


def fetch_api_snapshot(key: str) -> Dict[str, Any]:
    snap: Dict[str, Any] = {}
    endpoints = {
        "health": "/health",
        "registry": "/v1/plan9/registry",
        "approvals": "/v1/authority/approvals/pending",
        "audit": "/v1/authority/audit?limit=5",
        "workflow": "/v1/coding/workflow/status",
        "connectors": "/v1/connectors",
        "memory": "/v1/memory/status",
        "routing": "/v1/model-routing/status",
        "plan9_capabilities": "/v1/capabilities/matrix-summary",
    }
    for name, path in endpoints.items():
        code, body = _api_get(path, key)
        snap[name] = {"http": code, "body": body}
    return snap


def _check_health() -> bool:
    try:
        with urllib.request.urlopen(f"{API_BASE}/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def _ensure_frontend_built() -> None:
    dist = FRONTEND / "dist" / "index.html"
    if dist.is_file():
        return
    subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND), check=True)


def _start_preview() -> subprocess.Popen:
    env = {
        **dict(subprocess.os.environ),
        "VITE_API_URL": API_BASE,
    }
    return subprocess.Popen(
        ["npm", "run", "preview", "--", "--host", "127.0.0.1", "--port", str(PREVIEW_PORT)],
        cwd=str(FRONTEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_preview(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(PREVIEW_URL, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _forbidden_ui_markers(text: str) -> List[str]:
    bad = []
    if "Loading…" in text or "Loading..." in text:
        bad.append("generic_loading")
    if "0/?" in text:
        bad.append("zero_slash_question")
    if "All connected" in text and "connected" in text.lower():
        # flag only if contradictory with disconnected markers
        if "disconnected" in text.lower() or "error" in text.lower():
            bad.append("contradictory_all_connected")
    return bad


def _dismiss_overlays(page) -> None:
    """Close onboarding/savings modals that block HUD panels."""
    for label in ("No Thanks", "Close", "✕ close", "Skip"):
        try:
            btn = page.get_by_role("button", name=label)
            if btn.count() > 0:
                btn.first.click(timeout=2000)
                page.wait_for_timeout(500)
        except Exception:
            pass
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        pass


def _parity_checks(slug: str, snap: Dict[str, Any], page_text: str) -> List[str]:
    issues: List[str] = []
    reg = snap.get("registry", {}).get("body", {})
    if slug == "cockpit" and isinstance(reg, dict):
        for field in ("total_roles", "total_managers", "total_workers"):
            val = reg.get(field)
            if val is not None and str(val) not in page_text:
                issues.append(f"missing_registry_{field}_{val}")
    if slug in ("authority", "cockpit"):
        audit = snap.get("audit", {}).get("body", {})
        if isinstance(audit, dict):
            tc = audit.get("total_count")
            if tc is not None and int(tc) > 0:
                if str(tc) not in page_text and "audit" not in page_text.lower():
                    issues.append(f"missing_audit_total_count_{tc}")
    if slug == "workbench":
        wf = snap.get("workflow", {}).get("body", {})
        if isinstance(wf, dict) and wf.get("last_workflow") and "workflow" not in page_text.lower():
            issues.append("missing_workflow_status")
    return issues


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL: playwright not installed — run: uv pip install playwright && playwright install chromium")
        return 2

    if not _check_health():
        print(f"FAIL: local backend not reachable at {API_BASE}/health")
        return 1

    key = _load_api_key()
    if not key:
        print("FAIL: OPENJARVIS_API_KEY not found in ~/.openjarvis/config.toml")
        return 1

    snap = fetch_api_snapshot(key)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "api_snapshot.json").write_text(json.dumps(snap, indent=2))

    _ensure_frontend_built()
    preview = _start_preview()
    report: Dict[str, Any] = {"routes": {}, "issues": [], "passed": False}
    try:
        if not _wait_preview():
            report["issues"].append("preview_unavailable")
            print("FAIL: vite preview did not start")
            return 1

        settings = {"apiUrl": API_BASE, "apiKey": key}
        settings_js = json.dumps(json.dumps(settings))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.add_init_script(
                f"localStorage.setItem('openjarvis-settings', {settings_js});"
            )
            page = context.new_page()

            for slug, route, label in HUD_ROUTES:
                route_report: Dict[str, Any] = {"label": label, "route": route}
                try:
                    page.goto(f"{PREVIEW_URL}{route}", wait_until="networkidle", timeout=60000)
                    _dismiss_overlays(page)
                    wait_ms = 15000 if slug == "connectors" else 3500
                    page.wait_for_timeout(wait_ms)
                    text = page.inner_text("body")
                    route_report["text_len"] = len(text)
                    route_report["forbidden_markers"] = _forbidden_ui_markers(text)
                    route_report["parity_issues"] = _parity_checks(slug, snap, text)
                    shot = EVIDENCE / f"{slug}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    route_report["screenshot"] = str(shot.relative_to(REPO))
                    route_report["ok"] = (
                        not route_report["forbidden_markers"] and not route_report["parity_issues"]
                    )
                except Exception as exc:
                    route_report["ok"] = False
                    route_report["error"] = type(exc).__name__
                report["routes"][slug] = route_report

            browser.close()

        all_ok = all(r.get("ok") for r in report["routes"].values())
        report["passed"] = all_ok
        (EVIDENCE / "hud_report.json").write_text(json.dumps(report, indent=2))

        print(f"HUD proof report: {EVIDENCE / 'hud_report.json'}")
        for slug, r in report["routes"].items():
            status = "OK" if r.get("ok") else "HOLD"
            print(f"  {slug}: {status} screenshot={r.get('screenshot', 'n/a')}")
            if r.get("forbidden_markers"):
                print(f"    forbidden: {r['forbidden_markers']}")
            if r.get("parity_issues"):
                print(f"    parity: {r['parity_issues']}")
        print(f"OVERALL: {'PASS' if all_ok else 'HOLD'}")
        return 0 if all_ok else 1
    finally:
        preview.terminate()
        preview.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
