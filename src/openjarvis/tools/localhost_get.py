"""Localhost GET tool — read-only HTTP GET requests to localhost only."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

logger = logging.getLogger(__name__)

# Maximum response body size: 1 MB
_MAX_RESPONSE_BYTES = 1_048_576

# Allowed hosts for this tool
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@ToolRegistry.register("localhost_get")
class LocalhostGetTool(BaseTool):
    """Make read-only HTTP GET requests to localhost only.

    This tool is designed for safe local status inspection, such as fetching
    local dashboard endpoints. It only allows GET requests to localhost addresses
    and does not support headers, body, or other HTTP methods.
    """

    tool_id = "localhost_get"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="localhost_get",
            description=(
                "Make a read-only HTTP GET request to localhost only."
                " Only allows GET method and localhost/127.0.0.1 addresses."
                " No headers, body, or other HTTP methods supported."
                " Designed for safe local status inspection."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "The localhost URL to fetch."
                            " Must use http://127.0.0.1 or http://localhost."
                        ),
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout in seconds. Defaults to 10.",
                    },
                },
                "required": ["url"],
            },
            category="network",
            required_capabilities=["network:fetch"],
        )

    def execute(self, **params: Any) -> ToolResult:
        url = params.get("url", "")
        if not url:
            return ToolResult(
                tool_name="localhost_get",
                content="No URL provided.",
                success=False,
            )

        # Validate URL is localhost only
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return ToolResult(
                tool_name="localhost_get",
                content="Invalid URL: no hostname.",
                success=False,
            )

        if hostname not in _ALLOWED_HOSTS:
            return ToolResult(
                tool_name="localhost_get",
                content=f"URL must use localhost only. Got: {hostname}",
                success=False,
            )

        # Only allow http scheme (no https for localhost to avoid cert issues)
        if parsed.scheme != "http":
            return ToolResult(
                tool_name="localhost_get",
                content="Only http scheme is supported for localhost.",
                success=False,
            )

        timeout = params.get("timeout", 10)

        try:
            response = httpx.get(url, timeout=float(timeout), follow_redirects=True)
            
            # Truncate response body if larger than 1 MB
            raw_body = response.text
            truncated = False
            if len(raw_body) > _MAX_RESPONSE_BYTES:
                raw_body = raw_body[:_MAX_RESPONSE_BYTES]
                truncated = True

            content = raw_body
            if truncated:
                content += "\n\n[Response truncated at 1 MB]"

            return ToolResult(
                tool_name="localhost_get",
                content=content,
                success=True,
                metadata={
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "truncated": truncated,
                },
            )
        except httpx.TimeoutException as exc:
            return ToolResult(
                tool_name="localhost_get",
                content=f"Request timed out after {timeout}s: {exc}",
                success=False,
            )
        except httpx.RequestError as exc:
            return ToolResult(
                tool_name="localhost_get",
                content=f"Request error: {exc}",
                success=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="localhost_get",
                content=f"Unexpected error: {exc}",
                success=False,
            )


__all__ = ["LocalhostGetTool"]
