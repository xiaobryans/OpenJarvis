"""Plan 8 — Action Preview and Dry-Run.

For high-impact actions, Jarvis must produce a full action preview before
execution. Dry-run/simulation is supported for sensitive actions where feasible.

ActionPreview captures:
  - exact planned action
  - target system/files/accounts
  - diff or summary of changes
  - expected external side effects
  - cost/spend estimate
  - rollback/recovery plan
  - what requires human approval
  - tier and risk level
  - dry-run result (if simulated)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.authority.tiers import AuthorityTier


# ---------------------------------------------------------------------------
# ActionPreview
# ---------------------------------------------------------------------------


@dataclass
class ActionPreview:
    """Complete preview of a proposed high-impact action.

    Created before execution. Used as the approval request payload
    so the approver can see exactly what will happen.
    """

    action_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    action_type: str = ""
    action_description: str = ""        # Human-readable planned action

    # Target
    target_system: str = ""             # e.g. "local_filesystem", "github", "stripe"
    files_affected: List[str] = field(default_factory=list)
    resources_affected: List[str] = field(default_factory=list)
    accounts_affected: List[str] = field(default_factory=list)

    # Change summary
    diff_summary: str = ""              # git-style diff or prose summary
    change_count: int = 0

    # Side effects
    external_side_effects: List[str] = field(default_factory=list)
    side_effect_irreversible: bool = False

    # Cost
    cost_estimate: float = 0.0
    cost_estimate_source: str = ""      # "known" | "estimated" | "unknown"
    cost_unknown_warning: str = ""

    # Rollback
    rollback_plan: str = ""
    rollback_supported: bool = True
    rollback_method: str = ""           # "automatic" | "manual" | "impossible"
    irreversible_warning: str = ""

    # Approval
    requires_approval: bool = True
    tier: int = 0                       # AuthorityTier value
    risk_level: str = "low"
    approval_id: Optional[str] = None

    # Dry-run
    dry_run_requested: bool = False
    dry_run_completed: bool = False
    dry_run_result: Optional[Dict[str, Any]] = None
    dry_run_errors: List[str] = field(default_factory=list)

    # Metadata
    created_at: float = field(default_factory=time.time)
    created_by: str = ""

    def requires_human_approval(self) -> bool:
        """Return True if this action requires explicit human approval."""
        return self.tier >= AuthorityTier.TIER_2.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "action_description": self.action_description,
            "target_system": self.target_system,
            "files_affected": self.files_affected,
            "resources_affected": self.resources_affected,
            "accounts_affected": self.accounts_affected,
            "diff_summary": self.diff_summary,
            "change_count": self.change_count,
            "external_side_effects": self.external_side_effects,
            "side_effect_irreversible": self.side_effect_irreversible,
            "cost_estimate": self.cost_estimate,
            "cost_estimate_source": self.cost_estimate_source,
            "cost_unknown_warning": self.cost_unknown_warning,
            "rollback_plan": self.rollback_plan,
            "rollback_supported": self.rollback_supported,
            "rollback_method": self.rollback_method,
            "irreversible_warning": self.irreversible_warning,
            "requires_approval": self.requires_approval,
            "tier": self.tier,
            "risk_level": self.risk_level,
            "approval_id": self.approval_id,
            "dry_run_requested": self.dry_run_requested,
            "dry_run_completed": self.dry_run_completed,
            "dry_run_result": self.dry_run_result,
            "dry_run_errors": self.dry_run_errors,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "requires_human_approval": self.requires_human_approval(),
        }


# ---------------------------------------------------------------------------
# DryRunEngine
# ---------------------------------------------------------------------------


class DryRunEngine:
    """Executes a dry-run/simulation for supported action types.

    Dry runs do NOT execute external side effects. They:
    - Validate inputs and preconditions
    - Compute the expected diff/change set
    - Estimate cost
    - Report what would happen without doing it

    For irreversible or external-send actions, the dry run generates a
    detailed preview but confirms nothing is actually executed.
    """

    SUPPORTED_DRY_RUN_TYPES = frozenset({
        "file_write", "file_edit", "file_delete",
        "git_commit", "git_push", "git_add",
        "email_send", "slack_send", "external_send",
        "staging_deploy", "production_deploy",
        "billing_change", "stripe_change",
        "aws_infra_change", "credential_write",
    })

    def simulate(
        self,
        preview: ActionPreview,
        *,
        force: bool = False,
    ) -> ActionPreview:
        """Run dry-run simulation for the given preview.

        Updates preview.dry_run_result and preview.dry_run_completed.
        Does NOT execute the actual action.
        """
        preview.dry_run_requested = True

        if preview.action_type.lower() not in self.SUPPORTED_DRY_RUN_TYPES and not force:
            preview.dry_run_result = {
                "status": "not_supported",
                "reason": (
                    f"Dry-run not implemented for action type '{preview.action_type}'. "
                    "Action preview is available but simulation is not supported."
                ),
            }
            preview.dry_run_completed = False
            return preview

        # Simulate each supported type
        result = self._simulate_action(preview)
        preview.dry_run_result = result
        preview.dry_run_completed = result.get("status") == "simulated"
        return preview

    def _simulate_action(self, preview: ActionPreview) -> Dict[str, Any]:
        action = preview.action_type.lower()

        if action in ("file_write", "file_edit"):
            return {
                "status": "simulated",
                "what_would_happen": (
                    f"Would write/edit {len(preview.files_affected)} file(s): "
                    f"{preview.files_affected[:5]}"
                ),
                "diff_preview": preview.diff_summary or "(no diff provided)",
                "rollback_available": preview.rollback_supported,
                "external_side_effects": "none",
                "estimated_cost": 0.0,
            }

        if action in ("git_commit", "git_add"):
            return {
                "status": "simulated",
                "what_would_happen": (
                    f"Would stage/commit {len(preview.files_affected)} file(s). "
                    "No push performed."
                ),
                "diff_preview": preview.diff_summary or "(no diff provided)",
                "external_side_effects": "none (local only)",
                "estimated_cost": 0.0,
            }

        if action == "git_push":
            return {
                "status": "simulated",
                "what_would_happen": (
                    "Would push commits to remote. External side effect: YES. "
                    f"Target: {preview.target_system}"
                ),
                "external_side_effects": "push to remote repository",
                "estimated_cost": 0.0,
                "note": "DRY RUN ONLY — no actual push performed",
            }

        if action in ("email_send", "slack_send", "external_send"):
            return {
                "status": "simulated",
                "what_would_happen": (
                    f"Would send to: {preview.accounts_affected or preview.resources_affected}. "
                    "External side effect: YES. Irreversible once sent."
                ),
                "external_side_effects": "outbound message sent",
                "estimated_cost": 0.0,
                "note": "DRY RUN ONLY — no actual send performed",
                "irreversible_warning": preview.irreversible_warning,
            }

        if action in ("staging_deploy", "production_deploy", "vercel_deploy"):
            return {
                "status": "simulated",
                "what_would_happen": (
                    f"Would deploy to {preview.target_system}. "
                    f"Files: {len(preview.files_affected)}. "
                    f"Est. cost: ${preview.cost_estimate:.2f}"
                ),
                "external_side_effects": f"deploy to {preview.target_system}",
                "estimated_cost": preview.cost_estimate,
                "note": "DRY RUN ONLY — no actual deploy performed",
            }

        if action in ("billing_change", "stripe_change"):
            return {
                "status": "simulated",
                "what_would_happen": (
                    f"Would modify billing/subscription for: {preview.accounts_affected}. "
                    f"Est. financial impact: ${preview.cost_estimate:.2f}"
                ),
                "external_side_effects": "billing/subscription change",
                "estimated_cost": preview.cost_estimate,
                "warning": "TIER 5 — prohibited from autonomous execution",
                "note": "DRY RUN ONLY — no actual billing change performed",
            }

        if action in ("aws_infra_change", "credential_write"):
            return {
                "status": "simulated",
                "what_would_happen": (
                    f"Would modify infrastructure/credentials for: {preview.accounts_affected}. "
                    "HIGH RISK."
                ),
                "external_side_effects": "infrastructure/credential change",
                "warning": "TIER 5 — prohibited from autonomous execution",
                "note": "DRY RUN ONLY — no actual change performed",
            }

        return {
            "status": "simulated",
            "what_would_happen": f"Would execute: {preview.action_type}",
            "note": "Generic dry-run — no actual execution performed",
        }


# ---------------------------------------------------------------------------
# Preview builder helper
# ---------------------------------------------------------------------------


def build_preview(
    action_type: str,
    *,
    description: str = "",
    target_system: str = "",
    files: Optional[List[str]] = None,
    resources: Optional[List[str]] = None,
    accounts: Optional[List[str]] = None,
    diff_summary: str = "",
    external_side_effects: Optional[List[str]] = None,
    cost_estimate: float = 0.0,
    cost_estimate_source: str = "unknown",
    rollback_plan: str = "",
    rollback_supported: bool = True,
    rollback_method: str = "manual",
    tier: int = 0,
    risk_level: str = "low",
    created_by: str = "",
    run_dry_run: bool = False,
) -> ActionPreview:
    """Convenience builder for an ActionPreview.

    If run_dry_run=True, automatically simulates the action.
    """
    preview = ActionPreview(
        action_type=action_type,
        action_description=description or action_type,
        target_system=target_system,
        files_affected=files or [],
        resources_affected=resources or [],
        accounts_affected=accounts or [],
        diff_summary=diff_summary,
        change_count=len(files or []),
        external_side_effects=external_side_effects or [],
        side_effect_irreversible=rollback_method == "impossible",
        cost_estimate=cost_estimate,
        cost_estimate_source=cost_estimate_source,
        cost_unknown_warning=(
            "Cost is unknown — manual review required before execution."
            if cost_estimate_source == "unknown" and tier >= 3
            else ""
        ),
        rollback_plan=rollback_plan,
        rollback_supported=rollback_supported,
        rollback_method=rollback_method,
        irreversible_warning=(
            f"Action '{action_type}' is IRREVERSIBLE. Explicit human approval required."
            if rollback_method == "impossible"
            else ""
        ),
        requires_approval=tier >= AuthorityTier.TIER_2.value,
        tier=tier,
        risk_level=risk_level,
        created_by=created_by,
    )

    if run_dry_run:
        engine = DryRunEngine()
        preview = engine.simulate(preview)

    return preview


__all__ = [
    "ActionPreview",
    "DryRunEngine",
    "build_preview",
]
