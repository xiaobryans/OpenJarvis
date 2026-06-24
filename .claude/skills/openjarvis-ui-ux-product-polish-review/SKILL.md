---
name: openjarvis-ui-ux-product-polish-review
description: Review Jarvis UI/UX changes for Jarvis PA identity, product polish, mobile/desktop parity, accessibility, and real Jarvis end-goal alignment. Reads actual component files. Produces PASS | NEEDS_POLISH per component. Use before any UI-touching sprint is marked ready for review.
---

# OpenJarvis UI/UX Product Polish Review

Reviews UI/UX changes for **Jarvis PA identity**, **product polish**, and real Jarvis end-goal alignment.

## When to use
- Before any sprint touching frontend/UI components is marked ready for review.
- When `/ui-product-polish-review` is invoked.
- As part of Plan 4–6 UI/UX product polish work.

## Steps

1. Find all changed UI/frontend files in the sprint.
2. Invoke `ui-ux-product-reviewer` agent for each component.
3. Review: Jarvis PA identity, product polish, mobile/desktop parity, accessibility, real Jarvis end-goal alignment.
4. Flag regressions from prior accepted state.
5. Produce PASS | NEEDS_POLISH verdict per component.

## Safe commands
```bash
git diff HEAD~1..HEAD --name-only | grep -E '\.(tsx|ts|css|html|svelte)$'
```

## Output
```
UI/UX PRODUCT POLISH REVIEW
[structured output from ui-ux-product-reviewer agent]
OVERALL: PASS | NEEDS_POLISH
REQUIRED FIXES: [list]
```
