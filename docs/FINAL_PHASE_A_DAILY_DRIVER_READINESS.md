# Final Phase A — Daily-Driver Readiness Checklist

**Sprint:** `FINAL_PHASE_A_BLOCKER_CLOSURE_AND_DAILY_DRIVER_READINESS`
**Date:** 2026-06-25
**Status:** IN_PROGRESS — not accepted

---

## Legend

| Status | Meaning |
|--------|---------|
| CODE_READY | Feature implemented, tests pass, no further code action needed |
| MANUAL_VERIFICATION_REQUIRED | Code is present; Bryan must verify by hand at MacBook |
| EXTERNAL_CREDENTIAL_GATE | Requires Bryan to supply or configure credentials/accounts |
| RELEASE_SIGNING_GATE | Requires Apple signing/notarization or App Store enrollment |
| PARKED | Explicitly deferred; not a blocker |

---

## Core Features

| Item | Status | Evidence |
|------|--------|----------|
| Text-first chat / Jarvis PA identity | CODE_READY | Plan 1 ACCEPTED; governance tests 44/44 pass |
| Unified memory search | CODE_READY | Plan 1 ACCEPTED |
| Cloud-first routing / Fargate | CODE_READY | Plan 2 ACCEPTED; plan9 494/494 pass |
| Approval gates / 6-tier authority | CODE_READY | Plan 2/8 ACCEPTED; tests pass |
| Rules engine (CRUD + evaluation) | CODE_READY | Plan 4-6 ACCEPTED; 44 rules tests pass |
| Expert role orchestration | CODE_READY | Plan 4-6 ACCEPTED; 11 frontdoor tests pass |
| Self-knowledge endpoints | CODE_READY | Plan 4-6 ACCEPTED; 9 self-knowledge tests pass |
| Delegation queue UI + routes | CODE_READY | Plan 4-6 B7 ACCEPTED; 19 delegation tests pass |
| System/connector status route | CODE_READY | Plan 4-6 B7 ACCEPTED; 19 system_status tests pass |
| Productization gate matrix | CODE_READY | Plan 4-6 B3 ACCEPTED; 12 productization tests pass |
| Phase X OMNIX decoupling | CODE_READY | Phase X ACCEPTED; JARVIS_IDENTITY.primary_project = None |
| Routines/scheduler visibility | CODE_READY | /v1/routines endpoint added; honest empty state |
| PWA manifest + service worker | CODE_READY | Plan 2 ACCEPTED; manifest present |
| Mobile parity routes | CODE_READY | Plan 2 ACCEPTED; plan9 tests pass |

---

## UI / Frontend

| Item | Status | Evidence |
|------|--------|----------|
| Frontend build (Vite + PWA) | CODE_READY | 12.18s build; PWA v1.2.0; 0 TS errors |
| RulesManagerPage | CODE_READY | Built at bc5b8ea6; responsive breakpoints added |
| ExpertRolesPage | CODE_READY | Built at bc5b8ea6; empty state added; responsive breakpoints |
| JarvisCapabilitiesPage | CODE_READY | Built at fcf623d0; responsive breakpoints added |
| DelegationPage | CODE_READY | Built at fcf623d0; responsive filter wrap added |

---

## Release Gate Items

| Item | Status | Notes |
|------|--------|-------|
| Tauri desktop build artifacts present | CODE_READY | DMG at frontend/src-tauri/target/release/bundle/macos/OpenJarvis_1.0.2_x64.dmg |
| Installed DMG smoke test | MANUAL_VERIFICATION_REQUIRED | Bryan must mount + install DMG on macOS; no safe command-line equivalent |
| macOS ad-hoc signing | CODE_READY | Tauri signs with ad-hoc; installable locally without notarization |
| macOS notarization | RELEASE_SIGNING_GATE | Required for distribution outside App Store; needs Apple Developer Account |
| iOS native scaffold (tauri ios init) | EXTERNAL_CREDENTIAL_GATE | Requires Apple Developer Account enrollment first |
| App Store submission | RELEASE_SIGNING_GATE | Requires Apple Developer Account; external gate |
| Auto-updater / release channel | MANUAL_VERIFICATION_REQUIRED | Updater endpoint not verified live; check Tauri updater config |

---

## Connector Credentials

| Connector | Status | Notes |
|-----------|--------|-------|
| Gmail OAuth | EXTERNAL_CREDENTIAL_GATE | OAuth token required; presence-only check via /v1/system/status |
| Google Calendar | EXTERNAL_CREDENTIAL_GATE | Same OAuth token as Gmail |
| Google Drive | EXTERNAL_CREDENTIAL_GATE | Same OAuth token as Gmail |
| Slack | EXTERNAL_CREDENTIAL_GATE | SLACK_BOT_TOKEN env var needed in Fargate |
| Telegram | EXTERNAL_CREDENTIAL_GATE | TELEGRAM_BOT_TOKEN env var needed in Fargate |
| Notion | EXTERNAL_CREDENTIAL_GATE | NOTION_API_KEY env var needed |
| GitHub | EXTERNAL_CREDENTIAL_GATE | GITHUB_TOKEN env var needed |
| Tavily / web search | EXTERNAL_CREDENTIAL_GATE | TAVILY_API_KEY env var needed |
| S3 / memory cloud sync | EXTERNAL_CREDENTIAL_GATE | JARVIS_S3_BUCKET / JARVIS_S3_REGION / JARVIS_S3_PROFILE needed |
| Fargate / cloud workers | MANUAL_VERIFICATION_REQUIRED | Fargate tasks must be running; verify via AWS console or CLI |

---

## Voice / TTS

| Item | Status | Notes |
|------|--------|-------|
| Voice / wake word / TTS | PARKED | Plan 3 explicitly parked by Bryan. Not started. |

---

## Acceptance Gate

Do NOT mark Final Phase A as ACCEPTED until:
1. Bryan manually verifies installed DMG smoke test
2. Bryan confirms connector credential gates are resolved for daily-driver use
3. Bryan/ChatGPT reviewer performs formal acceptance review

Only Bryan can mark Final Phase A ACCEPTED.
