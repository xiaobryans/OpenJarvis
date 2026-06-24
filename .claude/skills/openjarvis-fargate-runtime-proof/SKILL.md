---
name: openjarvis-fargate-runtime-proof
description: Generate a structured Fargate/ECS runtime proof table — task health, task def revision, image tag, secrets injection count, endpoint reachability. Presence-only secret reporting. Use when a sprint involves Fargate deployment or before acceptance review of any cloud-deployed sprint.
---

# OpenJarvis Fargate Runtime Proof

Generates a **structured proof table** of the current Fargate/ECS runtime state.

## When to use
- After any ECS deployment sprint.
- Before acceptance review of any sprint that changed the Fargate task definition.
- When Bryan asks for Fargate runtime proof.

## Inputs
- Expected task def revision (from session state or sprint report)
- Expected image tag / git commit SHA
- Expected secrets count in task definition

## Steps

1. **Query ECS service** — `aws ecs describe-services` → running task count, rollout state.
2. **Query task definition** — `aws ecs describe-task-definition` → revision, image tag, secrets count.
3. **Query running task** — `aws ecs describe-tasks` → lastStatus, containerHealth.
4. **Check image tag** — confirm image tag suffix matches expected git commit SHA.
5. **Check secrets count** — confirm number of `secrets` entries in task def matches expected count. Presence-only — never print ARN values or secret contents.
6. **Check ECS Exec** — confirm `enableExecuteCommand=true` if ECS Exec was set up.
7. **Endpoint check** (if Tailscale/VPN available) — `curl -s /health` → HTTP status, `engine`, `git_commit`. Report `NOT_REACHABLE` if not on VPN.
8. **S3 env var** — confirm `OMNIX_WORKBENCH_MEMORY_BUCKET` is in task def environment (presence only).

## Safe commands
```bash
aws ecs describe-services --cluster [cluster] --services [service] --query 'services[0].{status:status,running:runningCount,desired:desiredCount,rollout:deployments[0].rolloutState}'
aws ecs describe-task-definition --task-definition [name] --query 'taskDefinition.{rev:revision,image:containerDefinitions[0].image,secretsCount:length(secrets)}'
aws ecs describe-tasks --cluster [cluster] --tasks [task-arn] --query 'tasks[0].{status:lastStatus,health:healthStatus}'
```

## Forbidden commands
- `aws secretsmanager get-secret-value` — NEVER (prints secrets)
- `aws ecs execute-command` — only if Bryan explicitly scopes a live ECS Exec run

## Output
```
FARGATE RUNTIME PROOF
[structured proof table from fargate-runtime-verifier agent]
```
