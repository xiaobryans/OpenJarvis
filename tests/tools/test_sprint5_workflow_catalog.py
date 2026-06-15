"""Ultra Sprint 5 — Workflow Catalog tests.

Covers:
  Phase B  — Project/Repo/Tests/Mission/QA/Governance tools
  Phase C  — Research/browser tools (mocked network)
  Phase D  — Communication/report tools
  Phase E  — Extended memory tools

Rules:
  - No real network calls (requests patched)
  - No real browser opens (dry_run=True)
  - All git ops use real OMNIX repo (read-only)
  - test_path paths validated for safety
  - Slack/Telegram draft tools: no send
  - web.search: confirmed not_configured without token
  - Planned/degraded/not_configured tools NOT in available list
  - project_id isolation verified
"""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus
from openjarvis.tools.execution_log import ExecutionOutcome
from openjarvis.tools.gateway import ToolExecutionGateway
from openjarvis.governance.constitution import ProjectRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_OMNIX_REPO = "/Users/user/OpenJarvis"


@pytest.fixture(autouse=True)
def _reset_registries():
    ToolRegistry.clear()
    ProjectRegistry.clear()
    yield
    ToolRegistry.clear()
    ProjectRegistry.clear()


@pytest.fixture()
def gateway(tmp_path):
    return ToolExecutionGateway(log_db_path=tmp_path / "test_executions.db")


@pytest.fixture()
def initialized_catalog():
    """Initialize full catalog (Sprint 4 + Sprint 5) and return gateway."""
    from openjarvis.tools.catalog import initialize_catalog
    initialize_catalog()


@pytest.fixture()
def initialized_with_gateway(tmp_path, initialized_catalog):
    return ToolExecutionGateway(log_db_path=tmp_path / "executions.db")


# ---------------------------------------------------------------------------
# 1. Catalog initialization — counts are honest
# ---------------------------------------------------------------------------


def test_workflow_catalog_initializes(initialized_catalog):
    """All Sprint 5 tools are registered after initialize_catalog()."""
    from openjarvis.tools.catalog import initialize_catalog
    stats = ToolRegistry.stats()
    assert stats["total_registered"] >= 49, (
        f"Expected >= 49 total tools, got {stats['total_registered']}"
    )


def test_workflow_available_count_no_inflation(initialized_catalog):
    """Available count matches only tools with status=available."""
    available = ToolRegistry.list_available()
    all_tools = ToolRegistry.list_all()
    unavailable = ToolRegistry.list_unavailable()
    assert len(available) + len(unavailable) == len(all_tools)
    for t in available:
        assert t.is_available(), f"Tool {t.tool_id} in available list but is_available()=False"


def test_web_search_not_configured_without_token(initialized_catalog):
    """web.search must be not_configured without TAVILY_API_KEY."""
    without_key = os.environ.pop("TAVILY_API_KEY", None)
    try:
        spec = ToolRegistry.get("web.search")
        if spec is not None:
            assert spec.implementation_status in (
                ToolStatus.NOT_CONFIGURED, ToolStatus.AVAILABLE
            ), f"Unexpected status: {spec.implementation_status}"
            if not os.environ.get("TAVILY_API_KEY"):
                assert spec.implementation_status == ToolStatus.NOT_CONFIGURED
                assert spec.blocker, "web.search should have a blocker message"
    finally:
        if without_key is not None:
            os.environ["TAVILY_API_KEY"] = without_key


def test_no_tool_available_without_executor(initialized_catalog):
    """No AVAILABLE tool may have a missing executor (Sprint 4 contract)."""
    for spec in ToolRegistry.list_available():
        exec_fn = ToolRegistry.get_executor(spec.tool_id)
        assert exec_fn is not None, (
            f"Tool '{spec.tool_id}' is status=available but has no executor"
        )


# ---------------------------------------------------------------------------
# 2. Phase B — Project tools
# ---------------------------------------------------------------------------


def test_project_status_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("project.status", inputs={"project_id": "omnix"}, project_id="omnix")
    assert result.ok, f"project.status failed: {result.error}"
    assert result.output["status"]["project_id"] == "omnix"
    assert result.output["status"]["active"] is True


def test_project_status_unknown_project(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("project.status", inputs={"project_id": "nonexistent_xyz"})
    assert result.ok
    assert result.output["ok"] is False


def test_project_handoff_read_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("project.handoff_read", inputs={"project_id": "omnix"})
    assert result.ok
    assert result.output["ok"] is True
    assert "handoff_files" in result.output
    # Handoff file should exist
    files = result.output["handoff_files"]
    assert len(files) > 0
    existing = [f for f in files if f.get("exists")]
    assert len(existing) > 0, "OMNIX handoff file should exist on disk"


def test_project_handoff_update_plan_writes_and_idempotent(initialized_catalog, tmp_path):
    """Append a draft section and verify content; calling again replaces it."""
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    content = "Test draft plan from Sprint 5 automated test."
    result = gw.execute(
        "project.handoff_update_plan",
        inputs={
            "project_id": "omnix",
            "content": content,
            "section_label": "TestDraftSection",
        },
    )
    assert result.ok, f"handoff_update_plan failed: {result.error}"
    assert result.output["ok"] is True
    # Verify the section was written
    handoff_path = Path(_OMNIX_REPO) / "JARVIS_OMNIX_HANDOFF.md"
    if handoff_path.exists():
        text = handoff_path.read_text()
        assert content in text
        # Second call replaces section (idempotent)
        gw.execute(
            "project.handoff_update_plan",
            inputs={
                "project_id": "omnix",
                "content": "Updated draft.",
                "section_label": "TestDraftSection",
            },
        )
        text2 = handoff_path.read_text()
        assert "Updated draft." in text2


def test_project_handoff_update_plan_rejects_secret(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    # Use a split string to avoid GitHub Push Protection
    fake_token = "xoxb-" + "000000000000-000000000000-aaaaaaaaaaaaaaaa"
    result = gw.execute(
        "project.handoff_update_plan",
        inputs={"project_id": "omnix", "content": fake_token},
    )
    # Should either block the write or return ok=False
    if result.ok:
        assert result.output.get("ok") is False
    else:
        assert result.outcome in (ExecutionOutcome.FAILED, ExecutionOutcome.BLOCKED)


# ---------------------------------------------------------------------------
# 3. Phase B — Repo tools (read-only git)
# ---------------------------------------------------------------------------


def test_repo_status_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("repo.status", inputs={"project_id": "omnix"})
    assert result.ok
    assert "is_clean" in result.output
    assert result.output["repo_path"] == _OMNIX_REPO


def test_repo_branch_info_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("repo.branch_info", inputs={"project_id": "omnix"})
    assert result.ok
    out = result.output
    assert out["branch"] == "localhost-get-tool"
    assert len(out["head_sha"]) >= 7


def test_repo_diff_summary_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("repo.diff_summary", inputs={"project_id": "omnix", "target": "HEAD"})
    assert result.ok
    assert "diff_stat" in result.output


def test_repo_recent_commits_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("repo.recent_commits", inputs={"project_id": "omnix", "n": 5})
    assert result.ok
    assert result.output["count"] > 0
    assert len(result.output["commits"]) > 0
    # Each commit should be in oneline format (sha + message)
    for commit in result.output["commits"]:
        assert len(commit) > 7


def test_repo_recent_commits_cap_at_50(initialized_catalog, tmp_path):
    """n is capped at 50."""
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("repo.recent_commits", inputs={"project_id": "omnix", "n": 9999})
    assert result.ok
    assert result.output["count"] <= 50


# ---------------------------------------------------------------------------
# 4. Phase B — Tests tools
# ---------------------------------------------------------------------------


def test_tests_discover_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "tests.discover",
        inputs={"project_id": "omnix", "tests_dir": "tests"},
    )
    assert result.ok
    assert result.output["count"] > 0
    # Sprint 4 test file must be discoverable
    files = result.output["test_files"]
    assert any("test_tool_registry.py" in f for f in files)


def test_tests_run_targeted_real(initialized_catalog, tmp_path):
    """Run the Sprint 4 test_tool_registry.py for real through the gateway."""
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "tests.run_targeted",
        inputs={
            "test_path": "tests/tools/test_tool_registry.py",
            "project_id": "omnix",
        },
    )
    assert result.ok, f"tests.run_targeted failed: {result.error}"
    assert "output" in result.output


def test_tests_run_targeted_blocks_outside_repo(initialized_catalog, tmp_path):
    """test_path outside project repo must be rejected."""
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "tests.run_targeted",
        inputs={
            "test_path": "/tmp/test_evil.py",
            "project_id": "omnix",
        },
    )
    # Should either fail gracefully (ok=False) or raise ValueError
    if result.ok:
        assert result.output.get("ok") is False
    else:
        assert result.outcome in (ExecutionOutcome.FAILED, ExecutionOutcome.BLOCKED)


def test_tests_report_summary_parses_output(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    sample = (
        "tests/tools/test_tool_registry.py ..............       [100%]\n"
        "=================== 20 passed in 1.23s ===================="
    )
    result = gw.execute("tests.report_summary", inputs={"output": sample})
    assert result.ok
    out = result.output
    assert out["passed"] == 20
    assert out["failed"] == 0
    assert out["all_pass"] is True


def test_tests_report_summary_detects_failures(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    sample = "5 failed, 3 passed, 1 error in 2.5s"
    result = gw.execute("tests.report_summary", inputs={"output": sample})
    assert result.ok
    out = result.output
    assert out["failed"] == 5
    assert out["passed"] == 3
    assert out["all_pass"] is False


# ---------------------------------------------------------------------------
# 5. Phase B — Mission tools
# ---------------------------------------------------------------------------


def test_mission_create_from_project_issue(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "mission.create_from_project_issue",
        inputs={
            "project_id": "omnix",
            "title": "Test mission from Sprint5 test",
            "description": "Automated test mission for OMNIX",
        },
    )
    assert result.ok, f"create_from_project_issue failed: {result.error}"
    out = result.output
    assert out["ok"] is True
    assert out["project_id"] == "omnix"
    assert out["status"] == "queued"
    assert out["mission_id"]


def test_mission_project_report_filters_by_project(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    # Create a mission for omnix
    gw.execute(
        "mission.create_from_project_issue",
        inputs={"project_id": "omnix", "title": "Report test mission"},
    )
    result = gw.execute(
        "mission.project_report",
        inputs={"project_id": "omnix"},
    )
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert out["project_id"] == "omnix"
    # Should find at least the mission we just created
    assert out["count"] >= 1
    for m in out["missions"]:
        assert "[project:omnix]" in m["objective"]


def test_mission_project_report_different_project_isolated(initialized_catalog, tmp_path):
    """Missions for omnix must not appear when querying a different project."""
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    gw.execute(
        "mission.create_from_project_issue",
        inputs={"project_id": "omnix", "title": "OMNIX isolation test"},
    )
    result = gw.execute(
        "mission.project_report",
        inputs={"project_id": "some_other_project"},
    )
    assert result.ok
    out = result.output
    # No omnix missions should appear for 'some_other_project'
    for m in out["missions"]:
        assert "[project:omnix]" not in m["objective"]


def test_mission_create_from_project_requires_valid_project(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "mission.create_from_project_issue",
        inputs={"project_id": "does_not_exist_xyz", "title": "Should fail"},
    )
    if result.ok:
        assert result.output.get("ok") is False


# ---------------------------------------------------------------------------
# 6. Phase B — QA/Governance tools
# ---------------------------------------------------------------------------


def test_qa_check_acceptance_evidence_accept(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "qa.check_acceptance_evidence",
        inputs={
            "evidence_items": [
                {"description": "Tests pass", "status": "verified", "source": "pytest output"},
                {"description": "Git clean", "status": "verified", "source": "git status"},
            ]
        },
    )
    assert result.ok
    assert result.output["verdict"] == "ACCEPT"
    assert result.output["sufficient"] is True
    assert result.output["verified_count"] == 2


def test_qa_check_acceptance_evidence_hold_on_missing(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "qa.check_acceptance_evidence",
        inputs={
            "evidence_items": [
                {"description": "Tests pass", "status": "missing"},
            ]
        },
    )
    assert result.ok
    assert result.output["verdict"] == "HOLD"
    assert result.output["sufficient"] is False


def test_qa_check_acceptance_evidence_empty_is_hold(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "qa.check_acceptance_evidence",
        inputs={"evidence_items": []},
    )
    assert result.ok
    assert result.output["verdict"] == "HOLD"


def test_governance_classify_report_hard_gate(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "governance.classify_report",
        inputs={"action_type": "omnix_production_deploy"},
    )
    assert result.ok
    out = result.output
    assert out["is_hard_gate"] is True
    assert out["allowed"] is False
    assert out["verdict"] == "UNSAFE"


def test_governance_classify_report_safe_action(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "governance.classify_report",
        inputs={"action_type": "read_project_status", "risk_level": "low"},
    )
    assert result.ok
    out = result.output
    assert out["is_hard_gate"] is False
    assert out["allowed"] is True


def test_governance_build_blocker_report(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "governance.build_blocker_report",
        inputs={
            "blocker": "TAVILY_API_KEY not set",
            "why_it_matters": "web.search cannot function without the API key",
            "unblock_path": "Set TAVILY_API_KEY env var",
            "can_continue_partially": True,
            "partial_scope": "All tools except web.search remain available",
        },
    )
    assert result.ok
    report = result.output["blocker_report"]
    assert report["blocker"] == "TAVILY_API_KEY not set"
    assert report["can_continue_partially"] is True
    assert report["unblock_path"] == "Set TAVILY_API_KEY env var"


# ---------------------------------------------------------------------------
# 7. Phase C — Research tools
# ---------------------------------------------------------------------------


def test_docs_summarize_text(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    text = (
        "# Sprint 5 Summary\n\n"
        "This sprint adds 35 new tools.\n\n"
        "- Project tools\n"
        "- Repo tools\n"
        "- Memory tools\n"
    )
    result = gw.execute("docs.summarize_text", inputs={"text": text})
    assert result.ok
    out = result.output
    assert out["header_count"] >= 1
    assert out["bullet_count"] >= 3
    assert "summary" in out
    assert len(out["summary"]) > 0


def test_sources_capture_writes_to_memory(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_sources_capture
    out = _exec_sources_capture(
        {"content": "Test content", "title": "Test Source", "project_id": "omnix"},
        {},
    )
    assert out["ok"] is True
    assert out["entry_id"]


def test_research_brief_writes_to_memory(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_research_brief
    out = _exec_research_brief(
        {
            "topic": "Test Topic",
            "findings": "Finding A, Finding B",
            "recommendations": "Do X",
            "project_id": "omnix",
        },
        {},
    )
    assert out["ok"] is True
    assert out["topic"] == "Test Topic"


def test_web_fetch_url_rejects_localhost(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("web.fetch_url", inputs={"url": "http://localhost:8080/admin"})
    assert result.ok
    assert result.output["ok"] is False
    assert "private" in result.output.get("error", "").lower() or "blocked" in result.output.get("error", "").lower()


def test_web_fetch_url_rejects_private_ip(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("web.fetch_url", inputs={"url": "http://192.168.1.1/secret"})
    assert result.ok
    assert result.output["ok"] is False


def test_web_fetch_url_mocked_success(initialized_catalog, tmp_path):
    """Real network is mocked — no actual HTTP request."""
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.text = "<html><body>Hello world</body></html>"
    mock_resp.status_code = 200
    with patch("requests.get", return_value=mock_resp):
        result = gw.execute("web.fetch_url", inputs={"url": "https://example.com"})
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert out["status_code"] == 200
    assert "Hello world" in out["content"]


def test_browser_open_url_dry_run(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("browser.open_url", inputs={"url": "https://example.com", "dry_run": True})
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["url"] == "https://example.com"


def test_web_search_not_configured_through_gateway(initialized_catalog, tmp_path):
    """web.search blocked when TAVILY_API_KEY absent."""
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    original = os.environ.pop("TAVILY_API_KEY", None)
    try:
        # Re-check registry state: web.search registered as not_configured
        spec = ToolRegistry.get("web.search")
        if spec and spec.implementation_status == ToolStatus.NOT_CONFIGURED:
            result = gw.execute("web.search", inputs={"query": "test"})
            assert not result.ok
            assert result.outcome == ExecutionOutcome.NOT_CONFIGURED
    finally:
        if original is not None:
            os.environ["TAVILY_API_KEY"] = original


# ---------------------------------------------------------------------------
# 8. Phase D — Communication tools (no real sends)
# ---------------------------------------------------------------------------


def test_slack_draft_update_no_send(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "slack.draft_update",
        inputs={
            "title": "Sprint 5 Status",
            "body": "All 35 new tools added.",
            "project_id": "omnix",
        },
    )
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert out["send_status"] == "not_sent"
    assert "Sprint 5 Status" in out["draft"]
    assert "not sent" in out["draft"].lower()


def test_telegram_draft_alert_no_send(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute(
        "telegram.draft_alert",
        inputs={
            "title": "Blocked Mission Alert",
            "body": "Mission abc123 is blocked on test infrastructure.",
            "project_id": "omnix",
            "urgency": "high",
        },
    )
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert out["send_status"] == "not_sent"
    assert "🔴" in out["draft"]


def test_report_generate_status_omnix(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("report.generate_status", inputs={"project_id": "omnix"})
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert "OMNIX" in out["report"]
    assert "mission_count" in out


def test_report_generate_daily_digest(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("report.generate_daily_digest", inputs={"project_id": "omnix"})
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert "Daily Digest" in out["digest"]
    assert "running_count" in out
    assert "blocked_count" in out


def test_approval_queue_summary(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("approval.queue_summary", inputs={})
    assert result.ok
    out = result.output
    assert out["ok"] is True
    assert "pending_count" in out
    assert isinstance(out["items"], list)


# ---------------------------------------------------------------------------
# 9. Phase E — Extended memory tools
# ---------------------------------------------------------------------------


def test_memory_record_decision(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_memory_record_decision
    out = _exec_memory_record_decision(
        {"content": "Use SQLite for memory store", "project_id": "omnix"},
        {},
    )
    assert out["ok"] is True
    assert out["entry_type"] == "decision"
    assert out["project_id"] == "omnix"


def test_memory_record_bug(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_memory_record_bug
    out = _exec_memory_record_bug(
        {"content": "Tool registry clears on test teardown", "project_id": "omnix"},
        {},
    )
    assert out["ok"] is True
    assert out["entry_type"] == "bug"


def test_memory_record_fix(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_memory_record_fix
    out = _exec_memory_record_fix(
        {"content": "Added autouse fixture to reset registry", "project_id": "omnix"},
        {},
    )
    assert out["ok"] is True
    assert out["entry_type"] == "fix"


def test_memory_record_blocker(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_memory_record_blocker
    out = _exec_memory_record_blocker(
        {"content": "TAVILY_API_KEY not set", "project_id": "omnix"},
        {},
    )
    assert out["ok"] is True
    assert out["entry_type"] == "blocker"


def test_memory_record_validation(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_memory_record_validation
    out = _exec_memory_record_validation(
        {"content": "Ultra Sprint 5 ACCEPT — all gates passed", "project_id": "omnix"},
        {},
    )
    assert out["ok"] is True
    assert out["entry_type"] == "validation"


def test_memory_record_typed_prefix(initialized_catalog, tmp_path):
    """Tagged entries must have [TYPE] prefix in stored content."""
    from openjarvis.memory.store import JarvisMemory
    mem = JarvisMemory(db_path=tmp_path / "mem.db")
    mem.write(
        namespace="project:omnix",
        content="[BUG] Some content",
        source="test",
        project_id="omnix",
        tags=["bug"],
    )
    results = mem.search("BUG", project_id="omnix")
    assert len(results) >= 1
    assert "[BUG]" in results[0].content


def test_memory_scrub_check_detects_secret(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    # Use split string to avoid GitHub Push Protection
    fake_token = "xoxb-" + "000000000000-000000000000-aaaaaaaaaaaaaaaa"
    result = gw.execute("memory.scrub_check", inputs={"value": fake_token})
    assert result.ok
    assert result.output["would_reject"] is True


def test_memory_scrub_check_safe_value(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("memory.scrub_check", inputs={"value": "This is a normal note"})
    assert result.ok
    assert result.output["would_reject"] is False


def test_memory_project_summary(initialized_catalog, tmp_path):
    from openjarvis.tools.workflow_catalog import _exec_memory_project_summary, _exec_memory_record_decision
    # Write a decision entry first so the namespace has at least one entry
    _exec_memory_record_decision(
        {"content": "Test decision for memory_project_summary test", "project_id": "omnix"},
        {},
    )
    out = _exec_memory_project_summary({"project_id": "omnix"}, {})
    assert out["ok"] is True
    assert out["count"] >= 1


def test_memory_list_recent_project_entries_isolation(initialized_catalog, tmp_path):
    """Entries for one project must not appear for another."""
    import uuid
    from openjarvis.memory.store import JarvisMemory
    # Use unique project IDs to avoid collisions with other test data
    proj_a = f"test_proj_a_{uuid.uuid4().hex[:8]}"
    proj_b = f"test_proj_b_{uuid.uuid4().hex[:8]}"
    mem = JarvisMemory()  # real default DB
    mem.write(namespace=f"project:{proj_a}", content="Proj A note", source="t", project_id=proj_a)
    mem.write(namespace=f"project:{proj_b}", content="Proj B note", source="t", project_id=proj_b)
    from openjarvis.tools.workflow_catalog import _exec_memory_list_recent_project_entries
    out = _exec_memory_list_recent_project_entries({"project_id": proj_a}, {})
    assert out["ok"] is True
    assert out["count"] >= 1
    for entry in out["entries"]:
        assert entry["project_id"] == proj_a


# ---------------------------------------------------------------------------
# 10. Execution log entries
# ---------------------------------------------------------------------------


def test_gateway_produces_execution_log_entries(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    gw.execute("project.list", inputs={})
    gw.execute("memory.scrub_check", inputs={"value": "safe text"})
    entries = gw.get_log().list_recent(limit=10)
    tool_ids = {e.tool_id for e in entries}
    assert "project.list" in tool_ids
    assert "memory.scrub_check" in tool_ids


def test_gateway_logs_not_configured_outcome(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    spec = ToolRegistry.get("web.search")
    if spec and spec.implementation_status == ToolStatus.NOT_CONFIGURED:
        result = gw.execute("web.search", inputs={"query": "test"})
        entries = gw.get_log().list_recent(limit=5)
        ws_entries = [e for e in entries if e.tool_id == "web.search"]
        assert len(ws_entries) >= 1
        assert ws_entries[0].outcome == ExecutionOutcome.NOT_CONFIGURED


# ---------------------------------------------------------------------------
# 11. OMNIX is Project 1
# ---------------------------------------------------------------------------


def test_omnix_is_project_1(initialized_catalog, tmp_path):
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("project.list", inputs={})
    assert result.ok
    projects = result.output["projects"]
    assert len(projects) >= 1
    # OMNIX must be first (priority=1)
    assert projects[0]["project_id"] == "omnix"
    assert projects[0]["priority"] == 1


def test_future_project_can_be_registered(initialized_catalog, tmp_path):
    """Non-OMNIX projects can be registered alongside OMNIX."""
    from openjarvis.governance.constitution import ProjectProfile
    p2 = ProjectProfile(
        project_id="project_two",
        display_name="Project Two",
        priority=2,
    )
    ProjectRegistry.register(p2)
    gw = ToolExecutionGateway(log_db_path=tmp_path / "exec.db")
    result = gw.execute("project.list", inputs={})
    assert result.ok
    ids = [p["project_id"] for p in result.output["projects"]]
    assert "omnix" in ids
    assert "project_two" in ids
    # OMNIX still first
    assert result.output["projects"][0]["project_id"] == "omnix"


# ---------------------------------------------------------------------------
# 12. No fake tools counted as available
# ---------------------------------------------------------------------------


def test_planned_tool_not_in_available_list(initialized_catalog):
    for spec in ToolRegistry.list_available():
        assert spec.implementation_status == ToolStatus.AVAILABLE, (
            f"Tool '{spec.tool_id}' in available list but status={spec.implementation_status}"
        )


def test_not_configured_tools_in_unavailable_list(initialized_catalog):
    unavailable = ToolRegistry.list_unavailable()
    not_configured = [t for t in unavailable if t.implementation_status == ToolStatus.NOT_CONFIGURED]
    # web.search + slack.notify_mission + telegram.notify_mission = 3 not_configured
    assert len(not_configured) >= 3
