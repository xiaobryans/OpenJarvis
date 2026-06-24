# OpenJarvis Claude Code Hooks

Hook scripts are **prepared but NOT yet activated**.
Activation requires wiring into `.claude/settings.json` (see template below).
Review each hook before activating. Do not auto-activate in CI or shared env.

## Hooks included

| Script | Trigger | Exit | Purpose |
|--------|---------|------|---------|
| `warn-env-access.sh` | PreToolUse (Read/Edit/Write) | 0 (warn only) | Warn when .env or secret-looking files are opened |
| `warn-tauri-build.sh` | PreToolUse (Bash) | 2 (block) | Block `build-local.sh --install` during Plan 2 |
| `remind-diff-check.sh` | PostToolUse (Bash) | 0 (warn only) | Remind to run `git diff --check` after git operations |
| `remind-action-ledger.sh` | PostToolUse (Bash) | 0 (warn only) | Remind to log action in sprint ledger after git ops |

## Activation

Add to `.claude/settings.json` (create if it doesn't exist):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/warn-env-access.sh"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/warn-tauri-build.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/remind-diff-check.sh"
          },
          {
            "type": "command",
            "command": "bash .claude/hooks/remind-action-ledger.sh"
          }
        ]
      }
    ]
  }
}
```

**Note:** Hook scripts receive tool input JSON on stdin and can:
- Write warnings to stderr (shown to Claude without blocking).
- Exit with code 2 to block the tool call (use sparingly — only for hard stops).
- Exit with code 0 to allow the tool call to proceed.

## What is NOT allowed in hooks
- Auto-deploy
- Auto-push without approval
- Auto-run destructive commands
- Auto-access external services
- Long validation loops
