# US15 + US16 Foundation

**Status:** FOUNDATION (not ACCEPT)  
**US13 voice:** HOLD / UNSAFE — **parked**; hands-free voice excluded from release readiness.

## US15 implemented (foundation)

| # | Item | Status |
|---|------|--------|
| 1 | Jarvis-native coding loop (Workbench) | PARTIAL — US14A loop + US15 hooks |
| 2 | Repo map / symbol / dependency index | FOUNDATION — `repo_index.py` |
| 3 | Terminal executor + safety gates | PARTIAL — existing `shell_exec` + approval gates |
| 4 | Validation runner profiles | FOUNDATION — `validation_profiles.py` |
| 5 | Bounded repair loop | FOUNDATION — `repair_loop.py` wired on validation failure |
| 6 | First-class diff review | PARTIAL — existing diff tab/API |
| 7 | Git workflow executor | PARTIAL — git subtasks + `git_workflow_status()` |
| 8 | GitHub/CI visibility | FOUNDATION — `ci_visibility_status()` (gh auth = setup required) |
| 9 | Context caching hooks | FOUNDATION — `context_cache.py` |
| 10 | Unified executor approvals/events | PARTIAL — workbench events + approval queue |
| 11 | Model routing | PARTIAL — `ModelRouter` (plan-time routing logged) |
| 12 | Cost ledger | FOUNDATION — `CostLedger.record()` wired per subtask |
| 13 | Mission Control UI visibility | FOUNDATION — Capabilities panel |
| 14 | Doctor/readiness checks | FOUNDATION — workbench doctor checks 13–15 |
| 15 | Coding dogfood evidence | FOUNDATION — `dogfood_evidence.py` |
| 16 | Agents/Capabilities visibility | FOUNDATION — `capabilities_registry.py` |

## US16 safe foundations

| # | Item | Status |
|---|------|--------|
| 1 | Prompt/context caching | FOUNDATION — `ContextCache` |
| 2 | Model routing by complexity/cost | PARTIAL — existing `ModelRouter` |
| 3 | Cost ledger events | FOUNDATION — subtask cost recording |
| 4 | Local-first validation profiles | FOUNDATION — pytest profiles |
| 5 | Bounded retry/repair + stop-on-blocker | FOUNDATION — `BoundedRepairLoop` |
| 6 | No repeated accepted-checkpoint reverification | POLICY — unchanged |
| 7 | Performance/readiness metrics | PARTIAL — MC health + workbench doctor |

## Auto Browser

- **Source:** https://github.com/LvcidPsyche/auto-browser  
- **Status:** BLOCKED — provider interface only (`auto_browser_provider.py`)  
- **Merged into core:** No — requires security review  
- **Supported path today:** Playwright tools (`browser.py`) when `uv sync --extra browser`  
- **Unsafe automation rejected:** CAPTCHA bypass, credential extraction, deceptive automation, unauthorized scraping, approval bypass, uncontrolled autopilot

## US13 parked voice backlog

Do **not** use hands-free voice for US15/US16 validation.

Backlog (not implemented in this sprint):

1. Replace fixed 5-second recording with real VAD/endpointing  
2. Start after wake, continue while user is speaking, stop after end-of-speech/silence  
3. Support longer utterances naturally  
4. Reject silence/noise/STT hallucinations before transcript/model/TTS routing (partial gate exists)  
5. Preserve wake-only privacy boundary  
6. Preserve follow-up timeout/session handling  
7. Preserve stop phrases  
8. TTS cancellation/barge-in  
9. Evaluate streaming STT / Deepgram only after core non-voice work progresses  

## API endpoints

- `GET /v1/workbench/capabilities`  
- `GET /v1/workbench/repo-index`  
- `GET /v1/workbench/validation-profiles`  
- `GET /v1/workbench/dogfood-evidence`  

## Remaining before US15 ACCEPT

- Full symbol/dependency graph (not keyword heuristics only)  
- Live model calls during execution (not mock-only default)  
- CI status via authenticated `gh` in Bryan environment  
- Auto Browser MCP connector after security review  
- Interactive terminal UX  
- Structured diff review approve/reject workflow  
- US13 voice live-proof (separate track)
