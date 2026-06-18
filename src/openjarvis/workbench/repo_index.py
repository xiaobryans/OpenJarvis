"""US15 bounded repo map / symbol / dependency index for the coding workbench."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class SymbolEntry:
    name: str
    kind: str
    path: str
    line: int

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "path": self.path, "line": self.line}


@dataclass
class RepoIndex:
    repo_path: str
    files: List[str] = field(default_factory=list)
    symbols: List[SymbolEntry] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    subsystems: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "file_count": len(self.files),
            "files": self.files[:200],
            "symbols": [s.to_dict() for s in self.symbols[:500]],
            "symbol_count": len(self.symbols),
            "dependencies": self.dependencies,
            "subsystems": self.subsystems,
        }


_SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".wake_worker_venv",
    "target",
}


def _collect_files(repo_root: Path, max_files: int = 400) -> List[str]:
    files: List[str] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(repo_root))
        if path.suffix in (".py", ".ts", ".tsx", ".rs", ".toml", ".md", ".yaml", ".yml"):
            files.append(rel)
        if len(files) >= max_files:
            break
    return files


def _extract_python_symbols(file_path: Path, rel: str) -> List[SymbolEntry]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    out: List[SymbolEntry] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            out.append(SymbolEntry(node.name, "class", rel, node.lineno))
        elif isinstance(node, ast.FunctionDef):
            out.append(SymbolEntry(node.name, "function", rel, node.lineno))
    return out


def _read_dependencies(repo_root: Path) -> List[str]:
    deps: List[str] = []
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            m = re.match(r'^[\s"]*([a-zA-Z0-9_.-]+)[\s"]*\=', line)
            if m and not line.strip().startswith("#"):
                name = m.group(1)
                if name not in ("name", "version", "description", "requires-python"):
                    deps.append(name)
    req = repo_root / "requirements.txt"
    if req.exists():
        for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                deps.append(line.split("==")[0].split("[")[0])
    return sorted(set(deps))[:80]


def _subsystem_map(files: List[str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {}
    for f in files:
        if f.startswith("src/openjarvis/workbench/"):
            key = "workbench"
        elif f.startswith("src/openjarvis/server/"):
            key = "server"
        elif f.startswith("frontend/"):
            key = "frontend"
        elif f.startswith("tests/"):
            key = "tests"
        elif f.startswith("docs/"):
            key = "docs"
        else:
            key = "other"
        buckets.setdefault(key, []).append(f)
    return {k: v[:30] for k, v in buckets.items()}


def build_repo_index(repo_path: str = ".", max_symbols: int = 300) -> RepoIndex:
    """Build a bounded repo index (no full dependency graph)."""
    root = Path(repo_path).resolve()
    files = _collect_files(root)
    symbols: List[SymbolEntry] = []
    for rel in files:
        if not rel.endswith(".py"):
            continue
        symbols.extend(_extract_python_symbols(root / rel, rel))
        if len(symbols) >= max_symbols:
            break
    return RepoIndex(
        repo_path=str(root),
        files=files,
        symbols=symbols[:max_symbols],
        dependencies=_read_dependencies(root),
        subsystems=_subsystem_map(files),
    )


def git_workflow_status(repo_path: str = ".") -> Dict[str, Any]:
    """Return git status summary for workbench git workflow executor."""
    root = Path(repo_path).resolve()
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "ok": True,
            "branch": branch.stdout.strip(),
            "dirty": bool(status.stdout.strip()),
            "status_short": status.stdout.strip().splitlines()[:20],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def ci_visibility_status(repo_path: str = ".") -> Dict[str, Any]:
    """Report GitHub/CI visibility from local workflow files (setup required for live CI)."""
    root = Path(repo_path).resolve()
    workflows = list((root / ".github" / "workflows").glob("*.yml")) + list(
        (root / ".github" / "workflows").glob("*.yaml")
    )
    gh_available = False
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        gh_available = proc.returncode == 0
    except Exception:
        gh_available = False

    if not workflows:
        return {
            "status": "requires_setup",
            "summary": "No GitHub workflow files found.",
            "workflow_files": [],
            "gh_cli_authenticated": gh_available,
        }
    return {
        "status": "ready" if gh_available else "requires_setup",
        "summary": (
            "Workflow files present."
            + (" gh CLI authenticated." if gh_available else " gh auth required for live CI status.")
        ),
        "workflow_files": [w.name for w in workflows[:20]],
        "gh_cli_authenticated": gh_available,
    }


__all__ = [
    "RepoIndex",
    "SymbolEntry",
    "build_repo_index",
    "git_workflow_status",
    "ci_visibility_status",
]
