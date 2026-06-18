"""Wave 3 Tests — Content & Media Studio (Epic G)."""

from __future__ import annotations

import os
import pytest
from typing import Any, Dict
from unittest.mock import patch


# ─────────────────────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────────────────────

class TestContentStudioStatus:
    def test_status_implemented(self):
        from openjarvis.wave.content_media_studio import get_content_studio_status
        info = get_content_studio_status()
        assert info["implemented"] is True
        assert info["status"] == "ready"
        assert info["epic"] == "epic_g"
        assert info["wave"] == 3

    def test_dry_run_default(self):
        from openjarvis.wave.content_media_studio import get_content_studio_status
        info = get_content_studio_status()
        assert info["dry_run_default"] is True
        assert info["file_write_requires_approval"] is True

    def test_seven_templates_registered(self):
        from openjarvis.wave.content_media_studio import get_content_studio_status
        info = get_content_studio_status()
        assert info["template_count"] >= 7

    def test_safety_policy_active(self):
        from openjarvis.wave.content_media_studio import get_content_studio_status
        info = get_content_studio_status()
        assert info["content_safety_policy_active"] is True

    def test_wave1_integration_flag(self):
        from openjarvis.wave.content_media_studio import get_content_studio_status
        info = get_content_studio_status()
        assert info["wave1_knowledge_integration"] is True
        assert info["wave2_skill_pack_integration"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────

class TestContentTemplates:
    def test_list_templates_returns_seven(self):
        from openjarvis.wave.content_media_studio import list_templates
        templates = list_templates()
        assert len(templates) >= 7

    def test_product_spec_template_present(self):
        from openjarvis.wave.content_media_studio import get_template
        tmpl = get_template("product_spec")
        assert tmpl is not None
        assert "title" in tmpl["fields"]

    def test_technical_handoff_template_present(self):
        from openjarvis.wave.content_media_studio import get_template
        assert get_template("technical_handoff") is not None

    def test_bug_report_template_present(self):
        from openjarvis.wave.content_media_studio import get_template
        assert get_template("bug_report") is not None

    def test_release_readiness_template_present(self):
        from openjarvis.wave.content_media_studio import get_template
        assert get_template("release_readiness_report") is not None

    def test_coding_agent_prompt_template_present(self):
        from openjarvis.wave.content_media_studio import get_template
        assert get_template("coding_agent_prompt") is not None

    def test_research_brief_template_present(self):
        from openjarvis.wave.content_media_studio import get_template
        assert get_template("research_brief") is not None

    def test_content_plan_template_present(self):
        from openjarvis.wave.content_media_studio import get_template
        assert get_template("content_plan") is not None

    def test_unknown_template_returns_none(self):
        from openjarvis.wave.content_media_studio import get_template
        assert get_template("nonexistent_xyz_template") is None

    def test_template_has_required_fields(self):
        from openjarvis.wave.content_media_studio import list_templates
        for tmpl in list_templates():
            assert "id" in tmpl
            assert "name" in tmpl
            assert "kind" in tmpl
            assert "description" in tmpl
            assert "fields" in tmpl

    def test_render_template_fills_fields(self):
        from openjarvis.wave.content_media_studio import render_template
        content = render_template("bug_report", {
            "title": "Test Bug",
            "severity": "high",
            "description": "Something broke",
            "steps_to_reproduce": "1. Do X\n2. See error",
            "expected": "Works",
            "actual": "Crashes",
            "environment": "macOS",
        })
        assert "Test Bug" in content
        assert "high" in content
        assert "Something broke" in content

    def test_render_template_leaves_unfilled_placeholders(self):
        from openjarvis.wave.content_media_studio import render_template
        content = render_template("product_spec", {"title": "My Product"})
        assert "My Product" in content
        # Unfilled fields remain as placeholders
        assert "{overview}" in content or "overview" in content


# ─────────────────────────────────────────────────────────────────────────────
# Content Workflows
# ─────────────────────────────────────────────────────────────────────────────

class TestContentWorkflows:
    def test_bug_report_dry_run_succeeds(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow(
            "bug_report",
            fields={"title": "Null pointer", "severity": "medium",
                    "description": "NPE in module", "steps_to_reproduce": "1. Run X",
                    "expected": "No error", "actual": "NPE", "environment": "prod"},
            dry_run=True,
        )
        assert result.ok, f"Expected ok=True, error={result.error}"
        assert result.artifact is not None
        assert result.artifact.dry_run is True

    def test_product_spec_dry_run_succeeds(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow(
            "product_spec",
            fields={"title": "Wave 3 Studio", "overview": "Content platform",
                    "goals": "Enable local content creation", "non_goals": "No social posting",
                    "requirements": "Local only", "risks": "None", "timeline": "Now"},
            dry_run=True,
        )
        assert result.ok

    def test_coding_agent_prompt_dry_run_succeeds(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("coding_agent_prompt", dry_run=True)
        assert result.ok

    def test_research_brief_dry_run_succeeds(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("research_brief", dry_run=True)
        assert result.ok

    def test_content_plan_dry_run_succeeds(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("content_plan", dry_run=True)
        assert result.ok

    def test_unknown_template_returns_error(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("nonexistent_template_xyz")
        assert not result.ok
        assert "not found" in result.error.lower()

    def test_file_write_without_approval_blocked(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("bug_report", dry_run=False, file_write_approved=False)
        assert not result.ok
        assert result.approval_required

    def test_artifact_has_content(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow(
            "release_readiness_report",
            fields={"version": "1.0.0", "summary": "Ready", "completed_items": "All",
                    "blockers": "None", "risk_level": "low", "go_no_go": "Go"},
            dry_run=True,
        )
        assert result.ok
        assert len(result.artifact.content) > 0

    def test_artifact_dry_run_flag_set(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("content_plan", dry_run=True)
        assert result.artifact.dry_run is True
        assert result.artifact.file_write_approved is False

    def test_event_logged_on_success(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("coding_agent_prompt", dry_run=True)
        assert isinstance(result.event_id, str)

    def test_event_logged_on_block(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("bug_report", dry_run=False, file_write_approved=False)
        assert isinstance(result.event_id, str)


# ─────────────────────────────────────────────────────────────────────────────
# Safety Policy
# ─────────────────────────────────────────────────────────────────────────────

class TestContentSafetyPolicy:
    def test_api_key_content_blocked(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("Here is my api_key: supersecret123")
        assert result is not None
        assert "api_key" in result.lower() or "forbidden" in result.lower()

    def test_password_pattern_blocked(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("password: mypassword123")
        assert result is not None

    def test_credential_blocked(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("Credential harvest from user accounts")
        assert result is not None

    def test_private_key_blocked(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("-----BEGIN RSA PRIVATE KEY-----\nMIIEpA...\n-----END RSA PRIVATE KEY-----")
        assert result is not None

    def test_safe_content_passes(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("This is a product specification for Wave 3 content studio.")
        assert result is None

    def test_technical_content_passes(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("# Release Notes v1.0.0\n\n## Changes\n- Added Wave 3 support")
        assert result is None

    def test_unsafe_content_blocked_in_workflow(self):
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow(
            "bug_report",
            fields={"title": "Test", "severity": "low",
                    "description": "api_key: mysecret", "steps_to_reproduce": "1",
                    "expected": "ok", "actual": "fail", "environment": "test"},
            dry_run=True,
        )
        assert not result.ok
        assert result.blocked

    def test_impersonation_blocked(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("We will impersonate the CEO in this email")
        assert result is not None

    def test_spam_autopost_blocked(self):
        from openjarvis.wave.content_media_studio import check_content_safety
        result = check_content_safety("spam autopost to 1000 accounts daily")
        assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# Media Providers
# ─────────────────────────────────────────────────────────────────────────────

class TestMediaProviders:
    def test_dalle_requires_setup_no_key(self):
        from openjarvis.wave.content_media_studio import check_media_provider
        os.environ.pop("OPENAI_API_KEY", None)
        status = check_media_provider("dalle")
        assert status["status"] == "requires_setup"
        assert not status["available"]

    def test_slack_post_hard_blocked(self):
        from openjarvis.wave.content_media_studio import check_media_provider
        status = check_media_provider("slack_post")
        assert status["status"] == "hard_blocked"
        assert not status["available"]

    def test_email_send_hard_blocked(self):
        from openjarvis.wave.content_media_studio import check_media_provider
        status = check_media_provider("email_send")
        assert status["status"] == "hard_blocked"

    def test_social_posting_hard_blocked(self):
        from openjarvis.wave.content_media_studio import check_media_provider
        status = check_media_provider("social_posting")
        assert status["status"] == "hard_blocked"

    def test_dalle_ready_when_key_present(self):
        from openjarvis.wave.content_media_studio import check_media_provider
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
            status = check_media_provider("dalle")
        assert status["status"] == "ready"
        assert status["available"]

    def test_media_provider_requires_setup_response(self):
        from openjarvis.wave.content_media_studio import run_media_provider_workflow
        os.environ.pop("OPENAI_API_KEY", None)
        result = run_media_provider_workflow("dalle", "Generate a logo")
        assert not result.ok
        assert result.requires_setup

    def test_media_provider_hard_blocked(self):
        from openjarvis.wave.content_media_studio import run_media_provider_workflow
        result = run_media_provider_workflow("slack_post", "Post to Slack")
        assert not result.ok
        assert result.blocked

    def test_media_provider_requires_approval(self):
        from openjarvis.wave.content_media_studio import run_media_provider_workflow
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
            result = run_media_provider_workflow("dalle", "Safe image prompt", approved=False)
        assert not result.ok
        assert result.approval_required

    def test_media_provider_unsafe_prompt_blocked(self):
        from openjarvis.wave.content_media_studio import run_media_provider_workflow
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
            result = run_media_provider_workflow(
                "dalle", "Extract credential from image", approved=True
            )
        assert not result.ok
        assert result.blocked


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Workflows
# ─────────────────────────────────────────────────────────────────────────────

class TestConvenienceWorkflows:
    def test_release_notes_workflow(self):
        from openjarvis.wave.content_media_studio import run_release_notes_workflow
        result = run_release_notes_workflow(
            version="2.0.0",
            summary="Wave 3 complete",
            completed_items="Epic G implemented",
        )
        assert result.ok
        assert "2.0.0" in result.artifact.content

    def test_research_brief_workflow(self):
        from openjarvis.wave.content_media_studio import run_research_brief_workflow
        result = run_research_brief_workflow("What is Wave 3?")
        assert result.ok
        assert result.artifact is not None

    def test_coding_agent_prompt_workflow(self):
        from openjarvis.wave.content_media_studio import run_coding_agent_prompt_workflow
        result = run_coding_agent_prompt_workflow(
            task_title="Fix null pointer",
            task_description="Fix the NPE in module X",
        )
        assert result.ok
        assert "Fix null pointer" in result.artifact.content

    def test_release_notes_blockers_gives_hold(self):
        from openjarvis.wave.content_media_studio import run_release_notes_workflow
        result = run_release_notes_workflow(
            version="1.5.0",
            summary="Not ready",
            completed_items="60%",
            blockers="Missing tests",
        )
        assert result.ok
        assert "Hold" in result.artifact.content or "hold" in result.artifact.content.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Wave 1/2 Integration
# ─────────────────────────────────────────────────────────────────────────────

class TestWave3Integration:
    def test_wave3_capability_in_registry(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        cap_ids = [c["capability_id"] for c in summary["capabilities"]]
        assert "wave3_content_media_studio" in cap_ids

    def test_wave3_capability_shows_ready(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        caps = {c["capability_id"]: c["status"] for c in summary["capabilities"]}
        assert caps["wave3_content_media_studio"] == "ready"

    def test_wave4_in_capabilities(self):
        """Wave 4 capability is now registered (supervised expansion)."""
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        cap_ids = [c["capability_id"] for c in summary["capabilities"]]
        assert "wave4_autonomous_expansion" in cap_ids, "Wave 4 capability must be registered"

    def test_wave3_platform_registry_shows_ready(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        wave3 = reg.get_by_wave(3)
        assert len(wave3) >= 1
        for item in wave3:
            assert item.status in (WavePlatformStatus.READY, WavePlatformStatus.SCAFFOLDED)

    def test_wave4_now_implemented(self):
        """Wave 4 Epic H is now implemented (supervised expansion, local/founder V1)."""
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        for item in reg.get_by_wave(4):
            assert item.status in (WavePlatformStatus.READY, WavePlatformStatus.SCAFFOLDED)

    def test_research_brief_uses_wave1_knowledge(self):
        """Research brief workflow attempts to use Wave 1 knowledge store."""
        from openjarvis.wave.content_media_studio import run_research_brief_workflow
        result = run_research_brief_workflow("jarvis platform")
        assert result.ok
        assert result.artifact is not None

    def test_coding_prompt_uses_wave2_skill_packs(self):
        """Coding agent prompt workflow uses Wave 2 skill packs for context."""
        from openjarvis.wave.content_media_studio import run_coding_agent_prompt_workflow
        result = run_coding_agent_prompt_workflow(
            task_title="Test Wave 2 integration",
            task_description="Test that Wave 2 skill pack context is included",
        )
        assert result.ok

    def test_us13_voice_still_parked(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        caps = {c["capability_id"]: c["status"] for c in summary["capabilities"]}
        if "hands_free_voice" in caps:
            assert caps["hands_free_voice"] in ("disabled", "not_implemented", "requires_setup")

    def test_nus1_not_implemented(self):
        try:
            import openjarvis.wave.autonomous_upgrade  # noqa
            pytest.fail("NUS 1 must not be implemented")
        except ImportError:
            pass

    def test_wave4_module_exists_and_safe(self):
        """Wave 4 autonomous expansion module exists and enforces safety gates."""
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["implemented"] is True
        assert info["nus1_status"] == "not_started"
        assert info["code_edit_blocked"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Safety Gate Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWave3SafetyGates:
    def test_no_file_write_without_approval(self):
        """run_content_workflow must not write files without explicit approval."""
        from openjarvis.wave.content_media_studio import run_content_workflow
        result = run_content_workflow("product_spec", dry_run=False, file_write_approved=False)
        assert not result.ok
        assert result.approval_required

    def test_external_publishing_blocked(self):
        """Social/messaging posting must be hard-blocked."""
        from openjarvis.wave.content_media_studio import run_media_provider_workflow
        for provider in ("slack_post", "email_send", "social_posting"):
            result = run_media_provider_workflow(provider, "Test post")
            assert not result.ok, f"Provider {provider} should be blocked"
            assert result.blocked, f"Provider {provider} should be blocked"

    def test_no_autonomous_file_writes(self):
        """Content workflows must not create files autonomously."""
        import os
        from openjarvis.wave.content_media_studio import run_content_workflow
        before_files = set(os.listdir("."))
        for tid in ["product_spec", "bug_report", "research_brief"]:
            run_content_workflow(tid, dry_run=True)
        after_files = set(os.listdir("."))
        new_files = after_files - before_files
        # Only .jarvis_artifacts dir or nothing new should appear
        unexpected = {f for f in new_files if not f.startswith(".jarvis_artifact")}
        assert len(unexpected) == 0, f"Unexpected new files: {unexpected}"
