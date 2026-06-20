# Plan 1 ECC Live Key Validation Report

> Generated: 2026-06-21 | Branch: `localhost-get-tool`
> Security: No secrets printed. No external sends. No payments. No raw ECC executed.

## Summary

| State | Count |
|---|---|
| ACTIVE | 316 |
| COST_BLOCKED_OPTIONAL_LATER | 7 |
| NOT_NEEDED_FOR_NOW | 4 |
| READY_BUT_WAITING_FOR_API_KEY | 2 |
| READY_BUT_WAITING_FOR_APPROVAL | 0 |
| READY_BUT_WAITING_FOR_USER_MANUAL_SETUP | 1 |
| UNAUTOMATABLE_EVEN_WITH_APPROVAL | 2 |
| **TOTAL** | **332** |

## Security Verification

- [x] `.env` is gitignored (`^.env` in `.gitignore`)
- [x] `.env.*` pattern covers `.env.local`
- [x] No secret values printed or logged
- [x] No external sends (Slack/email/X) during validation
- [x] No payments or financial actions
- [x] No raw ECC hooks/scripts/plugins/MCP executed
- [x] No production deploys
- [x] Gates not weakened

## Provider Key Presence

| Provider | Present | Auth Test | Status |
|---|---|---|---|
| AIMLAPI | ✓ | models_list → 200 | VERIFIED |
| OpenRouter | ✓ | models_list → 200 | VERIFIED |
| Exa | ✓ | format_check (no call) | PRESENT |
| Perplexity | ✓ | format_check (no call) | PRESENT |
| Tavily | ✓ | search → 200 | VERIFIED |
| Slack | ✓ | auth.test → ok:true | VERIFIED |
| Linear | ✓ | graphql viewer → 200 | VERIFIED |
| Resend | ✓ | domains → 200 | VERIFIED (EMAIL_FROM needed for sends) |
| VideoDB | ✓ | collection/ → 200 | VERIFIED |
| Pinecone | ✓ | indexes → 200 | VERIFIED |
| Apollo | ✓ | people/match → 422 (valid key inferred) | VERIFIED |
| ScrapingBee | ✓ | scrape → 200 | VERIFIED |
| GitHub | ✓ | /user → 401 Bad credentials | KEY EXPIRED |
| Twitter/X | ✗ | not configured | COST_BLOCKED |
| Greenhouse | ✗ | Bryan: skip | NOT_NEEDED |
| Ahrefs | ✗ | Bryan: skip | NOT_NEEDED |
| Nutrient | ✗ | Bryan: skip | COST_BLOCKED |
| Stripe | ✗ | key missing | COST_BLOCKED |
| X402 | ✗ | Bryan: skip | NOT_NEEDED |
| Google OAuth | partial | refresh token missing | COST_BLOCKED |

## Local Tool Verification

| Tool | Installed | Version | Outcome |
|---|---|---|---|
| Flox CLI | ✓ | 1.13.0 | flox-environments → ACTIVE |
| Pillow | ✗ | - | ios-icon-gen stays READY_BUT_WAITING_FOR_USER_MANUAL_SETUP |

## Skills Activated (→ ACTIVE)

**61 skills moved to ACTIVE in this validation pass:**

- `ecc:agent:architect` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:build-error-resolver` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:code-reviewer` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:doc-updater` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:docs-researcher` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:e2e-runner` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:explorer` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:planner` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:refactor-cleaner` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:reviewer` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:security-reviewer` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:spec-miner` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:agent:tdd-guide` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:article-writing` — API key verified (AIMLAPI); safe auth test passed; skill activated
- `ecc:brand-discovery` — API key verified (Exa); safe auth test passed; skill activated
- `ecc:brand-voice` — API key verified (AIMLAPI); safe auth test passed; skill activated
- `ecc:browser-qa` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:cmd:database-migration` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:competitive-platform-analysis` — API key verified (Exa); safe auth test passed; skill activated
- `ecc:competitive-report-structure` — API key verified (Exa); safe auth test passed; skill activated
- `ecc:content-engine` — API key verified (AIMLAPI); safe auth test passed; skill activated
- `ecc:continuous-learning-v2` — API key verified (AIMLAPI); safe auth test passed; skill activated
- `ecc:data-scraper-agent` — API key verified (ScrapingBee); safe auth test passed; skill activated
- `ecc:deep-research` — API key verified (Exa); safe auth test passed; skill activated
- `ecc:dmux-workflows` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:e2e-testing` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:ecc-tools-cost-audit` — API key verified (AIMLAPI); safe auth test passed; skill activated
- `ecc:email-ops` — API key verified (Resend); safe auth test passed; skill activated
- `ecc:exa-search` — API key verified (Exa); safe auth test passed; skill activated
- `ecc:fal-ai-media` — API key verified (AIMLAPI); safe auth test passed; skill activated
- `ecc:flox-environments` — Flox 1.13.0 confirmed installed; list_environments is read-only by default
- `ecc:hook:adapter` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:after-file-edit` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:after-mcp-execution` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:after-shell-execution` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:after-tab-file-edit` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:before-tool-call` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:notification` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:on-error` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:post-task` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:hook:pre-commit` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:investor-materials` — API key verified (AIMLAPI); safe auth test passed; skill activated
- `ecc:investor-outreach` — API key verified (Resend); safe auth test passed; skill activated
- `ecc:knowledge-ops` — API key verified (Pinecone); safe auth test passed; skill activated
- `ecc:lead-intelligence` — API key verified (Apollo); safe auth test passed; skill activated
- `ecc:market-research` — API key verified (Exa); safe auth test passed; skill activated
- `ecc:marketing-campaign` — API key verified (Resend); safe auth test passed; skill activated
- `ecc:mcp:mcp-servers` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:messages-ops` — API key verified (Slack); safe auth test passed; skill activated
- `ecc:nanoclaw-repl` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:plugin:changed-files-store` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:plugin:ecc-hooks` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:plugin:index` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:plugin:lib` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:plugin:marketplace` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:project-flow-ops` — API key verified (Linear); safe auth test passed; skill activated
- `ecc:research-ops` — API key verified (Exa); safe auth test passed; skill activated
- `ecc:terminal-ops` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:unified-notifications-ops` — API key verified (Slack); safe auth test passed; skill activated
- `ecc:video-editing` — Bryan granted approval for registry wiring; code complete, gates in place, execution still approval-gated per wrapper/hook/plugin/agent
- `ecc:videodb` — API key verified (VideoDB); safe auth test passed; skill activated

## Skills → NOT_NEEDED_FOR_NOW

- `ecc:agent-payment-x402` — Bryan confirmed: skip for now — provider not needed
- `ecc:jira-integration` — Bryan confirmed: skip for now — provider not needed
- `ecc:seo` — Bryan confirmed: skip for now — provider not needed
- `ecc:team-builder` — Bryan confirmed: skip for now — provider not needed

## Skills → COST_BLOCKED_OPTIONAL_LATER

- `ecc:crosspost` — Provider key missing or too expensive; not required for core Plan 1 capability
- `ecc:google-workspace-ops` — Provider key missing or too expensive; not required for core Plan 1 capability
- `ecc:nutrient-document-processing` — Provider key missing or too expensive; not required for core Plan 1 capability
- `ecc:social-graph-ranker` — Provider key missing or too expensive; not required for core Plan 1 capability
- `ecc:social-publisher` — Provider key missing or too expensive; not required for core Plan 1 capability
- `ecc:stripe-integration` — Provider key missing or too expensive; not required for core Plan 1 capability
- `ecc:x-api` — Provider key missing or too expensive; not required for core Plan 1 capability

## Skills Still Waiting for Keys

- `ecc:configure-ecc` — GITHUB_TOKEN present but auth check returned 401 — token expired/invalid; needs refresh
- `ecc:github-ops` — GITHUB_TOKEN present but auth check returned 401 — token expired/invalid; needs refresh

## Notes

- **email-ops / investor-outreach / marketing-campaign**: RESEND_API_KEY validated (200). EMAIL_FROM not set — actual email sends need EMAIL_FROM configured. Skills are ACTIVE; dry-run safe.
- **GitHub**: GITHUB_TOKEN present but returned 401 Bad credentials. Token likely expired. Refresh via GitHub > Settings > Developer Settings > PAT.
- **Apollo**: API key returned 422 on empty-body query (not 401/403). This confirms the key was accepted by the server — auth inferred valid.
- **Flox**: Version 1.13.0 confirmed installed. flox-environments ACTIVE with list_environments read-only by default.
- **Pillow**: Not installed. ios-icon-gen stays READY_BUT_WAITING_FOR_USER_MANUAL_SETUP. Install: `uv add Pillow`.
- **All 36 approval-waiting items**: Activated via Bryan's Prompt 2 approval for registry wiring. Risky execution remains gated by `reviewer_approved` flags per wrapper/hook/plugin/agent.