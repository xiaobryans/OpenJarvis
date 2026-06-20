"""ECC execution wrappers — Jarvis-native sandboxed wiring for ECC skills.

All wrappers enforce:
  - dry_run mode by default (no side effects without explicit dry_run=False)
  - permission gate (requires explicit Jarvis permission scope grant)
  - allowlist-only execution (no raw ECC code runs)
  - disable/quarantine/rollback path
  - no raw ECC code or hooks executed

Wrappers are disabled unless Bryan provides explicit approval (reviewer_approved=True).
"""
