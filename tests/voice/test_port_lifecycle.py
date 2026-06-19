"""Targeted tests for the backend single-instance / port lifecycle logic.

Tests:
- _check_port_lifecycle: FREE when nothing is listening
- _check_port_lifecycle: REUSE when healthy compatible OpenJarvis backend found
- _check_port_lifecycle: RESTARTED when OpenJarvis stale/wrong-config
- _check_port_lifecycle: FOREIGN when non-OpenJarvis process
- _check_port_lifecycle: FOREIGN for non-JSON response
- SIGTERM is sent to the stale OpenJarvis PID (not to other PIDs)
- /health returns version and git_commit fields
"""
from __future__ import annotations

import json
import os
import signal
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers to spin up a tiny HTTP server in a background thread
# ---------------------------------------------------------------------------


def _make_json_server(port: int, response_body: dict | str, status: int = 200):
    """Spin up a one-shot HTTP server returning the given response on /health."""
    if isinstance(response_body, dict):
        body_bytes = json.dumps(response_body).encode()
    else:
        body_bytes = response_body.encode()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body_bytes)

        def log_message(self, fmt, *args):  # suppress noise
            pass

    server = HTTPServer(("127.0.0.1", port), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _free_port() -> int:
    """Find an OS-assigned free TCP port."""
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Tests for _check_port_lifecycle (Python / CLI path)
# ---------------------------------------------------------------------------


def test_lifecycle_free_when_nothing_listening():
    """FREE when port is not in use."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    decision, msg = _check_port_lifecycle("127.0.0.1", port, "ollama", "qwen3.5:2b")
    assert decision == _PortDecision.FREE
    assert msg == ""


def test_lifecycle_reuse_compatible_openjarvis():
    """REUSE when healthy OpenJarvis with matching engine+model is found."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    fingerprint = {
        "status": "ok",
        "app": "openjarvis",
        "pid": 12345,
        "engine": "ollama",
        "model": "qwen3.5:2b",
        "git_commit": "abc1234",
        "stt_provider": "deepgram",
        "tts_provider": "deepgram",
    }
    server = _make_json_server(port, fingerprint)
    try:
        decision, msg = _check_port_lifecycle("127.0.0.1", port, "ollama", "qwen3.5:2b")
    finally:
        server.shutdown()

    assert decision == _PortDecision.REUSE, f"Expected REUSE, got {decision}: {msg}"
    assert "Reusing" in msg
    assert "12345" in msg


def test_lifecycle_reuse_empty_engine_name():
    """REUSE even when caller passes empty engine/model (no constraint)."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    fingerprint = {
        "status": "ok",
        "app": "openjarvis",
        "pid": 99,
        "engine": "lmstudio",
        "model": "deepseek",
        "git_commit": "abc",
        "stt_provider": "deepgram",
    }
    server = _make_json_server(port, fingerprint)
    try:
        decision, msg = _check_port_lifecycle("127.0.0.1", port, "", "")
    finally:
        server.shutdown()

    assert decision == _PortDecision.REUSE


def test_lifecycle_restart_wrong_engine():
    """RESTARTED when engine doesn't match, sends SIGTERM to existing PID."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    fake_pid = 99999  # non-existent PID — SIGTERM will raise ProcessLookupError
    fingerprint = {
        "status": "ok",
        "app": "openjarvis",
        "pid": fake_pid,
        "engine": "ollama",
        "model": "qwen3.5:2b",
        "git_commit": "abc",
    }
    server = _make_json_server(port, fingerprint)
    sigterm_calls = []

    original_kill = os.kill

    def fake_kill(pid, sig):
        sigterm_calls.append((pid, sig))
        # Don't actually send signal to a real PID
        raise ProcessLookupError(f"fake kill {pid}")

    try:
        with patch("os.kill", side_effect=fake_kill):
            decision, msg = _check_port_lifecycle("127.0.0.1", port, "lmstudio", "qwen3.5:2b")
    finally:
        server.shutdown()

    assert decision == _PortDecision.RESTARTED, f"Expected RESTARTED, got {decision}: {msg}"
    assert "Stopping stale" in msg
    assert any(pid == fake_pid and sig == signal.SIGTERM for pid, sig in sigterm_calls), \
        f"Expected SIGTERM to {fake_pid}, got: {sigterm_calls}"


def test_lifecycle_restart_wrong_model():
    """RESTARTED when model doesn't match."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    fingerprint = {
        "status": "ok",
        "app": "openjarvis",
        "pid": 88888,
        "engine": "ollama",
        "model": "llama3:8b",
        "git_commit": "abc",
    }
    server = _make_json_server(port, fingerprint)
    try:
        with patch("os.kill", side_effect=ProcessLookupError):
            decision, msg = _check_port_lifecycle("127.0.0.1", port, "ollama", "qwen3.5:2b")
    finally:
        server.shutdown()

    assert decision == _PortDecision.RESTARTED
    assert "model" in msg


def test_lifecycle_restart_unhealthy():
    """RESTARTED when OpenJarvis reports status != ok (503)."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    fingerprint = {
        "status": "degraded",
        "app": "openjarvis",
        "pid": 77777,
        "engine": "ollama",
        "model": "qwen3.5:2b",
    }
    server = _make_json_server(port, fingerprint)
    try:
        with patch("os.kill", side_effect=ProcessLookupError):
            decision, msg = _check_port_lifecycle("127.0.0.1", port, "ollama", "qwen3.5:2b")
    finally:
        server.shutdown()

    assert decision == _PortDecision.RESTARTED


def test_lifecycle_foreign_non_openjarvis():
    """FOREIGN when /health response doesn't identify as openjarvis."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    # nginx / some other service
    other_response = {"status": "ok", "service": "nginx"}
    server = _make_json_server(port, other_response)
    try:
        decision, msg = _check_port_lifecycle("127.0.0.1", port, "ollama", "qwen3.5:2b")
    finally:
        server.shutdown()

    assert decision == _PortDecision.FOREIGN
    assert "non-OpenJarvis" in msg
    assert "lsof" in msg


def test_lifecycle_foreign_non_json():
    """FOREIGN when /health returns non-JSON (e.g. HTML 200)."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    server = _make_json_server(port, "<html>some other app</html>")
    try:
        decision, msg = _check_port_lifecycle("127.0.0.1", port, "ollama", "qwen3.5:2b")
    finally:
        server.shutdown()

    assert decision == _PortDecision.FOREIGN
    assert "lsof" in msg


def test_lifecycle_foreign_pid_not_killed():
    """FOREIGN: os.kill is never called for a foreign process."""
    from openjarvis.cli.serve import _check_port_lifecycle, _PortDecision

    port = _free_port()
    foreign = {"status": "ok", "service": "postgres"}
    server = _make_json_server(port, foreign)
    kill_calls = []

    try:
        with patch("os.kill", side_effect=lambda pid, sig: kill_calls.append((pid, sig))):
            decision, _ = _check_port_lifecycle("127.0.0.1", port, "ollama", "qwen3.5")
    finally:
        server.shutdown()

    assert decision == _PortDecision.FOREIGN
    assert kill_calls == [], f"os.kill was called for foreign process: {kill_calls}"


# ---------------------------------------------------------------------------
# /health fingerprint fields
# ---------------------------------------------------------------------------


def test_health_returns_version_and_git_commit():
    """The /health endpoint must include version and git_commit fields."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.routes import router

    app = FastAPI()
    engine = MagicMock()
    engine.health.return_value = True
    app.state.engine = engine
    app.state.session_start = time.time()
    app.state.engine_name = "ollama"
    app.state.model = "qwen3.5:2b"
    app.include_router(router)

    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data, f"Missing 'version' in /health: {data}"
    assert "git_commit" in data, f"Missing 'git_commit' in /health: {data}"
    # Values may be "unknown" in a test env without git, but must be strings
    assert isinstance(data["version"], str)
    assert isinstance(data["git_commit"], str)


def test_health_fingerprint_app_is_openjarvis():
    """app field must be exactly 'openjarvis' for the lifecycle check to work."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from openjarvis.server.routes import router

    app = FastAPI()
    engine = MagicMock()
    engine.health.return_value = True
    app.state.engine = engine
    app.state.session_start = time.time()
    app.state.engine_name = "ollama"
    app.state.model = "qwen3.5:2b"
    app.include_router(router)

    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.json()["app"] == "openjarvis"
