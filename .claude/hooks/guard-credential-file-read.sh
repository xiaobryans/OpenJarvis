#!/usr/bin/env bash
# PreToolUse hook: block Read/Edit/Write on credential files.
# More specific than warn-env-access.sh — this BLOCKS (exit 2) on high-risk credential files.
# warn-env-access.sh warns on any sensitive-looking file; this blocks on the most dangerous ones.
# Receives Read/Edit/Write tool input JSON on stdin.
# Exit 0 = allow. Exit 2 = block with message.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null || true)

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH")
DIRPATH=$(dirname "$FILE_PATH")

# Block these specific high-risk credential file patterns
BLOCK_PATTERN='^(gmail\.json|google.*token.*\.json|oauth.*token.*\.json|\.env\.local|cloud-keys\.env|.*_private_key\.json|service-account.*\.json)$'
BLOCK_DIRS='cloud-keys\.env|\.openjarvis/connectors'

if echo "$BASENAME" | grep -qiE "$BLOCK_PATTERN"; then
  echo "[HOOK BLOCK] Reading credential file is blocked: $FILE_PATH" >&2
  echo "[HOOK BLOCK] CLAUDE.md rule: never intentionally read OAuth token files, .env.local, private keys, or credential files for their contents." >&2
  echo "[HOOK BLOCK] If you need to check presence: use 'test -f [path] && echo PRESENT || echo ABSENT' in Bash, not Read." >&2
  exit 2
fi

if echo "$DIRPATH" | grep -qE "$BLOCK_DIRS"; then
  echo "[HOOK BLOCK] Reading from credential directory is blocked: $FILE_PATH" >&2
  echo "[HOOK BLOCK] CLAUDE.md rule: never read OAuth token files or credential files for their contents." >&2
  echo "[HOOK BLOCK] For presence checks, use Bash with 'test -f' not Read." >&2
  exit 2
fi

exit 0
