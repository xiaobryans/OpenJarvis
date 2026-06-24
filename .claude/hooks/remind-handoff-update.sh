#!/usr/bin/env bash
# PostToolUse hook: remind to run /handoff-save after git commit operations.
# Receives Bash tool input/output JSON on stdin.
# Exit 0 always (reminder only — never blocks).

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('input',{}).get('command',''))" 2>/dev/null || true)

# Remind after git commit or push operations
if echo "$COMMAND" | grep -qE 'git (commit|push)'; then
  echo "[HANDOFF REMINDER] Run '/handoff-save' or update docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md." >&2
  echo "[HANDOFF REMINDER] The handoff files should reflect the new HEAD after this commit/push." >&2
  echo "[HANDOFF REMINDER] Update RESUME_FROM_HERE and safe_to_continue_automatically in the session state file." >&2
fi

exit 0
