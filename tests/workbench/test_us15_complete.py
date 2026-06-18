"""US15 complete integration tests — repo index, GitHub/CI, auto browser, capabilities."""

from __future__ import annotations

import pytest


class TestRepoIndexComplete:
    def test_has_js_ts_symbols(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        # May be empty if no JS/TS files, but attribute must exist
        assert isinstance(idx.js_ts_symbols, list)

    def test_has_test_files(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        assert len(idx.test_files) > 0
        assert any("test_" in f for f in idx.test_files)

    def test_has_config_files(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        assert len(idx.config_files) > 0

    def test_has_ignored_paths(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        assert len(idx.ignored_paths) > 0
        assert any(".git" in p for p in idx.ignored_paths)

    def test_has_freshness_metadata(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        assert "built_at" in idx.freshness
        assert "file_count" in idx.freshness
        assert "py_symbol_count" in idx.freshness
        assert idx.freshness["file_count"] > 0

    def test_to_dict_has_all_fields(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        d = idx.to_dict()
        required_keys = {
            "repo_path", "file_count", "files", "symbols", "symbol_count",
            "js_ts_symbols", "js_ts_symbol_count", "dependencies",
            "subsystems", "test_files", "test_file_count", "config_files",
            "ignored_paths", "freshness",
        }
        assert required_keys.issubset(d.keys())

    def test_python_symbols_include_classes_and_functions(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        kinds = {s.kind for s in idx.symbols}
        assert "class" in kinds or "function" in kinds

    def test_dependencies_from_pyproject(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        assert len(idx.dependencies) > 0


class TestCIVisibility:
    def test_ci_status_has_required_fields(self):
        from openjarvis.workbench.repo_index import ci_visibility_status

        ci = ci_visibility_status(".")
        assert "status" in ci
        assert ci["status"] in ("ready", "requires_setup")
        assert "gh_cli_authenticated" in ci
        assert "workflow_files" in ci

    def test_ci_authenticated_has_live_data(self):
        from openjarvis.workbench.repo_index import ci_visibility_status

        ci = ci_visibility_status(".")
        if ci["gh_cli_authenticated"]:
            # Should have workflow runs and PR status
            assert "workflow_runs" in ci or "workflow_files" in ci

    def test_workflow_files_found(self):
        from openjarvis.workbench.repo_index import ci_visibility_status
        from pathlib import Path

        ci = ci_visibility_status(".")
        if Path(".github/workflows").exists():
            assert len(ci["workflow_files"]) > 0
            assert ci["status"] in ("ready", "requires_setup")


class TestAutoBrowserComplete:
    def test_health_check_returns_dict(self):
        from openjarvis.workbench.auto_browser_provider import health_check

        hc = health_check()
        assert "playwright_available" in hc
        assert "auto_browser_enabled" in hc
        assert "mcp_url_configured" in hc
        assert "mcp_reachable" in hc
        assert "overall" in hc
        assert hc["overall"] in ("ready", "requires_setup")
        assert "client_sdk_installed" in hc
        assert hc["client_sdk_installed"] is True  # installed via PyPI
        # docker_available is diagnostic only — must not force requires_setup
        assert "docker_available" in hc

    def test_docker_unavailable_does_not_block_ready(self, monkeypatch):
        """docker_available=False must not force overall=requires_setup when server reachable."""
        import urllib.request
        from openjarvis.workbench import auto_browser_provider as abp

        monkeypatch.setenv("JARVIS_AUTO_BROWSER_ENABLED", "1")
        monkeypatch.setenv("JARVIS_AUTO_BROWSER_MCP_URL", "http://127.0.0.1:3000")

        class _FakeResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b'{"status":"ok"}'

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResp())

        hc = abp.health_check()
        # With server reachable, overall must be ready regardless of docker_available value
        assert hc["mcp_reachable"] is True
        assert hc["overall"] == "ready"

    def test_healthz_probe_succeeds(self, monkeypatch):
        """/healthz response marks server reachable."""
        import urllib.request
        from openjarvis.workbench import auto_browser_provider as abp

        monkeypatch.setenv("JARVIS_AUTO_BROWSER_ENABLED", "1")
        monkeypatch.setenv("JARVIS_AUTO_BROWSER_MCP_URL", "http://127.0.0.1:3000")

        probed = []

        class _FakeResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(url, **kw):
            probed.append(str(url))
            return _FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        hc = abp.health_check()
        assert hc["mcp_reachable"] is True
        # Must probe /healthz first (not /health)
        assert any("/healthz" in p for p in probed)
        assert not any(p.endswith("/health") for p in probed), \
            f"Should not probe /health — got {probed}"

    def test_health_404_does_not_fail_if_healthz_succeeds(self, monkeypatch):
        """/health 404 is irrelevant — provider probes /healthz, /readyz, /openapi.json."""
        import urllib.request
        from urllib.error import HTTPError
        from openjarvis.workbench import auto_browser_provider as abp

        monkeypatch.setenv("JARVIS_AUTO_BROWSER_ENABLED", "1")
        monkeypatch.setenv("JARVIS_AUTO_BROWSER_MCP_URL", "http://127.0.0.1:3000")

        class _OkResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(url, **kw):
            if str(url).endswith("/health"):
                raise HTTPError(str(url), 404, "Not Found", {}, None)
            return _OkResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        hc = abp.health_check()
        # /healthz should succeed even if /health 404s
        assert hc["mcp_reachable"] is True

    def test_session_status_returns_dict(self):
        from openjarvis.workbench.auto_browser_provider import session_status

        ss = session_status()
        assert "active_sessions" in ss
        assert "status" in ss

    def test_get_status_has_setup_steps(self):
        from openjarvis.workbench.auto_browser_provider import get_auto_browser_status

        status = get_auto_browser_status()
        assert "server_setup_steps" in status or "setup_steps" in status
        assert "health_check" in status
        assert "blocked_patterns" in status
        assert isinstance(status["blocked_patterns"], list)

    def test_safety_still_enforced(self):
        from openjarvis.workbench.auto_browser_provider import auto_browser_safety_allows

        assert auto_browser_safety_allows("captcha_bypass") is False
        assert auto_browser_safety_allows("credential_extraction") is False
        assert auto_browser_safety_allows("deceptive_automation") is False
        assert auto_browser_safety_allows("unauthorized_scraping") is False
        assert auto_browser_safety_allows("approval_bypass") is False
        assert auto_browser_safety_allows("uncontrolled_autopilot") is False
        assert auto_browser_safety_allows("file_read") is True
        assert auto_browser_safety_allows("navigate") is True

    def test_status_not_ready_without_config(self):
        import os
        from openjarvis.workbench.auto_browser_provider import get_auto_browser_status

        enabled = os.environ.get("JARVIS_AUTO_BROWSER_ENABLED", "")
        mcp = os.environ.get("JARVIS_AUTO_BROWSER_MCP_URL", "")
        if not enabled or not mcp:
            status = get_auto_browser_status()
            assert status["integration_status"] in ("requires_setup", "blocked")


class TestCapabilitiesComplete:
    def test_all_seven_capabilities_present(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities

        caps = get_all_capabilities()
        ids = {c.capability_id for c in caps}
        required = {
            "assistant", "workbench_coding", "reviewer_validator",
            "voice", "browser_automation", "research", "automation",
        }
        assert ids == required

    def test_no_fake_ready_statuses(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY

        caps = get_all_capabilities()
        for cap in caps:
            if cap.status == STATUS_READY:
                # Ready caps must have evidence
                assert cap.evidence, f"{cap.capability_id} claims ready but has no evidence"

    def test_voice_is_disabled_and_parked(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities

        voice = next(c for c in get_all_capabilities() if c.capability_id == "voice")
        assert voice.status == "disabled"
        assert voice.evidence.get("hands_free_excluded") is True
        assert "US13" in voice.summary or "HOLD" in voice.summary

    def test_workbench_is_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities

        wb = next(c for c in get_all_capabilities() if c.capability_id == "workbench_coding")
        assert wb.status == "ready"


class TestContextCacheIntegration:
    def test_warm_cache_and_retrieve(self, tmp_path, monkeypatch):
        from openjarvis.workbench.context_cache import ContextCache, warm_repo_map_cache

        db = tmp_path / "ctx.db"
        cache = ContextCache(str(db))
        monkeypatch.setattr(
            "openjarvis.workbench.context_cache.ContextCache",
            lambda db_path=None: cache,
        )
        result = warm_repo_map_cache(".")
        assert result["ok"] is True
        assert result["file_count"] > 0

        cached = cache.get("repo_map", ".")
        assert cached is not None
        assert cached["payload"]["file_count"] > 0

    def test_cache_all_key_types(self, tmp_path):
        from openjarvis.workbench.context_cache import ContextCache, CACHE_KEYS

        cache = ContextCache(str(tmp_path / "ctx.db"))
        for key in CACHE_KEYS:
            cache.put(key, {"test": True, "key": key}, repo_path=".")
            got = cache.get(key, ".")
            assert got is not None
            assert got["payload"]["key"] == key


class TestGitWorkflowStatus:
    def test_git_status_returns_branch(self):
        from openjarvis.workbench.repo_index import git_workflow_status

        status = git_workflow_status(".")
        assert status["ok"] is True
        assert "branch" in status
        assert "dirty" in status
