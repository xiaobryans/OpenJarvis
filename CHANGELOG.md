# Changelog

All notable changes to OpenJarvis are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### US12 — Small Gaps Closure + Product Polish

**Status wording and backend-only annotations** (`doctor/checks.py`):
- Fixed module docstring: "12 independent" → "32 independent diagnostic checks".
- `check_secrets_backend` FAIL summary now names the env vars to set
  (`JARVIS_OPENAI_API_KEY` / `JARVIS_ANTHROPIC_API_KEY` / macOS Keychain)
  instead of the opaque "0 keys present".
- `check_packaged_app_build_metadata` NOT_CONFIGURED summary now explicitly
  notes that US9–US12 capabilities are backend-only and not yet surfaced in
  the packaged app UI.
- `check_connector_readiness` NOT_CONFIGURED summary now carries a
  "backend-only status; no connector panel in the app UI yet" annotation so
  operators understand the distinction between backend capability and UI
  visibility.

**Stale reference cleanup** (`doctor/readiness.py`):
- Cost-control law comment updated: "US7" → "US11" (reflects the last sprint
  that touched the readiness layer).
- `evaluate_readiness()` docstring: "runs all 12 checks" → "runs all 32 checks".
- `generate_v1_report()` `remaining_limitations`: "not rebuilt in US7" →
  "not rebuilt in US12 (US9–US12 capabilities are backend-only)".
- Added US12 entry to `_ACCEPTED_CHECKPOINTS` so the accepted sprint chain
  is complete through US12.

**Test polish** (`tests/doctor/test_readiness.py`):
- Module docstring updated: "15 categories" → "27 categories".
- `test_category_checks_covers_all_15` renamed to
  `test_category_checks_covers_all_27` (the assertion already checked 27;
  only the name was stale).

**Documentation/handoff** (`CHANGELOG.md`, `JARVIS_OMNIX_HANDOFF.md`):
- Added this US12 section and the previously missing US11 section to
  `[Unreleased]`.
- Added US12 handoff section to `JARVIS_OMNIX_HANDOFF.md` documenting
  accepted capabilities, backend-only vs UI-visible limitations, and that
  packaged-app verification is intentionally deferred to the combined
  US9–US12 pass.

### US11 — Intelligence + Trust Layer

**Trust/evidence layer** (`intelligence/trust.py`):
- Added `TrustStatus` constants: `ready`, `degraded`, `blocked`,
  `unconfigured`, `unknown`.
- Added `EvidenceRecord`: verifiable evidence with source, reason, timestamp,
  value, and `is_verified()` / `to_dict()`.
- Added `INSUFFICIENT_DATA_MSG` + `insufficient_data()` helper — per honesty
  policy, missing evidence yields the standard `insufficient_data_to_verify`
  message rather than an inferred status.
- Added `ReadinessTrustReport` with `trust_status`, `is_sufficient`, and
  evidence list.
- Added `build_readiness_trust_report()`: returns READY if all required keys
  are present and non-empty, DEGRADED otherwise.

**Action confidence/approval** (`intelligence/trust.py`):
- Added `ActionAccessType` (read_only, propose_only, auto_approved,
  requires_approval, hard_blocked).
- Added `ActionProfile` dataclass: captures action_id, access_type,
  risk_level, requires_confirmation, and evidence.
- Added `build_action_profile()`: derives profile from action metadata;
  always blocks hard-gate actions regardless of context.

**Planner/self-check trust** (`intelligence/trust.py`):
- Added `PreExecutionSelfCheck.check()`: verifies all required context keys
  are present before execution.
- Added `PostExecutionSelfCheck.check()`: verifies result is non-empty and
  non-None; returns `ok=False` with a `reason` for empty or None results.

**Memory/context provenance** (`intelligence/trust.py`):
- Added `MemorySource` constants: `durable`, `transient`, `injected`,
  `inferred`, `unknown`.
- Added `MemoryProvenance`: captures source_type, namespace, recency,
  trust_status, and notes.
- Added `classify_memory_provenance()`: classifies durable sources as READY,
  transient as DEGRADED, injected as BLOCKED, inferred/unknown as UNKNOWN.

**Tool/connector intelligence** (`intelligence/trust.py`):
- Added `ConnectorTrustStatus` dataclass: connector_id, trust_status,
  last_health_ok, error_reason, evidence.
- Added `classify_connector_trust()`: READY when configured + healthy,
  DEGRADED when configured but last health failed (with reason), UNCONFIGURED
  when not configured.

**Readiness/status integration** (`doctor/checks.py`, `doctor/readiness.py`):
- Added `check_trust_layer` (check #32): imports all US11 symbols, verifies
  TrustStatus constants, exercises EvidenceRecord, MemoryProvenance,
  classify_connector_trust, PreExecutionSelfCheck, PostExecutionSelfCheck,
  build_readiness_trust_report, and insufficient_data.
- Added `TRUST_LAYER` category (27th category); marked required.
- Added US11 accepted checkpoint to `_ACCEPTED_CHECKPOINTS`.

### US10 — Daily-Driver Operations Hardening

**Runtime lifecycle hardening** (`daemon/service.py`):
- Added `RuntimeLifecycleManager`: PID file management, startup health probe
  (importability check for core modules), graceful shutdown with registered
  callbacks, SIGTERM/SIGINT handlers, and `is_running()` static helper.

**Voice worker lifecycle hardening** (`autonomy/wakeword_bridge.py`):
- Added watchdog thread with exponential-backoff auto-restart (`auto_restart=True`
  on `WakeWordBridge.start()`). Configurable via `JARVIS_WAKEWORD_MAX_RESTARTS`
  (default 5) and `JARVIS_WAKEWORD_RESTART_BACKOFF` (default 2.0s base).
- `status()` now reports `restart_count`, `last_restart_at`, `auto_restart`,
  and `max_restarts`.

**Connector health degradation handling** (`autonomy/connector_health.py`):
- Auto-promotes connectors from `degraded` → `blocked` when
  `consecutive_failures >= 3` (configurable `_DEGRADED_ESCALATION_THRESHOLD`).
- Added `get_degraded_connectors()`, `get_connector_degradation_summary()`,
  and `reset_connector_failures()` for remediation workflows.

**Durable queue retry/recovery visibility** (`autonomy/job_queue.py`):
- Added `get_stalled_jobs()`: jobs stuck in `running` state past stale threshold.
- Added `get_retry_stats()`: retry counts, exhausted-attempts summary.
- Added `get_queue_health_report()`: unified health report for ops dashboard.

**Alert limiting / failure escalation** (`autonomy/alert_limiter.py`):
- Added `auto_escalate_on_failures(failure_count, threshold)`: activates
  `incident_mode` when failure count exceeds threshold (no alert sends; advisory only).
- Added `get_escalation_status()`: current escalation state for doctor/readiness.

**Readiness/status accuracy** (`doctor/checks.py`, `doctor/readiness.py`):
- Added `check_runtime_lifecycle` (check #31): verifies lifecycle manager,
  queue crash recovery, wakeword bridge, connector degradation summary, and
  alert escalation are all importable; confirms PID dir is writable.
- Added `RUNTIME_LIFECYCLE` category (26th category); marked required.
- Added US10 accepted checkpoint to `_ACCEPTED_CHECKPOINTS`.

## [1.0.2] - 2026-05-24

A patch release that fixes a packaging bug which broke the v1.0.1
wheel on PyPI, silences a noisy startup warning, restores a working
install path while `openjarvis.ai` is down, improves desktop
first-boot diagnostics on Windows, and ships the RAM-detection fix
for Windows that missed the v1.0.1 cutoff.

### Fixed

**`openjarvis/traces/` missing from the v1.0.1 PyPI wheel** (#372).
The `.gitignore` carried an unanchored `traces/` pattern, which
hatchling honored at wheel-build time and matched the runtime module
`src/openjarvis/traces/` — silently dropping the whole package. Every
fresh `pip install openjarvis==1.0.1` then failed at import with
`ModuleNotFoundError: No module named 'openjarvis.traces'` on the
first `jarvis ask`, learning, or server call. Anchored the pattern to
`/traces/`. Verified: a clean `uv build` now produces a wheel
containing all four `traces/` files.

**`pynvml` deprecation `FutureWarning` on every command** (#389).
Switched the dependency from the legacy `pynvml` package to NVIDIA's
official `nvidia-ml-py` (same `pynvml` module name, no warning shim),
and added defensive `warnings.filterwarnings` at every `import pynvml`
site to suppress the warning even when `pynvml` is pulled in
transitively.

**Windows RAM detection returning `0.0 GB`** (#373). The Windows
branch of `_total_ram_gb()` (via `GlobalMemoryStatusEx`) landed after
the v1.0.1 cutoff, so v1.0.1 users still saw `0.0 GB` from `jarvis
init`. Now shipping in the wheel. A new `windows-latest` CI job runs
the real `GlobalMemoryStatusEx` path on every PR as a regression
guard.

**Desktop first-boot hung on "did not become healthy in time"**
(#331). The Tauri boot path ran `uv sync` with stderr discarded and
the exit code ignored, so a failed dependency install surfaced only
as a generic 600-second health-check timeout. Now captures stderr,
checks the exit status, and surfaces the actual `uv sync` error
(with the diagnostic tail) before the long wait. The error-formatting
logic is covered by unit tests.

### Changed

**Install URL moved to GitHub Pages** (#337, #352). The documented
`openjarvis.ai/install.sh` URL was failing with `sslv3 alert
handshake failure` (the domain is community-operated and had a broken
TLS config). The canonical installer is now served from the
project-controlled GitHub Pages site at
`https://open-jarvis.github.io/OpenJarvis/install.sh`, generated from
the same `scripts/install/install.sh` at docs-build time. The README
also documents the WSL2 path for Windows and the `uv` prerequisite
for the desktop binary, and the installer bails early with a clear
message when run under Git Bash / MSYS2 / Cygwin.

## [1.0.1] - 2026-05-17

A patch release that closes the auto-update gap so the analytics
module added in #351 actually reaches users on the desktop, adds
runtime opt-out for that analytics, fixes the misleading upgrade
hint the CLI was printing, and lands the ACE optimizer alongside
DSPy and GEPA.

### Added

**ACE agent optimizer** (`learning/agents/ace_optimizer.py`). Adds
[ACE](https://github.com/ace-agent/ace) as a third agent-learning
policy alongside DSPy and GEPA. Where DSPy bootstraps few-shot
examples and GEPA evolves prompt populations, ACE evolves a textual
*playbook* of strategies the agent reads at inference time, updated
by a Generator / Reflector / Curator triad. Pick via
`[learning.agent] policy = "ace"`. Setup is manual (ACE isn't on
PyPI and isn't a properly-packaged Python project as of v1.0.1) —
see `docs/learning/ace.md` for the install path and trace-adapter
behavior.

**`jarvis self-update`** subcommand. Detects how OpenJarvis was
installed (pip, uv tool, editable git checkout) by inspecting
`openjarvis.__file__`, then runs the right upgrade command. Supports
`--check` (print the command without running) and `-y` (skip the
confirmation prompt). The post-command "new version available" hint
now points users at this command instead of guessing at the right
flow.

**Desktop auto-update endpoint wired to the rolling
`desktop-latest` GitHub release.** The Tauri updater plugin was
configured on the build side (`createUpdaterArtifacts: true`,
`includeUpdaterJson: true`, signing key in `TAURI_SIGNING_PRIVATE_KEY`)
but inert on the runtime side (`active: false`, `endpoints: []`). The
installed desktop app would never check. Both are now fixed; the app
polls `releases/download/desktop-latest/latest.json` every 30 minutes
and signature-verifies downloads against the minisign pubkey baked
into the app. Full flow, key-rotation runbook, and dev escape hatch
(`OPENJARVIS_NO_UPDATER=1`) documented in `docs/desktop-auto-update.md`.

**Analytics env-var opt-out** (`DO_NOT_TRACK`, `OPENJARVIS_NO_ANALYTICS`).
Tanvir's analytics module (#351) only respected the
`[analytics] enabled` config-file setting. Both env vars are now
honored in `is_analytics_enabled()` and in the install.sh beacon
script. Any truthy value (`1`, `true`, `yes`, `on`) disables for
that process; env opt-out takes precedence over the config file.
Documented under a new "Opting out" section in `docs/telemetry.md`.

### Changed

**Version-check trigger widened.** The "new version available" hint
in `_version_check.py` used to fire only on `{ask, chat, serve}` and
hardcoded the wrong upgrade command (`git pull && uv sync` — only
correct for editable installs). Now fires on every interactive
command (`doctor`, `init`, `quickstart`, `model`, `agents`, `skill`,
`memory`, `bench`, `telemetry`, `config`, `eval`, `optimize`, plus
the original three) and uses install-detection to print the right
upgrade command. Honors `JARVIS_NO_UPDATE_CHECK=1` and `CI=true` to
stay silent in automation.

**Desktop app version bumped 0.1.0 → 1.0.1** across
`tauri.conf.json`, `frontend/package.json`, and
`frontend/src-tauri/Cargo.toml` so the Python and desktop release
streams are aligned and the auto-updater has a real version to
compare against.

### Migration from 1.0.0

- **Importing `is_analytics_enabled`?** Same signature; behavior now
  short-circuits on env opt-out before checking the config. Callers
  that want the raw "is the config flag set" semantic should read
  `cfg.enabled` directly.
- **Editable-git users running `jarvis self-update`** get the
  detected `git pull && uv sync` command pointed at their actual
  checkout, not `~/OpenJarvis`. If you'd come to rely on the
  hardcoded path, update your muscle memory.

## [1.0.0] - 2026-05-15

The five-primitive architecture (Intelligence, Engine, Agents,
Tools & Memory, Learning) is now stable, with efficiency and
on-device learning as first-class capabilities alongside accuracy.
Companion blog post:
[From Minions to OpenJarvis: A Retrospective on Two Years in Local AI](https://hazyresearch.stanford.edu/blog/2026-05-19-minions-to-openjarvis-retrospective).

### Highlights

**Five composable primitives.** Intelligence, Engine, Agents, Tools & Memory,
and Learning each sit behind a single typed interface — any slot is
substitutable without touching the rest. The composition layer is
`JarvisSystem` in `src/openjarvis/system.py`, driven by a TOML config.

**Built-in agents across three execution modes.** Eight agents spanning a
single-turn chat baseline, a deep-research agent with inline citations,
a CodeAct-style coder, and a continuous monitor with memory compression
for long-horizon workflows. Execution modes cover on-demand, scheduled,
and continuous.

**Starter presets.** Eight preset configs installable via
`jarvis init --preset <name>` bundle an agent with a hardware-appropriate
engine, connectors, and tools. Variants cover Apple Silicon, Linux GPU
servers, and CPU-only laptops, plus a quickstart for LLM-guided spec search.

**Inference engines.** Four first-class local engines (Ollama, vLLM, SGLang,
llama.cpp) and five cloud providers (OpenAI, Anthropic, Google Gemini,
OpenRouter, MiniMax) sit behind a single `Engine` interface. Discovery
in `engine/_discovery.py` picks a sensible default per host.

### Added — hybrid local-cloud capabilities

**Per-query routing via a query-complexity analyzer**
(`src/openjarvis/learning/routing/complexity.py`). Produces a 0.0–1.0
complexity score with code/math/reasoning signals and a suggested token
budget, populating `RoutingContext` so easy queries stay local and only
queries that need frontier capability escalate.

**LLM-guided spec search** (`src/openjarvis/learning/spec_search/`).
`SpecSearchOrchestrator` wires diagnose → plan → execute → gate into a
single learning session: a frontier model reads traces, proposes
coordinated edits across all five primitives, and a held-out benchmark
gate (`gate/benchmark_gate.py`, `gate/regression.py`, `gate/cold_start.py`)
accepts only non-regressing edits. Ships with the `spec-search-quickstart`
preset and a runnable tutorial at `examples/openjarvis/spec_search_quickstart.py`.

**Six hybrid coordination paradigms** in `src/openjarvis/agents/hybrid/`.
Each paradigm pairs a local student with a frontier cloud teacher under
a different orchestration shape, as `LocalCloudAgent` subclasses:

- `minions` — reactive single-local + single-cloud loop
- `conductor` — static DAG planner
- `advisors` — executor ↔ advisor loop
- `archon` — generate → rank → fuse
- `skillorchestra` — per-query router across local skills
- `toolorchestra` — RL'd local model with a tool pool

A runner CLI (`python -m openjarvis.agents.hybrid.runner --cell <name>`)
and a 35-cell experiment registry (one TOML per method × benchmark ×
model triple) let researchers run, score, and compare these on equal
footing. Includes a Modal-backed SWE-bench-Verified harness scorer
(`evals/scorers/swebench_harness.py`).

### Added — efficiency as a first-class constraint

**Hardware-agnostic energy telemetry at 50ms resolution** across NVIDIA
(`telemetry/energy_nvidia.py`), AMD (`telemetry/energy_amd.py`), Apple
Silicon (`telemetry/energy_apple.py`), and Intel RAPL
(`telemetry/energy_rapl.py`). Energy, dollar cost, FLOPs, and latency
are treated as evaluation targets alongside accuracy.

**Instrumentation for FLOPs, batch, steady-state, ITL, phase energy, and
vLLM-specific metrics.** Joined per-query by the aggregator
(`telemetry/aggregator.py`) so traces carry accuracy + efficiency together.

### Added — local learning loop

**Closed-loop optimization across the stack** — model weights via SFT
(`learning/intelligence/sft_trainer.py`) and GRPO
(`learning/intelligence/grpo_trainer.py` plus an orchestrator-specific
variant under `learning/intelligence/orchestrator/`), prompts via DSPy
(`learning/agents/dspy_optimizer.py`), agent logic via GEPA
(`learning/agents/gepa_optimizer.py`), and engine + stack configuration
via LLM-guided spec search. `LearningOrchestrator` coordinates triggers
and applies optimizer overlays at discovery time so improvements compound
across primitives.

### Added — cross-framework evaluation

**External agentic-framework evaluation via subprocess.** The
`evals/backends/external/` subpackage wraps Hermes Agent and OpenClaw as
one-shot subprocess backends behind the existing `InferenceBackend` ABC.
The `evals/comparison/` toolkit provides path + commit-pin enforcement
(`third_party.py`), config templating (`make_configs.py`), and LaTeX
table generation (`table_gen.py`).

Ships with a new optional extra `framework-comparison` (depends on
`polars`), a `live_external` pytest marker for integration tests
requiring real foreign-framework installations, and a `ToolOrchestra`
evaluation dataset (`evals/datasets/toolorchestra.py`) alongside the
existing 30+ benchmark suite.

### Added — Skills System (Plans 1, 2A, 2B)

- **Skills core** — every skill is a tool. Skills appear in a system prompt catalog, agents invoke them on demand, content (pipeline results, markdown instructions, or both) gets injected into context.
  - `SkillManifest` + `SkillStep` types with tags, depends, invocation flags, markdown content
  - `SkillManager` — discovery, precedence resolution, catalog XML generation, tool wrapping
  - `SkillTool(BaseTool)` — auto-extracts parameters from step argument templates
  - `SkillExecutor` — sequential pipeline execution with sub-skill delegation
  - Dependency graph with cycle detection, max depth enforcement, capability unions
  - Security: four trust tiers (bundled/indexed/unreviewed/workspace), capability-gated enforcement
  - Skill index module for git-backed registry search

- **agentskills.io spec adoption** — canonical `SKILL.md` format with YAML frontmatter following the [agentskills.io](https://agentskills.io/specification) open standard.
  - `SkillParser` with strict spec validation + tolerant field mapping via `FIELD_MAPPING` table
  - `ToolTranslator` for external tool name translation (Bash -> shell_exec, Read -> file_read, etc.)
  - Source resolvers: `HermesResolver`, `OpenClawResolver`, `GitHubResolver`
  - `SkillImporter` with provenance tracking (`.source` metadata files), optional script import
  - Sourced subdirectory layout (`~/.openjarvis/skills/<source>/<name>/`)

- **Skills learning loop** — trace tagging, pattern discovery, DSPy/GEPA optimization.
  - Trace metadata tagging: `skill`, `skill_source`, `skill_kind` flow through ToolExecutor -> TraceCollector -> TraceStep
  - `SkillDiscovery` wired into `SkillManager.discover_from_traces()` with kebab name normalization
  - `SkillOptimizer` — per-skill DSPy/GEPA wrapper that buckets traces and writes sidecar overlays
  - `SkillOverlay` — sidecar storage at `~/.openjarvis/learning/skills/<name>/optimized.toml`
  - `SkillManager._load_overlays()` applies optimized descriptions + few-shot examples at discovery time
  - `LearningOrchestrator._maybe_optimize_skills()` — opt-in auto-trigger

- **Skills benchmark harness** — 4-condition PinchBench evaluation.
  - I3 fix: `skill_few_shot_examples` wired through SystemBuilder -> `_run_agent` -> `ToolUsingAgent` -> `native_react.REACT_SYSTEM_PROMPT`
  - `SkillBenchmarkRunner` — 4-condition x N-seed x M-task sweep with markdown report
  - `JarvisAgentBackend` accepts `skills_enabled` and `overlay_dir` kwargs
  - Conditions: `no_skills`, `skills_on`, `skills_optimized_dspy`, `skills_optimized_gepa`

- **CLI commands:**
  - `jarvis skill list` / `info` / `run` / `install` / `sync` / `sources` / `update` / `remove` / `search`
  - `jarvis skill discover` — mine traces for recurring tool patterns
  - `jarvis skill show-overlay` — inspect optimization output
  - `jarvis optimize skills` — run DSPy/GEPA per-skill optimization
  - `jarvis bench skills` — run the PinchBench skills benchmark

- **Agent prompt improvement:**
  - `native_react.REACT_SYSTEM_PROMPT` now includes "Using Skills" guidance that teaches agents to distinguish executable vs. instructional skill responses
  - `{skill_examples}` placeholder for optimized few-shot example injection

- **Configuration:**
  - `[skills]` section: `enabled`, `skills_dir`, `active`, `auto_discover`, `auto_sync`, `max_depth`, `sandbox_dangerous`
  - `[[skills.sources]]` section: `source`, `url`, `filter`, `auto_update`
  - `[learning.skills]` section: `auto_optimize`, `optimizer`, `min_traces_per_skill`, `optimization_interval_seconds`, `overlay_dir`
  - `SkillSourceConfig` and `SkillsLearningConfig` dataclasses

- **Documentation:**
  - `docs/user-guide/skills.md` — comprehensive user guide
  - `docs/architecture/skills.md` — technical deep-dive
  - `docs/tutorials/skills-workflow.md` — end-to-end tutorial
  - `docs/getting-started/configuration.md` — expanded with skills config sections
  - `CLAUDE.md` — updated architecture section

### Examples & Tutorials

- `examples/openjarvis/spec_search_quickstart.py` — runnable end-to-end
  LLM-guided spec search session.
- `docs/user-guide/llm-guided-spec-search.md` — paper-aligned user guide.
- `docs/architecture/learning.md` — Learning primitive deep-dive covering
  routing, spec search, optimizers, and the orchestrator.
- `docs/tutorials/` — code-companion, deep-research, messaging-hub,
  scheduled-ops, and skills-workflow walkthroughs.
- `src/openjarvis/agents/hybrid/registry/*.toml` — 35-cell registry of
  paradigm × benchmark × model experiments.

### Migration from 0.x

- **`learning/distillation/` is now `learning/spec_search/`.** The
  subsystem was renamed to match the LLM-guided spec search semantics
  documented in the companion paper. Update any imports
  (`from openjarvis.learning.distillation.*` →
  `from openjarvis.learning.spec_search.*`). The `jarvis distillation`
  CLI command is removed; use `spec_search`-prefixed config keys instead.
- **`_third_party.toml` no longer ships default paths.** Set
  `HERMES_AGENT_PATH` and `OPENCLAW_PATH` env vars to point at your
  local checkouts before running the framework-comparison harness;
  missing or empty paths now raise `ThirdPartyNotFoundError` with an
  actionable hint.
- **Engine `generate_full` return shape extended.**
  `JarvisAgentBackend.generate_full` and `JarvisDirectBackend.generate_full`
  now return the spec §6.2 extended fields (`energy_joules`,
  `peak_power_w`, `tool_calls`, `turn_count`, `framework`,
  `framework_commit`, `error`). Existing callers that didn't read these
  fields are unaffected; new callers can rely on cross-framework parity.

### Fixed

- **Trace metadata flow** — `ToolResult.metadata` now propagates through `TOOL_CALL_END` event to `TraceStep.metadata` (was silently dropped at the event-bus boundary).
- **TaintSet JSON serialization** — `ToolExecutor._json_safe_metadata()` filters non-JSON-serializable values (like `TaintSet`) from event payloads before they reach `TraceStore`.
- **Non-dict YAML frontmatter** — source resolvers handle `yaml.safe_load()` returning a string instead of a dict (discovered on real OpenClaw imports).
- **OpenClaw category/name queries** — `jarvis skill install openclaw:owner/slug` now correctly splits into category + name match.
- **SkillDiscovery trace compatibility** — `_extract_tool_sequence` reads from `step.input["tool"]` (the actual `TraceStep` format), not the nonexistent `step.tool_name` attribute.
- **LearningOrchestrator skill trigger** — `_maybe_optimize_skills` runs BEFORE the SFT-data short-circuit (skills are tagged via trace metadata, not mined as SFT pairs).
- **PinchBenchScorer constructor** — `SkillBenchmarkRunner` constructs `PinchBenchScorer(judge_backend, model)` instead of no-args.
- **EvalRunner results access** — reads per-task data from `eval_runner.results` property, not nonexistent `summary.results`.
