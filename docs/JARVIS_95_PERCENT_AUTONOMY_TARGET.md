# Jarvis 95% Automation Target

**Status:** Documented — not fully enabled  
**NUS phase for controlled high-autonomy:** NUS 1F (NOT STARTED)

---

## Long-Term Target

**95% automated, 5% strict policy-controlled.**

This means policy-based delegated autonomy — not unsafe unrestricted access.

- Routine safe work (local analysis, docs, validation, scorecard generation)
  becomes automatic over time via NUS phases.
- Dangerous work (deploy, external sends, secret access, self-modification)
  remains strictly policy-controlled and gated, always requiring explicit
  human approval.

---

## Current Automation Coverage (NUS 1A–1E)

| Category | NUS Phase | Status |
|----------|-----------|--------|
| Learning signals | NUS 1A | Active |
| Scorecards + recommendations | NUS 1A/1B | Active |
| Persistent recommendation queue | NUS 1C | Active |
| Safe autopilot (local dry-runs) | NUS 1C | Active |
| Failure pattern learning | NUS 1C | Active |
| Learned routing recommendations | NUS 1C | Active |
| Eval gates | NUS 1D | Active |
| Rollback enforcement | NUS 1D | Active |
| Approval workflow | NUS 1D | Active |
| Power autopilot boundary | NUS 1D | Defined (not broadly active) |
| Low-risk execution classifier | NUS 1E | Active |
| Auto-commit foundation (dry-run) | NUS 1E | Active (scaffold) |
| Controlled high-autonomy sessions | NUS 1F | NOT STARTED |
| Production autonomy | NUS 1F | NOT STARTED |

---

## What Automation Means in Practice

Automation = **policy-based delegated autonomy**, not unrestricted access.

- The system autonomously handles local analysis, scorecard generation,
  telemetry normalization, recommendation deduplication, failure summarization,
  and low-risk docs/status updates.
- Medium-risk actions (file writes, config changes) require explicit approval.
- High-risk actions (external sends, browser automation) require explicit approval.
- Dangerous actions (deploy, self-modification, auto-push, secret access) are
  permanently blocked unless NUS 1F explicitly gates them with Bryan's approval.

---

## Path to 95% (Phased)

| Phase | Target | Activation |
|-------|--------|-----------|
| NUS 1C | ~30% (safe local dry-runs) | Active |
| NUS 1D/1E | ~40% (eval-gated low-risk execution) | Active |
| NUS 1F | ~60% (controlled high-autonomy sessions) | NOT STARTED |
| Post-NUS orchestrator | ~80–95% (multi-agent, policy-supervised) | LOCKED |

---

## 5% That Remains Human-Controlled (Always)

- Production deploys (Vercel, AWS, Supabase, Stripe)
- Billing and financial actions
- Slack/email/social sends (real outbound)
- Secret access or rotation
- Governance/safety policy changes
- Auto-merge into main branch
- Any action with irreversible external effects

---

## Safety Commitment

Moving toward 95% automation does NOT mean weakening safety gates.
It means systematically proving that safe actions can be trusted and
progressively delegating them while maintaining strict gating on dangerous actions.

US13 voice remains HOLD/UNSAFE/PARKED throughout NUS 1D/1E.

---

## See Also

- `docs/JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md`
- `docs/POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md`
- `docs/NUS1C_SAFE_AUTOPILOT.md`
- `src/openjarvis/nus/autonomy_policy.py`

---

## NUS 1F Update — Controlled High-Autonomy Session Framework

NUS 1F implements the first concrete framework toward the 95% target:

### What "95% automated" means
- **Policy-controlled delegated autonomy** — not unsafe unrestricted access.
- Routine safe work is auto-allowed under active policy.
- Medium-risk work is sandboxed or approval/policy-gated.
- High-risk work is strict policy-controlled.
- Dangerous work is permanently blocked.

### Action Tier Classification (NUS 1F)
| Tier | Fraction of actions (target) | Examples |
|---|---|---|
| `auto_allowed` | ~40–50% | local_read, health_check |
| `auto_allowed_with_audit` | ~20–25% | scorecard_generation, test_run_local |
| `dry_run_only` | ~10–15% | session_create_dry_run, eval_gate_dry_run |
| `needs_approval` | ~10% | source_code_mutation, config_update |
| `strict_policy_controlled` | ~3–5% | staging_deploy_dry_run |
| `blocked` | ~5% | production_deploy, secret_access, auto_push |

### Implementation
- `src/openjarvis/nus/autonomy_action_policy.py` — 6-tier classification
- `src/openjarvis/nus/high_autonomy_session.py` — session objects
- `src/openjarvis/nus/production_gate.py` — production gate (dry-run only in NUS 1F)

### Current state
Production execution remains blocked or dry-run only. NUS 1F lays the policy and session boundary infrastructure. Real autonomy expansion happens in future sprints with explicit Bryan authorization.

See `docs/NUS1F_CONTROLLED_HIGH_AUTONOMY.md` for full specification.
