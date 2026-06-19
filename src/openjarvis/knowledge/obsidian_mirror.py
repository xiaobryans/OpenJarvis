"""Obsidian Knowledge Mirror — human-readable vault/archive for Jarvis knowledge.

Purpose:
  Obsidian is a HUMAN-READABLE archive/mirror, NOT the operational source of truth.
  Jarvis runtime operates from cloud/local memory. Obsidian is written for Bryan to read.

Exports:
  - Accepted decisions
  - Sprint summaries
  - Blocker/action ledger snapshots
  - Architecture notes
  - Roadmap snapshots
  - Daily-driver/burn-in logs
  - Slack/Telegram ops summaries
  - Memory conflict/correction summaries

Redaction:
  - No secrets, tokens, private key material
  - No raw chain-of-thought
  - No unredacted credentials
  - No full private logs unless sanitized

Idempotency:
  - Rerunning export updates or appends safely
  - No uncontrolled duplicate files
  - Files are named with stable slugs; timestamp in frontmatter tracks last update

Vault path:
  - Default: ~/.jarvis/obsidian-vault
  - Configurable via JARVIS_OBSIDIAN_VAULT env var or explicit path
  - Does not require Obsidian app to be installed
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    r"xoxb-[A-Za-z0-9\-]+",          # Slack bot tokens
    r"xoxp-[A-Za-z0-9\-]+",          # Slack user tokens
    r"sk-[A-Za-z0-9]{20,}",          # OpenAI keys
    r"ghp_[A-Za-z0-9]{20,}",         # GitHub PATs
    r"gho_[A-Za-z0-9]{20,}",         # GitHub OAuth
    r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",  # JWT
    r"AKIA[A-Z0-9]{16}",              # AWS access key IDs
    r"(?i)(password|secret|token|api_key|auth|bearer|credential)\s*[:=]\s*\S+",
]

_SECRET_COMPILED = [re.compile(p) for p in _SECRET_PATTERNS]


def redact(text: str) -> str:
    """Redact known secret patterns from text before writing to vault."""
    for pattern in _SECRET_COMPILED:
        text = pattern.sub("[REDACTED]", text)
    return text


def _slug(title: str) -> str:
    """Convert title to a stable filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug.strip("-")[:80]


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _build_frontmatter(
    title: str,
    source: str,
    project: str,
    status: str,
    tags: List[str],
    trace_id: Optional[str] = None,
) -> str:
    """Build YAML frontmatter for Obsidian note."""
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "---",
        f'title: "{title}"',
        f"date: {now}",
        f'source: "{source}"',
        f'project: "{project}"',
        f'status: "{status}"',
    ]
    if trace_id:
        lines.append(f'trace_id: "{trace_id}"')
    if tags:
        tag_str = ", ".join(f'"{t}"' for t in tags)
        lines.append(f"tags: [{tag_str}]")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Vault document types
# ---------------------------------------------------------------------------

@dataclass
class VaultNote:
    """A note to be written to the Obsidian vault."""
    title: str
    body: str
    source: str = "jarvis"
    project: str = "openjarvis"
    status: str = "DAILY_DRIVER_ACCEPT"
    tags: List[str] = field(default_factory=list)
    trace_id: Optional[str] = None
    folder: str = ""          # Subfolder within vault; empty = root
    filename: Optional[str] = None   # Override filename; None = auto from title


# ---------------------------------------------------------------------------
# ObsidianMirror
# ---------------------------------------------------------------------------

class ObsidianMirror:
    """Writes Markdown notes to a local Obsidian-compatible vault.

    Does not require the Obsidian app. Writes plain Markdown with YAML frontmatter.
    Safe to run in CI, tests, and headless environments.

    Parameters
    ----------
    vault_path:
        Path to vault root directory.
        Defaults to JARVIS_OBSIDIAN_VAULT env var or ~/.jarvis/obsidian-vault
    """

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        if vault_path is None:
            env_path = os.environ.get("JARVIS_OBSIDIAN_VAULT", "")
            if env_path:
                vault_path = Path(env_path)
            else:
                vault_path = Path.home() / ".jarvis" / "obsidian-vault"
        self._vault = vault_path

    @property
    def vault_path(self) -> Path:
        return self._vault

    def _ensure_dir(self, folder: str) -> Path:
        target = self._vault / folder if folder else self._vault
        target.mkdir(parents=True, exist_ok=True)
        return target

    def write_note(self, note: VaultNote) -> Path:
        """Write or update a note idempotently.

        If the file already exists, it is overwritten with the latest content.
        Idempotency: stable filename → safe repeated writes.
        """
        body = redact(note.body)
        frontmatter = _build_frontmatter(
            title=note.title,
            source=note.source,
            project=note.project,
            status=note.status,
            tags=note.tags,
            trace_id=note.trace_id,
        )
        full_content = f"{frontmatter}\n\n# {note.title}\n\n{body}\n"

        folder_path = self._ensure_dir(note.folder)
        filename = note.filename or f"{_slug(note.title)}.md"
        dest = folder_path / filename

        dest.write_text(full_content, encoding="utf-8")
        logger.info("ObsidianMirror: wrote %s", dest)
        return dest

    def export_sprint_summary(
        self,
        sprint_name: str,
        body: str,
        project: str = "openjarvis",
        trace_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Path:
        return self.write_note(VaultNote(
            title=f"Sprint Summary — {sprint_name}",
            body=body,
            source="jarvis-sprint",
            project=project,
            status="DAILY_DRIVER_ACCEPT",
            tags=tags or ["sprint", "summary"],
            trace_id=trace_id,
            folder="sprints",
        ))

    def export_accepted_decisions(
        self,
        decisions: List[Dict[str, Any]],
        project: str = "openjarvis",
        trace_id: Optional[str] = None,
    ) -> Path:
        lines = []
        for d in decisions:
            title = redact(str(d.get("title", "Untitled")))
            status = d.get("status", "DAILY_DRIVER_ACCEPT")
            notes = redact(str(d.get("notes", "")))
            lines.append(f"### {title}\n\n**Status:** `{status}`\n\n{notes}\n")
        body = "\n".join(lines) or "_No accepted decisions recorded._"
        return self.write_note(VaultNote(
            title="Accepted Decisions",
            body=body,
            source="jarvis-decisions",
            project=project,
            status="DAILY_DRIVER_ACCEPT",
            tags=["decisions", "accepted"],
            trace_id=trace_id,
            folder="decisions",
        ))

    def export_blocker_ledger(
        self,
        blockers: List[Dict[str, Any]],
        project: str = "openjarvis",
        trace_id: Optional[str] = None,
    ) -> Path:
        lines = ["| Item | Owner | Priority | Status | Blocks Sprint | Blocks Final | Clearing Steps |",
                 "|------|-------|----------|--------|---------------|--------------|----------------|"]
        for b in blockers:
            item = redact(str(b.get("item", "")))
            owner = str(b.get("owner", "Bryan"))
            priority = str(b.get("priority", "medium"))
            status = str(b.get("status", "BLOCKED_CREDENTIALS"))
            blocks_sprint = "Yes" if b.get("blocks_sprint") else "No"
            blocks_final = "Yes" if b.get("blocks_final") else "No"
            steps = redact(str(b.get("clearing_steps", "")))
            lines.append(f"| {item} | {owner} | {priority} | `{status}` | {blocks_sprint} | {blocks_final} | {steps} |")
        body = "\n".join(lines)
        return self.write_note(VaultNote(
            title="Bryan-Action Blocker Ledger",
            body=body,
            source="jarvis-blockers",
            project=project,
            status="DAILY_DRIVER_ACCEPT",
            tags=["blockers", "ledger", "bryan-action"],
            trace_id=trace_id,
            folder="blockers",
        ))

    def export_memory_correction_summary(
        self,
        corrections: List[Dict[str, Any]],
        project: str = "openjarvis",
        trace_id: Optional[str] = None,
    ) -> Path:
        lines = []
        for c in corrections:
            entry_id = redact(str(c.get("entry_id", "")))
            reason = redact(str(c.get("reason", "")))
            lines.append(f"- `{entry_id}`: {reason}")
        body = "\n".join(lines) or "_No memory corrections recorded._"
        return self.write_note(VaultNote(
            title="Memory Correction Summary",
            body=body,
            source="jarvis-memory",
            project=project,
            status="DAILY_DRIVER_ACCEPT",
            tags=["memory", "corrections"],
            trace_id=trace_id,
            folder="memory",
        ))

    def export_slack_telegram_summary(
        self,
        summary: str,
        project: str = "openjarvis",
        trace_id: Optional[str] = None,
    ) -> Path:
        return self.write_note(VaultNote(
            title="Slack/Telegram Ops Summary",
            body=redact(summary),
            source="jarvis-ops",
            project=project,
            status="DAILY_DRIVER_ACCEPT",
            tags=["slack", "telegram", "ops"],
            trace_id=trace_id,
            folder="ops",
        ))

    def list_notes(self, folder: str = "") -> List[Path]:
        """List all Markdown notes in a vault folder."""
        target = self._vault / folder if folder else self._vault
        if not target.exists():
            return []
        return sorted(target.rglob("*.md"))

    def get_vault_summary(self) -> Dict[str, Any]:
        """Return a summary of vault contents without exposing sensitive paths."""
        if not self._vault.exists():
            return {"vault_exists": False, "note_count": 0, "folders": []}
        notes = list(self._vault.rglob("*.md"))
        folders = sorted({str(n.parent.relative_to(self._vault)) for n in notes})
        return {
            "vault_exists": True,
            "note_count": len(notes),
            "folders": folders,
        }


__all__ = [
    "ObsidianMirror",
    "VaultNote",
    "redact",
]
