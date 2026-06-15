"""Jarvis Workflow Catalog — Ultra Sprint 5 real workflow tool pack.

Phase B: OMNIX project/repo/test/mission/qa/governance tools (15)
Phase C: Research/browser tools (5 available + 1 not_configured)
Phase D: Communication/reporting tools (5)
Phase E: Extended memory tools (8)

All tools have real executors or honest not_configured/degraded executors.
No fake count inflation. No silent skips. Every tool logged through gateway.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus

logger = logging.getLogger(__name__)

_MAX_OUTPUT_BYTES = 50 * 1024   # 50 KB truncation for subprocess output
_MAX_FETCH_BYTES  = 20 * 1024   # 20 KB truncation for web fetch


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_bytes: int = _MAX_OUTPUT_BYTES) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) > max_bytes:
        return text[:max_bytes] + "\n... (output truncated)"
    return text


def _run_git_cmd(
    args: List[str],
    cwd: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Run a read-only git command. Returns {ok, output, returncode}."""
    if shutil.which("git") is None:
        return {"ok": False, "error": "git not found on PATH", "output": ""}
    try:
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        combined = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
        return {
            "ok": r.returncode == 0,
            "output": _truncate(combined),
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"git timed out after {timeout}s", "output": ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "output": ""}


def _resolve_project_repo(project_id: str) -> Optional[str]:
    """Return repo_path for project, or None if not found."""
    try:
        from openjarvis.governance.constitution import ProjectRegistry
        proj = ProjectRegistry.get(project_id)
        if proj and proj.repo_path:
            return proj.repo_path
    except Exception:
        pass
    return None


def _safe_test_path(test_path: str, project_id: str) -> Optional[str]:
    """Return absolute test path if it's safe, or None with logged reason."""
    repo = _resolve_project_repo(project_id) if project_id else None
    resolved = Path(test_path).resolve()
    if repo:
        repo_resolved = Path(repo).resolve()
        try:
            resolved.relative_to(repo_resolved)
        except ValueError:
            # Not within repo — reject
            return None
    # Path must look like a test file or directory
    name = resolved.name
    if not (name.startswith("test") or name.startswith("Test") or "test" in str(resolved).lower()):
        return None
    return str(resolved)


# ===========================================================================
# Phase B executors — Project / Repo / Tests / Mission / QA / Governance
# ===========================================================================


def _exec_project_status(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.governance.constitution import ProjectRegistry
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    if not project_id:
        # Default to OMNIX if none specified
        project_id = "omnix"
    proj = ProjectRegistry.get(project_id)
    if proj is None:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    status: Dict[str, Any] = {
        "project_id": proj.project_id,
        "display_name": proj.display_name,
        "active": proj.active,
        "priority": proj.priority,
        "memory_namespace": proj.memory_namespace,
    }
    # Handoff file existence
    handoff_exists: List[Dict[str, Any]] = []
    for hp in proj.handoff_paths:
        full = Path(proj.repo_path) / hp if proj.repo_path else Path(hp)
        handoff_exists.append({"path": str(full), "exists": full.exists()})
    status["handoff_paths"] = handoff_exists
    # Repo presence
    if proj.repo_path:
        rp = Path(proj.repo_path)
        status["repo_path"] = str(rp)
        status["repo_exists"] = rp.exists()
        if rp.exists():
            git_dir = rp / ".git"
            status["is_git_repo"] = git_dir.exists()
            if git_dir.exists():
                br = _run_git_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(rp))
                status["branch"] = br.get("output", "").strip() if br["ok"] else "unknown"
                rev = _run_git_cmd(["git", "rev-parse", "HEAD"], cwd=str(rp))
                status["head"] = rev.get("output", "").strip()[:12] if rev["ok"] else "unknown"
    return {"ok": True, "status": status}


def _exec_project_handoff_read(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.governance.constitution import ProjectRegistry
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    section = inputs.get("section", "")  # optional: read only a named section
    proj = ProjectRegistry.get(project_id)
    if proj is None:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    contents = []
    for hp in proj.handoff_paths:
        full = Path(proj.repo_path) / hp if proj.repo_path else Path(hp)
        if not full.exists():
            contents.append({"path": str(full), "exists": False, "content": ""})
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        if section:
            # Extract lines around section header
            lines = text.splitlines()
            result_lines: List[str] = []
            in_section = False
            for line in lines:
                if line.strip().lower().startswith("#") and section.lower() in line.lower():
                    in_section = True
                elif in_section and line.startswith("#") and section.lower() not in line.lower():
                    break
                if in_section:
                    result_lines.append(line)
            text = "\n".join(result_lines) if result_lines else f"Section '{section}' not found"
        contents.append({
            "path": str(full),
            "exists": True,
            "content": _truncate(text, max_bytes=30 * 1024),
        })
    return {"ok": True, "project_id": project_id, "handoff_files": contents}


def _exec_project_handoff_update_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """Append or replace a draft-plan section in the project handoff file.

    Safety gates:
    - Only writes to paths registered in project.handoff_paths.
    - Appends a clearly-delimited '## Draft Plan Update' section.
    - Does not overwrite the entire file.
    - Does not write secrets (content is screened by JarvisMemory scrub logic).
    """
    from openjarvis.governance.constitution import ProjectRegistry
    from openjarvis.memory.store import _looks_like_secret
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    content = inputs.get("content", "")
    section_label = inputs.get("section_label", "Draft Plan Update")
    if not content:
        raise ValueError("content is required")
    if _looks_like_secret(content):
        return {"ok": False, "error": "Content rejected: looks like a secret/token"}
    proj = ProjectRegistry.get(project_id)
    if proj is None:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    if not proj.handoff_paths:
        return {"ok": False, "error": f"No handoff_paths registered for project '{project_id}'"}
    # Write to the first handoff path
    hp = proj.handoff_paths[0]
    full = Path(proj.repo_path) / hp if proj.repo_path else Path(hp)
    if not full.exists():
        return {"ok": False, "error": f"Handoff file not found: {full}"}
    existing = full.read_text(encoding="utf-8", errors="replace")
    # Remove any previous draft-plan section with same label
    marker_start = f"<!-- {section_label} START -->"
    marker_end = f"<!-- {section_label} END -->"
    if marker_start in existing:
        start_idx = existing.index(marker_start)
        end_idx = existing.find(marker_end)
        if end_idx != -1:
            existing = existing[:start_idx] + existing[end_idx + len(marker_end):]
        else:
            existing = existing[:start_idx]
    timestamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    new_section = (
        f"\n\n{marker_start}\n"
        f"## {section_label} ({timestamp})\n\n"
        f"{content.strip()}\n\n"
        f"{marker_end}\n"
    )
    updated = existing.rstrip() + new_section
    full.write_text(updated, encoding="utf-8")
    return {
        "ok": True,
        "project_id": project_id,
        "file": str(full),
        "section_label": section_label,
        "message": f"Appended '{section_label}' section to {hp}",
    }


def _exec_repo_status(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    repo_path = inputs.get("repo_path", "") or _resolve_project_repo(project_id) or "."
    result = _run_git_cmd(["git", "status", "--short"], cwd=repo_path)
    return {
        "ok": result["ok"],
        "project_id": project_id,
        "repo_path": repo_path,
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "is_clean": result["ok"] and result.get("output", "").strip() == "",
    }


def _exec_repo_branch_info(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    repo_path = inputs.get("repo_path", "") or _resolve_project_repo(project_id) or "."
    branch = _run_git_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    head = _run_git_cmd(["git", "rev-parse", "HEAD"], cwd=repo_path)
    remote = _run_git_cmd(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=repo_path,
    )
    return {
        "ok": branch["ok"],
        "project_id": project_id,
        "repo_path": repo_path,
        "branch": branch.get("output", "").strip() if branch["ok"] else "unknown",
        "head_sha": head.get("output", "").strip()[:12] if head["ok"] else "unknown",
        "upstream": remote.get("output", "").strip() if remote["ok"] else "no upstream",
    }


def _exec_repo_diff_summary(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    repo_path = inputs.get("repo_path", "") or _resolve_project_repo(project_id) or "."
    target = inputs.get("target", "HEAD")  # e.g. 'HEAD', 'main..HEAD', 'HEAD~5..HEAD'
    result = _run_git_cmd(["git", "diff", "--stat", target], cwd=repo_path)
    return {
        "ok": result["ok"],
        "project_id": project_id,
        "repo_path": repo_path,
        "target": target,
        "diff_stat": result.get("output", ""),
        "error": result.get("error", ""),
    }


def _exec_repo_recent_commits(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    repo_path = inputs.get("repo_path", "") or _resolve_project_repo(project_id) or "."
    n = min(int(inputs.get("n", 10)), 50)  # max 50 commits
    result = _run_git_cmd(
        ["git", "log", "--oneline", f"-{n}"],
        cwd=repo_path,
    )
    lines = [ln for ln in result.get("output", "").splitlines() if ln.strip()]
    return {
        "ok": result["ok"],
        "project_id": project_id,
        "repo_path": repo_path,
        "commits": lines,
        "count": len(lines),
        "error": result.get("error", ""),
    }


def _exec_tests_discover(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    repo_path = inputs.get("repo_path", "") or _resolve_project_repo(project_id) or "."
    tests_dir = inputs.get("tests_dir", "tests")
    base = Path(repo_path) / tests_dir
    if not base.exists():
        return {"ok": False, "error": f"Tests directory not found: {base}"}
    found = sorted(str(p) for p in base.rglob("test_*.py"))
    return {
        "ok": True,
        "project_id": project_id,
        "tests_dir": str(base),
        "test_files": found,
        "count": len(found),
    }


def _exec_tests_run_targeted(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Run pytest on a specific test path.

    Safety constraints:
    - test_path must contain 'test' in the filename or directory.
    - test_path must be within the project repo_path when project_id is given.
    - No arbitrary shell commands — pytest is called directly.
    - Timeout: 120 seconds.
    - Output truncated to 50 KB.
    """
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    test_path = inputs.get("test_path", "")
    extra_args = inputs.get("extra_args", [])
    if not test_path:
        raise ValueError("test_path is required")

    repo_path = _resolve_project_repo(project_id) if project_id else None

    # Safety: validate path
    safe_path = _safe_test_path(test_path, project_id)
    if safe_path is None:
        # Allow relative paths within repo when repo_path known
        if repo_path:
            candidate = Path(repo_path) / test_path
            if candidate.exists() and "test" in test_path.lower():
                safe_path = str(candidate)
        if safe_path is None:
            return {
                "ok": False,
                "error": (
                    f"test_path '{test_path}' rejected: must be within project repo "
                    "and contain 'test' in the name. "
                    "Set project_id to enable path validation."
                ),
            }

    # Sanitize extra_args: only allow --tb, -v, -q, -x, -k, --no-header flags
    _ALLOWED_PREFIXES = ("-v", "-q", "-x", "--tb=", "--no-header", "-k ", "-k=")
    safe_extra: List[str] = []
    for arg in (extra_args if isinstance(extra_args, list) else []):
        if any(str(arg).startswith(p) for p in _ALLOWED_PREFIXES):
            safe_extra.append(str(arg))

    import sys as _sys
    cmd = [
        _sys.executable, "-m", "pytest", safe_path,
        "--tb=short", "--no-header", "-q",
    ] + safe_extra

    cwd = repo_path or str(Path(safe_path).parent)
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=120,
        )
        combined = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
        return {
            "ok": r.returncode == 0,
            "test_path": safe_path,
            "returncode": r.returncode,
            "output": _truncate(combined),
            "passed": r.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "pytest timed out after 120 seconds", "test_path": safe_path}
    except FileNotFoundError:
        return {"ok": False, "error": "pytest not importable via sys.executable", "test_path": safe_path}


def _exec_tests_report_summary(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a pytest output string and produce a structured summary."""
    output = inputs.get("output", "")
    if not output:
        raise ValueError("output (pytest text) is required")
    lines = output.splitlines()
    passed = failed = error = skipped = 0
    summary_line = ""
    for line in lines:
        ln = line.strip()
        if "passed" in ln or "failed" in ln or "error" in ln:
            summary_line = ln
        if "passed" in ln:
            import re
            m = re.search(r"(\d+) passed", ln)
            if m:
                passed = int(m.group(1))
        if "failed" in ln:
            import re
            m = re.search(r"(\d+) failed", ln)
            if m:
                failed = int(m.group(1))
        if "error" in ln.lower():
            import re
            m = re.search(r"(\d+) error", ln)
            if m:
                error = int(m.group(1))
        if "skipped" in ln:
            import re
            m = re.search(r"(\d+) skipped", ln)
            if m:
                skipped = int(m.group(1))
    return {
        "ok": True,
        "passed": passed,
        "failed": failed,
        "errors": error,
        "skipped": skipped,
        "all_pass": failed == 0 and error == 0,
        "summary_line": summary_line,
    }


def _exec_mission_create_from_project_issue(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a mission from a project issue description.

    Note: Mission model does not have a project_id field. project_id is
    embedded in the objective as '[project:<id>]' prefix for traceability.
    """
    from openjarvis.mission.store import MissionStore
    from openjarvis.mission.models import Mission, MissionStatus, RiskLevel
    from openjarvis.governance.constitution import ProjectRegistry
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    if not project_id:
        raise ValueError("project_id is required")
    title = inputs.get("title", "")
    description = inputs.get("description", "")
    risk_level_str = inputs.get("risk_level", "low")
    if not title:
        raise ValueError("title is required")
    # Validate project exists
    if ProjectRegistry.get(project_id) is None:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    # Embed project_id in objective for traceability
    objective = f"[project:{project_id}] {description}" if description else f"[project:{project_id}] {title}"
    try:
        risk_level = RiskLevel(risk_level_str.lower())
    except ValueError:
        risk_level = RiskLevel.LOW
    mission = Mission(
        title=title,
        objective=objective,
        status=MissionStatus.QUEUED,
        owner="Bryan",
        risk_level=risk_level,
        summary=f"Created from project issue for project:{project_id}",
    )
    store = MissionStore()
    store.save_mission(mission)
    return {
        "ok": True,
        "mission_id": mission.id,
        "title": mission.title,
        "project_id": project_id,
        "status": mission.status.value,
    }


def _exec_mission_project_report(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """List missions associated with a project.

    Missions embed project_id as '[project:<id>]' in objective when created
    via mission.create_from_project_issue. This tool scans for that pattern.
    Missions without the pattern are returned with project_id='unknown'.
    """
    from openjarvis.mission.store import MissionStore
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    limit = int(inputs.get("limit", 50))
    store = MissionStore()
    all_missions = store.list_missions(limit=limit)
    if project_id:
        tag = f"[project:{project_id}]"
        filtered = [m for m in all_missions if tag in m.objective]
    else:
        filtered = all_missions
    return {
        "ok": True,
        "project_id": project_id or "all",
        "missions": [m.to_dict() for m in filtered],
        "count": len(filtered),
        "total_missions": len(all_missions),
    }


def _exec_qa_check_acceptance_evidence(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """Check if a set of acceptance evidence items are sufficient for ACCEPT.

    Inputs:
      evidence_items: list of {description, status, source, value}
      verdict_target: 'ACCEPT' | 'HOLD' | 'UNSAFE' (what you're targeting)

    Returns:
      ok, verdict, sufficient, missing, verified_count, total_count
    """
    from openjarvis.governance.constitution import Evidence, EvidenceStatus
    from openjarvis.governance.policies import classify_verdict
    evidence_items = inputs.get("evidence_items", [])
    if not evidence_items:
        return {
            "ok": True,
            "verdict": "HOLD",
            "sufficient": False,
            "missing": ["No evidence items provided"],
            "verified_count": 0,
            "total_count": 0,
        }
    evidences = []
    for item in evidence_items:
        status_str = item.get("status", "assumed")
        try:
            ev_status = EvidenceStatus(status_str)
        except ValueError:
            ev_status = EvidenceStatus.ASSUMED
        evidences.append(Evidence(
            description=item.get("description", ""),
            status=ev_status,
            source=item.get("source", ""),
            value=item.get("value"),
        ))
    verdict = classify_verdict(evidences)
    verified = [e for e in evidences if e.is_sufficient()]
    missing = [e.description for e in evidences if not e.is_sufficient()]
    return {
        "ok": True,
        "verdict": verdict.value,
        "sufficient": verdict.value == "ACCEPT",
        "verified_count": len(verified),
        "total_count": len(evidences),
        "missing": missing,
        "evidence_summary": [e.to_dict() for e in evidences],
    }


def _exec_governance_classify_report(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """Classify an action against governance rules and return a full report."""
    from openjarvis.governance.policies import (
        check_action_category,
        is_hard_gate,
        requires_approval,
        gate_check,
    )
    action_type = inputs.get("action_type", "")
    risk_level = inputs.get("risk_level", "low")
    agent_id = inputs.get("agent_id", "")
    if not action_type:
        raise ValueError("action_type is required")
    category = check_action_category(action_type, risk_level, agent_id)
    hard_gate = is_hard_gate(action_type)
    approval_req = requires_approval(risk_level, agent_id)
    gate = gate_check(action_type=action_type, risk_level=risk_level, agent_id=agent_id)
    return {
        "ok": True,
        "action_type": action_type,
        "risk_level": risk_level,
        "agent_id": agent_id,
        "category": category.value,
        "is_hard_gate": hard_gate,
        "requires_approval": approval_req,
        "allowed": gate["allowed"],
        "verdict": gate["verdict"],
        "reason": gate["reason"],
    }


def _exec_governance_build_blocker_report(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """Build a structured Blocker report from provided fields."""
    from openjarvis.governance.constitution import Blocker
    blocker_str = inputs.get("blocker", "")
    why = inputs.get("why_it_matters", "")
    unblock_path = inputs.get("unblock_path", "")
    can_continue = bool(inputs.get("can_continue_partially", False))
    partial_scope = inputs.get("partial_scope", "")
    if not blocker_str:
        raise ValueError("blocker is required")
    b = Blocker(
        blocker=blocker_str,
        why_it_matters=why,
        unblock_path=unblock_path,
        can_continue_partially=can_continue,
        partial_scope=partial_scope,
    )
    return {"ok": True, "blocker_report": b.to_dict()}


# ===========================================================================
# Phase C executors — Research / Browser (safe read-only)
# ===========================================================================


def _exec_docs_summarize_text(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize or extract key points from a provided text block.

    Pure Python — no network, no AI call. Extracts first sentences,
    section headers, and bullet points up to max_chars.
    """
    text = inputs.get("text", "")
    max_chars = int(inputs.get("max_chars", 2000))
    if not text:
        raise ValueError("text is required")
    lines = text.splitlines()
    headers: List[str] = []
    bullets: List[str] = []
    first_sentences: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            headers.append(stripped)
        elif stripped.startswith(("- ", "* ", "• ")):
            bullets.append(stripped)
        elif stripped and not first_sentences:
            # Grab first non-header, non-bullet text paragraph
            first_sentences.append(stripped[:500])
    summary_parts = []
    if headers:
        summary_parts.append("Headers: " + " | ".join(headers[:10]))
    if first_sentences:
        summary_parts.append("Lead: " + first_sentences[0])
    if bullets:
        summary_parts.append("Key points: " + "; ".join(bullets[:10]))
    summary = "\n".join(summary_parts)
    if not summary:
        summary = text[:max_chars]
    return {
        "ok": True,
        "summary": summary[:max_chars],
        "char_count": len(text),
        "header_count": len(headers),
        "bullet_count": len(bullets),
    }


def _exec_sources_capture(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Capture a text source with metadata into project memory."""
    from openjarvis.memory.store import JarvisMemory
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    url = inputs.get("url", "")
    title = inputs.get("title", "")
    content = inputs.get("content", "")
    tags = inputs.get("tags", [])
    if not content:
        raise ValueError("content is required")
    namespace = f"project:{project_id}" if project_id else "global"
    all_tags = list(tags) + (["source", "captured"] if "source" not in tags else [])
    if url:
        all_tags.append(f"url:{url[:100]}")
    note = f"[Source: {title or url or 'untitled'}]\n{content[:5000]}"
    mem = JarvisMemory()
    entry = mem.write(
        namespace=namespace,
        content=note,
        source="sources.capture",
        tags=all_tags,
        project_id=project_id,
        confidence=0.8,
    )
    return {
        "ok": True,
        "entry_id": entry.entry_id,
        "namespace": namespace,
        "title": title or url or "untitled",
    }


def _exec_research_brief(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Write a structured research brief to project memory."""
    from openjarvis.memory.store import JarvisMemory
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    topic = inputs.get("topic", "")
    findings = inputs.get("findings", "")
    recommendations = inputs.get("recommendations", "")
    confidence = float(inputs.get("confidence", 0.7))
    tags = inputs.get("tags", [])
    if not topic or not findings:
        raise ValueError("topic and findings are required")
    namespace = f"project:{project_id}" if project_id else "global"
    brief = textwrap.dedent(f"""\
        # Research Brief: {topic}

        ## Findings
        {findings}

        ## Recommendations
        {recommendations or 'None provided.'}
    """)
    all_tags = list(tags) + ["research", "brief", topic[:40]]
    mem = JarvisMemory()
    entry = mem.write(
        namespace=namespace,
        content=brief[:10000],
        source="research.brief",
        tags=all_tags,
        project_id=project_id,
        confidence=max(0.0, min(1.0, confidence)),
    )
    return {
        "ok": True,
        "entry_id": entry.entry_id,
        "namespace": namespace,
        "topic": topic,
    }


def _exec_web_fetch_url(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch a URL and return text content. Read-only GET, no auth passed.

    SSRF protection: rejects localhost, private IP ranges.
    Timeout: 10 seconds. Output truncated to 20 KB.
    """
    import re
    url = inputs.get("url", "")
    if not url:
        raise ValueError("url is required")
    # SSRF guard
    _BLOCKED_PATTERNS = [
        r"^https?://localhost",
        r"^https?://127\.",
        r"^https?://0\.0\.",
        r"^https?://169\.254\.",
        r"^https?://10\.",
        r"^https?://172\.(1[6-9]|2[0-9]|3[01])\.",
        r"^https?://192\.168\.",
        r"^https?://\[::1\]",
    ]
    for pattern in _BLOCKED_PATTERNS:
        if re.match(pattern, url, re.IGNORECASE):
            return {
                "ok": False,
                "error": f"URL blocked: private/loopback addresses are not allowed",
                "url": url,
            }
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "URL must start with http:// or https://"}
    try:
        import requests  # type: ignore
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "JarvisBot/1.0 (read-only research)"},
            allow_redirects=True,
        )
        content_type = resp.headers.get("content-type", "")
        text = resp.text if "text" in content_type or "json" in content_type else f"[binary content: {content_type}]"
        return {
            "ok": True,
            "url": url,
            "status_code": resp.status_code,
            "content_type": content_type,
            "content": _truncate(text, max_bytes=_MAX_FETCH_BYTES),
            "content_length": len(text),
        }
    except ImportError:
        return {
            "ok": False,
            "error": "requests library not available",
            "error_type": "missing_dependency",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


def _exec_browser_open_url(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Open a URL in the system browser (macOS: open).

    Read-only: does not submit forms, authenticate, or mutate accounts.
    dry_run=True returns the URL without opening (for tests).
    """
    url = inputs.get("url", "")
    dry_run = bool(inputs.get("dry_run", False))
    if not url:
        raise ValueError("url is required")
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "URL must start with http:// or https://"}
    if dry_run:
        return {"ok": True, "url": url, "dry_run": True, "message": "dry_run: browser not opened"}
    try:
        r = subprocess.run(["open", url], capture_output=True, text=True, timeout=10)
        return {
            "ok": r.returncode == 0,
            "url": url,
            "message": "Browser opened" if r.returncode == 0 else r.stderr.strip(),
        }
    except FileNotFoundError:
        # Not macOS or open not available
        try:
            import webbrowser
            webbrowser.open(url)
            return {"ok": True, "url": url, "message": "Browser opened via webbrowser module"}
        except Exception as exc2:
            return {"ok": False, "error": str(exc2), "url": url}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


# web.search executor — honest not_configured without TAVILY_API_KEY
def _exec_web_search(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a web search. Requires TAVILY_API_KEY env var."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key or api_key.startswith("<"):
        return {
            "ok": False,
            "error_type": "not_configured",
            "error": "web.search requires TAVILY_API_KEY environment variable",
        }
    query = inputs.get("query", "")
    if not query:
        raise ValueError("query is required")
    max_results = int(inputs.get("max_results", 5))
    try:
        from tavily import TavilyClient  # type: ignore
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results)
        return {
            "ok": True,
            "query": query,
            "results": response.get("results", []),
            "count": len(response.get("results", [])),
        }
    except ImportError:
        return {
            "ok": False,
            "error_type": "missing_dependency",
            "error": "tavily-python package not installed. Install: pip install tavily-python",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ===========================================================================
# Phase D executors — Communication / Reporting (draft or report, no auto-send)
# ===========================================================================


def _exec_slack_draft_update(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Draft a Slack update message. Does NOT send. Returns formatted text only."""
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    title = inputs.get("title", "Status Update")
    body = inputs.get("body", "")
    urgency = inputs.get("urgency", "normal")
    if not body:
        raise ValueError("body is required")
    emoji_map = {"high": ":red_circle:", "normal": ":large_blue_circle:", "low": ":white_circle:"}
    emoji = emoji_map.get(urgency, ":large_blue_circle:")
    draft = (
        f"{emoji} *{title}* (Project: {project_id})\n\n"
        f"{body.strip()}\n\n"
        f"_Draft — not sent. Requires explicit approval to send._"
    )
    return {
        "ok": True,
        "draft": draft,
        "project_id": project_id,
        "send_status": "not_sent",
        "message": "Draft created. Use slack.notify_mission with explicit_approved=True to send.",
    }


def _exec_telegram_draft_alert(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Draft a Telegram alert message. Does NOT send. Returns formatted text only."""
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    title = inputs.get("title", "Alert")
    body = inputs.get("body", "")
    urgency = inputs.get("urgency", "normal")
    if not body:
        raise ValueError("body is required")
    prefix_map = {"high": "🔴", "normal": "🔵", "low": "⚪"}
    prefix = prefix_map.get(urgency, "🔵")
    draft = (
        f"{prefix} *{title}* (Project: `{project_id}`)\n\n"
        f"{body.strip()}\n\n"
        f"_Draft — not sent. Requires explicit approval._"
    )
    return {
        "ok": True,
        "draft": draft,
        "project_id": project_id,
        "send_status": "not_sent",
        "message": "Draft created. Use telegram.notify_mission with explicit_approved=True to send.",
    }


def _exec_report_generate_status(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a text status report for a project from live data."""
    from openjarvis.governance.constitution import ProjectRegistry
    from openjarvis.mission.store import MissionStore
    from openjarvis.mission.models import MissionStatus
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "omnix")
    proj = ProjectRegistry.get(project_id)
    if proj is None:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    # Gather missions for this project
    store = MissionStore()
    all_missions = store.list_missions(limit=200)
    tag = f"[project:{project_id}]"
    proj_missions = [m for m in all_missions if tag in m.objective]
    by_status: Dict[str, int] = {}
    for m in proj_missions:
        by_status[m.status.value] = by_status.get(m.status.value, 0) + 1
    # Repo status
    repo_info: Dict[str, Any] = {}
    if proj.repo_path:
        br = _run_git_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=proj.repo_path)
        rev = _run_git_cmd(["git", "rev-parse", "HEAD"], cwd=proj.repo_path)
        repo_info = {
            "branch": br.get("output", "").strip() if br["ok"] else "unknown",
            "head": rev.get("output", "").strip()[:12] if rev["ok"] else "unknown",
        }
    lines = [
        f"# Project Status Report: {proj.display_name}",
        f"Project ID: {proj.project_id}",
        f"Active: {proj.active}",
        f"Priority: {proj.priority}",
        "",
        "## Mission Summary",
        f"Total project missions: {len(proj_missions)}",
    ]
    for status, count in sorted(by_status.items()):
        lines.append(f"  {status}: {count}")
    if repo_info:
        lines += ["", "## Repository", f"Branch: {repo_info.get('branch','?')}",
                  f"HEAD: {repo_info.get('head','?')}"]
    report_text = "\n".join(lines)
    return {
        "ok": True,
        "project_id": project_id,
        "report": report_text,
        "mission_count": len(proj_missions),
        "mission_by_status": by_status,
    }


def _exec_report_generate_daily_digest(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate a daily digest report aggregating missions + recent events."""
    from openjarvis.mission.store import MissionStore
    from openjarvis.governance.constitution import ProjectRegistry
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    store = MissionStore()
    missions = store.list_missions(limit=50)
    events = store.list_recent_events(limit=20)
    # Filter by project_id if given
    if project_id:
        tag = f"[project:{project_id}]"
        missions = [m for m in missions if tag in m.objective]
    running = [m for m in missions if m.status.value in ("running", "planning")]
    blocked = [m for m in missions if m.status.value == "blocked"]
    completed = [m for m in missions if m.status.value == "completed"]
    lines = [
        f"# Daily Digest — {time.strftime('%Y-%m-%d UTC', time.gmtime())}",
        f"Project filter: {project_id or 'all'}",
        "",
        f"## Missions",
        f"Running/Planning: {len(running)}",
        f"Blocked: {len(blocked)}",
        f"Completed: {len(completed)}",
        f"Total in scope: {len(missions)}",
    ]
    if blocked:
        lines += ["", "### Blocked Missions"]
        for m in blocked[:5]:
            lines.append(f"  - [{m.id}] {m.title}")
    if running:
        lines += ["", "### Active Missions"]
        for m in running[:5]:
            lines.append(f"  - [{m.id}] {m.title}")
    lines += ["", f"## Recent Events ({len(events)} total)"]
    for e in events[:5]:
        lines.append(f"  - [{e.event_type}] {e.message[:100]}")
    return {
        "ok": True,
        "project_id": project_id or "all",
        "digest": "\n".join(lines),
        "running_count": len(running),
        "blocked_count": len(blocked),
        "completed_count": len(completed),
    }


def _exec_approval_queue_summary(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Return a summary of pending approval queue items."""
    from openjarvis.tools.approval_store import ApprovalStore, STATUS_PENDING
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    try:
        store = ApprovalStore()
        pending = store.list_pending()
    except Exception as exc:
        return {
            "ok": False,
            "error": f"ApprovalStore unavailable: {exc}",
            "pending_count": 0,
            "items": [],
        }
    items = [p.to_dict() for p in pending]
    return {
        "ok": True,
        "pending_count": len(items),
        "items": items[:20],  # cap at 20 for readability
        "project_id": project_id or "all",
    }


# ===========================================================================
# Phase E executors — Extended Memory
# ===========================================================================


def _exec_memory_project_summary(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """List all memory entries for a project namespace."""
    from openjarvis.memory.store import JarvisMemory
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    if not project_id:
        raise ValueError("project_id is required")
    namespace = inputs.get("namespace", f"project:{project_id}")
    limit = int(inputs.get("limit", 50))
    mem = JarvisMemory()
    entries = mem.list_by_namespace(namespace, project_id=project_id, limit=limit)
    return {
        "ok": True,
        "project_id": project_id,
        "namespace": namespace,
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
    }


def _memory_record_typed(
    entry_type: str,
    inputs: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Shared implementation for typed memory record operations."""
    from openjarvis.memory.store import JarvisMemory
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    content = inputs.get("content", "")
    if not content:
        raise ValueError("content is required")
    namespace = inputs.get("namespace", f"project:{project_id}" if project_id else "global")
    tags = list(inputs.get("tags", [])) + [entry_type]
    confidence = float(inputs.get("confidence", 0.9))
    source = inputs.get("source", f"memory.record_{entry_type}")
    mem = JarvisMemory()
    entry = mem.write(
        namespace=namespace,
        content=f"[{entry_type.upper()}] {content}",
        source=source,
        tags=tags,
        project_id=project_id,
        mission_id=inputs.get("mission_id") or ctx.get("mission_id"),
        agent_id=inputs.get("agent_id") or ctx.get("agent_id"),
        confidence=max(0.0, min(1.0, confidence)),
    )
    return {
        "ok": True,
        "entry_id": entry.entry_id,
        "namespace": namespace,
        "entry_type": entry_type,
        "project_id": project_id,
    }


def _exec_memory_record_decision(inputs, ctx):
    return _memory_record_typed("decision", inputs, ctx)

def _exec_memory_record_bug(inputs, ctx):
    return _memory_record_typed("bug", inputs, ctx)

def _exec_memory_record_fix(inputs, ctx):
    return _memory_record_typed("fix", inputs, ctx)

def _exec_memory_record_blocker(inputs, ctx):
    return _memory_record_typed("blocker", inputs, ctx)

def _exec_memory_record_validation(inputs, ctx):
    return _memory_record_typed("validation", inputs, ctx)


def _exec_memory_list_recent_project_entries(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """List the most recent memory entries for a project, across all namespaces."""
    from openjarvis.memory.store import JarvisMemory
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    if not project_id:
        raise ValueError("project_id is required")
    limit = int(inputs.get("limit", 20))
    mem = JarvisMemory()
    # Direct query across all namespaces for this project
    with mem._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM memory_entries WHERE project_id=? ORDER BY created_at DESC LIMIT ?",
            (project_id, max(1, min(limit, 100))),
        ).fetchall()
    entries = [mem._row_to_entry(r) for r in rows]
    return {
        "ok": True,
        "project_id": project_id,
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
    }


def _exec_memory_scrub_check(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Check whether a value would be rejected as a secret by the memory store."""
    from openjarvis.memory.store import _looks_like_secret
    value = inputs.get("value", "")
    if not isinstance(value, str):
        value = str(value)
    would_reject = _looks_like_secret(value)
    return {
        "ok": True,
        "value_preview": value[:20] + "..." if len(value) > 20 else value,
        "would_reject": would_reject,
        "reason": "Value matches secret pattern" if would_reject else "Value is safe to store",
    }


# ===========================================================================
# Tool definitions
# ===========================================================================


def _make_tool(spec: ToolSpec, fn: Callable) -> tuple:
    return (spec, fn)


_WORKFLOW_TOOL_DEFS = [
    # ---------- Phase B: Project ----------
    _make_tool(
        ToolSpec(
            tool_id="project.status",
            display_name="Project Status",
            description=(
                "Get comprehensive status for a project: profile, repo, branch, "
                "HEAD, handoff file presence."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string", "default": "omnix"}},
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_status,
    ),
    _make_tool(
        ToolSpec(
            tool_id="project.handoff_read",
            display_name="Project Handoff Read",
            description=(
                "Read the project's registered handoff file(s). "
                "Optionally extract a named section."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "default": "omnix"},
                    "section": {"type": "string", "description": "Optional section header to extract"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_handoff_read",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_handoff_read,
    ),
    _make_tool(
        ToolSpec(
            tool_id="project.handoff_update_plan",
            display_name="Project Handoff Update Plan",
            description=(
                "Append or replace a draft-plan section in the project's registered "
                "handoff file. Safe: only writes to registered handoff_paths. "
                "Does not overwrite the whole file."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "content": {"type": "string", "description": "Draft plan content to append"},
                    "section_label": {"type": "string", "default": "Draft Plan Update"},
                },
                "required": ["content"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_handoff_update_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_handoff_update_plan,
    ),
    # ---------- Phase B: Repo ----------
    _make_tool(
        ToolSpec(
            tool_id="repo.status",
            display_name="Repo Status",
            description="Show git working tree status (--short) for a project repo.",
            category="repo",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repo_path": {"type": "string"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:repo"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_repo_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_repo_status,
    ),
    _make_tool(
        ToolSpec(
            tool_id="repo.branch_info",
            display_name="Repo Branch Info",
            description="Get current branch, HEAD SHA, and upstream tracking info.",
            category="repo",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repo_path": {"type": "string"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:repo"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_repo_branch_info",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_repo_branch_info,
    ),
    _make_tool(
        ToolSpec(
            tool_id="repo.diff_summary",
            display_name="Repo Diff Summary",
            description="Show git diff --stat for a target range (read-only).",
            category="repo",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repo_path": {"type": "string"},
                    "target": {"type": "string", "default": "HEAD",
                                "description": "e.g. 'HEAD', 'main..HEAD', 'HEAD~5..HEAD'"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:repo"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_repo_diff_summary",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_repo_diff_summary,
    ),
    _make_tool(
        ToolSpec(
            tool_id="repo.recent_commits",
            display_name="Repo Recent Commits",
            description="Get the N most recent git commits (oneline format, read-only).",
            category="repo",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repo_path": {"type": "string"},
                    "n": {"type": "integer", "default": 10},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:repo"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_repo_recent_commits",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_repo_recent_commits,
    ),
    # ---------- Phase B: Tests ----------
    _make_tool(
        ToolSpec(
            tool_id="tests.discover",
            display_name="Tests Discover",
            description="Discover test files in the project's tests/ directory.",
            category="tests",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repo_path": {"type": "string"},
                    "tests_dir": {"type": "string", "default": "tests"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:repo"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_tests_discover",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_tests_discover,
    ),
    _make_tool(
        ToolSpec(
            tool_id="tests.run_targeted",
            display_name="Tests Run Targeted",
            description=(
                "Run pytest on a specific test file or directory. "
                "Safety: path must be within project repo and contain 'test' in name. "
                "Timeout: 120s. Output truncated to 50 KB."
            ),
            category="tests",
            input_schema={
                "type": "object",
                "properties": {
                    "test_path": {"type": "string"},
                    "project_id": {"type": "string"},
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Safe pytest flags only: -v, -q, -x, --tb=, --no-header, -k",
                    },
                },
                "required": ["test_path"],
            },
            output_schema={"type": "object"},
            required_permissions=["execute:tests"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_tests_run_targeted",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_tests_run_targeted,
    ),
    _make_tool(
        ToolSpec(
            tool_id="tests.report_summary",
            display_name="Tests Report Summary",
            description="Parse pytest output text and return structured pass/fail/error counts.",
            category="tests",
            input_schema={
                "type": "object",
                "properties": {
                    "output": {"type": "string", "description": "Raw pytest output text"},
                },
                "required": ["output"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:tests"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_tests_report_summary",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_tests_report_summary,
    ),
    # ---------- Phase B: Mission ----------
    _make_tool(
        ToolSpec(
            tool_id="mission.create_from_project_issue",
            display_name="Mission Create From Project Issue",
            description=(
                "Create a new queued mission from a project issue description. "
                "project_id is embedded in objective as '[project:<id>]' for traceability."
            ),
            category="mission",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "risk_level": {"type": "string", "default": "low"},
                },
                "required": ["project_id", "title"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:missions"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mission_create_from_project_issue",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mission_create_from_project_issue,
    ),
    _make_tool(
        ToolSpec(
            tool_id="mission.project_report",
            display_name="Mission Project Report",
            description=(
                "List missions associated with a project (scanned by '[project:<id>]' "
                "prefix in objective). Returns count by status."
            ),
            category="mission",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:missions"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mission_project_report",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mission_project_report,
    ),
    # ---------- Phase B: QA ----------
    _make_tool(
        ToolSpec(
            tool_id="qa.check_acceptance_evidence",
            display_name="QA Check Acceptance Evidence",
            description=(
                "Evaluate a list of evidence items against governance acceptance criteria. "
                "Returns ACCEPT/HOLD/UNSAFE verdict with missing evidence details."
            ),
            category="qa",
            input_schema={
                "type": "object",
                "properties": {
                    "evidence_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "status": {"type": "string", "enum": ["verified", "assumed", "missing", "insufficient"]},
                                "source": {"type": "string"},
                                "value": {},
                            },
                        },
                    },
                },
                "required": ["evidence_items"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:governance"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="qa",
            executor_ref="_exec_qa_check_acceptance_evidence",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_qa_check_acceptance_evidence,
    ),
    # ---------- Phase B: Governance ----------
    _make_tool(
        ToolSpec(
            tool_id="governance.classify_report",
            display_name="Governance Classify Report",
            description=(
                "Full governance classification report for an action_type: "
                "category, hard_gate flag, approval requirement, verdict, reason."
            ),
            category="governance",
            input_schema={
                "type": "object",
                "properties": {
                    "action_type": {"type": "string"},
                    "risk_level": {"type": "string", "default": "low"},
                    "agent_id": {"type": "string"},
                },
                "required": ["action_type"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:governance"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_governance_classify_report",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_governance_classify_report,
    ),
    _make_tool(
        ToolSpec(
            tool_id="governance.build_blocker_report",
            display_name="Governance Build Blocker Report",
            description=(
                "Build a structured Blocker report: exact blocker, why it matters, "
                "unblock path, can_continue_partially."
            ),
            category="governance",
            input_schema={
                "type": "object",
                "properties": {
                    "blocker": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "unblock_path": {"type": "string"},
                    "can_continue_partially": {"type": "boolean", "default": False},
                    "partial_scope": {"type": "string"},
                },
                "required": ["blocker"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:governance"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_governance_build_blocker_report",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_governance_build_blocker_report,
    ),
    # ---------- Phase C: Research ----------
    _make_tool(
        ToolSpec(
            tool_id="docs.summarize_text",
            display_name="Docs Summarize Text",
            description=(
                "Extract a summary from provided text: headers, lead paragraph, "
                "bullet points. Pure Python — no network, no AI call."
            ),
            category="research",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 2000},
                },
                "required": ["text"],
            },
            output_schema={"type": "object"},
            required_permissions=[],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="research",
            executor_ref="_exec_docs_summarize_text",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_docs_summarize_text,
    ),
    _make_tool(
        ToolSpec(
            tool_id="sources.capture",
            display_name="Sources Capture",
            description=(
                "Capture a text source (URL, document, snippet) with metadata "
                "into project memory for later retrieval."
            ),
            category="research",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "url": {"type": "string"},
                    "title": {"type": "string"},
                    "project_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="research",
            executor_ref="_exec_sources_capture",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_sources_capture,
    ),
    _make_tool(
        ToolSpec(
            tool_id="research.brief",
            display_name="Research Brief",
            description=(
                "Write a structured research brief (topic, findings, recommendations) "
                "to project memory."
            ),
            category="research",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "findings": {"type": "string"},
                    "recommendations": {"type": "string"},
                    "project_id": {"type": "string"},
                    "confidence": {"type": "number", "default": 0.7},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["topic", "findings"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="research",
            executor_ref="_exec_research_brief",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_research_brief,
    ),
    _make_tool(
        ToolSpec(
            tool_id="web.fetch_url",
            display_name="Web Fetch URL",
            description=(
                "Fetch a URL and return text content. Read-only GET, no auth, "
                "SSRF-protected (no private IPs). Timeout: 10s. Output: 20 KB max."
            ),
            category="research",
            input_schema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:web"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="research",
            executor_ref="_exec_web_fetch_url",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_web_fetch_url,
    ),
    _make_tool(
        ToolSpec(
            tool_id="browser.open_url",
            display_name="Browser Open URL",
            description=(
                "Open a URL in the system browser (macOS: open). "
                "Read-only: no forms, no auth, no mutations. "
                "dry_run=True returns URL without opening (safe for tests)."
            ),
            category="research",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["url"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:browser"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="research",
            executor_ref="_exec_browser_open_url",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_browser_open_url,
    ),
    # ---------- Phase C: web.search (NOT_CONFIGURED without TAVILY) ----------
    _make_tool(
        ToolSpec(
            tool_id="web.search",
            display_name="Web Search",
            description=(
                "Search the web via Tavily API. "
                "Returns not_configured without TAVILY_API_KEY."
            ),
            category="research",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:web"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=bool(
                os.environ.get("TAVILY_API_KEY", "")
                and not os.environ.get("TAVILY_API_KEY", "").startswith("<")
            ),
            approval_required=False,
            owning_agent_id="research",
            executor_ref="_exec_web_search",
            implementation_status=(
                ToolStatus.AVAILABLE
                if (
                    os.environ.get("TAVILY_API_KEY", "")
                    and not os.environ.get("TAVILY_API_KEY", "").startswith("<")
                )
                else ToolStatus.NOT_CONFIGURED
            ),
            blocker=(
                ""
                if (
                    os.environ.get("TAVILY_API_KEY", "")
                    and not os.environ.get("TAVILY_API_KEY", "").startswith("<")
                )
                else "TAVILY_API_KEY not set or placeholder"
            ),
        ),
        _exec_web_search,
    ),
    # ---------- Phase D: Communication ----------
    _make_tool(
        ToolSpec(
            tool_id="slack.draft_update",
            display_name="Slack Draft Update",
            description=(
                "Draft a Slack message. Does NOT send. "
                "Returns formatted text for review before sending."
            ),
            category="notify",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "project_id": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["high", "normal", "low"], "default": "normal"},
                },
                "required": ["body"],
            },
            output_schema={"type": "object"},
            required_permissions=["notify:slack"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_slack_draft_update",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_slack_draft_update,
    ),
    _make_tool(
        ToolSpec(
            tool_id="telegram.draft_alert",
            display_name="Telegram Draft Alert",
            description=(
                "Draft a Telegram alert message. Does NOT send. "
                "Returns formatted text for review before sending."
            ),
            category="notify",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "project_id": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["high", "normal", "low"], "default": "normal"},
                },
                "required": ["body"],
            },
            output_schema={"type": "object"},
            required_permissions=["notify:telegram"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_telegram_draft_alert",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_telegram_draft_alert,
    ),
    _make_tool(
        ToolSpec(
            tool_id="report.generate_status",
            display_name="Report Generate Status",
            description=(
                "Generate a text status report for a project: profile, mission summary, "
                "repo info. Reads from live ProjectRegistry and MissionStore."
            ),
            category="report",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string", "default": "omnix"}},
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects", "read:missions"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_report_generate_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_report_generate_status,
    ),
    _make_tool(
        ToolSpec(
            tool_id="report.generate_daily_digest",
            display_name="Report Generate Daily Digest",
            description=(
                "Generate a daily digest: running/blocked/completed missions "
                "and recent events. Optionally filtered by project_id."
            ),
            category="report",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:missions"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_report_generate_daily_digest",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_report_generate_daily_digest,
    ),
    _make_tool(
        ToolSpec(
            tool_id="approval.queue_summary",
            display_name="Approval Queue Summary",
            description="List pending approval queue items from the ApprovalStore.",
            category="report",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:approvals"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_approval_queue_summary",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_approval_queue_summary,
    ),
    # ---------- Phase E: Extended Memory ----------
    _make_tool(
        ToolSpec(
            tool_id="memory.project_summary",
            display_name="Memory Project Summary",
            description=(
                "List all memory entries for a project namespace "
                "(project:<id> by default)."
            ),
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "namespace": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["project_id"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_project_summary",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_project_summary,
    ),
    _make_tool(
        ToolSpec(
            tool_id="memory.record_decision",
            display_name="Memory Record Decision",
            description="Record a decision in project-scoped memory with [DECISION] tag.",
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "project_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "default": 0.9},
                },
                "required": ["content"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_record_decision",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_record_decision,
    ),
    _make_tool(
        ToolSpec(
            tool_id="memory.record_bug",
            display_name="Memory Record Bug",
            description="Record a bug in project-scoped memory with [BUG] tag.",
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "project_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_record_bug",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_record_bug,
    ),
    _make_tool(
        ToolSpec(
            tool_id="memory.record_fix",
            display_name="Memory Record Fix",
            description="Record a fix/resolution in project-scoped memory with [FIX] tag.",
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "project_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_record_fix",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_record_fix,
    ),
    _make_tool(
        ToolSpec(
            tool_id="memory.record_blocker",
            display_name="Memory Record Blocker",
            description="Record a blocker in project-scoped memory with [BLOCKER] tag.",
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "project_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_record_blocker",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_record_blocker,
    ),
    _make_tool(
        ToolSpec(
            tool_id="memory.record_validation",
            display_name="Memory Record Validation",
            description=(
                "Record a validation/acceptance result in project-scoped memory "
                "with [VALIDATION] tag."
            ),
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "project_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "default": 0.9},
                },
                "required": ["content"],
            },
            output_schema={"type": "object"},
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_record_validation",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_record_validation,
    ),
    _make_tool(
        ToolSpec(
            tool_id="memory.list_recent_project_entries",
            display_name="Memory List Recent Project Entries",
            description=(
                "List the most recent memory entries for a project across "
                "all namespaces, ordered by recency."
            ),
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["project_id"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_list_recent_project_entries",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_list_recent_project_entries,
    ),
    _make_tool(
        ToolSpec(
            tool_id="memory.scrub_check",
            display_name="Memory Scrub Check",
            description=(
                "Check whether a value would be rejected as a secret by the memory store. "
                "Returns would_reject=True if the value matches secret patterns."
            ),
            category="memory",
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            output_schema={"type": "object"},
            required_permissions=[],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_scrub_check",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_scrub_check,
    ),
]


# ===========================================================================
# Registration
# ===========================================================================


def _is_workflow_initialized() -> bool:
    return ToolRegistry.get("project.status") is not None


def initialize_workflow_catalog() -> None:
    """Register all Sprint 5 workflow tools into ToolRegistry.

    Safe to call multiple times — skips if already initialized.
    """
    if _is_workflow_initialized():
        return
    for spec, executor in _WORKFLOW_TOOL_DEFS:
        ToolRegistry.register(spec, executor=executor)
    stats = ToolRegistry.stats()
    logger.info(
        "Workflow catalog initialized: total=%d available=%d unavailable=%d",
        stats["total_registered"],
        stats["available"],
        stats["unavailable"],
    )


__all__ = ["initialize_workflow_catalog"]
