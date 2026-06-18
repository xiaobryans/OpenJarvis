"""US15 bounded repo map / symbol / dependency index for the coding workbench."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import time
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
    test_files: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    ignored_paths: List[str] = field(default_factory=list)
    js_ts_symbols: List[SymbolEntry] = field(default_factory=list)
    freshness: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "file_count": len(self.files),
            "files": self.files[:200],
            "symbols": [s.to_dict() for s in self.symbols[:500]],
            "symbol_count": len(self.symbols),
            "js_ts_symbols": [s.to_dict() for s in self.js_ts_symbols[:200]],
            "js_ts_symbol_count": len(self.js_ts_symbols),
            "dependencies": self.dependencies,
            "subsystems": self.subsystems,
            "test_files": self.test_files[:100],
            "test_file_count": len(self.test_files),
            "config_files": self.config_files[:50],
            "ignored_paths": self.ignored_paths,
            "freshness": self.freshness,
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
    ".next",
    "out",
    "coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "*.egg-info",
}

_IGNORED_PATHS_DOCUMENTED = [
    ".git/",
    ".venv/",
    "node_modules/",
    "dist/",
    "build/",
    ".next/",
    "__pycache__/",
    "*.egg-info/",
    ".openjarvis/  (runtime DB / secrets)",
    ".env, .env.local  (secrets — never indexed)",
]

_CONFIG_SUFFIXES = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".conf", ".env.example"}
_CONFIG_NAMES = {"Makefile", "Dockerfile", "docker-compose.yml", ".dockerignore",
                 "package.json", "tsconfig.json", "pyproject.toml", ".gitignore",
                 "requirements.txt", "uv.lock", "Cargo.toml", "next.config.js",
                 "next.config.ts", "tailwind.config.js", "tailwind.config.ts",
                 "vite.config.ts", "vite.config.js"}


def _collect_files(repo_root: Path, max_files: int = 600) -> List[str]:
    files: List[str] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(repo_root))
        if path.suffix in (
            ".py", ".ts", ".tsx", ".js", ".jsx", ".rs",
            ".toml", ".md", ".yaml", ".yml", ".json", ".ini",
            ".cfg", ".conf", ".sh",
        ) or path.name in _CONFIG_NAMES:
            files.append(rel)
        if len(files) >= max_files:
            break
    return files


def _collect_test_files(repo_root: Path, files: List[str]) -> List[str]:
    test_files = []
    for f in files:
        name = Path(f).name
        if name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f or "/test/" in f:
            test_files.append(f)
    return test_files


def _collect_config_files(repo_root: Path, files: List[str]) -> List[str]:
    config = []
    for f in files:
        p = Path(f)
        if p.name in _CONFIG_NAMES or p.suffix in _CONFIG_SUFFIXES:
            if not p.name.startswith("test_"):
                config.append(f)
    return config[:50]


def _extract_js_ts_symbols(file_path: Path, rel: str) -> List[SymbolEntry]:
    """Extract component/function/hook names from JS/TS files via simple regex."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    out: List[SymbolEntry] = []
    # React component exports: export default function Foo / export function Foo / export const Foo
    for m in re.finditer(
        r"^(?:export\s+(?:default\s+)?)?(?:function|class|const|let|var)\s+([A-Z][A-Za-z0-9_]+)",
        text,
        re.MULTILINE,
    ):
        line = text[: m.start()].count("\n") + 1
        name = m.group(1)
        kind = "component" if name[0].isupper() else "function"
        if name.startswith("use") and len(name) > 3:
            kind = "hook"
        out.append(SymbolEntry(name=name, kind=kind, path=rel, line=line))
    # Named exports: export { Foo, Bar }
    for m in re.finditer(r"export\s*\{([^}]+)\}", text):
        for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", m.group(1)):
            if name not in ("default", "as", "from"):
                line = text[: m.start()].count("\n") + 1
                out.append(SymbolEntry(name=name, kind="export", path=rel, line=line))
    return out[:30]


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


def build_repo_index(repo_path: str = ".", max_symbols: int = 500) -> RepoIndex:
    """Build a bounded repo index with Python symbols, JS/TS symbols, test map, config map."""
    root = Path(repo_path).resolve()
    built_at = time.time()
    files = _collect_files(root)

    # Python symbols
    py_symbols: List[SymbolEntry] = []
    for rel in files:
        if not rel.endswith(".py"):
            continue
        py_symbols.extend(_extract_python_symbols(root / rel, rel))
        if len(py_symbols) >= max_symbols:
            break

    # JS/TS symbols
    js_symbols: List[SymbolEntry] = []
    for rel in files:
        if not rel.endswith((".ts", ".tsx", ".js", ".jsx")):
            continue
        js_symbols.extend(_extract_js_ts_symbols(root / rel, rel))
        if len(js_symbols) >= 200:
            break

    test_files = _collect_test_files(root, files)
    config_files = _collect_config_files(root, files)

    freshness = {
        "built_at": built_at,
        "built_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(built_at)),
        "file_count": len(files),
        "py_symbol_count": len(py_symbols),
        "js_ts_symbol_count": len(js_symbols),
        "test_file_count": len(test_files),
        "config_file_count": len(config_files),
    }

    return RepoIndex(
        repo_path=str(root),
        files=files,
        symbols=py_symbols[:max_symbols],
        dependencies=_read_dependencies(root),
        subsystems=_subsystem_map(files),
        test_files=test_files,
        config_files=config_files,
        ignored_paths=_IGNORED_PATHS_DOCUMENTED,
        js_ts_symbols=js_symbols[:200],
        freshness=freshness,
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


def _gh_run_status(repo_path: str) -> Dict[str, Any]:
    """Fetch recent workflow run status via gh CLI."""
    try:
        proc = subprocess.run(
            ["gh", "run", "list", "--limit", "5", "--json",
             "name,status,conclusion,headBranch,updatedAt,databaseId"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=12,
        )
        if proc.returncode == 0:
            runs = json.loads(proc.stdout or "[]")
            return {"ok": True, "runs": runs[:5]}
        return {"ok": False, "error": proc.stderr.strip()[:200]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _gh_pr_status(repo_path: str) -> Dict[str, Any]:
    """Fetch current branch PR status via gh CLI."""
    try:
        branch_proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=8,
        )
        branch = branch_proc.stdout.strip()
        pr_proc = subprocess.run(
            ["gh", "pr", "view", "--json", "number,title,state,url,headRefName,reviewDecision",
             "--branch", branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=12,
        )
        if pr_proc.returncode == 0:
            pr = json.loads(pr_proc.stdout)
            return {"ok": True, "pr": pr, "branch": branch}
        # No PR for this branch — not an error
        return {"ok": True, "pr": None, "branch": branch, "note": "No PR for current branch"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def ci_visibility_status(repo_path: str = ".") -> Dict[str, Any]:
    """Report GitHub/CI visibility with live gh CLI data if available."""
    root = Path(repo_path).resolve()
    workflows = list((root / ".github" / "workflows").glob("*.yml")) + list(
        (root / ".github" / "workflows").glob("*.yaml")
    )

    gh_available = False
    gh_auth_account = ""
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        gh_available = proc.returncode == 0
        if gh_available:
            m = re.search(r"Logged in to [^\s]+ account (\S+)", proc.stdout + proc.stderr)
            gh_auth_account = m.group(1) if m else "authenticated"
    except Exception:
        gh_available = False

    if not workflows:
        return {
            "status": "requires_setup",
            "summary": "No GitHub workflow files found. Add .github/workflows/ to enable CI.",
            "workflow_files": [],
            "gh_cli_authenticated": gh_available,
            "gh_account": gh_auth_account,
            "setup_steps": [
                "Create .github/workflows/ci.yml with your test command",
                "Push to GitHub to trigger CI runs",
                "Run: gh auth login  (if not already authenticated)",
            ],
        }

    result: Dict[str, Any] = {
        "status": "ready",
        "summary": "GitHub CI visibility active.",
        "workflow_files": [w.name for w in workflows[:20]],
        "gh_cli_authenticated": gh_available,
        "gh_account": gh_auth_account,
    }

    if gh_available:
        result["workflow_runs"] = _gh_run_status(str(root))
        result["pr_status"] = _gh_pr_status(str(root))
    else:
        result["status"] = "requires_setup"
        result["summary"] = "Workflow files present but gh CLI not authenticated."
        result["setup_steps"] = [
            "Run: gh auth login",
            "Follow browser prompt to authenticate with GitHub",
            "Expected output: '✓ Logged in to github.com account <username>'",
            "Then rerun: GET /v1/workbench/repo-index to see live CI status",
        ]

    return result


__all__ = [
    "RepoIndex",
    "SymbolEntry",
    "build_repo_index",
    "git_workflow_status",
    "ci_visibility_status",
]
