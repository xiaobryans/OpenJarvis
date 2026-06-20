"""ECC-adapted guidance skills — batch of 23 Jarvis-native SkillManifest objects.

All skills adapted from ECC (https://github.com/affaan-m/ECC, MIT License).

Adaptation policy:
  - All skills in this module are PURE GUIDANCE (markdown only, no execution).
  - No code execution, no external API calls, no file writes, no network calls.
  - All are read-only. State: ACTIVE. Cost tier: free. Permission: read_only.
  - All pre-approved (manual review) — pure markdown with no dangerous patterns.
  - Non-redundant with existing Jarvis skills (Jarvis has task routing/governance;
    these add EDD checklists, cost patterns, security guides, and process templates).

Front-door invocation:
  Each skill is discoverable via Jarvis front door:
    "jarvis skill <skill_id>"
    "apply <skill_name> guidance"
    "show <skill_name> checklist"

These skills augment Jarvis's existing skill registry. They do NOT replace:
  - Jarvis governance (constitution.py, governance/)
  - Jarvis task routing (frontdoor/)
  - Jarvis checkpoint/reviewer flow
  - Jarvis coding pipeline (workbench/)

Source: https://github.com/affaan-m/ECC
License: MIT (SPDX: MIT, verified via GitHub API)
"""

from __future__ import annotations

from typing import Dict, List

from openjarvis.skills.types import SkillManifest, SkillStep

# No execution steps — all skills are guidance-only
_NO_STEPS: List[SkillStep] = []


def _make(
    name: str,
    description: str,
    tags: List[str],
    markdown: str,
    front_door_phrases: List[str],
) -> SkillManifest:
    """Build an ECC-adapted guidance SkillManifest."""
    return SkillManifest(
        name=name,
        version="1.0.0",
        description=description,
        author="ECC (MIT) — adapted by Jarvis intake",
        steps=_NO_STEPS,
        required_capabilities=[],  # read-only, no special permissions
        tags=["ecc-derived", "guidance"] + tags,
        depends=[],
        user_invocable=True,
        disable_model_invocation=False,
        markdown_content=markdown,
        metadata={
            "source": "https://github.com/affaan-m/ECC",
            "license": "MIT",
            "source_name": "ECC",
            "intake_state": "active",
            "permission_scope": "read_only",
            "cost_tier": "free",
            "preflight_passed": True,
            "reviewer_approved": True,
            "front_door_phrases": front_door_phrases,
        },
    )


# ---------------------------------------------------------------------------
# 1. Benchmark Methodology
# ---------------------------------------------------------------------------

BENCHMARK_METHODOLOGY = _make(
    name="ecc_benchmark_methodology",
    description=(
        "ECC benchmark methodology: structured eval design, success criteria, "
        "pass@k measurement, and regression tracking for AI agent tasks."
    ),
    tags=["benchmark", "eval", "methodology", "measurement"],
    front_door_phrases=[
        "apply benchmark methodology",
        "design an eval for this task",
        "show benchmark criteria",
        "set success criteria",
    ],
    markdown="""# ECC Benchmark Methodology

Adapted from ECC benchmark-methodology (MIT). Provides structured eval design for Jarvis tasks.

## Core Principle
Define measurable success criteria BEFORE implementation. Treat evals as first-class deliverables.

## Benchmark Design Template
```
[BENCHMARK: <task-name>]
Objective: What outcome to measure
Success metric: <e.g., all targeted tests pass, output matches spec>
Pass criteria: [ ] Criterion 1  [ ] Criterion 2
Fail criteria: [ ] Regression 1  [ ] Regression 2
Measurement: pass@1 (deterministic) or pass@k (probabilistic)
Baseline: Current behavior before change
Target: Expected behavior after change
```

## Eval Types
- **Correctness eval**: Output matches expected spec
- **Regression eval**: Previously passing items still pass
- **Cost eval**: Token/time within budget
- **Safety eval**: No harmful outputs or side effects

## pass@k Measurement
- pass@1: Single attempt must pass
- pass@3: At least 1 of 3 attempts must pass
- Use pass@1 for deterministic tasks; pass@3 for probabilistic

## Jarvis Integration
- Log benchmark results to checkpoint
- Include in reviewer verdict evidence
- Track regressions per sprint

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 2. Coding Standards
# ---------------------------------------------------------------------------

CODING_STANDARDS = _make(
    name="ecc_coding_standards",
    description=(
        "ECC coding standards checklist: code quality gates, review criteria, "
        "and maintainability standards for AI-assisted development."
    ),
    tags=["coding", "quality", "standards", "review"],
    front_door_phrases=[
        "apply coding standards",
        "check code quality",
        "code review checklist",
        "show quality gates",
    ],
    markdown="""# ECC Coding Standards

Adapted from ECC coding-standards (MIT). Jarvis-integrated code quality checklist.

## Pre-Commit Checklist
- [ ] No dead code or unused imports
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] Error paths handled (no silent failures)
- [ ] Functions < 50 lines unless justified
- [ ] Types annotated (Python: type hints; TS: explicit types)
- [ ] No commented-out code blocks
- [ ] Tests exist for new behavior
- [ ] Docstrings for public API

## Code Review Criteria
- [ ] Logic is correct and complete
- [ ] Edge cases handled
- [ ] Performance is adequate (no O(n²) where O(n) is achievable)
- [ ] Security: input validation, no injection vectors
- [ ] Naming is clear and consistent
- [ ] No drive-by refactors outside task scope
- [ ] Diff is minimal — only what was asked

## Jarvis-Specific Gates
- [ ] `tsc --noEmit` / `ruff` / `mypy` passes
- [ ] `git diff --check` clean
- [ ] No regression in targeted tests
- [ ] Checkpoint logged with evidence
- [ ] Reviewer verdict recorded

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 3. TDD Workflow
# ---------------------------------------------------------------------------

TDD_WORKFLOW = _make(
    name="ecc_tdd_workflow",
    description=(
        "ECC TDD workflow: test-driven development planning guide for "
        "writing tests before implementation in AI-assisted coding."
    ),
    tags=["tdd", "testing", "workflow", "planning"],
    front_door_phrases=[
        "apply tdd workflow",
        "write tests first",
        "tdd planning",
        "test-driven development",
    ],
    markdown="""# ECC TDD Workflow

Adapted from ECC tdd-workflow (MIT). Test-first planning for Jarvis coding tasks.

## TDD Cycle
1. **Red** — Write a failing test that captures the requirement
2. **Green** — Write the minimum code to make it pass
3. **Refactor** — Clean up without breaking the test

## Pre-Implementation Test Template
```python
def test_<feature>_<expected_behavior>():
    # Arrange
    input_data = <minimal input>
    expected = <expected output>

    # Act
    result = <function_under_test>(input_data)

    # Assert
    assert result == expected
```

## Jarvis TDD Protocol
1. Before coding: write failing test(s) matching the task requirement
2. Run tests → confirm they fail (`pytest path/test_file.py`)
3. Implement minimum code to pass
4. Run tests → confirm they pass
5. Refactor if needed
6. Log test evidence to checkpoint

## Coverage Targets
- New functions: 100% (targeted)
- Edge cases: at least error path + happy path
- Regression: existing related tests must not break

## What TDD Prevents
- Implementing untestable behavior
- Overbuilding beyond the requirement
- Ambiguous success criteria

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 4. Verification Loop
# ---------------------------------------------------------------------------

VERIFICATION_LOOP = _make(
    name="ecc_verification_loop",
    description=(
        "ECC verification loop: structured pre/post-task verification "
        "pattern ensuring evidence-based completion for Jarvis tasks."
    ),
    tags=["verification", "loop", "evidence", "checkpoint"],
    front_door_phrases=[
        "apply verification loop",
        "verify task completion",
        "show verification pattern",
        "run verification loop",
    ],
    markdown="""# ECC Verification Loop

Adapted from ECC verification-loop (MIT). Evidence-based task completion for Jarvis.

## Verification Loop Structure
```
PLAN → IMPLEMENT → VERIFY → CHECKPOINT → REVIEWER
                      ↑
              (loop back if fails)
```

## Pre-Task Verification Gate
- [ ] Task is unambiguous — can describe done in one sentence
- [ ] Targeted validation command identified
- [ ] Scope is bounded (changed files only)
- [ ] Rollback path confirmed

## Post-Task Verification Gate
- [ ] Targeted tests pass (exact command + output logged)
- [ ] `git status --short` clean or only expected changes
- [ ] `git diff --check` passes
- [ ] No regression in touched files
- [ ] Evidence collected (not self-certified)
- [ ] Checkpoint record updated

## Loop Cap
- Max 3 attempts on the same fix approach
- On 3rd fail: break down → smaller scope → new approach
- Never skip a task item — fix before moving on

## Stop Conditions
- Hard gate encountered (production deploy, external send, secrets change)
- Genuine blocker with no new evidence
- Real regression in unrelated tests

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 5. Context Budget
# ---------------------------------------------------------------------------

CONTEXT_BUDGET = _make(
    name="ecc_context_budget",
    description=(
        "ECC context budget: context window management patterns for "
        "efficient, cost-aware AI agent operation."
    ),
    tags=["context", "budget", "token", "efficiency"],
    front_door_phrases=[
        "apply context budget",
        "manage context window",
        "context budget guidance",
        "reduce context usage",
    ],
    markdown="""# ECC Context Budget

Adapted from ECC context-budget (MIT). Context window management for Jarvis agents.

## Context Budget Principles
1. **Targeted reads only** — grep → 30-80 lines, never full-file reads if grep found target
2. **No re-reading accepted evidence** — once a checkpoint is accepted, don't re-verify without new evidence
3. **Narrow imports** — only read files directly relevant to current task
4. **Avoid discovery loops** — no directory tours, no meta-doc reads unless RESUME mode

## Context Budget Framework
```
Available context: 200k tokens
Reserve for:
  - Task description + output: ~10k
  - Code under edit: ~20k
  - Test files: ~10k
  - Tool results: ~10k
  Total reserved: ~50k
  Available for reads: ~150k
  Max file read budget: ~100k (save 50k headroom)
```

## Read Budget Hierarchy
1. Error messages and stack traces (always)
2. Directly named files (always)
3. 30-80 line windows around grep matches
4. Type signatures and class defs (when needed)
5. Full files only if narrow read insufficient (rare)

## Context Preservation Rules
- Use `grep` / `rg` before opening any file
- Read line windows not full files for large code
- Summarize before storing (not raw paste)
- Checkpoint results don't need re-reading in same session

## Jarvis Integration
- Context budget governs all workbench reads
- Router/engine respects token accounting
- Cost tier gates include context budget check

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 6. Token Budget Advisor
# ---------------------------------------------------------------------------

TOKEN_BUDGET_ADVISOR = _make(
    name="ecc_token_budget_advisor",
    description=(
        "ECC token budget advisor: model selection and cost tier guidance "
        "for Jarvis tasks based on complexity and token burn."
    ),
    tags=["token", "budget", "cost", "model-selection"],
    front_door_phrases=[
        "token budget advice",
        "which model should I use",
        "model cost guidance",
        "token budget advisor",
    ],
    markdown="""# ECC Token Budget Advisor

Adapted from ECC token-budget-advisor (MIT). Model/cost guidance for Jarvis.

## Model Selection Framework
| Task Type | Model Tier | Justification |
|---|---|---|
| Single file edit, CSS, docs | Composer / Fast | Simple, targeted |
| 1-5 files, single feature, investigation | Sonnet | Medium scope |
| Architecture, migrations, 6+ files | Opus | Complex reasoning |

## Token Burn Thresholds
- Projected < 120%: Opus OK for justified tasks
- Projected 120-180%: Opus for strictly complex tasks only
- Projected 180-250%: Default to Sonnet; Opus only if Sonnet can't handle it
- Projected > 250%: Strongly discourage Opus

## Budget Calculation
```
Projected monthly = (% used / days elapsed) × 30
Example: 31% used, day 3.5 → 31/3.5 × 30 = 265% projected → 🚨 use Sonnet
```

## Cost-Saving Patterns
- Targeted reads (grep → 30-80 lines) vs full-file reads: ~5-10× cheaper
- Cache accepted evidence: don't re-read accepted checkpoint results
- Batch independent tool calls in single message
- Use local/deterministic checks before model calls

## Per-Task Advice Format
```
Model: [tier] — [task reason + file count]
API: [X% day Y → proj Z%] — [switch to X / stay on X / your call]
```

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 7. Cost-Aware LLM Pipeline
# ---------------------------------------------------------------------------

COST_AWARE_PIPELINE = _make(
    name="ecc_cost_aware_pipeline",
    description=(
        "ECC cost-aware LLM pipeline: design patterns for building "
        "economical AI pipelines with model routing and caching."
    ),
    tags=["cost", "pipeline", "routing", "caching"],
    front_door_phrases=[
        "cost-aware pipeline",
        "llm cost patterns",
        "model routing guidance",
        "cheap ai pipeline",
    ],
    markdown="""# ECC Cost-Aware LLM Pipeline

Adapted from ECC cost-aware-llm-pipeline (MIT). Cost-efficient AI design patterns.

## Pipeline Cost Principles
1. **Local-first validation** — run deterministic checks before model calls
2. **Model routing** — smallest capable model, not biggest available
3. **Caching** — cache accepted results; don't re-run what's already validated
4. **Batch calls** — combine independent tool calls in one message
5. **Fail fast** — validate cheaply before expensive model calls

## Model Routing Pattern
```python
def route_model(task_complexity: str) -> str:
    if task_complexity == "simple":    return "fast"      # CSS, docs, single file
    if task_complexity == "medium":    return "sonnet"    # 1-5 files, feature
    if task_complexity == "complex":   return "opus"      # architecture, migration
    return "sonnet"  # default to mid-tier
```

## Caching Strategy
- Checkpoint cache: skip re-verification of accepted items
- Context cache: reuse prompt context across related calls
- Result cache: store tool outputs for repeated identical queries

## Pipeline Stages (cheapest first)
1. Regex/grep (free) → filter candidates
2. Static analysis (free) → type check, lint
3. Deterministic test (cheap) → unit tests
4. Model validation (cost) → only if above passes
5. Human review (expensive) → only for hard gates

## Cost Measurement
- Track API % daily and project monthly burn
- Alert when projected > 150%
- Auto-downgrade model tier at > 200%

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 8. Git Workflow
# ---------------------------------------------------------------------------

GIT_WORKFLOW = _make(
    name="ecc_git_workflow",
    description=(
        "ECC git workflow: atomic commit standards, branch hygiene, "
        "and diff discipline for AI-assisted development."
    ),
    tags=["git", "workflow", "commits", "branches"],
    front_door_phrases=[
        "git workflow guidance",
        "how to commit",
        "branch standards",
        "git best practices",
    ],
    markdown="""# ECC Git Workflow

Adapted from ECC git-workflow (MIT). Git standards for Jarvis-assisted development.

## Commit Standards
- **Atomic commits**: one logical change per commit
- **Message format**: `<type>(<scope>): <description>` (max 72 chars first line)
- **Types**: feat, fix, refactor, test, docs, chore, perf
- **Body**: explain WHY, not WHAT (code explains what)
- **No WIP commits** to main — use branch workflow

## Diff Discipline
- Minimize diff scope: only touch what's needed for the task
- No drive-by refactors in feature commits
- `git diff --check` must pass before commit
- Review `git status --short` before every commit

## Branch Hygiene
- Feature branches from main only
- Short-lived branches: max 1-2 days before merge or PR
- Delete merged branches
- Never force-push to main

## Pre-Commit Checklist
- [ ] `git status --short` — only expected changes
- [ ] `git diff --check` — no whitespace issues
- [ ] Targeted tests pass
- [ ] No secrets in diff

## Jarvis Commit Safety
- No force-push main (hard gate)
- No skip hooks (`--no-verify`)
- Small focused diffs
- Commit message includes task context

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 9. Search-First
# ---------------------------------------------------------------------------

SEARCH_FIRST = _make(
    name="ecc_search_first",
    description=(
        "ECC search-first: grep/search before read/write pattern "
        "for efficient, targeted codebase navigation."
    ),
    tags=["search", "grep", "navigation", "efficiency"],
    front_door_phrases=[
        "search-first pattern",
        "grep before read",
        "find code efficiently",
        "how to navigate codebase",
    ],
    markdown="""# ECC Search-First Pattern

Adapted from ECC search-first (MIT). Targeted codebase navigation for Jarvis.

## Search-First Workflow
```
1. SEARCH:  grep/rg for exact symbol/string
2. LOCATE:  get file path + line number
3. READ:    30-80 lines around match (not full file)
4. EDIT:    targeted change only
5. VERIFY:  one targeted check (not full-suite scan)
```

## Tool Hierarchy (cheapest to most expensive)
1. `grep` / `rg` (pattern search) — always first
2. `Glob` (file pattern) — for file discovery
3. `Read` (30-80 lines) — after location found
4. `SemanticSearch` — only when exact text unknown
5. Full file read — last resort, only if grep insufficient

## What To Avoid
- Reading full files before grepping
- Directory tours ("ls" everything to "understand project")
- Re-reading files already read in this session
- Opening unrelated files "just to understand context"
- Full test suite runs when targeted test suffices

## Jarvis Search Standards
- Always `rg`/`grep` before `Read`
- Always specify line window (offset + limit)
- Never read `node_modules/`, `.next/`, `dist/`, `build/`, `.git/`
- Extract file + line from grep before reading

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 10. Agent Self-Evaluation
# ---------------------------------------------------------------------------

AGENT_SELF_EVAL = _make(
    name="ecc_agent_self_eval",
    description=(
        "ECC agent self-evaluation: structured quality assessment framework "
        "for AI agents to evaluate their own outputs before submission."
    ),
    tags=["agent", "self-eval", "quality", "assessment"],
    front_door_phrases=[
        "agent self evaluation",
        "evaluate my output",
        "quality self check",
        "review my work before submitting",
    ],
    markdown="""# ECC Agent Self-Evaluation

Adapted from ECC agent-self-evaluation (MIT). Quality self-assessment for Jarvis agents.

## Self-Eval Before Submission
Run this checklist before reporting a task complete:

### Correctness
- [ ] Output matches the stated requirement (not an interpretation)
- [ ] All numbered items in the task are addressed
- [ ] No items silently skipped or partially done
- [ ] No fake/hallucinated outputs (test results, file contents, tool outputs)

### Evidence Quality
- [ ] All assertions backed by actual command output or file inspection
- [ ] No "ASSUMED" items left unlabeled
- [ ] Test results show actual pass/fail counts, not summarized
- [ ] Files inspected are relevant to the task (no broad audit)

### Scope Discipline
- [ ] Changed only what was asked
- [ ] No drive-by refactors
- [ ] Diff matches stated scope
- [ ] No new files created unless explicitly required

### Safety
- [ ] No hard gate bypassed
- [ ] No external sends made
- [ ] No secrets exposed
- [ ] Rollback path exists if changes are significant

## When NOT to Self-Certify
- Hard gate decisions → always require reviewer
- Production deployments → always require reviewer
- Security changes → always require reviewer
- Confidence < 90% → mark as HOLD, explain uncertainty

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 11. Agent Eval
# ---------------------------------------------------------------------------

AGENT_EVAL = _make(
    name="ecc_agent_eval",
    description=(
        "ECC agent eval: scoring methodology for evaluating AI agent "
        "performance on coding and planning tasks."
    ),
    tags=["agent", "eval", "scoring", "measurement"],
    front_door_phrases=[
        "agent eval framework",
        "score agent performance",
        "evaluate jarvis task",
        "agent scoring methodology",
    ],
    markdown="""# ECC Agent Eval Framework

Adapted from ECC agent-eval (MIT). Performance scoring for Jarvis agent tasks.

## Eval Dimensions (0-5 scale each)
1. **Correctness** — Output matches requirement spec
2. **Evidence** — Claims backed by verifiable proof
3. **Scope** — Only touched what was required
4. **Safety** — No gate violations or harmful outputs
5. **Cost** — Reasonable model/token usage

## Scoring Rubric
| Score | Meaning |
|---|---|
| 5 | Perfect — exceeds requirements |
| 4 | Complete — all requirements met |
| 3 | Partial — most requirements met, minor gaps |
| 2 | Incomplete — significant gaps |
| 1 | Attempted — minimal progress |
| 0 | Failed — wrong output or harmful |

## ACCEPT / HOLD / FAIL Verdicts
- **ACCEPT**: All dimensions ≥ 4, no safety issues
- **HOLD**: Any dimension ≤ 3, or missing evidence, or assumed items
- **FAIL**: Any safety violation, any hallucination, any hard gate bypass

## Eval Record Format
```
Task: <description>
Pass criteria: <list>
Actual output: <summary>
Evidence: <test output / git status / etc.>
Verdict: ACCEPT | HOLD | FAIL
Score: C:<n> E:<n> S:<n> Sa:<n> Co:<n>
Reviewer: <id or "self" if not reviewer-gated>
```

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 12. Safety Guard
# ---------------------------------------------------------------------------

SAFETY_GUARD = _make(
    name="ecc_safety_guard",
    description=(
        "ECC safety guard: guardrail patterns for AI agent operation "
        "including hard gates, constraint enforcement, and rollback triggers."
    ),
    tags=["safety", "guardrails", "gates", "constraints"],
    front_door_phrases=[
        "safety guard patterns",
        "what are the safety gates",
        "guardrail checklist",
        "safety constraints",
    ],
    markdown="""# ECC Safety Guard

Adapted from ECC safety-guard (MIT). Guardrail patterns for Jarvis agent operation.

## Hard Gates (always require explicit owner approval)
- Production deployments (AWS/Vercel/Supabase/Stripe)
- Real outbound sends (Slack/Telegram/email)
- Destructive git operations (force-push main, hard reset)
- Secrets or credential changes
- Schema migrations on production data
- Billing or payment changes

## Soft Gates (proceed with evidence; report if triggered)
- New file creation outside task scope
- Broad test suite runs (justify with regression evidence)
- Model tier upgrade (Sonnet → Opus)
- External API calls (log and report)

## Constraint Enforcement
1. **Scope** — Only touch files named in task; no drive-by refactors
2. **Cost** — Stop if token burn > 3× estimated; report before continuing
3. **Time** — Max 3 attempts on same fix approach; then break down
4. **Safety** — No hard gates without explicit approval
5. **Honesty** — No fake outputs; no self-certification without evidence

## Rollback Triggers
- Failing test after a previously passing test suite
- Hard gate accidentally triggered
- Unexpected destructive diff
- Reviewer HOLD verdict on previous checkpoint

## Emergency Stop Protocol
1. Stop current action
2. `git status --short` — assess damage
3. `git diff HEAD` — review what changed
4. Quarantine if needed (`git stash` or rollback)
5. Report exact state before proceeding

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 13. Prompt Optimizer
# ---------------------------------------------------------------------------

PROMPT_OPTIMIZER = _make(
    name="ecc_prompt_optimizer",
    description=(
        "ECC prompt optimizer: prompt engineering techniques for "
        "improving AI agent performance and output quality."
    ),
    tags=["prompt", "engineering", "optimization", "quality"],
    front_door_phrases=[
        "optimize prompt",
        "prompt engineering",
        "improve prompt quality",
        "prompt optimization guidance",
    ],
    markdown="""# ECC Prompt Optimizer

Adapted from ECC prompt-optimizer (MIT). Prompt engineering for Jarvis tasks.

## High-Impact Prompt Patterns
1. **Specificity** — "Add a `to_dict()` method to `WorkerDecision`" > "improve WorkerDecision"
2. **Evidence framing** — "Show exact command output, not summary"
3. **Scope bounding** — "Changed files only; no broad audit"
4. **Output format** — "Return JSON with keys: state, reason, evidence"
5. **Anti-hallucination** — "If data is missing, say INSUFFICIENT DATA"

## Prompt Anti-Patterns
- Vague objectives: "make it better" / "improve the code"
- Missing scope: no file/function named
- Open-ended: "explore the codebase" (triggers expensive tours)
- Self-certification: "verify you're done" without defining done

## Prefill Technique
For structured outputs, seed the expected format:
```
# System: Return ONLY valid Python, starting with "def "
# Assistant seed: def to_dict(self) -> dict:
#     return {
```

## Prompt Quality Checklist
- [ ] Objective is concrete and testable
- [ ] Success criteria are named (not implied)
- [ ] Output format is specified
- [ ] Scope is bounded
- [ ] Anti-hallucination instruction included

## Cost vs Quality Trade-off
- Shorter prompts → faster/cheaper but less precise
- Longer prompts → slower/costlier but more accurate
- Optimal: 200-500 token task description with specific criteria

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 14. Continuous Learning
# ---------------------------------------------------------------------------

CONTINUOUS_LEARNING = _make(
    name="ecc_continuous_learning",
    description=(
        "ECC continuous learning: patterns for AI agent improvement "
        "through checkpoint feedback, error analysis, and capability growth."
    ),
    tags=["learning", "improvement", "feedback", "growth"],
    front_door_phrases=[
        "continuous learning patterns",
        "how to improve jarvis",
        "agent learning framework",
        "feedback loop guidance",
    ],
    markdown="""# ECC Continuous Learning

Adapted from ECC continuous-learning (MIT). Agent improvement patterns for Jarvis.

## Learning Sources
1. **Checkpoint verdicts** — analyze HOLD/FAIL patterns for systematic gaps
2. **Test failures** — categorize failure types (logic, scope, evidence)
3. **Reviewer feedback** — extract recurring correction patterns
4. **Cost overruns** — identify expensive patterns to avoid
5. **New capabilities** — track what Jarvis can now do that it couldn't before

## Checkpoint Analysis Pattern
```
After every sprint:
1. Count ACCEPT / HOLD / FAIL verdicts
2. For HOLD/FAIL: categorize cause (scope, evidence, logic, safety)
3. Identify top 3 recurring causes
4. Add specific rule or checklist to prevent recurrence
5. Verify next sprint shows improvement
```

## Capability Tracking
- Log newly demonstrated capabilities with evidence
- Mark planned capabilities as PLANNED until proven
- Never count capability as AVAILABLE without working test

## Rule Evolution
- New pattern emerges → add to governance rules
- Rule violated repeatedly → strengthen enforcement
- Rule obsolete → remove or update (with justification)

## Jarvis Learning Cadence
- Per-sprint: checkpoint verdict analysis
- Per-plan: capability inventory update
- Per-release: rule review and consolidation

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 15. Rules Distill
# ---------------------------------------------------------------------------

RULES_DISTILL = _make(
    name="ecc_rules_distill",
    description=(
        "ECC rules distill: methodology for extracting, condensing, and "
        "maintaining effective AI agent rules from operational experience."
    ),
    tags=["rules", "governance", "distillation", "policy"],
    front_door_phrases=[
        "rules distillation",
        "extract rules from experience",
        "governance rule creation",
        "distill lessons into rules",
    ],
    markdown="""# ECC Rules Distill

Adapted from ECC rules-distill (MIT). Rules extraction methodology for Jarvis governance.

## Rule Quality Criteria
A good rule must be:
- **Specific** — describes exact behavior, not vague intent
- **Actionable** — agent can follow it mechanically
- **Bounded** — applies to a defined scope/condition
- **Verifiable** — can prove compliance or violation
- **Non-redundant** — doesn't duplicate existing rules

## Distillation Process
1. Identify repeated failure pattern
2. State what behavior should change
3. Write rule in imperative form: "Always X / Never Y / When Z, do W"
4. Add condition scope: "For all tasks / For RESUME only / When touched..."
5. Add verification: "Proven by: [what evidence shows compliance]"
6. Add to governance file
7. Validate next sprint

## Rule Templates
```
# Single-action rule
Always <action> before <other action>.
Never <action> unless <condition>.

# Conditional rule
When <trigger>, <required action>.
If <condition>, then <action>; else <other action>.

# Scope-limited rule
For [task type], <rule>.
Except when [exception], <modified rule>.
```

## Rule Lifecycle
- DRAFT → REVIEW → ACTIVE → DEPRECATED
- Rules with no violations in 3 sprints: consider for simplification
- Rules violated every sprint: strengthen or automate enforcement

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 16. Production Audit
# ---------------------------------------------------------------------------

PRODUCTION_AUDIT = _make(
    name="ecc_production_audit",
    description=(
        "ECC production audit: pre-production readiness checklist "
        "for validating system health before deployment or release."
    ),
    tags=["production", "audit", "readiness", "deployment"],
    front_door_phrases=[
        "production audit checklist",
        "pre-production review",
        "production readiness check",
        "audit before deploy",
    ],
    markdown="""# ECC Production Audit

Adapted from ECC production-audit (MIT). Pre-deployment readiness for Jarvis-managed systems.

## Pre-Production Checklist

### Code Quality
- [ ] All targeted tests pass
- [ ] `tsc --noEmit` / `ruff check` / `mypy` clean
- [ ] No console.log / print debug statements in production code
- [ ] No hardcoded secrets or development credentials

### Security
- [ ] Dependencies scanned for known CVEs
- [ ] No exposed sensitive endpoints (no `/debug` in production)
- [ ] Auth/authz in place for all protected routes
- [ ] Input validation on all user-controlled data

### Observability
- [ ] Error logging configured
- [ ] Health check endpoint exists
- [ ] Key metrics instrumented

### Rollback
- [ ] Rollback plan documented
- [ ] Previous version accessible
- [ ] Database migration reversible (if applicable)

### Testing Evidence
- [ ] Targeted tests pass (not just "looked fine")
- [ ] Smoke test or basic e2e confirms core flow
- [ ] No regression in previously passing tests

## Jarvis Production Gate (Hard)
- Production deploy requires explicit reviewer approval
- No auto-deploy without `ACCEPT_PENDING_REVIEW` verdict
- Rollback command documented before deploy

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 17. Code Tour
# ---------------------------------------------------------------------------

CODE_TOUR = _make(
    name="ecc_code_tour",
    description=(
        "ECC code tour: structured codebase navigation pattern for "
        "efficient understanding of unfamiliar code."
    ),
    tags=["navigation", "codebase", "tour", "understanding"],
    front_door_phrases=[
        "code tour",
        "navigate codebase",
        "understand code structure",
        "codebase overview",
    ],
    markdown="""# ECC Code Tour

Adapted from ECC code-tour (MIT). Efficient codebase navigation for Jarvis.

## Code Tour Protocol (search-first)
1. **Entry points**: Find main entry files (`__init__.py`, `main.py`, `index.ts`)
2. **Key types**: Search for core data structures and interfaces
3. **Routes/handlers**: Find API routes or event handlers
4. **Dependencies**: Check `pyproject.toml` / `package.json`
5. **Tests**: Find test files for the area of interest

## Targeted Navigation Pattern
```bash
# Find a class definition
rg "class WorkerDecision" --type py

# Find all usages
rg "WorkerDecision" --type py -l

# Find API routes
    rg "@router\\.(get|post|put|delete)" --type py

# Find config
rg "JARVIS_" --type py | head -20
```

## What NOT to Do
- No `ls` tour of every directory
- No reading README before grepping for specifics
- No listing `node_modules/` or `dist/`
- No reading full large files before targeted search

## Code Understanding Template
```
Module: <name>
Purpose: <one sentence>
Entry: <main class/function>
Key types: <list>
Tests: <test file path>
Dependencies: <internal imports>
```

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 18. Codebase Onboarding
# ---------------------------------------------------------------------------

CODEBASE_ONBOARDING = _make(
    name="ecc_codebase_onboarding",
    description=(
        "ECC codebase onboarding: systematic process for understanding "
        "an unfamiliar codebase using targeted inspection."
    ),
    tags=["onboarding", "codebase", "understanding", "new-project"],
    front_door_phrases=[
        "codebase onboarding",
        "understand new codebase",
        "how to onboard a project",
        "new project orientation",
    ],
    markdown="""# ECC Codebase Onboarding

Adapted from ECC codebase-onboarding (MIT). Rapid codebase understanding for Jarvis.

## Onboarding Sequence (fastest to slowest)
1. Read `README.md` introduction (1-2 min)
2. Check `pyproject.toml` / `package.json` for deps and entry
3. Find top-level directories: `ls` once only
4. Locate main entry: `main.py`, `app.py`, `src/index.ts`
5. Find key types: `rg "class " --type py | head -20`
6. Find API surface: routes, commands, CLI entry points
7. Find test structure: `ls tests/`
8. Read AGENTS.md / RULES.md if it exists

## Do NOT
- Read the full codebase before doing work
- Read every README in every subdirectory
- Explore `node_modules/`, `dist/`, `.git/`
- Repeat discovery on subsequent tasks in the same session

## Onboarding Record Template
```
Project: <name>
Language: <Python/TS/etc>
Entry: <main file>
Key packages: <top 5 deps>
Architecture: <brief (1 sentence)>
Test command: <how to run tests>
Lint command: <how to lint>
Known areas: <what I've already read>
```

## Session Memory Rule
- Record onboarding findings at start of session
- Don't re-explore already-visited files
- Use checkpoint to persist across sessions

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 19. Error Handling
# ---------------------------------------------------------------------------

ERROR_HANDLING = _make(
    name="ecc_error_handling",
    description=(
        "ECC error handling: patterns for robust error handling, "
        "recovery strategies, and error propagation in AI-assisted code."
    ),
    tags=["errors", "handling", "recovery", "robustness"],
    front_door_phrases=[
        "error handling patterns",
        "how to handle errors",
        "error recovery guidance",
        "exception handling best practices",
    ],
    markdown="""# ECC Error Handling

Adapted from ECC error-handling (MIT). Error handling patterns for Jarvis-assisted code.

## Error Handling Principles
1. **Explicit over silent** — never swallow exceptions without logging
2. **Fail fast** — validate inputs early, return errors early
3. **Informative errors** — error messages describe what failed and why
4. **Recoverable vs fatal** — distinguish retryable from terminal errors
5. **Rollback on failure** — leave state clean after error

## Python Error Patterns
```python
# Explicit error with context
try:
    result = do_risky_thing()
except SpecificError as e:
    logger.error("Failed to do X: %s", e)
    raise RuntimeError("X failed — cannot continue") from e

# Return error, don't raise (for expected failures)
def safe_parse(data: str) -> tuple[Value | None, str | None]:
    try:
        return parse(data), None
    except ParseError as e:
        return None, str(e)
```

## Error Classification
| Class | Action |
|---|---|
| Validation (bad input) | Return 400, describe input requirement |
| Not found | Return 404, describe what was missing |
| Permission | Return 403, describe required permission |
| Timeout | Retry with backoff or fail fast |
| Internal bug | Log full trace, return 500, alert |

## AI Agent Error Protocol
1. Never fabricate tool outputs on error
2. Report exact error message verbatim
3. Stop on genuine blockers (don't loop 4+ times)
4. State what was attempted and what failed
5. Leave code in buildable state after error

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 20. Strategic Compact
# ---------------------------------------------------------------------------

STRATEGIC_COMPACT = _make(
    name="ecc_strategic_compact",
    description=(
        "ECC strategic compact: structured planning framework for "
        "decomposing complex goals into bounded, executable tasks."
    ),
    tags=["planning", "strategy", "decomposition", "goals"],
    front_door_phrases=[
        "strategic compact",
        "plan this task",
        "strategic planning framework",
        "decompose goal into tasks",
    ],
    markdown="""# ECC Strategic Compact

Adapted from ECC strategic-compact (MIT). Task decomposition for Jarvis planning.

## Strategic Compact Template
```
GOAL: <one-sentence objective>
SCOPE: <what is in / out of scope>
TIMELINE: <sprint / task / immediate>
SUCCESS: <concrete, verifiable criteria>
RISKS: <top 3 blockers>
APPROACH:
  1. <first bounded step>
  2. <second bounded step>
  ...
CHECKPOINT: <when to pause and verify>
ROLLBACK: <how to undo if needed>
```

## Decomposition Rules
1. Each step must be independently executable
2. Each step must have a verifiable output
3. Steps must be sequential or explicitly parallel
4. No step should span more than 1 sprint
5. Rollback plan must exist before starting

## Planning Anti-Patterns
- Vague steps: "improve the system" → not executable
- Missing success criteria: "make it better" → not verifiable
- Over-scoped steps: 10+ file changes in one step
- No rollback: "we'll figure it out if it fails"

## Jarvis Planning Integration
- Strategic compact → task tickets in project registry
- Each step → checkpoint-tracked sprint item
- Completed steps → ACCEPT before next step starts
- Blocked steps → HOLD with exact blocker recorded

## Priority Order (for sprint planning)
1. Safety fixes (blockers, regressions)
2. Core capability gaps
3. Efficiency improvements
4. Expansion features
5. Nice-to-have polish

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 21. Security Scan
# ---------------------------------------------------------------------------

SECURITY_SCAN = _make(
    name="ecc_security_scan",
    description=(
        "ECC security scan: security scanning checklist and vulnerability "
        "pattern guide for AI-assisted code review."
    ),
    tags=["security", "scanning", "vulnerabilities", "review"],
    front_door_phrases=[
        "security scan",
        "security checklist",
        "vulnerability scan guidance",
        "security review checklist",
    ],
    markdown="""# ECC Security Scan

Adapted from ECC security-scan (MIT). Security checklist for Jarvis code review.

## Top Security Checks

### Secrets and Credentials
- [ ] No hardcoded API keys, passwords, tokens, or secrets
- [ ] No secrets in git history or diffs
- [ ] Environment variables used for secrets (not config files)
- [ ] `.env` files excluded from git

### Input Validation
- [ ] User inputs validated before use
- [ ] SQL: parameterized queries only (no string concatenation)
- [ ] Shell: no user-controlled string in shell commands
- [ ] File paths: no path traversal (`../../` patterns)

### Authentication / Authorization
- [ ] Auth checked on all protected routes
- [ ] Role permissions enforced at resource level
- [ ] Sessions expire correctly
- [ ] Sensitive endpoints not publicly accessible

### Dependencies
- [ ] Check for known CVEs in direct dependencies
- [ ] Pinned dependency versions (no `*` or `latest`)
- [ ] No abandoned/unmaintained packages

### AI-Specific Security
- [ ] No prompt injection via user input
- [ ] Tool permission scopes enforced (no over-privileged tools)
- [ ] No model outputs executed without sanitization
- [ ] No secrets in model context

## Jarvis Security Gates
- Security scan required before any code that handles auth/secrets
- Hard gate: no production deployment without passing scan
- Agent-Shield: unsafe inputs are rejected at front door

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 22. Documentation Lookup
# ---------------------------------------------------------------------------

DOCUMENTATION_LOOKUP = _make(
    name="ecc_documentation_lookup",
    description=(
        "ECC documentation lookup: structured approach for finding "
        "authoritative documentation and reference materials efficiently."
    ),
    tags=["documentation", "lookup", "reference", "research"],
    front_door_phrases=[
        "documentation lookup",
        "find documentation",
        "where is the docs",
        "documentation reference pattern",
    ],
    markdown="""# ECC Documentation Lookup

Adapted from ECC documentation-lookup (MIT). Documentation discovery for Jarvis.

## Documentation Hierarchy (most authoritative first)
1. **Official spec** — language/protocol specification
2. **Official docs** — vendor/framework documentation
3. **Source code** — actual implementation (ground truth)
4. **Tests** — how the library is actually used
5. **README** — project-level guidance
6. **Issues/PRs** — known problems and workarounds
7. **Stack Overflow** — community solutions (verify against above)

## Efficient Lookup Pattern
1. Search official docs first (docs.python.org, docs.fastapi.tiangolo.com, etc.)
2. If not found: search GitHub source code for usage examples
3. If still unclear: check test files (`tests/` or `spec/`)
4. Only use unofficial sources if official confirms no answer

## What to Record
- URL of authoritative source
- Version of library/framework
- Key API signature or behavior
- Any caveats or breaking changes

## Jarvis Doc Lookup Policy
- Prefer local source code over web search (faster, authoritative)
- `rg "<function_name>" --type py` in dependencies before web search
- Record lookup findings in checkpoint if non-obvious
- Never assume API behavior without checking docs or source

## Common Lookup Targets
| Target | Where to look |
|---|---|
| Python stdlib | docs.python.org/3/ |
| FastAPI | fastapi.tiangolo.com |
| Pydantic | docs.pydantic.dev |
| OpenAI API | platform.openai.com/docs |
| GitHub API | docs.github.com |

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)

# ---------------------------------------------------------------------------
# 23. Continuous Learning v2
# ---------------------------------------------------------------------------

CONTINUOUS_LEARNING_V2 = _make(
    name="ecc_continuous_learning_v2",
    description=(
        "ECC continuous-learning v2: enhanced agent improvement with "
        "structured capability tracking and performance regression detection."
    ),
    tags=["learning", "capability", "regression", "improvement"],
    front_door_phrases=[
        "continuous learning v2",
        "capability tracking",
        "agent improvement protocol",
        "performance regression detection",
    ],
    markdown="""# ECC Continuous Learning v2

Adapted from ECC continuous-learning-v2 (MIT). Enhanced capability tracking for Jarvis.

## Capability Registry
Track capabilities as one of:
- `AVAILABLE` — demonstrated by passing test with evidence
- `DEGRADED` — works but with limitations (log limitation)
- `PLANNED` — on roadmap, not yet implemented
- `NOT_CONFIGURED` — needs setup (API key, model, etc.)

## Never count PLANNED or NOT_CONFIGURED as AVAILABLE.

## Performance Regression Detection
After each sprint:
1. Run previously-passing targeted tests
2. If any fail: flag as regression, halt sprint, investigate
3. Document root cause in checkpoint
4. Fix regression before new feature work

## Capability Growth Pattern
```
Baseline → Sprint → Checkpoint → (ACCEPT → capability++) | (HOLD → debug → retry)
```

## Learning from Holds
Every HOLD verdict must record:
- What failed
- Why it failed
- What rule or check would prevent recurrence
- Whether a new test should be added

## Improvement Velocity
- Track: accepts per sprint, holds per sprint, regressions per sprint
- Target: accepts↑, holds↓, regressions=0
- Alert if regressions > 0 in consecutive sprints

## Permission Scope: read_only | Cost: free | Source: ECC (MIT)
""",
)


# ---------------------------------------------------------------------------
# Registry: all adapted skills by Jarvis skill ID
# ---------------------------------------------------------------------------

ADAPTED_SKILLS: Dict[str, SkillManifest] = {
    "ecc_benchmark_methodology": BENCHMARK_METHODOLOGY,
    "ecc_coding_standards": CODING_STANDARDS,
    "ecc_tdd_workflow": TDD_WORKFLOW,
    "ecc_verification_loop": VERIFICATION_LOOP,
    "ecc_context_budget": CONTEXT_BUDGET,
    "ecc_token_budget_advisor": TOKEN_BUDGET_ADVISOR,
    "ecc_cost_aware_pipeline": COST_AWARE_PIPELINE,
    "ecc_git_workflow": GIT_WORKFLOW,
    "ecc_search_first": SEARCH_FIRST,
    "ecc_agent_self_eval": AGENT_SELF_EVAL,
    "ecc_agent_eval": AGENT_EVAL,
    "ecc_safety_guard": SAFETY_GUARD,
    "ecc_prompt_optimizer": PROMPT_OPTIMIZER,
    "ecc_continuous_learning": CONTINUOUS_LEARNING,
    "ecc_rules_distill": RULES_DISTILL,
    "ecc_production_audit": PRODUCTION_AUDIT,
    "ecc_code_tour": CODE_TOUR,
    "ecc_codebase_onboarding": CODEBASE_ONBOARDING,
    "ecc_error_handling": ERROR_HANDLING,
    "ecc_strategic_compact": STRATEGIC_COMPACT,
    "ecc_security_scan": SECURITY_SCAN,
    "ecc_documentation_lookup": DOCUMENTATION_LOOKUP,
    "ecc_continuous_learning_v2": CONTINUOUS_LEARNING_V2,
}


def get_adapted_skill(jarvis_skill_id: str) -> SkillManifest | None:
    """Return an adapted ECC skill by Jarvis skill ID, or None if not found."""
    return ADAPTED_SKILLS.get(jarvis_skill_id)


def list_adapted_skill_ids() -> list[str]:
    """Return list of all adapted Jarvis skill IDs."""
    return list(ADAPTED_SKILLS.keys())


__all__ = [
    "ADAPTED_SKILLS",
    "get_adapted_skill",
    "list_adapted_skill_ids",
    # Individual manifests for direct import
    "BENCHMARK_METHODOLOGY",
    "CODING_STANDARDS",
    "TDD_WORKFLOW",
    "VERIFICATION_LOOP",
    "CONTEXT_BUDGET",
    "TOKEN_BUDGET_ADVISOR",
    "COST_AWARE_PIPELINE",
    "GIT_WORKFLOW",
    "SEARCH_FIRST",
    "AGENT_SELF_EVAL",
    "AGENT_EVAL",
    "SAFETY_GUARD",
    "PROMPT_OPTIMIZER",
    "CONTINUOUS_LEARNING",
    "RULES_DISTILL",
    "PRODUCTION_AUDIT",
    "CODE_TOUR",
    "CODEBASE_ONBOARDING",
    "ERROR_HANDLING",
    "STRATEGIC_COMPACT",
    "SECURITY_SCAN",
    "DOCUMENTATION_LOOKUP",
    "CONTINUOUS_LEARNING_V2",
]
