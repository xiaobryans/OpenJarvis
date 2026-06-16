"""Tests for Jarvis Project Source Linker — US7 Hold Fix.

Proves:
  - OMNIX local_repo=/Users/user/OpenJarvis is detected as placeholder
  - get_linkage_status returns linkage_status=placeholder for OMNIX
  - Readiness HOLDs when OMNIX operational linkage is missing (placeholder)
  - Source statuses separate linked / placeholder / missing / not_configured / blocked / invalid
  - Local repo validation is read-only (no writes, no broad scans)
  - A future project's source profile can be represented
  - No secrets are read or printed
  - No broad scan required — only configured paths validated
  - ProjectSourceRegistry is safe to clear for test isolation
  - 10 project linker tools are all registered and available
  - make_future_project_source_template returns correct structure
"""

from __future__ import annotations

import pytest
from pathlib import Path

from openjarvis.projects.source_links import (
    ProjectSourceLink,
    ProjectSourceLinkType,
    ProjectSourceRegistry,
    ProjectSourceStatus,
    make_future_project_source_template,
    validate_source_link,
    _is_jarvis_codebase,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_LINKAGE_ENV_KEYS = (
    "JARVIS_PROJECT_OMNIX_REPO_PATH",
    "OPENCLAW_WORKSPACE_PATH",
    "OPENCLAW_HANDOFF_PATH",
)


_LINKAGE_ENV_OVERRIDES = {
    "JARVIS_PROJECT_OMNIX_REPO_PATH": "/Users/user/OpenJarvis",
    "OPENCLAW_WORKSPACE_PATH": "",
    "OPENCLAW_HANDOFF_PATH": "",
}


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch):
    for key, val in _LINKAGE_ENV_OVERRIDES.items():
        monkeypatch.setenv(key, val)
    ProjectSourceRegistry.clear()
    yield
    ProjectSourceRegistry.clear()


# ---------------------------------------------------------------------------
# Placeholder detection
# ---------------------------------------------------------------------------


class TestPlaceholderDetection:
    def test_openjarvis_path_is_jarvis_codebase(self):
        from openjarvis.projects.source_links import _JARVIS_REPO_ROOT
        assert _is_jarvis_codebase(_JARVIS_REPO_ROOT) is True

    def test_nonexistent_path_is_not_jarvis(self):
        assert _is_jarvis_codebase(Path("/tmp/some_fake_project_xyz")) is False

    def test_tmp_dir_is_not_jarvis(self, tmp_path):
        assert _is_jarvis_codebase(tmp_path) is False

    def test_jarvis_marker_file_causes_detection(self, tmp_path):
        marker = tmp_path / "src" / "openjarvis" / "governance"
        marker.mkdir(parents=True, exist_ok=True)
        (marker / "constitution.py").write_text("# fake")
        assert _is_jarvis_codebase(tmp_path) is True


# ---------------------------------------------------------------------------
# OMNIX bootstrap — placeholder detection
# ---------------------------------------------------------------------------


class TestOmnixBootstrap:
    def test_omnix_sources_bootstrapped(self):
        links = ProjectSourceRegistry.list_for_project("omnix")
        assert len(links) >= 6

    def test_omnix_local_repo_is_registered(self):
        link = ProjectSourceRegistry.get("omnix", "local_repo")
        assert link is not None
        assert link.link_type == ProjectSourceLinkType.LOCAL_REPO
        assert link.path_or_url  # path is non-empty (from profile or env)

    def test_omnix_local_repo_validates_as_placeholder(self):
        link = ProjectSourceRegistry.get("omnix", "local_repo")
        assert link is not None
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.PLACEHOLDER
        assert "Jarvis" in validated.blocker or "OpenJarvis" in validated.blocker
        assert validated.read_access is True

    def test_omnix_github_remote_is_not_configured(self):
        link = ProjectSourceRegistry.get("omnix", "github_remote")
        assert link is not None
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED

    def test_omnix_openclaw_workspace_is_not_configured(self):
        link = ProjectSourceRegistry.get("omnix", "openclaw_workspace")
        assert link is not None
        validated = validate_source_link(link)
        # env vars cleared by fixture → path is empty → not_configured
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED

    def test_omnix_runtime_health_is_not_configured(self):
        link = ProjectSourceRegistry.get("omnix", "runtime_health_endpoint")
        assert link is not None
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED

    def test_omnix_memory_namespace_is_linked(self):
        link = ProjectSourceRegistry.get("omnix", "memory_namespace")
        assert link is not None
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.LINKED
        assert validated.read_access is True

    def test_omnix_handoff_file_linked_or_missing(self):
        link = ProjectSourceRegistry.get("omnix", "handoff_file")
        assert link is not None
        validated = validate_source_link(link)
        assert validated.status in (
            ProjectSourceStatus.LINKED,
            ProjectSourceStatus.MISSING,
            ProjectSourceStatus.NOT_CONFIGURED,
        )


# ---------------------------------------------------------------------------
# get_linkage_status — OMNIX placeholder
# ---------------------------------------------------------------------------


class TestOmnixLinkageStatus:
    def test_omnix_linkage_status_is_placeholder(self):
        report = ProjectSourceRegistry.get_linkage_status("omnix")
        assert report["linkage_status"] == "placeholder"

    def test_omnix_blocker_mentions_jarvis(self):
        report = ProjectSourceRegistry.get_linkage_status("omnix")
        blocker = report["blocker"]
        assert blocker, "blocker should not be empty for placeholder"
        assert "placeholder" in blocker.lower() or "jarvis" in blocker.lower()

    def test_omnix_placeholder_count_gte_1(self):
        report = ProjectSourceRegistry.get_linkage_status("omnix")
        assert report["counts"]["placeholder"] >= 1

    def test_omnix_operational_count_is_zero(self):
        report = ProjectSourceRegistry.get_linkage_status("omnix")
        # operational = primary sources that are linked; OMNIX has none (only placeholder)
        assert report["counts"]["operational"] == 0
        assert report["linkage_status"] == "placeholder"

    def test_sources_field_present(self):
        report = ProjectSourceRegistry.get_linkage_status("omnix")
        assert "sources" in report
        assert len(report["sources"]) >= 6


# ---------------------------------------------------------------------------
# Readiness HOLD when OMNIX is placeholder
# ---------------------------------------------------------------------------


class TestReadinessHoldForOmnix:
    def test_check_project_linkage_fails_for_omnix(self):
        from openjarvis.doctor.checks import check_project_linkage_status, CheckStatus
        result = check_project_linkage_status("omnix")
        assert result.check_id == "project_linkage_status"
        assert result.status == CheckStatus.FAIL
        assert "PLACEHOLDER" in result.summary or "placeholder" in result.summary.lower()

    def test_readiness_holds_when_omnix_placeholder(self):
        from openjarvis.doctor.readiness import evaluate_readiness, ReadinessVerdict
        report = evaluate_readiness(project_id="omnix")
        assert report.verdict == ReadinessVerdict.HOLD

    def test_project_linkage_category_in_report(self):
        from openjarvis.doctor.readiness import evaluate_readiness, ReadinessCategory
        report = evaluate_readiness(project_id="omnix")
        cats = {c.category for c in report.categories}
        assert ReadinessCategory.PROJECT_LINKAGE in cats

    def test_project_linkage_category_fails(self):
        from openjarvis.doctor.readiness import evaluate_readiness, ReadinessCategory
        from openjarvis.doctor.checks import CheckStatus
        report = evaluate_readiness(project_id="omnix")
        pl_cat = next(
            (c for c in report.categories if c.category == ReadinessCategory.PROJECT_LINKAGE),
            None,
        )
        assert pl_cat is not None
        assert pl_cat.status == CheckStatus.FAIL

    def test_project_linkage_category_is_required(self):
        from openjarvis.doctor.readiness import evaluate_readiness, ReadinessCategory
        report = evaluate_readiness(project_id="omnix")
        pl_cat = next(
            (c for c in report.categories if c.category == ReadinessCategory.PROJECT_LINKAGE),
            None,
        )
        assert pl_cat is not None
        assert pl_cat.is_required is True

    def test_readiness_has_15_categories(self):
        from openjarvis.doctor.readiness import evaluate_readiness
        report = evaluate_readiness(project_id="omnix")
        assert len(report.categories) == 15

    def test_run_all_checks_returns_19(self):
        from openjarvis.doctor.checks import run_all_checks
        results = run_all_checks(project_id="omnix")
        assert len(results) == 19


# ---------------------------------------------------------------------------
# Real-linked local repo (tmp_path)
# ---------------------------------------------------------------------------


class TestRealLinkedLocalRepo:
    def test_real_non_jarvis_path_is_ready_read_only(self, tmp_path):
        link = ProjectSourceLink(
            source_id="local_repo",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url=str(tmp_path),
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.READY_READ_ONLY
        assert validated.read_access is True
        assert validated.write_access is False

    def test_missing_path_is_missing(self):
        link = ProjectSourceLink(
            source_id="local_repo",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url="/nonexistent/path/xyz123",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.MISSING
        assert validated.read_access is False

    def test_empty_path_is_not_configured(self):
        link = ProjectSourceLink(
            source_id="local_repo",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url="",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED

    def test_validation_is_read_only(self, tmp_path):
        """Validation must not create, modify, or delete any files."""
        initial_files = set(tmp_path.iterdir())
        link = ProjectSourceLink(
            source_id="local_repo",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url=str(tmp_path),
        )
        validate_source_link(link)
        assert set(tmp_path.iterdir()) == initial_files


# ---------------------------------------------------------------------------
# Handoff file validation
# ---------------------------------------------------------------------------


class TestHandoffFileValidation:
    def test_existing_handoff_file_is_linked(self, tmp_path):
        hf = tmp_path / "HANDOFF.md"
        hf.write_text("# handoff")
        link = ProjectSourceLink(
            source_id="handoff_file",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.HANDOFF_FILE,
            path_or_url=str(hf),
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.LINKED
        assert validated.read_access is True
        assert "size_bytes" in validated.evidence
        assert "age_days" in validated.evidence

    def test_missing_handoff_file_is_missing(self):
        link = ProjectSourceLink(
            source_id="handoff_file",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.HANDOFF_FILE,
            path_or_url="/nonexistent/HANDOFF.md",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.MISSING

    def test_empty_handoff_path_is_not_configured(self):
        link = ProjectSourceLink(
            source_id="handoff_file",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.HANDOFF_FILE,
            path_or_url="",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED


# ---------------------------------------------------------------------------
# OpenClaw validation
# ---------------------------------------------------------------------------


class TestOpenClawValidation:
    def test_existing_openclaw_path_is_ready_read_only(self, tmp_path):
        link = ProjectSourceLink(
            source_id="openclaw_workspace",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.OPENCLAW_WORKSPACE,
            path_or_url=str(tmp_path),
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.READY_READ_ONLY
        assert validated.read_access is True
        assert validated.write_access is False

    def test_missing_openclaw_path_is_missing(self):
        link = ProjectSourceLink(
            source_id="openclaw_workspace",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.OPENCLAW_WORKSPACE,
            path_or_url="/nonexistent/openclaw/workspace",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.MISSING

    def test_empty_openclaw_path_is_not_configured(self):
        link = ProjectSourceLink(
            source_id="openclaw_workspace",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.OPENCLAW_WORKSPACE,
            path_or_url="",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED

    def test_openclaw_no_write_access_without_approval(self, tmp_path):
        link = ProjectSourceLink(
            source_id="openclaw_workspace",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.OPENCLAW_WORKSPACE,
            path_or_url=str(tmp_path),
        )
        validated = validate_source_link(link)
        assert validated.write_access is False


# ---------------------------------------------------------------------------
# GitHub remote validation
# ---------------------------------------------------------------------------


class TestGitHubRemoteValidation:
    def test_empty_github_remote_is_not_configured(self):
        link = ProjectSourceLink(
            source_id="github_remote",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.GITHUB_REMOTE,
            path_or_url="",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED

    def test_valid_github_url_is_blocked_not_live(self):
        link = ProjectSourceLink(
            source_id="github_remote",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.GITHUB_REMOTE,
            path_or_url="https://github.com/owner/repo",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.BLOCKED
        assert validated.read_access is False

    def test_invalid_github_url_is_invalid(self):
        link = ProjectSourceLink(
            source_id="github_remote",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.GITHUB_REMOTE,
            path_or_url="not-a-github-url",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.INVALID


# ---------------------------------------------------------------------------
# Runtime endpoint validation
# ---------------------------------------------------------------------------


class TestRuntimeEndpointValidation:
    def test_empty_endpoint_is_not_configured(self):
        link = ProjectSourceLink(
            source_id="runtime_health_endpoint",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.RUNTIME_HEALTH_ENDPOINT,
            path_or_url="",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED

    def test_valid_url_is_blocked_not_live(self):
        link = ProjectSourceLink(
            source_id="runtime_health_endpoint",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.RUNTIME_HEALTH_ENDPOINT,
            path_or_url="https://api.omnix.example.com/health",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.BLOCKED
        assert validated.read_access is False


# ---------------------------------------------------------------------------
# Memory namespace validation
# ---------------------------------------------------------------------------


class TestMemoryNamespaceValidation:
    def test_namespace_is_always_linked(self):
        link = ProjectSourceLink(
            source_id="memory_namespace",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.MEMORY_NAMESPACE,
            path_or_url="project:test_proj",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.LINKED
        assert validated.read_access is True

    def test_empty_namespace_is_not_configured(self):
        link = ProjectSourceLink(
            source_id="memory_namespace",
            project_id="test_proj",
            link_type=ProjectSourceLinkType.MEMORY_NAMESPACE,
            path_or_url="",
        )
        validated = validate_source_link(link)
        assert validated.status == ProjectSourceStatus.NOT_CONFIGURED


# ---------------------------------------------------------------------------
# to_dict contract
# ---------------------------------------------------------------------------


class TestSourceLinkToDict:
    def test_to_dict_has_all_required_fields(self):
        link = ProjectSourceLink(
            source_id="local_repo",
            project_id="omnix",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url="/some/path",
        )
        d = link.to_dict()
        required = [
            "source_id", "project_id", "link_type", "path_or_url",
            "status", "read_access", "write_access",
            "last_checked_at", "evidence", "blocker",
        ]
        for k in required:
            assert k in d, f"Missing key: {k}"

    def test_write_access_false_by_default(self):
        link = ProjectSourceLink(
            source_id="test", project_id="test",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url="",
        )
        assert link.write_access is False

    def test_is_operational_true_for_linked(self):
        link = ProjectSourceLink(
            source_id="test", project_id="test",
            link_type=ProjectSourceLinkType.MEMORY_NAMESPACE,
            path_or_url="project:test",
            status=ProjectSourceStatus.LINKED,
            read_access=True,
        )
        assert link.is_operational() is True

    def test_is_operational_false_for_placeholder(self):
        link = ProjectSourceLink(
            source_id="test", project_id="test",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url="/fake",
            status=ProjectSourceStatus.PLACEHOLDER,
            read_access=True,
        )
        assert link.is_operational() is False


# ---------------------------------------------------------------------------
# Future project source template
# ---------------------------------------------------------------------------


class TestFutureProjectTemplate:
    def test_template_returns_6_sources(self):
        sources = make_future_project_source_template(
            project_id="future_proj",
            name="Future Project",
        )
        assert len(sources) == 6

    def test_template_all_not_configured_by_default(self):
        sources = make_future_project_source_template(
            project_id="future_proj",
            name="Future Project",
        )
        non_ns = [s for s in sources if s.link_type != ProjectSourceLinkType.MEMORY_NAMESPACE]
        for s in non_ns:
            assert s.path_or_url == "", f"{s.source_id} should be empty by default"

    def test_template_memory_namespace_auto_set(self):
        sources = make_future_project_source_template(
            project_id="newco",
            name="NewCo",
        )
        ns = next(s for s in sources if s.link_type == ProjectSourceLinkType.MEMORY_NAMESPACE)
        assert ns.path_or_url == "project:newco"

    def test_template_with_local_repo_set(self, tmp_path):
        sources = make_future_project_source_template(
            project_id="proj2",
            name="Project 2",
            local_repo=str(tmp_path),
        )
        lr = next(s for s in sources if s.link_type == ProjectSourceLinkType.LOCAL_REPO)
        assert lr.path_or_url == str(tmp_path)

    def test_template_project_id_correct(self):
        sources = make_future_project_source_template("alpha", "Alpha")
        for s in sources:
            assert s.project_id == "alpha"


# ---------------------------------------------------------------------------
# No secrets in output
# ---------------------------------------------------------------------------


class TestNoSecretsInOutput:
    def test_validate_local_repo_no_env_vars(self, tmp_path):
        import os
        link = ProjectSourceLink(
            source_id="local_repo",
            project_id="test",
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url=str(tmp_path),
        )
        validated = validate_source_link(link)
        d_str = str(validated.to_dict())
        env_secrets = [v for k, v in os.environ.items() if k.lower() in
                       ("openai_api_key", "slack_bot_token", "telegram_token", "aws_secret_access_key")
                       if v and v in d_str]
        assert not env_secrets, f"Secrets found in output: {env_secrets}"

    def test_linkage_status_no_env_vars(self):
        import os
        report = ProjectSourceRegistry.get_linkage_status("omnix")
        report_str = str(report)
        secret_keys = ["openai_api_key", "slack_bot_token", "telegram_token", "aws_secret"]
        for key in secret_keys:
            val = os.environ.get(key.upper(), "")
            if val:
                assert val not in report_str, f"Secret '{key}' found in output"


# ---------------------------------------------------------------------------
# Project linker tools — registration + executors
# ---------------------------------------------------------------------------


class TestProjectLinkerTools:
    @pytest.fixture(autouse=True)
    def setup_tools(self, monkeypatch):
        for key, val in _LINKAGE_ENV_OVERRIDES.items():
            monkeypatch.setenv(key, val)
        from openjarvis.tools.jarvis_registry import ToolRegistry
        from openjarvis.projects.source_links import ProjectSourceRegistry
        ToolRegistry.clear()
        ProjectSourceRegistry.clear()
        from openjarvis.tools.project_linker_catalog import initialize_project_linker_catalog
        initialize_project_linker_catalog()
        yield
        ToolRegistry.clear()
        ProjectSourceRegistry.clear()

    _TOOL_IDS = [
        "project.sources.list",
        "project.sources.validate_all",
        "project.source.validate",
        "project.link_local_repo_plan",
        "project.link_local_repo",
        "project.link_handoff_file",
        "project.link_openclaw_workspace",
        "project.link_runtime_endpoint",
        "project.link_memory_namespace",
        "project.linkage_doctor",
    ]

    def test_all_10_tools_registered(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        for tid in self._TOOL_IDS:
            assert ToolRegistry.get(tid) is not None, f"Tool '{tid}' not registered"

    def test_all_10_tools_available(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        for tid in self._TOOL_IDS:
            spec = ToolRegistry.get(tid)
            assert spec.is_available(), f"Tool '{tid}' not available"

    def test_all_10_tools_have_executors(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        for tid in self._TOOL_IDS:
            assert ToolRegistry.get_executor(tid) is not None

    def test_sources_list_executor(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.sources.list")
        result = ex({"project_id": "omnix"}, {})
        assert result["project_id"] == "omnix"
        assert result["total"] >= 6
        assert "sources" in result

    def test_sources_validate_all_executor(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.sources.validate_all")
        result = ex({"project_id": "omnix"}, {})
        assert result["linkage_status"] == "placeholder"
        assert result["counts"]["placeholder"] >= 1

    def test_linkage_doctor_executor(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.linkage_doctor")
        result = ex({"project_id": "omnix"}, {})
        assert result["linkage_status"] == "placeholder"
        assert "HOLD" in result["readiness_impact"]
        assert len(result["unblock_steps"]) >= 3

    def test_link_local_repo_plan_detects_placeholder(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.link_local_repo_plan")
        result = ex({"project_id": "omnix", "repo_path": "/Users/user/OpenJarvis"}, {})
        assert result["would_be_status"] == "placeholder"
        assert result["is_jarvis_codebase"] is True

    def test_link_local_repo_plan_real_path(self, tmp_path):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.link_local_repo_plan")
        result = ex({"project_id": "omnix", "repo_path": str(tmp_path)}, {})
        assert result["would_be_status"] == "ready_read_only"
        assert result["is_jarvis_codebase"] is False

    def test_link_memory_namespace_executor(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.link_memory_namespace")
        result = ex({"project_id": "omnix", "namespace": "project:omnix"}, {})
        assert result["source"]["status"] == "linked"

    def test_link_runtime_endpoint_no_url_is_not_configured(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.link_runtime_endpoint")
        result = ex({"project_id": "omnix"}, {})
        assert result["status"] == "not_configured"

    def test_link_openclaw_no_path_is_not_configured(self):
        from openjarvis.tools.jarvis_registry import ToolRegistry
        ex = ToolRegistry.get_executor("project.link_openclaw_workspace")
        result = ex({"project_id": "omnix"}, {})
        assert result["status"] == "not_configured"
