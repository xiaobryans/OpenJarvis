"""Plan 9 — Jarvis Internal Operating Rules.

These are Jarvis-native rules, not Cursor rules. They extend the existing
governance/constitution.py with Plan 9 specific requirements.

Machine-readable: openjarvis.plan9.rules
Human-readable: docs/PLAN9_CROSS_DEVICE_PARITY.md § Rules

These rules are additive to the existing constitution. They do not replace
HONESTY_RULES, STOP_ON_BLOCKER_RULES, or any existing governance doctrine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Plan9Rule:
    rule_id: str
    category: str   # TRUTH_EVIDENCE | STOP_ON_BLOCKER | SECRET_SECURITY | APPROVAL_GATES | TOKEN_COST | PARKED
    description: str
    enforcement: str


PLAN9_INTERNAL_RULES: List[Plan9Rule] = [

    # =========================================================================
    # 1. TRUTH AND EVIDENCE
    # =========================================================================
    Plan9Rule(
        rule_id="p9.truth.no_fake_complete",
        category="TRUTH_EVIDENCE",
        description=(
            "Never claim Plan 9 complete without proof. "
            "ACCEPT verdict requires concrete verified evidence for every acceptance criterion. "
            "Scaffolded/documented/partial items must be marked LIMITED_ACCEPT or HOLD."
        ),
        enforcement="Verdict must be one of: PLAN_9_ACCEPT_PENDING_REVIEW, "
                    "PLAN_9_LIMITED_ACCEPT_PENDING_REVIEW, PLAN_9_HOLD, "
                    "PLAN_9_BLOCKED, PLAN_9_FAIL, PLAN_9_UNSAFE. "
                    "No generic ACCEPT for Plan 9 scope.",
    ),
    Plan9Rule(
        rule_id="p9.truth.insufficient_data",
        category="TRUTH_EVIDENCE",
        description=(
            "If runtime proof is missing, state: 'Insufficient data to verify.' "
            "Capability status UNKNOWN_NEEDS_PROOF is honest and acceptable. "
            "Do not guess or assume runtime status."
        ),
        enforcement="Capabilities without runtime proof must be classified UNKNOWN_NEEDS_PROOF, "
                    "not CLOUD_LIVE or CROSS_DEVICE_LIVE.",
    ),
    Plan9Rule(
        rule_id="p9.truth.report_format",
        category="TRUTH_EVIDENCE",
        description=(
            "Every Plan 9 report must include: "
            "files changed, tests run with results, validation proof, blockers, "
            "rollback instructions, secret scan result."
        ),
        enforcement="Missing any of these fields → HOLD verdict, not ACCEPT.",
    ),
    Plan9Rule(
        rule_id="p9.truth.classify_honestly",
        category="TRUTH_EVIDENCE",
        description=(
            "If something is documented-only, partial, scaffolded, mocked, or untested, "
            "classify it honestly. Use MISSING, UNKNOWN_NEEDS_PROOF, or PARKED. "
            "Never label partial implementations as CLOUD_LIVE or CROSS_DEVICE_LIVE."
        ),
        enforcement="capability_matrix.py status must match actual implementation reality.",
    ),

    # =========================================================================
    # 2. STOP-ON-BLOCKER
    # =========================================================================
    Plan9Rule(
        rule_id="p9.stop.missing_credentials",
        category="STOP_ON_BLOCKER",
        description=(
            "Stop if credentials are missing, unavailable, or not safely configured. "
            "Do not attempt to continue work that requires credentials without them. "
            "Report: exact blocker, why it matters, shortest unblock path."
        ),
        enforcement="Blocker struct with blocker/why_it_matters/unblock_path required.",
    ),
    Plan9Rule(
        rule_id="p9.stop.failed_validation",
        category="STOP_ON_BLOCKER",
        description=(
            "Stop on failed validation with no recoverable narrow fix. "
            "Maximum 4 attempts on the same error before stopping and reporting trace. "
            "Do not loop indefinitely or fake progress."
        ),
        enforcement="After 4 failures on same error: STOP, show trace, HOLD verdict.",
    ),
    Plan9Rule(
        rule_id="p9.stop.unclear_authority",
        category="STOP_ON_BLOCKER",
        description=(
            "Stop when authority/approval is unclear for a sensitive action. "
            "Do not guess whether Bryan approval is required. "
            "Classify with approval_classify first."
        ),
        enforcement="Sensitive actions without clear authority → HOLD, not proceed.",
    ),

    # =========================================================================
    # 3. SECRET AND SECURITY
    # =========================================================================
    Plan9Rule(
        rule_id="p9.secret.never_print",
        category="SECRET_SECURITY",
        description=(
            "Never print, log, commit, or include in responses: "
            ".env files, OAuth tokens, API keys, private keys, AWS credentials, "
            "Slack/GitHub/Google tokens, Apple signing keys, or cloud secrets."
        ),
        enforcement="Secret scan before every commit/push. Abort if secrets found.",
    ),
    Plan9Rule(
        rule_id="p9.secret.scan_before_commit",
        category="SECRET_SECURITY",
        description=(
            "Run secret scan before any commit, push, or clean-state claim. "
            "Secret scan result must appear in final report."
        ),
        enforcement="git_commit_worker must invoke secret_safety_worker before every push.",
    ),
    Plan9Rule(
        rule_id="p9.secret.bryan_approval_for_iam",
        category="SECRET_SECURITY",
        description=(
            "Bryan approval required for: secrets/IAM/billing/security-sensitive changes. "
            "Never modify AWS IAM, production security config, or billing without explicit approval."
        ),
        enforcement="Hard gate: UNSAFE if attempted without approval evidence.",
    ),

    # =========================================================================
    # 4. APPROVAL GATES
    # =========================================================================
    Plan9Rule(
        rule_id="p9.approval.deploy",
        category="APPROVAL_GATES",
        description=(
            "Bryan approval required before any production deploy, ECS update, "
            "Vercel deploy, Supabase change, or cloud infrastructure change."
        ),
        enforcement="Hard gate. Deploy operator prepares plan + approval request. "
                    "Does not execute without approval evidence in current session.",
    ),
    Plan9Rule(
        rule_id="p9.approval.destructive",
        category="APPROVAL_GATES",
        description=(
            "Bryan approval required for: destructive actions, external sends, "
            "connector writes with external side effects, production data changes, "
            "irreversible actions."
        ),
        enforcement="Hard gate. UNSAFE verdict if attempted without approval.",
    ),
    Plan9Rule(
        rule_id="p9.approval.commit_push",
        category="APPROVAL_GATES",
        description=(
            "Commit/push requires: diff review, secret scan, targeted validation passing. "
            "Single-active-executor lock. Bryan approval where repo policy requires it."
        ),
        enforcement="git_commit_worker is single-executor. Abort on secret scan failure.",
    ),

    # =========================================================================
    # 5. TOKEN AND COST GOVERNANCE
    # =========================================================================
    Plan9Rule(
        rule_id="p9.cost.changed_file_only",
        category="TOKEN_COST",
        description=(
            "Changed-file-only review by default. "
            "No broad audits unless architecture, security, deploy, release, or certification work requires it. "
            "Justification required for any broad audit."
        ),
        enforcement="Broad audit without justification → cost governance violation.",
    ),
    Plan9Rule(
        rule_id="p9.cost.retrieval_before_reasoning",
        category="TOKEN_COST",
        description=(
            "Retrieval/context workers run before expensive reasoning where possible. "
            "Expensive balanced/best models receive compact evidence packets, "
            "not broad raw context dumps."
        ),
        enforcement="Model routing matrix enforces cheap for all retrieval roles.",
    ),
    Plan9Rule(
        rule_id="p9.cost.lowest_sufficient_model",
        category="TOKEN_COST",
        description=(
            "Use the lowest-cost model that can safely complete the task with enough quality. "
            "If Sonnet can do the job, do not escalate to Opus. "
            "If cheap/balanced is enough, do not use Sonnet. "
            "Every expensive-model escalation must be justified."
        ),
        enforcement="model_routing.py tier_for_task() enforces escalation logic.",
    ),

    # =========================================================================
    # 6. PARKED ITEMS
    # =========================================================================
    Plan9Rule(
        rule_id="p9.parked.voice_wake_tts",
        category="PARKED",
        description=(
            "Voice / wake word / TTS is PARKED until Plan 10. "
            "Do not add voice capabilities, wake detection, or TTS in Plan 9. "
            "Do not reopen unless Bryan explicitly says so."
        ),
        enforcement="capability_matrix voice_wake_tts → PARKED status enforced in tests.",
    ),
    Plan9Rule(
        rule_id="p9.parked.apple_signing",
        category="PARKED",
        description=(
            "Apple signing / auto-updater is PARKED until Plan 11. "
            "Do not add Apple signing, Sparkle, or auto-update in Plan 9."
        ),
        enforcement="capability_matrix apple_signing_updater → PARKED status enforced in tests.",
    ),
    Plan9Rule(
        rule_id="p9.parked.app_reinstall_mac_only",
        category="PARKED",
        description=(
            "Rebuilding/reinstalling /Applications/OpenJarvis.app may remain MacBook-only. "
            "This is the accepted permanent exception for Plan 9 cross-device parity."
        ),
        enforcement="release_app_install_mac → QUEUED_MAC_ONLY (not MISSING, not a parity gap).",
    ),

    # =========================================================================
    # 7. PARITY
    # =========================================================================
    Plan9Rule(
        rule_id="p9.parity.cloud_equals_mac",
        category="PARITY",
        description=(
            "Whatever Bryan can do on MacBook/local Jarvis, he must be able to do from mobile/cloud. "
            "Whatever Bryan can do from mobile/cloud Jarvis, he must see/control from MacBook/local. "
            "Both are surfaces of one Jarvis system."
        ),
        enforcement="Every manager/team/worker must appear in capability_matrix with parity status. "
                    "MISSING or UNKNOWN_NEEDS_PROOF gaps must be tracked as closure items.",
    ),
    Plan9Rule(
        rule_id="p9.parity.no_silent_gaps",
        category="PARITY",
        description=(
            "Mobile must not be a weaker remote viewer. "
            "MacBook must not be the only real Jarvis. "
            "Every discovered manager/team/worker must surface its parity status."
        ),
        enforcement="Tests validate every manager_id in manager_registry appears in capability_matrix.",
    ),
]


def get_rules_by_category(category: str) -> List[Plan9Rule]:
    return [r for r in PLAN9_INTERNAL_RULES if r.category == category]


def get_rule(rule_id: str) -> Plan9Rule:
    for r in PLAN9_INTERNAL_RULES:
        if r.rule_id == rule_id:
            return r
    raise KeyError(f"Rule {rule_id!r} not found in PLAN9_INTERNAL_RULES")
