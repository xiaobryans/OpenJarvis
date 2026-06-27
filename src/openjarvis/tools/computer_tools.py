"""Computer control by voice (3E) — open/close/switch apps, screenshot, open
files, make folders on the Mac via ``open``, ``osascript`` and shell.

Command construction is split into pure helpers so it is unit-testable; the
``execute`` paths run the real commands (macOS only).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any, List

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


# ── pure command builders (testable) ─────────────────────────────────────────
def open_app_cmd(app: str) -> List[str]:
    return ["open", "-a", app]


def quit_app_cmd(app: str) -> List[str]:
    return ["osascript", "-e", f'tell application "{app}" to quit']


def activate_app_cmd(app: str) -> List[str]:
    return ["osascript", "-e", f'tell application "{app}" to activate']


def open_path_cmd(path: str) -> List[str]:
    return ["open", os.path.expanduser(path)]


def _run(cmd: List[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()
    except Exception as exc:  # pragma: no cover - needs macOS
        return False, str(exc)


@ToolRegistry.register("computer_control")
class ComputerControlTool(BaseTool):
    """Control the Mac: open/close/switch apps, screenshot, open files, new folder."""

    tool_id = "computer_control"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="computer_control",
            description="Control the Mac by voice/text. actions: open_app, close_app, switch_app, "
                        "screenshot, open_file, new_folder. Provide 'target' (app name, file path, or folder name).",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["open_app", "close_app", "switch_app", "screenshot", "open_file", "new_folder"]},
                    "target": {"type": "string", "description": "App name, file path, or folder name."},
                },
                "required": ["action"],
            },
            category="system",
        )

    def execute(self, **p: Any) -> ToolResult:
        action = (p.get("action") or "").lower().strip()
        target = (p.get("target") or "").strip()
        if action in ("open_app", "close_app", "switch_app", "open_file", "new_folder") and not target:
            return ToolResult(tool_name=self.tool_id, content=f"{action} needs a target.", success=False, metadata={})

        if action == "open_app":
            ok, err = _run(open_app_cmd(target))
            return ToolResult(tool_name=self.tool_id, content=(f"Opened {target}." if ok else f"Couldn't open {target}: {err}"), success=ok, metadata={})
        if action == "close_app":
            ok, err = _run(quit_app_cmd(target))
            return ToolResult(tool_name=self.tool_id, content=(f"Closed {target}." if ok else f"Couldn't close {target}: {err}"), success=ok, metadata={})
        if action == "switch_app":
            ok, err = _run(activate_app_cmd(target))
            return ToolResult(tool_name=self.tool_id, content=(f"Switched to {target}." if ok else f"Couldn't switch: {err}"), success=ok, metadata={})
        if action == "open_file":
            ok, err = _run(open_path_cmd(target))
            return ToolResult(tool_name=self.tool_id, content=(f"Opened {target}." if ok else f"Couldn't open {target}: {err}"), success=ok, metadata={})
        if action == "new_folder":
            path = os.path.expanduser(target if "/" in target else f"~/Desktop/{target}")
            try:
                os.makedirs(path, exist_ok=True)
                return ToolResult(tool_name=self.tool_id, content=f"Created folder {path}.", success=True, metadata={"path": path})
            except Exception as exc:
                return ToolResult(tool_name=self.tool_id, content=f"Couldn't create folder: {exc}", success=False, metadata={})
        if action == "screenshot":
            out = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
            ok, err = _run(["screencapture", "-x", out])
            return ToolResult(tool_name=self.tool_id, content=(f"Screenshot saved to {out}." if ok else f"Screenshot failed: {err}"), success=ok, metadata={"path": out})
        return ToolResult(tool_name=self.tool_id, content=f"Unknown action: {action}", success=False, metadata={})


__all__ = ["ComputerControlTool", "open_app_cmd", "quit_app_cmd", "activate_app_cmd", "open_path_cmd"]
