#!/usr/bin/env bash
# PreToolUse hook: block 'git add .' and 'git add -A' — explicit staging only.
# Receives Bash tool input JSON on stdin.
# Exit 0 = allow. Exit 2 = block with message.

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null || true)

# Block 'git add .' and 'git add -A' in any form
if echo "$COMMAND" | grep -qE 'git add (\.|-A)( |$)'; then
  echo "[HOOK BLOCK] 'git add .' and 'git add -A' are prohibited in OpenJarvis sprints." >&2
  echo "[HOOK BLOCK] Use explicit file paths: git add <file1> <file2> ..." >&2
  echo "[HOOK BLOCK] CLAUDE.md rule: never stage unrelated dirty files; use explicit staging paths." >&2
  echo "[HOOK BLOCK] Known unrelated dirty files: JARVIS_OMNIX_HANDOFF.md, tests/workbench/test_us14a_fixture.py, evidence/, scripts/plan1_cockpit_proof.py, scripts/plan9_copy_cloud_api_key.sh, scripts/plan9_verify_cloud_api_key.py" >&2
  exit 2
fi

exit 0
