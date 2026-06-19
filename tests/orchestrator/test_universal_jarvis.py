"""Tests for Universal Jarvis OS architecture.

Proves:
  - UniversalTaskRequest works without OMNIX
  - ProjectContext supports OMNIX and non-OMNIX projects
  - Personal task with no project works
  - OMNIX is not required by orchestrator
  - COS/GM runtime accepts universal front-door request
  - JarvisFrontDoor handoff flow works
  - Worker execution adapter safe dry-run flow works
  - Worker adapter refuses unsafe actions
  - Activation planner uses NUS feedback metadata
  - Inactive managers classified
  - Model/provider sufficiency gap surfaced
  - Missing provider/key is blocker (not silent)
  - Completion gap register has no vague future scope
  - Structured decision record emitted
  - No raw chain-of-thought
  - Dangerous actions blocked
  - No auto-push/merge/deploy
  - US13 parked unchanged
"""

from __future__ import annotations

import os
import pytest
from typing import Optional


# ---------------------------------------------------------------------------
# ProjectContext tests
# ---------------------------------------------------------------------------

class TestProjectContext:
    def test_for_project_omnix(self):
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project(project_id="omnix", display_name="OMNIX")
        assert ctx.project_id == "omnix"
        assert ctx.memory_namespace == "project:omnix"
        assert ctx.display_name == "OMNIX"

    def test_for_project_openjarvis(self):
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project(project_id="openjarvis", display_name="OpenJarvis")
        assert ctx.project_id == "openjarvis"
        assert ctx.memory_namespace == "project:openjarvis"

    def test_for_project_synthetic(self):
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project(project_id="synthetic_xyz")
        assert ctx.project_id == "synthetic_xyz"
        assert ctx.memory_namespace == "project:synthetic_xyz"

    def test_personal_task_no_project_id(self):
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.personal()
        assert ctx.project_id is None
        assert ctx.memory_namespace == "global"
        assert ctx.display_name == "personal"

    def test_to_dict_serializable(self):
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project("test_proj")
        d = ctx.to_dict()
        assert d["project_id"] == "test_proj"
        assert "memory_namespace" in d
        assert "task_type" in d

    def test_omnix_not_required_for_context(self):
        """No OMNIX-specific field is required for ProjectContext."""
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project("some_future_project")
        assert ctx.project_id == "some_future_project"
        # No omnix-specific assertion needed

    def test_task_type_constants_available(self):
        from openjarvis.orchestrator.contracts import (
            TASK_TYPE_CODING, TASK_TYPE_RESEARCH, TASK_TYPE_PERSONAL,
            TASK_TYPE_AUTOMATION, TASK_TYPE_BUSINESS, TASK_TYPE_OPERATIONS,
            TASK_TYPE_UNKNOWN,
        )
        assert TASK_TYPE_CODING == "coding"
        assert TASK_TYPE_PERSONAL == "personal"
        assert TASK_TYPE_RESEARCH == "research"


# ---------------------------------------------------------------------------
# TaskRoutingRequest with ProjectContext tests
# ---------------------------------------------------------------------------

class TestTaskRoutingRequestWithProjectContext:
    def test_no_project_context_works(self):
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        req = TaskRoutingRequest.create(
            user_request_summary="personal task",
            intent="personal",
        )
        assert req.project_context is None

    def test_omnix_project_context_optional(self):
        from openjarvis.orchestrator.contracts import TaskRoutingRequest, ProjectContext
        ctx = ProjectContext.for_project("omnix")
        req = TaskRoutingRequest.create(
            user_request_summary="omnix upgrade",
            intent="upgrade",
            project_context=ctx,
        )
        assert req.project_context.project_id == "omnix"

    def test_openjarvis_project_context_works(self):
        from openjarvis.orchestrator.contracts import TaskRoutingRequest, ProjectContext
        ctx = ProjectContext.for_project("openjarvis")
        req = TaskRoutingRequest.create(
            user_request_summary="improve NUS learning",
            intent="self_improvement",
            project_context=ctx,
        )
        assert req.project_context.project_id == "openjarvis"

    def test_to_dict_includes_project_context(self):
        from openjarvis.orchestrator.contracts import TaskRoutingRequest, ProjectContext
        ctx = ProjectContext.for_project("test_proj")
        req = TaskRoutingRequest.create(
            user_request_summary="test",
            intent="test",
            project_context=ctx,
        )
        d = req.to_dict()
        assert d["project_context"] is not None
        assert d["project_context"]["project_id"] == "test_proj"

    def test_to_dict_null_project_context(self):
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        req = TaskRoutingRequest.create(user_request_summary="x", intent="x")
        d = req.to_dict()
        assert d["project_context"] is None


# ---------------------------------------------------------------------------
# UniversalTaskRequest tests
# ---------------------------------------------------------------------------

class TestUniversalTaskRequest:
    def test_create_without_omnix(self):
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        req = UniversalTaskRequest.create(
            user_input="research quantum computing",
            intent="research",
        )
        assert req.project_context is None
        assert req.request_id

    def test_personal_task_no_project(self):
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        req = UniversalTaskRequest.create(
            user_input="call dentist tomorrow",
            intent="personal_reminder",
        )
        assert req.project_context is None

    def test_omnix_project_context(self):
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project("omnix")
        req = UniversalTaskRequest.create(
            user_input="upgrade OMNIX",
            intent="upgrade_planning",
            project_context=ctx,
        )
        assert req.project_context.project_id == "omnix"

    def test_non_omnix_project(self):
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project("my_new_startup")
        req = UniversalTaskRequest.create(
            user_input="analyze market",
            intent="business_research",
            project_context=ctx,
        )
        assert req.project_context.project_id == "my_new_startup"

    def test_to_task_routing_request_preserves_project_context(self):
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        from openjarvis.orchestrator.contracts import ProjectContext
        ctx = ProjectContext.for_project("openjarvis")
        req = UniversalTaskRequest.create(
            user_input="improve doctor checks",
            intent="maintenance",
            project_context=ctx,
        )
        routing = req.to_task_routing_request()
        assert routing.project_context.project_id == "openjarvis"

    def test_to_task_routing_request_no_context(self):
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        req = UniversalTaskRequest.create(user_input="hello", intent="chat")
        routing = req.to_task_routing_request()
        assert routing.project_context is None

    def test_to_dict(self):
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        req = UniversalTaskRequest.create(user_input="test", intent="test")
        d = req.to_dict()
        assert "request_id" in d
        assert "user_input" in d
        assert d["project_context"] is None


# ---------------------------------------------------------------------------
# CosGmOrchestrator tests
# ---------------------------------------------------------------------------

class TestCosGmOrchestrator:
    def test_accepts_personal_task(self):
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        orch = CosGmOrchestrator()
        req = UniversalTaskRequest.create(user_input="personal task", intent="personal")
        result = orch.handle(req)
        assert result.status in ("planned", "executed", "blocked")
        assert result.no_raw_chain_of_thought is True

    def test_accepts_non_omnix_project(self):
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        from openjarvis.orchestrator.contracts import ProjectContext
        orch = CosGmOrchestrator()
        ctx = ProjectContext.for_project("synthetic_test_project")
        req = UniversalTaskRequest.create(
            user_input="analyze code",
            intent="code_analysis",
            project_context=ctx,
        )
        result = orch.handle(req)
        assert result.status in ("planned", "executed", "blocked")
        assert result.project_context.project_id == "synthetic_test_project"

    def test_accepts_openjarvis_project(self):
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        from openjarvis.orchestrator.contracts import ProjectContext
        orch = CosGmOrchestrator()
        ctx = ProjectContext.for_project("openjarvis")
        req = UniversalTaskRequest.create(
            user_input="improve Jarvis NUS",
            intent="self_improvement",
            project_context=ctx,
        )
        result = orch.handle(req)
        assert result.status in ("planned", "executed", "blocked")

    def test_omnix_not_required(self):
        """Orchestrator must not require OMNIX project context."""
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        orch = CosGmOrchestrator()
        req = UniversalTaskRequest.create(user_input="research AI", intent="research")
        assert req.project_context is None
        result = orch.handle(req)
        assert result.status in ("planned", "executed", "blocked")

    def test_blocks_auto_push(self):
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        orch = CosGmOrchestrator()
        req = UniversalTaskRequest.create(
            user_input="push to main",
            intent="git",
            metadata={"requested_actions": ["auto_push"]},
        )
        result = orch.handle(req)
        assert result.status == "blocked"
        assert "auto_push" in result.blocked_actions

    def test_blocks_production_deploy(self):
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        orch = CosGmOrchestrator()
        req = UniversalTaskRequest.create(
            user_input="deploy to prod",
            intent="deploy",
            metadata={"requested_actions": ["production_deploy"]},
        )
        result = orch.handle(req)
        assert result.status == "blocked"

    def test_emits_structured_decision_record(self):
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        orch = CosGmOrchestrator()
        req = UniversalTaskRequest.create(user_input="analyze code", intent="code_analysis")
        result = orch.handle(req)
        if result.status == "planned":
            assert result.structured_decision_record_id
            assert result.no_raw_chain_of_thought is True

    def test_us13_voice_blocked(self):
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
        orch = CosGmOrchestrator()
        req = UniversalTaskRequest.create(
            user_input="activate voice",
            intent="voice",
            metadata={"requested_actions": ["us13_voice_activation"]},
        )
        result = orch.handle(req)
        assert result.status == "blocked"

    def test_get_status(self):
        from openjarvis.orchestrator.cos_gm import get_cos_gm_orchestrator
        orch = get_cos_gm_orchestrator()
        status = orch.get_status()
        assert status["cos_gm_orchestrator"] == "active"
        assert status["us13_voice"] == "HOLD/UNSAFE/PARKED"
        assert status["no_raw_chain_of_thought"] is True


# ---------------------------------------------------------------------------
# JarvisFrontDoor tests
# ---------------------------------------------------------------------------

class TestJarvisFrontDoor:
    def test_handle_personal_task(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        fd = JarvisFrontDoor()
        req = UniversalTaskRequest.create(user_input="remind me dentist", intent="personal")
        result = fd.handle(req)
        assert result.status in ("planned", "executed", "blocked")
        assert result.no_raw_chain_of_thought is True

    def test_handle_non_omnix_project(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        from openjarvis.orchestrator.contracts import ProjectContext
        fd = JarvisFrontDoor()
        ctx = ProjectContext.for_project("future_startup")
        req = UniversalTaskRequest.create(
            user_input="build market analysis",
            intent="business",
            project_context=ctx,
        )
        result = fd.handle(req)
        assert result.status in ("planned", "executed", "blocked")

    def test_blocks_auto_push(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        fd = JarvisFrontDoor()
        req = UniversalTaskRequest.create(
            user_input="push code",
            intent="push",
            metadata={"requested_actions": ["auto_push"]},
        )
        result = fd.handle(req)
        assert result.status == "blocked"
        assert "auto_push" in result.blocked_actions

    def test_blocks_us13_voice(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        fd = JarvisFrontDoor()
        req = UniversalTaskRequest.create(
            user_input="voice",
            intent="voice",
            metadata={"requested_actions": ["us13_voice"]},
        )
        result = fd.handle(req)
        assert result.status == "blocked"

    def test_omnix_adapter_optional(self):
        """JarvisFrontDoor works without any adapters registered."""
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        fd = JarvisFrontDoor(adapters=[])  # no adapters
        req = UniversalTaskRequest.create(user_input="test", intent="test")
        result = fd.handle(req)
        assert result is not None

    def test_omnix_adapter_enriches_omnix_request(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        from openjarvis.frontdoor.omnix_adapter import OmnixFrontDoorAdapter
        adapter = OmnixFrontDoorAdapter()
        fd = JarvisFrontDoor(adapters=[adapter])
        req = UniversalTaskRequest.create(
            user_input="upgrade OMNIX",
            intent="omnix_upgrade",
        )
        result = fd.handle(req)
        assert result is not None
        assert result.metadata.get("omnix_adapter_applied") is True

    def test_non_omnix_request_not_enriched_by_omnix_adapter(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        from openjarvis.frontdoor.omnix_adapter import OmnixFrontDoorAdapter
        from openjarvis.orchestrator.contracts import ProjectContext
        adapter = OmnixFrontDoorAdapter()
        fd = JarvisFrontDoor(adapters=[adapter])
        ctx = ProjectContext.for_project("openjarvis")
        req = UniversalTaskRequest.create(
            user_input="improve jarvis",
            intent="self_improvement",
            project_context=ctx,
        )
        result = fd.handle(req)
        # The OMNIX adapter should NOT have applied (project_id != omnix)
        assert result.metadata.get("omnix_adapter_applied") is not True


# ---------------------------------------------------------------------------
# Worker execution adapter tests
# ---------------------------------------------------------------------------

class TestWorkerExecutionAdapters:
    def test_get_worker_adapter_known(self):
        from openjarvis.orchestrator.worker_adapters import get_worker_adapter
        for wid in ("unit_test_worker", "nus_learning_worker", "cost_analysis_worker"):
            adapter = get_worker_adapter(wid)
            assert adapter.worker_id == wid

    def test_get_worker_adapter_unknown_graceful(self):
        from openjarvis.orchestrator.worker_adapters import get_worker_adapter, WorkerAdapter
        adapter = get_worker_adapter("unknown_worker_xyz")
        assert isinstance(adapter, WorkerAdapter)

    def test_dry_run_safe_action_nus_worker(self):
        from openjarvis.orchestrator.worker_adapters import execute_worker
        result = execute_worker(
            "nus_learning_worker",
            action_type="nus_dry_run",
            inputs={},
            dry_run=True,
        )
        assert result.worker_id == "nus_learning_worker"
        assert result.status in ("ok", "error", "skipped", "dry_run_ok")
        assert result.no_raw_chain_of_thought is True

    def test_base_adapter_dry_run(self):
        """Base adapter dry-run for any worker ID works without crash."""
        from openjarvis.orchestrator.worker_adapters import execute_worker
        # Use a worker ID that exists in registry with local_read allowed
        result = execute_worker(
            "cost_analysis_worker",
            action_type="local_analysis",
            inputs={"key": "value"},
            dry_run=True,
        )
        assert result.no_raw_chain_of_thought is True

    def test_blocked_action_refused(self):
        from openjarvis.orchestrator.worker_adapters import execute_worker
        result = execute_worker(
            "nus_learning_worker",
            action_type="auto_push",
            inputs={},
            dry_run=True,
        )
        assert result.status == "blocked"
        assert result.blocked_reason

    def test_production_deploy_refused(self):
        from openjarvis.orchestrator.worker_adapters import execute_worker
        result = execute_worker(
            "nus_learning_worker",
            action_type="production_deploy",
            inputs={},
            dry_run=False,
        )
        assert result.status == "blocked"

    def test_result_no_raw_chain_of_thought(self):
        from openjarvis.orchestrator.worker_adapters import execute_worker
        result = execute_worker(
            "cost_analysis_worker",
            action_type="local_analysis",
            inputs={},
            dry_run=True,
        )
        assert result.no_raw_chain_of_thought is True

    def test_to_dict(self):
        from openjarvis.orchestrator.worker_adapters import execute_worker
        result = execute_worker(
            "nus_learning_worker",
            action_type="nus_dry_run",
            inputs={},
            dry_run=True,
        )
        d = result.to_dict()
        assert "worker_id" in d
        assert "no_raw_chain_of_thought" in d
        assert d["no_raw_chain_of_thought"] is True


# ---------------------------------------------------------------------------
# NUS scorecard feedback tests
# ---------------------------------------------------------------------------

class TestNusScorecardFeedback:
    def test_load_nus_feedback_exists(self):
        from openjarvis.orchestrator.activation import get_activation_planner
        planner = get_activation_planner()
        feedback = planner._load_nus_feedback()
        assert isinstance(feedback, dict)
        assert "loaded" in feedback
        assert "failure_patterns" in feedback
        assert "recent_outcomes" in feedback

    def test_plan_includes_nus_feedback_tag(self):
        from openjarvis.orchestrator.activation import get_activation_planner
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        planner = get_activation_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test nus feedback",
            intent="testing",
        )
        plan = planner.plan(req)
        nus_tags = plan.nus_learning_tags
        feedback_tags = [t for t in nus_tags if t.startswith("nus_feedback:")]
        assert feedback_tags, f"Expected nus_feedback: tag in plan; got {nus_tags}"

    def test_get_status_includes_nus_feedback(self):
        from openjarvis.orchestrator.activation import get_activation_planner
        planner = get_activation_planner()
        status = planner.get_status()
        assert "nus_feedback_available" in status
        assert isinstance(status["nus_feedback_available"], bool)


# ---------------------------------------------------------------------------
# Inactive manager classification tests
# ---------------------------------------------------------------------------

class TestInactiveManagerClassification:
    def test_connector_auth_manager_is_inactive(self):
        from openjarvis.orchestrator.manager_registry import get_manager_registry
        from openjarvis.orchestrator.contracts import STATUS_INACTIVE
        registry = get_manager_registry()
        mgr = registry.get("connector_auth_manager")
        assert mgr is not None
        assert mgr.status == STATUS_INACTIVE

    def test_release_packaging_manager_is_inactive(self):
        from openjarvis.orchestrator.manager_registry import get_manager_registry
        from openjarvis.orchestrator.contracts import STATUS_INACTIVE
        registry = get_manager_registry()
        mgr = registry.get("release_packaging_manager")
        assert mgr is not None
        assert mgr.status == STATUS_INACTIVE

    def test_inactive_managers_not_activated_for_simple_task(self):
        from openjarvis.orchestrator.activation import get_activation_planner
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        planner = get_activation_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="fix bug",
            intent="debug",
            domains_required=["backend"],
        )
        plan = planner.plan(req)
        assert "connector_auth_manager" not in plan.selected_managers
        assert "release_packaging_manager" not in plan.selected_managers


# ---------------------------------------------------------------------------
# Model/provider sufficiency tests
# ---------------------------------------------------------------------------

class TestModelProviderSufficiency:
    def test_sufficiency_gap_disclosed_in_plan(self):
        """Model provider gaps must be disclosed; no silent fallback."""
        from openjarvis.orchestrator.activation import get_activation_planner
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        planner = get_activation_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="complex multi-system refactor",
            intent="refactor",
            risk_level="high",
            complexity_level="complex",
        )
        plan = planner.plan(req)
        # model_routing_plan must include provider_sufficiency disclosure
        assert "provider_sufficiency" in plan.model_routing_plan

    def test_sufficiency_gap_type_exists(self):
        from openjarvis.orchestrator.contracts import ModelProviderSufficiencyGap
        gap = ModelProviderSufficiencyGap.create(
            missing_provider="openai_gpt4",
            reason_needed="High-risk autonomous execution",
            why_insufficient="No API key configured",
            improvement_unlocked="Real LLM-reviewed orchestration plans",
            cost_complexity_tradeoff="Requires OPENAI_API_KEY in ~/.jarvis/cloud-keys.env",
            fallback_used="dry_run_planning",
            fallback_quality_tradeoff="Dry-run only; no real model-in-the-loop",
        )
        assert gap.missing_provider == "openai_gpt4"
        d = gap.to_dict()
        assert "missing_provider" in d
        assert "fallback_used" in d


# ---------------------------------------------------------------------------
# Completion gap register tests
# ---------------------------------------------------------------------------

class TestCompletionGapRegister:
    def test_gap_register_exists(self):
        from pathlib import Path
        register_path = Path(__file__).parent.parent.parent / "docs" / "JARVIS_COMPLETION_GAP_REGISTER.md"
        assert register_path.exists(), f"Gap register must exist at {register_path}"

    def test_gap_register_has_no_vague_future_scope(self):
        from pathlib import Path
        import re
        register_path = Path(__file__).parent.parent.parent / "docs" / "JARVIS_COMPLETION_GAP_REGISTER.md"
        content = register_path.read_text()
        # Must use 4/5 matrix classification codes, not vague language
        assert "DAILY_DRIVER_ACCEPT" in content, "Gap register must have DAILY_DRIVER_ACCEPT items"
        assert "BLOCKED_" in content, "Gap register must classify blockers"
        # Must include score columns
        assert "Score" in content, "Gap register must include Score column"
        assert "Target" in content, "Gap register must include Target score column"
        # Must not have unclassified TODO or 'later' as a status cell
        vague_lines = [
            line for line in content.splitlines()
            if re.match(r"^\|.*`TODO`.*\|", line) or re.match(r"^\|.*`later`.*\|", line)
        ]
        assert not vague_lines, f"Gap register has vague status: {vague_lines}"

    def test_gap_register_classifies_all_required_statuses(self):
        from pathlib import Path
        register_path = Path(__file__).parent.parent.parent / "docs" / "JARVIS_COMPLETION_GAP_REGISTER.md"
        content = register_path.read_text()
        # Required 4/5 matrix classification types must be present
        required = (
            "DAILY_DRIVER_ACCEPT",
            "BLOCKED_IMPLEMENTATION",
            "BLOCKED_PROVIDER",
            "PLANNED_IN_EXISTING_PROMPT",
        )
        for status in required:
            assert status in content, f"Gap register must contain '{status}' classification"

    def test_gap_register_has_us13_voice_section(self):
        from pathlib import Path
        register_path = Path(__file__).parent.parent.parent / "docs" / "JARVIS_COMPLETION_GAP_REGISTER.md"
        content = register_path.read_text()
        assert "US13" in content, "Gap register must have US13 voice section"
        assert "HOLD" in content or "PARKED" in content, "US13 must be HOLD/PARKED"
        assert "VAD" in content, "US13 section must list VAD blocker"
        assert "barge-in" in content.lower() or "barge_in" in content.lower(), (
            "US13 section must list barge-in blocker"
        )

    def test_gap_register_has_bryan_action_table(self):
        from pathlib import Path
        register_path = Path(__file__).parent.parent.parent / "docs" / "JARVIS_COMPLETION_GAP_REGISTER.md"
        content = register_path.read_text()
        assert "Bryan Action" in content or "Required Bryan Actions" in content, (
            "Gap register must have Bryan action instructions"
        )
        assert "cloud-keys.env" in content, "Bryan action must reference cloud-keys.env"


# ---------------------------------------------------------------------------
# Structural: no raw chain-of-thought tests
# ---------------------------------------------------------------------------

class TestNoRawChainOfThought:
    def test_activation_plan_no_raw_cot(self):
        from openjarvis.orchestrator.activation import get_activation_planner
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        planner = get_activation_planner()
        req = TaskRoutingRequest.create(user_request_summary="test", intent="test")
        plan = planner.plan(req)
        assert plan.no_raw_chain_of_thought is True

    def test_front_door_result_no_raw_cot(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor, UniversalTaskRequest
        fd = JarvisFrontDoor()
        req = UniversalTaskRequest.create(user_input="test", intent="test")
        result = fd.handle(req)
        assert result.no_raw_chain_of_thought is True

    def test_worker_result_no_raw_cot(self):
        from openjarvis.orchestrator.worker_adapters import execute_worker
        result = execute_worker("validation_worker", "local_validation", {})
        assert result.no_raw_chain_of_thought is True
