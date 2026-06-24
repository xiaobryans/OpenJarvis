# /fargate-proof

Generate a **structured Fargate/ECS runtime proof table** for sprint reports.

## Usage
```
/fargate-proof
/fargate-proof [expected-task-def-rev] [expected-image-sha]
```

## What this does
Runs the `openjarvis-fargate-runtime-proof` skill:
1. Queries ECS service status (cluster, service, running count, rollout state).
2. Queries task definition revision (image tag, secrets count).
3. Queries running task health (lastStatus, containerHealth).
4. Checks image tag against expected git commit SHA.
5. Checks secrets count (presence only — never prints values).
6. Checks ECS Exec availability.
7. Checks endpoint reachability if on Tailscale/VPN.
8. Produces structured proof table.

## Output
```
FARGATE RUNTIME PROOF
Task def rev: [N] — ACTIVE
Image tag: [sha] — MATCH
Secrets: [N] keys
Task health: RUNNING + HEALTHY
ECS Exec: ENABLED
Endpoint: HTTP 200, engine=cloud
VERDICT: HEALTHY | DEGRADED | HOLD
```

## Rules
- NEVER runs `aws secretsmanager get-secret-value`.
- Reports `NOT_REACHABLE` for endpoint if not on VPN — no fake HEALTHY.
- Only invokes ECS Exec if Bryan explicitly scopes a live run.
