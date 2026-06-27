"""macOS desktop integration for VANTA — app control, global hotkey, menu bar.

Replaces the removed always-on background mic listener (which triggered from
ambient noise). VANTA is now launched/foregrounded via a global hotkey
(Cmd+Shift+V) and a menu-bar icon. Voice wake works only inside the running app.
"""

from openjarvis.macos.app_control import (
    APP_NAME,
    APP_PROCESS,
    HOTKEY,
    launch_or_foreground,
    start_tray_agent,
)

__all__ = ["APP_NAME", "APP_PROCESS", "HOTKEY", "launch_or_foreground", "start_tray_agent"]
