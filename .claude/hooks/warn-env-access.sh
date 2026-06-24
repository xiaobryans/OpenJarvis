#!/usr/bin/env bash
# PreToolUse hook: warn when .env or secret-looking files are about to be read/edited.
# Receives tool input JSON on stdin. Writes warning to stderr. Never prints file contents.
# Exit 0 = allow. Exit 2 = block with message.

set -euo pipefail

INPUT=$(cat)

# Extract the file path from the tool input (Read/Edit/Write tools use "file_path")
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null || true)

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH")
SENSITIVE_PATTERN='^(\.env|\.env\..+|.*\.pem|.*\.key|.*_secret|.*_token|.*credentials.*|.*secrets.*|google.*token.*\.json|oauth.*\.json)$'

if echo "$BASENAME" | grep -qiE "$SENSITIVE_PATTERN"; then
  echo "[HOOK WARNING] Accessing potentially sensitive file: $FILE_PATH" >&2
  echo "[HOOK WARNING] Reminder: presence-only reporting — do NOT print file contents or secret values." >&2
  # Allow access (exit 0) — warn only, do not block
fi

exit 0
