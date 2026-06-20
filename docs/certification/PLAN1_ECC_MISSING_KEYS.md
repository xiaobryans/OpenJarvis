# Plan 1 ECC Missing Keys — API Key Requirements

**Sprint:** Plan 1 ECC Completion Sprint — Pre-Keys (Prompt 1)
**Status:** PLAN_1_ECC_PRE_KEYS_COMPLETION_ACCEPT_PENDING_REVIEW

All 35 API-key-dependent ECC skills are structurally complete.
Each entry below documents exactly what Bryan must provide in Prompt 2.

## Summary

| Metric | Count |
|--------|-------|
| Total API-key skills | 35 |
| Unique providers | 30 |
| Read-only risk | 17 |
| Write/action risk | 8 |
| Send risk | 8 |
| Financial risk | 2 |

## Key Requirements by Skill

### `ecc:exa-search`

| Field | Value |
|-------|-------|
| **Provider** | Exa |
| **Risk** | read_only |
| **Required keys** | `EXA_API_KEY` |
| **Optional keys** | `none` |
| **OAuth scopes** | `none` |
| **Account setup** | Sign up at exa.ai, generate API key from dashboard |
| **Exact blocker** | Missing EXA_API_KEY env var |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_exa_search_mocked` |
| **Live test** | `EXA_API_KEY=$EXA_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set EXA_API_KEY env var, then call catalog.get('ecc:exa-search') → update state to active |
| **Rollback** | Unset EXA_API_KEY; skill auto-disables via key presence check |
| **Completable with keys** | ✅ Yes |

### `ecc:fal-ai-media`

| Field | Value |
|-------|-------|
| **Provider** | fal.ai |
| **Risk** | action |
| **Required keys** | `FAL_API_KEY` |
| **Optional keys** | `none` |
| **OAuth scopes** | `none` |
| **Account setup** | Sign up at fal.ai, generate API key from dashboard |
| **Exact blocker** | Missing FAL_API_KEY env var |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_fal_ai_media_mocked` |
| **Live test** | `FAL_API_KEY=$FAL_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set FAL_API_KEY env var, enable skill in catalog |
| **Rollback** | Unset FAL_API_KEY; skill auto-disables |
| **Completable with keys** | ✅ Yes |

### `ecc:deep-research`

| Field | Value |
|-------|-------|
| **Provider** | Exa or Perplexity |
| **Risk** | read_only |
| **Required keys** | `EXA_API_KEY` |
| **Optional keys** | `PERPLEXITY_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Exa.ai account required; optional Perplexity account for deeper research |
| **Exact blocker** | Missing EXA_API_KEY (and optionally PERPLEXITY_API_KEY) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_deep_research_mocked` |
| **Live test** | `EXA_API_KEY=$EXA_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set EXA_API_KEY; skill becomes active |
| **Rollback** | Unset EXA_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:market-research`

| Field | Value |
|-------|-------|
| **Provider** | Exa + SERP API |
| **Risk** | read_only |
| **Required keys** | `EXA_API_KEY` |
| **Optional keys** | `SERP_API_KEY`, `GOOGLE_SEARCH_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Exa.ai account; optional SerpAPI account (serpapi.com) |
| **Exact blocker** | Missing EXA_API_KEY |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_market_research_mocked` |
| **Live test** | `EXA_API_KEY=$EXA_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set EXA_API_KEY; enable skill |
| **Rollback** | Unset EXA_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:data-scraper-agent`

| Field | Value |
|-------|-------|
| **Provider** | ScrapingBee or BrightData |
| **Risk** | read_only |
| **Required keys** | `SCRAPING_BEE_API_KEY` |
| **Optional keys** | `BRIGHTDATA_USERNAME`, `BRIGHTDATA_PASSWORD` |
| **OAuth scopes** | `none` |
| **Account setup** | ScrapingBee account at scrapingbee.com; or BrightData account |
| **Exact blocker** | Missing SCRAPING_BEE_API_KEY |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_data_scraper_mocked` |
| **Live test** | `SCRAPING_BEE_API_KEY=$SCRAPING_BEE_API_KEY uv run python -c "from openjarvis.ski...` |
| **Activation** | Set SCRAPING_BEE_API_KEY; enable skill |
| **Rollback** | Unset SCRAPING_BEE_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:social-publisher`

| Field | Value |
|-------|-------|
| **Provider** | Multiple social platforms |
| **Risk** | send |
| **Required keys** | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET` |
| **Optional keys** | `LINKEDIN_ACCESS_TOKEN`, `META_PAGE_ACCESS_TOKEN`, `INSTAGRAM_ACCESS_TOKEN` |
| **OAuth scopes** | `twitter.write`, `linkedin.share`, `meta.publish` |
| **Account setup** | Twitter Developer account (developer.twitter.com), LinkedIn app, Meta Business account |
| **Exact blocker** | Missing TWITTER_API_KEY + TWITTER_API_SECRET + access tokens |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_social_publisher_mocked` |
| **Live test** | `uv run python -c "from openjarvis.skills.ecc_completion import live_test_skill; ...` |
| **Activation** | Set social API keys; enable skill with dry_run=True first |
| **Rollback** | Unset social API keys; disable skill |
| **Completable with keys** | ✅ Yes |

### `ecc:email-ops`

| Field | Value |
|-------|-------|
| **Provider** | SMTP / Resend / SendGrid |
| **Risk** | send |
| **Required keys** | `EMAIL_FROM` |
| **Optional keys** | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `SMTP_PORT`, `RESEND_API_KEY`, `SENDGRID_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | One of: SMTP credentials, Resend account (resend.com), or SendGrid account |
| **Exact blocker** | Missing email provider credentials (SMTP or RESEND_API_KEY or SENDGRID_API_KEY) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_email_ops_mocked` |
| **Live test** | `RESEND_API_KEY=$RESEND_API_KEY EMAIL_FROM=$EMAIL_FROM uv run python -c "from ope...` |
| **Activation** | Set email provider keys; enable skill with dry_run=True first |
| **Rollback** | Unset email keys; disable skill |
| **Completable with keys** | ✅ Yes |

### `ecc:github-ops`

| Field | Value |
|-------|-------|
| **Provider** | GitHub |
| **Risk** | write |
| **Required keys** | `GITHUB_TOKEN` |
| **Optional keys** | `GITHUB_ORG`, `GITHUB_REPO` |
| **OAuth scopes** | `repo`, `workflow`, `issues:write`, `pull_requests:write` |
| **Account setup** | GitHub account; generate Personal Access Token or GitHub App token with write scopes |
| **Exact blocker** | Missing GITHUB_TOKEN with write scopes |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_github_ops_mocked` |
| **Live test** | `GITHUB_TOKEN=$GITHUB_TOKEN uv run python -c "from openjarvis.skills.ecc_completi...` |
| **Activation** | Set GITHUB_TOKEN; enable skill with read_only=True first |
| **Rollback** | Unset GITHUB_TOKEN; revoke token if needed |
| **Completable with keys** | ✅ Yes |

### `ecc:jira-integration`

| Field | Value |
|-------|-------|
| **Provider** | Atlassian Jira |
| **Risk** | write |
| **Required keys** | `JIRA_API_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL` |
| **Optional keys** | `JIRA_PROJECT_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Jira account; generate API token at id.atlassian.com/manage-profile/security/api-tokens |
| **Exact blocker** | Missing JIRA_API_TOKEN + JIRA_BASE_URL + JIRA_EMAIL |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_jira_integration_mocked` |
| **Live test** | `JIRA_API_TOKEN=$JIRA_API_TOKEN JIRA_BASE_URL=$JIRA_BASE_URL JIRA_EMAIL=$JIRA_EMA...` |
| **Activation** | Set Jira env vars; enable skill |
| **Rollback** | Unset Jira env vars |
| **Completable with keys** | ✅ Yes |

### `ecc:google-workspace-ops`

| Field | Value |
|-------|-------|
| **Provider** | Google Workspace |
| **Risk** | read_only |
| **Required keys** | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` |
| **Optional keys** | `GOOGLE_SCOPES`, `GOOGLE_USER_EMAIL` |
| **OAuth scopes** | `gmail.readonly`, `calendar.events`, `drive.file`, `docs.readonly` |
| **Account setup** | Google Cloud Console project; OAuth 2.0 credentials; complete consent screen; obtain refresh token |
| **Exact blocker** | Missing GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GOOGLE_REFRESH_TOKEN + OAuth browser consent |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_google_workspace_mocked` |
| **Live test** | `GOOGLE_CLIENT_ID=$GC_ID GOOGLE_CLIENT_SECRET=$GC_SECRET GOOGLE_REFRESH_TOKEN=$GC...` |
| **Activation** | Set Google env vars; requires OAuth browser flow to obtain refresh token |
| **Rollback** | Revoke refresh token at myaccount.google.com/permissions |
| **Completable with keys** | ✅ Yes |
| **Remaining blockers** | Requires OAuth browser consent screen — cannot automate without browser access |

### `ecc:messages-ops`

| Field | Value |
|-------|-------|
| **Provider** | Slack / Telegram / Discord |
| **Risk** | send |
| **Required keys** | `SLACK_BOT_TOKEN` |
| **Optional keys** | `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `SLACK_SIGNING_SECRET` |
| **OAuth scopes** | `chat:write`, `channels:read` |
| **Account setup** | Slack workspace → create app at api.slack.com; or Telegram BotFather; or Discord Developer Portal |
| **Exact blocker** | Missing SLACK_BOT_TOKEN (or TELEGRAM_BOT_TOKEN / DISCORD_BOT_TOKEN) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_messages_ops_mocked` |
| **Live test** | `SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN uv run python -c "from openjarvis.skills.ecc_co...` |
| **Activation** | Set SLACK_BOT_TOKEN; enable skill with dry_run=True first |
| **Rollback** | Revoke bot token from Slack app settings |
| **Completable with keys** | ✅ Yes |

### `ecc:x-api`

| Field | Value |
|-------|-------|
| **Provider** | X (Twitter) |
| **Risk** | send |
| **Required keys** | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` |
| **Optional keys** | `X_BEARER_TOKEN` |
| **OAuth scopes** | `tweet.read`, `tweet.write`, `users.read` |
| **Account setup** | X Developer account at developer.twitter.com; create app; apply for elevated access for write |
| **Exact blocker** | Missing X_API_KEY + X_API_SECRET + X_ACCESS_TOKEN + X_ACCESS_TOKEN_SECRET |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_x_api_mocked` |
| **Live test** | `X_API_KEY=$X_API_KEY X_API_SECRET=$X_API_SECRET X_ACCESS_TOKEN=$X_AT X_ACCESS_TO...` |
| **Activation** | Set all X env vars; enable skill with dry_run=True |
| **Rollback** | Revoke access token from X Developer Portal |
| **Completable with keys** | ✅ Yes |

### `ecc:unified-notifications-ops`

| Field | Value |
|-------|-------|
| **Provider** | Multiple (Slack / Telegram / Email / PagerDuty) |
| **Risk** | send |
| **Required keys** | `NOTIFICATION_PROVIDER` |
| **Optional keys** | `SLACK_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, `RESEND_API_KEY`, `PAGERDUTY_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Set NOTIFICATION_PROVIDER=slack|telegram|email|pagerduty; provide corresponding key |
| **Exact blocker** | Missing NOTIFICATION_PROVIDER + provider-specific key |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_unified_notifications_mocked` |
| **Live test** | `NOTIFICATION_PROVIDER=slack SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN uv run python -c "f...` |
| **Activation** | Set NOTIFICATION_PROVIDER + matching key; enable skill |
| **Rollback** | Unset NOTIFICATION_PROVIDER |
| **Completable with keys** | ✅ Yes |

### `ecc:lead-intelligence`

| Field | Value |
|-------|-------|
| **Provider** | Apollo.io or Clearbit |
| **Risk** | read_only |
| **Required keys** | `APOLLO_API_KEY` |
| **Optional keys** | `CLEARBIT_API_KEY`, `HUNTER_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Apollo.io account at apollo.io; generate API key from settings |
| **Exact blocker** | Missing APOLLO_API_KEY (or CLEARBIT_API_KEY) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_lead_intelligence_mocked` |
| **Live test** | `APOLLO_API_KEY=$APOLLO_API_KEY uv run python -c "from openjarvis.skills.ecc_comp...` |
| **Activation** | Set APOLLO_API_KEY; enable skill |
| **Rollback** | Unset APOLLO_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:investor-outreach`

| Field | Value |
|-------|-------|
| **Provider** | Email (Resend/SendGrid) + CRM |
| **Risk** | send |
| **Required keys** | `EMAIL_FROM`, `RESEND_API_KEY` |
| **Optional keys** | `CRM_API_KEY`, `AIRTABLE_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Resend account (resend.com) + optional Airtable or CRM account |
| **Exact blocker** | Missing RESEND_API_KEY + EMAIL_FROM |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_investor_outreach_mocked` |
| **Live test** | `RESEND_API_KEY=$RESEND_API_KEY EMAIL_FROM=$EMAIL_FROM uv run python -c "from ope...` |
| **Activation** | Set RESEND_API_KEY + EMAIL_FROM; enable with dry_run=True first |
| **Rollback** | Unset RESEND_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:crosspost`

| Field | Value |
|-------|-------|
| **Provider** | Multiple social platforms |
| **Risk** | send |
| **Required keys** | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET` |
| **Optional keys** | `LINKEDIN_ACCESS_TOKEN`, `META_PAGE_ACCESS_TOKEN` |
| **OAuth scopes** | `twitter.write`, `linkedin.share` |
| **Account setup** | Twitter Developer account; LinkedIn OAuth; optionally Meta Business |
| **Exact blocker** | Missing Twitter API keys (minimum); optionally LinkedIn + Meta tokens |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_crosspost_mocked` |
| **Live test** | `uv run python -c "from openjarvis.skills.ecc_completion import live_test_skill; ...` |
| **Activation** | Set Twitter API keys; enable with dry_run=True |
| **Rollback** | Unset API keys |
| **Completable with keys** | ✅ Yes |

### `ecc:videodb`

| Field | Value |
|-------|-------|
| **Provider** | VideoDB |
| **Risk** | read_only |
| **Required keys** | `VIDEODB_API_KEY` |
| **Optional keys** | `none` |
| **OAuth scopes** | `none` |
| **Account setup** | VideoDB account at videodb.io; generate API key |
| **Exact blocker** | Missing VIDEODB_API_KEY |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_videodb_mocked` |
| **Live test** | `VIDEODB_API_KEY=$VIDEODB_API_KEY uv run python -c "from openjarvis.skills.ecc_co...` |
| **Activation** | Set VIDEODB_API_KEY; enable skill |
| **Rollback** | Unset VIDEODB_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:ecc-tools-cost-audit`

| Field | Value |
|-------|-------|
| **Provider** | Anthropic / OpenAI / OpenRouter |
| **Risk** | read_only |
| **Required keys** | `ANTHROPIC_API_KEY` |
| **Optional keys** | `OPENAI_API_KEY`, `OPENROUTER_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Anthropic account; or OpenRouter account (already configured if OPENROUTER_API_KEY is set) |
| **Exact blocker** | Missing ANTHROPIC_API_KEY (or OPENROUTER_API_KEY if already configured) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_ecc_tools_cost_audit_mocked` |
| **Live test** | `ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY uv run python -c "from openjarvis.skills.ec...` |
| **Activation** | Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY; enable skill |
| **Rollback** | Unset API key |
| **Completable with keys** | ✅ Yes |

### `ecc:configure-ecc`

| Field | Value |
|-------|-------|
| **Provider** | GitHub |
| **Risk** | write |
| **Required keys** | `GITHUB_TOKEN` |
| **Optional keys** | `ECC_REPO_PATH` |
| **OAuth scopes** | `repo:write` |
| **Account setup** | GitHub PAT with write access to ECC config repo (affaan-m/ECC or Bryan's fork) |
| **Exact blocker** | Missing GITHUB_TOKEN with write scopes to ECC repo |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_configure_ecc_mocked` |
| **Live test** | `GITHUB_TOKEN=$GITHUB_TOKEN uv run python -c "from openjarvis.skills.ecc_completi...` |
| **Activation** | Set GITHUB_TOKEN with write scopes; enable skill |
| **Rollback** | Revoke token; revert ECC config changes via git revert |
| **Completable with keys** | ✅ Yes |

### `ecc:article-writing`

| Field | Value |
|-------|-------|
| **Provider** | OpenRouter / Anthropic / OpenAI |
| **Risk** | read_only |
| **Required keys** | `(uses existing LLM config)` |
| **Optional keys** | `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Uses existing LLM configuration; likely already active via OPENROUTER_API_KEY |
| **Exact blocker** | Requires LLM API key (may already be configured via OPENROUTER_API_KEY) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_article_writing_mocked` |
| **Live test** | `uv run python -c "from openjarvis.skills.ecc_completion import live_test_skill; ...` |
| **Activation** | If OPENROUTER_API_KEY is set, activate immediately; otherwise set ANTHROPIC_API_KEY |
| **Rollback** | Disable skill in catalog |
| **Completable with keys** | ✅ Yes |

### `ecc:content-engine`

| Field | Value |
|-------|-------|
| **Provider** | LLM + optional CMS |
| **Risk** | write |
| **Required keys** | `OPENROUTER_API_KEY` |
| **Optional keys** | `CMS_API_KEY`, `CONTENTFUL_API_KEY`, `NOTION_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | LLM API (OpenRouter); optional CMS for publishing |
| **Exact blocker** | Requires OPENROUTER_API_KEY (may already be configured) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_content_engine_mocked` |
| **Live test** | `uv run python -c "from openjarvis.skills.ecc_completion import live_test_skill; ...` |
| **Activation** | If OPENROUTER_API_KEY set, enable skill; add CMS key for publishing |
| **Rollback** | Disable skill in catalog |
| **Completable with keys** | ✅ Yes |

### `ecc:brand-discovery`

| Field | Value |
|-------|-------|
| **Provider** | Exa or SERP API |
| **Risk** | read_only |
| **Required keys** | `EXA_API_KEY` |
| **Optional keys** | `SERP_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Exa.ai account |
| **Exact blocker** | Missing EXA_API_KEY |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_brand_discovery_mocked` |
| **Live test** | `EXA_API_KEY=$EXA_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set EXA_API_KEY; enable skill |
| **Rollback** | Unset EXA_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:brand-voice`

| Field | Value |
|-------|-------|
| **Provider** | OpenRouter / Anthropic |
| **Risk** | read_only |
| **Required keys** | `(uses existing LLM config)` |
| **Optional keys** | `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Uses existing LLM configuration |
| **Exact blocker** | Requires LLM API key (may already be configured) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_brand_voice_mocked` |
| **Live test** | `uv run python -c "from openjarvis.skills.ecc_completion import live_test_skill; ...` |
| **Activation** | If OPENROUTER_API_KEY set, activate immediately |
| **Rollback** | Disable skill |
| **Completable with keys** | ✅ Yes |

### `ecc:competitive-platform-analysis`

| Field | Value |
|-------|-------|
| **Provider** | Exa |
| **Risk** | read_only |
| **Required keys** | `EXA_API_KEY` |
| **Optional keys** | `SERP_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Exa.ai account |
| **Exact blocker** | Missing EXA_API_KEY |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_competitive_platform_mocked` |
| **Live test** | `EXA_API_KEY=$EXA_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set EXA_API_KEY; enable skill |
| **Rollback** | Unset EXA_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:competitive-report-structure`

| Field | Value |
|-------|-------|
| **Provider** | Exa |
| **Risk** | read_only |
| **Required keys** | `EXA_API_KEY` |
| **Optional keys** | `none` |
| **OAuth scopes** | `none` |
| **Account setup** | Exa.ai account |
| **Exact blocker** | Missing EXA_API_KEY |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_competitive_report_mocked` |
| **Live test** | `EXA_API_KEY=$EXA_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set EXA_API_KEY; enable skill |
| **Rollback** | Unset EXA_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:investor-materials`

| Field | Value |
|-------|-------|
| **Provider** | LLM |
| **Risk** | read_only |
| **Required keys** | `(uses existing LLM config)` |
| **Optional keys** | `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Uses existing LLM configuration |
| **Exact blocker** | Requires LLM API key (may already be configured via OPENROUTER_API_KEY) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_investor_materials_mocked` |
| **Live test** | `uv run python -c "from openjarvis.skills.ecc_completion import live_test_skill; ...` |
| **Activation** | If OPENROUTER_API_KEY set, activate immediately |
| **Rollback** | Disable skill |
| **Completable with keys** | ✅ Yes |

### `ecc:marketing-campaign`

| Field | Value |
|-------|-------|
| **Provider** | Email + Social APIs |
| **Risk** | send |
| **Required keys** | `RESEND_API_KEY`, `EMAIL_FROM` |
| **Optional keys** | `TWITTER_API_KEY`, `LINKEDIN_ACCESS_TOKEN`, `META_PAGE_ACCESS_TOKEN` |
| **OAuth scopes** | `email.send`, `twitter.write` |
| **Account setup** | Resend account; Twitter Developer account; optional LinkedIn/Meta |
| **Exact blocker** | Missing RESEND_API_KEY + EMAIL_FROM (minimum); optionally social API keys |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_marketing_campaign_mocked` |
| **Live test** | `RESEND_API_KEY=$RESEND_API_KEY EMAIL_FROM=$EMAIL_FROM uv run python -c "from ope...` |
| **Activation** | Set email keys; enable with dry_run=True first |
| **Rollback** | Unset email keys |
| **Completable with keys** | ✅ Yes |

### `ecc:seo`

| Field | Value |
|-------|-------|
| **Provider** | Ahrefs or SEMrush or Moz |
| **Risk** | read_only |
| **Required keys** | `AHREFS_API_KEY` |
| **Optional keys** | `SEMRUSH_API_KEY`, `MOZ_ACCESS_ID`, `MOZ_SECRET_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Ahrefs account (ahrefs.com); or SEMrush; or Moz Pro |
| **Exact blocker** | Missing AHREFS_API_KEY (or SEMRUSH_API_KEY or MOZ keys) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_seo_mocked` |
| **Live test** | `AHREFS_API_KEY=$AHREFS_API_KEY uv run python -c "from openjarvis.skills.ecc_comp...` |
| **Activation** | Set AHREFS_API_KEY; enable skill |
| **Rollback** | Unset API key |
| **Completable with keys** | ✅ Yes |

### `ecc:agent-payment-x402`

| Field | Value |
|-------|-------|
| **Provider** | X402 Protocol / Payment Provider |
| **Risk** | financial |
| **Required keys** | `X402_PAYMENT_KEY` |
| **Optional keys** | `STRIPE_API_KEY`, `COINBASE_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | X402 protocol account; or Stripe account with payment intents enabled |
| **Exact blocker** | Missing X402_PAYMENT_KEY; financial risk requires Bryan's explicit approval |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_agent_payment_mocked` |
| **Live test** | `X402_PAYMENT_KEY=$X402_PAYMENT_KEY uv run python -c "from openjarvis.skills.ecc_...` |
| **Activation** | Set X402_PAYMENT_KEY + Bryan explicit approval + dry_run test first |
| **Rollback** | Revoke X402 payment key; disable skill immediately |
| **Completable with keys** | ✅ Yes |
| **Remaining blockers** | Financial risk — requires Bryan explicit approval even with keys |

### `ecc:social-graph-ranker`

| Field | Value |
|-------|-------|
| **Provider** | Social Media APIs |
| **Risk** | read_only |
| **Required keys** | `TWITTER_BEARER_TOKEN` |
| **Optional keys** | `LINKEDIN_ACCESS_TOKEN`, `X_API_KEY` |
| **OAuth scopes** | `twitter.read` |
| **Account setup** | Twitter Developer account; generate bearer token |
| **Exact blocker** | Missing TWITTER_BEARER_TOKEN |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_social_graph_ranker_mocked` |
| **Live test** | `TWITTER_BEARER_TOKEN=$TBT uv run python -c "from openjarvis.skills.ecc_completio...` |
| **Activation** | Set TWITTER_BEARER_TOKEN; enable skill |
| **Rollback** | Revoke bearer token |
| **Completable with keys** | ✅ Yes |

### `ecc:research-ops`

| Field | Value |
|-------|-------|
| **Provider** | Exa or Perplexity |
| **Risk** | read_only |
| **Required keys** | `EXA_API_KEY` |
| **Optional keys** | `PERPLEXITY_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Exa.ai account |
| **Exact blocker** | Missing EXA_API_KEY |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_research_ops_mocked` |
| **Live test** | `EXA_API_KEY=$EXA_API_KEY uv run python -c "from openjarvis.skills.ecc_completion...` |
| **Activation** | Set EXA_API_KEY; enable skill |
| **Rollback** | Unset EXA_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:knowledge-ops`

| Field | Value |
|-------|-------|
| **Provider** | Pinecone or Weaviate or Qdrant |
| **Risk** | write |
| **Required keys** | `PINECONE_API_KEY` |
| **Optional keys** | `PINECONE_ENV`, `WEAVIATE_URL`, `WEAVIATE_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Pinecone account at pinecone.io; or Weaviate Cloud; or Qdrant Cloud |
| **Exact blocker** | Missing PINECONE_API_KEY (or WEAVIATE_URL + WEAVIATE_API_KEY or QDRANT_URL + QDRANT_API_KEY) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_knowledge_ops_mocked` |
| **Live test** | `PINECONE_API_KEY=$PINECONE_API_KEY uv run python -c "from openjarvis.skills.ecc_...` |
| **Activation** | Set PINECONE_API_KEY + PINECONE_ENV; enable skill |
| **Rollback** | Unset PINECONE_API_KEY; delete Pinecone index if created |
| **Completable with keys** | ✅ Yes |

### `ecc:project-flow-ops`

| Field | Value |
|-------|-------|
| **Provider** | Linear or Jira |
| **Risk** | write |
| **Required keys** | `LINEAR_API_KEY` |
| **Optional keys** | `JIRA_API_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL` |
| **OAuth scopes** | `none` |
| **Account setup** | Linear account at linear.app; generate API key from Settings → API |
| **Exact blocker** | Missing LINEAR_API_KEY (or JIRA_API_TOKEN + JIRA_BASE_URL + JIRA_EMAIL) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_project_flow_ops_mocked` |
| **Live test** | `LINEAR_API_KEY=$LINEAR_API_KEY uv run python -c "from openjarvis.skills.ecc_comp...` |
| **Activation** | Set LINEAR_API_KEY; enable skill |
| **Rollback** | Unset LINEAR_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:team-builder`

| Field | Value |
|-------|-------|
| **Provider** | Greenhouse or Workday |
| **Risk** | write |
| **Required keys** | `GREENHOUSE_API_KEY` |
| **Optional keys** | `WORKDAY_API_KEY`, `LEVER_API_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Greenhouse account at greenhouse.io; generate Harvest API key |
| **Exact blocker** | Missing GREENHOUSE_API_KEY (or WORKDAY_API_KEY or LEVER_API_KEY) |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_team_builder_mocked` |
| **Live test** | `GREENHOUSE_API_KEY=$GREENHOUSE_API_KEY uv run python -c "from openjarvis.skills....` |
| **Activation** | Set GREENHOUSE_API_KEY; enable skill |
| **Rollback** | Unset GREENHOUSE_API_KEY |
| **Completable with keys** | ✅ Yes |

### `ecc:stripe-integration`

| Field | Value |
|-------|-------|
| **Provider** | Stripe |
| **Risk** | financial |
| **Required keys** | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` |
| **Optional keys** | `STRIPE_PRICE_ID`, `STRIPE_PUBLISHABLE_KEY` |
| **OAuth scopes** | `none` |
| **Account setup** | Stripe account at stripe.com; generate API keys from Dashboard → Developers → API Keys |
| **Exact blocker** | Missing STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET; financial risk requires Bryan approval |
| **Mocked test** | `uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_stripe_integration_mocked` |
| **Live test** | `STRIPE_API_KEY=$STRIPE_API_KEY uv run python -c "from openjarvis.skills.ecc_comp...` |
| **Activation** | Set STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET; use test mode first (sk_test_...) |
| **Rollback** | Delete webhook; revoke API key from Stripe dashboard |
| **Completable with keys** | ✅ Yes |
| **Remaining blockers** | Financial risk — use Stripe test mode keys first (sk_test_...) |

## Prompt 2 — What Bryan Must Provide

To run live tests and activate all 35 provider skills, Bryan must provide:

1. **exa-search** → `EXA_API_KEY`
2. **fal-ai-media** → `FAL_API_KEY`
3. **deep-research** → `EXA_API_KEY`
4. **market-research** → `EXA_API_KEY`
5. **data-scraper-agent** → `SCRAPING_BEE_API_KEY`
...

See `build/reports/plan1_ecc_missing_keys.json` for the complete machine-readable list.

## Agents Waiting for Approval

11 planning/review agents are `READY_BUT_WAITING_FOR_APPROVAL`.
No API key needed — Bryan must approve Jarvis agent routing wiring:

- `ecc:agent:architect`, `ecc:agent:code-reviewer`, `ecc:agent:doc-updater`
- `ecc:agent:planner`, `ecc:agent:reviewer`, `ecc:agent:security-reviewer`
- `ecc:agent:spec-miner`, `ecc:agent:tdd-guide`, `ecc:agent:refactor-cleaner`
- `ecc:agent:build-error-resolver`, `ecc:agent:explorer`

Activation route: wire Jarvis agent routing framework → Bryan approves → set `reviewer_approved=True`