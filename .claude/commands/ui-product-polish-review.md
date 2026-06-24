# /ui-product-polish-review

Run a **UI/UX product polish review** of changed frontend components.

## Usage
```
/ui-product-polish-review
/ui-product-polish-review [component path]
```

## What this does
Runs the `openjarvis-ui-ux-product-polish-review` skill:
1. Finds all changed UI/frontend files.
2. Invokes `ui-ux-product-reviewer` agent for each component.
3. Reviews: Jarvis PA identity, product polish, mobile/desktop parity, accessibility, real Jarvis end-goal alignment.
4. Flags regressions from prior accepted state.
5. Produces PASS | NEEDS_POLISH per component.

## Output
```
UI/UX PRODUCT POLISH REVIEW
[N] components reviewed
[component]: PASS | NEEDS_POLISH
OVERALL: PASS | NEEDS_POLISH
REQUIRED FIXES: [list]
```

## Rules
- Reads actual component files — no assumptions.
- Flags regressions; does not suggest redesigns.
