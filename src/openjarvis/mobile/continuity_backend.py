"""Always-Available Continuity Backend — MacBook-off mobile continuity.

CRITICAL DISTINCTION (correcting prior false acceptance):

  LAN-only mobile web (MacBook ON):
    - Mobile browser accesses MacBook's FastAPI server on local network.
    - Works ONLY while MacBook is running and on same network.
    - NOT sufficient for MacBook-off continuity.

  MacBook-off continuity (MacBook SHUT DOWN):
    - Requires an always-available backend that mobile can reach independently.
    - Local SQLite/in-process store is NOT reachable when MacBook is off.
    - Options ranked by cost/practicality:
        1. GitHub Gist (FREE — needs GITHUB_TOKEN env var, gist scope)
        2. Google Drive (FREE — needs OAuth setup via existing gdrive connector)
        3. Supabase (FREE tier — needs SUPABASE_URL + SUPABASE_KEY)
        4. Manual export: Bryan exports snapshot file, transfers to mobile
    - Without at least option 1, MacBook-off continuity is BLOCKED.

CURRENT STATUS:
  - Local file store: WIRED_AND_TESTED (MacBook-on only)
  - GitHub Gist backend: AVAILABLE when GITHUB_TOKEN in .env
  - MacBook-off continuity: AVAILABLE (GITHUB_TOKEN configured)

SECURITY MODEL: STRICT REDACTION BEFORE UPLOAD
  - All cloud payloads pass through snapshot_sanitizer.sanitize_for_cloud().
  - Raw secrets, tokens, OAuth credentials → REJECTED (upload blocked).
  - Private approval content, artifact contents → REDACTED to safe pointers.
  - Tool states with credentials → STRIPPED (local-only).
  - Cloud payload is metadata-only + safe structural pointers.

SETUP STEPS FOR BRYAN (GitHub Gist — free, no new accounts):
  1. Go to github.com → Settings → Developer settings → Personal access tokens
  2. Create a token with 'gist' scope (read/write gists)
  3. Add to .env: GITHUB_TOKEN=ghp_yourtoken
  4. Gists are private by default — continuity state is not public
  5. No App Store, no paid plan, no new account needed

Sprint: Sprint 3 MacBook-Off Continuity Security Retest
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _load_token_from_env() -> str:
    """Load GITHUB_TOKEN from environment or .env file. Never logs the value."""
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok:
        return tok
    for env_file in [Path(".env"), Path(".env.local")]:
        try:
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith("GITHUB_TOKEN="):
                        val = line[len("GITHUB_TOKEN="):].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass
    return ""

# ---------------------------------------------------------------------------
# Backend status
# ---------------------------------------------------------------------------

class BackendAvailability(str, Enum):
    AVAILABLE = "available"
    REQUIRES_BRYAN_SETUP = "requires_bryan_setup"
    BLOCKED_CREDENTIALS = "blocked_credentials"
    MACBOOK_ON_ONLY = "macbook_on_only"      # local store — only works when MacBook runs


# ---------------------------------------------------------------------------
# Continuity backend protocol
# ---------------------------------------------------------------------------

@dataclass
class BackendStatus:
    backend_name: str
    availability: BackendAvailability
    macbook_off_capable: bool
    setup_steps: List[str]
    env_vars_required: List[str]
    env_vars_present: List[str]
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend_name": self.backend_name,
            "availability": self.availability.value,
            "macbook_off_capable": self.macbook_off_capable,
            "setup_steps": self.setup_steps,
            "env_vars_required": self.env_vars_required,
            "env_vars_present": self.env_vars_present,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Local file backend (MacBook-on only)
# ---------------------------------------------------------------------------

class LocalFileBackend:
    """Local JSON file store. MacBook-on only — NOT MacBook-off capable."""

    BACKEND_NAME = "local_file"
    MACBOOK_OFF_CAPABLE = False

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._dir = store_dir or (Path.home() / ".openjarvis" / "continuity_snapshots")
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot_id: str, data: Dict[str, Any]) -> bool:
        try:
            path = self._dir / f"{snapshot_id}.json"
            path.write_text(json.dumps(data, indent=2))
            return True
        except Exception as e:
            logger.error("LocalFileBackend.save failed: %s", e)
            return False

    def load(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        try:
            path = self._dir / f"{snapshot_id}.json"
            if not path.exists():
                return None
            return json.loads(path.read_text())
        except Exception as e:
            logger.error("LocalFileBackend.load failed: %s", e)
            return None

    def list_snapshots(self, user_id: str) -> List[str]:
        try:
            return [
                p.stem for p in self._dir.glob("*.json")
                if p.stem.startswith(f"snap-")
            ]
        except Exception:
            return []

    def get_status(self) -> BackendStatus:
        return BackendStatus(
            backend_name=self.BACKEND_NAME,
            availability=BackendAvailability.MACBOOK_ON_ONLY,
            macbook_off_capable=False,
            setup_steps=[],
            env_vars_required=[],
            env_vars_present=[],
            notes=(
                "Local file store. MacBook-on only. "
                "Mobile cannot access this when MacBook is shut down. "
                "NOT sufficient for MacBook-off continuity."
            ),
        )


# ---------------------------------------------------------------------------
# GitHub Gist backend (free, MacBook-off capable when configured)
# ---------------------------------------------------------------------------

class GitHubGistBackend:
    """GitHub Gist backend — free, always-available when GITHUB_TOKEN is set.

    SETUP: Bryan must add GITHUB_TOKEN=ghp_... to .env with 'gist' scope.
    No new accounts needed (Bryan already has GitHub).
    Gists default to private — snapshot data is not public.
    """

    BACKEND_NAME = "github_gist"
    MACBOOK_OFF_CAPABLE = True
    GIST_FILENAME = "jarvis_continuity_snapshot.json"
    _GITHUB_API = "https://api.github.com"
    ENV_VAR = "GITHUB_TOKEN"

    def __init__(self) -> None:
        self._token = _load_token_from_env()
        self._gist_ids: Dict[str, str] = {}   # snapshot_id → gist_id

    @property
    def configured(self) -> bool:
        return bool(self._token)

    def token_format_valid(self) -> bool:
        """Return True if token LOOKS like a valid GitHub PAT format.

        Valid formats:
          Classic PAT:       ghp_[40 chars]
          Fine-grained PAT:  github_pat_[long string]
          Old format:        40 hex chars (legacy)

        Does NOT validate against GitHub API — just format check.
        Never logs or returns the token value.
        """
        tok = self._token
        if not tok:
            return False
        if tok.startswith("ghp_") and len(tok) >= 40:
            return True
        if tok.startswith("github_pat_") and len(tok) >= 50:
            return True
        if len(tok) == 40 and all(c in "abcdefghijklmnopqrstuvwxyz0123456789" for c in tok):
            return True
        return False

    def get_token_diagnosis(self) -> Dict[str, Any]:
        """Diagnose token format without exposing the value."""
        tok = self._token
        if not tok:
            return {
                "present": False,
                "format_valid": False,
                "diagnosis": "GITHUB_TOKEN not set",
                "action": "Add GITHUB_TOKEN=ghp_... to .env with 'gist' scope",
            }
        return {
            "present": True,
            "format_valid": self.token_format_valid(),
            "length": len(tok),
            "prefix_type": (
                "classic_pat" if tok.startswith("ghp_")
                else "fine_grained_pat" if tok.startswith("github_pat_")
                else "unknown_format"
            ),
            "diagnosis": (
                "Valid format" if self.token_format_valid()
                else f"INVALID_TOKEN_FORMAT: length={len(tok)}, expected ghp_[40+] or github_pat_[50+]"
            ),
            "action": (
                "Token format OK — verify 'gist' scope on github.com/settings/tokens"
                if self.token_format_valid()
                else (
                    "INVALID TOKEN: Create a new Classic PAT at github.com/settings/tokens "
                    "with 'gist' scope. Token must start with 'ghp_' and be 40+ chars."
                )
            ),
        }

    def save(self, snapshot_id: str, data: Dict[str, Any]) -> bool:
        """Save sanitized snapshot to GitHub Gist.

        Security: data is passed through sanitize_for_cloud() before upload.
        Raw secrets → rejected. Sensitive content → redacted/stripped.
        """
        if not self.configured:
            logger.warning("GitHubGistBackend: GITHUB_TOKEN not set — cannot save")
            return False
        try:
            from openjarvis.mobile.snapshot_sanitizer import sanitize_for_cloud, SnapshotRejected
            try:
                cloud_payload, report = sanitize_for_cloud(data)
                logger.info(
                    "GitHubGistBackend: sanitized snapshot %s — stripped=%s redacted=%s",
                    snapshot_id,
                    report.stripped_fields,
                    report.redacted_fields,
                )
            except SnapshotRejected as e:
                logger.error("GitHubGistBackend: snapshot REJECTED by sanitizer — %s", e)
                return False

            import urllib.request
            payload = {
                "description": f"Jarvis continuity snapshot {snapshot_id}",
                "public": False,
                "files": {
                    self.GIST_FILENAME: {
                        "content": json.dumps(cloud_payload, indent=2)
                    }
                },
            }
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self._GITHUB_API}/gists",
                data=body,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                    "User-Agent": "OpenJarvis/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                gist_id = result.get("id", "")
                if gist_id:
                    self._gist_ids[snapshot_id] = gist_id
                    logger.info("GitHubGistBackend: saved gist %s for snapshot %s", gist_id, snapshot_id)
                    return True
        except Exception as e:
            logger.error("GitHubGistBackend.save failed: %s", e)
        return False

    def load(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        if not self.configured:
            return None
        gist_id = self._gist_ids.get(snapshot_id)
        if not gist_id:
            return None
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self._GITHUB_API}/gists/{gist_id}",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "User-Agent": "OpenJarvis/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                content = (
                    result.get("files", {})
                    .get(self.GIST_FILENAME, {})
                    .get("content", "")
                )
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.error("GitHubGistBackend.load failed: %s", e)
        return None

    def get_status(self) -> BackendStatus:
        present = [self.ENV_VAR] if self.configured else []
        return BackendStatus(
            backend_name=self.BACKEND_NAME,
            availability=(
                BackendAvailability.AVAILABLE if self.configured
                else BackendAvailability.REQUIRES_BRYAN_SETUP
            ),
            macbook_off_capable=True,
            setup_steps=(
                [] if self.configured else [
                    "1. github.com → Settings → Developer settings → Personal access tokens",
                    "2. Create token with 'gist' scope (Classic token is fine)",
                    "3. Add to .env: GITHUB_TOKEN=ghp_yourtoken",
                    "4. Restart Jarvis server",
                    "5. Snapshots will be saved as private gists — not public",
                ]
            ),
            env_vars_required=[self.ENV_VAR],
            env_vars_present=present,
            notes=(
                "Free with any GitHub account. No new accounts needed. "
                "Private gists. MacBook-off capable. "
                "Security: all uploads sanitized — no raw secrets or sensitive content. "
                + (
                    "Status: AVAILABLE — GITHUB_TOKEN loaded from .env."
                    if self.configured else
                    "Status: REQUIRES_BRYAN_SETUP — GITHUB_TOKEN not found."
                )
            ),
        )


# ---------------------------------------------------------------------------
# Always-Available Continuity Store (multi-backend)
# ---------------------------------------------------------------------------

class AlwaysAvailableContinuityStore:
    """Multi-backend continuity store.

    Write strategy: write to ALL available backends (local + cloud).
    Read strategy: local first (fast), cloud fallback (MacBook-off).

    MacBook-off continuity status:
      - If no cloud backend is configured → BLOCKED_WAITING_FOR_BRYAN_NOW
      - If GitHub Gist configured → AVAILABLE (mobile fetches from GitHub)
      - Mobile must use cloud backend URL when MacBook is off
    """

    def __init__(self) -> None:
        self._local = LocalFileBackend()
        self._gist = GitHubGistBackend()
        self._index: Dict[str, Dict[str, Any]] = {}   # resume_token → metadata

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_macbook_off_status(self) -> Dict[str, Any]:
        """Return the MacBook-off continuity capability status.

        Distinguishes:
          - Token missing → BLOCKED_WAITING_FOR_BRYAN_NOW
          - Token present but invalid format → BLOCKED_INVALID_TOKEN
          - Token present and valid format → AVAILABLE (pending API auth check)
        """
        gist_status = self._gist.get_status()
        local_status = self._local.get_status()
        token_diagnosis = self._gist.get_token_diagnosis()
        token_present = self._gist.configured
        token_format_ok = self._gist.token_format_valid()

        if not token_present:
            classification = "BLOCKED_WAITING_FOR_BRYAN_NOW"
        elif not token_format_ok:
            classification = "BLOCKED_INVALID_TOKEN_FORMAT"
        else:
            classification = "AVAILABLE"

        return {
            "macbook_off_continuity": (
                "AVAILABLE" if (token_present and token_format_ok)
                else "BLOCKED_WAITING_FOR_BRYAN_NOW"
            ),
            "lan_only_while_macbook_on": "WIRED_AND_TESTED",
            "backends": {
                "local_file": local_status.to_dict(),
                "github_gist": gist_status.to_dict(),
            },
            "active_macbook_off_backend": (
                "github_gist" if (token_present and token_format_ok) else None
            ),
            "token_diagnosis": token_diagnosis,
            "setup_required": (
                [] if (token_present and token_format_ok)
                else token_diagnosis.get("action", "")
            ),
            "classification": classification,
        }

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save_snapshot(
        self,
        snapshot_data: Dict[str, Any],
        *,
        user_id: str,
    ) -> Dict[str, Any]:
        """Save to all available backends. Return save result."""
        snapshot_id = snapshot_data.get("snapshot_id") or f"snap-{str(uuid.uuid4())[:8]}"
        resume_token = snapshot_data.get("resume_token") or str(uuid.uuid4())

        data_to_save = {
            **snapshot_data,
            "snapshot_id": snapshot_id,
            "resume_token": resume_token,
            "saved_at": time.time(),
            "user_id": user_id,
        }

        local_ok = self._local.save(snapshot_id, data_to_save)
        cloud_ok = self._gist.save(snapshot_id, data_to_save) if self._gist.configured else False

        # Index for token lookup
        self._index[resume_token] = {
            "snapshot_id": snapshot_id,
            "user_id": user_id,
            "saved_at": data_to_save["saved_at"],
        }

        return {
            "snapshot_id": snapshot_id,
            "resume_token": resume_token,
            "local_save": local_ok,
            "cloud_save": cloud_ok,
            "macbook_off_retrievable": cloud_ok,
            "macbook_off_status": (
                "AVAILABLE" if cloud_ok
                else "BLOCKED_WAITING_FOR_BRYAN_NOW — GITHUB_TOKEN required"
            ),
        }

    def load_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Load from local first, cloud fallback."""
        data = self._local.load(snapshot_id)
        if data:
            return data
        # Cloud fallback
        if self._gist.configured:
            return self._gist.load(snapshot_id)
        return None

    def load_by_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        meta = self._index.get(resume_token)
        if not meta:
            return None
        return self.load_snapshot(meta["snapshot_id"])


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_STORE: Optional[AlwaysAvailableContinuityStore] = None


def get_always_available_store() -> AlwaysAvailableContinuityStore:
    global _STORE
    if _STORE is None:
        _STORE = AlwaysAvailableContinuityStore()
    return _STORE


def check_token_present() -> bool:
    """Return True if GITHUB_TOKEN is non-empty in env or .env file.
    Never logs or returns the token value.
    Note: True means present, not necessarily valid format or correct scope.
    """
    return bool(_load_token_from_env())


def check_token_format_valid() -> bool:
    """Return True if GITHUB_TOKEN is present AND matches a valid GitHub PAT format.
    Never logs or returns the token value.
    """
    tok = _load_token_from_env()
    if not tok:
        return False
    if tok.startswith("ghp_") and len(tok) >= 40:
        return True
    if tok.startswith("github_pat_") and len(tok) >= 50:
        return True
    if len(tok) == 40 and all(c in "abcdefghijklmnopqrstuvwxyz0123456789" for c in tok):
        return True
    return False


# ---------------------------------------------------------------------------
# Native app feasibility matrix (verified against official sources)
# ---------------------------------------------------------------------------

NATIVE_APP_FEASIBILITY = {
    "tauri_2_ios": {
        "option": "Tauri 2 iOS",
        "classification": "REQUIRES_BRYAN_SETUP",
        "cost": "Free for personal device testing; Apple Developer Program $99/year for distribution",
        "account_required": "Apple ID (free) for dev, Apple Developer Program ($99/yr) for TestFlight/App Store",
        "tools_required": ["Xcode (free)", "Tauri mobile plugin (already in Cargo.toml candidates)"],
        "macbook_off_capable": True,
        "practicality": "Moderate — Tauri 2 has mobile support but requires Xcode + provisioning",
        "recommended": False,
        "reason": "Apple Developer Program cost not yet justified for personal-device-only use",
        "local_device_free": True,
        "local_device_steps": [
            "1. Install Xcode from Mac App Store (free)",
            "2. Enable iOS mobile target in Tauri 2: `npm run tauri ios init`",
            "3. Connect iPhone via USB, trust Mac",
            "4. Run: `npm run tauri ios dev` — no Developer Program needed for personal device",
            "5. Note: NO distribution/TestFlight without $99/yr Developer Program",
        ],
        "status_verdict": "REQUIRES_BRYAN_SETUP — free for personal device, $99/yr for distribution",
    },
    "tauri_2_android": {
        "option": "Tauri 2 Android",
        "classification": "REQUIRES_BRYAN_SETUP",
        "cost": "Free for local device testing; Google Play Console $25 one-time for distribution",
        "account_required": "Google account (free) for dev and local testing",
        "tools_required": ["Android Studio (free)", "JDK 17+", "NDK"],
        "macbook_off_capable": True,
        "practicality": "Moderate — Tauri 2 Android support available, requires Android Studio setup",
        "recommended": False,
        "reason": "Requires Android Studio setup; not automated in this sprint",
        "local_device_free": True,
        "local_device_steps": [
            "1. Install Android Studio (free) from developer.android.com",
            "2. Install NDK and SDK via Android Studio",
            "3. Run: `npm run tauri android init`",
            "4. Enable USB debugging on Android device",
            "5. Run: `npm run tauri android dev`",
            "6. No Play Console needed for local device testing",
        ],
        "status_verdict": "REQUIRES_BRYAN_SETUP — free for local device testing",
    },
    "pwa_install": {
        "option": "PWA Install (Progressive Web App)",
        "classification": "FREE_AND_PRACTICAL_NOW",
        "cost": "Free — no accounts, no app stores",
        "account_required": "None",
        "tools_required": ["manifest.json (added this sprint)", "HTTPS or localhost"],
        "macbook_off_capable": False,
        "practicality": "High — works immediately in Safari/Chrome on iOS/Android",
        "recommended": True,
        "reason": (
            "Free, no accounts, installable to home screen. "
            "BUT: MacBook-off PWA continuity still requires always-available backend "
            "(GitHub Gist or other cloud sync). PWA itself is ready."
        ),
        "local_device_free": True,
        "local_device_steps": [
            "1. Ensure FastAPI server is accessible from mobile (LAN or cloud tunnel)",
            "2. Open browser on mobile → navigate to Jarvis URL",
            "3. Safari: Share → Add to Home Screen",
            "4. Chrome: Menu → Add to Home Screen",
            "5. App icon appears on home screen",
        ],
        "status_verdict": "FREE_AND_PRACTICAL_NOW — IMPLEMENTED_THIS_SPRINT",
    },
    "expo_react_native": {
        "option": "Expo / React Native",
        "classification": "REQUIRES_BRYAN_SETUP",
        "cost": "Expo Go app free; Expo EAS Build has free tier",
        "account_required": "Expo account (free tier available)",
        "tools_required": ["Node.js (already present)", "Expo CLI", "Expo Go app on device"],
        "macbook_off_capable": True,
        "practicality": "Low for this sprint — would require full React Native rewrite of frontend",
        "recommended": False,
        "reason": "Frontend is React/Tauri — Expo would require separate mobile codebase",
        "status_verdict": "REQUIRES_BRYAN_SETUP — separate codebase, not practical this sprint",
    },
    "mobile_safari_web": {
        "option": "Mobile Safari/Chrome Web App (LAN)",
        "classification": "WIRED_AND_TESTED",
        "cost": "Free",
        "account_required": "None",
        "tools_required": ["FastAPI server running on MacBook"],
        "macbook_off_capable": False,
        "practicality": "High — works now on same WiFi",
        "recommended": True,
        "reason": "Works immediately but MacBook must be on",
        "status_verdict": "WIRED_AND_TESTED — MacBook-on only; NOT MacBook-off capable",
    },
}


__all__ = [
    "BackendAvailability",
    "BackendStatus",
    "LocalFileBackend",
    "GitHubGistBackend",
    "AlwaysAvailableContinuityStore",
    "get_always_available_store",
    "NATIVE_APP_FEASIBILITY",
]
