#!/usr/bin/env bash
# DEPRECATED — the always-on background wake listener was removed because it
# triggered randomly from ambient noise. Voice wake now works ONLY inside the
# VANTA app (foreground or background). Launch VANTA with the Cmd+Shift+V global
# hotkey or the menu-bar icon instead.
#
# This script now only CLEANS UP any previously-installed launchd agent. It no
# longer installs anything. Safe to run multiple times.
set -euo pipefail

LABEL="com.vanta.wake.listener"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

echo "The background wake listener has been removed."
if [[ -f "$PLIST" ]]; then
  echo "Cleaning up leftover launchd agent…"
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed $PLIST"
else
  echo "No launchd agent installed — nothing to do."
fi
echo "Use Cmd+Shift+V or the menu-bar icon to launch VANTA."
exit 0
