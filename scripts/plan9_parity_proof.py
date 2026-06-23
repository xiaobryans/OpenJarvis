#!/usr/bin/env python3
"""Plan 9 parity proof: memory sync, connectors, file read, broader workflow."""

from __future__ import annotations

import json
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

LOCAL = "http://127.0.0.1:8000"
CLOUD = "https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com"
MARKER = f"plan9-parity-{int(time.time())}"


def local_key() -> str:
    raw = tomllib.load((Path.home() / ".openjarvis/config.toml").open("rb"))
    return raw.get("server", {}).get("auth", {}).get("api_key") or raw.get("api_key", "")


def cloud_key() -> str:
    import boto3

    sm = boto3.Session(profile_name="openclaw-admin").client(
        "secretsmanager", region_name="ap-southeast-1"
    )
    raw = sm.get_secret_value(SecretId="omnix-workbench-071179620006-ap-southeast-1-secrets")
    return json.loads(raw["SecretString"])["OPENJARVIS_API_KEY"]


def call(base: str, method: str, path: str, key: str, body=None):
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read()[:300].decode("utf-8", "replace")}


def main() -> int:
    lk, ck = local_key(), cloud_key()
    report = {}

    # Memory parity item
    st, w = call(LOCAL, "POST", "/v1/memory", lk, {
        "content": f"Plan9 parity test {MARKER}",
        "namespace": "plan9_parity",
        "tags": ["plan9", "parity"],
    })
    report["local_write"] = st
    st, push = call(LOCAL, "POST", "/v1/memory/sync?mode=push&namespace=plan9_parity", lk)
    report["local_push"] = {"http": st, "ok": push.get("push", {}).get("ok")}

    st, pull = call(CLOUD, "POST", "/v1/memory/sync?mode=pull", ck)
    report["cloud_pull"] = {"http": st, "ok": pull.get("pull", {}).get("ok")}
    st, search = call(CLOUD, "GET", f"/v1/memory/search?query={MARKER}&namespace=plan9_parity", ck)
    report["cloud_search"] = {
        "http": st,
        "found": any(MARKER in (r.get("content") or "") for r in search.get("results", [])),
    }

    st_l, mem_l = call(LOCAL, "GET", "/v1/memory/status", lk)
    st_c, mem_c = call(CLOUD, "GET", "/v1/memory/status", ck)
    report["memory_counts"] = {
        "local": mem_l.get("memory_os", {}).get("total_entries"),
        "cloud": mem_c.get("memory_os", {}).get("total_entries"),
    }

    # File read parity
    for base, key, label in [(LOCAL, lk, "local"), (CLOUD, ck, "cloud")]:
        st, body = call(base, "POST", "/v1/coding/files/read", key, {
            "file_path": "docs/plan9_broader_workflow_proof.md",
            "start_line": 1,
            "end_line": 5,
        })
        report[f"file_read_{label}"] = {"http": st, "has_content": bool(body.get("content"))}

    st, blocked = call(CLOUD, "POST", "/v1/coding/files/read", ck, {"file_path": ".env"})
    report["file_read_blocked"] = blocked.get("http") if isinstance(blocked, dict) else st

    st, ws = call(CLOUD, "GET", "/v1/coding/workspace", ck)
    report["cloud_workspace"] = {
        "http": st,
        "root": ws.get("workspace_root"),
        "indexed": ws.get("indexed_file_count"),
    }

    # Connectors
    st_l, conn_l = call(LOCAL, "GET", "/v1/connectors", lk)
    st_c, conn_c = call(CLOUD, "GET", "/v1/connectors", ck)
    def summarize(data):
        items = data if isinstance(data, list) else data.get("connectors", [])
        connected = sum(1 for c in items if c.get("is_connected") or c.get("connected"))
        return {"total": len(items), "connected": connected}
    report["connectors"] = {"local": summarize(conn_l), "cloud": summarize(conn_c)}

    out = Path("evidence/plan9-parity-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    ok = (
        report.get("cloud_search", {}).get("found")
        and report.get("file_read_cloud", {}).get("http") == 200
        and report.get("file_read_local", {}).get("http") == 200
    )
    print("OVERALL:", "PASS" if ok else "HOLD")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
