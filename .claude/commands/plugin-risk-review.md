# /plugin-risk-review

Assess a proposed **MCP server or Claude Code plugin** before activation.

## Usage
```
/plugin-risk-review [tool name or description]
/plugin-risk-review github-mcp
/plugin-risk-review "linear MCP from anthropic"
```

## What this does
Runs the `openjarvis-plugin-mcp-risk-review` skill:
1. Invokes `plugin-mcp-risk-reviewer` agent.
2. Assesses 7 risk dimensions: source, permission scope, prompt injection, secret exposure, external network calls, cloud spend, data residency.
3. Applies decision matrix: ACTIVATE | DEFER | REJECT.
4. Updates `docs/automation/MCP_PLUGIN_EXPANSION_PLAN.md` with assessment.
5. Returns verdict — never activates the tool.

## Output
```
PLUGIN/MCP RISK REVIEW: [tool name]
Source: [vendor]
Risk dimensions: [7 assessments]
VERDICT: ACTIVATE | DEFER | REJECT
CONDITION (if DEFER): [what Bryan must approve]
```

## Hard stops
- Never adds MCP config to `settings.json` without Bryan's explicit approval.
- Never installs packages for new MCP tools without Bryan's approval.
- REJECT means do not activate under any circumstances without re-review.
