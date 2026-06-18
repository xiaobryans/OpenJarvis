# US12 — Small Gaps Closure + Product Polish

**Status: DONE**
**Branch:** localhost-get-tool
**Base HEAD:** dc94532ee3ef4a53edc3123b0566ff80c3fd2b01

---

## Scope Item Status

| Item | Status | Evidence | Files Changed |
|---|---|---|---|
| Start Here onboarding (first-run entry point) | DONE | `GetStartedPage.tsx` context-aware (hosted/desktop/selfhosted) with server health check | `frontend/src/pages/GetStartedPage.tsx` |
| Setup wizard (guided connector + source setup) | DONE | `SetupWizard.tsx` (pick → connect → ingest → ready), `SetupScreen.tsx` (Ollama/model/server) | `frontend/src/components/SetupScreen.tsx`, `frontend/src/components/setup/SetupWizard.tsx` |
| Permission wizard — Microphone, Accessibility, Screen Recording | PARTIAL | macOS permissions must be granted manually (System Settings). `wake-word status` and info row added to Speech & Hotkeys section. Cannot programmatically request permissions — `Entitlements.plist` declares microphone/accessibility entitlements. | `frontend/src/pages/SettingsPage.tsx` |
| Connector setup UX (Slack, Telegram, Tavily, GitHub, OpenClaw, OMNIX) | PARTIAL | API key inputs for cloud/web-search providers in SettingsPage. Slack/Telegram/GitHub/OpenClaw/OMNIX tokens are backend-only. No connector panel in packaged UI. No secrets printed. | `frontend/src/pages/SettingsPage.tsx` |
| Hotkey/voice settings UX | DONE | Input & Voice section: voice push-to-talk hotkey (Cmd+Shift+Space, from backend JARVIS_VOICE_HOTKEY), model/settings palette (Cmd+K — not voice), system panel (Cmd+I), wake-word status (live from /v1/voice/status), STT/TTS/microphone status | `frontend/src/pages/SettingsPage.tsx` |
| Known limitations panel | DONE | `Known Limitations` section in SettingsPage loads from `/v1/limitations`. Shows severity, description, workaround for each. Falls back gracefully when backend is unreachable. | `src/openjarvis/server/doctor_routes.py`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/lib/api.ts` |
| Better doctor/readiness UX — human-readable fix instructions | DONE | `/v1/doctor` returns human-readable summaries + evidence. Secrets backend FAIL now names exact env vars. Connector NOT_CONFIGURED names the UI gap. Known limitations endpoint provides exact workarounds. | `src/openjarvis/server/doctor_routes.py`, `src/openjarvis/doctor/checks.py` |
| One-click repair / guided repair | NOT_APPLICABLE | No destructive or auto-fix actions permitted by governance policy. Dry-run is enforced. Repair instructions are text-only in doctor output and known limitations panel. |  |
| Error messaging polish | DONE | SetupScreen shows specific error with detail. Doctor check FAIL summaries name exact env vars/commands. Known limitations list actionable workarounds. | `frontend/src/components/SetupScreen.tsx`, `src/openjarvis/doctor/checks.py` |
| Local log viewer/export | DONE | LogsPage: copy-to-clipboard, export-to-file (secrets redacted via `redactLogText` before download). Redaction header included in export bundle. | `frontend/src/pages/LogsPage.tsx` |
| Version/status display (commit, branch, app version, connector status) | DONE | `/v1/version` endpoint returns version, git_commit, git_branch, queried_at. SettingsPage About section shows live version/commit/branch if server reachable. | `src/openjarvis/server/doctor_routes.py`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/lib/api.ts` |
| Minor UI inconsistencies (labels, badges, readiness colors, button states) | DONE | Speech section renamed to "Speech & Hotkeys". Known Limitations section uses severity-colored cards. Version panel uses monospace commit display. | `frontend/src/pages/SettingsPage.tsx` |
| Packaged app polish (app icon, menu bar/tray, launch behavior) | DONE | App icon pipeline exists (`icons/` in `src-tauri`). `signingIdentity = "-"` (ad-hoc). `createUpdaterArtifacts = true`. Launch behavior via `SetupScreen`. | `frontend/src-tauri/tauri.conf.json` |
| Remaining paper cuts — redaction utility | DONE | `redact_log_text()` and `secret_scan_text()` added as pure-Python helpers (no Rust dependency). Tests in `tests/test_us12_polish.py`. | `src/openjarvis/security/credential_stripper.py` |

---

## External Limitations

| Item | Status | Reason | Next Step |
|---|---|---|---|
| Slack/Telegram guided setup in UI | EXTERNALLY_NOT_PROVEN | Connector tokens are environment-only; no OAuth flow in packaged app | Add OAuth callback flow post-V1 |
| macOS permission wizard (programmatic request) | EXTERNALLY_NOT_PROVEN | macOS does not allow programmatic Accessibility/Screen Recording permission prompts from non-entitlement paths | Entitlements declared; user must grant in System Settings > Privacy & Security |
| Wake-word activation (auto-start) | HOLD | `.wake_worker_venv` with openwakeword is installed. Wake-word listener requires explicit `VoicePipeline.start()` or `jarvis serve --voice`. Configuration is correct; live activation not proven in this session. | Run `jarvis serve --voice` and say "hey jarvis" |

---

## Tests

- `tests/test_us12_polish.py` — 28 tests covering: CredentialStripper, `redact_log_text`, `secret_scan_text`, version helpers, limitations schema, no-secrets assertions.

---

## Safety

- No secrets printed.
- No live connector sends.
- No approval bypass.
- No destructive repair.
- No deploy.
