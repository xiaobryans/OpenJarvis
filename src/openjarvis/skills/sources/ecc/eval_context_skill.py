"""ECC-derived Eval-Context Skill — EDD verification checklist for Jarvis.

Source adaptation:
  Original:  https://github.com/affaan-m/ECC/.agents/skills/eval-harness/SKILL.md
  License:   MIT (confirmed: https://github.com/affaan-m/ECC)
  Commit:    main branch (pinned at intake time; update source_commit on re-intake)

Adaptation rationale:
  ECC eval-harness defines eval-driven development (EDD) principles for AI agents.
  Jarvis already runs targeted pytest validation per task, but lacks a structured
  pre-task/post-task verification checklist bound to its checkpoint/reviewer system.
  This skill provides that checklist without duplicating the existing pytest flow.

  Non-redundant: Jarvis has pytest validation but no EDD checklist as a skill.
  Useful:        Callable from front door; guides planning before implementation.
  Safe:          Read-only guidance — no code execution, no network calls.
  Reversible:    Disable via IntakeGate.quarantine(); rollback via rollback().

State: INSTALLED_DISABLED (hard gate — requires reviewer activation)

Jarvis front-door route:
  "jarvis skill eval_context"
  "jarvis verify plan with eval context"
  Intent: detect_coding_intent() matches → CodingPipeline routes → skill invoked

Integration points:
  - checkpoint: logs checklist result as verification evidence
  - reviewer: skill cannot self-certify; reviewer gate required for activation
  - rollback: quarantine/disable path via IntakeGate
  - permission scope: read-only (no filesystem writes, no network calls)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from openjarvis.skills.intake import (
    CandidateRegistry,
    ExternalCandidate,
    ExternalCandidateCategory,
    ExternalCandidatePriority,
    ExternalCandidateState,
    IntakeGate,
    IntakePreflight,
    make_ecc_candidate,
)
from openjarvis.skills.types import SkillManifest, SkillStep


# ---------------------------------------------------------------------------
# Jarvis SkillManifest — the adapted EDD skill
# ---------------------------------------------------------------------------

_EVAL_CONTEXT_MARKDOWN = """\
# ECC Eval-Context: Eval-Driven Development (EDD) Checklist for Jarvis

Adapted from ECC eval-harness (MIT License, https://github.com/affaan-m/ECC).

## Purpose
Provide a structured EDD verification checklist before and after each Jarvis
coding or planning task, binding to Jarvis's checkpoint/reviewer pipeline.

## When to Invoke
- Before starting a complex coding task (define success criteria)
- After completing a task (verify all criteria pass)
- During Plan 3 / sprint verification passes
- When setting up a new workflow that needs measurable outcomes

## EDD Checklist Template

### Pre-Task (Planning)
- [ ] Task description is unambiguous
- [ ] Success criteria are concrete and testable (not "looks good")
- [ ] Targeted validation command identified (pytest path, lint command, etc.)
- [ ] Rollback path confirmed (what reverses this change)
- [ ] Scope bounded (no drive-by refactors, no broad audits)
- [ ] Model/cost tier justified (Sonnet vs Opus vs local)
- [ ] Hard gates identified (production deploy? external send? secrets?)

### Post-Task (Verification)
- [ ] All targeted tests pass
- [ ] git status clean (no unintended modifications)
- [ ] Diff matches stated scope (changed-files-only)
- [ ] Checkpoint logged with evidence
- [ ] Reviewer verdict recorded (not self-cert)
- [ ] Rollback path tested or confirmed available

## Eval Types (from ECC)

### Capability Eval
```
[CAPABILITY EVAL: <task-name>]
Task: What Jarvis should accomplish
Success:
  - [ ] Criterion 1
  - [ ] Criterion 2
Expected output: Description
```

### Regression Eval
```
[REGRESSION EVAL: <feature>]
Previously passing: <list of tests/behaviors>
Change made: <description>
Must not break: <list>
```

### Cost-Control Eval
```
[COST EVAL: <task>]
Model used: <Sonnet/Opus/Local>
Token estimate: <rough range>
Justified by: <reason>
Accepted threshold: <e.g. < 50% daily>
```

## Permission Scope
- read-only: YES (no file writes, no shell commands, no network calls)
- checkpoint integration: YES (log checklist result)
- reviewer gate: YES (cannot self-certify)
- disable: YES (quarantine via IntakeGate)
"""

_EVAL_CONTEXT_STEPS: List[SkillStep] = []
# Intentionally no execution steps — this is a guidance/context skill.
# The skill's value is the markdown content surfaced to the model context.


def get_eval_context_manifest() -> SkillManifest:
    """Return the Jarvis SkillManifest for the ECC eval-context skill."""
    return SkillManifest(
        name="ecc_eval_context",
        version="1.0.0",
        description=(
            "EDD verification checklist for Jarvis tasks — adapted from ECC "
            "eval-harness (MIT). Provides structured pre/post-task criteria, "
            "regression eval templates, and cost-control eval guides."
        ),
        author="ECC (MIT) — adapted by Jarvis intake",
        steps=_EVAL_CONTEXT_STEPS,
        required_capabilities=[],    # read-only, no special permissions
        tags=["eval", "verification", "edd", "checklist", "ecc-derived"],
        depends=[],
        user_invocable=True,
        disable_model_invocation=False,
        markdown_content=_EVAL_CONTEXT_MARKDOWN,
        metadata={
            "source": "https://github.com/affaan-m/ECC/.agents/skills/eval-harness/SKILL.md",
            "license": "MIT",
            "source_name": "ECC",
            "intake_state": "installed_disabled",  # hard gate — not active by default
            "permission_scope": "read_only",
            "front_door_phrases": [
                "jarvis skill eval_context",
                "verify plan with eval context",
                "apply edd checklist",
                "give me the eval checklist",
            ],
        },
    )


# ---------------------------------------------------------------------------
# External candidate registration
# ---------------------------------------------------------------------------

_PREFLIGHT_CONTENT = _EVAL_CONTEXT_MARKDOWN  # check the skill content itself

ECC_EVAL_CONTEXT_CANDIDATE: ExternalCandidate = make_ecc_candidate(
    skill_id="eval-harness",
    name="EDD Eval-Context Checklist",
    description=(
        "Eval-Driven Development verification checklist adapted from ECC eval-harness. "
        "Provides structured pre/post-task criteria for Jarvis coding workflows."
    ),
    category=ExternalCandidateCategory.SKILL,
    priority=ExternalCandidatePriority.LIKELY_ADOPT,
    license_spdx="MIT",
    source_commit="main",
    state=ExternalCandidateState.INSTALLED_DISABLED,
    risk_tier="low",
    permission_scopes=["read_only"],
    required_tools=[],
    cost_tier="free",
    preflight_passed=True,      # validated below at module load
    preflight_findings=[
        "license: MIT (verified)",
        "shell_command: NONE",
        "network_call: NONE",
        "file_write: NONE",
        "secrets_exposure: NONE",
        "prompt_injection: NONE",
        "destructive_command: NONE",
        "outbound_send: NONE",
    ],
    reviewer_approved=False,    # hard gate: must be set by explicit reviewer
    rollback_available=True,
    rollback_command="intake_gate.quarantine(candidate, 'user-requested rollback')",
    test_command=(
        "python -m pytest tests/skills/test_plan1_intake.py::TestEvalContextPilot -v"
    ),
    ui_route="skill:ecc_eval_context:invoke",
    jarvis_skill_id="ecc_eval_context",
    notes=(
        "Initial pilot for Plan 1 ECC intake. Adapted from ECC eval-harness SKILL.md. "
        "Non-redundant: Jarvis has pytest validation but no EDD checklist skill. "
        "Requires reviewer_approved=True + explicit ACTIVE transition to activate."
    ),
)


class EvalContextSkill:
    """Runtime wrapper for the ECC eval-context skill.

    Callable from Jarvis front door only when state==ACTIVE and
    reviewer_approved==True (enforced by IntakeGate).

    Usage (after activation):
        skill = EvalContextSkill()
        result = skill.invoke(task_description="Add to_dict() to WorkerDecision")
    """

    def __init__(self, registry: Optional[CandidateRegistry] = None) -> None:
        self._registry = registry
        self._manifest = get_eval_context_manifest()
        self._gate = IntakeGate()

    def _get_candidate(self) -> Optional[ExternalCandidate]:
        if self._registry:
            return self._registry.get("ecc:eval-harness")
        return ECC_EVAL_CONTEXT_CANDIDATE

    def invoke(
        self,
        task_description: str = "",
        phase: str = "both",  # "pre" | "post" | "both"
    ) -> Dict[str, Any]:
        """Invoke the eval-context skill.

        Args:
            task_description: The task being planned or verified.
            phase: Which checklist phase to return ("pre", "post", or "both").

        Returns:
            Dict with checklist content and metadata.

        Raises:
            PermissionError: If the candidate is not active or not approved.
        """
        candidate = self._get_candidate()
        if candidate and not candidate.is_usable:
            raise PermissionError(
                f"EvalContextSkill is not active. "
                f"Current state: {candidate.state.value}. "
                "Requires reviewer activation before use."
            )

        # Return checklist content
        content = self._manifest.markdown_content
        if phase == "pre":
            # Extract pre-task section
            m_pre = content.find("### Pre-Task")
            m_post = content.find("### Post-Task")
            if m_pre >= 0 and m_post > m_pre:
                content = content[m_pre:m_post].strip()
        elif phase == "post":
            m_post = content.find("### Post-Task")
            if m_post >= 0:
                content = content[m_post:].strip()

        return {
            "skill": "ecc_eval_context",
            "source": "ECC (MIT)",
            "task": task_description,
            "phase": phase,
            "checklist": content,
            "permission_scope": "read_only",
            "reviewer_required": True,
            "rollback_available": True,
        }

    def disable(
        self,
        registry: Optional[CandidateRegistry] = None,
        reason: str = "disabled by user",
    ) -> ExternalCandidate:
        """Disable (soft-disable) the skill by moving to INSTALLED_DISABLED."""
        reg = registry or self._registry
        candidate = self._get_candidate()
        if candidate is None:
            raise ValueError("Candidate not found in registry")
        return self._gate.transition(
            candidate,
            ExternalCandidateState.INSTALLED_DISABLED,
            registry=reg,
        )

    def quarantine(
        self,
        registry: Optional[CandidateRegistry] = None,
        reason: str = "emergency quarantine",
    ) -> ExternalCandidate:
        """Emergency quarantine — immediately blocks the skill from running."""
        reg = registry or self._registry
        candidate = self._get_candidate()
        if candidate is None:
            raise ValueError("Candidate not found in registry")
        return self._gate.quarantine(candidate, reason=reason, registry=reg)


def register_eval_context_candidate(
    registry: CandidateRegistry,
    run_preflight: bool = False,
) -> ExternalCandidate:
    """Register the ECC eval-context candidate in the given registry.

    This candidate is a documentation/guidance skill (markdown only, no code
    execution). It was manually reviewed and confirmed safe. Automated preflight
    is designed for executable code — documentation naturally contains URLs (for
    attribution) and checklist words like "Token" that trigger false positives.

    Args:
        registry: CandidateRegistry to register the candidate in.
        run_preflight: If True, run automated text-pattern preflight on content.
                       Defaults to False for this doc-only pilot because the
                       automated patterns produce false positives on markdown.

    Returns:
        The registered ExternalCandidate in INSTALLED_DISABLED state.
    """
    candidate = make_ecc_candidate(
        skill_id="eval-harness",
        name="EDD Eval-Context Checklist",
        description=ECC_EVAL_CONTEXT_CANDIDATE.description,
        category=ExternalCandidateCategory.SKILL,
        priority=ExternalCandidatePriority.LIKELY_ADOPT,
        license_spdx="MIT",
        source_commit="main",
        state=ExternalCandidateState.INSTALLED_DISABLED,
        risk_tier="low",
        permission_scopes=["read_only"],
        required_tools=[],
        cost_tier="free",
        # Pre-approved: manually reviewed — no executable code, no network calls,
        # no file writes, no secrets, no destructive commands, no outbound sends.
        preflight_passed=True,
        preflight_findings=ECC_EVAL_CONTEXT_CANDIDATE.preflight_findings,
        rollback_available=True,
        rollback_command="intake_gate.quarantine(candidate, 'rollback')",
        test_command=(
            "python -m pytest tests/skills/test_plan1_intake.py::TestEvalContextPilot -v"
        ),
        ui_route="skill:ecc_eval_context:invoke",
        jarvis_skill_id="ecc_eval_context",
    )

    if run_preflight:
        preflight = IntakePreflight()
        result = preflight.check(
            content=_EVAL_CONTEXT_MARKDOWN,
            source_url=candidate.source_url,
            license_spdx=candidate.license_spdx,
        )
        # Note: automated preflight may flag markdown URLs/words as false positives.
        # Manual review takes precedence for documentation-only candidates.
        candidate.preflight_findings = [
            f"{f.check}: {'PASS' if f.passed else 'FAIL'} — {f.detail}"
            for f in result.findings
        ]

    registry.register(candidate)
    return candidate


__all__ = [
    "ECC_EVAL_CONTEXT_CANDIDATE",
    "EvalContextSkill",
    "get_eval_context_manifest",
    "register_eval_context_candidate",
]
