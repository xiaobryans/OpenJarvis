#!/usr/bin/env bash
# PreToolUse hook: warn when a file write contains ACCEPTED/PLAN_X_ACCEPTED patterns.
# Only Bryan or designated ChatGPT reviewer can mark acceptance.
# Receives Edit/Write tool input JSON on stdin.
# Exit 0 = allow (warn only). Exit 2 = block with message.
# NOTE: This hook warns and allows (exit 0) — it does not hard-block.
# Hard-blocking writes is too invasive; this is a prominent warning to trigger review.

set -euo pipefail

INPUT=$(cat)

# Extract content being written (Edit: new_string; Write: content)
CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('new_string', d.get('content', '')))
except Exception:
    print('')
" 2>/dev/null || true)

# Check for acceptance labels that only Bryan can grant
ACCEPTANCE_PATTERN='(PLAN_[0-9A-Z_]+_ACCEPTED|_ACCEPTED[^_]|VERDICT.*ACCEPTED|status.*ACCEPTED)'

if echo "$CONTENT" | grep -qE "$ACCEPTANCE_PATTERN"; then
  echo "[HOOK WARNING] This write contains an ACCEPTED label pattern." >&2
  echo "[HOOK WARNING] CLAUDE.md rule: No agent may claim acceptance on Bryan's behalf." >&2
  echo "[HOOK WARNING] Only Bryan (or designated ChatGPT reviewer) can mark a plan ACCEPTED." >&2
  echo "[HOOK WARNING] If this is a READY_FOR_REVIEW verdict (not ACCEPTED), this warning can be ignored." >&2
  echo "[HOOK WARNING] If you are writing an ACCEPTED label: stop and verify Bryan has explicitly granted acceptance." >&2
fi

# Allow the write (warn only — do not block legitimate doc updates)
exit 0
