"""Jarvis Universal Front Door.

The front door is the entry point for any Bryan request regardless of project.
OMNIX, OpenJarvis, personal tasks, research, automation, and future projects
all enter through the same front door. Routing is fully internal.

Key types:
  - UniversalTaskRequest  — any request from Bryan, with optional project context
  - FrontDoorResult       — unified result returned after orchestration
  - FrontDoorAdapter      — ABC for project-specific adapters (OMNIX, etc.)
  - JarvisFrontDoor       — universal entry point
"""

from openjarvis.frontdoor.frontdoor import (
    UniversalTaskRequest,
    FrontDoorResult,
    FrontDoorAdapter,
    JarvisFrontDoor,
    get_jarvis_front_door,
)

__all__ = [
    "UniversalTaskRequest",
    "FrontDoorResult",
    "FrontDoorAdapter",
    "JarvisFrontDoor",
    "get_jarvis_front_door",
]
