# Post-Plan-2 Automation Gap Matrix

**Sprint:** POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION
**Date:** 2026-06-25
**Branch:** localhost-get-tool

This matrix captures the pre-sprint automation gaps and the proposed/implemented fixes.

---

## 1. Agent Coverage

| Agent | Current | Gap | Risk | Proposed | Status |
|-------|---------|-----|------|----------|--------|
| plan-acceptance-reviewer | MISSING | No agent to verify plan meets acceptance bar without faking PASS | HIGH | New agent: reviews plan artifacts against acceptance checklist, produces READY_FOR_REVIEW or HOLD | ADDED |
| fargate-runtime-verifier | MISSING | No agent to verify Fargate deployment health, secrets injection, task status | HIGH | New agent: reads ECS state, task def, secrets presence, health; produces proof report | ADDED |
| aws-deployment-safety-reviewer | MISSING | No agent to catch unsafe AWS actions (role widening, public bucket, key exposure) | HIGH | New agent: reviews AWS commands/plans for safety violations | ADDED |
| secret-sanitization-auditor | MISSING | No agent for deep secret audit beyond basic scan | MEDIUM | New agent: audits logs, responses, docs for accidental secret exposure | ADDED |
| endpoint-security-smoke-runner | MISSING | No agent to smoke-test public endpoints for leakage | HIGH | New agent: checks each public endpoint for field leakage, auth bypass, unexpected exposure | ADDED |
| tauri-release-gate-reviewer | MISSING | No agent to gate Tauri release (SHA match, signing, version) | MEDIUM | New agent: verifies SHA, version, signing, distribution requirements before Tauri release | ADDED |
| handoff-continuity-keeper | MISSING | No agent to maintain crash-safe handoff files after each sprint | MEDIUM | New agent: updates session state, progress ledger, and resume prompt after each sprint | ADDED |
| no-skip-blocker-auditor | MISSING | No agent to verify no blockers were quietly skipped | HIGH | New agent: audits final report for undisclosed blockers or partial PASS | ADDED |
| quality-score-reviewer | MISSING | No agent to produce consistent quality score (out of 5) | MEDIUM | New agent: scores sprint against 5 quality dimensions, produces 1–5 score with rationale | ADDED |
| plan4-6-mega-sprint-architect | MISSING | No agent to plan and decompose Plan 4–6 mega-sprints | MEDIUM | New agent: decomposes Plan 4–6 into safe sub-sprints with file ownership and sequencing | ADDED |
| plugin-mcp-risk-reviewer | MISSING | No agent to assess new MCP/plugin risk before activation | HIGH | New agent: reviews proposed MCP tools for secret exposure, prompt injection, spend risk | ADDED |
| ui-ux-product-reviewer | MISSING | No agent for UI/UX product polish review | LOW | New agent: reviews UI for Jarvis PA identity, product consistency, mobile/desktop parity | ADDED |
| mobile-cloud-parity-reviewer | MISSING | No agent to verify mobile/cloud parity after each sprint | MEDIUM | New agent: checks parity endpoints and matrix for regressions after mobile-affecting sprints | ADDED |
| regression-triage-reviewer | MISSING | No agent to triage test failures and distinguish pre-existing vs new regressions | MEDIUM | New agent: classifies each test failure as pre-existing or sprint-introduced | ADDED |

---

## 2. Skill Coverage

| Skill | Current | Gap | Risk | Proposed | Status |
|-------|---------|-----|------|----------|--------|
| openjarvis-final-acceptance-review | MISSING | No skill for full plan acceptance review workflow | HIGH | New skill: runs all acceptance checks and produces gated READY_FOR_REVIEW report | ADDED |
| openjarvis-fargate-runtime-proof | MISSING | No skill to produce Fargate runtime proof report | HIGH | New skill: queries ECS, verifies task health, secrets, endpoints; produces proof table | ADDED |
| openjarvis-tauri-release-gate | MISSING | No skill for Tauri release gating workflow | MEDIUM | New skill: SHA check, signing check, version check, distribution validation | ADDED |
| openjarvis-secret-sanitization | MISSING | No deep secret sanitization skill beyond basic scan | MEDIUM | New skill: audit all changed files + logs + docs for accidental secret exposure | ADDED |
| openjarvis-endpoint-security-audit | MISSING | No dedicated endpoint security audit skill | HIGH | New skill: smoke each public endpoint, check for field leakage, auth bypass | ADDED |
| openjarvis-handoff-continuity | MISSING | No skill to save/verify crash-safe handoff state | MEDIUM | New skill: saves session state, progress ledger, resume prompt; verifies branch/HEAD safety | ADDED |
| openjarvis-no-skip-blocker-closure | MISSING | No skill to audit blocker closure completeness | HIGH | New skill: verifies all declared blockers have explicit evidence of closure, no quiet skips | ADDED |
| openjarvis-quality-score | MISSING | No consistent quality scoring skill | MEDIUM | New skill: scores sprint on 5 dimensions, returns N/5 with per-dimension rationale | ADDED |
| openjarvis-plan4-6-mega-sprint-planning | MISSING | No skill for Plan 4–6 mega-sprint planning | LOW | New skill: decomposes Plan 4–6 goals into safe sprint sequence with ownership matrix | ADDED |
| openjarvis-plugin-mcp-risk-review | MISSING | No skill for MCP/plugin risk review before activation | HIGH | New skill: reviews proposed plugin/MCP for risk; produces ACTIVATE/DEFER/REJECT verdict | ADDED |
| openjarvis-ui-ux-product-polish-review | MISSING | No skill for Jarvis UI/UX product polish review | LOW | New skill: reviews UI components for Jarvis PA identity, consistency, polish | ADDED |

---

## 3. Slash Command Coverage

| Command | Current | Gap | Risk | Proposed | Status |
|---------|---------|-----|------|----------|--------|
| /plan-acceptance-review | MISSING | No quick command for acceptance review | HIGH | Invokes openjarvis-final-acceptance-review skill | ADDED |
| /fargate-proof | MISSING | No quick command to generate Fargate runtime proof | HIGH | Invokes openjarvis-fargate-runtime-proof skill | ADDED |
| /tauri-release-gate | MISSING | No quick command for Tauri release gate | MEDIUM | Invokes openjarvis-tauri-release-gate skill | ADDED |
| /endpoint-security-audit | MISSING | No quick command for endpoint security audit | HIGH | Invokes openjarvis-endpoint-security-audit skill | ADDED |
| /secret-scan-deep | MISSING | Existing /secret-scan covers staged files; no deep scan of logs/docs | MEDIUM | Invokes openjarvis-secret-sanitization skill on broader scope | ADDED |
| /handoff-save | MISSING | No command to save crash-safe handoff state | MEDIUM | Invokes openjarvis-handoff-continuity skill to write/update handoff docs | ADDED |
| /handoff-resume-check | MISSING | No command to verify handoff state matches repo | MEDIUM | Reads handoff files; verifies branch/HEAD/dirty state match | ADDED |
| /no-skip-audit | MISSING | No command to audit blocker closure completeness | HIGH | Invokes openjarvis-no-skip-blocker-closure skill | ADDED |
| /quality-score | MISSING | No command to produce quality score | MEDIUM | Invokes openjarvis-quality-score skill; returns N/5 | ADDED |
| /plan4-6-mega-sprint | MISSING | No command to plan/launch Plan 4–6 | LOW | Invokes plan4-6-mega-sprint-architect agent for planning only | ADDED |
| /plugin-risk-review | MISSING | No command for MCP/plugin risk assessment | HIGH | Invokes openjarvis-plugin-mcp-risk-review skill | ADDED |
| /ui-product-polish-review | MISSING | No command for UI/UX review | LOW | Invokes openjarvis-ui-ux-product-polish-review skill | ADDED |
| /post-plan2-automation-status | MISSING | No command to show full automation status | LOW | Reads all automation docs and reports current state | ADDED |
| /crash-resume | MISSING | No quick command to verify crash-resume safety and show resume prompt | MEDIUM | Reads handoff docs, verifies safety, prints RESUME_FROM_HERE | ADDED |

---

## 4. Hook Coverage

| Hook | Current | Gap | Risk | Proposed | Status |
|------|---------|-----|------|----------|--------|
| guard-no-git-add-all.sh | MISSING | Nothing blocks `git add .` or `git add -A` | HIGH | PreToolUse Bash hook: blocks git add . and git add -A with clear message | ADDED |
| guard-acceptance-label.sh | MISSING | Nothing blocks Claude from marking something ACCEPTED in a file | HIGH | PreToolUse Edit/Write hook: blocks writes of ACCEPTED/PLAN_X_ACCEPTED pattern without Bryan approval | ADDED |
| guard-credential-file-read.sh | MISSING | warn-env-access is warn-only; no block for credential file reads | MEDIUM | PreToolUse hook: blocks Read/Edit on .env, OAuth JSON, private key files | ADDED |
| remind-handoff-update.sh | MISSING | No reminder to update handoff files after commits | MEDIUM | PostToolUse Bash hook: reminds to run /handoff-save after git commit | ADDED |

---

## 5. Validation / Release Automation

| Area | Current | Gap | Risk | Proposed | Status |
|------|---------|-----|------|----------|--------|
| Full acceptance review workflow | Ad hoc | No structured acceptance review skill | HIGH | openjarvis-final-acceptance-review skill | ADDED |
| Fargate runtime proof | Manual ECS Exec | No structured proof skill | HIGH | openjarvis-fargate-runtime-proof skill | ADDED |
| Quality scoring | Informal | No consistent N/5 scoring | MEDIUM | openjarvis-quality-score skill | ADDED |
| Blocker closure audit | Manual | No audit for quiet skips | HIGH | openjarvis-no-skip-blocker-closure skill | ADDED |

---

## 6. Future Plan 4–6 Readiness

| Area | Current | Gap | Risk | Proposed | Status |
|------|---------|-----|------|----------|--------|
| Mega-sprint planning agent | MISSING | No agent for Plan 4–6 decomposition | MEDIUM | plan4-6-mega-sprint-architect agent | ADDED |
| Planning templates | MISSING | No templates for Plan 4–6 acceptance/blocker/quality | LOW | PLAN4_6_READINESS_CHECKLIST.md | ADDED |
| UI/UX product review | MISSING | No UI/UX polish review for Jarvis product | LOW | ui-ux-product-reviewer agent + skill | ADDED |
| MCP/plugin risk assessment | MISSING | No review gate for new tools | HIGH | plugin-mcp-risk-reviewer agent + skill | ADDED |

---

*Matrix updated: 2026-06-25 — all gaps addressed in POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION sprint*
