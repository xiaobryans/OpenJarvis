---
name: openjarvis-plugin-mcp-risk-review
description: Assess proposed MCP servers or plugins before activation — prompt-injection risk, secret exposure, network calls, spend risk, permission scope, rollback. Produces ACTIVATE | DEFER | REJECT per tool. Never activates tools — planning only. Use when Bryan proposes a new MCP server or Claude Code plugin.
---

# OpenJarvis Plugin/MCP Risk Review

Assesses proposed MCP servers or Claude Code plugins before activation.

## When to use
- When Bryan proposes activating a new MCP server.
- When `/plugin-risk-review [tool-name]` is invoked.
- Before updating `.claude/settings.json` with new MCP config.

## Steps

1. Invoke `plugin-mcp-risk-reviewer` agent for each proposed tool.
2. Assess 7 risk dimensions (source, scope, prompt injection, secret exposure, network, spend, rollback).
3. Apply decision matrix: ACTIVATE | DEFER | REJECT.
4. Update `docs/automation/MCP_PLUGIN_EXPANSION_PLAN.md` with assessment.
5. Return verdict to Bryan — never activate unilaterally.

## Forbidden
- Never add MCP config to `settings.json` without Bryan's explicit approval.
- Never install npm packages or Python packages for new MCP tools without Bryan's approval.

## Output
```
PLUGIN/MCP RISK REVIEW
[structured output per tool from plugin-mcp-risk-reviewer agent]
RECOMMENDATION: ACTIVATE | DEFER | REJECT
BRYAN MUST APPROVE: [what needs explicit sign-off before activation]
```
