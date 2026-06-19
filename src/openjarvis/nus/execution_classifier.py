"""NUS 1E — Low-Risk Execution Classifier.

Classifies actions into risk tiers based on:
  - action metadata (action_type, tool_requirements, file_targets)
  - risk level
  - task category
  - file type and scope
  - agent/worker metadata (evaluated by metadata/contract, not hardcoded names)

This classifier is NOT tied to any specific current agent name.
It evaluates by action type, risk, tool requirements, capability metadata,
validation evidence, and agent metadata contracts — supporting future
agents/workers without requiring code changes.

Classification results:
  - SAFE_LOCAL_DRY_RUN: safe local read/analysis — auto-allowed
  - SAFE_DOCS_METADATA: docs/test metadata/internal status — low-risk, potentially auto
  - MEDIUM_FILE_WRITE: file write with audit — needs approval
  - HIGH_EXTERNAL: external send / browser / provider — needs approval
  - BLOCKED_DANGEROUS: deploy/secret/self_mod/push/merge — permanently blocked

Hard safety constraints:
  - No hardcoding of specific agent names.
  - Classification based on metadata/contract-driven inputs.
  - No self-modification, no deploy, no auto-push.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

logger = logging.getLogger(__name__)

NUS1E_CLASSIFIER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Classification tiers
# ---------------------------------------------------------------------------

TIER_SAFE_LOCAL_DRY_RUN = "safe_local_dry_run"
TIER_SAFE_DOCS_METADATA = "safe_docs_metadata"
TIER_MEDIUM_FILE_WRITE = "medium_file_write"
TIER_HIGH_EXTERNAL = "high_external"
TIER_BLOCKED_DANGEROUS = "blocked_dangerous"

# ---------------------------------------------------------------------------
# Action type mappings (metadata-driven, not agent-name-driven)
# ---------------------------------------------------------------------------

_SAFE_LOCAL_ACTIONS: FrozenSet[str] = frozenset({
    "local_read", "local_analysis", "local_validation",
    "validation_planning", "scorecard_generation",
    "telemetry_normalization", "failure_pattern_summarization",
    "recommendation_deduplication", "dry_run_recommendation_execution",
    "safe_local_status_snapshot",
})

_SAFE_DOCS_ACTIONS: FrozenSet[str] = frozenset({
    "docs_write",          # docs-only file write (e.g. .md files in docs/)
    "test_metadata_update", # test metadata/fixture update only
    "internal_status_write", # internal status JSON in safe state path
    "changelog_update",
    "readme_update",
})

_MEDIUM_RISK_ACTIONS: FrozenSet[str] = frozenset({
    "file_write",
    "config_change",
    "dependency_update",
    "package_install",
    "connector_setup",
    "account_auth_change",
})

_HIGH_RISK_ACTIONS: FrozenSet[str] = frozenset({
    "external_provider_setup",
    "browser_automation",
    "external_send",
})

_BLOCKED_ACTIONS: FrozenSet[str] = frozenset({
    "self_modification",
    "code_edit",
    "auto_push",
    "auto_merge",
    "deploy",
    "secret_access",
    "safety_policy_change",
    "destructive_delete",
    "production_action",
    "payment_action",
    "financial_action",
})

# File extension patterns that indicate safe docs/metadata
_SAFE_DOCS_EXTENSIONS = re.compile(r"\.(md|txt|rst|yaml|yml|json|toml)$", re.IGNORECASE)

# Secret/credential file patterns — reject these regardless
_SECRET_FILE_PATTERNS = re.compile(
    r"(\.env|\.env\.local|credentials|\.ssh|\.aws|\.git/|secrets|api_key"
    r"|password|passwd|token|private_key|id_rsa|id_ed25519|pgpass|\.netrc"
    r"|keychain|vault|\.htpasswd)",
    re.IGNORECASE,
)

# Deploy/package artifact patterns — reject for auto-commit
_DEPLOY_ARTIFACT_PATTERNS = re.compile(
    r"(\.dmg|\.pkg|notarization|\.app/|node_modules/|\.next/|dist/|build/|__pycache__)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# ClassificationResult
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Result of classifying a candidate action."""

    result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    action_type: str = ""
    tier: str = TIER_BLOCKED_DANGEROUS
    risk_level: str = "low"
    reason: str = ""
    auto_allowed: bool = False
    needs_approval: bool = False
    blocked: bool = False
    file_targets: List[str] = field(default_factory=list)
    secret_files_detected: List[str] = field(default_factory=list)
    deploy_artifacts_detected: List[str] = field(default_factory=list)
    agent_metadata: Dict[str, Any] = field(default_factory=dict)
    classified_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_type": self.action_type,
            "tier": self.tier,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "auto_allowed": self.auto_allowed,
            "needs_approval": self.needs_approval,
            "blocked": self.blocked,
            "file_targets": self.file_targets[:10],
            "secret_files_detected": self.secret_files_detected[:5],
            "deploy_artifacts_detected": self.deploy_artifacts_detected[:5],
            "agent_metadata": self.agent_metadata,
            "classified_at": self.classified_at,
        }


# ---------------------------------------------------------------------------
# ExecutionClassifier
# ---------------------------------------------------------------------------


class ExecutionClassifier:
    """Classifies actions into risk tiers for NUS 1E low-risk execution.

    Metadata and contract-driven — not tied to specific agent names.
    Supports any future agent/worker that provides standard metadata.
    """

    def classify(
        self,
        action_type: str,
        risk_level: str = "low",
        file_targets: Optional[List[str]] = None,
        tool_requirements: Optional[List[str]] = None,
        agent_metadata: Optional[Dict[str, Any]] = None,
        task_category: str = "unknown",
    ) -> ClassificationResult:
        """Classify an action into a risk tier.

        Inputs are evaluated by metadata/contract — not by agent name.
        Any future agent providing the same metadata will be classified
        the same way without code changes.
        """
        files = file_targets or []
        tools = tool_requirements or []
        agent_meta = agent_metadata or {}

        # Check for secret files first — always block
        secret_files = [f for f in files if _SECRET_FILE_PATTERNS.search(f)]
        if secret_files:
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_BLOCKED_DANGEROUS,
                risk_level="critical",
                reason=f"Secret/credential files detected in targets: {secret_files[:3]}. Permanently blocked.",
                blocked=True,
                file_targets=files,
                secret_files_detected=secret_files,
                agent_metadata=agent_meta,
            )

        # Check for deploy/package artifacts
        deploy_artifacts = [f for f in files if _DEPLOY_ARTIFACT_PATTERNS.search(f)]
        if deploy_artifacts:
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_BLOCKED_DANGEROUS,
                risk_level="high",
                reason=f"Deploy/package artifacts detected: {deploy_artifacts[:3]}. Blocked.",
                blocked=True,
                file_targets=files,
                deploy_artifacts_detected=deploy_artifacts,
                agent_metadata=agent_meta,
            )

        # Check tool requirements for dangerous tools
        dangerous_tools = {"git_push", "git_merge", "deploy_cli", "secret_reader", "browser_control"}
        detected_dangerous = dangerous_tools.intersection(tools)
        if detected_dangerous:
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_BLOCKED_DANGEROUS,
                risk_level="critical",
                reason=f"Dangerous tool requirements detected: {detected_dangerous}. Blocked.",
                blocked=True,
                file_targets=files,
                agent_metadata=agent_meta,
            )

        # Action type classification
        if action_type in _BLOCKED_ACTIONS:
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_BLOCKED_DANGEROUS,
                risk_level="critical",
                reason=f"action_type={action_type} is permanently blocked.",
                blocked=True,
                file_targets=files,
                agent_metadata=agent_meta,
            )

        if action_type in _HIGH_RISK_ACTIONS:
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_HIGH_EXTERNAL,
                risk_level="high",
                reason=f"action_type={action_type} is high-risk external — needs approval.",
                needs_approval=True,
                file_targets=files,
                agent_metadata=agent_meta,
            )

        if action_type in _SAFE_LOCAL_ACTIONS:
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_SAFE_LOCAL_DRY_RUN,
                risk_level="low",
                reason=f"action_type={action_type} is safe local — auto-allowed.",
                auto_allowed=True,
                file_targets=files,
                agent_metadata=agent_meta,
            )

        if action_type in _SAFE_DOCS_ACTIONS:
            # Validate files are actually docs/metadata (not source code)
            if files:
                non_docs = [f for f in files if not _SAFE_DOCS_EXTENSIONS.search(f)]
                if non_docs:
                    return ClassificationResult(
                        action_type=action_type,
                        tier=TIER_MEDIUM_FILE_WRITE,
                        risk_level="medium",
                        reason=(
                            f"action_type={action_type} claimed docs-only but "
                            f"non-doc file targets detected: {non_docs[:3]}. Escalated to medium."
                        ),
                        needs_approval=True,
                        file_targets=files,
                        agent_metadata=agent_meta,
                    )
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_SAFE_DOCS_METADATA,
                risk_level="low",
                reason=f"action_type={action_type} is safe docs/metadata — low risk.",
                auto_allowed=True,
                file_targets=files,
                agent_metadata=agent_meta,
            )

        if action_type in _MEDIUM_RISK_ACTIONS:
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_MEDIUM_FILE_WRITE,
                risk_level="medium",
                reason=f"action_type={action_type} is medium-risk file write — needs approval.",
                needs_approval=True,
                file_targets=files,
                agent_metadata=agent_meta,
            )

        # Risk level override for unknown action types
        if risk_level in ("high", "critical"):
            return ClassificationResult(
                action_type=action_type,
                tier=TIER_HIGH_EXTERNAL,
                risk_level=risk_level,
                reason=f"Unknown action_type={action_type} with risk_level={risk_level} — needs approval.",
                needs_approval=True,
                file_targets=files,
                agent_metadata=agent_meta,
            )

        # Default: unknown action type → needs approval (conservative)
        return ClassificationResult(
            action_type=action_type,
            tier=TIER_MEDIUM_FILE_WRITE,
            risk_level=risk_level or "medium",
            reason=f"Unknown action_type={action_type} — defaulting to needs_approval (conservative).",
            needs_approval=True,
            file_targets=files,
            agent_metadata=agent_meta,
        )

    def classify_batch(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[ClassificationResult]:
        """Classify a batch of candidates. Returns list of ClassificationResult."""
        results = []
        for c in candidates:
            result = self.classify(
                action_type=c.get("action_type", "unknown"),
                risk_level=c.get("risk_level", "low"),
                file_targets=c.get("file_targets"),
                tool_requirements=c.get("tool_requirements"),
                agent_metadata=c.get("agent_metadata"),
                task_category=c.get("task_category", "unknown"),
            )
            results.append(result)
        return results

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": NUS1E_CLASSIFIER_VERSION,
            "safe_local_actions": sorted(_SAFE_LOCAL_ACTIONS),
            "safe_docs_actions": sorted(_SAFE_DOCS_ACTIONS),
            "medium_risk_actions": sorted(_MEDIUM_RISK_ACTIONS),
            "high_risk_actions": sorted(_HIGH_RISK_ACTIONS),
            "blocked_actions": sorted(_BLOCKED_ACTIONS),
            "metadata_driven": True,
            "agent_name_agnostic": True,
            "note": (
                "Classification is metadata/contract-driven. "
                "Any future agent providing standard action_type, risk_level, "
                "file_targets, tool_requirements, and agent_metadata will be "
                "classified correctly without code changes."
            ),
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }
