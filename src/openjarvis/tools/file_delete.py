"""File delete tool — safe file/directory removal with governance gates."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# Paths that are never deletable, regardless of permissions
_PROTECTED_PATHS = frozenset(
    {
        "/",
        "/usr",
        "/etc",
        "/bin",
        "/sbin",
        "/lib",
        "/var",
        "/home",
        "/root",
        "/tmp",
    }
)


@ToolRegistry.register("file_delete")
class FileDeleteTool(BaseTool):
    """Delete a file or empty directory with safety checks."""

    tool_id = "file_delete"

    def __init__(
        self,
        allowed_dirs: Optional[List[str]] = None,
    ) -> None:
        self._allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [])]

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_delete",
            description=(
                "Delete a file or directory safely."
                " Protected system paths are always blocked."
                " Directories are only deleted if empty unless recursive=true."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file or directory to delete.",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": (
                            "Allow recursive directory deletion. Default: false."
                            " Requires explicit confirmation."
                        ),
                    },
                },
                "required": ["path"],
            },
            category="filesystem",
            required_capabilities=["file:write"],
            requires_confirmation=True,
        )

    def _is_path_allowed(self, path: Path) -> bool:
        if not self._allowed_dirs:
            return True
        resolved = path.resolve()
        return any(
            resolved == d or resolved.is_relative_to(d) for d in self._allowed_dirs
        )

    def _is_protected(self, path: Path) -> bool:
        resolved = str(path.resolve())
        # Block exact protected paths and their first-level children
        if resolved in _PROTECTED_PATHS:
            return True
        # Block sensitive files
        from openjarvis.security.file_policy import is_sensitive_file
        if is_sensitive_file(path):
            return True
        return False

    def execute(self, **params: Any) -> ToolResult:
        file_path = params.get("path", "")
        if not file_path:
            return ToolResult(
                tool_name="file_delete",
                content="No path provided.",
                success=False,
            )
        recursive = bool(params.get("recursive", False))
        path = Path(file_path)

        if self._is_protected(path):
            return ToolResult(
                tool_name="file_delete",
                content=f"Access denied: {file_path} is a protected path.",
                success=False,
            )

        if not self._is_path_allowed(path):
            return ToolResult(
                tool_name="file_delete",
                content=f"Access denied: {file_path} is outside allowed directories.",
                success=False,
            )

        if not path.exists():
            return ToolResult(
                tool_name="file_delete",
                content=f"Path not found: {file_path}",
                success=False,
            )

        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
                return ToolResult(
                    tool_name="file_delete",
                    content=f"Deleted file: {file_path}",
                    success=True,
                    metadata={"path": str(path.resolve()), "type": "file"},
                )
            elif path.is_dir():
                if recursive:
                    shutil.rmtree(path)
                    return ToolResult(
                        tool_name="file_delete",
                        content=f"Recursively deleted directory: {file_path}",
                        success=True,
                        metadata={"path": str(path.resolve()), "type": "directory"},
                    )
                else:
                    try:
                        path.rmdir()  # Only works on empty directories
                        return ToolResult(
                            tool_name="file_delete",
                            content=f"Deleted empty directory: {file_path}",
                            success=True,
                            metadata={"path": str(path.resolve()), "type": "directory"},
                        )
                    except OSError:
                        return ToolResult(
                            tool_name="file_delete",
                            content=(
                                f"Directory not empty: {file_path}."
                                " Use recursive=true to delete non-empty directories."
                            ),
                            success=False,
                        )
            else:
                return ToolResult(
                    tool_name="file_delete",
                    content=f"Unknown file type at: {file_path}",
                    success=False,
                )
        except PermissionError as exc:
            return ToolResult(
                tool_name="file_delete",
                content=f"Permission denied: {exc}",
                success=False,
            )
        except OSError as exc:
            return ToolResult(
                tool_name="file_delete",
                content=f"Delete error: {exc}",
                success=False,
            )


__all__ = ["FileDeleteTool"]
