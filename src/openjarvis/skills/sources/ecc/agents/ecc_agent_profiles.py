"""ECC Agent Profiles — Jarvis-native agent profile definitions.

Defines Jarvis agent profiles for execution-dependent ECC agents.
All profiles are disabled by default (reviewer_approved=False).
Activation requires Bryan's explicit approval AND Jarvis agent routing wiring.

Agents covered:
  - EccE2ERunnerAgent (ecc:agent:e2e-runner)
  - EccDocsResearcherAgent (ecc:agent:docs-researcher)
  - EccCodeReviewerAgent (ecc:agent:code-reviewer) — approval-waiting
  - EccSecurityReviewerAgent (ecc:agent:security-reviewer) — approval-waiting
  - EccPlannerAgent (ecc:agent:planner) — approval-waiting
  - EccArchitectAgent (ecc:agent:architect) — approval-waiting
  - EccTddGuideAgent (ecc:agent:tdd-guide) — approval-waiting
  - EccSpecMinerAgent (ecc:agent:spec-miner) — approval-waiting
  - EccRefactorCleanerAgent (ecc:agent:refactor-cleaner) — approval-waiting
  - EccDocUpdaterAgent (ecc:agent:doc-updater) — approval-waiting
  - EccBuildErrorResolverAgent (ecc:agent:build-error-resolver) — approval-waiting
  - EccReviewerAgent (ecc:agent:reviewer) — approval-waiting
  - EccExplorerAgent (ecc:agent:explorer) — approval-waiting

Machine-readable: openjarvis.skills.sources.ecc.agents.ecc_agent_profiles
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


AGENT_PLAN1_STATE_APPROVAL = "READY_BUT_WAITING_FOR_APPROVAL"

# Activation route for all agents
AGENT_ACTIVATION_ROUTE = (
    "1. Wire Jarvis agent routing framework (JarvisAgentRouter.register_profile()) "
    "2. Bryan approves agent: set reviewer_approved=True "
    "3. Agent becomes discoverable via Jarvis front door (/v1/agents/{agent_id})"
)
AGENT_ROLLBACK_PATH = "Unregister from JarvisAgentRouter; set reviewer_approved=False"


@dataclass
class AgentProfile:
    """Jarvis-native agent profile definition."""

    agent_id: str
    name: str
    role: str
    capabilities: List[str]
    permission_scopes: List[str]
    reviewer_approved: bool = False
    enabled: bool = False
    plan1_state: str = AGENT_PLAN1_STATE_APPROVAL
    description: str = ""
    activation_route: str = AGENT_ACTIVATION_ROUTE
    rollback_path: str = AGENT_ROLLBACK_PATH
    live_test_command: str = ""
    mocked_test_command: str = ""

    def enable(self) -> None:
        if not self.reviewer_approved:
            raise RuntimeError(
                f"Agent '{self.agent_id}' cannot be enabled without reviewer_approved=True. "
                "Bryan must explicitly approve agent routing wiring."
            )
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
        self.reviewer_approved = False

    def mock_invocation(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "dry_run": True,
            "result": "MOCKED_SUCCESS",
            "plan1_state": self.plan1_state,
            "enabled": self.enabled,
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "permission_scopes": self.permission_scopes,
            "reviewer_approved": self.reviewer_approved,
            "enabled": self.enabled,
            "plan1_state": self.plan1_state,
            "description": self.description,
            "activation_route": self.activation_route,
            "rollback_path": self.rollback_path,
        }


# ---------------------------------------------------------------------------
# Execution agents (from ADAPT_NEEDED — wrappers now built)
# ---------------------------------------------------------------------------

ECC_E2E_RUNNER_AGENT = AgentProfile(
    agent_id="ecc:agent:e2e-runner",
    name="E2E Test Runner Agent",
    role="execution",
    capabilities=["run_playwright_tests", "run_pytest_suites", "capture_test_results"],
    permission_scopes=["test:e2e:run", "filesystem:test_dirs:read"],
    description=(
        "Jarvis agent that orchestrates end-to-end test execution via E2ETestRunner wrapper. "
        "Uses Playwright + pytest under the hood. "
        "Requires Playwright installed and Bryan's approval for test execution authorization."
    ),
    live_test_command=(
        "uv run python -c \"from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import "
        "ECC_E2E_RUNNER_AGENT; print(ECC_E2E_RUNNER_AGENT.mock_invocation())\""
    ),
    mocked_test_command=(
        "uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_e2e_runner_agent_mocked"
    ),
)

ECC_DOCS_RESEARCHER_AGENT = AgentProfile(
    agent_id="ecc:agent:docs-researcher",
    name="Documentation Researcher Agent",
    role="research",
    capabilities=["search_documentation", "extract_api_patterns", "synthesize_references"],
    permission_scopes=["search:docs:read", "web:read_only"],
    description=(
        "Jarvis agent that researches documentation and synthesizes API patterns. "
        "Optionally uses EXA_API_KEY for deep research. Can operate with guidance-only mode "
        "if no search API key is configured (returns curated documentation references)."
    ),
    live_test_command=(
        "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.sources.ecc.agents."
        "ecc_agent_profiles import ECC_DOCS_RESEARCHER_AGENT; print(ECC_DOCS_RESEARCHER_AGENT.as_dict())\""
    ),
    mocked_test_command=(
        "uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_docs_researcher_agent_mocked"
    ),
)

# ---------------------------------------------------------------------------
# Planning/review agents (from READY_BUT_WAITING_FOR_APPROVAL)
# ---------------------------------------------------------------------------

ECC_CODE_REVIEWER_AGENT = AgentProfile(
    agent_id="ecc:agent:code-reviewer",
    name="Code Reviewer Agent",
    role="review",
    capabilities=["review_pr", "suggest_improvements", "check_standards"],
    permission_scopes=["code:read_only", "git:diff:read"],
    description="Jarvis agent that performs code review using ECC code-reviewer skill guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_code_reviewer_mocked",
)

ECC_SECURITY_REVIEWER_AGENT = AgentProfile(
    agent_id="ecc:agent:security-reviewer",
    name="Security Reviewer Agent",
    role="review",
    capabilities=["security_audit", "vulnerability_scan_guidance", "threat_model"],
    permission_scopes=["code:read_only", "security:audit:read"],
    description="Jarvis agent that performs security review using ECC security-reviewer guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_security_reviewer_mocked",
)

ECC_PLANNER_AGENT = AgentProfile(
    agent_id="ecc:agent:planner",
    name="Planner Agent",
    role="planning",
    capabilities=["task_breakdown", "sprint_planning", "dependency_analysis"],
    permission_scopes=["planning:read_only"],
    description="Jarvis planning agent using ECC planner guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_planner_mocked",
)

ECC_ARCHITECT_AGENT = AgentProfile(
    agent_id="ecc:agent:architect",
    name="Architect Agent",
    role="architecture",
    capabilities=["system_design", "architecture_review", "tech_decision"],
    permission_scopes=["architecture:read_only"],
    description="Jarvis architecture agent using ECC architect guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_architect_mocked",
)

ECC_TDD_GUIDE_AGENT = AgentProfile(
    agent_id="ecc:agent:tdd-guide",
    name="TDD Guide Agent",
    role="guidance",
    capabilities=["tdd_methodology", "test_patterns", "coverage_analysis"],
    permission_scopes=["guidance:read_only"],
    description="Jarvis TDD guidance agent using ECC tdd-guide skill.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_tdd_guide_mocked",
)

ECC_SPEC_MINER_AGENT = AgentProfile(
    agent_id="ecc:agent:spec-miner",
    name="Spec Miner Agent",
    role="analysis",
    capabilities=["spec_extraction", "requirement_analysis", "acceptance_criteria"],
    permission_scopes=["code:read_only", "docs:read_only"],
    description="Jarvis spec mining agent using ECC spec-miner guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_spec_miner_mocked",
)

ECC_REFACTOR_CLEANER_AGENT = AgentProfile(
    agent_id="ecc:agent:refactor-cleaner",
    name="Refactor Cleaner Agent",
    role="refactoring",
    capabilities=["code_cleanup", "refactoring_suggestions", "dead_code_detection"],
    permission_scopes=["code:read_only"],
    description="Jarvis refactoring agent using ECC refactor-cleaner guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_refactor_cleaner_mocked",
)

ECC_DOC_UPDATER_AGENT = AgentProfile(
    agent_id="ecc:agent:doc-updater",
    name="Documentation Updater Agent",
    role="documentation",
    capabilities=["doc_sync", "readme_update", "api_doc_generation"],
    permission_scopes=["docs:read_only", "git:diff:read"],
    description="Jarvis documentation agent using ECC doc-updater guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_doc_updater_mocked",
)

ECC_BUILD_ERROR_RESOLVER_AGENT = AgentProfile(
    agent_id="ecc:agent:build-error-resolver",
    name="Build Error Resolver Agent",
    role="debugging",
    capabilities=["error_analysis", "fix_suggestion", "dependency_resolution"],
    permission_scopes=["build:logs:read", "code:read_only"],
    description="Jarvis build error resolution agent using ECC build-error-resolver guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_build_error_resolver_mocked",
)

ECC_REVIEWER_AGENT = AgentProfile(
    agent_id="ecc:agent:reviewer",
    name="General Reviewer Agent",
    role="review",
    capabilities=["general_review", "feedback_synthesis"],
    permission_scopes=["code:read_only"],
    description="Jarvis general reviewer agent using ECC reviewer guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_reviewer_mocked",
)

ECC_EXPLORER_AGENT = AgentProfile(
    agent_id="ecc:agent:explorer",
    name="Codebase Explorer Agent",
    role="exploration",
    capabilities=["codebase_navigation", "symbol_search", "dependency_mapping"],
    permission_scopes=["code:read_only", "filesystem:read_only"],
    description="Jarvis codebase exploration agent using ECC explorer guidance.",
    mocked_test_command="uv run pytest tests/skills/test_plan1_correction.py::TestAgentProfiles::test_explorer_mocked",
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_AGENT_PROFILES: Dict[str, AgentProfile] = {
    "ecc:agent:e2e-runner": ECC_E2E_RUNNER_AGENT,
    "ecc:agent:docs-researcher": ECC_DOCS_RESEARCHER_AGENT,
    "ecc:agent:code-reviewer": ECC_CODE_REVIEWER_AGENT,
    "ecc:agent:security-reviewer": ECC_SECURITY_REVIEWER_AGENT,
    "ecc:agent:planner": ECC_PLANNER_AGENT,
    "ecc:agent:architect": ECC_ARCHITECT_AGENT,
    "ecc:agent:tdd-guide": ECC_TDD_GUIDE_AGENT,
    "ecc:agent:spec-miner": ECC_SPEC_MINER_AGENT,
    "ecc:agent:refactor-cleaner": ECC_REFACTOR_CLEANER_AGENT,
    "ecc:agent:doc-updater": ECC_DOC_UPDATER_AGENT,
    "ecc:agent:build-error-resolver": ECC_BUILD_ERROR_RESOLVER_AGENT,
    "ecc:agent:reviewer": ECC_REVIEWER_AGENT,
    "ecc:agent:explorer": ECC_EXPLORER_AGENT,
}

EXECUTION_AGENTS = ["ecc:agent:e2e-runner", "ecc:agent:docs-researcher"]
REVIEW_AGENTS = [k for k in ALL_AGENT_PROFILES if k not in EXECUTION_AGENTS]


def get_agent_profile(agent_id: str) -> Optional[AgentProfile]:
    return ALL_AGENT_PROFILES.get(agent_id)


__all__ = [
    "AgentProfile",
    "ALL_AGENT_PROFILES",
    "EXECUTION_AGENTS",
    "REVIEW_AGENTS",
    "AGENT_PLAN1_STATE_APPROVAL",
    "AGENT_ACTIVATION_ROUTE",
    "AGENT_ROLLBACK_PATH",
    "ECC_E2E_RUNNER_AGENT",
    "ECC_DOCS_RESEARCHER_AGENT",
    "ECC_CODE_REVIEWER_AGENT",
    "ECC_SECURITY_REVIEWER_AGENT",
    "ECC_PLANNER_AGENT",
    "ECC_ARCHITECT_AGENT",
    "ECC_TDD_GUIDE_AGENT",
    "ECC_SPEC_MINER_AGENT",
    "ECC_REFACTOR_CLEANER_AGENT",
    "ECC_DOC_UPDATER_AGENT",
    "ECC_BUILD_ERROR_RESOLVER_AGENT",
    "ECC_REVIEWER_AGENT",
    "ECC_EXPLORER_AGENT",
    "get_agent_profile",
]
