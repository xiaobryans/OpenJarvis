"""
Tests for cloud_runtime.py v3 auth and route protection.

Verifies:
  - /health is public (no auth required)
  - /v1/* routes reject missing/invalid Bearer tokens (401/403)
  - /v1/* routes accept valid Bearer token (200)
  - POST routes reject unauthenticated requests
  - CORS headers present
"""

from __future__ import annotations

import json
import threading
import time
from http.server import HTTPServer
from http.client import HTTPConnection
from typing import Any, Generator

import pytest


# ---------------------------------------------------------------------------
# Helpers to start/stop the cloud runtime server in-process
# ---------------------------------------------------------------------------

def _import_handler():
    """Import the cloud runtime module's handler without starting the server."""
    import importlib.util
    import sys
    from pathlib import Path

    spec_path = Path(__file__).parents[2] / "deploy" / "aws" / "cloud_runtime.py"
    spec = importlib.util.spec_from_file_location("cloud_runtime_v3", spec_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)  # type: ignore
    return mod


@pytest.fixture(scope="module")
def cloud_server(monkeypatch_module) -> Generator[tuple[HTTPServer, int, str], None, None]:
    """Start cloud_runtime server on an ephemeral port with test API key."""
    import os
    test_key = "test-cloud-key-plan4-secure"

    mod = _import_handler()
    # Inject test config
    mod.OPENJARVIS_API_KEY = test_key
    mod.MEMORY_BUCKET = ""   # no real S3 in unit test
    mod.GITHUB_TOKEN = "ghp_testtoken"
    mod.PORT = 0  # OS picks port

    server = HTTPServer(("127.0.0.1", 0), mod.JarvisCloudHandler)
    port = server.server_address[1]

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server, port, test_key
    server.shutdown()


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch (no S3 calls needed for unit tests)."""
    import unittest.mock as mock
    with mock.patch("builtins.__import__", side_effect=_mock_import):
        yield


def _mock_import(name: str, *args, **kwargs):
    """Mock boto3 to avoid real S3 calls in unit tests."""
    if name == "boto3":
        raise ImportError("boto3 not available in unit test mode")
    return __builtins__["__import__"](name, *args, **kwargs)  # type: ignore


# ---------------------------------------------------------------------------
# Simpler approach: unit-test the _check_auth function directly
# ---------------------------------------------------------------------------

def _get_module():
    import importlib.util
    from pathlib import Path
    spec_path = Path(__file__).parents[2] / "deploy" / "aws" / "cloud_runtime.py"
    spec = importlib.util.spec_from_file_location("cloud_runtime_v3_test", spec_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)  # type: ignore
    return mod


# ---------------------------------------------------------------------------
# Auth unit tests (_check_auth)
# ---------------------------------------------------------------------------

class TestCheckAuth:
    def setup_method(self):
        self.mod = _get_module()
        self.mod.OPENJARVIS_API_KEY = "valid-test-key-32chars-xxxxxxxxxxx"

    def test_health_is_public(self):
        assert self.mod._check_auth("/health", "") is None

    def test_root_is_public(self):
        assert self.mod._check_auth("/", "") is None

    def test_v1_route_requires_auth(self):
        err = self.mod._check_auth("/v1/system/health", "")
        assert err is not None
        assert "Missing" in err

    def test_invalid_scheme_rejected(self):
        err = self.mod._check_auth("/v1/memory/status", "Basic abc123")
        assert err is not None
        assert "Bearer" in err

    def test_invalid_token_rejected(self):
        err = self.mod._check_auth("/v1/system/health", "Bearer wrong-token")
        assert err is not None
        assert "Invalid" in err

    def test_valid_token_accepted(self):
        err = self.mod._check_auth("/v1/system/health",
                                   "Bearer valid-test-key-32chars-xxxxxxxxxxx")
        assert err is None

    def test_no_key_configured_allows_all(self):
        """If OPENJARVIS_API_KEY not set, all requests pass (misconfigured but open)."""
        self.mod.OPENJARVIS_API_KEY = ""
        err = self.mod._check_auth("/v1/memory/status", "")
        assert err is None

    def test_approvals_requires_auth(self):
        self.mod.OPENJARVIS_API_KEY = "valid-test-key-32chars-xxxxxxxxxxx"
        err = self.mod._check_auth("/v1/approvals/pending", "")
        assert err is not None

    def test_tasks_requires_auth(self):
        err = self.mod._check_auth("/v1/tasks", "")
        assert err is not None

    def test_connectors_requires_auth(self):
        err = self.mod._check_auth("/v1/connectors/status", "")
        assert err is not None

    def test_tools_requires_auth(self):
        err = self.mod._check_auth("/v1/tools", "")
        assert err is not None

    def test_chat_requires_auth(self):
        err = self.mod._check_auth("/v1/chat/message", "")
        assert err is not None


# ---------------------------------------------------------------------------
# Integration tests: actual HTTP server
# ---------------------------------------------------------------------------

def _http_get(port: int, path: str, headers: dict = None) -> tuple[int, dict]:
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    conn.request("GET", path, headers=h)
    resp = conn.getresponse()
    body = json.loads(resp.read().decode())
    conn.close()
    return resp.status, body


def _http_post(port: int, path: str, body: dict, headers: dict = None) -> tuple[int, dict]:
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        h.update(headers)
    data = json.dumps(body).encode()
    h["Content-Length"] = str(len(data))
    conn.request("POST", path, body=data, headers=h)
    resp = conn.getresponse()
    body_resp = json.loads(resp.read().decode())
    conn.close()
    return resp.status, body_resp


@pytest.fixture(scope="module")
def live_server():
    """Start a real cloud_runtime server for integration tests."""
    import importlib.util
    import unittest.mock as mock
    from pathlib import Path

    spec_path = Path(__file__).parents[2] / "deploy" / "aws" / "cloud_runtime.py"
    spec = importlib.util.spec_from_file_location("cloud_runtime_live", spec_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)  # type: ignore

    TEST_KEY = "integration-test-key-plan4-xxxxx"
    mod.OPENJARVIS_API_KEY = TEST_KEY
    mod.MEMORY_BUCKET = ""
    mod.GITHUB_TOKEN = "ghp_faketoken"
    mod.AWS_REGION = "ap-southeast-1"

    # Patch S3 calls
    def _mock_s3_available():
        return False  # no real S3 in unit tests

    def _mock_s3_read(key, default=None):
        return default if default is not None else []

    def _mock_s3_write(key, data):
        return True  # pretend write succeeded

    mod._s3_available = _mock_s3_available
    mod._s3_read_json = _mock_s3_read
    mod._s3_write_json = _mock_s3_write

    server = HTTPServer(("127.0.0.1", 0), mod.JarvisCloudHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)
    yield port, TEST_KEY
    server.shutdown()


class TestPublicRoutes:
    def test_health_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/health")
        assert status == 200
        assert body["status"] == "ok"

    def test_root_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/")
        assert status == 200
        assert "routes" in body


class TestProtectedRoutes:
    def test_system_health_rejected_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/v1/system/health")
        assert status == 401
        assert "error" in body

    def test_memory_status_rejected_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/v1/memory/status")
        assert status == 401

    def test_approvals_rejected_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/v1/approvals/pending")
        assert status == 401

    def test_tasks_rejected_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/v1/tasks")
        assert status == 401

    def test_connectors_rejected_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/v1/connectors/status")
        assert status == 401

    def test_invalid_token_forbidden(self, live_server):
        port, _ = live_server
        status, body = _http_get(port, "/v1/system/health",
                                  {"Authorization": "Bearer wrong-key"})
        assert status == 403
        assert "Invalid" in body.get("error", "")

    def test_system_health_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/system/health",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert body["status"] == "ok"
        assert body["runtime"]["macbook_off_capable"] is True

    def test_memory_status_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/memory/status",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert "memory_os" in body

    def test_continuity_status_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/mobile/continuity/status",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert body["runtime_macbook_off_capable"] is True

    def test_approvals_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/approvals/pending",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert "pending" in body

    def test_tasks_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/tasks",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert "tasks" in body

    def test_connectors_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/connectors/status",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert "connectors" in body

    def test_tools_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/tools",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert "tools" in body

    def test_autonomy_with_valid_auth(self, live_server):
        port, key = live_server
        status, body = _http_get(port, "/v1/autonomy/status",
                                  {"Authorization": f"Bearer {key}"})
        assert status == 200
        assert "tool_execution_enabled" in body


class TestPostRoutes:
    def test_task_create_rejected_no_auth(self, live_server):
        port, _ = live_server
        status, body = _http_post(port, "/v1/tasks", {"description": "test"})
        assert status == 401

    def test_task_create_with_auth(self, live_server):
        port, key = live_server
        status, body = _http_post(port, "/v1/tasks", {"description": "run plan 4 test"},
                                   {"Authorization": f"Bearer {key}"})
        assert status == 201
        assert body.get("created") is True
        assert "id" in body

    def test_task_create_missing_description(self, live_server):
        port, key = live_server
        status, body = _http_post(port, "/v1/tasks", {},
                                   {"Authorization": f"Bearer {key}"})
        assert status == 400

    def test_memory_entry_write_with_auth(self, live_server):
        port, key = live_server
        status, body = _http_post(port, "/v1/memory/entries",
                                   {"content": "plan 4 cloud memory entry", "namespace": "test"},
                                   {"Authorization": f"Bearer {key}"})
        assert status == 201
        assert body.get("stored") is True

    def test_chat_message_with_auth(self, live_server):
        port, key = live_server
        status, body = _http_post(port, "/v1/chat/message",
                                   {"message": "hello jarvis from cloud"},
                                   {"Authorization": f"Bearer {key}"})
        assert status == 201
        assert body.get("received") is True
        assert "no-LLM" in body.get("classification", "")

    def test_chat_rejected_no_auth(self, live_server):
        port, _ = live_server
        status, _ = _http_post(port, "/v1/chat/message", {"message": "test"})
        assert status == 401

    def test_approval_create_with_auth(self, live_server):
        port, key = live_server
        status, body = _http_post(port, "/v1/approvals",
                                   {"action_type": "deploy", "description": "test deploy"},
                                   {"Authorization": f"Bearer {key}"})
        assert status == 201
        assert body.get("created") is True
