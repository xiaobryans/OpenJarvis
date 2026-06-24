#!/usr/bin/env bash
# PostToolUse hook: remind to run git diff --check and secret scan after git operations.
# Receives Bash tool input/output JSON on stdin.
# Exit 0 always (reminder only — never blocks).

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('input',{}).get('command',''))" 2>/dev/null || true)

# Remind after git add, git commit, or git stage operations
if echo "$COMMAND" | grep -qE 'git (add|commit|stage)'; then
  echo "[HOOK REMINDER] Run 'git diff --check' to verify no whitespace/conflict markers." >&2
  echo "[HOOK REMINDER] Run '/secret-scan' (or the secret-safety-review skill) on staged files before committing." >&2
fi

exit 0
