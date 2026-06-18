# US13 — V1 Daily-Driver Certification

**Verdict: HOLD**
**Branch:** localhost-get-tool
**Base HEAD:** dc94532ee3ef4a53edc3123b0566ff80c3fd2b01

---

## Certification Matrix

| Area | Item | Status | Evidence | Notes |
|---|---|---|---|---|
| 1. Packaged app | `/Applications/OpenJarvis.app` launch | EXTERNALLY_NOT_PROVEN | `tauri.conf.json` version 1.0.1, `signingIdentity = "-"` (ad-hoc). Tauri build pipeline exists. | Gatekeeper prompt on first launch; notarization blocked by Apple Developer account. |
| 1. Packaged app | UI/backend connected | DONE | `SetupScreen.tsx` polls `/v1/setup-status` and gates on `server_ready=true` before handing off to main UI. | — |
| 2. Core mission system | Mission creation | DONE | `MissionControlPage.tsx` + `mission_routes.py`. `check_backend_health` verifies `openjarvis.mission.store`. | — |
| 2. Core mission system | Task lifecycle | DONE | `WorkbenchPage.tsx` shows task queue + approval state. `coding_manager.py` emits lifecycle events. | — |
| 2. Core mission system | Agent execution path | DONE | `CodingManager` → `JobQueue` → tool gateway. `check_execution_log_health` passes. | — |
| 3. Tool/skill/memory | Tool registry counts | DONE | `check_tool_registry_counts` passes; count accessible via `/v1/doctor`. | — |
| 3. Tool/skill/memory | Skill registry counts | DONE | `check_skill_registry_counts` passes. | — |
| 3. Tool/skill/memory | Memory write/search/export | DONE | `memory_routes.py`, `memory/store.py`. `check_memory_store_health` passes. `/v1/memory` endpoint accessible. | — |
| 4. Connectors | Slack private/sandbox readiness | EXTERNALLY_NOT_PROVEN | `check_connector_readiness` returns NOT_CONFIGURED. JARVIS_SLACK_BOT_TOKEN not set in this environment. Plan-only and dry-run gates enforced — no live send possible. | Set JARVIS_SLACK_BOT_TOKEN in environment. |
| 4. Connectors | Telegram private/sandbox readiness | EXTERNALLY_NOT_PROVEN | Same as Slack. JARVIS_TELEGRAM_BOT_TOKEN not set. Dry-run gate enforced. | Set JARVIS_TELEGRAM_BOT_TOKEN. |
| 4. Connectors | Tavily/web search | EXTERNALLY_NOT_PROVEN | `check_connector_readiness` — Tavily key not configured in this environment. | Set JARVIS_TAVILY_API_KEY. |
| 4. Connectors | GitHub/source status | EXTERNALLY_NOT_PROVEN | GitHub PAT not configured. | Set JARVIS_GITHUB_TOKEN. |
| 4. Connectors | OpenClaw linkage | EXTERNALLY_NOT_PROVEN | `check_openclaw_linkage` returns NOT_CONFIGURED. OpenClaw workspace not wired. | Configure OpenClaw handoff per OMNIX_WORKBENCH.md. |
| 4. Connectors | OMNIX linkage | DONE | `check_project_linkage_status` returns PASS. OMNIX project linked. | — |
| 5. Voice | True wake-word | HOLD | `.wake_worker_venv` with `openwakeword` is installed (`worker_available=True`). Wake-word listener is **configured but not started** — requires `jarvis voice start`. Not proven via live activation in this session. | Run: `jarvis voice start`. Say "hey jarvis" with mic open. |
| 5. Voice | In-app push-to-talk (mic button) | DONE | `MicButton` in `InputArea.tsx`. Click to record; uses `useSpeech` hook → `transcribeAudio`. STT=openai_whisper. Always available in app. | — |
| 5. Voice | Quick chat overlay (Cmd+Shift+Space) | DONE | Tauri `lib.rs:2460` registers `Cmd+Shift+Space` to toggle native overlay chat window. **This is chat, not voice.** Correctly labeled in Settings. | — |
| 5. Voice | CLI voice hotkey (daemon mode) | DONE | `wakeword_fallback.py` registers `cmd+shift+space` via `pynput.GlobalHotKeys` as voice hotkey. Active only when running `jarvis` as CLI daemon (not in packaged Tauri app where Tauri captures the binding first). Configurable via `JARVIS_VOICE_HOTKEY`. | — |
| 5. Voice | Model/settings palette (Cmd+K) | DONE | Opens `CommandPalette` for model management and API keys. **Not voice.** | — |
| 5. Voice | Manual chatbox | DONE | `ChatPage.tsx` always available. | — |
| 5. Voice | Microphone (STT toggle) | DONE | STT toggle in SettingsPage. `fetchSpeechHealth` reports backend status. | — |
| 5. Voice | STT backend | DONE | `stt_status = openai_whisper` (OPENAI_API_KEY configured). `faster_whisper` is priority 1 (not installed). Falls back to OpenAI Whisper. | — |
| 5. Voice | TTS | DONE | `tts_status = macos_say`. macOS `say` command detected. Built-in, no API key needed. | — |
| 5. Voice | Approval PIN | DONE | `set_operator_pin.py` script exists. Approval gates in `WorkbenchPage.tsx`. | — |
| 6. Desktop/operator | Permission status | DONE | Entitlements declared in `Entitlements.plist`. Wake-word status shown in Settings. Known Limitations panel describes exact manual steps. | — |
| 6. Desktop/operator | Dry-run | DONE | `CodingManager.DRY_RUN` path verified in tests. Plan-only and dry-run no-send gates confirmed in US14B tests. | — |
| 7. Automation | Queue | DONE | `JobQueue`, `get_queue_health_report()`, `check_job_queue` pass. | — |
| 7. Automation | Retry/backoff | DONE | `WakeWordBridge` exponential-backoff auto-restart. `get_retry_stats()` in job_queue. | — |
| 7. Automation | Idempotency | DONE | `JobQueue` dedup enforced by job_id. | — |
| 7. Automation | Persistent operations mode | DONE | `check_persistent_ops_status` passes. | — |
| 7. Automation | Approval gates | DONE | `approval_routes.py`, `WorkbenchPage.tsx` approval queue, `can_execute_without_approval = false`. | — |
| 8. Safety/governance | Hard gates | DONE | `check_autonomy_mode_status` and `check_strict_operating_rules_present` pass. `constitution.py` enforces hard gates. | — |
| 8. Safety/governance | Cost-control law | DONE | `cost_ledger.py`, `model_router.py`, `check_budget_guard` pass. | — |
| 8. Safety/governance | Rollback plans | DONE | `check_rollback_policy` passes. `ROLLBACK.md` created. | — |
| 8. Safety/governance | Prompt-injection guard | DONE | `check_inject_guard` passes. `security/inject_guard.py` verified. | — |
| 8. Safety/governance | Secret redaction | DONE | `CredentialStripper`, `redact_log_text`, `secret_scan_text` implemented and tested. Log export redacted before download. | — |
| 8. Safety/governance | Audit logs | DONE | `security/audit.py`, `workbench/event_log.py`. Local-only event log. | — |
| 9. Recovery | Safe reset | DONE | SettingsPage > Data > Clear All (confirm gate). | — |
| 9. Recovery | Backup/restore | DONE | Conversation export/import (JSON) in SettingsPage. | — |
| 9. Recovery | Queue recovery | DONE | `get_queue_health_report()`, `get_stalled_jobs()`, `reset_connector_failures()`. | — |
| 9. Recovery | Memory recovery | DONE | `check_memory_backup` passes. | — |
| 9. Recovery | Connector degraded behavior | DONE | `check_connector_health_monitor` + `get_degraded_connectors()`. Auto-escalates to blocked at 3 consecutive failures. | — |
| 10. Dogfood proof | Real Bryan workflow | NOT_PROVEN | Local environment: server starts, chat works, workbench visible, doctor/readiness accessible. No live connector send performed. | Full dogfood blocked by: Slack/Telegram tokens, wake-word, STT backend. |

---

## Certification Verdict

**HOLD**

All repo-controlled items are DONE. Voice pipeline is configured (wake-word worker available, STT=openai_whisper, TTS=macos_say, mic=granted, hotkey=available).

US13 is HOLD because:
- True wake-word activation has not been live-tested. Worker must be running (`jarvis voice start`) and "hey jarvis" must be spoken without crashing the callback.
- In-app mic button (push-to-talk) has not been live-tested via STT → chat reply in this session.
- Full activation flow (wake/mic → STT → chat reply → TTS speak) has not been proven in this session.
- Known bug fixed this session: `event.model_name` callback crash → now uses `event.model` (the actual field on `WakeWordTriggerEvent`).

**Bryan local verification commands** (run to upgrade to ACCEPT):
```bash
# 1. Check full voice pipeline readiness (no secrets printed)
jarvis voice status
# Expected: READY_FOR_LIVE_PROOF (all deps configured, worker not started)

# 2. Test TTS (macOS 'say' command — speaks "Jarvis is ready.")
jarvis voice test-tts
# Expected: TTS OK: engine='macos_say'

# 3. Check STT config (does not record audio)
jarvis voice test-stt
# Expected: STT engine=openai_whisper, configured=True

# 4. In-app push-to-talk (frontend): start server, open app, click mic button in chat
jarvis serve
# → open http://localhost:8080, click the mic icon in the chat input
# Speak a sentence. Expected: transcription appears in chat input, send to get reply.

# 5. Start the wake-word listener (blocks; say "hey jarvis" to activate)
jarvis voice start
# Expected: status shows RUNTIME_STARTED
# Say "hey jarvis" — expected log: "Wake word detected! model='hey_jarvis_v0.1' score=X.XXX"
# Press Ctrl+C to stop.

# 6. Run all voice readiness tests
.venv/bin/python3 -m pytest tests/test_us13_voice_readiness.py tests/test_voice_cli.py -v
```

Note on hotkeys:
- `Cmd+Shift+Space` in the packaged Tauri app = opens native chat overlay (NOT voice)
- Voice push-to-talk in app = mic button (🎤) in InputArea (always visible)
- CLI voice hotkey = JARVIS_VOICE_HOTKEY (only active when running as CLI daemon)

External limitations (connector tokens):
- Slack, Telegram, Tavily, GitHub tokens not in this environment (FUTURE_BACKLOG for dogfood)

No fake PASS claimed for any external item.

---

## Machine-Readable Status Source

- `GET /v1/readiness` — 28-category readiness gate (ready/warn/hold/unsafe)
- `GET /v1/doctor` — 33 diagnostic checks with evidence
- `GET /v1/readiness/report` — full V1 evidence summary
- `GET /v1/limitations` — structured known limitations list
- `GET /v1/version` — live version, git commit, branch

---

## Tests

- `tests/test_us13_certification.py` — 66 tests (module-scoped fixtures, truthfulness gate, all matrix areas)
- `tests/test_us12_polish.py` — 28 tests (redaction, version schema, limitations schema)
- `tests/workbench/test_us14b.py` — plan-only/dry-run gate tests
- `tests/test_us13_voice_readiness.py` — 15 test classes covering: voice schema, hotkey≠wake-word, manual chat always available, TTS/STT honest status, is_listening safety contract, no secrets in status
