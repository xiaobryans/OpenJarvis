# /plan2-report

Generate the **required 13-point OpenJarvis sprint final report**.

## What this does
Runs the `plan2-report` skill to produce the mandatory report format:
1. Verdict
2. Branch
3. Previous HEAD
4. New HEAD
5. Changed files
6. Files inspected and why
7. Root cause
8. Exact fix
9. Validation command outputs
10. Secret scan result
11. Proof accepted checkpoints were not regressed
12. Tauri rebuild deferred statement
13. Remaining blockers

## Rules
- All 13 points required — no skipping.
- No fake PASS / no fake ACCEPTED.
- No secret values in any field.
- Use data collected during the sprint — do not re-run commands if outputs
  are already recorded; include them verbatim.
