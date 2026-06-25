> **NOTE: This document is OMNIX project-specific.** It describes the workbench tools for the OMNIX project — one optional integration built on top of Jarvis OS. Jarvis does not require OMNIX. For Jarvis core documentation, see README.md.

# Jarvis OMNIX Workbench v1

Functional local front door for OMNIX upgrade work using Jarvis agents.

## Starting Mission Control

**User-facing Mission Control bridge** (internal service):
```bash
cd /Users/user/CascadeProjects/omnix-command-center
OPENCLAW_WORKSPACE_DIR=/Users/user/CascadeProjects/openclaw-workspace-omnix PORT=3091 node server.js
```

Mission Control provides the status bundle endpoint at `http://127.0.0.1:3091/api/jarvis/status-bundle`

## Running the Workbench

**Visible launcher (recommended):**
```bash
cd /Users/user/OpenJarvis
bash scripts/jarvis-omnix <mode> [args]
```

**Direct script:**
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
Real local memory system for continuity and decisions.
```bash
bash scripts/omnix-workbench memory add "decision made"
bash scripts/omnix-workbench memory list
bash scripts/omnix-workbench memory search "query"
bash scripts/omnix-workbench memory show 1
```

### Artifact
Real local artifact context for documents.
```bash
bash scripts/omnix-workbench artifact add /path/to/file.txt
bash scripts/omnix-workbench artifact list
bash scripts/omnix-workbench artifact show 1
bash scripts/omnix-workbench artifact summarize 1
```

### Run
Orchestrate status→plan→prompt→gate workflow.
```bash
bash scripts/omnix-workbench run "Improve OMNIX tester onboarding"
```

### Slack
Slack status and test-send using existing OpenClaw infrastructure.
```bash
bash scripts/omnix-workbench slack status
bash scripts/omnix-workbench slack test-send
```

### Deploy
Deploy readiness check only (no actual deployment).
```bash
bash scripts/omnix-workbench deploy
bash scripts/omnix-workbench deploy vercel
```

## Agent Routing

Uses available Jarvis agents (simple, orchestrator, etc.) for LLM-powered modes.
Custom agent names are mapped to available Jarvis agents for compatibility.

## Safety Rules

- Workbench rejects non-localhost status URLs
- Prompts are compact to avoid timeout
- Output is labeled as [JARVIS LLM] or [FALLBACK - LLM unavailable]
- Never marks deployment/production ready unless explicitly asked
- Slack not configured = risk, not blocker for branch-only planning
- No secrets, no Slack sends, no OMNIX/OpenClaw writes
- Memory/artifact systems reject content with potential secrets
- Deploy mode only checks readiness, does not perform deployment

## OpenClaw/Jarvis Parity Contract

**Jarvis is the primary front door** for Bryan's OMNIX/OpenClaw work:
- Jarvis Workbench provides unified interface for planning, coding prompts, review, QA, gates
- Jarvis agents execute decision-making and coordination workflows
- OpenClaw is backend/runtime status source where useful
- Dashboard is observability/status bridge
- OMNIX is product surface

**OpenClaw workflow features** must be surfaced in Jarvis or marked backend-only:
- OpenClaw runtime status: Available via status bundle
- OpenClaw mission engine: Accessible via dashboard bridge only
- OpenClaw workflows: To be integrated via Jarvis agents or marked backend-only
- OpenClaw actions: Jarvis can read but not execute without approval

**Slack sends/deployments/writes require explicit mode and gate**:
- Slack sends: Use `slack test-send` mode with explicit confirmation
- Deployments: Use `deploy` mode for readiness check only, manual deployment required
- OMNIX/OpenClaw writes: Not performed by Jarvis Workbench (read-only operations only)

## Current Limitations

- Requires local dashboard bridge running on port 3091 for status-dependent modes
- Agent routing depends on available Jarvis agents
- Some modes may fallback to deterministic logic if Jarvis LLM unavailable
- Memory system is local-only (no cloud sync)
- Artifact system supports limited file types (.txt, .md, .json, .log) with size cap
- Slack integration requires existing OpenClaw configuration
- Deploy mode only validates readiness, does not deploy
