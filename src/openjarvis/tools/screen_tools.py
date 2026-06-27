"""Screen awareness tool (2A) — VANTA can see the Mac screen on request.

"Hey VANTA what's on my screen" -> screenshot via macOS ``screencapture`` ->
GPT-4o vision -> a short description. Ivy speaks a summary; the full text shows
on screen. Registered as the ``screen_capture`` orchestrator tool.
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def capture_screen_png(path: Optional[str] = None) -> Optional[str]:
    """Take a silent screenshot via ``screencapture -x``; return the file path."""
    target = path or tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    try:
        subprocess.run(["screencapture", "-x", target], check=True, timeout=15)
        return target
    except Exception:  # pragma: no cover - needs macOS + screen-recording perm
        return None


def describe_image_with_gpt4o(image_path: str, question: str = "") -> str:
    """Send a PNG to GPT-4o vision and return its description (or an error str)."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return "OPENAI_API_KEY not set — cannot run vision."
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        import httpx
        prompt = question.strip() or "Briefly describe what is on this screen."
        with httpx.Client(timeout=60) as c:
            r = c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ],
                    }],
                    "max_tokens": 400,
                },
            )
            r.raise_for_status()
            return (((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    except Exception as exc:  # pragma: no cover - network
        return f"Vision request failed: {exc}"


@ToolRegistry.register("screen_capture")
class ScreenCaptureTool(BaseTool):
    """Look at the user's screen and describe it (2A)."""

    tool_id = "screen_capture"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="screen_capture",
            description="Take a screenshot of the Mac screen and describe what's on it. "
                        "Use for 'what's on my screen', 'read this', 'what does this say'.",
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "What to look for / answer about the screen."},
                },
                "required": [],
            },
            category="system",
        )

    def execute(self, **p: Any) -> ToolResult:
        path = capture_screen_png()
        if not path:
            return ToolResult(tool_name=self.tool_id,
                              content="Couldn't capture the screen (grant Screen Recording permission to the app).",
                              success=False, metadata={})
        desc = describe_image_with_gpt4o(path, p.get("question", ""))
        return ToolResult(tool_name=self.tool_id, content=desc, success=bool(desc), metadata={"image_path": path})


__all__ = ["ScreenCaptureTool", "capture_screen_png", "describe_image_with_gpt4o"]
