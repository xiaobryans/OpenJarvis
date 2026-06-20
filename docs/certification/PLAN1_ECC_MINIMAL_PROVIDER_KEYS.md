# Plan 1 ECC Minimal Provider Keys

**Sprint:** Plan 1 ECC Correction Pass — Provider Consolidation
**Policy:** AIMLAPI first, OpenRouter fallback, native only when required

## Summary

| Total API-key skills | 37 |
|---|---|
| Consolidatable via AIMLAPI | 7 |
| Require native provider | 30 |

**Key reduction:** Instead of 35+ separate provider keys, Bryan needs:
1 AIMLAPI gateway key + 14 native service keys + 1 OAuth flow

## A. Gateway Keys (covers multiple skills with ONE key)

| Key | Account | Skills Covered |
|-----|---------|----------------|
| `AIMLAPI_API_KEY` | aimlapi.com | ecc-tools-cost-audit, article-writing, content-engine, brand-voice, investor-materials, continuous-learning-v2, fal-ai-media |
| `OPENROUTER_API_KEY` (fallback) | openrouter.ai | LLM-only skills (5) |

## B. Native Service Connector Keys

| Key | Account | Skills Covered |
|-----|---------|----------------|
| `EXA_API_KEY` | exa.ai | 7 search/research skills |
| `GITHUB_TOKEN` | github.com/settings/tokens | github-ops, configure-ecc |
| `SLACK_BOT_TOKEN` | api.slack.com | messages-ops, unified-notifications-ops |
| Twitter API keys (4) | developer.twitter.com | social-publisher, x-api, crosspost |
| `TWITTER_BEARER_TOKEN` | Same Twitter dev account | social-graph-ranker |
| `RESEND_API_KEY + EMAIL_FROM` | resend.com | email-ops, investor-outreach, marketing-campaign |
| `VIDEODB_API_KEY` | videodb.io | videodb |
| `LINEAR_API_KEY` | linear.app | project-flow-ops |
| `APOLLO_API_KEY` | apollo.io | lead-intelligence |
| `AHREFS_API_KEY` | ahrefs.com | seo |
| `GREENHOUSE_API_KEY` | greenhouse.io | team-builder |
| `PINECONE_API_KEY + PINECONE_ENV` | pinecone.io | knowledge-ops |
| `SCRAPING_BEE_API_KEY` | scrapingbee.com | data-scraper-agent |
| `JIRA_API_TOKEN + JIRA_BASE_URL + JIRA_EMAIL` | atlassian.com | jira-integration |
| `NUTRIENT_API_KEY` | nutrient.io | nutrient-document-processing |

## C. OAuth / Browser-Consent Setups

| Setup | Skills | Steps |
|-------|--------|-------|
| Google Workspace OAuth | google-workspace-ops | Cloud Console + consent screen + browser flow |

## D. Financial / High-Risk Approvals

| Item | Skills | Note |
|------|--------|------|
| Stripe (test mode first) | stripe-integration | Use sk_test_... before live keys |
| X402 Payment | agent-payment-x402 | Bryan approval required BEFORE key |

## E. Optional / Later Keys

| Key | Purpose |
|-----|---------|
| `PERPLEXITY_API_KEY` | Optional upgrade for research skills |
| `LINKEDIN_ACCESS_TOKEN` | Optional for social publishing |
| `SEMRUSH_API_KEY` | Alternative to Ahrefs for SEO |
| `SENDGRID_API_KEY` | Alternative to Resend for email |

## What Was NOT Required

The following keys from the original list were **eliminated via consolidation:**
- ~~`ANTHROPIC_API_KEY`~~ → use `AIMLAPI_API_KEY`
- ~~`OPENAI_API_KEY`~~ → use `AIMLAPI_API_KEY`
- ~~`FAL_API_KEY`~~ → use `AIMLAPI_API_KEY` (covers fal-equivalent models)
- ~~`GOOGLE_AI_API_KEY`~~ → not required
- ~~`DEEPSEEK_API_KEY`~~ → not required
- ~~`GEMINI_API_KEY`~~ → not required