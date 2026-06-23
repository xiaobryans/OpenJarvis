#!/usr/bin/env python3
"""Plan 9 MacBook-off proof — cloud endpoints without local backend dependency."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

CLOUD = "https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com"
LOCAL = "http://127.0.0.1:8000"


def _cloud_key() -> str:
    import boto3

    sm = boto3.Session(profile_name="openclaw-admin").client(
        "secretsmanager", region_name="ap-southeast-1"
    )
    raw = sm.get_secret_value(SecretId="omnix-workbench-071179620006-ap-southeast-1-secrets")
    return json.loads(raw["SecretString"]).get("OPENJARVIS_API_KEY", "")


def _get(url: str, key: str, path: str) -> int:
    req = urllib.request.Request(
        f"{url}{path}",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main() -> int:
    key = _cloud_key()
    if not key:
        print("FAIL: cloud API key missing")
        return 1

    # Stop local backend if listening (safe for MacBook-off proof)
    stopped = subprocess.run(
        ["bash", "-c", "lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill 2>/dev/null; sleep 2; true"],
        check=False,
    )
    print(f"local_backend_stop_attempted exit={stopped.returncode}")

    local_down = True
    try:
        urllib.request.urlopen(f"{LOCAL}/health", timeout=2)
        local_down = False
    except Exception:
        pass
    print(f"local_backend_down={local_down}")

    paths = [
        "/health",
        "/v1/plan9/registry",
        "/v1/coding/workflow/status",
        "/v1/authority/audit",
        "/v1/model-routing/status",
        "/v1/coding/workspace",
        "/v1/mac-worker/status",
    ]
    results = {}
    for path in paths:
        code = _get(CLOUD, key, path)
        results[path] = code
        print(f"cloud {path} -> {code}")

    mac_worker = results.get("/v1/mac-worker/status", 0)
    cloud_ok = all(
        results[p] == 200
        for p in paths
        if p != "/v1/mac-worker/status"
    )
    print(f"mac_worker_status_http={mac_worker} (expected available, not routing cloud tasks to Mac by default)")
    print(f"OVERALL: {'PASS' if local_down and cloud_ok else 'HOLD'}")
    return 0 if local_down and cloud_ok else 1


if __name__ == "__main__":
    sys.exit(main())
