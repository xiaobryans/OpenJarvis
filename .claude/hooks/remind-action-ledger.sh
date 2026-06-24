#!/usr/bin/env bash
# PostToolUse hook: remind to update the action ledger after medium/high-risk operations.
# Receives tool output JSON on stdin. Writes reminder to stderr. Never blocks (exit 0).

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # PostToolUse wraps input under 'input' key
    cmd = d.get('input', d).get('command', '')
    print(cmd)
except Exception:
    print('')
" 2>/dev/null <<< "$INPUT" || true)

# Remind after staging, committing, or pushing — these are medium/high-risk actions
if echo "$COMMAND" | grep -qE 'git (add|commit|push|reset|checkout|merge|rebase)'; then
  echo "[LEDGER REMINDER] Log this action in the sprint action ledger." >&2
  echo "[LEDGER REMINDER] Required fields: action, reason, risk level, files, command, validation, result, Bryan approval?" >&2
  echo "[LEDGER REMINDER] Run /automation-ledger to view or update the current ledger." >&2
fi

exit 0
