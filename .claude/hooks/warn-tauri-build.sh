#!/usr/bin/env bash
# PreToolUse hook: block 'bash scripts/build-local.sh --install' during Plan 2.
# Receives Bash tool input JSON on stdin.
# Exit 0 = allow. Exit 2 = block with message.

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null || true)

if echo "$COMMAND" | grep -qE 'build-local\.sh.*--install|--install.*build-local\.sh'; then
  echo "[HOOK BLOCK] 'bash scripts/build-local.sh --install' is blocked during Plan 2." >&2
  echo "[HOOK BLOCK] Tauri rebuild is deferred until full Plan 2 completion (CLAUDE.md rule)." >&2
  echo "[HOOK BLOCK] To override, Bryan must explicitly approve a Tauri rebuild for this sprint." >&2
  exit 2
fi

exit 0
