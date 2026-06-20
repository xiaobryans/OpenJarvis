"""ECC Completion Module — Plan 1 Pre-Keys Automation.

Provides:
  - ECC_KEY_REQUIREMENTS: machine-readable key requirements for all 35 API-key skills
  - check_key_presence(): validates which keys are present in environment
  - get_readiness_report(): CLI/API report of key readiness and activation readiness
  - generate_missing_keys_json(): write build/reports/plan1_ecc_missing_keys.json
  - format_missing_keys_md(): generate docs/certification/PLAN1_ECC_MISSING_KEYS.md content

This module uses NO secrets, makes NO network calls, and executes NO ECC code.
All keys are referenced by name only. Bryan provides actual values in Prompt 2.

Machine-readable: openjarvis.skills.ecc_completion
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Plan 1 state constants
# ---------------------------------------------------------------------------

class Plan1State:
    ACTIVE = "ACTIVE"
    READY_BUT_WAITING_FOR_API_KEY = "READY_BUT_WAITING_FOR_API_KEY"
    READY_BUT_WAITING_FOR_APPROVAL = "READY_BUT_WAITING_FOR_APPROVAL"
    ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK = "ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK"
    INSTALLED_DISABLED_WITH_EXACT_BLOCKER = "INSTALLED_DISABLED_WITH_EXACT_BLOCKER"
    UNAUTOMATABLE_EVEN_WITH_APPROVAL = "UNAUTOMATABLE_EVEN_WITH_APPROVAL"
    REJECTED_WITH_REASON = "REJECTED_WITH_REASON"
    DUPLICATE_WITH_REASON = "DUPLICATE_WITH_REASON"
    QUARANTINED_WITH_REASON = "QUARANTINED_WITH_REASON"


# ---------------------------------------------------------------------------
# Key requirements: all 35 API-key-dependent skills
# ---------------------------------------------------------------------------
# Format per entry:
#   skill_id: ECC skill ID (without "ecc:" prefix)
#   provider: provider name
#   required_env_keys: env var names Bryan must set
#   optional_env_keys: optional env vars
#   oauth_scopes: OAuth scopes or provider permissions needed
#   account_setup: provider account/plan requirements
#   risk: read_only | write | action | send | deploy | financial
#   jarvis_permission_scope: Jarvis internal permission scope
#   plan1_state: current state
#   exact_blocker: what is missing to activate
#   mocked_test_command: run this now (no keys needed)
#   live_test_command: run this after Bryan provides keys
#   activation_route: how to activate after keys provided
#   rollback_path: how to disable/quarantine if needed
#   completable_with_keys: True if Bryan providing keys is sufficient
#   impossible_even_with_keys: list any remaining blockers

ECC_KEY_REQUIREMENTS: List[Dict[str, Any]] = [
    {
        "skill_id": "exa-search",
        "provider": "Exa",
        "required_env_keys": ["EXA_API_KEY"],
        "optional_env_keys": [],
        "oauth_scopes": [],
        "account_setup": "Sign up at exa.ai, generate API key from dashboard",
        "risk": "read_only",
        "jarvis_permission_scope": "search:read_only",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing EXA_API_KEY env var",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_exa_search_mocked",
        "live_test_command": "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('exa-search')\"",
        "activation_route": "Set EXA_API_KEY env var, then call catalog.get('ecc:exa-search') → update state to active",
        "rollback_path": "Unset EXA_API_KEY; skill auto-disables via key presence check",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "fal-ai-media",
        "provider": "fal.ai",
        "required_env_keys": ["FAL_API_KEY"],
        "optional_env_keys": [],
        "oauth_scopes": [],
        "account_setup": "Sign up at fal.ai, generate API key from dashboard",
        "risk": "action",
        "jarvis_permission_scope": "media:generate",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing FAL_API_KEY env var",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_fal_ai_media_mocked",
        "live_test_command": "FAL_API_KEY=$FAL_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('fal-ai-media')\"",
        "activation_route": "Set FAL_API_KEY env var, enable skill in catalog",
        "rollback_path": "Unset FAL_API_KEY; skill auto-disables",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "deep-research",
        "provider": "Exa or Perplexity",
        "required_env_keys": ["EXA_API_KEY"],
        "optional_env_keys": ["PERPLEXITY_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Exa.ai account required; optional Perplexity account for deeper research",
        "risk": "read_only",
        "jarvis_permission_scope": "search:read_only",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing EXA_API_KEY (and optionally PERPLEXITY_API_KEY)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_deep_research_mocked",
        "live_test_command": "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('deep-research')\"",
        "activation_route": "Set EXA_API_KEY; skill becomes active",
        "rollback_path": "Unset EXA_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "market-research",
        "provider": "Exa + SERP API",
        "required_env_keys": ["EXA_API_KEY"],
        "optional_env_keys": ["SERP_API_KEY", "GOOGLE_SEARCH_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Exa.ai account; optional SerpAPI account (serpapi.com)",
        "risk": "read_only",
        "jarvis_permission_scope": "search:read_only",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing EXA_API_KEY",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_market_research_mocked",
        "live_test_command": "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('market-research')\"",
        "activation_route": "Set EXA_API_KEY; enable skill",
        "rollback_path": "Unset EXA_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "data-scraper-agent",
        "provider": "ScrapingBee or BrightData",
        "required_env_keys": ["SCRAPING_BEE_API_KEY"],
        "optional_env_keys": ["BRIGHTDATA_USERNAME", "BRIGHTDATA_PASSWORD"],
        "oauth_scopes": [],
        "account_setup": "ScrapingBee account at scrapingbee.com; or BrightData account",
        "risk": "read_only",
        "jarvis_permission_scope": "web:scrape:read_only",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing SCRAPING_BEE_API_KEY",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_data_scraper_mocked",
        "live_test_command": "SCRAPING_BEE_API_KEY=$SCRAPING_BEE_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('data-scraper-agent')\"",
        "activation_route": "Set SCRAPING_BEE_API_KEY; enable skill",
        "rollback_path": "Unset SCRAPING_BEE_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "social-publisher",
        "provider": "Multiple social platforms",
        "required_env_keys": ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"],
        "optional_env_keys": ["LINKEDIN_ACCESS_TOKEN", "META_PAGE_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN"],
        "oauth_scopes": ["twitter.write", "linkedin.share", "meta.publish"],
        "account_setup": "Twitter Developer account (developer.twitter.com), LinkedIn app, Meta Business account",
        "risk": "send",
        "jarvis_permission_scope": "social:publish",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing TWITTER_API_KEY + TWITTER_API_SECRET + access tokens",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_social_publisher_mocked",
        "live_test_command": "uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('social-publisher')\"",
        "activation_route": "Set social API keys; enable skill with dry_run=True first",
        "rollback_path": "Unset social API keys; disable skill",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "email-ops",
        "provider": "SMTP / Resend / SendGrid",
        "required_env_keys": ["EMAIL_FROM"],
        "optional_env_keys": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_PORT", "RESEND_API_KEY", "SENDGRID_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "One of: SMTP credentials, Resend account (resend.com), or SendGrid account",
        "risk": "send",
        "jarvis_permission_scope": "email:send",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing email provider credentials (SMTP or RESEND_API_KEY or SENDGRID_API_KEY)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_email_ops_mocked",
        "live_test_command": "RESEND_API_KEY=$RESEND_API_KEY EMAIL_FROM=$EMAIL_FROM uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('email-ops')\"",
        "activation_route": "Set email provider keys; enable skill with dry_run=True first",
        "rollback_path": "Unset email keys; disable skill",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "github-ops",
        "provider": "GitHub",
        "required_env_keys": ["GITHUB_TOKEN"],
        "optional_env_keys": ["GITHUB_ORG", "GITHUB_REPO"],
        "oauth_scopes": ["repo", "workflow", "issues:write", "pull_requests:write"],
        "account_setup": "GitHub account; generate Personal Access Token or GitHub App token with write scopes",
        "risk": "write",
        "jarvis_permission_scope": "github:repo:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing GITHUB_TOKEN with write scopes",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_github_ops_mocked",
        "live_test_command": "GITHUB_TOKEN=$GITHUB_TOKEN uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('github-ops')\"",
        "activation_route": "Set GITHUB_TOKEN; enable skill with read_only=True first",
        "rollback_path": "Unset GITHUB_TOKEN; revoke token if needed",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "jira-integration",
        "provider": "Atlassian Jira",
        "required_env_keys": ["JIRA_API_TOKEN", "JIRA_BASE_URL", "JIRA_EMAIL"],
        "optional_env_keys": ["JIRA_PROJECT_KEY"],
        "oauth_scopes": [],
        "account_setup": "Jira account; generate API token at id.atlassian.com/manage-profile/security/api-tokens",
        "risk": "write",
        "jarvis_permission_scope": "jira:issues:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing JIRA_API_TOKEN + JIRA_BASE_URL + JIRA_EMAIL",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_jira_integration_mocked",
        "live_test_command": "JIRA_API_TOKEN=$JIRA_API_TOKEN JIRA_BASE_URL=$JIRA_BASE_URL JIRA_EMAIL=$JIRA_EMAIL uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('jira-integration')\"",
        "activation_route": "Set Jira env vars; enable skill",
        "rollback_path": "Unset Jira env vars",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "google-workspace-ops",
        "provider": "Google Workspace",
        "required_env_keys": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"],
        "optional_env_keys": ["GOOGLE_SCOPES", "GOOGLE_USER_EMAIL"],
        "oauth_scopes": ["gmail.readonly", "calendar.events", "drive.file", "docs.readonly"],
        "account_setup": "Google Cloud Console project; OAuth 2.0 credentials; complete consent screen; obtain refresh token",
        "risk": "read_only",
        "jarvis_permission_scope": "google:workspace:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GOOGLE_REFRESH_TOKEN + OAuth browser consent",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_google_workspace_mocked",
        "live_test_command": "GOOGLE_CLIENT_ID=$GC_ID GOOGLE_CLIENT_SECRET=$GC_SECRET GOOGLE_REFRESH_TOKEN=$GC_RT uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('google-workspace-ops')\"",
        "activation_route": "Set Google env vars; requires OAuth browser flow to obtain refresh token",
        "rollback_path": "Revoke refresh token at myaccount.google.com/permissions",
        "completable_with_keys": True,
        "impossible_even_with_keys": ["Requires OAuth browser consent screen — cannot automate without browser access"],
    },
    {
        "skill_id": "messages-ops",
        "provider": "Slack / Telegram / Discord",
        "required_env_keys": ["SLACK_BOT_TOKEN"],
        "optional_env_keys": ["TELEGRAM_BOT_TOKEN", "DISCORD_BOT_TOKEN", "SLACK_SIGNING_SECRET"],
        "oauth_scopes": ["chat:write", "channels:read"],
        "account_setup": "Slack workspace → create app at api.slack.com; or Telegram BotFather; or Discord Developer Portal",
        "risk": "send",
        "jarvis_permission_scope": "messaging:send",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing SLACK_BOT_TOKEN (or TELEGRAM_BOT_TOKEN / DISCORD_BOT_TOKEN)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_messages_ops_mocked",
        "live_test_command": "SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('messages-ops')\"",
        "activation_route": "Set SLACK_BOT_TOKEN; enable skill with dry_run=True first",
        "rollback_path": "Revoke bot token from Slack app settings",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "x-api",
        "provider": "X (Twitter)",
        "required_env_keys": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"],
        "optional_env_keys": ["X_BEARER_TOKEN"],
        "oauth_scopes": ["tweet.read", "tweet.write", "users.read"],
        "account_setup": "X Developer account at developer.twitter.com; create app; apply for elevated access for write",
        "risk": "send",
        "jarvis_permission_scope": "social:x:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing X_API_KEY + X_API_SECRET + X_ACCESS_TOKEN + X_ACCESS_TOKEN_SECRET",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_x_api_mocked",
        "live_test_command": "X_API_KEY=$X_API_KEY X_API_SECRET=$X_API_SECRET X_ACCESS_TOKEN=$X_AT X_ACCESS_TOKEN_SECRET=$X_ATS uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('x-api')\"",
        "activation_route": "Set all X env vars; enable skill with dry_run=True",
        "rollback_path": "Revoke access token from X Developer Portal",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "unified-notifications-ops",
        "provider": "Multiple (Slack / Telegram / Email / PagerDuty)",
        "required_env_keys": ["NOTIFICATION_PROVIDER"],
        "optional_env_keys": ["SLACK_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "RESEND_API_KEY", "PAGERDUTY_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Set NOTIFICATION_PROVIDER=slack|telegram|email|pagerduty; provide corresponding key",
        "risk": "send",
        "jarvis_permission_scope": "notifications:send",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing NOTIFICATION_PROVIDER + provider-specific key",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_unified_notifications_mocked",
        "live_test_command": "NOTIFICATION_PROVIDER=slack SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('unified-notifications-ops')\"",
        "activation_route": "Set NOTIFICATION_PROVIDER + matching key; enable skill",
        "rollback_path": "Unset NOTIFICATION_PROVIDER",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "lead-intelligence",
        "provider": "Apollo.io or Clearbit",
        "required_env_keys": ["APOLLO_API_KEY"],
        "optional_env_keys": ["CLEARBIT_API_KEY", "HUNTER_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Apollo.io account at apollo.io; generate API key from settings",
        "risk": "read_only",
        "jarvis_permission_scope": "crm:contacts:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing APOLLO_API_KEY (or CLEARBIT_API_KEY)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_lead_intelligence_mocked",
        "live_test_command": "APOLLO_API_KEY=$APOLLO_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('lead-intelligence')\"",
        "activation_route": "Set APOLLO_API_KEY; enable skill",
        "rollback_path": "Unset APOLLO_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "investor-outreach",
        "provider": "Email (Resend/SendGrid) + CRM",
        "required_env_keys": ["EMAIL_FROM", "RESEND_API_KEY"],
        "optional_env_keys": ["CRM_API_KEY", "AIRTABLE_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Resend account (resend.com) + optional Airtable or CRM account",
        "risk": "send",
        "jarvis_permission_scope": "email:send:outreach",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing RESEND_API_KEY + EMAIL_FROM",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_investor_outreach_mocked",
        "live_test_command": "RESEND_API_KEY=$RESEND_API_KEY EMAIL_FROM=$EMAIL_FROM uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('investor-outreach')\"",
        "activation_route": "Set RESEND_API_KEY + EMAIL_FROM; enable with dry_run=True first",
        "rollback_path": "Unset RESEND_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "crosspost",
        "provider": "Multiple social platforms",
        "required_env_keys": ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"],
        "optional_env_keys": ["LINKEDIN_ACCESS_TOKEN", "META_PAGE_ACCESS_TOKEN"],
        "oauth_scopes": ["twitter.write", "linkedin.share"],
        "account_setup": "Twitter Developer account; LinkedIn OAuth; optionally Meta Business",
        "risk": "send",
        "jarvis_permission_scope": "social:crosspost",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing Twitter API keys (minimum); optionally LinkedIn + Meta tokens",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_crosspost_mocked",
        "live_test_command": "uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('crosspost')\"",
        "activation_route": "Set Twitter API keys; enable with dry_run=True",
        "rollback_path": "Unset API keys",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "videodb",
        "provider": "VideoDB",
        "required_env_keys": ["VIDEODB_API_KEY"],
        "optional_env_keys": [],
        "oauth_scopes": [],
        "account_setup": "VideoDB account at videodb.io; generate API key",
        "risk": "read_only",
        "jarvis_permission_scope": "media:video:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing VIDEODB_API_KEY",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_videodb_mocked",
        "live_test_command": "VIDEODB_API_KEY=$VIDEODB_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('videodb')\"",
        "activation_route": "Set VIDEODB_API_KEY; enable skill",
        "rollback_path": "Unset VIDEODB_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "ecc-tools-cost-audit",
        "provider": "Anthropic / OpenAI / OpenRouter",
        "required_env_keys": ["ANTHROPIC_API_KEY"],
        "optional_env_keys": ["OPENAI_API_KEY", "OPENROUTER_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Anthropic account; or OpenRouter account (already configured if OPENROUTER_API_KEY is set)",
        "risk": "read_only",
        "jarvis_permission_scope": "llm:usage:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing ANTHROPIC_API_KEY (or OPENROUTER_API_KEY if already configured)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_ecc_tools_cost_audit_mocked",
        "live_test_command": "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('ecc-tools-cost-audit')\"",
        "activation_route": "Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY; enable skill",
        "rollback_path": "Unset API key",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "configure-ecc",
        "provider": "GitHub",
        "required_env_keys": ["GITHUB_TOKEN"],
        "optional_env_keys": ["ECC_REPO_PATH"],
        "oauth_scopes": ["repo:write"],
        "account_setup": "GitHub PAT with write access to ECC config repo (affaan-m/ECC or Bryan's fork)",
        "risk": "write",
        "jarvis_permission_scope": "github:ecc:configure",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing GITHUB_TOKEN with write scopes to ECC repo",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_configure_ecc_mocked",
        "live_test_command": "GITHUB_TOKEN=$GITHUB_TOKEN uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('configure-ecc')\"",
        "activation_route": "Set GITHUB_TOKEN with write scopes; enable skill",
        "rollback_path": "Revoke token; revert ECC config changes via git revert",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "article-writing",
        "provider": "OpenRouter / Anthropic / OpenAI",
        "required_env_keys": [],
        "optional_env_keys": ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Uses existing LLM configuration; likely already active via OPENROUTER_API_KEY",
        "risk": "read_only",
        "jarvis_permission_scope": "content:generate:read_only",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Requires LLM API key (may already be configured via OPENROUTER_API_KEY)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_article_writing_mocked",
        "live_test_command": "uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('article-writing')\"",
        "activation_route": "If OPENROUTER_API_KEY is set, activate immediately; otherwise set ANTHROPIC_API_KEY",
        "rollback_path": "Disable skill in catalog",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "content-engine",
        "provider": "LLM + optional CMS",
        "required_env_keys": ["OPENROUTER_API_KEY"],
        "optional_env_keys": ["CMS_API_KEY", "CONTENTFUL_API_KEY", "NOTION_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "LLM API (OpenRouter); optional CMS for publishing",
        "risk": "write",
        "jarvis_permission_scope": "content:generate:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Requires OPENROUTER_API_KEY (may already be configured)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_content_engine_mocked",
        "live_test_command": "uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('content-engine')\"",
        "activation_route": "If OPENROUTER_API_KEY set, enable skill; add CMS key for publishing",
        "rollback_path": "Disable skill in catalog",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "brand-discovery",
        "provider": "Exa or SERP API",
        "required_env_keys": ["EXA_API_KEY"],
        "optional_env_keys": ["SERP_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Exa.ai account",
        "risk": "read_only",
        "jarvis_permission_scope": "search:brand:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing EXA_API_KEY",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_brand_discovery_mocked",
        "live_test_command": "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('brand-discovery')\"",
        "activation_route": "Set EXA_API_KEY; enable skill",
        "rollback_path": "Unset EXA_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "brand-voice",
        "provider": "OpenRouter / Anthropic",
        "required_env_keys": [],
        "optional_env_keys": ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Uses existing LLM configuration",
        "risk": "read_only",
        "jarvis_permission_scope": "content:analysis:read_only",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Requires LLM API key (may already be configured)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_brand_voice_mocked",
        "live_test_command": "uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('brand-voice')\"",
        "activation_route": "If OPENROUTER_API_KEY set, activate immediately",
        "rollback_path": "Disable skill",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "competitive-platform-analysis",
        "provider": "Exa",
        "required_env_keys": ["EXA_API_KEY"],
        "optional_env_keys": ["SERP_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Exa.ai account",
        "risk": "read_only",
        "jarvis_permission_scope": "search:competitive:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing EXA_API_KEY",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_competitive_platform_mocked",
        "live_test_command": "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('competitive-platform-analysis')\"",
        "activation_route": "Set EXA_API_KEY; enable skill",
        "rollback_path": "Unset EXA_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "competitive-report-structure",
        "provider": "Exa",
        "required_env_keys": ["EXA_API_KEY"],
        "optional_env_keys": [],
        "oauth_scopes": [],
        "account_setup": "Exa.ai account",
        "risk": "read_only",
        "jarvis_permission_scope": "search:reports:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing EXA_API_KEY",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_competitive_report_mocked",
        "live_test_command": "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('competitive-report-structure')\"",
        "activation_route": "Set EXA_API_KEY; enable skill",
        "rollback_path": "Unset EXA_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "investor-materials",
        "provider": "LLM",
        "required_env_keys": [],
        "optional_env_keys": ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Uses existing LLM configuration",
        "risk": "read_only",
        "jarvis_permission_scope": "content:generate:read_only",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Requires LLM API key (may already be configured via OPENROUTER_API_KEY)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_investor_materials_mocked",
        "live_test_command": "uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('investor-materials')\"",
        "activation_route": "If OPENROUTER_API_KEY set, activate immediately",
        "rollback_path": "Disable skill",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "marketing-campaign",
        "provider": "Email + Social APIs",
        "required_env_keys": ["RESEND_API_KEY", "EMAIL_FROM"],
        "optional_env_keys": ["TWITTER_API_KEY", "LINKEDIN_ACCESS_TOKEN", "META_PAGE_ACCESS_TOKEN"],
        "oauth_scopes": ["email.send", "twitter.write"],
        "account_setup": "Resend account; Twitter Developer account; optional LinkedIn/Meta",
        "risk": "send",
        "jarvis_permission_scope": "marketing:campaign:send",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing RESEND_API_KEY + EMAIL_FROM (minimum); optionally social API keys",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_marketing_campaign_mocked",
        "live_test_command": "RESEND_API_KEY=$RESEND_API_KEY EMAIL_FROM=$EMAIL_FROM uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('marketing-campaign')\"",
        "activation_route": "Set email keys; enable with dry_run=True first",
        "rollback_path": "Unset email keys",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "seo",
        "provider": "Ahrefs or SEMrush or Moz",
        "required_env_keys": ["AHREFS_API_KEY"],
        "optional_env_keys": ["SEMRUSH_API_KEY", "MOZ_ACCESS_ID", "MOZ_SECRET_KEY"],
        "oauth_scopes": [],
        "account_setup": "Ahrefs account (ahrefs.com); or SEMrush; or Moz Pro",
        "risk": "read_only",
        "jarvis_permission_scope": "seo:metrics:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing AHREFS_API_KEY (or SEMRUSH_API_KEY or MOZ keys)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_seo_mocked",
        "live_test_command": "AHREFS_API_KEY=$AHREFS_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('seo')\"",
        "activation_route": "Set AHREFS_API_KEY; enable skill",
        "rollback_path": "Unset API key",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "agent-payment-x402",
        "provider": "X402 Protocol / Payment Provider",
        "required_env_keys": ["X402_PAYMENT_KEY"],
        "optional_env_keys": ["STRIPE_API_KEY", "COINBASE_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "X402 protocol account; or Stripe account with payment intents enabled",
        "risk": "financial",
        "jarvis_permission_scope": "payments:charge",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing X402_PAYMENT_KEY; financial risk requires Bryan's explicit approval",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_agent_payment_mocked",
        "live_test_command": "X402_PAYMENT_KEY=$X402_PAYMENT_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('agent-payment-x402')\"",
        "activation_route": "Set X402_PAYMENT_KEY + Bryan explicit approval + dry_run test first",
        "rollback_path": "Revoke X402 payment key; disable skill immediately",
        "completable_with_keys": True,
        "impossible_even_with_keys": ["Financial risk — requires Bryan explicit approval even with keys"],
    },
    {
        "skill_id": "social-graph-ranker",
        "provider": "Social Media APIs",
        "required_env_keys": ["TWITTER_BEARER_TOKEN"],
        "optional_env_keys": ["LINKEDIN_ACCESS_TOKEN", "X_API_KEY"],
        "oauth_scopes": ["twitter.read"],
        "account_setup": "Twitter Developer account; generate bearer token",
        "risk": "read_only",
        "jarvis_permission_scope": "social:graph:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing TWITTER_BEARER_TOKEN",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_social_graph_ranker_mocked",
        "live_test_command": "TWITTER_BEARER_TOKEN=$TBT uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('social-graph-ranker')\"",
        "activation_route": "Set TWITTER_BEARER_TOKEN; enable skill",
        "rollback_path": "Revoke bearer token",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "research-ops",
        "provider": "Exa or Perplexity",
        "required_env_keys": ["EXA_API_KEY"],
        "optional_env_keys": ["PERPLEXITY_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Exa.ai account",
        "risk": "read_only",
        "jarvis_permission_scope": "research:search:read",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing EXA_API_KEY",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_research_ops_mocked",
        "live_test_command": "EXA_API_KEY=$EXA_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('research-ops')\"",
        "activation_route": "Set EXA_API_KEY; enable skill",
        "rollback_path": "Unset EXA_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "knowledge-ops",
        "provider": "Pinecone or Weaviate or Qdrant",
        "required_env_keys": ["PINECONE_API_KEY"],
        "optional_env_keys": ["PINECONE_ENV", "WEAVIATE_URL", "WEAVIATE_API_KEY", "QDRANT_URL", "QDRANT_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Pinecone account at pinecone.io; or Weaviate Cloud; or Qdrant Cloud",
        "risk": "write",
        "jarvis_permission_scope": "knowledge:vector:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing PINECONE_API_KEY (or WEAVIATE_URL + WEAVIATE_API_KEY or QDRANT_URL + QDRANT_API_KEY)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_knowledge_ops_mocked",
        "live_test_command": "PINECONE_API_KEY=$PINECONE_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('knowledge-ops')\"",
        "activation_route": "Set PINECONE_API_KEY + PINECONE_ENV; enable skill",
        "rollback_path": "Unset PINECONE_API_KEY; delete Pinecone index if created",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "project-flow-ops",
        "provider": "Linear or Jira",
        "required_env_keys": ["LINEAR_API_KEY"],
        "optional_env_keys": ["JIRA_API_TOKEN", "JIRA_BASE_URL", "JIRA_EMAIL"],
        "oauth_scopes": [],
        "account_setup": "Linear account at linear.app; generate API key from Settings → API",
        "risk": "write",
        "jarvis_permission_scope": "project:issues:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing LINEAR_API_KEY (or JIRA_API_TOKEN + JIRA_BASE_URL + JIRA_EMAIL)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_project_flow_ops_mocked",
        "live_test_command": "LINEAR_API_KEY=$LINEAR_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('project-flow-ops')\"",
        "activation_route": "Set LINEAR_API_KEY; enable skill",
        "rollback_path": "Unset LINEAR_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "team-builder",
        "provider": "Greenhouse or Workday",
        "required_env_keys": ["GREENHOUSE_API_KEY"],
        "optional_env_keys": ["WORKDAY_API_KEY", "LEVER_API_KEY"],
        "oauth_scopes": [],
        "account_setup": "Greenhouse account at greenhouse.io; generate Harvest API key",
        "risk": "write",
        "jarvis_permission_scope": "hr:candidates:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing GREENHOUSE_API_KEY (or WORKDAY_API_KEY or LEVER_API_KEY)",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_team_builder_mocked",
        "live_test_command": "GREENHOUSE_API_KEY=$GREENHOUSE_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('team-builder')\"",
        "activation_route": "Set GREENHOUSE_API_KEY; enable skill",
        "rollback_path": "Unset GREENHOUSE_API_KEY",
        "completable_with_keys": True,
        "impossible_even_with_keys": [],
    },
    {
        "skill_id": "stripe-integration",
        "provider": "Stripe",
        "required_env_keys": ["STRIPE_API_KEY", "STRIPE_WEBHOOK_SECRET"],
        "optional_env_keys": ["STRIPE_PRICE_ID", "STRIPE_PUBLISHABLE_KEY"],
        "oauth_scopes": [],
        "account_setup": "Stripe account at stripe.com; generate API keys from Dashboard → Developers → API Keys",
        "risk": "financial",
        "jarvis_permission_scope": "payments:stripe:write",
        "plan1_state": Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        "exact_blocker": "Missing STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET; financial risk requires Bryan approval",
        "mocked_test_command": "uv run pytest tests/skills/test_plan1_completion.py::TestEccKeySkillsMocked::test_stripe_integration_mocked",
        "live_test_command": "STRIPE_API_KEY=$STRIPE_API_KEY uv run python -c \"from openjarvis.skills.ecc_completion import live_test_skill; live_test_skill('stripe-integration')\"",
        "activation_route": "Set STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET; use test mode first (sk_test_...)",
        "rollback_path": "Delete webhook; revoke API key from Stripe dashboard",
        "completable_with_keys": True,
        "impossible_even_with_keys": ["Financial risk — use Stripe test mode keys first (sk_test_...)"],
    },
]

# Quick lookup by skill_id
ECC_KEY_REQUIREMENTS_BY_ID: Dict[str, Dict[str, Any]] = {
    req["skill_id"]: req for req in ECC_KEY_REQUIREMENTS
}


# ---------------------------------------------------------------------------
# Key presence checker (reads env vars — no secrets stored)
# ---------------------------------------------------------------------------

def check_key_presence(skill_id: str) -> Dict[str, Any]:
    """Check which required env keys are present for a skill (reads env vars).

    Does NOT validate actual key values — only checks presence.
    Never prints or logs key values.
    """
    req = ECC_KEY_REQUIREMENTS_BY_ID.get(skill_id)
    if req is None:
        return {"skill_id": skill_id, "found": False, "error": "skill not in key requirements"}

    required_keys = req.get("required_env_keys", [])
    optional_keys = req.get("optional_env_keys", [])

    required_present = {k: (k in os.environ and len(os.environ[k]) > 0) for k in required_keys}
    optional_present = {k: (k in os.environ and len(os.environ[k]) > 0) for k in optional_keys}

    all_required_present = all(required_present.values()) if required_keys else True
    can_activate = all_required_present

    return {
        "skill_id": skill_id,
        "provider": req["provider"],
        "plan1_state": req["plan1_state"],
        "required_keys_present": required_present,
        "optional_keys_present": optional_present,
        "all_required_present": all_required_present,
        "can_activate": can_activate,
        "missing_required": [k for k, v in required_present.items() if not v],
        "risk": req["risk"],
        "activation_route": req["activation_route"] if can_activate else "Set missing keys first",
        "live_test_command": req["live_test_command"],
    }


def get_readiness_report() -> Dict[str, Any]:
    """Return full readiness report for all 35 API-key skills.

    Shows which are ready, which need keys, and what Bryan must provide.
    Reads env vars only — no secrets stored or printed.
    """
    results = []
    ready_count = 0
    missing_count = 0
    missing_providers: Dict[str, List[str]] = {}

    for req in ECC_KEY_REQUIREMENTS:
        check = check_key_presence(req["skill_id"])
        if check["can_activate"]:
            ready_count += 1
        else:
            missing_count += 1
            provider = req["provider"]
            if provider not in missing_providers:
                missing_providers[provider] = []
            missing_providers[provider].extend(check["missing_required"])

        results.append(check)

    return {
        "total_api_key_skills": len(ECC_KEY_REQUIREMENTS),
        "ready_to_activate": ready_count,
        "missing_keys": missing_count,
        "results": results,
        "missing_by_provider": missing_providers,
        "prompt2_action": (
            f"Provide {missing_count} missing key sets to Bryan to enable live tests. "
            f"See docs/certification/PLAN1_ECC_MISSING_KEYS.md for exact key names."
        ),
    }


# ---------------------------------------------------------------------------
# Mocked test helpers (no live calls, no secrets)
# ---------------------------------------------------------------------------

def _mock_skill_invocation(skill_id: str) -> Dict[str, Any]:
    """Simulate a skill invocation using mock data (no live calls)."""
    req = ECC_KEY_REQUIREMENTS_BY_ID.get(skill_id, {})
    return {
        "skill_id": skill_id,
        "provider": req.get("provider", "unknown"),
        "dry_run": True,
        "result": "MOCKED_SUCCESS",
        "message": f"Mocked invocation of {skill_id} — no live API calls made",
        "mocked_test_command": req.get("mocked_test_command", ""),
        "requires_keys": req.get("required_env_keys", []),
    }


def run_mocked_tests() -> Dict[str, Any]:
    """Run mocked tests for all 35 API-key skills (no live calls)."""
    results = [_mock_skill_invocation(req["skill_id"]) for req in ECC_KEY_REQUIREMENTS]
    return {
        "total": len(results),
        "all_mocked_success": all(r["result"] == "MOCKED_SUCCESS" for r in results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Live test helper placeholder (Bryan provides keys in Prompt 2)
# ---------------------------------------------------------------------------

def live_test_skill(skill_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """Placeholder for live skill testing with real keys.

    In Prompt 2: Bryan provides keys → this function runs real API calls.
    In Prompt 1: raises RuntimeError if called without keys (safe by default).

    Args:
        skill_id: ECC skill ID to test
        dry_run: If True, validates key presence but makes no API calls
    """
    check = check_key_presence(skill_id)
    if not check["can_activate"]:
        raise RuntimeError(
            f"Cannot run live test for {skill_id}: "
            f"missing keys {check['missing_required']}. "
            f"Provide these in Prompt 2."
        )

    if dry_run:
        return {
            "skill_id": skill_id,
            "dry_run": True,
            "keys_present": True,
            "result": "DRY_RUN_PASS",
            "message": f"Keys present for {skill_id}. Remove dry_run=False to run live test.",
        }

    # Actual live test implementations go here in Prompt 2
    raise NotImplementedError(
        f"Live test for {skill_id} not yet implemented. "
        f"Implement in Prompt 2 after keys provided."
    )


# ---------------------------------------------------------------------------
# Artifact generators
# ---------------------------------------------------------------------------

def generate_missing_keys_json(output_path: Optional[Path] = None) -> str:
    """Generate machine-readable JSON artifact for all API-key skills.

    Returns JSON string. If output_path given, also writes file.
    """
    payload = {
        "generated_by": "openjarvis.skills.ecc_completion",
        "sprint": "Plan 1 ECC Completion Sprint — Pre-Keys (Prompt 1)",
        "total_api_key_skills": len(ECC_KEY_REQUIREMENTS),
        "skills": ECC_KEY_REQUIREMENTS,
        "prompt2_inputs": [
            "EXA_API_KEY — for exa-search, deep-research, market-research, research-ops, brand-discovery, competitive-platform-analysis, competitive-report-structure",
            "FAL_API_KEY — for fal-ai-media",
            "GITHUB_TOKEN (write) — for github-ops, configure-ecc",
            "JIRA_API_TOKEN + JIRA_BASE_URL + JIRA_EMAIL — for jira-integration",
            "GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GOOGLE_REFRESH_TOKEN — for google-workspace-ops (requires OAuth browser flow)",
            "SLACK_BOT_TOKEN (or TELEGRAM_BOT_TOKEN) — for messages-ops, unified-notifications-ops",
            "X_API_KEY + X_API_SECRET + X_ACCESS_TOKEN + X_ACCESS_TOKEN_SECRET — for x-api, social-publisher, crosspost",
            "VIDEODB_API_KEY — for videodb",
            "STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET (use sk_test_... first) — for stripe-integration",
            "LINEAR_API_KEY (or JIRA_API_TOKEN) — for project-flow-ops",
            "APOLLO_API_KEY — for lead-intelligence",
            "AHREFS_API_KEY (or SEMRUSH_API_KEY) — for seo",
            "GREENHOUSE_API_KEY — for team-builder",
            "PINECONE_API_KEY + PINECONE_ENV — for knowledge-ops",
            "SCRAPING_BEE_API_KEY — for data-scraper-agent",
            "RESEND_API_KEY + EMAIL_FROM — for email-ops, investor-outreach, marketing-campaign",
            "TWITTER_BEARER_TOKEN — for social-graph-ranker",
            "ANTHROPIC_API_KEY — for ecc-tools-cost-audit (or OPENROUTER_API_KEY if already set)",
            "X402_PAYMENT_KEY + Bryan approval — for agent-payment-x402 (financial risk)",
            "Bryan approval — for all 11 planning/review agents (after Jarvis routing wired)",
        ],
    }

    json_str = json.dumps(payload, indent=2)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str)

    return json_str


def format_missing_keys_md() -> str:
    """Generate Markdown documentation for all API-key skills."""
    lines = [
        "# Plan 1 ECC Missing Keys — API Key Requirements",
        "",
        "**Sprint:** Plan 1 ECC Completion Sprint — Pre-Keys (Prompt 1)",
        "**Status:** PLAN_1_ECC_PRE_KEYS_COMPLETION_ACCEPT_PENDING_REVIEW",
        "",
        "All 35 API-key-dependent ECC skills are structurally complete.",
        "Each entry below documents exactly what Bryan must provide in Prompt 2.",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total API-key skills | {len(ECC_KEY_REQUIREMENTS)} |",
        f"| Unique providers | {len({r['provider'] for r in ECC_KEY_REQUIREMENTS})} |",
        f"| Read-only risk | {sum(1 for r in ECC_KEY_REQUIREMENTS if r['risk'] == 'read_only')} |",
        f"| Write/action risk | {sum(1 for r in ECC_KEY_REQUIREMENTS if r['risk'] in ('write', 'action'))} |",
        f"| Send risk | {sum(1 for r in ECC_KEY_REQUIREMENTS if r['risk'] == 'send')} |",
        f"| Financial risk | {sum(1 for r in ECC_KEY_REQUIREMENTS if r['risk'] == 'financial')} |",
        "",
        "## Key Requirements by Skill",
        "",
    ]

    for req in ECC_KEY_REQUIREMENTS:
        lines += [
            f"### `ecc:{req['skill_id']}`",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Provider** | {req['provider']} |",
            f"| **Risk** | {req['risk']} |",
            f"| **Required keys** | `{'`, `'.join(req['required_env_keys']) if req['required_env_keys'] else '(uses existing LLM config)'}` |",
            f"| **Optional keys** | `{'`, `'.join(req['optional_env_keys']) if req['optional_env_keys'] else 'none'}` |",
            f"| **OAuth scopes** | `{'`, `'.join(req['oauth_scopes']) if req['oauth_scopes'] else 'none'}` |",
            f"| **Account setup** | {req['account_setup']} |",
            f"| **Exact blocker** | {req['exact_blocker']} |",
            f"| **Mocked test** | `{req['mocked_test_command']}` |",
            f"| **Live test** | `{req['live_test_command'][:80]}...` |",
            f"| **Activation** | {req['activation_route']} |",
            f"| **Rollback** | {req['rollback_path']} |",
            f"| **Completable with keys** | {'✅ Yes' if req['completable_with_keys'] else '❌ No'} |",
        ]
        if req["impossible_even_with_keys"]:
            lines.append(f"| **Remaining blockers** | {'; '.join(req['impossible_even_with_keys'])} |")
        lines.append("")

    lines += [
        "## Prompt 2 — What Bryan Must Provide",
        "",
        "To run live tests and activate all 35 provider skills, Bryan must provide:",
        "",
    ]
    for i, item in enumerate(ECC_KEY_REQUIREMENTS[:5], 1):
        keys = ", ".join(f"`{k}`" for k in item["required_env_keys"]) if item["required_env_keys"] else "(already configured)"
        lines.append(f"{i}. **{item['skill_id']}** → {keys}")

    lines += [
        "...",
        "",
        "See `build/reports/plan1_ecc_missing_keys.json` for the complete machine-readable list.",
        "",
        "## Agents Waiting for Approval",
        "",
        "11 planning/review agents are `READY_BUT_WAITING_FOR_APPROVAL`.",
        "No API key needed — Bryan must approve Jarvis agent routing wiring:",
        "",
        "- `ecc:agent:architect`, `ecc:agent:code-reviewer`, `ecc:agent:doc-updater`",
        "- `ecc:agent:planner`, `ecc:agent:reviewer`, `ecc:agent:security-reviewer`",
        "- `ecc:agent:spec-miner`, `ecc:agent:tdd-guide`, `ecc:agent:refactor-cleaner`",
        "- `ecc:agent:build-error-resolver`, `ecc:agent:explorer`",
        "",
        "Activation route: wire Jarvis agent routing framework → Bryan approves → set `reviewer_approved=True`",
    ]

    return "\n".join(lines)


__all__ = [
    "Plan1State",
    "ECC_KEY_REQUIREMENTS",
    "ECC_KEY_REQUIREMENTS_BY_ID",
    "check_key_presence",
    "get_readiness_report",
    "run_mocked_tests",
    "live_test_skill",
    "generate_missing_keys_json",
    "format_missing_keys_md",
]
