"""File search tool — grep/find-based search with ripgrep fallback."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_MAX_OUTPUT_BYTES = 102_400
_MAX_RESULTS = 200


@ToolRegistry.register("file_search")
class FileSearchTool(BaseTool):
    """Search files using ripgrep (rg) or grep fallback."""

    tool_id = "file_search"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_search",
            description=(
                "Search file contents using ripgrep (rg) or grep."
                " Returns matching lines with file path and line number."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (regex or literal string).",
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in. Default: current directory.",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "File glob pattern (e.g., '*.py'). Optional.",
                    },
                    "fixed_strings": {
                        "type": "boolean",
                        "description": "Treat pattern as literal string, not regex. Default: false.",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case-sensitive search. Default: false.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": f"Max results to return. Default: {_MAX_RESULTS}.",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Lines of context around matches. Default: 0.",
                    },
                },
                "required": ["pattern"],
            },
            category="filesystem",
            required_capabilities=["file:read"],
        )

    def execute(self, **params: Any) -> ToolResult:
        pattern = params.get("pattern", "")
        if not pattern:
            return ToolResult(
                tool_name="file_search",
                content="No pattern provided.",
                success=False,
            )

        directory = params.get("directory", ".")
        file_glob = params.get("file_glob")
        fixed_strings = params.get("fixed_strings", False)
        case_sensitive = params.get("case_sensitive", False)
        max_results = min(int(params.get("max_results", _MAX_RESULTS)), _MAX_RESULTS)
        context_lines = int(params.get("context_lines", 0))

        dir_path = Path(directory)
        if not dir_path.exists():
            return ToolResult(
                tool_name="file_search",
                content=f"Directory not found: {directory}",
                success=False,
            )

        if shutil.which("rg"):
            return self._run_rg(
                pattern, str(dir_path), file_glob,
                fixed_strings, case_sensitive, max_results, context_lines,
            )
        return self._run_grep(
            pattern, str(dir_path), file_glob,
            fixed_strings, case_sensitive, max_results, context_lines,
        )

    def _run_rg(
        self,
        pattern: str,
        directory: str,
        file_glob: Optional[str],
        fixed_strings: bool,
        case_sensitive: bool,
        max_results: int,
        context_lines: int,
    ) -> ToolResult:
        cmd: List[str] = ["rg", "--line-number", "--no-heading"]
        if fixed_strings:
            cmd.append("--fixed-strings")
        if not case_sensitive:
            cmd.append("--ignore-case")
        if file_glob:
            cmd.extend(["--glob", file_glob])
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        cmd.extend(["--max-count", str(max_results)])
        cmd.append(pattern)
        cmd.append(directory)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout
            if len(output) > _MAX_OUTPUT_BYTES:
                output = output[:_MAX_OUTPUT_BYTES] + "\n... (output truncated)"
            return ToolResult(
                tool_name="file_search",
                content=output or "(no matches)",
                success=True,
                metadata={
                    "tool": "rg",
                    "pattern": pattern,
                    "directory": directory,
                    "match_count": output.count("\n") if output else 0,
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="file_search",
                content="Search timed out after 30 seconds.",
                success=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="file_search",
                content=f"rg error: {exc}",
                success=False,
            )

    def _run_grep(
        self,
        pattern: str,
        directory: str,
        file_glob: Optional[str],
        fixed_strings: bool,
        case_sensitive: bool,
        max_results: int,
        context_lines: int,
    ) -> ToolResult:
        cmd: List[str] = ["grep", "-rn"]
        if fixed_strings:
            cmd.append("-F")
        if not case_sensitive:
            cmd.append("-i")
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        if file_glob:
            cmd.extend(["--include", file_glob])
        cmd.extend(["-m", str(max_results)])
        cmd.append(pattern)
        cmd.append(directory)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout
            if len(output) > _MAX_OUTPUT_BYTES:
                output = output[:_MAX_OUTPUT_BYTES] + "\n... (output truncated)"
            return ToolResult(
                tool_name="file_search",
                content=output or "(no matches)",
                success=result.returncode in (0, 1),
                metadata={
                    "tool": "grep",
                    "pattern": pattern,
                    "directory": directory,
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="file_search",
                content="Search timed out after 30 seconds.",
                success=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="file_search",
                content=f"grep error: {exc}",
                success=False,
            )


__all__ = ["FileSearchTool"]
