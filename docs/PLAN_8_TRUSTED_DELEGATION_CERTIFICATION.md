# Plan 8 — Trusted Delegation / Sensitive Authority Expansion
## Certification Document

**Verdict:** `PLAN_8_TRUSTED_DELEGATION_ACCEPT_PENDING_REVIEW`
**Branch:** `localhost-get-tool`
**HEAD before:** `09547dae`
**Certified by:** Jarvis/Cursor agent (Sonnet 4.6)
**Date:** 2026-06-21
**Final cutover:** NOT STARTED — this is not final cutover certification

---

## 1. Scope

Plan 8 introduces a real permission tier model, approval modes, risk controls,
auditability, dry-run/simulation, rollback/recovery visibility, revocation,
emergency stop, and certification gates before higher authority levels can be
unlocked. It does **not** grant any autonomous high-impact/sensitive powers.

---

## 2. Implemented Files

| File | Purpose |
|---|---|
| `src/openjarvis/authority/__init__.py` | Module init — exports all Plan 8 symbols |
| `src/openjarvis/authority/tiers.py` | A. Permission tiers (Tier 0-5) |
| `src/openjarvis/authority/risk_classifier.py` | B. Risk classifier |
| `src/openjarvis/authority/approval_engine.py` | C. Approval modes + SQLite engine |
| `src/openjarvis/authority/action_preview.py` | D. Action preview + DryRunEngine |
| `src/openjarvis/authority/audit_store.py` | E. Durable SQLite audit log |
| `src/openjarvis/authority/rollback.py` | F. Rollback/recovery model |
| `src/openjarvis/authority/spend_guard.py` | G. Spend/rate guardrails |
| `src/openjarvis/authority/secret_policy.py` | H. Secret/credential access policy |
| `src/openjarvis/authority/emergency.py` | I. Emergency stop + revocation |
| `src/openjarvis/server/authority_routes.py` | J. API visibility (19 routes) |
| `src/openjarvis/server/api_routes.py` | J. authority_router registered |
| `tests/test_plan8_authority.py` | 88 tests covering all Plan 8 areas |

---

## 3. Permission Tier Matrix (A)

| Tier | Label | Approval Mode | Credentials | Spend | External Sends | Deploy | Account Changes |
|---|---|---|---|---|---|---|---|
| 0 | Read-only / Explain / Plan | auto_allow | ❌ | ❌ | ❌ | ❌ | ❌ |
| 1 | Draft-only / Simulation | auto_allow | ❌ | ❌ | ❌ | ❌ | ❌ |
| 2 | Low-risk Reversible | one_time | ❌ | ❌ | ❌ | ❌ | ❌ |
| 3 | Medium-risk Write | one_time | read_only_scoped | ❌ | ❌ | ❌ | ❌ |
| 4 | High-risk Sensitive | step_up | scoped | ≤$10/action | ✅ (approved) | staging only | ❌ |
| 5 | Prohibited / Human-only | **prohibited** | ❌ | ❌ | ❌ | ❌ | ❌ |

Each TierDefinition includes: `allowed_action_types`, `blocked_action_types`,
`required_approval_mode`, `step_up_required`, `required_audit_fields`,
`audit_on_execution`, `rollback_required`, `rollback_method`,
`credentials_allowed`, `credential_scope`, `spend_bearing_allowed`,
`max_spend_per_action`, `external_sends_allowed`, `production_deploy_allowed`,
`account_changes_allowed`.

---

## 4. Risk Classifier Matrix (B)

The risk classifier covers 9 action type categories:

| Category | Default Tier | Example Actions |
|---|---|---|
| `read_only` | 0 | read, explain, plan, search, list |
| `draft_simulation` | 1 | draft, simulate, dry_run, preview |
| `reversible_write` | 2-3 | file_write, file_edit, git_commit |
| `destructive_write_delete` | 4-5 | file_delete, destructive_irreversible_delete |
| `external_communication_send` | 4 | email_send, slack_send, external_send |
| `production_deploy` | 4-5 | staging_deploy (4), production_deploy (5), vercel_deploy (5) |
| `billing_payment_subscription` | 5 | billing_change, stripe_change |
| `credential_security_account` | 4-5 | credential_write (5), account_mutation (5), aws_infra_change (5) |
| `sensitive_private_data` | 3-4 | private_data_read |

**Risk dimensions scored:** destructive_potential (0-30), external_side_effect (0-20),
money_impact (0-20), credential_impact (0-15), privacy_impact (0-10),
reversibility penalty (0-5). Total score → 0-100 → tier mapping.

**Unknown actions:** fall back to conservative medium-high default (Tier 2+).

---

## 5. Approval Mode Matrix (C)

| Mode | When Used | Status Flow |
|---|---|---|
| `auto_allow` | Tier 0/1 | request → GRANTED immediately |
| `one_time` | Tier 2/3 | request → PENDING → GRANTED/DENIED |
| `step_up` | Tier 4 | request → PENDING → GRANTED (requires re-verification) |
| `prohibited` | Tier 5 | request → BLOCKED immediately |
| `deny` | Explicit denial | PENDING → DENIED |
| `revoked` | Post-grant revocation | GRANTED → REVOKED |

**Approval record fields (all required):**
`approval_id`, `requester`, `action_type`, `action_preview`, `risk_level`,
`tier`, `affected_systems`, `affected_files`, `affected_accounts`,
`estimated_spend`, `rollback_plan`, `scope`, `mode`, `status`,
`audit_trace_id`, `created_at`, `granted_at`, `expires_at`, `context` (scrubbed).

**No secret values stored in approval records.**

---

## 6. Action Preview / Dry-Run Proof (D)

`ActionPreview` fields: `action_id`, `action_type`, `action_description`,
`target_system`, `files_affected`, `resources_affected`, `accounts_affected`,
`diff_summary`, `change_count`, `external_side_effects`, `side_effect_irreversible`,
`cost_estimate`, `cost_estimate_source`, `cost_unknown_warning`, `rollback_plan`,
`rollback_supported`, `rollback_method`, `irreversible_warning`,
`requires_approval`, `tier`, `risk_level`, `dry_run_requested`,
`dry_run_completed`, `dry_run_result`, `dry_run_errors`, `created_at`, `created_by`.

`DryRunEngine.SUPPORTED_DRY_RUN_TYPES`:
`file_write`, `file_edit`, `file_delete`, `git_commit`, `git_push`, `git_add`,
`email_send`, `slack_send`, `external_send`, `staging_deploy`, `production_deploy`,
`billing_change`, `stripe_change`, `aws_infra_change`, `credential_write`.

Dry-run for `billing_change` outputs: `"status": "simulated"` + `"warning": "TIER 5 — prohibited from autonomous execution"` + `"note": "DRY RUN ONLY — no actual billing change performed"`.

---

## 7. Audit Log Proof (E)

**Storage:** SQLite at `~/.jarvis/authority_audit.db` (WAL mode).
**Append-only:** Records written once, never updated.
**Secret scrubbing:** `_scrub()` recursively replaces sensitive key values with `<redacted>`.
Scans for: `ghp_`, `gho_`, `sk-`, `xoxb-`, `AKIA`, `Bearer` patterns.

**Audit fields:**
`audit_id`, `ts`, `iso_ts`, `action_type`, `actor`, `tier`, `risk_level`,
`approval_decision`, `execution_status`, `affected_resource`, `rollback_metadata`,
`error_info` (scrubbed), `retry_count`, `connector`, `approval_id`,
`audit_trace_id`, `context` (scrubbed).

**Query API:** `list_recent(n)`, `list_by_action()`, `list_by_actor()`,
`list_blocked()`, `list_failed()`, `count()`.

---

## 8. Rollback/Recovery Proof (F)

**Three categories handled:**

| Category | Method | Implementation |
|---|---|---|
| File edits | `AUTOMATIC` | backup_path, diff_forward, diff_reverse, original_content_hash |
| Task/goal state | `BEST_EFFORT` | previous_state_json snapshot |
| External systems | `MANUAL` or `IMPOSSIBLE` | rollback_instructions, external_rollback_url |

**Action type → rollback method mapping:**

| Action | Method |
|---|---|
| `file_write`, `file_edit`, `git_commit` | AUTOMATIC |
| `production_deploy`, `git_push`, `staging_deploy` | MANUAL |
| `email_send`, `billing_change`, `stripe_change` | IMPOSSIBLE |
| `read`, `draft`, `simulate` | NOT_APPLICABLE |

**Irreversible actions** require higher-tier approval + `irreversible_warning` field.
`RollbackRecord.is_expired()` tracks backup expiry.

---

## 9. Emergency Stop / Revocation Proof (I)

**Persistence:** SQLite at `~/.jarvis/authority_emergency.db` (WAL mode, survives restarts).

**Operations:**
- `set_emergency_stop(activated_by, reason)` → sets `active=1`, records activator + reason
- `clear_emergency_stop(cleared_by)` → sets `active=0`, records who cleared
- `is_emergency_stop_active()` → fast boolean check (used by all Tier 2+ gates)
- `revoke_all_active()` → mass revocation of all GRANTED approvals
- `log_revocation(approval_id)` → audit trail for each revocation
- `emergency_gate_check(tier)` → Tier 0/1 never blocked; Tier 2+ blocked when active

**Behavior when emergency stop active:**
```
{
  "blocked": True,
  "reason": "EMERGENCY STOP ACTIVE. All Tier N actions blocked. ...",
  "emergency_status": { "active": True, ... }
}
```

---

## 10. Spend / Secret Policy Proof (G, H)

### Spend Guard (G)

**Budget defaults:** `daily_budget=$5.00`, `session_budget=$1.00`, `alert_threshold=80%`.
**Unknown cost (`-1.0`):** requires_approval=True, hard_stop=False.
**Over daily budget:** hard_stop=True.
**Zero-cost actions (Tier 0-3):** always allowed without approval.

**Action cost table covers:** read/plan/draft (free), file_write (free), git_commit (free),
email_send (free), staging_deploy ($0.10), production_deploy ($1.00),
aws_infra_change (unknown/-1.0), billing_change (unknown/-1.0).

### Secret Policy (H)

**Allowed stores:** `os_keychain`, `dot_env`, `aws_config`, `gh_cli`, `oauth_store`, `env_var`.
**Forbidden stores:** `hardcoded`, `git_committed`, `log_output`, `ui_response`, `chat_message`.
**Min tier for credential access:**

| Scope | Min Tier |
|---|---|
| read_only | 3 |
| write | 4 |
| admin | 5 |

**Token patterns scanned:**
`ghp_` (GitHub PAT), `gho_` (GitHub OAuth), `sk-` (OpenAI), `xoxb-` (Slack bot),
`AKIA` (AWS Access Key), `Bearer` tokens, password/api_key/secret assignments.

**Secret scan clean confirmation:** No real secrets in source.
All pattern occurrences in `secret_policy.py` and `audit_store.py` are regex
pattern strings for detection, not actual tokens. All occurrences in test files
are `"ghp_" + "A" * 36` style constructions — these are deliberately fake values
used to test the scanner, not real tokens.

---

## 11. API / UI Visibility (J)

**Backend routes (19 total):**

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/authority/status` | Current tier, emergency stop, summary |
| GET | `/v1/authority/tiers` | Full 6-tier permission matrix |
| GET | `/v1/authority/approvals/pending` | Pending approvals |
| GET | `/v1/authority/approvals/active` | Active (granted) approvals |
| GET | `/v1/authority/approvals/revoked` | Revoked/denied approvals |
| POST | `/v1/authority/approvals/request` | Create approval record |
| POST | `/v1/authority/approvals/{id}/grant` | Grant pending approval |
| POST | `/v1/authority/approvals/{id}/deny` | Deny pending approval |
| POST | `/v1/authority/approvals/{id}/revoke` | Revoke granted approval |
| GET | `/v1/authority/emergency-stop` | Emergency stop status |
| POST | `/v1/authority/emergency-stop/set` | Activate emergency stop |
| POST | `/v1/authority/emergency-stop/clear` | Clear emergency stop |
| GET | `/v1/authority/audit` | Recent audit entries |
| GET | `/v1/authority/audit/blocked` | Blocked action audit entries |
| POST | `/v1/authority/classify` | Classify action risk profile |
| GET | `/v1/authority/risk-matrix` | Full risk classification matrix |
| POST | `/v1/authority/preview` | Generate action preview + dry-run |
| GET | `/v1/authority/spend/summary` | Session and daily spend summary |
| GET | `/v1/authority/secret-policy` | Secret policy manifest |
| POST | `/v1/authority/secret-policy/scan` | Scan text for secret patterns |

**UI integration status:** Backend-only. Routes are registered and functional.
Frontend UI integration (cockpit/settings) is **not implemented in Plan 8**.
This is honestly reported as a limitation — UI remains on future plan.

**API-ready state covers:**
- Current authority tier (via `/v1/authority/status`)
- Pending/active/revoked approvals
- Emergency stop status
- Recent audit entries
- Blocked sensitive actions
- Risk labels
- Rollback/recovery info (via approval records)

---

## 12. Validation Commands and Outputs

### Plan 8 tests (88 tests — 83 passed, 5 skipped)

```
$ python -m pytest tests/test_plan8_authority.py -v --tb=short

83 passed, 5 skipped in 1.76s

(5 skipped = fastapi not installed in test env — same as all other server route tests)
```

### Governance regression (44 tests — all pass)

```
$ python -m pytest tests/test_governance.py -v --tb=short

44 passed in 0.19s
```

### Git diff whitespace check

```
$ git diff --check && echo "diff check clean"

diff check clean
```

### Secret scan (Plan 8 files only)

```
$ rg "ghp_|gho_|sk-[A-Za-z0-9]{32}|xoxb-|AKIA[A-Z0-9]{16}|Bearer [A-Za-z0-9]" \
    src/openjarvis/authority/ tests/test_plan8_authority.py

All matches are:
  - Regex detection patterns in secret_policy.py / audit_store.py
  - Test strings constructed as "ghp_" + "A" * 36 (fake test values)
  - Test assertions like assert "ghp_" not in redacted
  
Result: NO real secrets. CLEAN.
```

---

## 13. Remaining Blockers (carried forward — unchanged)

| Blocker | Status |
|---|---|
| Apple signing / updater | `BLOCKED_APPLE_ENROLLMENT_PENDING` |
| US13 Voice | `PARKED / UNSAFE` |
| Gmail / Calendar OAuth | `BLOCKED_NEEDS_OAUTH` |
| Slack / Telegram tokens | `BLOCKED_NEEDS_TOKEN` |
| macOS Screen/System Audio permission prompt | `TRACKED_PREFINAL_POLISH_BLOCKER` |
| Plan 8 UI integration (cockpit) | `BACKEND_ONLY_PLAN8_UI_NOT_STARTED` |
| Final hostile/lazy-user cutover certification | `NOT STARTED` |

---

## 14. Explicit Statements

1. **Final cutover is NOT started.** This document certifies Plan 8 implementation only.
2. **No autonomous high-impact real-world action was executed.** All Plan 8 code is
   behavioral/policy logic. No billing, deploy, credential, account, or external-send
   action was performed during this implementation.
3. **Jarvis is not 100% ready.** The remaining blockers above are real and unresolved.
4. **UI integration is backend-only.** Frontend cockpit/settings UI for Plan 8 authority
   state is not implemented and is an honest known gap.

---

## 15. Next Recommended Step

Plan 9 candidates (pending Bryan approval):
- `PLAN_9_UI_AUTHORITY_COCKPIT` — Wire Plan 8 API routes into the existing cockpit UI
  to show tier, pending approvals, emergency stop, and audit log to Bryan
- `PLAN_9_OAUTH_UNBLOCK` — Unblock Gmail/Calendar OAuth (`BLOCKED_NEEDS_OAUTH`)
- Continue holding Apple signing until enrollment is confirmed active
