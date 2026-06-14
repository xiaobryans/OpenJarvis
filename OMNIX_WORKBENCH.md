# Jarvis OMNIX Workbench v1

All-in-one local front door for OMNIX upgrade work using Jarvis agents.

## Starting the Dashboard Bridge

```bash
cd /Users/user/CascadeProjects/omnix-command-center
OPENCLAW_WORKSPACE_DIR=/Users/user/CascadeProjects/openclaw-workspace-omnix PORT=3091 node server.js
```

## Running the Workbench

```bash
cd /Users/user/OpenJarvis
bash scripts/omnix-workbench <mode> [args]
```

## Modes

### Status
Fetch and summarize the OMNIX status bundle.
```bash
bash scripts/omnix-workbench status
```

### Plan
Produce a Jarvis-led OMNIX upgrade plan.
```bash
bash scripts/omnix-workbench plan "Improve OMNIX tester onboarding"
```

### Prompt
Generate a branch-only coding-agent prompt.
```bash
bash scripts/omnix-workbench prompt "Improve OMNIX tester onboarding"
```

### Review
Review a coding-agent report and return ACCEPT/HOLD.
```bash
bash scripts/omnix-workbench review "<pasted final report>"
```

### QA
List necessary validation gaps from evidence.
```bash
bash scripts/omnix-workbench qa "<pasted validation evidence>"
```

### Gate
Release-gatekeeper ACCEPT/HOLD decision.
```bash
bash scripts/omnix-workbench gate "<pasted report>"
```

### Memory
Obsidian-style memory/continuity placeholder.
```bash
bash scripts/omnix-workbench memory "query"
```

### Artifact
Paperclip-style document/artifact context placeholder.
```bash
bash scripts/omnix-workbench artifact "context"
```

## Agent Routing

Uses available Jarvis agents (simple, orchestrator, etc.) for LLM-powered modes.
Custom agent names are mapped to available Jarvis agents for compatibility.

## Safety Rules

- Workbench rejects non-localhost status URLs
- Prompts are compact to avoid timeout
- Output is labeled as [JARVIS LLM] or [FALLBACK]
- Never marks deployment/production ready unless explicitly asked
- Slack not configured = risk, not blocker for branch-only planning
- No secrets, no Slack sends, no OMNIX/OpenClaw writes

## OpenClaw Parity Contract

Future OpenClaw workflow features must be surfaced in Jarvis or marked backend-only.
- OpenClaw runtime status: Available via status bundle
- OpenClaw mission engine: Accessible via dashboard bridge only
- OpenClaw workflows: To be integrated via Jarvis agents or marked backend-only
- OpenClaw actions: Jarvis can read but not execute without approval

## Current Limitations

- Requires local dashboard bridge running on port 3091
- Agent routing depends on available Jarvis agents
- Some modes may fallback to deterministic logic if Jarvis LLM unavailable
- Memory and artifact modes are placeholders (no persistence/indexing yet)
- No persistent state or memory across sessions
