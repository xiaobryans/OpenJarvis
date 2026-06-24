# OpenJarvis MCP/Plugin Expansion Plan

**Sprint:** POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION
**Policy:** Controlled expansion — no tool activated without risk review and Bryan approval.
**Date:** 2026-06-25

---

## Activation Policy

A new MCP server or Claude Code plugin may only be activated when ALL of the following are true:
1. `plugin-mcp-risk-review` skill returns ACTIVATE verdict.
2. Bryan has explicitly approved the activation.
3. Source is auditable and trusted.
4. Rollback plan is documented.
5. No HIGH risk on prompt injection, secret exposure, or cloud spend.

---

## Proposed Tools — Assessment Queue

### Tier 1: Low-risk, high-value (ACTIVATE after Bryan approval)

| Tool | Source | Purpose | Risk | Verdict |
|------|--------|---------|------|---------|
| GitHub official MCP | Anthropic/official | Read PRs, issues, code — no write without approval | LOW — no secret exposure if token scoped read-only; prompt injection via PR titles (LOW) | DEFER — Bryan must set read-only PAT scope and approve |
| Linear MCP | Anthropic/official | Read/create issues for sprint tracking | LOW — no credential exposure if token scoped correctly | DEFER — Bryan must verify Linear workspace permissions |
| Filesystem MCP (read-only) | Anthropic/official | Structured file access | LOW — read-only scope limits damage | DEFER — verify no accidental credential file access |

### Tier 2: Medium-risk, useful (DEFER — Bryan must review specific risks)

| Tool | Source | Purpose | Risk | Verdict |
|------|--------|---------|------|---------|
| Slack MCP | Third-party | Read/post Slack messages | MEDIUM — prompt injection via message content; Slack token scoped to workspace | DEFER — requires dedicated read-only Slack bot token, not main workspace token |
| Browser/web MCP | Various | Web research | MEDIUM — prompt injection via web content (HIGH); network cost | DEFER — only activate for scoped research sessions, not always-on |
| AWS MCP | Third-party | ECS/S3/Secrets queries | HIGH (secrets exposure risk) | REJECT until official Anthropic AWS MCP with read-only role is available |

### Tier 3: High-risk (REJECT or permanent defer)

| Tool | Source | Purpose | Risk | Verdict |
|------|--------|---------|------|---------|
| Any MCP with `*` permission scope | Unknown | General | HIGH — uncontrolled access | REJECT |
| Any MCP that reads `.env` or OAuth files | Unknown | Credential access | HIGH — secret exposure | REJECT |
| Any MCP with unbounded external API calls | Unknown | General | HIGH — cloud spend, data residency | REJECT |
| Community/unaudited MCPs | Unknown | Various | HIGH — no source audit possible | REJECT until audited |

---

## Currently Active MCP Configuration

None — no MCP servers are configured in `.claude/settings.json` beyond built-in tools.

---

## Activation Checklist (per tool)

Before activating any tool, complete this checklist:
- [ ] `plugin-mcp-risk-review [tool]` returns ACTIVATE verdict
- [ ] Bryan has explicitly said "activate [tool]" in the current sprint prompt
- [ ] Source is auditable (official Anthropic or well-known vendor with public repo)
- [ ] Token/credential is scoped to minimum required permissions (read-only where possible)
- [ ] Rollback is documented (how to disable the MCP server)
- [ ] No .env or OAuth file access is possible from the tool
- [ ] Cloud spend risk is LOW or has a spend cap
- [ ] Prompt injection risk is LOW or has a mitigating scope (no untrusted content ingestion)

---

## Rollback Procedure (for any active MCP)

1. Remove the MCP entry from `.claude/settings.json`.
2. Revoke the associated token/credential in the vendor's dashboard.
3. Verify the tool no longer appears in `ToolSearch` output.
4. Document the rollback in the sprint progress ledger.

---

## Next Review

Re-evaluate Tier 1 tools (GitHub MCP, Linear MCP) when:
- Plan 4–6 sprint tracking requirements are defined.
- Bryan explicitly asks to activate sprint tracking tools.

Do NOT activate any Tier 2 or Tier 3 tool without a full `plugin-mcp-risk-review` run and Bryan's explicit approval.

---

*Last updated: Post-Plan-2 automation expansion sprint, 2026-06-25*
