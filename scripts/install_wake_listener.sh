#!/usr/bin/env bash
#
# Install (or remove) the VANTA always-on wake listener as a launchd agent.
# Run once to set up:    scripts/install_wake_listener.sh
# Remove:                scripts/install_wake_listener.sh --remove
#
# The listener detects "Hey VANTA" or a double clap and launches/fronts the
# VANTA app. It does NOT run the brain/TTS — the app's own voice loop does that.
#
set -euo pipefail

LABEL="com.vanta.wake.listener"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO_DIR/deploy/launchd/${LABEL}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG="$HOME/Library/Logs/vanta-wake.log"

if [[ "${1:-}" == "--remove" || "${1:-}" == "-r" ]]; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  rm -f "$PLIST_DST"
  echo "Removed $LABEL (plist deleted, agent unloaded)."
  exit 0
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: plist template not found: $TEMPLATE" >&2
  exit 1
fi

# Prefer the repo virtualenv python; fall back to system python3.
PYTHON="$REPO_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: no python found (.venv/bin/python or python3)." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$(dirname "$LOG")"

# Substitute absolute paths into the template (launchd does not expand ~).
sed -e "s#__PYTHON__#${PYTHON}#g" \
    -e "s#__WORKDIR__#${REPO_DIR}#g" \
    -e "s#__LOG__#${LOG}#g" \
    "$TEMPLATE" > "$PLIST_DST"

# Reload cleanly.
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Installed and loaded $LABEL"
echo "  python: $PYTHON"
echo "  plist:  $PLIST_DST"
echo "  log:    $LOG"
echo
echo "It starts at every login and detects 'Hey VANTA' / double clap to open VANTA."
echo "Uninstall with: $0 --remove"
