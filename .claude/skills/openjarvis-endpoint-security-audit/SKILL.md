---
name: openjarvis-endpoint-security-audit
description: Audit all public OpenJarvis API endpoints for auth gate enforcement, field leakage, error safety, and CORS correctness. Read the actual route handlers — do not assume. Produces PASS | HOLD per endpoint. Use before acceptance review or when new endpoints are added.
---

# OpenJarvis Endpoint Security Audit

Audits all public OpenJarvis API endpoints for security safety.

## When to use
- Before acceptance review.
- After any sprint that adds or modifies API routes.
- When Bryan asks for an endpoint security audit.

## Files to read
- `src/openjarvis/server/plan2_routes.py`
- `src/openjarvis/server/routes.py` (if exists)
- Any new route files added in this sprint

## Steps

1. **List all endpoints** — grep for `@router.get`, `@router.post`, `@router.delete`, `@app.get`, etc.
2. **For each endpoint** — invoke `endpoint-security-smoke-runner` agent logic:
   - Check auth gate: `Authorization: Bearer` check before data access.
   - Check response schema: no token presence, env names, account IDs, local paths.
   - Check error handling: 401/403/500 must not expose internals.
   - Check CORS: no wildcard on auth-gated routes.
3. **Verify connector presence flags** — no connector endpoint exposes `configured: true/false` to unauthenticated callers.
4. **Verify destructive endpoints** — `POST/DELETE` on mutation endpoints must be auth-gated.

## Safe commands
```bash
grep -n '@router\.\|@app\.' src/openjarvis/server/plan2_routes.py | head -50
grep -n 'Authorization\|bearer\|auth_token\|get_current_user' src/openjarvis/server/plan2_routes.py | head -30
grep -n 'token_present\|configured\|is_set\|env_var' src/openjarvis/server/plan2_routes.py | head -20
```

## Output
```
ENDPOINT SECURITY AUDIT
[structured output from endpoint-security-smoke-runner agent]
```
