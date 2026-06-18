# US17 + US18 Readiness

**Status:** US17 ACCEPT-ready (local) | US18 ACCEPT-ready (local/founder V1)  
**US13 voice:** HOLD / UNSAFE — **parked**; hands-free excluded from public readiness.

---

## US17 — Adversarial Safety & Failure Recovery

| # | Item | Status |
|---|------|--------|
| 1 | Prompt injection denial | DONE — `inject_guard` + `evaluate_prompt_injection()` |
| 2 | Tool injection denial | DONE — `evaluate_tool_injection()` |
| 3 | Browser automation abuse denial | DONE — `auto_browser_provider` + `evaluate_browser_action()` |
| 4 | Terminal/destructive command denial | DONE — `terminal_executor` + `evaluate_terminal_command()` |
| 5 | Credential/secret exfiltration denial | DONE — exfil patterns + `file_policy` |
| 6 | Unauthorized file access denial | DONE — `evaluate_file_access()` |
| 7 | CAPTCHA bypass / deceptive / scraping / approval bypass / autopilot | DONE — blocked patterns |
| 8 | Git/CI misuse denial | DONE — force-push, skip-hooks patterns |
| 9 | Cost runaway / budget exceeded | DONE — `evaluate_cost_budget()` |
| 10 | Production/deploy hard gates | DONE — governance `HARD_GATE_ACTIONS` |
| 11 | External send hard gate | DONE — Slack/Telegram/email blocked |
| 12 | Autopilot disabled / approval bypass blocked | DONE — `evaluate_autopilot_policy()` |
| 13 | US13 voice parked enforcement | DONE — `evaluate_voice_parked()` |
| 14 | Safety events logged | DONE — `EVENT_SAFETY_BLOCKED`, `log_safety_event()` |
| 15 | Failure recovery playbooks | DONE — `failure_recovery.py` (12+ scenarios) |
| 16 | Doctor checks 23–26 | DONE — adversarial, recovery, founder, safety events |
| 17 | API routes | DONE — `/v1/workbench/safety/status`, `/safety/evaluate` |
| 18 | Adversarial self-test suite | DONE — `run_adversarial_self_test()` |

### API

- `GET /v1/workbench/safety/status` — adversarial + failure recovery summary
- `POST /v1/workbench/safety/evaluate` — evaluate category + payload

---

## US18 — Founder Dogfood + Public Readiness Gate

| # | Item | Status |
|---|------|--------|
| 1 | Founder dogfood checklist (14 items) | DONE — `founder_readiness.py` |
| 2 | Public readiness matrix | DONE — honest claims, no fake voice/cloud/mobile |
| 3 | Known limitations documented | DONE |
| 4 | Blocked/not-in-scope items | DONE — Waves, US13 voice, enterprise indexing |
| 5 | Rollback instructions | DONE |
| 6 | Founder retest steps | DONE |
| 7 | Release safety (no secrets, no auto-deploy) | DONE — secrets scan + hard gates |
| 8 | Tauri build | REQUIRES_USER_ACTION — run manually; signing may BLOCK |
| 9 | API routes | DONE — `/v1/workbench/founder-readiness`, `/public-readiness` |

### API

- `GET /v1/workbench/founder-readiness` — 14-item founder checklist
- `GET /v1/workbench/public-readiness` — release-safe matrix

---

## US13 Parked Voice Backlog

Location: `docs/US15_US16_FOUNDATION.md` § US13 parked voice backlog  
Also: `capabilities_registry.py` → `US13_VOICE_PARKED_NOTE`

Do **not** use hands-free voice for US17/US18 validation.

Backlog (unchanged):

1. Real VAD/endpointing (replace fixed 5s recording)
2. Record until end-of-speech
3. Long utterance support
4. Silence/noise/STT hallucination rejection
5. Wake privacy boundary
6. Follow-up session handling
7. Stop phrases
8. TTS cancellation/barge-in
9. Streaming STT/Deepgram evaluation (later)

---

## Founder Retest Steps

```bash
cd /Users/user/OpenJarvis
uv sync --extra server --extra browser --extra dev

export JARVIS_AUTO_BROWSER_ENABLED=1
export JARVIS_AUTO_BROWSER_MCP_URL=http://127.0.0.1:3000

uv run python -m pytest tests/workbench/test_us17_adversarial.py tests/workbench/test_us18_readiness.py -q --tb=short

uv run python -c "from openjarvis.workbench.adversarial_safety import get_safety_status_summary; import json; print(json.dumps(get_safety_status_summary(), indent=2))"

uv run python -c "from openjarvis.workbench.founder_readiness import generate_public_readiness_matrix; import json; print(json.dumps(generate_public_readiness_matrix(), indent=2))"
```

---

## Remaining Before Full Public Release (Not US17/US18 Blockers)

- Tauri desktop build + signing (REQUIRES_USER_ACTION)
- Live OpenRouter model calls (REQUIRES_USER_ACTION if cloud tier needed)
- US13 voice acceptance (separate track — parked)
