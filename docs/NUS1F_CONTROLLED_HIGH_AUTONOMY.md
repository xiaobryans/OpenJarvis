# NUS 1F — Controlled High-Autonomy Session Framework

**Sprint:** NUS 1F  
**Accepted at:** TBD (pending validation pass)  
**Prior sprint:** NUS 1D + 1E ACCEPT at `43591f5e`

---

## Summary

NUS 1F implements the policy-based controlled high-autonomy session framework targeting Bryan's long-term goal of **95% automated, 5% strict policy-controlled** Jarvis operation.

**95% automation does NOT mean unsafe unrestricted access.**  
It means policy-based delegated autonomy with explicit boundaries, scope constraints, risk gates, budget limits, rollback requirements, kill switch, audit logs, blocked dangerous categories, and a strict production gate.

---

## What NUS 1F Adds

| Component | File | Purpose |
|---|---|---|
| High-Autonomy Session Manager | `nus/high_autonomy_session.py` | Explicit time-limited sessions with TTL, scope, budget, kill switch |
| Autonomy Action Policy | `nus/autonomy_action_policy.py` | 95% automation policy — 6-tier action classification |
| Production Gate | `nus/production_gate.py` | Production safety gate (dry-run only in NUS 1F) |
| Structured Decision Records | `nus/decision_record.py` | No raw CoT — evidence-based records for all hierarchy levels |

---

## 1. Founder Override Session Framework

### Session Object

Every high-autonomy session requires:

| Field | Description |
|---|---|
| `session_id` | UUID |
| `created_at` | Unix timestamp |
| `expires_at` | Unix timestamp (TTL enforced — no indefinite sessions) |
| `owner` | Session owner identity |
| `requested_profile` | Profile requested |
| `active_profile` | Profile activated |
| `allowed_domains` | Restricted domains |
| `allowed_action_types` | Explicit allow list |
| `blocked_action_types` | Explicit block list (merged with permanently blocked) |
| `allowed_repos_or_paths` | Scope restriction |
| `cost_budget` | Max cost in this session |
| `token_budget` | Max tokens |
| `time_budget` | Max wall time |
| `risk_ceiling` | Max risk tier allowed |
| `tool_policy` | Tool-level constraints |
| `validation_policy` | Validation requirements |
| `rollback_policy` | Rollback plan reference |
| `audit_log_id` | Audit log UUID |
| `kill_switch_state` | `off` or `on` |
| `status` | `draft`/`active`/`expired`/`revoked`/`blocked`/`completed` |
| `reason` | Human-readable rationale |
| `structured_decision_record` | Decision record (no raw CoT) |

### Session Lifecycle

```
draft → active → expired (TTL)
              → revoked (explicit)
              → blocked (kill switch)
              → completed (scope exhausted)
```

- Sessions must be explicitly created (`draft`) and then activated.
- TTL is mandatory — maximum 30 days, minimum >0 seconds.
- No indefinite founder override.

### Kill Switch

- Global kill switch (`activate_kill_switch()`) blocks ALL active sessions.
- Per-session kill switch available.
- Kill switch can be deactivated by owner only.

---

## 2. Controlled High-Autonomy Profiles

| Profile | Description |
|---|---|
| `manual` | All actions require human approval |
| `safe_autopilot` | Local read/analysis/validation auto-allowed |
| `power_autopilot` | Local ops + file writes (audited); sends/browser/secrets gated |
| `founder_override_session` | Session-level expanded permissions; still gated for risky ops |
| `production_restricted` | Read-only; all mutations blocked; not session-activatable in NUS 1F |

---

## 3. 95% Automation Policy Model

### Action Tiers

| Tier | Description | Example actions |
|---|---|---|
| `auto_allowed` | Routine safe — no approval needed | `local_read`, `health_check` |
| `auto_allowed_with_audit` | Auto but mandatory audit log | `scorecard_generation`, `telemetry_normalization` |
| `dry_run_only` | Can run as dry-run, no real mutation | `recommendation_dry_run`, `production_gate_dry_run` |
| `needs_approval` | Explicit approval before execution | `medium_file_write`, `source_code_mutation` |
| `strict_policy_controlled` | High-risk — explicit policy gate required | `staging_deploy_dry_run`, `governance_policy_update_dry_run` |
| `blocked` | Permanently blocked — no policy can override | `production_deploy`, `auto_push`, `secret_access` |

### Permanently Blocked Categories

The following are permanently blocked — no session policy, approval, or model tier can unblock them in NUS 1F:

- production_deploy
- payment_financial_action
- destructive_delete
- secret_access, secret_mutation
- auth_security_change, safety_governance_change
- public_posting
- real_slack_send, real_email_send, real_social_send
- merge_to_main
- public_release, notarization
- self_modifying_autonomy_logic
- auto_push, auto_merge, auto_deploy
- external_provider_setup, browser_account_setup

### Model Tier Constraints

Cheap models cannot approve critical or strict-policy actions.

| Tier | Minimum model |
|---|---|
| `auto_allowed` | Any |
| `auto_allowed_with_audit` | Any |
| `dry_run_only` | standard_model |
| `needs_approval` | standard_model |
| `strict_policy_controlled` | premium_model |
| `blocked` | No model — permanently blocked |

---

## 4. Production Gate

### NUS 1F Status

**Production execution is BLOCKED or DRY-RUN ONLY in NUS 1F.**  
Real deploys do not execute. Auto-push and auto-merge are permanently blocked.

### Required Preconditions (for future gate pass)

1. Explicit gate object with owner authorization
2. Staging/safe preconditions verified
3. Rollback plan present
4. Validation plan present
5. Audit log reference
6. Risk review completed
7. Cost/budget check passed
8. No secret leakage
9. Kill switch available and off
10. Non-production environment (staging or local)

Even with all preconditions met, NUS 1F returns `dry_run_only` — never approved.

---

## 5. Structured Decision Records

All autonomy/session decisions emit structured decision records.

### Schema

| Field | Description |
|---|---|
| `record_id` | UUID |
| `created_at` | Timestamp |
| `schema_version` | Schema version |
| `decision` | `allowed`/`blocked`/`revoked`/`escalated`/`dry_run` |
| `reason` | Machine-readable reason code |
| `rationale` | Human-readable summary (structured, not CoT) |
| `session_id` | Associated session |
| `action_type` | What was evaluated |
| `hierarchy_level` | `jarvis_pa`/`cos_gm`/`manager`/`worker`/`validator`/`governance` |
| `agent_metadata` | Metadata/contract fields (no hardcoded names) |
| `risk_level` | `low`/`medium`/`high`/`blocked` |
| `cost_estimate` | Estimated cost |
| `token_estimate` | Estimated tokens |
| `validation_evidence` | Validation results |
| `rollback_evidence` | Rollback plan/evidence |
| `context_evidence` | Task context |
| `nus_learning_tags` | NUS learning tags |
| `policy_reference` | Governing policy |
| `blocking_reason` | Populated when blocked |
| `escalation_target` | Where to escalate |
| `no_raw_chain_of_thought` | Always `True` |

**`raw_chain_of_thought` field is intentionally absent from the schema.**

---

## 6. NUS Applies to All Hierarchy Levels

NUS (Next-generation Upgrade System) is NOT Jarvis PA only.

NUS applies to:
- **Jarvis PA** — personal assistant decisions
- **COS/GM** — chief-of-staff and general manager decisions
- **Domain Managers** — manager-level routing and delegation
- **Workers** — execution-level decisions
- **Validators** — validation pass/fail decisions
- **Governance** — policy gate decisions

Structured decision records use `hierarchy_level` field to tag which level emitted each record. NUS learns from all levels through telemetry, structured decision records, scorecards, failure patterns, routing recommendations, and autonomy policy.

---

## 7. Dynamic Activation Policy

**No fixed worker-count formulas.**

Activation principles:
- Activate as many managers/workers as evidence justifies
- Prefer minimum sufficient team
- Expand only based on evidence
- Every activation needs rationale
- Every skipped relevant manager/worker should have rationale when useful

The full manager/worker orchestrator is **NOT implemented in NUS 1F** (locked for post-NUS company-grade orchestrator). Only policy/docs/test scaffolding for readiness is added here.

---

## 8. Duplicate/Overwrite Prevention

Before NUS 1F was built, existing files were inspected:

| Existing | NUS 1F action |
|---|---|
| `autonomy_policy.py` (NUS 1B) | Extended by adding `autonomy_action_policy.py` — not replaced |
| `power_autopilot.py` (NUS 1D) | Not modified — NUS 1F adds sessions on top |
| `execution_classifier.py` (NUS 1E) | Not modified — different classifier |
| `safe_autopilot.py` (NUS 1C) | Not modified |

New files were only created where a proven gap existed:
- `high_autonomy_session.py` — session manager (no existing equivalent)
- `autonomy_action_policy.py` — 6-tier policy (complements existing policy)
- `production_gate.py` — production gate (no existing equivalent)
- `decision_record.py` — structured decision record schema (no existing equivalent)

---

## 9. Seamless Integration

NUS 1F integrates with all existing Jarvis systems:

| System | Integration |
|---|---|
| Capability Registry | 3 NUS 1F capability IDs added |
| Event Log | 10 NUS 1F event type constants added |
| Doctor/Readiness | `check_nus1f_high_autonomy` added (21 sub-checks) |
| NUS Routes | 8 NUS 1F routes added (all read-only or dry-run) |
| NUS `__init__.py` | All NUS 1F public symbols exported |

---

## 10. Routes

All NUS 1F routes are read-only or dry-run. No real execution.

| Route | Method | Purpose |
|---|---|---|
| `/v1/nus/high-autonomy/status` | GET | Framework status |
| `/v1/nus/high-autonomy/session/dry-run-create` | POST | Create session (dry-run) |
| `/v1/nus/high-autonomy/session/evaluate-dry-run` | POST | Evaluate action in session |
| `/v1/nus/high-autonomy/session/revoke-dry-run` | POST | Revoke session |
| `/v1/nus/high-autonomy/policy/status` | GET | 95% automation policy |
| `/v1/nus/production-gate/status` | GET | Production gate status |
| `/v1/nus/production-gate/evaluate-dry-run` | POST | Gate evaluation (dry-run) |
| `/v1/nus/decision-records/dry-run` | POST | Create decision record |

---

## 11. Capabilities

| Capability ID | Status | Notes |
|---|---|---|
| `nus1f_controlled_high_autonomy` | `ready` | Session framework, policy eval, dry-run, audit, strict gates |
| `nus1f_founder_override_sessions` | `needs_approval` | Medium/high-risk needs approval; dangerous blocked |
| `nus1f_production_policy_gate` | `ready` | Dry-run evaluation; no real execution |

---

## 12. Safety Proof

- No production deploys execute.
- No real external sends (Slack/email/social).
- No secret access, logging, or commits.
- No auto-push, auto-merge.
- No self-modification of safety/governance logic.
- No approval bypass.
- Cheap models cannot approve critical actions.
- Kill switch available at all times.
- Session TTL enforced — no indefinite override.
- All dangerous categories permanently blocked.
- US13 voice: **HOLD/UNSAFE/PARKED**.

---

## 13. Post-NUS Company Orchestrator

**Remains LOCKED.** Not implemented in NUS 1F.

The 100+ worker company-grade hierarchical orchestrator is explicitly locked for a future sprint. NUS 1F only provides the policy scaffolding, session boundary framework, and structured decision record schema that the post-NUS orchestrator will build on.

---

## NUS Status Summary

| Sprint | Status |
|---|---|
| NUS 1A | ACCEPT at `52ccbe0e` |
| NUS 1B | ACCEPT at `ba059ddd` |
| NUS 1C | ACCEPT at `25e77763` |
| NUS 1D + 1E | ACCEPT at `43591f5e` |
| NUS 1F | Implemented — pending ACCEPT |
| Post-NUS orchestrator | LOCKED |
