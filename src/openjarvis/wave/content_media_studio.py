"""Epic G — Content & Media Studio (Wave 3).

Local-first content creation studio. Supports structured content workflows
and safe artifact generation via dry-run by default.

Rules:
- All workflows are local-first. No external API calls without env key + approval.
- File writes are approval-gated (dry-run returns artifact, never writes silently).
- External media (image/video gen, social posting, Slack/email) are hard-blocked
  unless a recognized env key is present AND approval is passed explicitly.
- Content safety policy blocks: credential extraction, secret inclusion, copyright
  reproduction, impersonation, spam/autoposting, unsafe final claims.
- Uses Wave 1 knowledge + research platforms and Wave 2 skill packs/optimization
  where available.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKFLOW_STATUS_DRAFT = "draft"
WORKFLOW_STATUS_READY = "ready"
WORKFLOW_STATUS_BLOCKED = "blocked"
WORKFLOW_STATUS_REQUIRES_APPROVAL = "requires_approval"
WORKFLOW_STATUS_REQUIRES_SETUP = "requires_setup"

ARTIFACT_KIND_TEXT = "text"
ARTIFACT_KIND_MARKDOWN = "markdown"
ARTIFACT_KIND_OUTLINE = "outline"
ARTIFACT_KIND_RELEASE_NOTES = "release_notes"
ARTIFACT_KIND_TECHNICAL_SUMMARY = "technical_summary"
ARTIFACT_KIND_PROMPT_PACK = "prompt_pack"
ARTIFACT_KIND_MEDIA_PLAN = "media_plan"

# Content safety: blocked terms/patterns
_BLOCKED_CONTENT_PATTERNS: List[str] = [
    "api_key", "api key", "secret_key", "private_key",
    "password:", "passwd:", "credential", "token:",
    "-----BEGIN", "-----END",
]

_BLOCKED_CONTENT_TOPICS = [
    "impersonat", "phish", "spam autopost",
    "bypass captcha", "credential harvest",
    "copyright reproduction",
]

# Templates dict: id → {name, kind, fields, description}
_BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "product_spec": {
        "id": "product_spec",
        "name": "Product Specification",
        "kind": ARTIFACT_KIND_MARKDOWN,
        "description": "Structured product spec with overview, goals, non-goals, requirements, risks.",
        "fields": ["title", "overview", "goals", "non_goals", "requirements", "risks", "timeline"],
        "example": "# Product Spec: {title}\n\n## Overview\n{overview}\n\n## Goals\n{goals}\n\n## Non-Goals\n{non_goals}\n\n## Requirements\n{requirements}\n\n## Risks\n{risks}\n\n## Timeline\n{timeline}",
    },
    "technical_handoff": {
        "id": "technical_handoff",
        "name": "Technical Handoff Document",
        "kind": ARTIFACT_KIND_MARKDOWN,
        "description": "Technical handoff with context, files changed, decisions, known issues.",
        "fields": ["title", "context", "files_changed", "decisions", "known_issues", "next_steps"],
        "example": "# Technical Handoff: {title}\n\n## Context\n{context}\n\n## Files Changed\n{files_changed}\n\n## Key Decisions\n{decisions}\n\n## Known Issues\n{known_issues}\n\n## Next Steps\n{next_steps}",
    },
    "bug_report": {
        "id": "bug_report",
        "name": "Bug Report",
        "kind": ARTIFACT_KIND_MARKDOWN,
        "description": "Structured bug report with reproduction steps, expected/actual behavior.",
        "fields": ["title", "severity", "description", "steps_to_reproduce", "expected", "actual", "environment"],
        "example": "# Bug Report: {title}\n\n**Severity:** {severity}\n\n## Description\n{description}\n\n## Steps to Reproduce\n{steps_to_reproduce}\n\n## Expected\n{expected}\n\n## Actual\n{actual}\n\n## Environment\n{environment}",
    },
    "release_readiness_report": {
        "id": "release_readiness_report",
        "name": "Release Readiness Report",
        "kind": ARTIFACT_KIND_RELEASE_NOTES,
        "description": "Pre-release checklist and readiness summary.",
        "fields": ["version", "summary", "completed_items", "blockers", "risk_level", "go_no_go"],
        "example": "# Release Readiness: v{version}\n\n## Summary\n{summary}\n\n## Completed Items\n{completed_items}\n\n## Blockers\n{blockers}\n\n## Risk Level: {risk_level}\n\n## Go / No-Go: {go_no_go}",
    },
    "coding_agent_prompt": {
        "id": "coding_agent_prompt",
        "name": "Coding Agent Prompt Pack",
        "kind": ARTIFACT_KIND_PROMPT_PACK,
        "description": "Structured prompt for a coding agent: context, task, constraints, output format.",
        "fields": ["task_title", "context", "task_description", "constraints", "output_format", "acceptance_criteria"],
        "example": "## Task: {task_title}\n\n### Context\n{context}\n\n### Task\n{task_description}\n\n### Constraints\n{constraints}\n\n### Output Format\n{output_format}\n\n### Acceptance Criteria\n{acceptance_criteria}",
    },
    "research_brief": {
        "id": "research_brief",
        "name": "Research Brief",
        "kind": ARTIFACT_KIND_TECHNICAL_SUMMARY,
        "description": "Research brief with question, scope, sources, and findings.",
        "fields": ["question", "scope", "background", "sources", "findings", "conclusion"],
        "example": "# Research Brief\n\n## Question\n{question}\n\n## Scope\n{scope}\n\n## Background\n{background}\n\n## Sources\n{sources}\n\n## Findings\n{findings}\n\n## Conclusion\n{conclusion}",
    },
    "content_plan": {
        "id": "content_plan",
        "name": "Content Plan",
        "kind": ARTIFACT_KIND_MEDIA_PLAN,
        "description": "Content calendar / media plan: topics, formats, schedule, goals.",
        "fields": ["title", "goal", "audience", "topics", "formats", "schedule", "kpis"],
        "example": "# Content Plan: {title}\n\n## Goal\n{goal}\n\n## Audience\n{audience}\n\n## Topics\n{topics}\n\n## Formats\n{formats}\n\n## Schedule\n{schedule}\n\n## KPIs\n{kpis}",
    },
}

# Safe generated artifacts output path (relative, dry-run only by default)
_SAFE_ARTIFACT_PATH_PREFIX = ".jarvis_artifacts"

# External providers that require setup
_EXTERNAL_PROVIDERS = {
    "dalle": "OPENAI_API_KEY",
    "stability": "STABILITY_API_KEY",
    "midjourney": "MIDJOURNEY_API_KEY",
    "runway": "RUNWAY_API_KEY",
    "social_posting": None,
    "slack_post": None,
    "email_send": None,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ContentArtifact:
    artifact_id: str
    workflow_id: str
    template_id: str
    kind: str
    title: str
    content: str
    generated_at: float
    dry_run: bool = True
    file_write_approved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "workflow_id": self.workflow_id,
            "template_id": self.template_id,
            "kind": self.kind,
            "title": self.title,
            "content_preview": self.content[:500],
            "content_length": len(self.content),
            "generated_at": self.generated_at,
            "dry_run": self.dry_run,
            "file_write_approved": self.file_write_approved,
        }


@dataclass
class ContentWorkflowResult:
    workflow_id: str
    ok: bool
    template_id: str = ""
    artifact: Optional[ContentArtifact] = None
    error: str = ""
    blocked: bool = False
    approval_required: bool = False
    requires_setup: bool = False
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "ok": self.ok,
            "template_id": self.template_id,
            "artifact": self.artifact.to_dict() if self.artifact else None,
            "error": self.error,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
            "requires_setup": self.requires_setup,
            "event_id": self.event_id,
        }


# ---------------------------------------------------------------------------
# Content safety policy
# ---------------------------------------------------------------------------

def check_content_safety(content: str, context: Optional[str] = None) -> Optional[str]:
    """Return a block reason if the content violates safety policy, else None.

    Blocks:
    - Credential/secret patterns
    - Impersonation/deception signals
    - Spam/autoposting signals
    - CAPTCHA bypass
    - Copyright reproduction signals
    """
    combined = ((context or "") + " " + content).lower()

    for pattern in _BLOCKED_CONTENT_PATTERNS:
        if pattern.lower() in combined:
            return f"Content contains forbidden pattern: '{pattern}'"

    for topic in _BLOCKED_CONTENT_TOPICS:
        if topic in combined:
            return f"Content involves blocked topic: '{topic}'"

    return None


def check_media_provider(provider_id: str) -> Dict[str, Any]:
    """Return provider status for an external media provider.

    Returns:
      {available: bool, status: 'ready'|'requires_setup', env_var: str|None}
    """
    import os
    env_var = _EXTERNAL_PROVIDERS.get(provider_id)
    if env_var is None:
        return {
            "available": False,
            "status": "hard_blocked",
            "provider_id": provider_id,
            "reason": f"Provider '{provider_id}' is hard-blocked (social/messaging send)",
        }
    key_present = bool(os.environ.get(env_var))
    return {
        "available": key_present,
        "status": "ready" if key_present else "requires_setup",
        "provider_id": provider_id,
        "env_var": env_var,
    }


# ---------------------------------------------------------------------------
# Template operations
# ---------------------------------------------------------------------------

def list_templates() -> List[Dict[str, Any]]:
    """Return all built-in content templates."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "kind": t["kind"],
            "description": t["description"],
            "fields": t["fields"],
        }
        for t in _BUILTIN_TEMPLATES.values()
    ]


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Return a template by ID."""
    return _BUILTIN_TEMPLATES.get(template_id)


def render_template(template_id: str, fields: Dict[str, str]) -> str:
    """Render a template with provided field values.

    Unfilled fields are left as {field_name} placeholders.
    """
    tmpl = _BUILTIN_TEMPLATES.get(template_id)
    if not tmpl:
        return f"[Template '{template_id}' not found]"

    content = tmpl["example"]
    for key, value in fields.items():
        content = content.replace(f"{{{key}}}", value)
    return content


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------

def _log_content_event(
    workflow_id: str,
    event_type: str,
    ok: bool,
    detail: str,
) -> str:
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log = WorkbenchEventLog()
        ev = log.push(
            session_id="wave3_content_studio",
            task_id=workflow_id,
            event_type=event_type,
            title=f"Content studio {event_type}: {workflow_id}",
            detail=detail,
            tone="success" if ok else ("error" if "blocked" in event_type else "warning"),
            metadata={"workflow_id": workflow_id, "ok": ok},
        )
        return ev.id
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main workflow runner
# ---------------------------------------------------------------------------

def run_content_workflow(
    template_id: str,
    fields: Optional[Dict[str, str]] = None,
    *,
    workflow_id: Optional[str] = None,
    dry_run: bool = True,
    file_write_approved: bool = False,
) -> ContentWorkflowResult:
    """Run a local content workflow using a template.

    All workflows are dry-run by default.
    File writes require file_write_approved=True.
    External providers are checked separately and require setup + approval.

    Safety policy is applied to rendered content before returning.
    """
    import uuid as _uuid

    wid = workflow_id or _uuid.uuid4().hex[:12]
    tmpl = get_template(template_id)

    if tmpl is None:
        return ContentWorkflowResult(
            workflow_id=wid, ok=False,
            error=f"Template '{template_id}' not found",
        )

    # Render template
    content = render_template(template_id, fields or {})

    # Content safety check
    block_reason = check_content_safety(content, context=template_id)
    if block_reason:
        eid = _log_content_event(wid, "content_workflow_blocked", False, block_reason)
        return ContentWorkflowResult(
            workflow_id=wid, ok=False, template_id=template_id,
            blocked=True, error=block_reason, event_id=eid,
        )

    # File write gate
    if not dry_run and not file_write_approved:
        eid = _log_content_event(
            wid, "artifact_write_requires_approval", False,
            "File write requires explicit approval"
        )
        return ContentWorkflowResult(
            workflow_id=wid, ok=False, template_id=template_id,
            approval_required=True,
            error="File write requires explicit approval (pass file_write_approved=True after approval)",
            event_id=eid,
        )

    # Build artifact
    artifact_id = _uuid.uuid4().hex[:12]
    artifact = ContentArtifact(
        artifact_id=artifact_id,
        workflow_id=wid,
        template_id=template_id,
        kind=tmpl["kind"],
        title=fields.get("title", template_id) if fields else template_id,
        content=content,
        generated_at=time.time(),
        dry_run=dry_run,
        file_write_approved=file_write_approved,
        metadata={"fields_provided": list((fields or {}).keys())},
    )

    # Try to enrich with Wave 1 knowledge if available
    _enrich_artifact_from_knowledge(artifact, template_id)

    event_type = "artifact_drafted" if dry_run else "content_workflow_created"
    eid = _log_content_event(wid, event_type, True,
                              f"Artifact '{artifact_id}' from template '{template_id}' "
                              f"({'dry-run' if dry_run else 'file-write approved'})")

    return ContentWorkflowResult(
        workflow_id=wid, ok=True, template_id=template_id,
        artifact=artifact, event_id=eid,
    )


def _enrich_artifact_from_knowledge(artifact: ContentArtifact, template_id: str) -> None:
    """Optionally enrich artifact with local knowledge store data (best-effort)."""
    try:
        from openjarvis.wave.knowledge_platform import search_knowledge
        results = search_knowledge(template_id, max_results=2)
        if results:
            artifact.metadata["knowledge_sources"] = [r.source_id for r in results]
    except Exception:
        pass


def run_media_provider_workflow(
    provider_id: str,
    prompt: str,
    *,
    approved: bool = False,
) -> ContentWorkflowResult:
    """Request a media asset from an external provider.

    Always requires: env key configured + approved=True.
    Social/email providers are hard-blocked regardless.
    """
    import uuid as _uuid

    wid = _uuid.uuid4().hex[:12]

    # Safety check on prompt
    block_reason = check_content_safety(prompt, context=f"media:{provider_id}")
    if block_reason:
        eid = _log_content_event(wid, "content_workflow_blocked", False, block_reason)
        return ContentWorkflowResult(
            workflow_id=wid, ok=False,
            blocked=True, error=block_reason, event_id=eid,
        )

    status = check_media_provider(provider_id)

    if status["status"] == "hard_blocked":
        eid = _log_content_event(wid, "content_workflow_blocked", False, status["reason"])
        return ContentWorkflowResult(
            workflow_id=wid, ok=False,
            blocked=True, error=status["reason"], event_id=eid,
        )

    if status["status"] == "requires_setup":
        eid = _log_content_event(
            wid, "media_provider_requires_setup", False,
            f"Provider '{provider_id}' requires {status.get('env_var')} env var"
        )
        return ContentWorkflowResult(
            workflow_id=wid, ok=False,
            requires_setup=True,
            error=(
                f"Media provider '{provider_id}' requires {status.get('env_var')} env var. "
                "Set the env var and request approval for live generation."
            ),
            event_id=eid,
        )

    # Key present — but live generation still requires approval
    if not approved:
        eid = _log_content_event(
            wid, "artifact_write_requires_approval", False,
            f"Provider '{provider_id}' requires approval=True for live generation"
        )
        return ContentWorkflowResult(
            workflow_id=wid, ok=False,
            approval_required=True,
            error=f"Live media generation with '{provider_id}' requires approval=True",
            event_id=eid,
        )

    # Would execute live generation here — stub for local/founder V1
    eid = _log_content_event(
        wid, "content_workflow_created", True,
        f"Media generation approved for provider '{provider_id}' (stub — not yet wired)"
    )
    return ContentWorkflowResult(
        workflow_id=wid, ok=True,
        event_id=eid,
        error="",
    )


# ---------------------------------------------------------------------------
# Wave 1/2 integration helpers
# ---------------------------------------------------------------------------

def run_release_notes_workflow(
    version: str,
    summary: str,
    completed_items: str,
    blockers: str = "None",
    risk_level: str = "low",
) -> ContentWorkflowResult:
    """Convenience: generate release notes using the release_readiness_report template."""
    return run_content_workflow(
        "release_readiness_report",
        fields={
            "version": version,
            "summary": summary,
            "completed_items": completed_items,
            "blockers": blockers,
            "risk_level": risk_level,
            "go_no_go": "Go" if blockers.lower() in ("none", "") else "Hold",
        },
        dry_run=True,
    )


def run_research_brief_workflow(
    question: str,
    scope: str = "",
    use_local_knowledge: bool = True,
) -> ContentWorkflowResult:
    """Generate a research brief, optionally enriched with local knowledge."""
    extra_findings = ""
    if use_local_knowledge:
        try:
            from openjarvis.wave.knowledge_platform import search_knowledge
            results = search_knowledge(question, max_results=3)
            if results:
                extra_findings = "\n".join(f"- {r.title}: {r.content[:100]}" for r in results)
        except Exception:
            pass

    return run_content_workflow(
        "research_brief",
        fields={
            "question": question,
            "scope": scope or "Local knowledge base + platform context",
            "background": "Generated from local knowledge sources.",
            "sources": "Local knowledge store",
            "findings": extra_findings or "No local records found for this query.",
            "conclusion": "See findings above for available local context.",
        },
        dry_run=True,
    )


def run_coding_agent_prompt_workflow(
    task_title: str,
    task_description: str,
    constraints: str = "",
    output_format: str = "Code + explanation",
    acceptance_criteria: str = "Tests pass",
) -> ContentWorkflowResult:
    """Generate a coding agent prompt pack using Wave 2 skill pack context."""
    context = ""
    try:
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        packs = reg.list_enabled()
        context = f"Available skill packs: {', '.join(p.name for p in packs[:3])}"
    except Exception:
        pass

    return run_content_workflow(
        "coding_agent_prompt",
        fields={
            "task_title": task_title,
            "context": context or "Local Jarvis coding environment",
            "task_description": task_description,
            "constraints": constraints or "Follow project rules. No approval bypass. Targeted edits only.",
            "output_format": output_format,
            "acceptance_criteria": acceptance_criteria,
        },
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def get_content_studio_status() -> Dict[str, Any]:
    template_count = len(_BUILTIN_TEMPLATES)
    provider_statuses = {}
    for pid in _EXTERNAL_PROVIDERS:
        provider_statuses[pid] = check_media_provider(pid)["status"]

    return {
        "epic": "epic_g",
        "wave": 3,
        "status": "ready",
        "implemented": True,
        "template_count": template_count,
        "templates": list(_BUILTIN_TEMPLATES.keys()),
        "dry_run_default": True,
        "file_write_requires_approval": True,
        "content_safety_policy_active": True,
        "wave1_knowledge_integration": True,
        "wave2_skill_pack_integration": True,
        "external_providers": provider_statuses,
        "local_workflows": [
            "text_draft", "document_outline", "release_notes",
            "technical_summary", "prompt_pack", "media_asset_plan",
        ],
        "note": (
            "Wave 3 Epic G: Local content studio. "
            "All workflows dry-run by default. File writes require approval. "
            "External media providers require env key + approval."
        ),
    }


__all__ = [
    "ContentArtifact",
    "ContentWorkflowResult",
    "check_content_safety",
    "check_media_provider",
    "list_templates",
    "get_template",
    "render_template",
    "run_content_workflow",
    "run_media_provider_workflow",
    "run_release_notes_workflow",
    "run_research_brief_workflow",
    "run_coding_agent_prompt_workflow",
    "get_content_studio_status",
    "WORKFLOW_STATUS_DRAFT",
    "WORKFLOW_STATUS_READY",
    "WORKFLOW_STATUS_BLOCKED",
    "WORKFLOW_STATUS_REQUIRES_APPROVAL",
    "WORKFLOW_STATUS_REQUIRES_SETUP",
    "ARTIFACT_KIND_TEXT",
    "ARTIFACT_KIND_MARKDOWN",
    "ARTIFACT_KIND_RELEASE_NOTES",
    "ARTIFACT_KIND_PROMPT_PACK",
    "ARTIFACT_KIND_MEDIA_PLAN",
]
