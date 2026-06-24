# /endpoint-security-audit

Run a **full endpoint security audit** of all public OpenJarvis API routes.

## Usage
```
/endpoint-security-audit
/endpoint-security-audit [route file path]
```

## What this does
Runs the `openjarvis-endpoint-security-audit` skill:
1. Lists all endpoints in `plan2_routes.py` and related route files.
2. Checks auth gate enforcement (Bearer check before data).
3. Checks response schemas for field leakage (token presence, env names, account IDs, paths).
4. Checks error handling (no internals exposed in 401/403/500).
5. Checks CORS headers.
6. Checks connector presence flags (must not be visible to unauthenticated callers).
7. Checks destructive endpoints are auth-gated.
8. Produces PASS | HOLD per endpoint.

## Output
```
ENDPOINT SECURITY AUDIT
[N] endpoints reviewed
[method] [path]: PASS | HOLD
OVERALL: PASS | HOLD
REQUIRED FIXES (if HOLD): [exact endpoint and issue]
```

## Rules
- Reads actual route handler code — no assumptions.
- Does not make live HTTP calls (reads code only, unless Bryan scopes a live check).
